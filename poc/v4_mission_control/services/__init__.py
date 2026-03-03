"""Service exports for Mission Control v4."""

from .commands import CommandService
from .preflight import PreflightService
from .waypoint_uploader import WaypointUploader

__all__ = [
    "CommandService",
    "PreflightService",
    "ServiceContainer",
    "WaypointUploader",
    "get_service_container",
]


def __getattr__(name: str):
    if name == "ServiceContainer":
        from .runtime import ServiceContainer

        return ServiceContainer
    if name == "get_service_container":
        from .runtime import get_service_container

        return get_service_container
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
