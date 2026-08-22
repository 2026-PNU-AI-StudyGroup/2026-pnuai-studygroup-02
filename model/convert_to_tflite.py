# model/convert_to_tflite.py
#
# .keras 모델을 float16 양자화된 .tflite로 변환한다.
# 변환에는 풀 TensorFlow가 필요하지만(로컬/CI에서만 실행), 배포 서버는 결과물인
# .tflite 파일과 ai-edge-litert 인터프리터만 있으면 되므로 메모리 사용량이 크게 줄어든다.

from pathlib import Path

import tensorflow as tf

ARTIFACT_DIR = Path(__file__).resolve().parent / "artifacts"
KERAS_MODEL_PATH = ARTIFACT_DIR / "ingredient_model_v2.keras"
TFLITE_MODEL_PATH = ARTIFACT_DIR / "ingredient_model_v2.tflite"


def convert() -> None:
    model = tf.keras.models.load_model(KERAS_MODEL_PATH)

    converter = tf.lite.TFLiteConverter.from_keras_model(model)
    converter.optimizations = [tf.lite.Optimize.DEFAULT]
    converter.target_spec.supported_types = [tf.float16]

    tflite_model = converter.convert()

    TFLITE_MODEL_PATH.write_bytes(tflite_model)

    print(f"변환 완료: {TFLITE_MODEL_PATH} ({TFLITE_MODEL_PATH.stat().st_size / 1024 / 1024:.2f} MB)")


if __name__ == "__main__":
    convert()
