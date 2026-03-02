"""FastAPI dependencies for Mission Control v4."""

from ..config import Settings, get_settings
from ..services.runtime import ServiceContainer, get_service_container


def get_runtime() -> ServiceContainer:
    """Return the singleton service container."""

    return get_service_container()


def get_v4_settings() -> Settings:
    """Return the singleton settings object."""

    return get_settings()
