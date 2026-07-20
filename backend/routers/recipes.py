# backend/routers/recipes.py

# [LLM-RECIPE] Gemini 기반 레시피 서비스와 API를 연결한다.

from fastapi import APIRouter, HTTPException

from backend.schemas.recipe import (
    CommonError,
    RecipeRequest,
    RecipeResponse,
)
from backend.services.llm_recipe_service import generate_recipes


router = APIRouter(
    prefix="/api/recipes",
    tags=["recipes"],
)


@router.post(
    "/recommend",
    response_model=RecipeResponse,
    summary="Gemini 기반 레시피 추천",
    description=(
        "사용자가 보유한 재료와 부족 영양소를 바탕으로 "
        "Gemini가 레시피를 생성합니다. "
        "호출 또는 검증에 실패하면 Mock 응답을 반환합니다."
    ),
    responses={
        422: {
            "model": CommonError,
            "description": "요청 데이터가 올바르지 않은 경우",
        },
        500: {
            "model": CommonError,
            "description": "Gemini와 Mock 응답 생성이 모두 실패한 경우",
        },
    },
)
def recommend_recipes(
    request: RecipeRequest,
) -> RecipeResponse:
    try:
        recipes = generate_recipes(
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
                "message": "레시피 생성에 실패했습니다.",
                "details": str(exc),
            },
        ) from exc