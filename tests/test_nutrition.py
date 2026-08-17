# [TEST] 지은 담당. 한국어 주석 필수

"""
nutrition_service.py의 serving_g 검증(resolve_serving_g / calculate_totals) 경계값 테스트.

kdri.csv, nutrition.csv 등 실제 데이터 파일에 의존하지 않도록, 테스트 안에서
가짜(mock) nutrition_data를 직접 만들어서 사용한다. 이렇게 하면 데이터 파일
내용이 나중에 바뀌어도 이 테스트는 영향받지 않는다.

실행 방법 (프로젝트 최상위 폴더에서):
    pytest backend/tests/test_nutrition.py -v
"""

import logging

import pytest

from backend.services import nutrition_service as ns


# ------------------------------------------------------------------
# 테스트용 가짜 데이터 (실제 nutrition.csv 대신 사용)
# ------------------------------------------------------------------
@pytest.fixture
def fake_nutrition_data():
    """
    100g당 모든 영양소 값이 딱 떨어지는 가짜 재료 하나를 만든다.
    (calories_kcal=100이면, serving_g=100일 때 결과값도 정확히 100이 되어
    "기본값 100g으로 대체됐는지"를 검증하기 쉽다)
    """
    return {
        "테스트재료": {
            "calories_kcal": 100.0,
            "carbohydrate_g": 100.0,
            "protein_g": 100.0,
            "fat_g": 100.0,
            "calcium_mg": 100.0,
            "iron_mg": 100.0,
            "vitamin_c_mg": 100.0,
        }
    }


@pytest.fixture
def fake_aliases():
    """별칭 변환이 결과에 영향을 주지 않도록 빈 별칭 사전을 사용한다."""
    return {}


# ------------------------------------------------------------------
# 경계값 테스트 (최소 4개 케이스: 0 / 음수 / 2000 초과 / 미입력)
# ------------------------------------------------------------------


def test_serving_g_zero_falls_back_to_default(fake_nutrition_data, fake_aliases, caplog):
    """serving_g=0(0 이하)이면 기본값 100g으로 대체되고 경고 로그가 남아야 한다."""
    ingredients = [{"name": "테스트재료", "serving_g": 0}]

    with caplog.at_level(logging.WARNING):
        totals = ns.calculate_totals(
            ingredients, nutrition_data=fake_nutrition_data, aliases=fake_aliases
        )

    # serving_g가 100(기본값)으로 대체됐다면, ratio=1이므로 결과값이 100g 기준 원본 값과 같아야 한다.
    assert totals["calories_kcal"] == 100.0
    assert totals["calcium_mg"] == 100.0

    # 경고 로그가 실제로 남았는지 확인 (재료 이름과 "기본값" 문구 포함)
    assert any(
        "테스트재료" in record.message and "기본값" in record.message
        for record in caplog.records
    )


def test_serving_g_negative_falls_back_to_default(fake_nutrition_data, fake_aliases, caplog):
    """serving_g가 음수이면 기본값 100g으로 대체되고 경고 로그가 남아야 한다."""
    ingredients = [{"name": "테스트재료", "serving_g": -50}]

    with caplog.at_level(logging.WARNING):
        totals = ns.calculate_totals(
            ingredients, nutrition_data=fake_nutrition_data, aliases=fake_aliases
        )

    assert totals["protein_g"] == 100.0
    assert any(
        "테스트재료" in record.message and "기본값" in record.message
        for record in caplog.records
    )


def test_serving_g_over_max_falls_back_to_default(fake_nutrition_data, fake_aliases, caplog):
    """serving_g가 2000g을 초과하면(예: 5000g) 기본값 100g으로 대체되고 경고 로그가 남아야 한다."""
    ingredients = [{"name": "테스트재료", "serving_g": 5000}]

    with caplog.at_level(logging.WARNING):
        totals = ns.calculate_totals(
            ingredients, nutrition_data=fake_nutrition_data, aliases=fake_aliases
        )

    assert totals["fat_g"] == 100.0
    assert any(
        "테스트재료" in record.message and "기본값" in record.message
        for record in caplog.records
    )


def test_serving_g_missing_uses_default_without_warning_flavor(
    fake_nutrition_data, fake_aliases, caplog
):
    """
    serving_g 키 자체가 없으면(미입력) 기본값 100g이 적용되어야 한다.
    (resolve_serving_g 입장에서는 None으로 들어오는 경우와 동일하게 처리된다)
    """
    ingredients = [{"name": "테스트재료"}]  # serving_g 키 자체를 안 넣음

    with caplog.at_level(logging.WARNING):
        totals = ns.calculate_totals(
            ingredients, nutrition_data=fake_nutrition_data, aliases=fake_aliases
        )

    assert totals["iron_mg"] == 100.0
    assert any(
        "테스트재료" in record.message and "기본값" in record.message
        for record in caplog.records
    )


# ------------------------------------------------------------------
# 대조군: 정상 범위 값은 그대로 반영되고, 경고 로그가 남지 않아야 한다.
# ------------------------------------------------------------------


def test_serving_g_valid_value_is_used_as_is(fake_nutrition_data, fake_aliases, caplog):
    """serving_g가 정상 범위(1~2000g) 안이면 대체되지 않고 그 값 그대로 비례 계산되어야 한다."""
    ingredients = [{"name": "테스트재료", "serving_g": 50}]  # 100g 기준의 절반

    with caplog.at_level(logging.WARNING):
        totals = ns.calculate_totals(
            ingredients, nutrition_data=fake_nutrition_data, aliases=fake_aliases
        )

    # 100g 기준 100.0인 값을 50g 섭취했으니 결과는 50.0이어야 한다 (기본값 100g으로 대체되지 않음).
    assert totals["calories_kcal"] == 50.0
    assert totals["vitamin_c_mg"] == 50.0

    # 정상 범위 값이므로 "기본값으로 대체" 경고가 없어야 한다.
    assert not any(
        "테스트재료" in record.message and "기본값" in record.message
        for record in caplog.records
    )


def test_resolve_serving_g_directly_for_all_boundary_cases():
    """
    resolve_serving_g() 함수를 단위 테스트 레벨에서 직접 확인한다.
    (calculate_totals를 거치지 않고 경계값 각각을 명확히 검증)
    """
    assert ns.resolve_serving_g("테스트재료", 0) == float(ns.DEFAULT_SERVING_G)
    assert ns.resolve_serving_g("테스트재료", -10) == float(ns.DEFAULT_SERVING_G)
    assert ns.resolve_serving_g("테스트재료", 2001) == float(ns.DEFAULT_SERVING_G)
    assert ns.resolve_serving_g("테스트재료", None) == float(ns.DEFAULT_SERVING_G)

    # 경계값 바로 안쪽(1g, 2000g)은 정상적으로 그 값 그대로 반환되어야 한다.
    assert ns.resolve_serving_g("테스트재료", 1) == 1.0
    assert ns.resolve_serving_g("테스트재료", 2000) == 2000.0