# backend/services/recipe_indexer.py

# [RAG-INDEX] 레시피 JSONL을 청킹하고
# 임베딩을 생성하여 FAISS 로컬 인덱스로 저장한다.
# 한국어 주석 필수

import json
from pathlib import Path
from typing import Any

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer


# 프로젝트 루트
PROJECT_ROOT = (
    Path(__file__).resolve().parent.parent.parent
)

# 원본 레시피 코퍼스
CORPUS_PATH = (
    PROJECT_ROOT
    / "data"
    / "recipe_corpus"
    / "recipes.jsonl"
)

# 인덱스 저장 폴더
INDEX_DIR = (
    PROJECT_ROOT
    / "data"
    / "recipe_corpus"
    / "index"
)

# FAISS 인덱스 파일
INDEX_PATH = INDEX_DIR / "recipes.faiss"

# FAISS 인덱스 번호와 실제 텍스트를 연결하기 위한 메타데이터
CHUNKS_PATH = INDEX_DIR / "chunks.jsonl"

# 임베딩 설정을 기록하는 파일
CONFIG_PATH = INDEX_DIR / "config.json"


# 한국어를 포함한 다국어 임베딩 모델
MODEL_NAME = (
    "sentence-transformers/"
    "paraphrase-multilingual-MiniLM-L12-v2"
)

# 문자 기준 청킹 크기
CHUNK_SIZE = 700

# 청크 사이 중복 문자 수
CHUNK_OVERLAP = 100


def load_recipes() -> list[dict[str, Any]]:
    """
    [RAG-INDEX] recipes.jsonl 파일을 읽어
    레시피 목록으로 반환한다.
    """

    recipes: list[dict[str, Any]] = []

    if not CORPUS_PATH.exists():
        raise FileNotFoundError(
            f"레시피 코퍼스가 없습니다: {CORPUS_PATH}"
        )

    with CORPUS_PATH.open(
        "r",
        encoding="utf-8",
    ) as file:
        for line_number, line in enumerate(
            file,
            start=1,
        ):
            line = line.strip()

            if not line:
                continue

            try:
                recipe = json.loads(line)

            except json.JSONDecodeError as exc:
                print(
                    "[RAG-INDEX] JSON 파싱 실패. "
                    f"line={line_number} error={exc}"
                )
                continue

            recipes.append(recipe)

    return recipes


def recipe_to_text(
    recipe: dict[str, Any],
) -> str:
    """
    [RAG-INDEX] 레시피 딕셔너리를
    검색하기 좋은 하나의 텍스트로 변환한다.
    """

    title = str(
        recipe.get("title", "")
    ).strip()

    ingredients = recipe.get(
        "ingredients",
        [],
    )

    steps = recipe.get(
        "steps",
        [],
    )

    ingredient_text = (
        ", ".join(
            str(item)
            for item in ingredients
            if item
        )
    )

    if not ingredient_text:
        ingredient_text = "재료 정보 없음"

    step_lines = []

    for index, step in enumerate(
        steps,
        start=1,
    ):
        step = str(step).strip()

        if step:
            step_lines.append(
                f"{index}. {step}"
            )

    steps_text = "\n".join(
        step_lines
    )

    return (
        f"레시피명: {title}\n"
        f"재료: {ingredient_text}\n"
        f"조리법:\n{steps_text}"
    )


def split_text(
    text: str,
    chunk_size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
) -> list[str]:
    """
    [RAG-INDEX] 긴 레시피 텍스트를
    문자 단위로 겹치게 청킹한다.
    """

    if chunk_size <= overlap:
        raise ValueError(
            "chunk_size는 overlap보다 커야 합니다."
        )

    text = text.strip()

    if not text:
        return []

    if len(text) <= chunk_size:
        return [text]

    chunks: list[str] = []

    start = 0

    while start < len(text):
        end = min(
            start + chunk_size,
            len(text),
        )

        chunk = text[start:end].strip()

        if chunk:
            chunks.append(chunk)

        if end >= len(text):
            break

        start = end - overlap

    return chunks


def create_chunks(
    recipes: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    [RAG-INDEX] 모든 레시피를 청킹하고
    각 청크에 메타데이터를 붙인다.
    """

    chunks: list[dict[str, Any]] = []

    chunk_id = 0

    for recipe_id, recipe in enumerate(
        recipes
    ):
        title = str(
            recipe.get("title", "")
        ).strip()

        source = recipe.get(
            "source",
            {},
        )

        recipe_text = recipe_to_text(
            recipe
        )

        recipe_chunks = split_text(
            recipe_text
        )

        for chunk_index, chunk_text in enumerate(
            recipe_chunks
        ):
            # [RAG-INDEX] 두 번째 청크 이후에도
            # 어떤 레시피인지 알 수 있도록 제목을 붙인다.
            if not chunk_text.startswith(
                "레시피명:"
            ):
                chunk_text = (
                    f"레시피명: {title}\n"
                    f"{chunk_text}"
                )

            chunk = {
                "id": chunk_id,
                "recipe_id": recipe_id,
                "chunk_index": chunk_index,
                "title": title,
                "text": chunk_text,
                "source": source,
            }

            chunks.append(chunk)

            chunk_id += 1

    return chunks


def save_chunks(
    chunks: list[dict[str, Any]],
) -> None:
    """
    [RAG-INDEX] FAISS의 벡터 번호와
    원문 청크를 연결하기 위해 JSONL로 저장한다.
    """

    with CHUNKS_PATH.open(
        "w",
        encoding="utf-8",
    ) as file:
        for chunk in chunks:
            json.dump(
                chunk,
                file,
                ensure_ascii=False,
            )

            file.write("\n")


def build_index() -> None:
    """
    [RAG-INDEX] 레시피를 청킹하고 임베딩한 후
    FAISS 인덱스로 저장한다.
    """

    print(
        "[RAG-INDEX] 레시피 코퍼스를 읽습니다."
    )

    recipes = load_recipes()

    print(
        f"[RAG-INDEX] 레시피 {len(recipes)}개 로드 완료"
    )

    chunks = create_chunks(
        recipes
    )

    print(
        f"[RAG-INDEX] 청크 {len(chunks)}개 생성 완료"
    )

    if not chunks:
        raise RuntimeError(
            "생성된 청크가 없습니다."
        )

    print(
        "[RAG-INDEX] 임베딩 모델을 불러옵니다."
    )

    model = SentenceTransformer(
        MODEL_NAME
    )

    texts = [
        chunk["text"]
        for chunk in chunks
    ]

    print(
        "[RAG-INDEX] 임베딩을 생성합니다."
    )

    embeddings = model.encode(
        texts,
        batch_size=32,
        show_progress_bar=True,
        convert_to_numpy=True,

        # [RAG-INDEX] 코사인 유사도 검색을 위해
        # 임베딩을 단위 벡터로 정규화한다.
        normalize_embeddings=True,
    )

    embeddings = np.asarray(
        embeddings,
        dtype="float32",
    )

    dimension = embeddings.shape[1]

    print(
        "[RAG-INDEX] "
        f"임베딩 shape={embeddings.shape}"
    )

    # [RAG-INDEX] 정규화된 벡터에 Inner Product를 사용하면
    # 코사인 유사도 기반 검색이 가능하다.
    index = faiss.IndexFlatIP(
        dimension
    )

    index.add(
        embeddings
    )

    INDEX_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    faiss.write_index(
        index,
        str(INDEX_PATH),
    )

    save_chunks(
        chunks
    )

    config = {
        "model_name": MODEL_NAME,
        "embedding_dimension": dimension,
        "recipe_count": len(recipes),
        "chunk_count": len(chunks),
        "chunk_size": CHUNK_SIZE,
        "chunk_overlap": CHUNK_OVERLAP,
        "index_type": "IndexFlatIP",
        "metric": "cosine_similarity",
    }

    with CONFIG_PATH.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            config,
            file,
            ensure_ascii=False,
            indent=2,
        )

    print()
    print(
        "[RAG-INDEX] 인덱스 생성 완료"
    )
    print(
        f"[RAG-INDEX] 레시피 수: {len(recipes)}"
    )
    print(
        f"[RAG-INDEX] 청크 수: {len(chunks)}"
    )
    print(
        f"[RAG-INDEX] 벡터 수: {index.ntotal}"
    )
    print(
        f"[RAG-INDEX] 저장 위치: {INDEX_DIR}"
    )


if __name__ == "__main__":
    build_index()