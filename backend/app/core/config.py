from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.paths import BACKEND_ROOT, REPOSITORY_ROOT


class Settings(BaseSettings):
    APP_NAME: str = "AgentBench"
    APP_ENV: str = "development"
    OMNIROUTE_BASE_URL: str = "http://localhost:20128/v1"
    OMNIROUTE_API_KEY: str = ""
    OMNIROUTE_TIMEOUT_SECONDS: float = 60.0
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.5-flash"
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    OPENROUTER_API_KEY: str = ""

    model_config = SettingsConfigDict(
        env_file=(REPOSITORY_ROOT / ".env", BACKEND_ROOT / ".env"),
        env_file_encoding="utf-8",
    )


settings = Settings()
