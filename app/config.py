from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str  # --admin Used by alembic
    app_database_url: str  # --non superuser Used by the app
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 30
    storage_dir: str = "uploads"


settings = Settings()
