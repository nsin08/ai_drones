"""Shared runtime container for the v4 foundation slice."""

from dataclasses import dataclass
from functools import lru_cache

from ..config import Settings, get_settings
from ..repos.command_repo import InMemoryCommandRepository, SQLCommandRepository
from ..repos.event_repo import InMemoryEventRepository, SQLEventRepository
from ..repos.mission_repo import InMemoryMissionRepository, SQLMissionRepository
from .commands import CommandService
from .event_replay import EventReplayService
from .mission_service import MissionService
from .preflight import PreflightService


@dataclass(frozen=True)
class ServiceContainer:
    """Singleton service container for the v4 app."""

    settings: Settings
    command_repo: InMemoryCommandRepository | SQLCommandRepository
    event_repo: InMemoryEventRepository | SQLEventRepository
    mission_repo: InMemoryMissionRepository | SQLMissionRepository
    preflight_service: PreflightService
    command_service: CommandService
    mission_service: MissionService
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
        mission_repo: InMemoryMissionRepository | SQLMissionRepository = SQLMissionRepository()
    else:
        command_repo = InMemoryCommandRepository()
        event_repo = InMemoryEventRepository()
        mission_repo = InMemoryMissionRepository()

    preflight_service = PreflightService(settings=settings)
    command_service = CommandService(
        settings=settings,
        command_repo=command_repo,
        event_repo=event_repo,
        preflight_service=preflight_service,
    )
    mission_service = MissionService(
        mission_repo=mission_repo,
        event_repo=event_repo,
    )
    event_replay_service = EventReplayService()

    return ServiceContainer(
        settings=settings,
        command_repo=command_repo,
        event_repo=event_repo,
        mission_repo=mission_repo,
        preflight_service=preflight_service,
        command_service=command_service,
        mission_service=mission_service,
        event_replay_service=event_replay_service,
    )
