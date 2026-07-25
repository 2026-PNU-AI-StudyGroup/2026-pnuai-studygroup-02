# backend/routers/profile.py

# [ROUTER] 지은 담당, main.py(현지)가 등록. 한국어 주석 필수
# 프로필(성별/나이) 기반 권장섭취량 조회 라우터.

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.services import nutrition_service as ns

router = APIRouter(prefix="/api/profile", tags=["profile"])


# [ROUTER] POST /api/profile/recommendations 요청 바디 (성별/나이)
class ProfileRequest(BaseModel):
    gender: str = Field(..., description="성별 ('남' 또는 '여')")
    age: int = Field(..., description="나이(세)")


@router.post("/recommendations", summary="프로필 기반 권장섭취량 조회")
def get_recommendations(profile: ProfileRequest) -> dict:
    if profile.gender not in ("남", "여"):
        raise HTTPException(
            status_code=400,
            detail={
                "code": "INVALID_PROFILE",
                "message": "성별은 '남' 또는 '여'만 입력 가능합니다.",
            },
        )

    recommendation = ns.get_recommendation(profile.gender, profile.age)

    if recommendation is None:
        # [ROUTER] 나이가 19~49세(4그룹) 범위 밖이거나 매칭되는 그룹이 없는 경우
        raise HTTPException(
            status_code=400,
            detail={
                "code": "INVALID_PROFILE",
                "message": "지원하지 않는 나이 범위입니다. (19~49세만 지원)",
            },
        )

    return recommendation
