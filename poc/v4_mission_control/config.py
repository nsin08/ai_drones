"""Centralized v4 configuration."""

from functools import lru_cache

from pydantic import AliasChoices, Field, field_validator
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

    # Environment / MQTT routing (W14)
    DRONE_ENV: str = "ALL"  # SIM | HARDWARE | ALL
    MQTT_TOPIC_PREFIX: str = "fleet/sim"  # auto-derived; use fleet/{env} convention
    # MQTT broker — accept both MQTT_HOST (docker-compose) and MC_V4_MQTT_HOST
    MQTT_HOST: str = Field(
        default="localhost",
        validation_alias=AliasChoices("MC_V4_MQTT_HOST", "MQTT_HOST"),
    )
    MQTT_PORT: int = Field(
        default=1883,
        validation_alias=AliasChoices("MC_V4_MQTT_PORT", "MQTT_PORT"),
    )

    # Auth (W14) — False = bypass auth (legacy / test mode); True = require JWT Bearer
    AUTH_ENABLED: bool = False
    JWT_SECRET_KEY: str = "dev-secret-change-in-production"  # override via MC_V4_JWT_SECRET_KEY
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60

    @field_validator("ENVIRONMENT")
    @classmethod
    def normalize_environment(cls, value: str) -> str:
        normalized = value.strip().upper()
        if normalized not in {"SIM", "HARDWARE"}:
            raise ValueError("ENVIRONMENT must be SIM or HARDWARE")
        return normalized

    @field_validator("DRONE_ENV")
    @classmethod
    def normalize_drone_env(cls, value: str) -> str:
        normalized = value.strip().upper()
        if normalized not in {"SIM", "HARDWARE", "ALL"}:
            raise ValueError("DRONE_ENV must be SIM, HARDWARE, or ALL")
        return normalized


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached settings instance."""

    return Settings()
