# backend/services/llm_recipe_service.py

# [LLM-RECIPE] 시은 최종 책임(7/24까지)

import json
import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types

from backend.schemas.recipe import RecipeMode, RecipeResponse


# [LLM-RECIPE] 프로젝트 최상위의 .env 환경변수를 읽는다.
load_dotenv()

logger = logging.getLogger(__name__)

# [LLM-RECIPE] 구조화된 출력을 지원하는 안정 버전 모델을 사용한다.
MODEL_NAME = "gemini-3.5-flash"

# [LLM-RECIPE] 최초 1회와 재시도 2회, 최대 3회 호출한다.
MAX_RETRIES = 2

ALLOWED_MODES: set[str] = {
    "owned_first",
    "nutrition_supplement",
}

BASIC_SEASONINGS: set[str] = {
    "물",
    "소금",
    "후추",
    "식용유",
}

STAPLE_KEYWORDS: tuple[str, ...] = (
    "밥",
    "쌀",
    "면",
    "국수",
    "라면",
    "우동",
    "파스타",
    "스파게티",
    "빵",
    "식빵",
    "바게트",
)

# [LLM-RECIPE] Gemini 호출 실패 시 사용할 고정 Mock 응답
MOCK_FILE_PATH = (
    Path(__file__).resolve().parent.parent
    / "mock"
    / "recipe_mock.json"
)


# [LLM-RECIPE] 입력 목록의 공백과 중복을 제거한다.
def _normalize_items(items: list[str]) -> list[str]:
    result: list[str] = []

    for item in items:
        if not isinstance(item, str):
            continue

        cleaned = item.strip()

        if cleaned and cleaned not in result:
            result.append(cleaned)

    return result


# [LLM-RECIPE] 재료 비교를 위해 공백을 제거하고 소문자로 변환한다.
def _normalize_name(value: str) -> str:
    return "".join(value.lower().split())


# [LLM-RECIPE] 밥·면·빵 계열인지 검사한다.
def _is_staple_ingredient(ingredient: str) -> bool:
    normalized = _normalize_name(ingredient)

    return any(
        keyword in normalized
        for keyword in STAPLE_KEYWORDS
    )


# [LLM-RECIPE] 사용자 입력과 모드에 맞는 프롬프트를 만든다.
def _build_prompt(
    ingredients: list[str],
    deficient_nutrients: list[str],
    mode: RecipeMode,
    retry_feedback: str = "",
) -> str:
    ingredients_text = ", ".join(ingredients)

    nutrients_text = (
        ", ".join(deficient_nutrients)
        if deficient_nutrients
        else "없음"
    )

    if mode == "owned_first":
        mode_rule = """
- 사용자가 보유한 재료를 최대한 우선 활용하세요.
- 서로 다른 레시피를 반드시 3개 이상 생성하세요.
- 추가 재료는 가능한 한 적게 사용하세요.
""".strip()

    else:
        mode_rule = f"""
- 부족한 영양소인 '{nutrients_text}'를 보완할 재료를 포함하세요.
- 영양 보완 재료는 additional_ingredients에 넣으세요.
- 최소 하나 이상의 레시피에 영양 보완용 추가 재료가 있어야 합니다.
""".strip()

    retry_rule = ""

    if retry_feedback:
        retry_rule = f"""
[이전 응답의 오류]
{retry_feedback}

위 오류를 수정하여 새로운 결과를 생성하세요.
""".strip()

    return f"""
당신은 한국 가정식 레시피를 만드는 요리 전문가입니다.

[사용자가 보유한 재료]
{ingredients_text}

[부족한 영양소]
{nutrients_text}

[생성 모드]
{mode}

[필수 규칙]
1. 보유 재료와 기본 양념인 물·소금·후추·식용유만
   필수 재료로 가정하세요.
2. owned_ingredients에는 사용자가 입력한 재료만 넣으세요.
3. 보유하지 않은 재료는 owned_ingredients에 넣지 마세요.
4. 보유하지 않은 재료가 필요하면 additional_ingredients에 넣으세요.
5. 밥·쌀·면·국수·라면·우동·파스타·빵·식빵은
   반드시 additional_ingredients로 분류하세요.
6. 물·소금·후추·식용유는 재료 목록에 넣지 마세요.
7. 보유하지 않은 재료를 steps에서 갑자기 사용하지 마세요.
8. steps는 구체적인 한국어 문장으로 작성하세요.
9. steps는 빈 배열이면 안 됩니다.
10. 모든 레시피의 sources는 빈 배열이어야 합니다.
11. recipe_mode는 반드시 "{mode}"로 작성하세요.
12. recipe_id는 각 레시피마다 서로 달라야 합니다.

[모드별 규칙]
{mode_rule}

{retry_rule}
""".strip()


# [LLM-RECIPE] Google Gen AI SDK로 Gemini를 직접 호출한다.
def _call_gemini(prompt: str) -> RecipeResponse:
    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY가 설정되지 않았습니다."
        )

    client = genai.Client(api_key=api_key)

    # [LLM-RECIPE] Pydantic 스키마를 전달해 JSON 구조를 강제한다.
    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=RecipeResponse,
            temperature=0.4,
        ),
    )

    if not response.text:
        raise ValueError(
            "Gemini 응답 본문이 비어 있습니다."
        )

    # [LLM-RECIPE] Gemini가 반환한 JSON을 Pydantic으로 검증한다.
    return RecipeResponse.model_validate_json(response.text)


# [LLM-RECIPE] Pydantic 이외의 업무 규칙을 추가로 검사한다.
def _validate_business_rules(
    response: RecipeResponse,
    input_ingredients: list[str],
    deficient_nutrients: list[str],
    mode: RecipeMode,
) -> None:
    normalized_inputs = {
        _normalize_name(item)
        for item in input_ingredients
    }

    if response.recipe_mode != mode:
        raise ValueError(
            "응답의 recipe_mode가 요청한 mode와 다릅니다."
        )

    if mode == "owned_first" and len(response.recipes) < 3:
        raise ValueError(
            "owned_first 모드는 레시피가 3개 이상이어야 합니다."
        )

    recipe_ids: set[str] = set()
    has_additional_ingredient = False

    for recipe in response.recipes:
        if recipe.recipe_id in recipe_ids:
            raise ValueError(
                f"중복된 recipe_id가 있습니다: {recipe.recipe_id}"
            )

        recipe_ids.add(recipe.recipe_id)

        invalid_owned: list[str] = []

        for ingredient in recipe.owned_ingredients:
            normalized = _normalize_name(ingredient)

            if normalized not in normalized_inputs:
                invalid_owned.append(ingredient)

            elif _is_staple_ingredient(ingredient):
                invalid_owned.append(ingredient)

            elif ingredient in BASIC_SEASONINGS:
                invalid_owned.append(ingredient)

        if invalid_owned:
            raise ValueError(
                "owned_ingredients에 입력하지 않은 재료가 있습니다: "
                + ", ".join(sorted(set(invalid_owned)))
            )

        # [LLM-RECIPE] 기본 양념은 추가 재료 목록에서도 제거한다.
        cleaned_additional: list[str] = []

        for ingredient in recipe.additional_ingredients:
            if ingredient in BASIC_SEASONINGS:
                continue

            if ingredient not in cleaned_additional:
                cleaned_additional.append(ingredient)

        recipe.additional_ingredients = cleaned_additional

        if cleaned_additional:
            has_additional_ingredient = True

        cleaned_steps = [
            step.strip()
            for step in recipe.steps
            if isinstance(step, str) and step.strip()
        ]

        if not cleaned_steps:
            raise ValueError(
                f"'{recipe.title}' 레시피의 steps가 비어 있습니다."
            )

        recipe.steps = cleaned_steps

        # [LLM-RECIPE] RAG가 아니므로 sources를 빈 배열로 강제한다.
        recipe.sources = []

    if mode == "nutrition_supplement":
        if not deficient_nutrients:
            raise ValueError(
                "nutrition_supplement 모드에는 "
                "deficient_nutrients가 필요합니다."
            )

        if not has_additional_ingredient:
            raise ValueError(
                "영양 보완용 additional_ingredients가 없습니다."
            )


# [LLM-RECIPE] Gemini 호출 실패 시 Mock JSON을 반환한다.
def _load_mock_fallback(
    mode: RecipeMode,
) -> list[dict]:
    if not MOCK_FILE_PATH.exists():
        raise FileNotFoundError(
            f"Mock 파일이 없습니다: {MOCK_FILE_PATH}"
        )

    with MOCK_FILE_PATH.open(
        mode="r",
        encoding="utf-8",
    ) as file:
        mock_data = json.load(file)

    mock_data["recipe_mode"] = mode

    mock_response = RecipeResponse.model_validate(mock_data)

    result: list[dict] = []

    for recipe in mock_response.recipes:
        recipe.sources = []
        result.append(recipe.model_dump())

    return result


# [LLM-RECIPE] Gemini 호출·검증·재시도·fallback을 총괄한다.
def generate_recipes(
    ingredients: list[str],
    deficient_nutrients: list[str],
    mode: RecipeMode,
) -> list[dict]:
    normalized_ingredients = _normalize_items(ingredients)
    normalized_nutrients = _normalize_items(deficient_nutrients)

    if not normalized_ingredients:
        raise ValueError(
            "ingredients는 최소 한 개 이상 필요합니다."
        )

    if mode not in ALLOWED_MODES:
        raise ValueError(
            f"지원하지 않는 mode입니다: {mode}"
        )

    if (
        mode == "nutrition_supplement"
        and not normalized_nutrients
    ):
        raise ValueError(
            "nutrition_supplement 모드에는 "
            "deficient_nutrients가 필요합니다."
        )

    retry_feedback = ""

    # [LLM-RECIPE] 최초 1회와 재시도 2회를 수행한다.
    for attempt in range(MAX_RETRIES + 1):
        try:
            prompt = _build_prompt(
                ingredients=normalized_ingredients,
                deficient_nutrients=normalized_nutrients,
                mode=mode,
                retry_feedback=retry_feedback,
            )

            response = _call_gemini(prompt)

            _validate_business_rules(
                response=response,
                input_ingredients=normalized_ingredients,
                deficient_nutrients=normalized_nutrients,
                mode=mode,
            )

            return [
                recipe.model_dump()
                for recipe in response.recipes
            ]

        except Exception as exc:
            retry_feedback = str(exc)

            logger.warning(
                "Gemini 레시피 생성 실패: 시도=%s/%s, 오류=%s",
                attempt + 1,
                MAX_RETRIES + 1,
                exc,
            )

    logger.error(
        "Gemini 레시피 생성에 실패하여 Mock 응답을 사용합니다."
    )

    return _load_mock_fallback(mode)