# backend/services/image_service.py

# [IMAGE] 현지 담당. 저장된 EfficientNetB0 모델을 로드해 식재료 이미지를 분류한다.

import io
import json
import logging
import os
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, UnidentifiedImageError


logger = logging.getLogger(__name__)

# [IMAGE] 학습 노트북(model/notebooks)과 동일한 입력 크기를 사용한다.
IMG_SIZE = (224, 224)

# [IMAGE] Top-3 후보까지만 반환한다.
TOP_K = 3

# [IMAGE] PIL이 인식하는 포맷 이름 기준으로 jpg/jpeg/png만 허용한다.
ALLOWED_FORMATS: set[str] = {"JPEG", "PNG"}

# [IMAGE] 학습된 모델과 클래스명 파일이 저장되는 경로
ARTIFACT_DIR = (
    Path(__file__).resolve().parent.parent.parent
    / "model"
    / "artifacts"
)
MODEL_PATH = ARTIFACT_DIR / "ingredient_model.keras"
CLASS_NAMES_PATH = ARTIFACT_DIR / "class_names.json"

# [IMAGE] MOCK_MODE=true면 모델을 로드하지 않고 고정 결과를 반환한다.
MOCK_MODE = os.getenv("MOCK_MODE", "false").lower() == "true"

# [IMAGE] MOCK_MODE에서 사용할 고정 결과
MOCK_CANDIDATES: list[dict[str, Any]] = [
    {"name": "potato", "confidence": 0.95},
    {"name": "carrot", "confidence": 0.03},
    {"name": "cabbage", "confidence": 0.02},
]

# [IMAGE] 모델과 클래스명을 1회만 로딩해 모듈 전역에 캐싱한다.
_model: Any = None
_class_names: list[str] | None = None


# [IMAGE] 저장된 .keras 모델과 class_names.json을 1회만 로딩해 캐싱한다.
def load_model() -> tuple[Any, list[str]]:
    global _model, _class_names

    if _model is not None and _class_names is not None:
        return _model, _class_names

    # [IMAGE] TensorFlow는 임포트 자체가 무거워 실제로 필요할 때만 불러온다.
    import tensorflow as tf

    if not MODEL_PATH.exists():
        raise FileNotFoundError(f"모델 파일이 없습니다: {MODEL_PATH}")

    if not CLASS_NAMES_PATH.exists():
        raise FileNotFoundError(
            f"클래스명 파일이 없습니다: {CLASS_NAMES_PATH}"
        )

    _model = tf.keras.models.load_model(MODEL_PATH)

    with CLASS_NAMES_PATH.open(mode="r", encoding="utf-8") as file:
        _class_names = json.load(file)

    logger.info("이미지 분류 모델을 로딩했습니다: %s", MODEL_PATH)

    return _model, _class_names


# [IMAGE] 이미지 바이트를 실제로 열어 포맷을 감지한다. 손상된 파일이면 None을 반환한다.
def _detect_image_format(file_bytes: bytes) -> str | None:
    try:
        with Image.open(io.BytesIO(file_bytes)) as image:
            return image.format

    except UnidentifiedImageError:
        return None


# [IMAGE] 이미지 바이트를 모델 입력 크기로 리사이즈하고 배치 차원을 추가한 배열로 변환한다.
def preprocess_image(file_bytes: bytes) -> np.ndarray:
    image = Image.open(io.BytesIO(file_bytes)).convert("RGB")
    image = image.resize(IMG_SIZE)

    # [IMAGE] 픽셀값 정규화(0~255 -> 모델 기대 범위)는 저장된 모델 내부의
    # preprocess_input 레이어가 이미 처리하므로, 여기서는 리사이즈와
    # float32 배열 변환만 수행하고 0~255 값을 그대로 둔다.
    image_array = np.array(image, dtype=np.float32)

    return np.expand_dims(image_array, axis=0)


# [IMAGE] 업로드 객체(UploadFile), 파일 객체, 원본 바이트를 모두 바이트로 통일한다.
def _read_file_bytes(file: Any) -> bytes:
    if hasattr(file, "file"):
        return file.file.read()

    if hasattr(file, "read"):
        return file.read()

    return file


# [IMAGE] 이미지 한 장을 분류해 Top-3 신뢰도를 포함한 결과를 반환한다.
def predict_single(file_bytes: bytes, image_id: str) -> dict[str, Any]:
    if MOCK_MODE:
        best = MOCK_CANDIDATES[0]

        return {
            "image_id": image_id,
            "name": best["name"],
            "confidence": best["confidence"],
            "candidates": MOCK_CANDIDATES,
            "error": None,
        }

    image_format = _detect_image_format(file_bytes)

    if image_format not in ALLOWED_FORMATS:
        return {
            "image_id": image_id,
            "name": None,
            "confidence": None,
            "candidates": [],
            "error": "jpg, jpeg, png 형식의 이미지만 지원합니다.",
        }

    try:
        model, class_names = load_model()
        image_array = preprocess_image(file_bytes)
        predictions = model.predict(image_array, verbose=0)[0]

        top_indices = np.argsort(predictions)[::-1][:TOP_K]
        candidates = [
            {
                "name": class_names[index],
                "confidence": float(predictions[index]),
            }
            for index in top_indices
        ]

        best = candidates[0]

        return {
            "image_id": image_id,
            "name": best["name"],
            "confidence": best["confidence"],
            "candidates": candidates,
            "error": None,
        }

    except Exception as exc:
        logger.error(
            "이미지 분류 실패: image_id=%s, 오류=%s", image_id, exc
        )

        return {
            "image_id": image_id,
            "name": None,
            "confidence": None,
            "candidates": [],
            "error": "이미지 분류 중 오류가 발생했습니다.",
        }


# [IMAGE] 여러 이미지 파일을 predict_single로 순회 분류해 결과 목록을 묶어 반환한다.
def predict_batch(files: list[Any]) -> dict[str, list[dict[str, Any]]]:
    results: list[dict[str, Any]] = []

    for index, file in enumerate(files):
        image_id = getattr(file, "filename", None) or f"image_{index}"
        file_bytes = _read_file_bytes(file)

        results.append(predict_single(file_bytes, image_id))

    return {"results": results}
