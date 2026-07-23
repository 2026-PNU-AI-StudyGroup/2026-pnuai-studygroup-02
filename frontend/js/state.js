// [STATE] 근영 담당. 상태 필드 변경 시 다른 팀원에게 먼저 알릴 것

/**
 * 전역 애플리케이션 상태 객체 (단일 소스)
 * 7/17~21 부재 전 확정한 구조입니다. 현지, 시은님은 이 구조를 기준으로 Mock을 구성해주세요.
 */
const appState = {
    // [프로필 정보] 성별 및 나이 정보 관리
    profile: {
        gender: null, // 'male' | 'female' | null
        age: null     // number | null
    },
    
    // [업로드 이미지] 사용자가 업로드한 원본 파일 및 프리뷰 URL 목록
    // 구조: { image_id: string, file: File, previewUrl: string }
    images: [],
    
    // [인식 결과] AI가 이미지에서 식별한 식재료 및 사용자 수정 데이터
    // 구조: { image_id: string, name: string, confidence: number, candidates: string[], edited: boolean }
    recognized: [],
    
    // [영양 분석] 백엔드로부터 받은 영양소 충족률 및 부족 영양소 정보
    nutrition: null,
    
    // [레시피 추천] 추천된 레시피 카드 목록
    recipes: null,
    
    // [앱 진행 단계] 
    // 'idle' -> 'uploaded' -> 'recognized' -> 'confirmed' -> 'analyzed' -> 'recommended'
    stage: 'idle'
};

/**
 * 이미지 파일을 받아 상태에 추가하고 프리뷰 URL을 생성하는 함수
 * @param {File} file - 업로드된 이미지 파일 객체
 * @returns {Object} 추가된 이미지 객체 정보
 */
function addImage(file) {
    // 중복 방지 및 고유 식별을 위해 타임스탬프와 랜덤값을 조합한 ID 생성
    const imageId = 'img_' + Date.now() + '_' + Math.random().toString(36).substr(2, 5);
    const previewUrl = URL.createObjectURL(file);
    
    const newImage = {
        image_id: imageId,
        file: file,
        previewUrl: previewUrl
    };
    
    appState.images.push(newImage);
    
    // 이미지가 하나라도 등록되면 스테이지 변경
    if (appState.stage === 'idle') {
        appState.stage = 'uploaded';
    }
    return newImage;
}

/**
 * imageId를 기준으로 상태 내의 이미지와 리소스를 해제하는 함수
 * @param {string} imageId - 삭제할 이미지의 고유 ID
 */
function removeImage(imageId) {
    const targetIndex = appState.images.findIndex(img => img.image_id === imageId);
    
    if (targetIndex !== -1) {
        // 메모리 누수 방지를 위해 브라우저에 생성되어 있던 ObjectURL 메모리 해제
        URL.revokeObjectURL(appState.images[targetIndex].previewUrl);
        
        // 상태 배열에서 삭제
        appState.images.splice(targetIndex, 1);
    }
    
    // 등록된 이미지가 없으면 앱 상태를 다시 대기(idle)로 변경
    if (appState.images.length === 0) {
        appState.stage = 'idle';
    }
}

// ==========================================
// [STATE] 추가 요구사항 및 보완 함수들
// ==========================================

/**
 * [STATE] 프로필 설정 완료 여부를 확인한다.
 * @returns {boolean}
 */
function isProfileComplete() {
    return !!(appState.profile.gender && appState.profile.age);
}

/**
 * [STATE] 프로필 완료 + 확정 재료 1개 이상일 때 analyze-btn disabled 상태를 자동 갱신한다.
 * @returns {boolean} 분석 가능 여부
 */
function canAnalyze() {
    const hasIngredients = appState.recognized.length > 0;
    const profileReady = isProfileComplete();
    const canDo = profileReady && hasIngredients;

    // analyze-btn 활성화/비활성화 제어
    const analyzeBtn = document.getElementById('analyze-btn');
    if (analyzeBtn) {
        analyzeBtn.disabled = !canDo;
    }

    return canDo;
}

/**
 * [STATE] 해당 이미지의 인식 결과를 수정하고 영양/레시피 결과를 null로 초기화한다.
 * @param {string} imageId - 수정할 식재료의 image_id
 * @param {string} newName - 새 식재료 이름
 */
function updateIngredient(imageId, newName) {
    const target = appState.recognized.find(item => item.image_id === imageId);
    if (target) {
        target.name = newName;
        target.edited = true;

        // 재료 수정 시 영양/레시피 결과 초기화
        appState.nutrition = null;
        appState.recipes = null;

        canAnalyze();
        console.log(`[STATE] 식재료 수정 완료 (imageId: ${imageId} -> ${newName})`);
    }
}

/**
 * [STATE] 사진(images)과 인식 결과(recognized)를 동시에 삭제하고 결과를 초기화한다.
 * @param {string} imageId - 삭제할 image_id
 */
function removeIngredient(imageId) {
    // 1. 원본 이미지 리소스 메모리 해제 및 images 배열에서 삭제
    removeImage(imageId);

    // 2. recognized (인식 결과) 배열에서 동시 제거
    appState.recognized = appState.recognized.filter(item => item.image_id !== imageId);

    // 3. 영양 및 레시피 결과 초기화
    appState.nutrition = null;
    appState.recipes = null;

    canAnalyze();
    console.log(`[STATE] 사진 및 인식 결과 삭제 완료 (imageId: ${imageId})`);
}

/**
 * [STATE] image_id 없이 수동으로 식재료를 목록에 추가한다.
 * @param {string} name - 식재료 이름
 */
function addManualIngredient(name) {
    if (!name || !name.trim()) return;

    const manualItem = {
        image_id: null, // 수동 추가는 image_id 없음
        name: name.trim(),
        confidence: 1.0,
        candidates: [],
        edited: true
    };

    appState.recognized.push(manualItem);

    // 영양 및 레시피 결과 초기화
    appState.nutrition = null;
    appState.recipes = null;

    // 식재료가 하나라도 생겼으므로 스테이지 갱신 (idle/uploaded -> confirmed)
    if (appState.stage === 'idle' || appState.stage === 'uploaded') {
        appState.stage = 'confirmed';
    }

    canAnalyze();
    console.log(`[STATE] 수동 식재료 추가 완료: ${name.trim()}`);
}

// [STATE] DOM 로드 완료 시 버튼 연동 및 초기 상태 설정
document.addEventListener('DOMContentLoaded', () => {
    // id='add-ingredient-btn' 버튼 이벤트 연결
    const addBtn = document.getElementById('add-ingredient-btn');
    const inputEl = document.getElementById('manual-ingredient-input');

    if (addBtn) {
        addBtn.addEventListener('click', () => {
            const name = inputEl ? inputEl.value : prompt('추가할 식재료 이름을 입력하세요:');
            if (name) {
                addManualIngredient(name);
                if (inputEl) inputEl.value = '';
            }
        });
    }

    // 초기 버튼 활성화 여부 계산
    canAnalyze();
});