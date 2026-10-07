from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "AgentBench"
    APP_ENV: str = "development"
    OMNIROUTE_BASE_URL: str = "http://localhost:20128/v1"
    OMNIROUTE_API_KEY: str = ""

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()
