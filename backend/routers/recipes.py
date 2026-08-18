# backend/routers/recipes.py

# [RAG-RECIPE] 시은 최종 책임. 한국어 주석 필수
# [RAG-RECIPE] RAG 기반 레시피 서비스와 API를 연결한다.

from fastapi import (
    APIRouter,
    HTTPException,
)

from backend.schemas.recipe import (
    CommonError,
    RecipeRequest,
    RecipeResponse,
)

from backend.services.rag_recipe_service import (
    generate_rag_recipes,
)


router = APIRouter(
    prefix="/api/recipes",
    tags=["recipes"],
)


@router.post(
    "/recommend",
    response_model=RecipeResponse,
    summary="RAG 기반 레시피 추천",
    description=(
        "사용자가 보유한 재료와 부족 영양소를 바탕으로 "
        "벡터 인덱스에서 관련 레시피를 먼저 검색합니다. "
        "검색된 레시피를 근거로 Gemini가 최종 레시피를 생성하며, "
        "실제로 참고한 레시피 출처를 sources에 포함합니다. "
        "검색 결과가 없거나 RAG 처리에 실패하면 "
        "기존 Gemini 직접 생성 방식으로 fallback합니다."
    ),
    responses={
        422: {
            "model": CommonError,
            "description": (
                "요청 데이터가 올바르지 않은 경우"
            ),
        },
        500: {
            "model": CommonError,
            "description": (
                "레시피 생성에 실패한 경우"
            ),
        },
    },
)
def recommend_recipes(
    request: RecipeRequest,
) -> RecipeResponse:
    """
    [RAG-RECIPE] 클라이언트의 레시피 추천 요청을 받아
    RAG 기반 레시피 서비스를 호출한다.
    """

    try:
        recipes = generate_rag_recipes(
            ingredients=request.ingredients,
            deficient_nutrients=request.deficient_nutrients,
            mode=request.mode,
        )

        return RecipeResponse(
            recipe_mode=request.mode,
            recipes=recipes,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "INVALID_RECIPE_REQUEST",
                "message": str(exc),
                "details": None,
            },
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail={
                "code": "RECIPE_GENERATION_FAILED",
                "message": (
                    "레시피 생성에 실패했습니다."
                ),
                "details": str(exc),
            },
        ) from exc