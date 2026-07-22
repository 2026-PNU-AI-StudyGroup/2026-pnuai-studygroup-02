# backend/routers/nutrition.py

# [MAIN] 지은 담당. 영양소 관련 라우터 (구현 예정).

from fastapi import APIRouter

router = APIRouter(
    prefix="/api/nutrition",
    tags=["nutrition"],
)
