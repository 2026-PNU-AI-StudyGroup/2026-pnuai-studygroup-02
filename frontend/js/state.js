// [STATE] 근영 담당. 상태 필드 변경 시 다른 팀원에게 먼저 알릴 것

/**
 * 전역 애플리케이션 상태 객체 (단일 소스)
 * 7/17~21 부재 전 확정한 구조입니다. 현지, 시은님은 이 구조를 기준으로 Mock을 구성해주세요.
 */
const appState = {
    // [프로필 정보] 성별 및 나이 정보 관리
    profile: {
        gender: null, // '남' | '여' | null (백엔드 profile.py/nutrition.py가 요구하는 값과 동일)
        age: null     // number | null
    },
    
    // [업로드 이미지] 사용자가 업로드한 원본 파일 및 프리뷰 URL 목록
    // 구조: { image_id: string, file: File, previewUrl: string }
    images: [],
    
    // [인식 결과] AI가 이미지에서 식별한 식재료 및 사용자 수정 데이터
    // [STATE] 근영 담당: servingG(기본값 100) 필드 추가
    // 구조: { image_id: string, name: string, confidence: number, candidates: string[], edited: boolean, servingG: number }
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
// [STATE] 추가 요구사항 및 보완 함수들 (근영 담당)
// ==========================================

/**
 * [STATE] 근영 담당. 프로필 설정 완료 여부를 확인한다.
 * @returns {boolean}
 */
function isProfileComplete() {
    return !!(appState.profile.gender && appState.profile.age);
}

/**
 * [STATE] 근영 담당. 프로필 완료 + 확정 재료 1개 이상일 때 analyze-btn disabled 상태를 자동 갱신한다.
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
 * [STATE] 근영 담당. 사진(images)과 인식 결과(recognized)를 동시에 삭제하고 결과를 초기화한다.
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
 * [STATE] 근영 담당. image_id 없이 수동으로 식재료를 목록에 추가한다.
 * @param {string} name - 식재료 이름
 * @param {number} [servingG=100] - 용량(g) (기본값 100)
 */
function addManualIngredient(name, servingG = 100) {
    if (!name || !name.trim()) return;

    const manualItem = {
        image_id: null, // 수동 추가는 image_id 없음
        name: name.trim(),
        confidence: 1.0,
        candidates: [],
        edited: true,
        servingG: Math.max(1, Number(servingG) || 100) // [STATE] 기본값 100g
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
    console.log(`[STATE] 수동 식재료 추가 완료: ${name.trim()} (${manualItem.servingG}g)`);
}

/**
 * [STATE] 근영 담당. 식재료 용량(servingG) 변경 함수 (범위 검증: 1~2000g)
 * @param {string|null} imageId - 변경할 식재료의 image_id (수동 추가 항목은 null 가능)
 * @param {number|string} grams - 변경할 용량(g)
 * @param {number} [index] - image_id가 null이거나 중복일 때 정확한 항목 지정을 위한 배열 인덱스
 * @returns {boolean} - 갱신 성공 여부
 */
function updateServingG(imageId, grams, index = null) {
    const parsedGrams = Number(grams);

    // [STATE] 범위 검증: 1~2000g 범위를 벗어나거나 숫자가 아니면 무시하고 오류 표시
    if (isNaN(parsedGrams) || parsedGrams < 1 || parsedGrams > 2000) {
        alert("식재료 용량은 1g 이상 2000g 이하로 입력해주세요.");
        console.warn(`[STATE] 용량 변경 실패 (범위 초과): ${grams}g`);
        return false;
    }

    // 대상 식재료 찾기 (인덱스가 지정되면 인덱스 우선, 없으면 imageId 검색)
    let targetItem = null;
    if (index !== null && index !== undefined && appState.recognized[index]) {
        targetItem = appState.recognized[index];
    } else {
        targetItem = appState.recognized.find(item => item.image_id === imageId);
    }

    if (targetItem) {
        targetItem.servingG = parsedGrams;

        // [STATE] servingG 변경 시 nutrition / recipes 결과를 null로 초기화 (기존 재료 변경 로직과 동일)
        appState.nutrition = null;
        appState.recipes = null;

        console.log(`[STATE] 용량 변경 완료 - name: ${targetItem.name}, servingG: ${parsedGrams}g`);
        return true;
    }

    return false;
}

/**
 * [STATE] 근영 담당. 기존 updateIngredientServing 함수와의 호환성을 위한 래퍼 함수 (인덱스 기준)
 * @param {number} index - appState.recognized 배열 내 인덱스
 * @param {number} grams - 변경할 용량(g)
 */
function updateIngredientServing(index, grams) {
    if (appState.recognized[index]) {
        const item = appState.recognized[index];
        updateServingG(item.image_id, grams, index);
    }
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

                // [STATE] 카드 목록도 함께 갱신한다 (renderResultCards는 upload.js에 정의됨).
                const resultCardsContainer = document.getElementById('result-cards');
                if (typeof renderResultCards === 'function' && resultCardsContainer) {
                    renderResultCards(appState.recognized, resultCardsContainer);
                }
            }
        });
    }

    // [STATE] id='rice-toggle-checkbox' 체크 시 쌀을 수동 재료로 추가/제거한다.
    // 이미지 인식 모델이 쌀을 학습하지 않아 사진으로는 인식이 안 되므로 별도 체크박스로 지원한다.
    const riceCheckbox = document.getElementById('rice-toggle-checkbox');

    if (riceCheckbox) {
        riceCheckbox.addEventListener('change', () => {
            if (riceCheckbox.checked) {
                const alreadyAdded = appState.recognized.some(item => item.name === '쌀');
                if (!alreadyAdded) {
                    addManualIngredient('쌀');
                }
            } else {
                appState.recognized = appState.recognized.filter(item => item.name !== '쌀');
                appState.nutrition = null;
                appState.recipes = null;
                canAnalyze();
            }

            const resultCardsContainer = document.getElementById('result-cards');
            if (typeof renderResultCards === 'function' && resultCardsContainer) {
                renderResultCards(appState.recognized, resultCardsContainer);
            }
        });
    }

    // 초기 버튼 활성화 여부 계산
    canAnalyze();
});