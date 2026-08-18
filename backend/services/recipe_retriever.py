# backend/services/recipe_retriever.py

# [RAG-RETRIEVE] 시은 담당

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer


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
    index = faiss.read_index(
        str(INDEX_PATH)
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


def _build_query(
    ingredients: list[str],
) -> str:
    """
    [RAG-RETRIEVE] 보유 재료 목록을
    벡터 검색용 문장으로 변환한다.
    """

    cleaned = [
        str(ingredient).strip()
        for ingredient in ingredients
        if str(ingredient).strip()
    ]

    if not cleaned:
        return ""

    ingredient_text = ", ".join(
        cleaned
    )

    return (
        "다음 재료를 활용할 수 있는 레시피: "
        f"{ingredient_text}"
    )


def search(
    ingredients: list[str],
    k: int = 5,
) -> list[dict]:
    """
    [RAG-RETRIEVE] 보유 재료 목록을 이용해
    FAISS 벡터 인덱스에서 관련 레시피 top-k를 검색한다.

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

    # [RAG-RETRIEVE] 하나의 레시피가 여러 청크로
    # 나뉘어 있을 수 있으므로 k보다 넉넉하게 검색한다.
    candidate_k = min(
        max(k * 5, k),
        index.ntotal,
    )

    scores, indices = index.search(
        query_embedding,
        candidate_k,
    )

    results: list[dict] = []

    # [RAG-RETRIEVE] 같은 레시피가 여러 청크에서
    # 검색되더라도 한 번만 반환하기 위해 사용한다.
    seen_recipe_ids: set[int] = set()

    for vector_index in indices[0]:
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

        results.append(
            result
        )

        seen_recipe_ids.add(
            recipe_id
        )

        if len(results) >= k:
            break

    return results


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