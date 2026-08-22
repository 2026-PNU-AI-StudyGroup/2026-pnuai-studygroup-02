# Dockerfile
#
# Render 배포용 이미지: FastAPI(backend) + 정적 파일(frontend)을 한 컨테이너에서 서빙한다.
# backend/main.py가 StaticFiles로 frontend/를 "/"에 마운트하는 구조를 그대로 사용한다.

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/app/.cache/huggingface

WORKDIR /app

# faiss-cpu가 런타임에 필요로 하는 OpenMP 공유 라이브러리
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# 의존성 레이어를 소스 코드보다 먼저 캐싱해 재빌드 시간을 줄인다.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# RAG에서 사용하는 SentenceTransformer 임베딩 모델을 빌드 시점에 미리 받아 이미지에 포함한다.
# (런타임 콜드 스타트 때 HuggingFace 네트워크 호출 없이 바로 로딩되도록 하기 위함)
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2')"

# 애플리케이션 코드와 데이터 (model/artifacts의 .tflite 모델 포함)
COPY backend ./backend
COPY frontend ./frontend
COPY model ./model
COPY data ./data

EXPOSE 8000

# Render는 PORT 환경변수로 리슨 포트를 지정하므로 기본값 8000과 함께 셸 형태로 실행한다.
CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
