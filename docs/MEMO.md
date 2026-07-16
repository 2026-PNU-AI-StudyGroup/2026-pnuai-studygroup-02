# ⚙️ js/state.js 필드 구조 확정 및 협업 가이드 (7/17~21 부재 전 확정)

근영의 부재 기간(7/17 ~ 7/21) 동안 현지·시은님이 Mock 데이터 및 모델을 차질 없이 개발할 수 있도록 확정된 `js/state.js` 상태 관리 구조, 프론트엔드 이미지 업로드 흐름, 그리고 API 협업 가이드를 이 한 페이지에 통째로 정리해 둡니다.

---

## 1. frontend/js/state.js (전역 상태 관리 확정)

```javascript
// [STATE] 근영 담당. 상태 필드 변경 시 다른 팀원에게 먼저 알릴 것

/**
 * 전역 애플리케이션 상태 객체 (단일 소스)
 * 7/17~21 부재 전 확정한 구조입니다. 현지, 시은님은 이 구조를 기준으로 Mock을 구성해주세요.
 */
const appState = {
    // [프로필 정보] 성별 및 나이 정보 관리
    profile: {
        gender: null, // 'male' | 'female' | null (토글 값)
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
 * 이미지 파일을 받아 상태에 추가하고 프리뷰용 URL을 생성하는 함수
 */
function addImage(file) {
    const imageId = 'img_' + Date.now() + '_' + Math.random().toString(36).substr(2, 5);
    const previewUrl = URL.createObjectURL(file);
    
    const newImage = {
        image_id: imageId,
        file: file,
        previewUrl: previewUrl
    };
    
    appState.images.push(newImage);
    
    if (appState.stage === 'idle') {
        appState.stage = 'uploaded';
    }
    
    return newImage;
}

/**
 * imageId를 기준으로 상태 내의 이미지와 리소스를 해제하는 함수
 */
function removeImage(imageId) {
    const targetIndex = appState.images.findIndex(img => img.image_id === imageId);
    if (targetIndex !== -1) {
        URL.revokeObjectURL(appState.images[targetIndex].previewUrl);
        appState.images.splice(targetIndex, 1);
    }
    
    if (appState.images.length === 0) {
        appState.stage = 'idle';
    }
}

/**
 * 해당 이미지의 식재료 인식 결과를 수정하는 함수
 */
function updateIngredient(imageId, newName) {
    const target = appState.recognized.find(item => item.image_id === imageId);
    if (target) {
        target.name = newName;
        target.edited = true;
    }
    
    // 데이터가 변경되면 기존 분석/추천 결과는 강제 초기화
    appState.nutrition = null;
    appState.recipes = null;
    
    if (appState.stage === 'analyzed' || appState.stage === 'recommended') {
        appState.stage = 'confirmed';
    }
}

/**
 * 사진과 인식 결과를 동시에 삭제하는 함수 (동기화)
 */
function removeIngredient(imageId) {
    appState.images = appState.images.filter(img => img.image_id !== imageId);
    appState.recognized = appState.recognized.filter(rec => rec.image_id !== imageId);
    
    appState.nutrition = null;
    appState.recipes = null;
    
    if (appState.images.length === 0) {
        appState.stage = 'idle';
    }
}

/**
 * 이미지 없이 텍스트로만 식재료를 수동 추가하는 함수
 */
function addManualIngredient(name) {
    const manualId = 'manual_' + Date.now();
    
    appState.recognized.push({
        image_id: manualId,
        name: name,
        confidence: 100, // 직접 입력은 신뢰도 100% 취급
        candidates: [],
        edited: true
    });
    
    appState.nutrition = null;
    appState.recipes = null;
}

/**
 * 영양 분석 시작 가능 여부 판별 함수
 */
function canAnalyze() {
    const hasProfile = appState.profile.gender !== null && appState.profile.age !== null && appState.profile.age > 0;
    const hasIngredients = appState.recognized.length > 0;
    return hasProfile && hasIngredients;
}

/**
 * 레시피 추천 시작 가능 여부 판별 함수
 */
function canRecommend() {
    return appState.nutrition !== null;
}