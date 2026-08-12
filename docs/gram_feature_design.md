# serving_g(실제 섭취량 그램) 반영 설계

<!-- [DATA] 지은 담당. 설계 문서 - 코드 수정 없음. 한국어 주석 필수 -->

## 1. 문제 상황: 100g 고정 가정이 있는 곳

`backend/services/nutrition_service.py`의 `calculate_totals()` 함수를 보면,
재료 리스트를 받아 **각 재료를 전부 100g씩 섭취했다고 가정**하고 단순 합산한다.

```python
def calculate_totals(
    ingredients: List[str],
    nutrition_data: Optional[Dict[str, Dict[str, float]]] = None,
    aliases: Optional[Dict[str, str]] = None,
) -> Dict[str, float]:
    """
    재료명 리스트를 받아 각 재료를 100g씩 섭취했다고 가정하고 영양소 합계를 계산한다.
    ...
    """
    ...
    for ingredient in ingredients:
        nutrients = get_nutrition_for_ingredient(...)
        if nutrients is None:
            continue
        for key in NUTRIENT_KEYS:
            totals[key] += nutrients.get(key, 0.0)   # <- 100g 기준값을 그대로(1배) 더함
    ...
```

- 함수 시그니처가 `ingredients: List[str]` (재료 "이름"만 받음) 이라서, 애초에
  **재료별 실제 섭취량을 입력받을 자리가 없다.**
- `nutrition.csv`의 값은 100g 기준이므로, `nutrients.get(key)`를 그대로 더하는 건
  "이 재료를 정확히 100g 먹었다"는 가정과 같다. 재료를 30g만 먹었든 500g을 먹었든
  똑같이 100g 값으로 계산되어 실제 섭취량과 괴리가 생긴다.

### 참고: 라우터에서 이미 임시로 우회 중

`backend/routers/nutrition.py`의 `/api/nutrition/analyze`는 이 문제를 알고 있어서,
`calculate_totals()`를 쓰지 않고 **라우터 코드 안에서 직접** `serving_g / 100` 비율로
스케일링하는 로직을 중복 구현해뒀다.

```python
ratio = item.serving_g / 100.0
scaled_nutrients = {
    key: round(base_nutrients.get(key, 0.0) * ratio, 1) for key in ns.NUTRIENT_KEYS
}
```

즉 현재는 "서비스 계층(`calculate_totals`)"과 "라우터 계층"에 계산 로직이
**이중으로 존재**하는 상태다. `calculate_totals`가 serving_g를 지원하게 되면
라우터 쪽 중복 로직을 제거하고 서비스 함수를 호출하는 형태로 정리할 수 있다.

---

## 2. serving_g 필드는 어디에 추가할 것인가

### 선택지 비교

| 위치 | 설명 | 장점 | 단점 |
|---|---|---|---|
| A. 요청 스키마 최상위 (`serving_g: float`, 전체 공통) | 분석 요청 전체에 대해 1개 값만 적용 | 구조 단순 | 재료마다 실제 섭취량이 다른 현실을 반영 못함(예: 밥 150g + 대파 5g을 같은 비율로 계산하게 됨) |
| **B. 재료 객체 안 (`{ingredient_id, name, serving_g}`)** | 재료마다 개별 섭취량 지정 | 재료별 실제 섭취량을 정확히 반영 가능, 현재 `/api/nutrition/analyze`의 `IngredientInput` 구조와 이미 일치 | 재료 개수만큼 값을 입력/검증해야 함(입력 부담 소폭 증가) |

### 결론: **B안 (재료 객체 안)** 채택

- 이미 `routers/nutrition.py`의 `IngredientInput` 스키마에
  `ingredient_id, name, serving_g`가 정의되어 있어 **현재 API 계약과 100% 일치**한다.
- `calculate_totals()`가 받는 `ingredients` 파라미터 타입을
  `List[str]` → `List[Dict]` (또는 `List[IngredientInput]`류) 형태로 바꿔서
  각 원소가 `{name, serving_g}`를 갖도록 확장하는 방향이 자연스럽다.
- A안(공통 1개 값)은 "한 끼 전체를 몇 그램 먹었다"는 식이라 재료별 정밀 계산이 불가능해서 기각.

### 함수 시그니처 변경 방향 (설계만, 코드는 아직 미수정)

```python
# 변경 전
def calculate_totals(ingredients: List[str], ...) -> Dict[str, float]:
    ...

# 변경 후 (예시안)
def calculate_totals(
    ingredients: List[Dict[str, object]],  # [{"name": "두부", "serving_g": 150}, ...]
    ...
) -> Dict[str, float]:
    ...
    for item in ingredients:
        name = item["name"]
        serving_g = item.get("serving_g", DEFAULT_SERVING_G)  # 기본값 100
        ratio = serving_g / 100.0
        nutrients = get_nutrition_for_ingredient(name, ...)
        if nutrients is None:
            continue
        for key in NUTRIENT_KEYS:
            totals[key] += nutrients.get(key, 0.0) * ratio
```

- 기존 `List[str]`만 넘기는 호출부(있다면)와의 호환을 위해, `serving_g`가 없는 경우
  기본값(100)으로 자동 대체하는 방식을 유지한다.

---

## 3. 기본값 및 허용 범위

| 항목 | 값 | 근거 |
|---|---|---|
| **기본값(default)** | `100` (g) | 현재 `nutrition.csv`가 100g 기준 데이터이므로, 값을 안 넣었을 때 "기존 100g 가정 동작"과 동일하게 하위 호환 유지 |
| **허용 범위(min~max)** | `1 ~ 2000` (g) | - 최소 1g: 0 이하 값은 의미 없음(0으로 나누기·음수 섭취량 방지) <br> - 최대 2000g: 1인분 재료 섭취량으로 비현실적인 값(예: 수천g) 입력을 막기 위한 상한선. 국·찌개류 1인분(500~800g) 등을 감안해도 2000g이면 충분히 여유 있는 상한 |

### 검증 위치

- Pydantic 스키마(`routers/nutrition.py`의 `IngredientInput`) 단에서 1차 검증:
```python
  serving_g: float = Field(100, ge=1, le=2000, description="섭취량(g), 기본 100g")
```
  - 현재 `IngredientInput`은 `gt=0`만 걸려있고 상한선이 없음 → **상한(le=2000) 추가 필요**
  - 기본값도 현재는 필수 입력(`...`)으로 되어 있음 → **기본값(100)으로 변경 필요** (프론트/모델 쪽에서 값을 안 보내도 동작하도록)
- `nutrition_service.calculate_totals()` 내부에서도 방어적으로 한 번 더 range 처리
  (라우터를 거치지 않고 서비스 함수를 직접 호출하는 경우 대비)

---

## 4. 요약 (TL;DR)

1. `calculate_totals()`는 현재 모든 재료를 100g 고정으로 가정하고 있음 (스케일링 로직 없음)
2. `serving_g`는 **재료 객체 안**에 추가 (요청 전체 공통값 아님) — 기존 `/api/nutrition/analyze`의 `IngredientInput` 구조와 통일
3. 기본값 `100`(g), 허용 범위 `1~2000`(g)
4. 이번 변경으로 `routers/nutrition.py`에 중복 구현된 스케일링 로직을 `calculate_totals()` 호출로 대체 가능 → 계산 로직 단일화

## 5. 다음 단계 (코드 수정 시 체크리스트)

- [ ] `calculate_totals()` 시그니처를 `List[Dict]`(또는 dataclass/Pydantic 모델) 받도록 변경
- [ ] `IngredientInput.serving_g`에 기본값 100, `le=2000` 상한 추가
- [ ] `routers/nutrition.py`의 중복 스케일링 로직 제거 후 `calculate_totals()` 재사용
- [ ] `test_my_routes.py` 류 개인 테스트로 기존 응답과 동일한지 회귀 확인