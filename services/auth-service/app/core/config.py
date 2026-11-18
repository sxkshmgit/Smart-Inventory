"""App settings, read from environment variables or the .env file."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All configurable values in one place.

    pydantic-settings fills each field from an environment variable with the
    same name (or from .env). Fields without a default are required: the app
    refuses to start if they are missing, instead of failing later.
    """

    MONGO_URI: str
    DB_NAME: str = "auth_db"

    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


# Import this object anywhere: `from app.core.config import settings`
settings = Settings()
