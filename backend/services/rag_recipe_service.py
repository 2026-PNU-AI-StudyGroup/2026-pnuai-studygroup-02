# backend/services/rag_recipe_service.py

# [RAG-RECIPE] 시은 최종 책임. 한국어 주석 필수

import copy
import logging
import time
from threading import Lock
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


# [RAG-RECIPE] 벡터 검색에서 가져올 관련 문서 수
RAG_TOP_K = 5


# [RAG-RECIPE] 동일 재료 조합의 검색 결과를
# 60초 동안 메모리에 캐싱한다.
SEARCH_CACHE_TTL_SECONDS = 60.0


# [RAG-RECIPE] 검색 캐시가 무한히 증가하지 않도록
# 최대 저장 개수를 제한한다.
SEARCH_CACHE_MAX_ITEMS = 32


# [RAG-RECIPE]
# key:
#   정렬된 재료 이름 tuple
#
# value:
#   (
#       캐시 생성 시각,
#       검색 결과 문서
#   )
_search_cache: dict[
    tuple[str, ...],
    tuple[
        float,
        list[dict[str, Any]],
    ],
] = {}


# [RAG-RECIPE] 여러 요청이 동시에 접근할 경우를 대비해
# 검색 캐시 접근을 보호한다.
_search_cache_lock = Lock()


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

    # [RAG-RECIPE] 기존 직접 생성 프롬프트에는
    # sources=[] 규칙이 있으므로
    # RAG 호출에서만 해당 규칙을 변경한다.
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
최종 추천 레시피 생성의 근거로 활용하세요.

검색 문서의 조리 순서, 조리 방식(굽기/볶기/끓이기 등),
재료 분량 비율을 최대한 그대로 유지하세요.

사용자가 보유하지 않은 재료를 대체해야 하는 경우,
그 재료명만 보유 재료로 바꾸고 조리 방식과 분량 비율,
소요 시간은 원본 문서와 최대한 동일하게 유지하세요.

sources에 명시한 문서와 전혀 다른 요리로
임의로 재창작하지 마세요.

sources에는 실제로 참고한 검색 문서만 넣으세요.

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

    return (
        f"{base_prompt}\n\n{rag_instruction}",
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

    기존 업무 규칙 검증 함수가 sources를
    빈 배열로 변경하므로 검증 전에 저장했던
    sources를 다시 복원한다.
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


def _make_search_cache_key(
    ingredients: list[str],
) -> tuple[str, ...]:
    """
    [RAG-RECIPE] 같은 재료 조합이면
    입력 순서가 달라도 같은 캐시 키를 만든다.

    예:
    ["감자", "양파"]
    ["양파", "감자"]

    위 두 입력은 동일한 캐시를 사용한다.
    """

    normalized = {
        ingredient.strip().lower()
        for ingredient in ingredients
        if (
            isinstance(
                ingredient,
                str,
            )
            and ingredient.strip()
        )
    }

    return tuple(
        sorted(
            normalized
        )
    )


def _clear_expired_search_cache(
    now: float,
) -> None:
    """
    [RAG-RECIPE] TTL이 지난 검색 캐시를 제거한다.

    이 함수는 cache lock을 획득한 상태에서 호출한다.
    """

    expired_keys = [
        key
        for key, (
            created_at,
            _,
        ) in _search_cache.items()
        if (
            now - created_at
            >= SEARCH_CACHE_TTL_SECONDS
        )
    ]

    for key in expired_keys:
        _search_cache.pop(
            key,
            None,
        )


def _search_with_cache(
    ingredients: list[str],
) -> list[dict[str, Any]]:
    """
    [RAG-RECIPE] 동일 재료 조합에 대한
    FAISS 검색 결과를 짧게 캐싱한다.

    캐시에 결과가 있으면 임베딩 생성과
    FAISS 검색을 다시 수행하지 않는다.
    """

    cache_key = (
        _make_search_cache_key(
            ingredients
        )
    )

    if not cache_key:
        return []

    now = time.monotonic()

    with _search_cache_lock:
        _clear_expired_search_cache(
            now
        )

        cached = _search_cache.get(
            cache_key
        )

        if cached is not None:
            (
                created_at,
                documents,
            ) = cached

            cache_age = (
                now - created_at
            )

            logger.info(
                "[RAG-RECIPE] 검색 캐시 HIT. "
                "ingredients=%s age=%.2fs",
                cache_key,
                cache_age,
            )

            # [RAG-RECIPE] 반환된 값을 수정해도
            # 캐시 원본이 바뀌지 않도록 복사한다.
            return copy.deepcopy(
                documents
            )

    logger.info(
        "[RAG-RECIPE] 검색 캐시 MISS. "
        "ingredients=%s",
        cache_key,
    )

    # [RAG-RECIPE] 실제 임베딩 생성 및
    # FAISS 벡터 검색을 수행한다.
    documents = search(
        list(cache_key),
        k=RAG_TOP_K,
    )

    with _search_cache_lock:
        # [RAG-RECIPE] 최대 캐시 크기를 넘으면
        # 가장 오래된 항목을 제거한다.
        if (
            len(_search_cache)
            >= SEARCH_CACHE_MAX_ITEMS
        ):
            oldest_key = min(
                _search_cache,
                key=lambda key: (
                    _search_cache[key][0]
                ),
            )

            _search_cache.pop(
                oldest_key,
                None,
            )

        _search_cache[
            cache_key
        ] = (
            time.monotonic(),
            copy.deepcopy(
                documents
            ),
        )

    return documents


def _direct_fallback(
    *,
    ingredients: list[str],
    deficient_nutrients: list[str],
    mode: RecipeMode,
    reason: str,
    total_started_at: float,
) -> list[dict]:
    """
    [RAG-RECIPE] RAG 검색이 불가능하거나
    검색 결과가 없을 때 기존 LLM 직접 생성으로 fallback한다.

    직접 생성 결과는 기존 llm_recipe_service 규칙에 따라
    sources=[]를 유지한다.
    """

    logger.warning(
        "[RAG-RECIPE] 직접 생성 fallback 시작. "
        "reason=%s",
        reason,
    )

    fallback_started_at = (
        time.perf_counter()
    )

    result = generate_direct_recipes(
        ingredients=ingredients,
        deficient_nutrients=deficient_nutrients,
        mode=mode,
    )

    fallback_elapsed_ms = (
        time.perf_counter()
        - fallback_started_at
    ) * 1000

    total_elapsed_ms = (
        time.perf_counter()
        - total_started_at
    ) * 1000

    logger.info(
        "[RAG-RECIPE] 직접 생성 fallback 완료. "
        "fallback_ms=%.2f total_ms=%.2f",
        fallback_elapsed_ms,
        total_elapsed_ms,
    )

    return result


def generate_rag_recipes(
    ingredients: list[str],
    deficient_nutrients: list[str],
    mode: RecipeMode,
) -> list[dict]:
    """
    [RAG-RECIPE] 사용자의 보유 재료로
    관련 레시피 문서를 검색한 뒤,
    검색 결과를 근거로 Gemini가 최종 레시피를 생성한다.

    응답 속도를 측정하며 동일 재료 조합의
    검색 결과는 짧은 시간 동안 캐싱한다.

    검색 결과가 없거나 로컬 벡터 검색이 실패하면
    기존 llm_recipe_service의 직접 생성 방식으로 fallback한다.
    """

    # [RAG-RECIPE] 전체 요청 시간을 측정한다.
    total_started_at = (
        time.perf_counter()
    )

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

    # [RAG-RECIPE] 기존 서비스와 동일한 입력 검증
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

    # [RAG-RECIPE] Mock 모드에서는
    # 기존 서비스 로직을 그대로 사용한다.
    if _is_mock_mode():
        logger.info(
            "[RAG-RECIPE] MOCK_MODE=true. "
            "기존 직접 생성 로직을 사용합니다."
        )

        return _direct_fallback(
            ingredients=normalized_ingredients,
            deficient_nutrients=normalized_nutrients,
            mode=mode,
            reason="mock_mode",
            total_started_at=total_started_at,
        )

    # [RAG-RECIPE] 검색 단계 응답 시간 측정 시작
    retrieve_started_at = (
        time.perf_counter()
    )

    try:
        documents = (
            _search_with_cache(
                normalized_ingredients
            )
        )

    except Exception as exc:
        retrieve_elapsed_ms = (
            time.perf_counter()
            - retrieve_started_at
        ) * 1000

        logger.warning(
            "[RAG-RECIPE] 레시피 검색 실패. "
            "retrieve_ms=%.2f error=%s",
            retrieve_elapsed_ms,
            exc,
        )

        # [RAG-RECIPE]
        # 현재 검색 단계에서는 농촌진흥청이나
        # 식품안전나라 API를 실시간 호출하지 않는다.
        #
        # 이미 생성해 둔 recipes.jsonl과
        # FAISS 로컬 인덱스를 사용한다.
        #
        # 따라서 공공 API 장애는 기존 로컬 인덱스가
        # 존재하는 동안 서비스 검색에 영향을 주지 않는다.
        #
        # 로컬 인덱스가 없거나 손상되어 검색 자체가 실패하면
        # 기존 LLM 직접 생성으로 fallback한다.
        return _direct_fallback(
            ingredients=normalized_ingredients,
            deficient_nutrients=normalized_nutrients,
            mode=mode,
            reason=(
                "vector_search_failure: "
                f"{exc}"
            ),
            total_started_at=total_started_at,
        )

    retrieve_elapsed_ms = (
        time.perf_counter()
        - retrieve_started_at
    ) * 1000

    logger.info(
        "[RAG-RECIPE] 검색 완료. "
        "documents=%s retrieve_ms=%.2f",
        len(documents),
        retrieve_elapsed_ms,
    )

    # [RAG-RECIPE] 검색 결과가 없으면
    # 기존 직접 생성으로 fallback한다.
    if not documents:
        return _direct_fallback(
            ingredients=normalized_ingredients,
            deficient_nutrients=normalized_nutrients,
            mode=mode,
            reason="search_result_empty",
            total_started_at=total_started_at,
        )

    logger.info(
        "[RAG-RECIPE] 관련 레시피 문서 %s건 검색 완료",
        len(documents),
    )

    retry_feedback = ""

    # [RAG-RECIPE] 기존 llm_recipe_service와 동일하게
    # 최초 1회 + 최대 2회 재시도한다.
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

            # [RAG-RECIPE] LLM 응답 시간 측정
            llm_started_at = (
                time.perf_counter()
            )

            response = _call_gemini(
                prompt
            )

            llm_elapsed_ms = (
                time.perf_counter()
                - llm_started_at
            ) * 1000

            logger.info(
                "[RAG-RECIPE] Gemini 응답 완료. "
                "attempt=%s llm_ms=%.2f",
                attempt + 1,
                llm_elapsed_ms,
            )

            # [RAG-RECIPE] 기존 검증 함수가
            # sources=[]로 변경하기 전에
            # LLM이 생성한 출처를 별도로 저장한다.
            raw_sources = [
                list(
                    recipe.sources
                )
                for recipe in response.recipes
            ]

            # [RAG-RECIPE] 기존 owned_first /
            # nutrition_supplement 검증 규칙 재사용
            _validate_business_rules(
                response=response,
                input_ingredients=normalized_ingredients,
                deficient_nutrients=normalized_nutrients,
                mode=mode,
            )

            # [RAG-RECIPE] 검증 이후 실제 검색 문서의
            # 출처만 다시 복원한다.
            _restore_and_validate_sources(
                response=response,
                raw_sources=raw_sources,
                allowed_sources=allowed_sources,
            )

            total_elapsed_ms = (
                time.perf_counter()
                - total_started_at
            ) * 1000

            logger.info(
                "[RAG-RECIPE] RAG 레시피 생성 성공. "
                "retrieve_ms=%.2f "
                "llm_ms=%.2f "
                "total_ms=%.2f",
                retrieve_elapsed_ms,
                llm_elapsed_ms,
                total_elapsed_ms,
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
    return _direct_fallback(
        ingredients=normalized_ingredients,
        deficient_nutrients=normalized_nutrients,
        mode=mode,
        reason="rag_generation_failed",
        total_started_at=total_started_at,
    )
