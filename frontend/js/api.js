// [API] 백엔드 서버와의 통신을 담당하는 모듈

// 백엔드가 프론트도 같이 서빙하므로(main.py의 StaticFiles 마운트), 페이지가 열린 주소를 그대로 사용한다.
// localhost/127.0.0.1 등 접속 방식이 달라도 항상 같은 origin으로 요청이 나가 CORS 문제가 생기지 않는다.
const API_BASE = window.location.origin;

/**
 * 이미지 식재료 예측 API 호출 함수
 * @param {File[]} images - 업로드할 이미지 파일 배열 (multipart/form-data)
 * @returns {Promise<Object>} API 응답 데이터
 */
async function predictIngredients(images) {
    const formData = new FormData();
    
    // 복수 이미지 파일을 'images' 필드명으로 담기
    images.forEach((image) => {
        formData.append('images', image);
    });

    try {
        const response = await fetch(`${API_BASE}/api/ingredients/predict`, {
            method: 'POST',
            body: formData,
        });

        const data = await response.json();

        // 요청 실패 시 공통 오류 형태로 throw
        if (!response.ok) {
            throw {
                code: data.code || response.status,
                message: data.message || '서버 통신 중 오류가 발생했습니다.',
                details: data.details || null
            };
        }

        return data;
    } catch (error) {
        // 네트워크 오류 등 예외 발생 시 공통 오류 형태로 가공 후 전달
        throw {
            code: error.code || 500,
            message: error.message || '네트워크 연결을 확인해주세요.',
            details: error.details || null
        };
    }
}

/**
 * 영양 분석 API 호출 함수
 * @param {Object} payload - { profile: { gender, age }, ingredients: [{ ingredient_id, name, serving_g }] }
 * @returns {Promise<Object>} API 응답 데이터 ({ per_ingredient, summary, deficient_supplements })
 */
async function analyzeNutrition(payload) {
    try {
        const response = await fetch(`${API_BASE}/api/nutrition/analyze`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(payload),
        });

        const data = await response.json();

        // 요청 실패 시 공통 오류 형태로 throw
        if (!response.ok) {
            throw {
                code: data.code || response.status,
                message: data.message || '서버 통신 중 오류가 발생했습니다.',
                details: data.details || null
            };
        }

        return data;
    } catch (error) {
        // 네트워크 오류 등 예외 발생 시 공통 오류 형태로 가공 후 전달
        throw {
            code: error.code || 500,
            message: error.message || '네트워크 연결을 확인해주세요.',
            details: error.details || null
        };
    }
}

/**
 * 레시피 추천 API 호출 함수
 * @param {Object} payload - { ingredients: string[], deficient_nutrients: string[], mode: 'owned_first'|'nutrition_supplement' }
 * @returns {Promise<Object>} API 응답 데이터 ({ recipe_mode, recipes })
 */
async function recommendRecipes(payload) {
    try {
        const response = await fetch(`${API_BASE}/api/recipes/recommend`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(payload),
        });

        const data = await response.json();

        // 요청 실패 시 공통 오류 형태로 throw
        if (!response.ok) {
            throw {
                code: data.code || response.status,
                message: data.message || '서버 통신 중 오류가 발생했습니다.',
                details: data.details || null
            };
        }

        return data;
    } catch (error) {
        // 네트워크 오류 등 예외 발생 시 공통 오류 형태로 가공 후 전달
        throw {
            code: error.code || 500,
            message: error.message || '네트워크 연결을 확인해주세요.',
            details: error.details || null
        };
    }
}

// nutrition.js, recipes.js 등 다른 모듈에서 api.xxx() 형태로 호출할 수 있도록 네임스페이스로도 노출한다.
const api = {
    predictIngredients,
    analyzeNutrition,
    recommendRecipes
};