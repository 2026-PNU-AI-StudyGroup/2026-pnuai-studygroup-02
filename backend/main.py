# backend/main.py

# [MAIN] 현지 담당. 한국어 주석 필수
# FastAPI 앱 진입점: CORS, 정적 파일 서빙, 라우터 등록, 공통 예외 처리를 담당한다.

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend.config import settings
from backend.routers.health import router as health_router
from backend.routers.ingredients import router as ingredients_router
from backend.routers.nutrition import router as nutrition_router
from backend.routers.profile import router as profile_router
from backend.routers.recipes import router as recipes_router

# [MAIN] frontend 정적 파일 위치 (backend/main.py 기준 상위 폴더의 frontend/)
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"

app = FastAPI(title="Ingredient Project API")

# [MAIN] 프론트엔드(로컬 정적 서버 등)에서 API를 호출할 수 있도록 CORS를 허용한다.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# [MAIN] 팀원별 담당 라우터 등록
app.include_router(health_router)
app.include_router(ingredients_router)  # 현지
app.include_router(profile_router)
app.include_router(nutrition_router)  # 지은
app.include_router(recipes_router)  # 시은


# [MAIN] HTTPException(및 detail이 code/message/details 형태인 경우)을 공통 포맷으로 변환한다.
# [MAIN] fastapi.HTTPException은 starlette.exceptions.HTTPException의 서브클래스이므로,
# 기반 클래스로 등록해야 StaticFiles 등이 내부에서 던지는 starlette 예외까지 함께 잡힌다.
@app.exception_handler(StarletteHTTPException)
async def custom_http_exception_handler(
    request: Request,
    exc: StarletteHTTPException,
) -> JSONResponse:
    detail = exc.detail

    if isinstance(detail, dict) and "code" in detail and "message" in detail:
        body = {
            "code": detail.get("code"),
            "message": detail.get("message"),
            "details": detail.get("details"),
        }
    else:
        # [MAIN] 라우터에서 code/message/details 형태로 detail을 채우지 않은 경우를 대비한 기본값
        body = {
            "code": f"HTTP_{exc.status_code}",
            "message": detail if isinstance(detail, str) else "요청 처리 중 오류가 발생했습니다.",
            "details": None if isinstance(detail, str) else detail,
        }

    return JSONResponse(status_code=exc.status_code, content=body)


# [MAIN] 요청 스키마 검증 실패(422)도 동일한 공통 포맷으로 변환한다.
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "code": "VALIDATION_ERROR",
            "message": "요청 데이터가 올바르지 않습니다.",
            "details": exc.errors(),
        },
    )


# [MAIN] 그 외 예상하지 못한 예외는 500으로 감싸 공통 포맷으로 반환한다.
@app.exception_handler(Exception)
async def unhandled_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={
            "code": "INTERNAL_SERVER_ERROR",
            "message": "서버 내부 오류가 발생했습니다.",
            "details": str(exc),
        },
    )


# [MAIN] frontend/ 폴더를 정적 파일로 서빙한다. (index.html은 "/"에서 바로 접근 가능)
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
