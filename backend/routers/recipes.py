# [MOCK] 실제 LLM을 호출하지 않고 고정된 JSON 응답을 반환한다.

import json
from pathlib import Path

from fastapi import APIRouter

from backend.schemas.recipe import RecipeRequest, RecipeResponse


router = APIRouter(
    prefix="/api/recipes",
    tags=["recipes"],
)


# [MOCK] recipe_mock.json 파일의 위치를 계산한다.
MOCK_FILE_PATH = (
    Path(__file__).resolve().parent.parent
    / "mock"
    / "recipe_mock.json"
)


@router.post(
    "/recommend",
    response_model=RecipeResponse,
)
def recommend_recipes(
    request: RecipeRequest,
) -> RecipeResponse:
    """
    사용자의 레시피 추천 요청을 받는다.

    현재는 실제 LLM을 사용하지 않고,
    recipe_mock.json에 저장된 고정 응답을 반환한다.
    """

    # [MOCK] 요청 데이터는 아직 레시피 생성에 사용하지 않는다.
    _ = request

    # [MOCK] JSON 파일을 UTF-8 형식으로 읽는다.
    with MOCK_FILE_PATH.open(
        mode="r",
        encoding="utf-8",
    ) as file:
        mock_data = json.load(file)

    # [MOCK] JSON 데이터를 RecipeResponse 스키마로 검증한다.
    return RecipeResponse.model_validate(mock_data)