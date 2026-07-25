# backend/routers/ingredients.py

# [ROUTER] 현지 담당. 한국어 주석 필수
# 식재료 이미지 예측(POST /predict)과 재료명 검색(GET /search) API를 제공한다.

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile

from backend.services import image_service

router = APIRouter(
    prefix="/api/ingredients",
    tags=["ingredients"],
)

# [ROUTER] 모델 출력명(alias) -> 실제 재료명 매핑 파일 (data/ingredient_aliases.json)
ALIASES_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "data"
    / "ingredient_aliases.json"
)


# [ROUTER] ingredient_aliases.json의 "aliases" 맵을 읽어온다.
# 파일이 없거나 형식이 잘못된 경우 빈 매핑을 반환해 검색 API가 500 대신 빈 결과를 준다.
def _load_aliases() -> dict[str, str]:
    if not ALIASES_PATH.exists():
        return {}

    with ALIASES_PATH.open(mode="r", encoding="utf-8") as file:
        data = json.load(file)

    return data.get("aliases", {})


@router.post("/predict", summary="이미지 기반 식재료 예측")
async def predict_ingredients(
    images: list[UploadFile] = File(..., description="분류할 식재료 이미지 목록"),
) -> dict[str, Any]:
    if not images:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "NO_IMAGES",
                "message": "이미지를 1개 이상 업로드해야 합니다.",
            },
        )

    result = image_service.predict_batch(images)

    # [ROUTER] 모델은 영어 클래스명(potato 등)을 반환하므로, ingredient_aliases.json 기준으로
    # 사용자에게 보여줄 한글 재료명(감자 등)으로 변환한다. 매핑에 없는 이름은 원본을 그대로 둔다.
    aliases = _load_aliases()

    for item in result.get("results", []):
        if item.get("name"):
            item["name"] = aliases.get(item["name"], item["name"])

        for candidate in item.get("candidates", []):
            if candidate.get("name"):
                candidate["name"] = aliases.get(candidate["name"], candidate["name"])

    return result


@router.get("/search", summary="재료명 검색")
def search_ingredients(query: str) -> dict[str, Any]:
    query = query.strip()

    if not query:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "EMPTY_QUERY",
                "message": "검색어(query)를 입력해야 합니다.",
            },
        )

    aliases = _load_aliases()

    # [ROUTER] 별칭(alias)과 실제 재료명(name) 양쪽에 대해 단순 문자열 포함 검색을 수행한다.
    results = [
        {"alias": alias, "name": name}
        for alias, name in aliases.items()
        if query in alias or query in name
    ]

    return {"query": query, "results": results}
