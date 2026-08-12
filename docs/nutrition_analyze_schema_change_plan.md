# POST /api/nutrition/analyze 요청 스키마 변경 계획

<!-- [ROUTER] 지은 담당. 문서 초안 - 실제 구현은 다음 주. 한국어 주석 필수 -->

> 관련 문서: `docs/gram_feature_design.md` (serving_g 설계 배경)
> 이 문서는 **계획(초안)**이며, 실제 코드 수정은 아직 하지 않는다.

## 1. 현재 상태 (As-Is)

`backend/routers/nutrition.py`의 `IngredientInput` 스키마:

```python
class IngredientInput(BaseModel):
    """분석 요청에 포함되는 재료 하나의 정보."""

    ingredient_id: str = Field(..., description="재료 식별용 ID (프론트/모델 쪽 고유값)")
    name: str = Field(..., description="재료명 (모델 출력명 또는 사용자가 입력한 이름)")
    serving_g: float = Field(..., gt=0, description="실제 섭취량(g), 0보다 커야 함")
```

문제점:
- `serving_g`가 **필수(required) 필드**다. `...`(Ellipsis)로 되어 있어, 프론트/모델 쪽에서
  이 값을 안 보내면 요청 자체가 422(스키마 검증 실패)로 거부된다.
- **상한선이 없다**. `gt=0`만 있어서 이론상 100000처럼 비현실적인 값도 통과한다.
- `nutrition_service.calculate_totals()`가 이제 `{"name", "serving_g"}` 딕셔너리를
  지원하도록 수정됐으므로, 라우터에서 굳이 수동으로 `ratio = serving_g / 100.0` 계산을
  중복할 필요가 없어졌다 (서비스 함수 재사용 가능).

## 2. 목표 상태 (To-Be)

### 2-1. 필드 변경

```python
class IngredientInput(BaseModel):
    """분석 요청에 포함되는 재료 하나의 정보."""

    ingredient_id: str = Field(..., description="재료 식별용 ID (프론트/모델 쪽 고유값)")
    name: str = Field(..., description="재료명 (모델 출력명 또는 사용자가 입력한 이름)")
    serving_g: float = Field(
        default=100,
        ge=1,
        le=2000,
        description="실제 섭취량(g). 생략 시 기본값 100g. 허용 범위 1~2000g",
    )
```

변경 요약:

| 항목 | 기존 | 변경 후 | 이유 |
|---|---|---|---|
| 필수 여부 | 필수(`...`) | 선택(기본값 `100`) | serving_g 없이 보내는 기존/구버전 클라이언트와의 호환 |
| 하한 | `gt=0` (0 초과) | `ge=1` (1 이상) | `docs/gram_feature_design.md`의 허용 범위(1~2000)와 통일 |
| 상한 | 없음 | `le=2000` | 비현실적인 섭취량 입력 방지 |

### 2-2. 라우터 로직 변경 (analyze_nutrition 함수)

현재는 라우터 안에서 직접 스케일링하고 있다:

```python
ratio = item.serving_g / 100.0
scaled_nutrients = {
    key: round(base_nutrients.get(key, 0.0) * ratio, 1) for key in ns.NUTRIENT_KEYS
}
```

앞으로는 `nutrition_service.calculate_totals()`가 `{"name", "serving_g"}` 형태를
지원하므로, `per_ingredient`(재료별 상세 내역)는 지금처럼 라우터에서 직접 계산하되,
`totals`(전체 합계) 부분은 아래처럼 서비스 함수를 재사용하는 방향으로 정리할 계획이다.

```python
# 변경 후 예시 (개념 스케치, 실제 구현 시 세부 조정 가능)
ingredient_dicts = [
    {"name": item.name, "serving_g": item.serving_g} for item in payload.ingredients
]
totals = ns.calculate_totals(
    ingredient_dicts, nutrition_data=nutrition_data, aliases=aliases
)
```

`per_ingredient` 응답(재료별 matched 여부, 개별 nutrients 표시)은 사용자에게
보여주는 상세 내역이라 라우터에 남겨두고, "총합 계산"만 서비스 함수로 위임해서
계산 로직 중복을 없애는 것이 목표다.

## 3. 응답(response) 형식 변경 여부

**응답 형식은 변경하지 않는다.** 지금 확정된 응답 구조를 그대로 유지:

```json
{
  "per_ingredient": [...],
  "summary": [...],
  "deficient_supplements": [...]
}
```

`serving_g` 기본값/범위 변경은 **요청 스키마에만** 영향을 준다.

## 4. 하위 호환 / 영향 범위 체크

- [ ] 프론트엔드가 이미 `serving_g`를 항상 채워서 보내고 있는지 확인 필요
      (필수 → 선택으로 바뀌는 것뿐이라 기존에 값을 보내던 클라이언트는 영향 없음)
- [ ] `serving_g`를 2000 초과로 보내던 테스트/목업 데이터가 있다면 422 에러로 바뀜
      → 팀 목업 데이터(`backend/mock/`) 점검 필요
- [ ] `serving_g`를 0 이하로 보내던 경우 기존엔 `gt=0` 위반으로도 422였으므로 동작 차이 없음

## 5. 테스트 계획 (구현 후 확인할 것)

| 케이스 | 입력 | 기대 결과 |
|---|---|---|
| serving_g 생략 | `{"ingredient_id": "1", "name": "두부"}` | 기본값 100으로 처리, 200 응답 |
| serving_g 정상 범위 | `serving_g: 150` | 150g 기준으로 스케일링된 값, 200 응답 |
| serving_g 하한 미만 | `serving_g: 0` | 422 (ge=1 위반) |
| serving_g 상한 초과 | `serving_g: 3000` | 422 (le=2000 위반) |
| 기존 회귀 테스트 | 이전 `test_my_routes.py` 케이스 재실행 | 응답 구조·값 동일하게 유지되는지 확인 |

## 6. 일정

- 이번 주: 계획 문서 작성 (본 문서)
- 다음 주: `IngredientInput` 필드 수정 + 라우터 로직에서 `calculate_totals()` 재사용하도록 리팩터링 + 위 테스트 케이스로 회귀 확인 후 커밋