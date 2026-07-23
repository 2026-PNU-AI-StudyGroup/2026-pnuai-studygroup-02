# [ROUTER] 지은 담당, main.py(현지)가 등록. 한국어 주석 필수

"""
프로필(성별/나이) 기반 권장섭취량 조회 라우터.

POST /api/profile/recommendations
- 입력: {gender, age}
- 출력: kdri.csv 기준 해당 그룹의 권장섭취량
- 범위 밖이거나 잘못된 입력이면 HTTP 400 + {code: "INVALID_PROFILE", message}
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.services import nutrition_service as ns

router = APIRouter(prefix="/api/profile", tags=["profile"])


class ProfileRequest(BaseModel):
    """성별/나이 입력 스키마."""

    gender: str = Field(..., description="성별 ('남' 또는 '여')")
    age: int = Field(..., description="나이(세)")


@router.post("/recommendations")
def get_recommendations(profile: ProfileRequest):
    """
    성별과 나이를 받아 KDRI 기준 권장섭취량을 반환한다.

    - 성별이 '남'/'여'가 아니거나
    - 나이가 지원 범위(19~49세, 4그룹) 밖이면
    HTTP 400과 함께 {code: "INVALID_PROFILE", message} 형태의 에러를 반환한다.
    """
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
        # 나이가 19~49세(4그룹) 범위 밖이거나 매칭되는 그룹이 없는 경우
        raise HTTPException(
            status_code=400,
            detail={
                "code": "INVALID_PROFILE",
                "message": "지원하지 않는 나이 범위입니다. (19~49세만 지원)",
            },
        )

    return recommendation