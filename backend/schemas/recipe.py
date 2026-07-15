# backend/schemas/recipe.py

from typing import Literal

from pydantic import BaseModel, Field


# [SCHEMA] 레시피 생성 요청 데이터
class RecipeRequest(BaseModel):
    ingredients: list[str] = Field(
        ...,
        description="사용자가 보유한 식재료 목록",
        examples=[["감자", "당근", "양배추"]],
    )
    deficient_nutrients: list[str] = Field(
        default_factory=list,
        description="사용자에게 부족한 영양소 목록",
        examples=[["단백질", "비타민 C"]],
    )
    mode: Literal["llm"] = Field(
        default="llm",
        description="레시피 생성 방식",
    )


# [SCHEMA] 개별 레시피 데이터
class Recipe(BaseModel):
    recipe_id: str = Field(
        ...,
        description="레시피 고유 식별자",
        examples=["recipe-001"],
    )
    title: str = Field(
        ...,
        description="레시피 이름",
        examples=["감자 당근 볶음"],
    )
    owned_ingredients: list[str] = Field(
        default_factory=list,
        description="사용자가 보유한 재료 중 레시피에 사용되는 재료",
        examples=[["감자", "당근"]],
    )
    additional_ingredients: list[str] = Field(
        default_factory=list,
        description="추가로 필요한 재료",
        examples=[["소금", "식용유"]],
    )
    steps: list[str] = Field(
        ...,
        description="순서대로 정리한 조리 단계",
        examples=[
            [
                "감자와 당근을 먹기 좋은 크기로 썬다.",
                "팬에 식용유를 두르고 재료를 볶는다.",
                "소금으로 간한 뒤 접시에 담는다.",
            ]
        ],
    )


# [SCHEMA] 레시피 생성 성공 응답 데이터
class RecipeResponse(BaseModel):
    recipe_mode: Literal["llm"] = Field(
        default="llm",
        description="레시피 생성에 사용된 방식",
    )
    recipes: list[Recipe] = Field(
        default_factory=list,
        description="생성된 레시피 목록",
    )


# [SCHEMA] API 공통 오류 응답 데이터
class CommonError(BaseModel):
    code: str = Field(
        ...,
        description="오류 코드",
        examples=["INVALID_REQUEST"],
    )
    message: str = Field(
        ...,
        description="사용자에게 전달할 오류 메시지",
        examples=["요청 데이터가 올바르지 않습니다."],
    )
    details: dict[str, object] | list[object] | str | None = Field(
        default=None,
        description="오류에 대한 추가 정보",
    )