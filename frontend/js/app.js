// [APP] 근영 담당. 한국어 주석 필수
// 애플리케이션 화면 섹션 초기화 및 전역 공통 에러 핸들링 시스템

const app = {
    // 0. 성별 토글 버튼을 생성하고, 클릭 시 appState.profile.gender를 갱신한다.
    //    백엔드(profile.py/nutrition.py)가 '남'/'여' 문자열을 그대로 요구하므로 값도 '남'/'여'로 저장한다.
    initGenderToggle() {
        const container = document.getElementById('gender-toggle');
        if (!container) return;

        const GENDER_OPTIONS = [
            { value: '남', label: '남성' },
            { value: '여', label: '여성' }
        ];

        container.innerHTML = '';
        Object.assign(container.style, {
            display: 'flex',
            gap: '12px',
            justifyContent: 'center'
        });

        const updateActiveStyles = () => {
            container.querySelectorAll('.gender-option-btn').forEach((btn) => {
                const isActive = btn.dataset.value === appState.profile.gender;
                btn.style.backgroundColor = isActive ? 'var(--primary-color)' : '';
                btn.style.color = isActive ? '#ffffff' : '';
            });
        };

        GENDER_OPTIONS.forEach((option) => {
            const btn = document.createElement('button');
            btn.type = 'button';
            btn.textContent = option.label;
            btn.className = 'btn-secondary gender-option-btn';
            btn.dataset.value = option.value;

            btn.addEventListener('click', () => {
                appState.profile.gender = option.value;
                updateActiveStyles();

                if (typeof canAnalyze === 'function') {
                    canAnalyze();
                }
            });

            container.appendChild(btn);
        });

        updateActiveStyles();
    },

    // 0-1. 나이 입력값을 appState.profile.age에 반영한다.
    initAgeInput() {
        const ageInput = document.getElementById('age-input');
        if (!ageInput) return;

        ageInput.addEventListener('input', () => {
            const value = parseInt(ageInput.value, 10);
            appState.profile.age = Number.isNaN(value) ? null : value;

            if (typeof canAnalyze === 'function') {
                canAnalyze();
            }
        });
    },

    // 0-2. "레시피 추천 받기"/"분석 화면으로" 버튼으로 분석 화면 <-> 레시피 화면을 전환한다.
    //      실제 페이지 이동(URL 변경)이 아니라 같은 문서 안에서 두 섹션의 표시 여부만 바꾸는 방식이라
    //      appState(인식 결과·영양 분석 결과 등)가 그대로 유지된다.
    initViewSwitcher() {
        const viewAnalysis = document.getElementById('view-analysis');
        const viewRecipe = document.getElementById('view-recipe');
        const recommendBtn = document.getElementById('recommend-btn');
        const backBtn = document.getElementById('back-to-analysis-btn');

        if (!viewAnalysis || !viewRecipe) return;

        const showRecipeView = () => {
            viewAnalysis.hidden = true;
            viewRecipe.hidden = false;
            window.scrollTo(0, 0);
        };

        const showAnalysisView = () => {
            viewRecipe.hidden = true;
            viewAnalysis.hidden = false;
            window.scrollTo(0, 0);
        };

        // recipes.js가 같은 버튼에 실제 추천 API 호출 로직을 이미 연결해 두었으므로,
        // 여기서는 화면 전환만 추가로 연결한다(클릭 시 두 리스너가 함께 실행됨).
        if (recommendBtn) {
            recommendBtn.addEventListener('click', showRecipeView);
        }

        if (backBtn) {
            backBtn.addEventListener('click', showAnalysisView);
        }
    },

    // 1. 페이지 최초 로드 시 HTML 내부의 모든 유동 섹션을 대기 상태로 초기화 시키는 함수
    initSections() {
        console.log('[APP] HTML에 명시된 모든 섹션을 대기 상태로 초기화합니다.');
        
        // 이미지 업로드 대기 영역 초기화
        const previewList = document.getElementById('preview-list');
        if (previewList) {
            previewList.innerHTML = '<p class="placeholder-text">선택한 이미지 미리보기가 여기에 표시됩니다.</p>';
        }

        // 식재료 인식 결과 영역 초기화
        const resultCards = document.getElementById('result-cards');
        if (resultCards) {
            resultCards.innerHTML = '<p class="placeholder-text">인식된 식재료가 여기에 태그로 표시됩니다.</p>';
        }

        // 종합 영양 분석 그래프 영역 초기화
        const nutritionBars = document.getElementById('nutrition-bars');
        if (nutritionBars) {
            nutritionBars.innerHTML = '<p class="placeholder-text">칼로리, 탄수화물, 단백질, 지방 등 영양소 그래프가 여기에 표시됩니다.</p>';
        }

        // 부족한 영양소 분석 카드 영역 초기화
        const deficientCards = document.getElementById('deficient-cards');
        if (deficientCards) {
            deficientCards.innerHTML = '<p class="placeholder-text">나이와 성별 대비 부족한 영양소 카드가 여기에 표시됩니다.</p>';
        }

        // 최종 추천 레시피 구역 초기화
        const recipeCards = document.getElementById('recipe-cards');
        if (recipeCards) {
            recipeCards.innerHTML = '<p class="placeholder-text">부족한 영양소를 채워줄 추천 레시피가 여기에 표시됩니다.</p>';
        }
    },

    // 2. 프로젝트 내 모든 비동기 API 요청 실패 시 화면 최상단에 띄울 공통 오류 알림 배너
    showCommonError(message = '서버와의 통신이 원활하지 않습니다. 잠시 후 다시 시도해 주세요.') {
        // 기존에 이미 에러 배너가 떠 있다면 제거하여 중복 생성을 방지
        const existingBanner = document.getElementById('common-error-banner');
        if (existingBanner) {
            existingBanner.remove();
        }

        // 브라우저 최상단에 고정될 전역 에러 배너 엘리먼트 생성 및 배치
        const errorBanner = document.createElement('div');
        errorBanner.id = 'common-error-banner';
        
        // 화면 가장 상단에 띄우기 위한 뷰포트 고정 스타일링
        Object.assign(errorBanner.style, {
            position: 'fixed',
            top: '0',
            left: '0',
            width: '100%',
            backgroundColor: '#e63946',
            color: '#ffffff',
            textAlign: 'center',
            padding: '14px 24px',
            fontWeight: 'bold',
            fontSize: '15px',
            zIndex: '10000', // 다른 레이어 요소를 압도하도록 z-index 최상위 설정
            boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
            gap: '20px'
        });

        // 배너 내부 레이아웃 구성 및 우측 폐쇄(X) 버튼 추가
        errorBanner.innerHTML = `
            <span>⚠️ 시스템 오류 안내: ${message}</span>
            <button id="close-error-banner" style="background: rgba(255,255,255,0.2); border: 1px solid #fff; color: #fff; cursor: pointer; padding: 4px 10px; border-radius: 4px; font-size: 13px; transition: 0.2s;">창 닫기</button>
        `;

        // <body>의 가장 첫 번째 자식 노드로 삽입하여 강제 최상단 정렬
        document.body.insertBefore(errorBanner, document.body.firstChild);

        // 닫기 버튼 누르면 에러 배너가 즉시 휘발하도록 이벤트 연동
        document.getElementById('close-error-banner').addEventListener('click', () => {
            errorBanner.remove();
        });

        // 사용자가 명시적으로 닫지 않아도 7초 뒤 자연스럽게 사라지도록 타이머 정의
        setTimeout(() => {
            if (document.getElementById('common-error-banner')) {
                errorBanner.remove();
            }
        }, 7000);
    }
};

// DOM트리 생성이 완료되는 즉시 섹션 초기화 및 프로필 입력 UI 연동 메서드 가동
document.addEventListener('DOMContentLoaded', () => {
    app.initSections();
    app.initGenderToggle();
    app.initAgeInput();
    app.initViewSwitcher();
});
