"""Shared runtime container for the v4 foundation slice."""

from dataclasses import dataclass
from functools import lru_cache

from ..config import Settings, get_settings
from ..repos.command_repo import InMemoryCommandRepository
from ..repos.event_repo import InMemoryEventRepository
from .commands import CommandService
from .preflight import PreflightService


@dataclass(frozen=True)
class ServiceContainer:
    """Singleton service container for the v4 app."""

    settings: Settings
    command_repo: InMemoryCommandRepository
    event_repo: InMemoryEventRepository
    preflight_service: PreflightService
    command_service: CommandService


@lru_cache(maxsize=1)
def get_service_container() -> ServiceContainer:
    """Build and cache the v4 service container."""

    settings = get_settings()
    command_repo = InMemoryCommandRepository()
    event_repo = InMemoryEventRepository()
    preflight_service = PreflightService(settings=settings)
    command_service = CommandService(
        settings=settings,
        command_repo=command_repo,
        event_repo=event_repo,
        preflight_service=preflight_service,
    )
    return ServiceContainer(
        settings=settings,
        command_repo=command_repo,
        event_repo=event_repo,
        preflight_service=preflight_service,
        command_service=command_service,
    )
