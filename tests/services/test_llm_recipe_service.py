# tests/services/test_llm_recipe_service.py

from __future__ import annotations

import json
import logging
from types import SimpleNamespace
from typing import Any

import httpx
import pytest

from backend.services import llm_recipe_service as service


class FakeModels:
    """Gemini models 객체를 대신하는 테스트용 객체."""

    def __init__(self, outcome: object) -> None:
        self.outcome = outcome

    def generate_content(
        self,
        **_: Any,
    ) -> object:
        if isinstance(self.outcome, BaseException):
            raise self.outcome

        return self.outcome


class FakeClient:
    """genai.Client를 대신하는 테스트용 객체."""

    outcome: object

    def __init__(
        self,
        *_: object,
        **__: object,
    ) -> None:
        self.models = FakeModels(self.outcome)


def install_fake_client(
    monkeypatch: pytest.MonkeyPatch,
    outcome: object,
) -> None:
    """
    실제 Gemini API가 호출되지 않도록
    genai.Client를 FakeClient로 교체한다.
    """
    FakeClient.outcome = outcome

    monkeypatch.setattr(
        service.genai,
        "Client",
        FakeClient,
    )

    monkeypatch.setenv(
        "GEMINI_API_KEY",
        "test-api-key",
    )

    # 테스트에서는 한 번 실패한 직후 fallback을 확인한다.
    monkeypatch.setattr(
        service,
        "MAX_RETRIES",
        0,
    )


def load_expected_mock_recipes() -> list[dict]:
    """
    mock/recipe_mock.json을 직접 읽어
    예상 fallback 결과를 만든다.
    """
    mock_data = json.loads(
        service.MOCK_FILE_PATH.read_text(
            encoding="utf-8",
        )
    )

    expected: list[dict] = []

    for recipe in mock_data["recipes"]:
        expected_recipe = dict(recipe)
        expected_recipe["sources"] = []
        expected.append(expected_recipe)

    return expected


def generate_owned_first_recipes() -> list[dict]:
    return service.generate_recipes(
        ingredients=[
            "감자",
            "당근",
            "양배추",
        ],
        deficient_nutrients=[],
        mode="owned_first",
    )


def assert_only_expected_event_logged(
    caplog: pytest.LogCaptureFixture,
    expected_event: str,
) -> None:
    failure_events = (
        "event=llm_api_timeout",
        "event=llm_response_parse_failure",
        "event=llm_empty_response",
    )

    assert expected_event in caplog.text

    for event in failure_events:
        if event != expected_event:
            assert event not in caplog.text

    assert "event=mock_fallback" in caplog.text


def test_timeout_is_logged_and_uses_mock_fallback(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """
    LLM API 타임아웃 발생 시:
    1. llm_api_timeout 로그가 남는다.
    2. mock/recipe_mock.json 결과가 반환된다.
    """
    request = httpx.Request(
        method="POST",
        url="https://example.test/gemini",
    )

    timeout_error = httpx.ReadTimeout(
        "Gemini 요청 시간 초과",
        request=request,
    )

    install_fake_client(
        monkeypatch,
        timeout_error,
    )

    with caplog.at_level(
        logging.WARNING,
        logger=service.logger.name,
    ):
        result = generate_owned_first_recipes()

    assert result == load_expected_mock_recipes()

    assert_only_expected_event_logged(
        caplog,
        "event=llm_api_timeout",
    )


def test_parse_failure_is_logged_and_uses_mock_fallback(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """
    LLM 응답 JSON 파싱 실패 시:
    1. llm_response_parse_failure 로그가 남는다.
    2. mock/recipe_mock.json 결과가 반환된다.
    """
    invalid_json_response = SimpleNamespace(
        text=(
            '{"recipe_mode": "owned_first", '
            '"recipes": [invalid-json]}'
        ),
    )

    install_fake_client(
        monkeypatch,
        invalid_json_response,
    )

    with caplog.at_level(
        logging.WARNING,
        logger=service.logger.name,
    ):
        result = generate_owned_first_recipes()

    assert result == load_expected_mock_recipes()

    assert_only_expected_event_logged(
        caplog,
        "event=llm_response_parse_failure",
    )


def test_empty_response_is_logged_and_uses_mock_fallback(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """
    LLM 응답이 비어 있을 때:
    1. llm_empty_response 로그가 남는다.
    2. mock/recipe_mock.json 결과가 반환된다.
    """
    empty_response = SimpleNamespace(
        text="   ",
    )

    install_fake_client(
        monkeypatch,
        empty_response,
    )

    with caplog.at_level(
        logging.WARNING,
        logger=service.logger.name,
    ):
        result = generate_owned_first_recipes()

    assert result == load_expected_mock_recipes()

    assert_only_expected_event_logged(
        caplog,
        "event=llm_empty_response",
    )