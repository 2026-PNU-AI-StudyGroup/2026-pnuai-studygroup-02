# tests/test_recipes.py

# [HANDOVER] 시은 작성, 24일 필수 완성

from fastapi.testclient import TestClient

from backend.main import app


client = TestClient(app)


# [HANDOVER] owned_first 모드가 정상 응답하는지 확인한다.
def test_owned_first_recommendation(monkeypatch):
    mock_recipes = [
        {
            "recipe_id": "test-owned-001",
            "title": "감자 당근 볶음",
            "owned_ingredients": [
                "감자",
                "당근",
            ],
            "additional_ingredients": [],
            "steps": [
                "감자와 당근을 깨끗하게 씻는다.",
                "감자와 당근을 먹기 좋은 크기로 썬다.",
                "팬에 식용유를 두르고 재료를 볶는다.",
            ],
            "sources": [],
        },
        {
            "recipe_id": "test-owned-002",
            "title": "감자 양배추 볶음",
            "owned_ingredients": [
                "감자",
                "양배추",
            ],
            "additional_ingredients": [],
            "steps": [
                "감자와 양배추를 깨끗하게 씻는다.",
                "감자는 얇게 썰고 양배추는 먹기 좋은 크기로 자른다.",
                "팬에 감자를 먼저 볶은 뒤 양배추를 넣어 익힌다.",
            ],
            "sources": [],
        },
        {
            "recipe_id": "test-owned-003",
            "title": "당근 양배추 볶음",
            "owned_ingredients": [
                "당근",
                "양배추",
            ],
            "additional_ingredients": [],
            "steps": [
                "당근과 양배추를 깨끗하게 씻는다.",
                "당근과 양배추를 가늘게 채 썬다.",
                "팬에 식용유를 두르고 재료를 볶는다.",
            ],
            "sources": [],
        },
    ]

    # [HANDOVER] 실제 LLM 호출 대신 준비된 테스트 데이터를 반환한다.
    monkeypatch.setattr(
        "backend.routers.recipes.generate_recipes",
        lambda ingredients, deficient_nutrients, mode: mock_recipes,
    )

    response = client.post(
        "/api/recipes/recommend",
        json={
            "ingredients": [
                "감자",
                "당근",
                "양배추",
            ],
            "deficient_nutrients": [],
            "mode": "owned_first",
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["recipe_mode"] == "owned_first"
    assert len(body["recipes"]) >= 3

    for recipe in body["recipes"]:
        assert recipe["recipe_id"]
        assert recipe["title"]
        assert recipe["steps"]
        assert recipe["sources"] == []

        for ingredient in recipe["owned_ingredients"]:
            assert ingredient in {
                "감자",
                "당근",
                "양배추",
            }


# [HANDOVER] nutrition_supplement 모드가 정상 응답하는지 확인한다.
def test_nutrition_supplement_recommendation(monkeypatch):
    mock_recipes = [
        {
            "recipe_id": "test-nutrition-001",
            "title": "양배추 두부 감자볶음",
            "owned_ingredients": [
                "감자",
                "양배추",
            ],
            "additional_ingredients": [
                "두부",
            ],
            "steps": [
                "감자와 양배추를 깨끗하게 씻는다.",
                "감자와 양배추를 먹기 좋은 크기로 자른다.",
                "두부의 물기를 제거하고 먹기 좋은 크기로 자른다.",
                "팬에 감자와 양배추를 볶은 뒤 두부를 넣어 익힌다.",
            ],
            "sources": [],
        }
    ]

    # [HANDOVER] 실제 LLM 호출 대신 영양 보충 테스트 데이터를 반환한다.
    monkeypatch.setattr(
        "backend.routers.recipes.generate_recipes",
        lambda ingredients, deficient_nutrients, mode: mock_recipes,
    )

    response = client.post(
        "/api/recipes/recommend",
        json={
            "ingredients": [
                "감자",
                "양배추",
            ],
            "deficient_nutrients": [
                "단백질",
            ],
            "mode": "nutrition_supplement",
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["recipe_mode"] == "nutrition_supplement"
    assert len(body["recipes"]) >= 1

    first_recipe = body["recipes"][0]

    assert first_recipe["recipe_id"]
    assert first_recipe["title"]
    assert "두부" in first_recipe["additional_ingredients"]
    assert first_recipe["steps"]
    assert first_recipe["sources"] == []

    for ingredient in first_recipe["owned_ingredients"]:
        assert ingredient in {
            "감자",
            "양배추",
        }


# [HANDOVER] LLM 호출 실패 시 Mock fallback이 동작하는지 확인한다.
def test_llm_failure_uses_mock_fallback(monkeypatch):
    # [HANDOVER] Gemini 호출이 항상 실패하도록 테스트용 함수로 교체한다.
    def raise_llm_error(prompt):
        raise RuntimeError("테스트용 LLM 호출 실패")

    monkeypatch.setattr(
        "backend.services.llm_recipe_service._call_gemini",
        raise_llm_error,
    )

    response = client.post(
        "/api/recipes/recommend",
        json={
            "ingredients": [
                "감자",
                "당근",
                "양배추",
            ],
            "deficient_nutrients": [],
            "mode": "owned_first",
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["recipe_mode"] == "owned_first"
    assert body["recipes"]

    # [HANDOVER] Mock JSON의 recipe_id가 mock-으로 시작하는지 확인한다.
    assert body["recipes"][0]["recipe_id"].startswith("mock-")

    for recipe in body["recipes"]:
        assert recipe["recipe_id"]
        assert recipe["title"]
        assert recipe["steps"]
        assert recipe["sources"] == []