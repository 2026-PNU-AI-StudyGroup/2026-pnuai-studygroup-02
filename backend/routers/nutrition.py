# backend/routers/nutrition.py

# [ROUTER] 지은 담당, main.py(현지)가 등록. 한국어 주석 필수
# 식단 영양 분석 라우터. 재료별 섭취량(serving_g)을 반영해 영양성분을 계산하고,
# 프로필(성별/나이) 기준 권장섭취량 대비 충족률과 부족 영양소 보완 재료를 반환한다.

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.services import nutrition_service as ns

router = APIRouter(prefix="/api/nutrition", tags=["nutrition"])


# [ROUTER] 분석 요청에 포함되는 프로필 정보
class ProfileInput(BaseModel):
    gender: str = Field(..., description="성별 ('남' 또는 '여')")
    age: int = Field(..., description="나이(세)")


# [ROUTER] 분석 요청에 포함되는 재료 하나의 정보
class IngredientInput(BaseModel):
    ingredient_id: str = Field(..., description="재료 식별용 ID (프론트/모델 쪽 고유값)")
    name: str = Field(..., description="재료명 (모델 출력명 또는 사용자가 입력한 이름)")
    serving_g: float = Field(..., gt=0, description="실제 섭취량(g), 0보다 커야 함")


# [ROUTER] POST /api/nutrition/analyze 요청 바디
class AnalyzeRequest(BaseModel):
    profile: ProfileInput
    ingredients: list[IngredientInput]


@router.post("/analyze", summary="식단 영양 분석")
def analyze_nutrition(payload: AnalyzeRequest) -> dict:
    # 1. 프로필로 권장섭취량 조회 (profile.py의 검증 로직과 동일한 기준 사용)
    recommendation = ns.get_recommendation(payload.profile.gender, payload.profile.age)
    if recommendation is None:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "INVALID_PROFILE",
                "message": "지원하지 않는 나이 범위입니다. (19~49세만 지원)",
            },
        )

    nutrition_data = ns.load_nutrition_data()
    aliases = ns.load_aliases()

    per_ingredient = []
    totals = {key: 0.0 for key in ns.NUTRIENT_KEYS}

    for item in payload.ingredients:
        base_nutrients = ns.get_nutrition_for_ingredient(
            item.name, nutrition_data=nutrition_data, aliases=aliases
        )

        if base_nutrients is None:
            # nutrition.csv에 없는 재료(매칭 실패)는 0으로 처리하고 matched=False로 표시한다.
            per_ingredient.append(
                {
                    "ingredient_id": item.ingredient_id,
                    "name": item.name,
                    "matched": False,
                    "serving_g": item.serving_g,
                    "nutrients": {key: 0.0 for key in ns.NUTRIENT_KEYS},
                }
            )
            continue

        # nutrition.csv는 100g 기준값이므로, 실제 섭취량(serving_g)에 비례해서 환산한다.
        ratio = item.serving_g / 100.0
        scaled_nutrients = {
            key: round(base_nutrients.get(key, 0.0) * ratio, 1) for key in ns.NUTRIENT_KEYS
        }

        for key in ns.NUTRIENT_KEYS:
            totals[key] += scaled_nutrients[key]

        per_ingredient.append(
            {
                "ingredient_id": item.ingredient_id,
                "name": item.name,
                "matched": True,
                "serving_g": item.serving_g,
                "nutrients": scaled_nutrients,
            }
        )

    # 부동소수점 오차 정리
    totals = {key: round(value, 1) for key, value in totals.items()}

    # 2. 전체 섭취 총합 대비 권장섭취량 충족률 계산
    summary = ns.calculate_percentage(totals, recommendation)

    # 3. 충족률이 "낮음"으로 판정된 영양소를 뽑아 보완 재료를 추천한다.
    deficient_nutrients = [row["nutrient"] for row in summary if row["status"] == "낮음"]
    deficient_supplements = ns.get_deficient_ingredients(
        deficient_nutrients, nutrition_data=nutrition_data
    )

    return {
        "per_ingredient": per_ingredient,
        "summary": summary,
        "deficient_supplements": deficient_supplements,
    }
