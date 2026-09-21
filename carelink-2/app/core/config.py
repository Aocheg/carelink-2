from functools import lru_cache
from os import getenv

from dotenv import load_dotenv
from pydantic import BaseModel, Field

load_dotenv()

class Settings(BaseModel):
    app_name: str = "CARELINK"
    environment: str = Field(default_factory=lambda: getenv("CARELINK_ENV", "development"))
    database_url: str = Field(default_factory=lambda: getenv("CARELINK_DATABASE_URL", "sqlite:///./carelink.db"))
    secret_key: str = Field(
        default_factory=lambda: getenv(
            "CARELINK_SECRET_KEY",
            "development-only-change-this-secret-before-shared-use",
        )
    )
    access_token_minutes: int = Field(default_factory=lambda: int(getenv("CARELINK_ACCESS_TOKEN_MINUTES", "60")))

@lru_cache
def get_settings() -> Settings:
    return Settings()
