"""App settings, read from environment variables or the .env file."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All configurable values in one place.

    Fields without a default are required: the app refuses to start if they are missing.
    """

    MONGO_URI: str
    DB_NAME: str = "product_db"

    # Same secret as auth-service: we only verify its tokens, we never create them.
    SECRET_KEY: str
    ALGORITHM: str = "HS256"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


# Import this object anywhere: `from app.core.config import settings`
settings = Settings()
