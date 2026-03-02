"""Centralized v4 configuration."""

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-backed v4 settings."""

    model_config = SettingsConfigDict(env_prefix="MC_V4_", case_sensitive=False)

    SERVICE_NAME: str = "mission-control-v4"
    ENVIRONMENT: str = "SIM"
    BATTERY_ARM_MIN_PCT: int = 10
    GPS_ARM_MIN_SATS: int = 4
    STALE_TIMEOUT_SEC: int = 30
    COMMAND_ACK_TIMEOUT_SEC: int = 5
    COMMAND_MAX_RETRIES: int = 3
    COMMAND_RETRY_BACKOFF_SEC: tuple[int, int, int] = (1, 2, 4)

    # Persistence
    DATABASE_URL: str = "postgresql+psycopg2://v4:v4@localhost:5432/missioncontrol"
    USE_DATABASE: bool = False  # set True in docker-compose; False keeps in-memory repos for tests
    EVENT_SNAPSHOT_INTERVAL: int = 100  # write DroneSnapshot every N events per drone

    @field_validator("ENVIRONMENT")
    @classmethod
    def normalize_environment(cls, value: str) -> str:
        normalized = value.strip().upper()
        if normalized not in {"SIM", "HARDWARE"}:
            raise ValueError("ENVIRONMENT must be SIM or HARDWARE")
        return normalized


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached settings instance."""

    return Settings()
