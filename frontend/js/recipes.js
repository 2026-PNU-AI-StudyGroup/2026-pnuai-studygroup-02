// [RECIPES] 근영 담당. 한국어 주석 필수
// 맞춤형 레시피 추천 API 연동 및 데이터 동적 화면 렌더링

document.addEventListener('DOMContentLoaded', () => {
    const recommendBtn = document.getElementById('recommend-btn');
    const recipeCardsContainer = document.getElementById('recipe-cards');

    if (!recommendBtn || !recipeCardsContainer) {
        console.error('[RECIPES] 필수 DOM 요소를 찾을 수 없습니다.');
        return;
    }

    // 맞춤형 레시피 추천받기 버튼 클릭 이벤트
    recommendBtn.addEventListener('click', async () => {
        try {
            // 사용자 경험을 위해 로딩 상태 문구 표시
            recipeCardsContainer.innerHTML = '<div class="loading-text">인공지능이 영양소 맞춤형 레시피를 생성하고 있습니다...</div>';

            // api.js에 정의된 레시피 추천 API 호출
            const response = await api.recommendRecipes();
            
            if (!response || !response.recipes) {
                throw new Error('유효하지 않은 레시피 응답 데이터 구조입니다.');
            }

            const { recipe_mode, recipes } = response;

            // 기존에 있던 대기 상태 텍스트 초기화
            recipeCardsContainer.innerHTML = '';

            // 1. 받아온 레시피 목록 배열 순회하며 카드 렌더링
            recipes.forEach(recipe => {
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

                // 카드 바디 구성 (레시피명, 추천이유, 보유재료, 추가재료, 조리순서 일괄 주입)
                card.innerHTML = `
                    <h3 class="recipe-title">${recipe.recipe_name || '이름 없는 레시피'}</h3>
                    <p class="recipe-reason"><strong>추천 이유:</strong> ${recipe.reason || 'N/A'}</p>
                    
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
                    
                    <div class="recipe-steps-wrap">
                        <h4>조리 순서 안내</h4>
                        <ol>${stepsHTML}</ol>
                    </div>
                `;
                recipeCardsContainer.appendChild(card);
            });

            // 2. recipe_mode가 'llm'(데이터베이스 외부 생성)일 경우 출처 없음 경고 배너 렌더링
            if (recipe_mode === 'llm') {
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
            }

        } catch (error) {
            console.error('[RECIPES] 레시피 처리 실패:', error);
            // 에러 발생 시 app.js에 선언된 공통 전역 에러 배너를 호출하여 공유
            if (typeof app !== 'undefined' && typeof app.showCommonError === 'function') {
                app.showCommonError('레시피 데이터를 불러오지 못했습니다. 서버 상태를 확인해 주세요.');
            }
        }
    });
});