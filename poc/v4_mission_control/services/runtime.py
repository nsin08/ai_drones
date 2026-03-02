"""Shared runtime container for the v4 foundation slice."""

from dataclasses import dataclass
from functools import lru_cache

from ..config import Settings, get_settings
from ..repos.command_repo import InMemoryCommandRepository, SQLCommandRepository
from ..repos.event_repo import InMemoryEventRepository, SQLEventRepository
from .commands import CommandService
from .event_replay import EventReplayService
from .preflight import PreflightService


@dataclass(frozen=True)
class ServiceContainer:
    """Singleton service container for the v4 app."""

    settings: Settings
    command_repo: InMemoryCommandRepository | SQLCommandRepository
    event_repo: InMemoryEventRepository | SQLEventRepository
    preflight_service: PreflightService
    command_service: CommandService
    event_replay_service: EventReplayService


@lru_cache(maxsize=1)
def get_service_container() -> ServiceContainer:
    """Build and cache the v4 service container.

    Uses SQL-backed repositories when settings.USE_DATABASE is True,
    otherwise falls back to in-memory repos (safe for tests without a DB).
    """
    settings = get_settings()

    if settings.USE_DATABASE:
        command_repo: InMemoryCommandRepository | SQLCommandRepository = SQLCommandRepository()
        event_repo: InMemoryEventRepository | SQLEventRepository = SQLEventRepository()
    else:
        command_repo = InMemoryCommandRepository()
        event_repo = InMemoryEventRepository()

    preflight_service = PreflightService(settings=settings)
    command_service = CommandService(
        settings=settings,
        command_repo=command_repo,
        event_repo=event_repo,
        preflight_service=preflight_service,
    )
    event_replay_service = EventReplayService()

    return ServiceContainer(
        settings=settings,
        command_repo=command_repo,
        event_repo=event_repo,
        preflight_service=preflight_service,
        command_service=command_service,
        event_replay_service=event_replay_service,
    )
