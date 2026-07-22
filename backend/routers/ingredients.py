# backend/routers/ingredients.py

# [MAIN] 현지 담당. 식재료 관련 라우터 (구현 예정).

from fastapi import APIRouter

router = APIRouter(
    prefix="/api/ingredients",
    tags=["ingredients"],
)
