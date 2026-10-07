from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "AgentBench"
    APP_ENV: str = "development"

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()
