from functools import lru_cache
from os import getenv

from dotenv import load_dotenv
from pydantic import BaseModel, Field

load_dotenv()


class Settings(BaseModel):
    app_name: str = "CARELINK"
    environment: str = Field(default_factory=lambda: getenv("CARELINK_ENV", "development"))
    database_url: str = Field(
        default_factory=lambda: getenv("CARELINK_DATABASE_URL", "sqlite:///./carelink.db")
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
