// [API] 백엔드 서버와의 통신을 담당하는 모듈

const API_BASE = 'http://localhost:8000';
//나중에 연결시 바꿔야 할 주소!!

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

// nutrition.js 등 다른 모듈에서 api.analyzeNutrition() 형태로 호출할 수 있도록 네임스페이스로도 노출한다.
const api = {
    predictIngredients,
    analyzeNutrition
};