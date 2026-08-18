# backend/services/rag_recipe_service.py

# [RAG-RECIPE] 시은 최종 책임. 한국어 주석 필수

import logging
from typing import Any

from backend.schemas.recipe import (
    RecipeMode,
    RecipeResponse,
)

from backend.services.recipe_retriever import (
    search,
)

from backend.services.llm_recipe_service import (
    ALLOWED_MODES,
    MAX_RETRIES,
    LLMEmptyResponseError,
    LLMResponseParseError,
    LLMTimeoutError,
    _build_prompt,
    _call_gemini,
    _is_mock_mode,
    _normalize_items,
    _validate_business_rules,
    generate_recipes as generate_direct_recipes,
)


logger = logging.getLogger(__name__)


# [RAG-RECIPE] 벡터 검색에서 가져올 최대 관련 문서 수
RAG_TOP_K = 5


def _make_source_label(
    document: dict[str, Any],
) -> str:
    """
    [RAG-RECIPE] 검색 문서의 레시피명과 출처를
    Recipe.sources에 넣을 문자열로 만든다.
    """

    title = str(
        document.get(
            "title",
            "",
        )
    ).strip()

    source = document.get(
        "source",
        {},
    )

    if not isinstance(
        source,
        dict,
    ):
        source = {}

    api_name = str(
        source.get(
            "api_name",
            "",
        )
    ).strip()

    url = str(
        source.get(
            "url",
            "",
        )
    ).strip()

    parts = [
        value
        for value in (
            title,
            api_name,
            url,
        )
        if value
    ]

    return " - ".join(
        parts
    )


def _format_retrieved_documents(
    documents: list[dict[str, Any]],
) -> tuple[str, list[str]]:
    """
    [RAG-RECIPE] 검색된 레시피 문서를
    Gemini 프롬프트용 문자열로 변환한다.

    동시에 sources에서 사용할 수 있는
    실제 출처 문자열 목록을 만든다.
    """

    document_blocks: list[str] = []
    source_labels: list[str] = []

    for index, document in enumerate(
        documents,
        start=1,
    ):
        title = str(
            document.get(
                "title",
                "",
            )
        ).strip()

        ingredients = document.get(
            "ingredients",
            [],
        )

        steps = document.get(
            "steps",
            [],
        )

        if not isinstance(
            ingredients,
            list,
        ):
            ingredients = []

        if not isinstance(
            steps,
            list,
        ):
            steps = []

        ingredient_text = ", ".join(
            str(item).strip()
            for item in ingredients
            if str(item).strip()
        )

        if not ingredient_text:
            ingredient_text = (
                "재료 정보 없음"
            )

        step_lines: list[str] = []

        for step_index, step in enumerate(
            steps,
            start=1,
        ):
            cleaned_step = str(
                step
            ).strip()

            if cleaned_step:
                step_lines.append(
                    f"{step_index}. "
                    f"{cleaned_step}"
                )

        steps_text = "\n".join(
            step_lines
        )

        if not steps_text:
            steps_text = (
                "조리 단계 정보 없음"
            )

        source_label = (
            _make_source_label(
                document
            )
        )

        if (
            source_label
            and source_label
            not in source_labels
        ):
            source_labels.append(
                source_label
            )

        document_blocks.append(
            "\n".join(
                [
                    f"[검색 문서 {index}]",
                    f"레시피명: {title}",
                    f"재료: {ingredient_text}",
                    "조리단계:",
                    steps_text,
                    f"출처: {source_label}",
                ]
            )
        )

    return (
        "\n\n".join(
            document_blocks
        ),
        source_labels,
    )


def _build_rag_prompt(
    ingredients: list[str],
    deficient_nutrients: list[str],
    mode: RecipeMode,
    documents: list[dict[str, Any]],
    retry_feedback: str = "",
) -> tuple[str, list[str]]:
    """
    [RAG-RECIPE] 기존 llm_recipe_service의
    프롬프트 규칙을 그대로 재사용하고,
    검색 문서 및 RAG 출처 규칙만 추가한다.
    """

    base_prompt = _build_prompt(
        ingredients=ingredients,
        deficient_nutrients=deficient_nutrients,
        mode=mode,
        retry_feedback=retry_feedback,
    )

    # [RAG-RECIPE] 기존 직접 생성 프롬프트는
    # sources=[]를 요구하므로 RAG 모드에서만 규칙을 교체한다.
    base_prompt = base_prompt.replace(
        (
            "10. 모든 레시피의 sources는 "
            "빈 배열이어야 합니다."
        ),
        (
            "10. 각 레시피를 생성할 때 실제로 참고한 "
            "검색 문서의 출처를 sources에 넣으세요."
        ),
    )

    (
        documents_text,
        source_labels,
    ) = _format_retrieved_documents(
        documents
    )

    allowed_sources_text = "\n".join(
        f"- {source}"
        for source in source_labels
    )

    rag_instruction = f"""
[RAG 검색 문서 사용 규칙]

아래 검색된 레시피를 참고해 답하고,
실제로 사용한 문서의 출처를 sources에 명시하세요.

검색된 문서의 레시피명, 재료, 조리 방법을
최종 추천 레시피를 만드는 근거로 활용하세요.

sources에는 실제로 참고한 문서만 넣으세요.

sources 문자열은 반드시 아래
[사용 가능한 sources] 목록에 있는 문자열을
그대로 사용해야 합니다.

검색 결과에 존재하지 않는 출처나 URL을
임의로 만들지 마세요.

각 추천 레시피에는 최소 1개 이상의
유효한 sources를 넣으세요.

[사용 가능한 sources]
{allowed_sources_text}

[검색된 레시피]
{documents_text}
""".strip()

    prompt = (
        f"{base_prompt}\n\n"
        f"{rag_instruction}"
    )

    return (
        prompt,
        source_labels,
    )


def _restore_and_validate_sources(
    response: RecipeResponse,
    raw_sources: list[list[str]],
    allowed_sources: list[str],
) -> None:
    """
    [RAG-RECIPE] LLM이 반환한 sources가
    실제 검색 문서의 출처인지 검사한다.

    기존 업무 규칙 검증 함수는 직접 생성용으로
    sources를 빈 배열로 변경하므로,
    검증 전에 저장했던 sources를 다시 복원한다.
    """

    allowed_set = set(
        allowed_sources
    )

    for recipe, recipe_sources in zip(
        response.recipes,
        raw_sources,
    ):
        valid_sources: list[str] = []

        for source in recipe_sources:
            if not isinstance(
                source,
                str,
            ):
                continue

            cleaned = source.strip()

            if not cleaned:
                continue

            if cleaned not in allowed_set:
                continue

            if cleaned in valid_sources:
                continue

            valid_sources.append(
                cleaned
            )

        if not valid_sources:
            raise ValueError(
                f"'{recipe.title}' 레시피에 "
                "유효한 RAG 출처가 없습니다."
            )

        recipe.sources = (
            valid_sources
        )


def generate_rag_recipes(
    ingredients: list[str],
    deficient_nutrients: list[str],
    mode: RecipeMode,
) -> list[dict]:
    """
    [RAG-RECIPE] 사용자의 보유 재료로
    관련 레시피 문서를 검색한 뒤,
    검색 결과를 근거로 Gemini가 최종 레시피를 생성한다.

    검색 결과가 없으면 기존 llm_recipe_service의
    직접 생성 로직으로 fallback한다.
    """

    normalized_ingredients = (
        _normalize_items(
            ingredients
        )
    )

    normalized_nutrients = (
        _normalize_items(
            deficient_nutrients
        )
    )

    # [RAG-RECIPE] 기존 서비스와 동일하게
    # 보유 재료가 없으면 요청을 거부한다.
    if not normalized_ingredients:
        raise ValueError(
            "ingredients는 최소 한 개 이상 필요합니다."
        )

    # [RAG-RECIPE] 기존 서비스와 동일한 모드만 허용한다.
    if mode not in ALLOWED_MODES:
        raise ValueError(
            f"지원하지 않는 mode입니다: {mode}"
        )

    # [RAG-RECIPE] 영양 보충 모드에는
    # 부족 영양소 입력이 반드시 필요하다.
    if (
        mode == "nutrition_supplement"
        and not normalized_nutrients
    ):
        raise ValueError(
            "nutrition_supplement 모드에는 "
            "deficient_nutrients가 필요합니다."
        )

    # [RAG-RECIPE] Mock 모드에서는
    # 기존 서비스의 Mock 생성 로직을 그대로 사용한다.
    if _is_mock_mode():
        logger.info(
            "[RAG-RECIPE] MOCK_MODE=true. "
            "기존 직접 생성 로직을 사용합니다."
        )

        return generate_direct_recipes(
            ingredients=normalized_ingredients,
            deficient_nutrients=normalized_nutrients,
            mode=mode,
        )

    # [RAG-RECIPE] LLM 호출 전에 먼저
    # 벡터 검색으로 관련 레시피를 가져온다.
    try:
        documents = search(
            normalized_ingredients,
            k=RAG_TOP_K,
        )

    except Exception as exc:
        # [RAG-RECIPE] 인덱스 파일 문제 등으로
        # 검색 자체에 실패하면 기존 서비스로 fallback한다.
        logger.warning(
            "[RAG-RECIPE] 레시피 검색 실패. "
            "직접 생성으로 fallback합니다. "
            "error=%s",
            exc,
        )

        return generate_direct_recipes(
            ingredients=normalized_ingredients,
            deficient_nutrients=normalized_nutrients,
            mode=mode,
        )

    # [RAG-RECIPE] 검색 결과가 0건이면
    # 요구사항대로 기존 직접 생성 로직을 사용한다.
    # 직접 생성 서비스는 sources=[]를 유지한다.
    if not documents:
        logger.info(
            "[RAG-RECIPE] 검색 결과가 0건입니다. "
            "기존 직접 생성으로 fallback합니다."
        )

        return generate_direct_recipes(
            ingredients=normalized_ingredients,
            deficient_nutrients=normalized_nutrients,
            mode=mode,
        )

    logger.info(
        "[RAG-RECIPE] 관련 레시피 문서 %s건 검색 완료",
        len(documents),
    )

    retry_feedback = ""

    # [RAG-RECIPE] 기존 llm_recipe_service와 동일하게
    # 최초 호출 1회 + 최대 2회 재시도한다.
    for attempt in range(
        MAX_RETRIES + 1
    ):
        try:
            (
                prompt,
                allowed_sources,
            ) = _build_rag_prompt(
                ingredients=normalized_ingredients,
                deficient_nutrients=normalized_nutrients,
                mode=mode,
                documents=documents,
                retry_feedback=retry_feedback,
            )

            # [RAG-RECIPE] 기존 Gemini 호출 로직을 재사용한다.
            response = _call_gemini(
                prompt
            )

            # [RAG-RECIPE] 기존 업무 규칙 검증 함수가
            # sources를 빈 배열로 만들기 때문에,
            # 검증 전에 LLM이 생성한 sources를 보관한다.
            raw_sources = [
                list(
                    recipe.sources
                )
                for recipe in response.recipes
            ]

            # [RAG-RECIPE] 기존 owned_first,
            # nutrition_supplement 검증을 그대로 재사용한다.
            _validate_business_rules(
                response=response,
                input_ingredients=normalized_ingredients,
                deficient_nutrients=normalized_nutrients,
                mode=mode,
            )

            # [RAG-RECIPE] 기존 검증 후
            # 실제 검색 문서 출처만 다시 복원한다.
            _restore_and_validate_sources(
                response=response,
                raw_sources=raw_sources,
                allowed_sources=allowed_sources,
            )

            logger.info(
                "[RAG-RECIPE] RAG 레시피 생성 성공"
            )

            return [
                recipe.model_dump()
                for recipe in response.recipes
            ]

        except LLMTimeoutError as exc:
            retry_feedback = str(
                exc
            )

            logger.warning(
                "[RAG-RECIPE] Gemini timeout. "
                "attempt=%s/%s error=%s",
                attempt + 1,
                MAX_RETRIES + 1,
                exc,
            )

        except LLMResponseParseError as exc:
            retry_feedback = str(
                exc
            )

            logger.warning(
                "[RAG-RECIPE] Gemini 응답 파싱 실패. "
                "attempt=%s/%s error=%s",
                attempt + 1,
                MAX_RETRIES + 1,
                exc,
            )

        except LLMEmptyResponseError as exc:
            retry_feedback = str(
                exc
            )

            logger.warning(
                "[RAG-RECIPE] Gemini 빈 응답. "
                "attempt=%s/%s error=%s",
                attempt + 1,
                MAX_RETRIES + 1,
                exc,
            )

        except Exception as exc:
            retry_feedback = str(
                exc
            )

            logger.warning(
                "[RAG-RECIPE] RAG 생성 또는 검증 실패. "
                "attempt=%s/%s error=%s",
                attempt + 1,
                MAX_RETRIES + 1,
                exc,
            )

    # [RAG-RECIPE] RAG 생성이 반복 실패하면
    # 기존 직접 생성 서비스로 fallback한다.
    # 이 경우 sources는 빈 배열이다.
    logger.error(
        "[RAG-RECIPE] RAG 생성 최종 실패. "
        "기존 직접 생성으로 fallback합니다."
    )

    return generate_direct_recipes(
        ingredients=normalized_ingredients,
        deficient_nutrients=normalized_nutrients,
        mode=mode,
    )