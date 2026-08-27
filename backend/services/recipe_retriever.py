# backend/services/recipe_retriever.py

# [RAG-RETRIEVE] 시은 담당

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np


# [RAG-RETRIEVE] 프로젝트 루트 경로
PROJECT_ROOT = (
    Path(__file__).resolve().parent.parent.parent
)

# [RAG-RETRIEVE] 레시피 원본 데이터
CORPUS_PATH = (
    PROJECT_ROOT
    / "data"
    / "recipe_corpus"
    / "recipes.jsonl"
)

# [RAG-RETRIEVE] FAISS 인덱스 저장 폴더
INDEX_DIR = (
    PROJECT_ROOT
    / "data"
    / "recipe_corpus"
    / "index"
)

INDEX_PATH = INDEX_DIR / "recipes.faiss"
CHUNKS_PATH = INDEX_DIR / "chunks.jsonl"
CONFIG_PATH = INDEX_DIR / "config.json"

# [RAG-RETRIEVE] 재료명 별칭 매핑 (backend/routers/ingredients.py와 동일 파일 공유)
# 예: "소세지", "소시지", "후랑크소세지" 등이 전부 "비엔나소세지"로 묶여 있다.
ALIASES_PATH = (
    PROJECT_ROOT
    / "data"
    / "ingredient_aliases.json"
)


def _load_jsonl(
    path: Path,
) -> list[dict[str, Any]]:
    """
    [RAG-RETRIEVE] JSONL 파일을 읽어
    딕셔너리 목록으로 반환한다.
    """

    if not path.exists():
        raise FileNotFoundError(
            f"파일을 찾을 수 없습니다: {path}"
        )

    result: list[dict[str, Any]] = []

    with path.open(
        "r",
        encoding="utf-8",
    ) as file:
        for line in file:
            line = line.strip()

            if not line:
                continue

            result.append(
                json.loads(line)
            )

    return result


@lru_cache(maxsize=1)
def _load_retrieval_resources():
    """
    [RAG-RETRIEVE] FAISS 인덱스, 청크,
    레시피 원본, 임베딩 모델을 최초 1회만 로딩한다.

    이후 search() 호출에서는 캐시된 객체를 재사용한다.
    """

    # [RAG-RETRIEVE] faiss, sentence-transformers(torch 포함)는 임포트 자체가
    # 무거워 RAG 기능이 실제로 필요할 때만 불러온다. (배포 환경 메모리 절약)
    import faiss
    from sentence_transformers import SentenceTransformer

    if not INDEX_PATH.exists():
        raise FileNotFoundError(
            "FAISS 인덱스가 없습니다. "
            "recipe_indexer.py를 먼저 실행하세요."
        )

    if not CONFIG_PATH.exists():
        raise FileNotFoundError(
            f"인덱스 설정 파일이 없습니다: {CONFIG_PATH}"
        )

    # [RAG-RETRIEVE] FAISS 인덱스 로딩
    # faiss.read_index(경로)는 내부적으로 C++ fopen을 사용해 비-ASCII 경로(한글 등)에서
    # "Illegal byte sequence" 오류가 날 수 있어, 바이트를 직접 읽어 역직렬화한다.
    index = faiss.deserialize_index(
        np.frombuffer(INDEX_PATH.read_bytes(), dtype=np.uint8)
    )

    # [RAG-RETRIEVE] FAISS 벡터와 연결된 청크 정보 로딩
    chunks = _load_jsonl(
        CHUNKS_PATH
    )

    # [RAG-RETRIEVE] 최종 검색 결과에
    # 재료와 조리단계를 포함하기 위해 원본 레시피도 로딩한다.
    recipes = _load_jsonl(
        CORPUS_PATH
    )

    # [RAG-RETRIEVE] 인덱스를 만들 때 사용한
    # 임베딩 모델명을 그대로 사용한다.
    with CONFIG_PATH.open(
        "r",
        encoding="utf-8",
    ) as file:
        config = json.load(file)

    model_name = config.get(
        "model_name"
    )

    if not model_name:
        raise ValueError(
            "config.json에 model_name이 없습니다."
        )

    model = SentenceTransformer(
        model_name
    )

    print(
        "[RAG-RETRIEVE] "
        "FAISS 인덱스와 임베딩 모델 로딩 완료"
    )

    return (
        index,
        chunks,
        recipes,
        model,
    )


def _clean_ingredients(
    ingredients: list[str],
) -> list[str]:
    """
    [RAG-RETRIEVE] 보유 재료 목록에서
    빈 문자열을 제거하고 공백을 정리한다.
    """

    return [
        str(ingredient).strip()
        for ingredient in ingredients
        if str(ingredient).strip()
    ]


# [RAG-RETRIEVE] 요리의 정체성을 좌우하는 주재료(단백질류) 판별 키워드.
# "마늘", "대파" 같은 부재료 하나만 겹쳐도 같은 요리로 취급되는 걸 막기 위해,
# 검색 매칭 가중치와 출처 검증에 함께 쓰인다.
PROTEIN_KEYWORDS: tuple[str, ...] = (
    "고기",
    "닭",
    "돼지",
    "소고기",
    "한우",
    "삼겹살",
    "목살",
    "안심",
    "등심",
    "차돌박이",
    "우삼겹",
    "오징어",
    "새우",
    "생선",
    "고등어",
    "연어",
    "참치",
    "계란",
    "달걀",
    "두부",
    "소세지",
    "소시지",
)

# [RAG-RETRIEVE] 주재료 매칭에 부여할 가중치 (부재료는 1.0)
PROTEIN_WEIGHT = 2.0
DEFAULT_WEIGHT = 1.0


def _is_protein_ingredient(
    ingredient: str,
) -> bool:
    """
    [RAG-RETRIEVE] 요리의 정체성을 결정하는 주재료(단백질류)인지 판별한다.
    """

    normalized = ingredient.replace(
        " ",
        "",
    )

    return any(
        keyword in normalized
        for keyword in PROTEIN_KEYWORDS
    )


def _ingredient_weight(
    ingredient: str,
) -> float:
    """
    [RAG-RETRIEVE] 재료 매칭 시 반영할 가중치.
    주재료는 부재료보다 요리를 특정하는 데 더 중요하므로 더 큰 가중치를 준다.
    """

    return (
        PROTEIN_WEIGHT
        if _is_protein_ingredient(ingredient)
        else DEFAULT_WEIGHT
    )


def _build_query(
    ingredients: list[str],
) -> str:
    """
    [RAG-RETRIEVE] 보유 재료 목록을
    벡터 검색용 문장으로 변환한다.
    """

    cleaned = _clean_ingredients(
        ingredients
    )

    if not cleaned:
        return ""

    ingredient_text = ", ".join(
        cleaned
    )

    return (
        "다음 재료를 활용할 수 있는 레시피: "
        f"{ingredient_text}"
    )


@lru_cache(maxsize=1)
def _load_ingredient_aliases() -> dict[str, str]:
    """
    [RAG-RETRIEVE] ingredient_aliases.json의 "aliases" 맵을 읽어온다.
    파일이 없거나 형식이 잘못된 경우 빈 매핑을 반환한다.
    """

    if not ALIASES_PATH.exists():
        return {}

    with ALIASES_PATH.open(
        "r",
        encoding="utf-8",
    ) as file:
        data = json.load(file)

    return data.get("aliases", {})


@lru_cache(maxsize=1)
def _build_synonym_index() -> dict[str, frozenset[str]]:
    """
    [RAG-RETRIEVE] 별칭 매핑을 "같은 재료를 가리키는 표현들의 묶음"으로 재구성한다.

    예) "소세지", "소시지", "후랑크소세지", "비엔나소세지"는 모두
    같은 그룹으로 묶여, 쿼리에 어느 표현이 들어와도 서로를 매칭할 수 있다.
    (공백은 비교 전 제거한다: "비엔나 소세지" == "비엔나소세지")
    """

    aliases = _load_ingredient_aliases()

    canonical_groups: dict[str, set[str]] = {}

    for alias_key, canonical in aliases.items():
        canonical_norm = canonical.replace(
            " ",
            "",
        )

        alias_norm = alias_key.replace(
            " ",
            "",
        )

        group = canonical_groups.setdefault(
            canonical_norm,
            {canonical_norm},
        )

        group.add(
            alias_norm
        )

    index: dict[str, frozenset[str]] = {}

    for group in canonical_groups.values():
        frozen_group = frozenset(
            group
        )

        for term in group:
            index[term] = frozen_group

    return index


def _expand_synonyms(
    ingredient: str,
) -> frozenset[str]:
    """
    [RAG-RETRIEVE] 재료명 하나를 별칭 그룹으로 확장한다.
    그룹에 속하지 않으면 자기 자신만 담은 집합을 반환한다.
    """

    normalized = ingredient.replace(
        " ",
        "",
    )

    index = _build_synonym_index()

    return index.get(
        normalized,
        frozenset(
            {normalized}
        ),
    )


# [RAG-RETRIEVE] 한글 완성형 음절 범위. 이 범위 문자가 좌우로 이어지면
# "같은 단어의 일부"로 간주해 부분 문자열 오탐(예: "파"가 "양파" 안에서 매칭)을 막는다.
_HANGUL_SYLLABLE = re.compile(
    r"[가-힣]"
)


def _contains_ingredient_term(
    recipe_text: str,
    term: str,
) -> bool:
    """
    [RAG-RETRIEVE] recipe_text 안에 term이 "독립된 단어"로 등장하는지 확인한다.

    단순 부분 문자열 검사(`term in text`)는 "파"가 "양파", "파프리카"
    안에서도 매칭되는 오탐을 일으킨다. term의 앞/뒤가 한글 음절이 아니라면
    (문자열 시작/끝, 공백, 괄호, 숫자 등) 독립된 단어로 판단한다.
    """

    if not term:
        return False

    start = 0

    while True:
        index = recipe_text.find(
            term,
            start,
        )

        if index == -1:
            return False

        before = (
            recipe_text[index - 1]
            if index > 0
            else ""
        )

        after_index = index + len(term)

        after = (
            recipe_text[after_index]
            if after_index < len(recipe_text)
            else ""
        )

        if (
            not _HANGUL_SYLLABLE.match(before)
            and not _HANGUL_SYLLABLE.match(after)
        ):
            return True

        start = index + 1


def _match_ratio(
    query_ingredients: list[str],
    recipe_ingredients: list,
) -> float:
    """
    [RAG-RETRIEVE] 쿼리 재료 중 레시피 재료 목록에
    실제로 포함된 재료의 가중 비율을 계산한다.

    표기가 다르더라도(오타, 동의어) 같은 재료로 인식되도록
    ingredient_aliases.json 기반 별칭 그룹으로 확장해서 비교한다.

    닭고기·삼겹살 같은 주재료는 요리의 정체성을 좌우하므로
    마늘·대파 같은 부재료보다 더 큰 가중치(PROTEIN_WEIGHT)로 반영한다.
    그렇지 않으면 부재료 하나만 겹쳐도 "매칭됐다"고 판단해,
    전혀 다른 요리가 상위로 올라오거나 출처 검증을 통과하는 문제가 있었다.

    임베딩 유사도는 "의미가 비슷한 레시피"는 잘 찾지만
    "이 재료가 실제로 들어있는가"는 보장하지 않으므로,
    이 값을 최종 점수에 함께 반영해 재료 매칭을 보정한다.
    """

    if not query_ingredients:
        return 0.0

    recipe_text = " ".join(
        str(item) for item in recipe_ingredients
    )

    matched_weight = 0.0
    total_weight = 0.0

    for ingredient in query_ingredients:
        weight = _ingredient_weight(
            ingredient
        )

        total_weight += weight

        synonyms = _expand_synonyms(
            ingredient
        )

        if any(
            _contains_ingredient_term(
                recipe_text,
                synonym,
            )
            for synonym in synonyms
        ):
            matched_weight += weight

    if total_weight <= 0:
        return 0.0

    return matched_weight / total_weight


def search(
    ingredients: list[str],
    k: int = 5,
) -> list[dict]:
    """
    [RAG-RETRIEVE] 보유 재료 목록을 이용해
    FAISS 벡터 인덱스에서 관련 레시피 top-k를 검색한다.

    보유 재료 매칭 비율을 1순위, 임베딩 유사도를 2순위(동점 시
    타이브레이커)로 정렬한다. "재료가 많이 겹치는 레시피"를
    우선하기 위함이며, 가중합 방식은 어휘 매칭으로만 찾은
    후보(유사도 점수 없음)가 항상 밀리는 문제가 있어 채택하지 않았다.

    반환값:
    [
        {
            "title": 레시피명,
            "ingredients": 재료 목록,
            "steps": 조리 단계,
            "source": 출처 정보,
        },
        ...
    ]
    """

    if not ingredients:
        return []

    if k <= 0:
        return []

    cleaned_ingredients = _clean_ingredients(
        ingredients
    )

    query = _build_query(
        ingredients
    )

    if not query:
        return []

    (
        index,
        chunks,
        recipes,
        model,
    ) = _load_retrieval_resources()

    # [RAG-RETRIEVE] 검색 문장을
    # 인덱스 생성 시와 동일한 방식으로 임베딩한다.
    query_embedding = model.encode(
        [query],
        convert_to_numpy=True,
        normalize_embeddings=True,
    )

    query_embedding = np.asarray(
        query_embedding,
        dtype="float32",
    )

    # [RAG-RETRIEVE] 재료 매칭 비율로 재정렬하면 임베딩 상위권 밖에 있던
    # 레시피가 올라올 수 있으므로, k보다 훨씬 넉넉하게 후보를 확보한다.
    candidate_k = min(
        max(k * 10, k),
        index.ntotal,
    )

    scores, indices = index.search(
        query_embedding,
        candidate_k,
    )

    # [RAG-RETRIEVE] 같은 레시피가 여러 청크에서
    # 검색되더라도 한 번만 반영하기 위해 사용한다.
    seen_recipe_ids: set[int] = set()

    # [RAG-RETRIEVE] 정렬 키는 (재료 매칭 비율, 임베딩 유사도) 튜플이며,
    # 어휘 매칭으로만 추가된 후보는 유사도가 없으므로 0.0으로 둔다
    # (같은 매칭 비율의 다른 후보보다는 뒤로 밀리되, 매칭 비율 자체는
    # 그대로 반영되어 살아남는다).
    candidates: list[tuple[float, float, dict]] = []

    for similarity, vector_index in zip(
        scores[0],
        indices[0],
    ):
        if vector_index < 0:
            continue

        if vector_index >= len(chunks):
            continue

        chunk = chunks[
            int(vector_index)
        ]

        recipe_id = chunk.get(
            "recipe_id"
        )

        if recipe_id is None:
            continue

        try:
            recipe_id = int(
                recipe_id
            )
        except (
            TypeError,
            ValueError,
        ):
            continue

        if recipe_id in seen_recipe_ids:
            continue

        if (
            recipe_id < 0
            or recipe_id >= len(recipes)
        ):
            continue

        recipe = recipes[
            recipe_id
        ]

        seen_recipe_ids.add(
            recipe_id
        )

        match_ratio = _match_ratio(
            cleaned_ingredients,
            recipe.get(
                "ingredients",
                [],
            ),
        )

        result = {
            "title": recipe.get(
                "title",
                "",
            ),
            "ingredients": recipe.get(
                "ingredients",
                [],
            ),
            "steps": recipe.get(
                "steps",
                [],
            ),
            "source": recipe.get(
                "source",
                {},
            ),
        }

        candidates.append(
            (
                match_ratio,
                float(similarity),
                result,
            )
        )

    # [RAG-RETRIEVE] 임베딩 검색 상위 후보에 실제 재료가 하나도 안 걸리는 레시피는
    # 재정렬만으로는 살아나지 못한다(애초에 후보 집합에 없으므로).
    # 전체 레시피를 대상으로 재료가 문자 그대로 포함된 레시피를 보강 후보로 추가한다.
    for recipe_id, recipe in enumerate(recipes):
        if recipe_id in seen_recipe_ids:
            continue

        match_ratio = _match_ratio(
            cleaned_ingredients,
            recipe.get(
                "ingredients",
                [],
            ),
        )

        if match_ratio <= 0:
            continue

        seen_recipe_ids.add(
            recipe_id
        )

        result = {
            "title": recipe.get(
                "title",
                "",
            ),
            "ingredients": recipe.get(
                "ingredients",
                [],
            ),
            "steps": recipe.get(
                "steps",
                [],
            ),
            "source": recipe.get(
                "source",
                {},
            ),
        }

        # [RAG-RETRIEVE] 임베딩 후보 밖에서 온 레시피는 유사도 점수가 없다(0.0).
        candidates.append(
            (
                match_ratio,
                0.0,
                result,
            )
        )

    # [RAG-RETRIEVE] (재료 매칭 비율, 임베딩 유사도) 내림차순 정렬 후 상위 k개만 반환한다.
    candidates.sort(
        key=lambda candidate: (
            candidate[0],
            candidate[1],
        ),
        reverse=True,
    )

    return [
        result
        for _, _, result in candidates[:k]
    ]


if __name__ == "__main__":
    # [RAG-RETRIEVE] 간단한 로컬 동작 테스트
    test_ingredients = [
        "돼지고기",
        "양파",
        "감자",
    ]

    test_results = search(
        test_ingredients,
        k=5,
    )

    for index, recipe in enumerate(
        test_results,
        start=1,
    ):
        print()
        print(
            f"[{index}] {recipe['title']}"
        )
        print(
            f"재료: {recipe['ingredients']}"
        )
        print(
            f"조리단계: {recipe['steps']}"
        )
        print(
            f"출처: {recipe['source']}"
        )