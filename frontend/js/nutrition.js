// [NUTRITION] 근영 담당. 한국어 주석 필수
// 영양 분석 요청 처리 및 막대그래프 렌더링을 담당하는 모듈

// [NUTRITION] 충족률 상태별 막대 색상
const NUTRITION_STATUS_COLORS = {
    '높음': '#22c55e',
    '보통': '#f59e0b',
    '낮음': '#ef4444'
};

// [NUTRITION] 상태 문자열 -> 배지 CSS 클래스
const NUTRITION_STATUS_BADGE_CLASS = {
    '높음': 'status-high',
    '보통': 'status-mid',
    '낮음': 'status-low'
};

// [NUTRITION] 영양소 표시 단위
const NUTRIENT_UNITS = {
    calories_kcal: 'kcal',
    carbohydrate_g: 'g',
    protein_g: 'g',
    fat_g: 'g',
    calcium_mg: 'mg',
    iron_mg: 'mg',
    vitamin_c_mg: 'mg'
};

// [NUTRITION] 칼로리는 오른쪽에 별도 강조 카드로 빼고, 나머지 영양소만 막대그래프로 보여준다.
const NUTRITION_CALORIE_KEY = 'calories_kcal';

/**
 * [NUTRITION] id='nutrition-bars' 영역을 [막대그래프(좌) | 칼로리 강조 카드(우)]로 나눠 렌더링한다.
 * @param {Object} nutritionData - 영양 분석 결과 데이터 ({ summary, ... })
 */
function renderNutritionBars(nutritionData) {
    const container = document.getElementById('nutrition-bars');
    if (!container) return;

    const summary = nutritionData.summary || [];

    if (summary.length === 0) {
        container.innerHTML = '<p class="placeholder-text">영양 분석 결과가 없습니다.</p>';
        return;
    }

    const calorieRow = summary.find((row) => row.nutrient === NUTRITION_CALORIE_KEY);
    const barRows = summary.filter((row) => row.nutrient !== NUTRITION_CALORIE_KEY);

    // 1. 칼로리를 제외한 나머지 영양소: 막대그래프
    const barsHTML = barRows.map((row) => {
        const label = NUTRIENT_LABELS[row.nutrient] || row.nutrient;
        const barWidth = Math.min(row.percentage, 100);
        const color = NUTRITION_STATUS_COLORS[row.status] || '#868e96';

        return `
            <div class="nutrition-bar-row">
                <div class="nutrition-bar-label">
                    <span>${label}</span>
                    <span>${row.percentage}% (${row.status})</span>
                </div>
                <div class="nutrition-bar-track">
                    <div class="nutrition-bar-fill" style="width: ${barWidth}%; background-color: ${color};"></div>
                </div>
            </div>
        `;
    }).join('');

    // 2. 칼로리: 권장량 대비 퍼센트를 강조하는 카드
    const calorieHTML = calorieRow
        ? `
            <div class="nutrition-calorie-card">
                <div class="nutrition-calorie-icon">🔥</div>
                <div class="nutrition-calorie-label">칼로리</div>
                <div class="nutrition-calorie-value">${calorieRow.total}<small>${NUTRIENT_UNITS[NUTRITION_CALORIE_KEY]}</small></div>
                <span class="nutrition-calorie-badge ${NUTRITION_STATUS_BADGE_CLASS[calorieRow.status] || ''}">
                    권장량 대비 ${calorieRow.percentage}% (${calorieRow.status})
                </span>
            </div>
        `
        : '';

    container.innerHTML = `
        <div class="nutrition-summary-split">
            <div class="nutrition-bars-wrap">${barsHTML}</div>
            ${calorieHTML}
        </div>
    `;
}

// [NUTRITION] backend/services/nutrition_service.py의 NUTRIENT_KEYS와 동일한 키를 화면 표시용
// 한글 라벨로 매핑한다. (백엔드에 공식 매핑이 없어 프론트 표시 전용으로만 사용, API 요청에는 쓰지 않는다)
const NUTRIENT_LABELS = {
    calories_kcal: '칼로리',
    carbohydrate_g: '탄수화물',
    protein_g: '단백질',
    fat_g: '지방',
    calcium_mg: '칼슘',
    iron_mg: '철분',
    vitamin_c_mg: '비타민C'
};

/**
 * [NUTRITION] id='deficient-cards' 영역에 부족 영양소 및 보완 재료 카드를 렌더링한다.
 * @param {Object} nutritionData - handleNutritionAnalysis 응답 ({ summary, deficient_supplements })
 */
function renderDeficientCards(nutritionData) {
    const container = document.getElementById('deficient-cards');
    if (!container) return;

    const summary = nutritionData.summary || [];
    const deficientRows = summary.filter((row) => row.status === '낮음');

    if (deficientRows.length === 0) {
        container.innerHTML = '<p class="placeholder-text">부족한 영양소가 없습니다.</p>';
        return;
    }

    const cardsHTML = deficientRows.map((row) => {
        const label = NUTRIENT_LABELS[row.nutrient] || row.nutrient;
        return `
            <div class="deficient-card">
                <div class="deficient-card-icon">⚠️</div>
                <div class="deficient-card-body">
                    <div class="deficient-card-label">${label}</div>
                    <div class="deficient-card-percentage">권장량 대비 ${row.percentage}%</div>
                    <div class="deficient-card-detail">${row.total} / ${row.recommended}</div>
                </div>
            </div>
        `;
    }).join('');

    const supplements = nutritionData.deficient_supplements || [];
    const supplementsHTML = supplements.length > 0
        ? `
            <div class="deficient-supplements">
                <strong>🛒 보완 추천 재료</strong>
                <div class="supplement-chips">
                    ${supplements.map((name) => `<span class="supplement-chip">${name}</span>`).join('')}
                </div>
            </div>
        `
        : '';

    container.innerHTML = `
        <div class="deficient-cards-grid">${cardsHTML}</div>
        ${supplementsHTML}
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

    // [NUTRITION] 백엔드 IngredientInput.name은 필수 문자열이라, 인식 실패(name=null)한 항목을
    // 그대로 보내면 요청 전체가 422로 거부된다. 분석 대상에서 미리 제외한다.
    const validItems = appState.recognized.filter(item => !!item.name);
    const failedCount = appState.recognized.length - validItems.length;

    if (failedCount > 0) {
        alert(`${failedCount}개의 식재료는 인식에 실패해 영양 분석에서 제외됩니다.`);
    }

    if (validItems.length === 0) {
        alert('영양 분석이 가능한 식재료가 없습니다. 인식에 성공한 재료가 없습니다.');
        return;
    }

    try {
        // [NUTRITION] 백엔드 AnalyzeRequest 스키마
        // ({ profile: { gender, age }, ingredients: [{ ingredient_id, name, serving_g }] })에 맞춰 변환한다.
        const payload = {
            profile: {
                gender: GENDER_TO_BACKEND[appState.profile.gender] || appState.profile.gender,
                age: appState.profile.age
            },
            ingredients: validItems.map((item, index) => ({
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
        renderDeficientCards(response);

    } catch (error) {
        console.error('[NUTRITION] 영양 분석 요청 실패:', error);

        // app.js에 정의된 공통 전역 에러 배너를 호출하여 공유
        if (typeof app !== 'undefined' && typeof app.showCommonError === 'function') {
            app.showCommonError(error.message || '영양 분석 처리 중 오류가 발생했습니다.');
        }
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