// [API] 근영 담당. serving_g, sources 필드명은 역할분담 계약 참고. 한국어 주석 필수
// 백엔드 서버와의 통신을 담당하는 모듈

const API_BASE = window.location.origin;

/**
 * 이미지 식재료 예측 API 호출 함수
 * @param {File[]} images - 업로드할 이미지 파일 배열 (multipart/form-data)
 * @param {Array<{ingredient_id?: string, name?: string, serving_g: number}>} [ingredientsData] - 식재료 별 용량(serving_g) 정보
 * @returns {Promise<Object>} API 응답 데이터
 */
async function predictIngredients(images, ingredientsData = []) {
    const formData = new FormData();
    
    // 복수 이미지 파일을 'images' 필드명으로 담기
    images.forEach((image) => {
        formData.append('images', image);
    });

    // 각 재료의 serving_g 정보가 전달되면 요청 바디(FormData)에 포함
    if (ingredientsData && ingredientsData.length > 0) {
        formData.append('ingredients_data', JSON.stringify(ingredientsData.map(item => ({
            ingredient_id: item.ingredient_id || null,
            name: item.name || '',
            serving_g: item.serving_g || 100
        }))));
    }

    try {
        const response = await fetch(`${API_BASE}/api/ingredients/predict`, {
            method: 'POST',
            body: formData,
        });

        const data = await response.json();

        if (!response.ok) {
            throw {
                code: data.code || response.status,
                message: data.message || '서버 통신 중 오류가 발생했습니다.',
                details: data.details || null
            };
        }

        return data;
    } catch (error) {
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
        // payload 내 ingredients 배열의 각 객체에 serving_g 명시적 확인 및 매핑
        const formattedPayload = {
            ...payload,
            ingredients: (payload.ingredients || []).map(item => ({
                ingredient_id: item.ingredient_id || item.id || null,
                name: item.name,
                serving_g: Number(item.serving_g) || 100
            }))
        };

        const response = await fetch(`${API_BASE}/api/nutrition/analyze`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(formattedPayload),
        });

        const data = await response.json();

        if (!response.ok) {
            throw {
                code: data.code || response.status,
                message: data.message || '서버 통신 중 오류가 발생했습니다.',
                details: data.details || null
            };
        }

        return data;
    } catch (error) {
        throw {
            code: error.code || 500,
            message: error.message || '네트워크 연결을 확인해주세요.',
            details: error.details || null
        };
    }
}

/**
 * 레시피 추천 API 호출 함수
 * @param {Object} payload - { ingredients: Array<{name: string, serving_g: number}>|string[], deficient_nutrients: string[], mode: 'owned_first'|'nutrition_supplement' }
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

        if (!response.ok) {
            throw {
                code: data.code || response.status,
                message: data.message || '서버 통신 중 오류가 발생했습니다.',
                details: data.details || null
            };
        }

        return data;
    } catch (error) {
        throw {
            code: error.code || 500,
            message: error.message || '네트워크 연결을 확인해주세요.',
            details: error.details || null
        };
    }
}

const api = {
    predictIngredients,
    analyzeNutrition,
    recommendRecipes
};