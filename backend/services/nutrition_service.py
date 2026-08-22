# [NUTRITION] 지은 담당. 순수 계산 함수만, LLM 호출 없음. 한국어 주석 필수

"""
식재료별 영양 조회 + 개인 충족률 계산 서비스.

- data/nutrition.csv   : 식재료 100g 기준 영양성분표
- data/kdri.csv        : 성별/연령대별 권장섭취량(KDRI)
- data/ingredient_aliases.json : 모델 출력명 -> nutrition.csv 재료명 매핑

이 모듈은 전부 "순수 계산"만 수행하며, 외부 API나 LLM을 호출하지 않는다.
"""

import csv
import json
import logging
import os
from typing import Dict, List, Optional, Union

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# 경로 설정
# ------------------------------------------------------------------
# 이 파일 위치: backend/services/nutrition_service.py
# 데이터 폴더 위치: backend/data/
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_DATA_DIR = os.path.join(_BASE_DIR, "data")

NUTRITION_CSV_PATH = os.path.join(_DATA_DIR, "nutrition.csv")
KDRI_CSV_PATH = os.path.join(_DATA_DIR, "kdri.csv")
ALIASES_JSON_PATH = os.path.join(_DATA_DIR, "ingredient_aliases.json")

# 영양소 컬럼 목록 (nutrition.csv / kdri.csv 공통)
NUTRIENT_KEYS = [
    "calories_kcal",
    "carbohydrate_g",
    "protein_g",
    "fat_g",
    "calcium_mg",
    "iron_mg",
    "vitamin_c_mg",
]

# kdri.csv의 4개 연령 그룹과 나이 범위 매핑
_AGE_GROUP_RANGES = {
    "19-29": (19, 29),
    "30-49": (30, 49),
}

# [NUTRITION] docs/gram_feature_design.md 설계에 따른 serving_g 기본값/허용 범위
# 기본값 100g: nutrition.csv가 100g 기준 데이터이므로, 값을 안 넣었을 때 "기존 100g 가정 동작"과 동일하게 하위 호환 유지
# 허용 범위 1~2000g: 0 이하 값 방지 + 비현실적인 섭취량(수천g) 입력 방지
DEFAULT_SERVING_G = 100
MIN_SERVING_G = 1
MAX_SERVING_G = 2000


def _read_csv_rows(path: str) -> List[Dict[str, str]]:
    """CSV 파일을 읽어 '#'으로 시작하는 주석 줄을 제거하고 DictReader로 파싱한다."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"데이터 파일을 찾을 수 없습니다: {path}")

    with open(path, encoding="utf-8") as f:
        # 주석 줄(#으로 시작)과 빈 줄은 건너뛰고 실제 데이터 줄만 남긴다.
        # (빈 줄을 남겨두면 DictReader가 그 줄을 헤더로 오인해 모든 데이터가 유실된다.)
        lines = [
            line
            for line in f
            if line.strip() and not line.lstrip().startswith("#")
        ]

    reader = csv.DictReader(lines)
    return list(reader)


def load_nutrition_data(path: str = NUTRITION_CSV_PATH) -> Dict[str, Dict[str, float]]:
    """
    nutrition.csv를 읽어 {재료명: {영양소: 값}} 형태의 딕셔너리로 반환한다.
    값은 전부 float로 변환한다.
    """
    rows = _read_csv_rows(path)
    result: Dict[str, Dict[str, float]] = {}

    for row in rows:
        name = row.get("ingredient_name", "").strip()
        if not name:
            continue
        nutrients = {}
        for key in NUTRIENT_KEYS:
            raw_value = row.get(key, "0")
            try:
                nutrients[key] = float(raw_value)
            except (TypeError, ValueError):
                nutrients[key] = 0.0
        result[name] = nutrients

    return result


def load_kdri_data(path: str = KDRI_CSV_PATH) -> Dict[str, Dict[str, float]]:
    """
    kdri.csv를 읽어 {"성별_연령대": {영양소: 값}} 형태의 딕셔너리로 반환한다.
    예: {"남_19-29": {...}, "여_30-49": {...}}
    """
    rows = _read_csv_rows(path)
    result: Dict[str, Dict[str, float]] = {}

    for row in rows:
        gender = row.get("gender", "").strip()
        age_group = row.get("age_group", "").strip()
        if not gender or not age_group:
            continue

        nutrients = {}
        for key in NUTRIENT_KEYS:
            raw_value = row.get(key, "0")
            try:
                nutrients[key] = float(raw_value)
            except (TypeError, ValueError):
                nutrients[key] = 0.0

        result[f"{gender}_{age_group}"] = nutrients

    return result


def load_aliases(path: str = ALIASES_JSON_PATH) -> Dict[str, str]:
    """
    ingredient_aliases.json을 읽어 {별칭: 원본명} 딕셔너리(aliases 키 내부)를 반환한다.
    파일이 없거나 형식이 다르면 빈 딕셔너리를 반환한다.
    """
    if not os.path.exists(path):
        return {}

    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    return data.get("aliases", {})


def normalize_ingredient_name(name: str, aliases: Optional[Dict[str, str]] = None) -> str:
    """
    모델이 출력한 재료명을 별칭 사전을 통해 nutrition.csv의 표준 재료명으로 변환한다.
    별칭 사전에 매칭되는 항목이 없으면 원본 이름을 그대로 반환한다.
    """
    if aliases is None:
        aliases = load_aliases()

    name = name.strip()
    return aliases.get(name, name)


def get_nutrition_for_ingredient(
    name: str,
    nutrition_data: Optional[Dict[str, Dict[str, float]]] = None,
    aliases: Optional[Dict[str, str]] = None,
) -> Optional[Dict[str, float]]:
    """
    재료명(모델 출력명 또는 표준명)을 받아 100g 기준 영양 정보를 반환한다.
    별칭 변환 후에도 nutrition.csv에 없으면 None을 반환한다.
    """
    if nutrition_data is None:
        nutrition_data = load_nutrition_data()

    normalized_name = normalize_ingredient_name(name, aliases=aliases)
    return nutrition_data.get(normalized_name)


def resolve_serving_g(ingredient_name: str, serving_g: object) -> float:
    """
    serving_g 입력값을 검증해 실제로 계산에 사용할 값을 반환한다.

    아래 경우에는 기본값(DEFAULT_SERVING_G = 100g)으로 대체하고 경고 로그를 남긴다.
    - 값이 없음(None)
    - 숫자로 변환할 수 없음
    - 0 이하
    - MAX_SERVING_G(2000g) 초과

    라우터(Pydantic) 쪽에서 이미 1차 검증을 하더라도, 이 함수가 서비스 계층에서
    독립적으로 호출되는 경우(다른 스크립트, 테스트 등)를 대비한 방어 로직이다.
    """
    if serving_g is None:
        logger.warning(
            "[NUTRITION] '%s' 재료의 serving_g가 없어 기본값 %dg으로 대체합니다.",
            ingredient_name,
            DEFAULT_SERVING_G,
        )
        return float(DEFAULT_SERVING_G)

    try:
        value = float(serving_g)
    except (TypeError, ValueError):
        logger.warning(
            "[NUTRITION] '%s' 재료의 serving_g 값(%r)이 올바르지 않아 기본값 %dg으로 대체합니다.",
            ingredient_name,
            serving_g,
            DEFAULT_SERVING_G,
        )
        return float(DEFAULT_SERVING_G)

    if value <= 0 or value > MAX_SERVING_G:
        logger.warning(
            "[NUTRITION] '%s' 재료의 serving_g 값(%s)이 허용 범위(%d~%dg)를 벗어나 "
            "기본값 %dg으로 대체합니다.",
            ingredient_name,
            value,
            MIN_SERVING_G,
            MAX_SERVING_G,
            DEFAULT_SERVING_G,
        )
        return float(DEFAULT_SERVING_G)

    return value


def calculate_totals(
    ingredients: List[Union[str, Dict[str, object]]],
    nutrition_data: Optional[Dict[str, Dict[str, float]]] = None,
    aliases: Optional[Dict[str, str]] = None,
) -> Dict[str, float]:
    """
    재료 목록을 받아 실제 섭취량(serving_g)에 비례한 영양소 합계를 계산한다.

    ingredients의 각 원소는 두 가지 형태를 모두 지원한다.
    - 문자열(str): 재료명만 넘기는 경우. serving_g는 기본값(100g)으로 간주한다.
      (기존 호출부와의 하위 호환을 위해 유지, 이 경우는 경고 로그를 남기지 않는다)
    - 딕셔너리(dict): {"name": 재료명, "serving_g": 실제 섭취량(g)} 형태.
      serving_g가 없거나(0 이하 / 2000 초과 등) 잘못된 값이면 기본값(100g)으로
      대체하고 resolve_serving_g()가 경고 로그를 남긴다.

    각 재료의 100g 기준 영양값에 (serving_g / 100)을 곱해 실제 섭취량 기준으로 합산한다.
    nutrition.csv에서 찾을 수 없는 재료는 계산에서 제외한다(값 0 취급).
    """
    if nutrition_data is None:
        nutrition_data = load_nutrition_data()
    if aliases is None:
        aliases = load_aliases()

    totals = {key: 0.0 for key in NUTRIENT_KEYS}

    for item in ingredients:
        if isinstance(item, dict):
            name = item.get("name", "")
            serving_g = resolve_serving_g(name, item.get("serving_g"))
        else:
            # 문자열만 넘어온 경우: 기존 방식과 동일하게 100g으로 계산(하위 호환)
            name = item
            serving_g = float(DEFAULT_SERVING_G)

        nutrients = get_nutrition_for_ingredient(
            name, nutrition_data=nutrition_data, aliases=aliases
        )
        if nutrients is None:
            # 매칭 실패한 재료는 무시하고 계속 진행한다.
            continue

        # nutrition.csv는 100g 기준값이므로, 실제 섭취량(serving_g)에 비례해서 환산한다.
        ratio = serving_g / 100.0
        for key in NUTRIENT_KEYS:
            totals[key] += nutrients.get(key, 0.0) * ratio

    totals = {key: round(value, 1) for key, value in totals.items()}

    return totals


def get_recommendation(
    gender: str,
    age: int,
    kdri_data: Optional[Dict[str, Dict[str, float]]] = None,
) -> Optional[Dict[str, float]]:
    """
    성별과 나이를 받아 kdri.csv의 4개 그룹(남/여 x 19-29/30-49) 중
    해당하는 그룹의 권장섭취량을 반환한다.
    나이가 19~49 범위를 벗어나면 None을 반환한다.
    """
    if kdri_data is None:
        kdri_data = load_kdri_data()

    age_group = None
    for group_name, (min_age, max_age) in _AGE_GROUP_RANGES.items():
        if min_age <= age <= max_age:
            age_group = group_name
            break

    if age_group is None:
        # 4그룹 범위(19~49세) 밖의 나이는 지원하지 않는다.
        return None

    key = f"{gender}_{age_group}"
    return kdri_data.get(key)


def calculate_percentage(
    total: Dict[str, float], recommended: Dict[str, float]
) -> List[Dict[str, object]]:
    """
    영양소별 합계(total)와 권장섭취량(recommended)을 비교해 충족률을 계산한다.

    반환값: 영양소별 {nutrient, total, recommended, percentage, status} 딕셔너리 리스트
    - status 기준: 90% 이상 = "높음", 70~90% 미만 = "보통", 70% 미만 = "낮음"
    """
    results = []

    for nutrient in NUTRIENT_KEYS:
        total_value = total.get(nutrient, 0.0)
        recommended_value = recommended.get(nutrient, 0.0)

        if recommended_value <= 0:
            # 권장섭취량이 0이거나 없으면 퍼센트 계산이 불가능하므로 0으로 처리한다.
            percentage = 0.0
        else:
            percentage = round((total_value / recommended_value) * 100, 1)

        if percentage >= 90:
            status = "높음"
        elif percentage >= 70:
            status = "보통"
        else:
            status = "낮음"

        results.append(
            {
                "nutrient": nutrient,
                "total": round(total_value, 1),
                "recommended": round(recommended_value, 1),
                "percentage": percentage,
                "status": status,
            }
        )

    return results


def get_deficient_ingredients(
    deficient_nutrients: List[str],
    nutrition_data: Optional[Dict[str, Dict[str, float]]] = None,
    top_n: int = 3,
) -> List[str]:
    """
    부족한 영양소 리스트(예: ["calcium_mg", "iron_mg"])를 받아
    해당 영양소들을 가장 많이 함유한 재료 상위 top_n개를 추천한다.

    점수 계산: 재료별로 부족한 영양소 값들을 단순 합산해 정렬한다.
    (단위가 다른 영양소를 함께 더하는 단순 근사치이므로, 정교한 우선순위가
    필요하면 영양소별 가중치를 추가로 조정해야 한다.)
    """
    if nutrition_data is None:
        nutrition_data = load_nutrition_data()

    if not deficient_nutrients:
        return []

    scored = []
    for ingredient_name, nutrients in nutrition_data.items():
        score = sum(nutrients.get(nutrient, 0.0) for nutrient in deficient_nutrients)
        if score > 0:
            scored.append((ingredient_name, score))

    scored.sort(key=lambda pair: pair[1], reverse=True)

    return [name for name, _score in scored[:top_n]]