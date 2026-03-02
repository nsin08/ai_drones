"""REST routes for Mission Control v4."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse

from ..config import Settings
from ..schemas.command import (
    CommandAcceptedResponse,
    CommandHistoryResponse,
    CommandRejectedResponse,
    CommandRequest,
)
from ..schemas.health import FleetHealthSummary, HealthResponse
from ..schemas.preflight import PreflightResponse
from ..services.runtime import ServiceContainer
from .dependencies import get_runtime, get_v4_settings

router = APIRouter(prefix="/api")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@router.get("/health", response_model=HealthResponse)
def read_health(settings: Settings = Depends(get_v4_settings)) -> HealthResponse:
    """Bootstrap liveness/readiness endpoint."""

    return HealthResponse(
        status="ok",
        service=settings.SERVICE_NAME,
        environment=settings.ENVIRONMENT,
        timestamp=_utc_now_iso(),
    )


@router.get("/drones/{drone_id}/preflight", response_model=PreflightResponse)
def read_preflight(
    drone_id: str,
    runtime: ServiceContainer = Depends(get_runtime),
) -> PreflightResponse:
    """Return the current preflight state for one drone."""

    return runtime.preflight_service.get_preflight(drone_id)


@router.post(
    "/commands",
    response_model=CommandAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={400: {"model": CommandRejectedResponse}},
)
def submit_command(
    payload: CommandRequest,
    runtime: ServiceContainer = Depends(get_runtime),
) -> CommandAcceptedResponse | JSONResponse:
    """Submit a command through the safe command path."""

    result = runtime.command_service.submit_command(payload)
    if isinstance(result, CommandRejectedResponse):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=result.model_dump(mode="json"),
        )
    return result


@router.get("/commands", response_model=CommandHistoryResponse)
def read_commands(
    drone_id: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    runtime: ServiceContainer = Depends(get_runtime),
) -> CommandHistoryResponse:
    """Return recent command history."""

    items = runtime.command_repo.list_recent(drone_id=drone_id, limit=limit)
    return CommandHistoryResponse(items=[item.as_history_item() for item in items])


@router.get("/fleet/health", response_model=FleetHealthSummary)
def read_fleet_health() -> FleetHealthSummary:
    """Placeholder fleet health summary for the v4 shell."""

    return FleetHealthSummary(healthy=0, warning=0, critical=0, offline=0, details=[])
