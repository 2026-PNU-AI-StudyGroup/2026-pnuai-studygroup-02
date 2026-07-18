# backend/schemas/recipe.py

from typing import Literal, TypeAlias

from pydantic import BaseModel, Field, field_validator


# [SCHEMA] 레시피 생성 모드
RecipeMode: TypeAlias = Literal[
    "owned_first",
    "nutrition_supplement",
]


# [SCHEMA] 레시피 생성 요청 데이터
class RecipeRequest(BaseModel):
    ingredients: list[str] = Field(
        min_length=1,
        description="사용자가 보유한 식재료 목록",
        examples=[["감자", "당근", "양배추"]],
    )

    deficient_nutrients: list[str] = Field(
        default_factory=list,
        description="사용자에게 부족한 영양소 목록",
        examples=[["단백질"]],
    )

    mode: RecipeMode = Field(
        default="owned_first",
        description="레시피 생성 모드",
    )

    # [SCHEMA] 입력 문자열의 공백과 중복을 제거한다.
    @field_validator(
        "ingredients",
        "deficient_nutrients",
        mode="before",
    )
    @classmethod
    def clean_string_list(
        cls,
        value: object,
    ) -> object:
        if not isinstance(value, list):
            return value

        result: list[str] = []

        for item in value:
            if not isinstance(item, str):
                continue

            cleaned = item.strip()

            if cleaned and cleaned not in result:
                result.append(cleaned)

        return result


# [SCHEMA] 개별 레시피 데이터
class Recipe(BaseModel):
    recipe_id: str = Field(
        min_length=1,
        description="레시피 고유 식별자",
    )

    title: str = Field(
        min_length=1,
        description="레시피 이름",
    )

    owned_ingredients: list[str] = Field(
        default_factory=list,
        description="사용자가 보유한 재료",
    )

    additional_ingredients: list[str] = Field(
        default_factory=list,
        description="추가로 준비해야 하는 재료",
    )

    steps: list[str] = Field(
        min_length=1,
        description="조리 단계",
    )

    sources: list[str] = Field(
        default_factory=list,
        description="RAG를 사용하지 않으므로 항상 빈 배열",
    )

    # [SCHEMA] 문자열 필드의 앞뒤 공백을 제거한다.
    @field_validator(
        "recipe_id",
        "title",
        mode="before",
    )
    @classmethod
    def clean_string(
        cls,
        value: object,
    ) -> object:
        if isinstance(value, str):
            return value.strip()

        return value

    # [SCHEMA] 재료 목록의 공백과 중복을 제거한다.
    @field_validator(
        "owned_ingredients",
        "additional_ingredients",
        mode="before",
    )
    @classmethod
    def clean_ingredient_list(
        cls,
        value: object,
    ) -> object:
        if not isinstance(value, list):
            return value

        result: list[str] = []

        for item in value:
            if not isinstance(item, str):
                continue

            cleaned = item.strip()

            if cleaned and cleaned not in result:
                result.append(cleaned)

        return result

    # [SCHEMA] 빈 문자열로 된 조리 단계를 제거한다.
    @field_validator(
        "steps",
        mode="before",
    )
    @classmethod
    def clean_steps(
        cls,
        value: object,
    ) -> object:
        if not isinstance(value, list):
            return value

        return [
            item.strip()
            for item in value
            if isinstance(item, str) and item.strip()
        ]

    # [SCHEMA] sources는 항상 빈 배열로 만든다.
    @field_validator(
        "sources",
        mode="before",
    )
    @classmethod
    def force_empty_sources(
        cls,
        value: object,
    ) -> list[str]:
        return []


# [SCHEMA] 레시피 생성 성공 응답 데이터
class RecipeResponse(BaseModel):
    recipe_mode: RecipeMode = Field(
        description="레시피 생성 모드",
    )

    recipes: list[Recipe] = Field(
        min_length=1,
        description="생성된 레시피 목록",
    )


# [SCHEMA] API 공통 오류 응답
class CommonError(BaseModel):
    code: str
    message: str
    details: dict[str, object] | list[object] | str | None = None