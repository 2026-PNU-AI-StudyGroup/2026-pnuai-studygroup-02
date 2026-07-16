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