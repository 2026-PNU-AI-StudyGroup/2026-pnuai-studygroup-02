// [RECIPES] 근영 담당. 한국어 주석 필수
// 맞춤형 레시피 추천 API 연동 및 데이터 동적 화면 렌더링

// [RECIPES] 레시피 카드 상단 장식용 아이콘 (백엔드가 이미지 URL을 제공하지 않아 실제 사진 대신 아이콘을 사용한다)
const RECIPE_CARD_ICONS = ['🍳', '🥘', '🍲', '🥗', '🍛', '🍜'];

/**
 * [RECIPES] 레시피 하나를 카드 엘리먼트로 만든다.
 * @param {Object} recipe - 백엔드 Recipe 스키마 ({ title, owned_ingredients, additional_ingredients, steps })
 * @param {number} index - 카드 아이콘을 다양하게 보여주기 위한 인덱스
 */
function buildRecipeCard(recipe, index) {
    const card = document.createElement('div');
    card.className = 'recipe-card'; // style.css 스타일 적용을 위한 클래스 선언

    // 보유 재료 목록 생성 (요구사항: ✅ 이모지 필수)
    const ownedHTML = recipe.owned_ingredients && recipe.owned_ingredients.length > 0
        ? recipe.owned_ingredients.map(ing => `<li>✅ ${ing}</li>`).join('')
        : '<li>보유 중인 필수 재료가 없습니다.</li>';

    // 추가 필요 재료 목록 생성 (요구사항: 🛒 이모지 필수)
    const additionalHTML = recipe.additional_ingredients && recipe.additional_ingredients.length > 0
        ? recipe.additional_ingredients.map(ing => `<li>🛒 ${ing}</li>`).join('')
        : '<li>추가로 구매할 재료가 없습니다.</li>';

    // 조리 순서(steps) 리스트 태그 생성
    const stepsHTML = recipe.steps && recipe.steps.length > 0
        ? recipe.steps.map((step, idx) => `<li>${idx + 1}. ${step}</li>`).join('')
        : '<li>조리 순서 정보가 제공되지 않았습니다.</li>';

    const icon = RECIPE_CARD_ICONS[index % RECIPE_CARD_ICONS.length];

    // 카드 바디 구성: 왼쪽(레시피명/재료), 오른쪽(조리순서)을 가로로 나란히 배치한다.
    // 백엔드 Recipe 스키마에는 title만 있고 reason/조리시간/난이도 필드는 없어 표시하지 않는다.
    card.innerHTML = `
        <div class="recipe-card-main">
            <div class="recipe-card-thumb">${icon}</div>
            <h3 class="recipe-title">${recipe.title || '이름 없는 레시피'}</h3>

            <div class="recipe-ingredients-wrap">
                <div class="ing-block">
                    <h4>내 냉장고 재료</h4>
                    <ul>${ownedHTML}</ul>
                </div>
                <div class="ing-block">
                    <h4>필요한 추가 장보기 목록</h4>
                    <ul>${additionalHTML}</ul>
                </div>
            </div>
        </div>

        <div class="recipe-card-steps">
            <h4>조리 순서 안내</h4>
            <ol>${stepsHTML}</ol>
        </div>
    `;

    return card;
}

/**
 * [RECIPES] 레시피 목록을 "냉장고 재료로만 가능" / "추천(추가) 재료 필요"
 * 두 그룹으로 나눠 id='recipe-cards' 영역에 카드 그리드로 렌더링한다.
 * @param {Array} recipes - 백엔드 Recipe 배열
 * @param {HTMLElement} container
 */
function renderRecipeCards(recipes, container) {
    container.innerHTML = '';

    // additional_ingredients가 비어 있으면(=추가로 살 재료가 없으면) 냉장고 재료만으로 가능한 레시피다.
    const ownedOnlyRecipes = recipes.filter(
        recipe => !recipe.additional_ingredients || recipe.additional_ingredients.length === 0
    );
    const withExtraRecipes = recipes.filter(
        recipe => recipe.additional_ingredients && recipe.additional_ingredients.length > 0
    );

    const renderGroup = (title, description, groupRecipes) => {
        const groupSection = document.createElement('div');
        groupSection.className = 'recipe-group';

        const heading = document.createElement('h3');
        heading.className = 'recipe-group-title';
        heading.textContent = title;
        groupSection.appendChild(heading);

        const desc = document.createElement('p');
        desc.className = 'recipe-group-desc';
        desc.textContent = description;
        groupSection.appendChild(desc);

        if (groupRecipes.length === 0) {
            const empty = document.createElement('p');
            empty.className = 'placeholder-text';
            empty.textContent = '해당하는 레시피가 없습니다.';
            groupSection.appendChild(empty);
        } else {
            const grid = document.createElement('div');
            grid.className = 'recipe-cards-grid';
            groupRecipes.forEach((recipe, index) => grid.appendChild(buildRecipeCard(recipe, index)));
            groupSection.appendChild(grid);
        }

        container.appendChild(groupSection);
    };

    renderGroup(
        '🥬 내 냉장고 재료로만 가능한 레시피',
        '현재 보유한 재료만으로 만들 수 있는 레시피입니다.',
        ownedOnlyRecipes
    );
    renderGroup(
        '🛒 추천 재료가 들어간 레시피',
        '재료 몇 가지만 추가하면 만들 수 있는 레시피입니다.',
        withExtraRecipes
    );
}

document.addEventListener('DOMContentLoaded', () => {
    const recommendBtn = document.getElementById('recommend-btn');
    const recipeCardsContainer = document.getElementById('recipe-cards');

    if (!recommendBtn || !recipeCardsContainer) {
        console.error('[RECIPES] 필수 DOM 요소를 찾을 수 없습니다.');
        return;
    }

    // 맞춤형 레시피 추천받기 버튼 클릭 이벤트
    recommendBtn.addEventListener('click', async () => {
        // 인식 실패(name=null) 항목은 제외한다 (백엔드 RecipeRequest.ingredients는 최소 1개 필요).
        const validIngredientNames = (appState.recognized || [])
            .map(item => item.name)
            .filter(Boolean);

        if (validIngredientNames.length === 0) {
            alert('레시피를 추천받으려면 인식에 성공한 식재료가 1개 이상 있어야 합니다.');
            return;
        }

        try {
            // 사용자 경험을 위해 로딩 상태 문구 표시
            recipeCardsContainer.innerHTML = '<div class="loading-text">인공지능이 영양소 맞춤형 레시피를 생성하고 있습니다...</div>';

            // [RECIPES] 영양 분석에서 부족(status === '낮음')으로 판정된 영양소가 있으면
            // nutrition.js의 NUTRIENT_LABELS(영문 키 -> 한글명)로 변환해 nutrition_supplement 모드로 요청한다.
            // NUTRIENT_LABELS는 nutrition.js가 index.html에서 recipes.js보다 먼저 로드되어 전역으로 사용 가능하다.
            const summary = (appState.nutrition && appState.nutrition.summary) || [];
            const deficientNutrients = summary
                .filter(row => row.status === '낮음')
                .map(row => NUTRIENT_LABELS[row.nutrient] || row.nutrient);

            // [RECIPES] 체크된 기본 소스도 보유 재료로 취급해 백엔드에 함께 전달한다.
            // (LLM 프롬프트의 "사용자가 보유한 재료" 목록에 포함되어, 추가 구매 목록으로 빠지지 않는다)
            const pantryChecklist = document.getElementById('pantry-checklist');
            const checkedSeasonings = pantryChecklist
                ? Array.from(pantryChecklist.querySelectorAll('input[type="checkbox"]:checked')).map(cb => cb.value)
                : [];

            // 백엔드 RecipeRequest 스키마({ ingredients, deficient_nutrients, mode })에 맞춰 요청을 구성한다.
            const payload = {
                ingredients: [...validIngredientNames, ...checkedSeasonings],
                deficient_nutrients: deficientNutrients,
                mode: deficientNutrients.length > 0 ? 'nutrition_supplement' : 'owned_first'
            };

            // api.js에 정의된 레시피 추천 API 호출
            const response = await api.recommendRecipes(payload);

            if (!response || !response.recipes) {
                throw new Error('유효하지 않은 레시피 응답 데이터 구조입니다.');
            }

            const { recipes } = response;

            // [RECIPES] 전역 상태 업데이트 (state.js가 정의한 appState.recipes/stage 구조 반영)
            appState.recipes = recipes;
            appState.stage = 'recommended';

            // 1. 레시피 목록을 "냉장고 재료로만 가능" / "추천 재료 필요" 두 그룹으로 나눠 렌더링
            renderRecipeCards(recipes, recipeCardsContainer);

            // 2. 출처 없음 안내 배너 렌더링
            // 백엔드는 RAG를 사용하지 않아 모든 레시피의 sources가 항상 빈 배열이므로(recipe_mode와 무관),
            // 매번 LLM이 직접 생성한 레시피라는 안내를 띄운다.
            const noticeBanner = document.createElement('div');
            noticeBanner.className = 'recipe-llm-notice';

            // 직관적인 인라인 스타일 적용 (디자인 요구사항 반영)
            Object.assign(noticeBanner.style, {
                marginTop: '20px',
                padding: '12px',
                backgroundColor: '#fff3cd',
                border: '1px solid #ffeeba',
                color: '#856404',
                textAlign: 'center',
                borderRadius: '4px',
                fontWeight: '500'
            });
            noticeBanner.innerText = '출처 없음: LLM이 직접 생성한 레시피입니다';

            recipeCardsContainer.appendChild(noticeBanner);

        } catch (error) {
            console.error('[RECIPES] 레시피 처리 실패:', error);
            // 에러 발생 시 app.js에 선언된 공통 전역 에러 배너를 호출하여 공유
            if (typeof app !== 'undefined' && typeof app.showCommonError === 'function') {
                app.showCommonError('레시피 데이터를 불러오지 못했습니다. 서버 상태를 확인해 주세요.');
            }
        }
    });
});