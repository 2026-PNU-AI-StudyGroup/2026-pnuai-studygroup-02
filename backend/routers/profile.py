# backend/routers/profile.py

# [MAIN] 프로필 관련 라우터 (구현 예정).

from fastapi import APIRouter

router = APIRouter(
    prefix="/api/profile",
    tags=["profile"],
)
