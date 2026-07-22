# tests/test_image_service.py

# [TEST] 현지 담당. image_service.py의 전처리·분류·Mock 모드를 검증한다.

import io

import numpy as np
import pytest
from PIL import Image

from backend.services import image_service


def _make_image_bytes(fmt: str = "JPEG", size: tuple[int, int] = (300, 200)) -> bytes:
    image = Image.new("RGB", size, color=(120, 80, 40))
    buffer = io.BytesIO()
    image.save(buffer, format=fmt)
    return buffer.getvalue()


def test_preprocess_image_resizes_and_adds_batch_dim() -> None:
    file_bytes = _make_image_bytes()

    array = image_service.preprocess_image(file_bytes)

    assert array.shape == (1, *image_service.IMG_SIZE, 3)
    assert array.dtype == np.float32


def test_predict_single_mock_mode_returns_fixed_candidates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(image_service, "MOCK_MODE", True)

    result = image_service.predict_single(b"unused-in-mock-mode", "img-1")

    assert result["image_id"] == "img-1"
    assert result["error"] is None
    assert result["name"] == image_service.MOCK_CANDIDATES[0]["name"]
    assert result["candidates"] == image_service.MOCK_CANDIDATES


def test_predict_single_invalid_format_returns_error_without_loading_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(image_service, "MOCK_MODE", False)

    result = image_service.predict_single(b"this is not an image", "img-2")

    assert result["image_id"] == "img-2"
    assert result["name"] is None
    assert result["candidates"] == []
    assert result["error"] is not None


def test_predict_single_uses_loaded_model_for_top3(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # [TEST] TensorFlow 모델을 실제로 로딩하지 않도록 load_model을 가짜 모델로 대체한다.
    monkeypatch.setattr(image_service, "MOCK_MODE", False)

    class FakeModel:
        def predict(self, image_array: np.ndarray, verbose: int = 0) -> np.ndarray:
            return np.array([[0.1, 0.7, 0.2]], dtype=np.float32)

    fake_class_names = ["cabbage", "potato", "carrot"]

    monkeypatch.setattr(
        image_service,
        "load_model",
        lambda: (FakeModel(), fake_class_names),
    )

    file_bytes = _make_image_bytes()
    result = image_service.predict_single(file_bytes, "img-3")

    assert result["error"] is None
    assert result["name"] == "potato"
    assert len(result["candidates"]) == image_service.TOP_K
    assert result["candidates"][0]["name"] == "potato"


def test_predict_single_wraps_model_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(image_service, "MOCK_MODE", False)

    def raise_error() -> tuple[object, list[str]]:
        raise FileNotFoundError("모델 파일이 없습니다")

    monkeypatch.setattr(image_service, "load_model", raise_error)

    file_bytes = _make_image_bytes()
    result = image_service.predict_single(file_bytes, "img-4")

    assert result["name"] is None
    assert result["error"] is not None


def test_predict_batch_returns_results_for_each_file(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(image_service, "MOCK_MODE", True)

    class FakeUploadFile:
        def __init__(self, filename: str, content: bytes) -> None:
            self.filename = filename
            self._content = content

        def read(self) -> bytes:
            return self._content

    files = [
        FakeUploadFile("potato.jpg", _make_image_bytes()),
        FakeUploadFile("carrot.png", _make_image_bytes(fmt="PNG")),
    ]

    output = image_service.predict_batch(files)

    assert list(output.keys()) == ["results"]
    assert len(output["results"]) == 2
    assert output["results"][0]["image_id"] == "potato.jpg"
    assert output["results"][1]["image_id"] == "carrot.png"
