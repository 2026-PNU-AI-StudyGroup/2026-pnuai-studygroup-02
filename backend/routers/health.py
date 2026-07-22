# backend/routers/health.py

# [MAIN] 현지 담당. 서버 생존 확인용 헬스체크 엔드포인트.

from fastapi import APIRouter

router = APIRouter(
    prefix="/api/health",
    tags=["health"],
)


@router.get("", summary="헬스체크")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
