# tests/test_api_integration.py

# [TEST] 현지 담당. main.py의 라우터 등록·정적 서빙·공통 예외 포맷을 검증한다.

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.schemas.recipe import Recipe, RecipeResponse


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_health_check(client: TestClient) -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_static_frontend_index_served(client: TestClient) -> None:
    # [TEST] StaticFiles(html=True)로 frontend/index.html이 "/"에서 서빙되는지 확인한다.
    response = client.get("/")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_unknown_route_returns_common_error_format(client: TestClient) -> None:
    # [TEST] 존재하지 않는 API 경로도 {code, message, details} 형태로 내려오는지 확인한다.
    response = client.get("/api/does-not-exist")

    assert response.status_code == 404
    body = response.json()
    assert set(body.keys()) == {"code", "message", "details"}


def test_recipes_empty_ingredients_returns_common_validation_error(
    client: TestClient,
) -> None:
    # [TEST] RecipeRequest.ingredients는 min_length=1이므로 빈 배열은 422가 되어야 하고,
    # 그 응답도 공통 {code, message, details} 포맷을 따라야 한다.
    response = client.post(
        "/api/recipes/recommend",
        json={"ingredients": [], "deficient_nutrients": [], "mode": "owned_first"},
    )

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "VALIDATION_ERROR"
    assert set(body.keys()) == {"code", "message", "details"}


def test_recipes_recommend_success(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # [TEST] llm_recipe_service를 실제로 호출하지 않도록 라우터에 주입된 함수를 대체한다.
    def fake_generate_recipes(
        ingredients: list[str],
        deficient_nutrients: list[str],
        mode: str,
    ) -> list[Recipe]:
        return [
            Recipe(
                recipe_id="r1",
                title="감자볶음",
                owned_ingredients=ingredients,
                additional_ingredients=[],
                steps=["재료를 볶는다"],
                sources=[],
            )
        ]

    monkeypatch.setattr(
        "backend.routers.recipes.generate_recipes",
        fake_generate_recipes,
    )

    response = client.post(
        "/api/recipes/recommend",
        json={"ingredients": ["감자"], "deficient_nutrients": [], "mode": "owned_first"},
    )

    assert response.status_code == 200
    body = RecipeResponse.model_validate(response.json())
    assert body.recipe_mode == "owned_first"
    assert body.recipes[0].title == "감자볶음"


def test_recipes_recommend_generation_failure_returns_common_error(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def raise_error(
        ingredients: list[str],
        deficient_nutrients: list[str],
        mode: str,
    ) -> list[Recipe]:
        raise RuntimeError("Gemini 호출 실패")

    monkeypatch.setattr(
        "backend.routers.recipes.generate_recipes",
        raise_error,
    )

    response = client.post(
        "/api/recipes/recommend",
        json={"ingredients": ["감자"], "deficient_nutrients": [], "mode": "owned_first"},
    )

    assert response.status_code == 500
    body = response.json()
    assert body["code"] == "RECIPE_GENERATION_FAILED"
    assert set(body.keys()) == {"code", "message", "details"}
