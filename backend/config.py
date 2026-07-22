# backend/config.py

# [MAIN] 현지 담당. 한국어 주석 필수
# .env 파일에서 환경 변수를 읽어 전역 설정 객체로 노출한다.

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # [MAIN] Gemini(Anthropic) API 호출에 사용하는 키. 없으면 Mock 응답으로 대체된다.
    ANTHROPIC_API_KEY: str = ""

    # [MAIN] true면 외부 API/모델 호출 없이 고정된 Mock 데이터를 반환한다.
    MOCK_MODE: bool = False

    # [MAIN] CORS를 허용할 프론트엔드 origin 목록. .env에는 "a,b,c" 형태의 문자열로 저장한다.
    # [MAIN] list[str]로 선언하면 pydantic-settings가 JSON으로 먼저 파싱을 시도해 실패하므로 str로 받는다.
    CORS_ORIGINS: str = "http://localhost:5500,http://127.0.0.1:5500"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


# [MAIN] 앱 전역에서 재사용할 설정 객체. lru_cache로 한 번만 생성한다.
@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
