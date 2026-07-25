// [NUTRITION] 근영 담당. 한국어 주석 필수
// 영양 분석 요청 처리 및 막대그래프 렌더링을 담당하는 모듈

/**
 * [NUTRITION] id='nutrition-bars' 영역에 영양소 막대그래프를 렌더링할 자릿값 함수
 * @param {Object} nutritionData - 영양 분석 결과 데이터
 */
function renderNutritionBars(nutritionData) {
    const container = document.getElementById('nutrition-bars');
    if (!container) return;

    // TODO: 다음 주 실제 UI 디자인 및 CSS 차트 연동 시 확장 예정
    console.log('[NUTRITION] 영양소 막대그래프 렌더링 호출:', nutritionData);

    // [NUTRITION] 임시 테스트용 영역 표시 (Mock 응답 확인용)
    container.innerHTML = `
        <div class="nutrition-mock-box" style="padding: 12px; border: 1px dashed #4CAF50; border-radius: 8px; margin-top: 10px; background-color: #f9fbf9;">
            <p style="margin: 0 0 8px 0; color: #2E7D32;"><strong>📊 영양 분석 결과 (Mock 막대그래프 렌더링 영역)</strong></p>
            <pre style="font-size: 12px; background: #ffffff; padding: 8px; border: 1px solid #e0e0e0; border-radius: 4px; overflow-x: auto;">${JSON.stringify(nutritionData, null, 2)}</pre>
        </div>
    `;
}

// [NUTRITION] appState.profile.gender('male'/'female')를 백엔드가 요구하는 '남'/'여'로 변환한다.
const GENDER_TO_BACKEND = {
    male: '남',
    female: '여'
};

// [NUTRITION] serving_g(실제 섭취량) 입력 UI가 아직 없으므로 nutrition.csv 기준량인 100g을 기본값으로 사용한다.
const DEFAULT_SERVING_G = 100;

/**
 * [NUTRITION] 영양 분석 실행 함수 (api.analyzeNutrition 호출)
 */
async function handleNutritionAnalysis() {
    console.log('[NUTRITION] 영양 분석 API 요청 시작...');

    try {
        // [NUTRITION] 백엔드 AnalyzeRequest 스키마
        // ({ profile: { gender, age }, ingredients: [{ ingredient_id, name, serving_g }] })에 맞춰 변환한다.
        const payload = {
            profile: {
                gender: GENDER_TO_BACKEND[appState.profile.gender] || appState.profile.gender,
                age: appState.profile.age
            },
            ingredients: appState.recognized.map((item, index) => ({
                ingredient_id: item.image_id || `manual_${index}`,
                name: item.name,
                serving_g: DEFAULT_SERVING_G
            }))
        };

        // api.js의 analyzeNutrition 함수 호출 (현재 Mock 응답 반환)
        const response = await api.analyzeNutrition(payload);

        console.log('[NUTRITION] 영양 분석 응답 성공:', response);

        // [NUTRITION] 전역 상태 업데이트 및 막대그래프 렌더링
        appState.nutrition = response;
        appState.stage = 'analyzed';

        renderNutritionBars(response);

    } catch (error) {
        console.error('[NUTRITION] 영양 분석 요청 실패:', error);
        alert(error.message || '영양 분석 처리 중 오류가 발생했습니다.');
    }
}

// [NUTRITION] analyze-btn 클릭 이벤트 연결
document.addEventListener('DOMContentLoaded', () => {
    const analyzeBtn = document.getElementById('analyze-btn');

    if (analyzeBtn) {
        analyzeBtn.addEventListener('click', async () => {
            // [NUTRITION] 분석 자격 조건(프로필 완료 + 확정 재료 1개 이상) 재검증
            if (typeof canAnalyze === 'function' && !canAnalyze()) {
                alert('프로필 작성과 최소 1개 이상의 식재료 등록이 필요합니다.');
                return;
            }

            await handleNutritionAnalysis();
        });
    }
});