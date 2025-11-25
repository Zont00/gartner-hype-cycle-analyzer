from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    # API Keys
    deepseek_api_key: str = ""
    news_api_key: str | None = None
    twitter_bearer_token: str | None = None

    # Database
    database_path: str = "data/hype_cycle.db"

    # Cache
    cache_ttl_hours: int = 24

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    reload: bool = True

    # Logging
    log_level: str = "INFO"

    class Config:
        env_file = ".env"
        case_sensitive = False

@lru_cache()
def get_settings():
    """Cached settings singleton"""
    return Settings()
