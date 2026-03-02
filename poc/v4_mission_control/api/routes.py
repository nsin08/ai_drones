"""REST routes for Mission Control v4."""

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from fastapi.responses import JSONResponse

from ..config import Settings
from ..schemas.command import (
    CommandAcceptedResponse,
    CommandHistoryItem,
    CommandHistoryResponse,
    CommandRejectedResponse,
    CommandRequest,
)
from ..schemas.health import DroneHealthResult, FleetHealthSummary, HealthResponse
from ..schemas.mission import (
    MissionCreateRequest,
    MissionListResponse,
    MissionResponse,
    MissionStatus,
    MissionTransitionRequest,
    TaskState,
)
from ..schemas.preflight import PreflightResponse
from ..services.runtime import ServiceContainer
from .dependencies import get_runtime, get_v4_settings

router = APIRouter(prefix="/api")

# WebSocket endpoint lives outside the /api prefix so clients connect as ws://host/ws
ws_router = APIRouter()


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


@router.get("/health", response_model=HealthResponse)
def read_health(settings: Settings = Depends(get_v4_settings)) -> HealthResponse:
    """Bootstrap liveness/readiness endpoint."""

    return HealthResponse(
        status="ok",
        service=settings.SERVICE_NAME,
        environment=settings.ENVIRONMENT,
        timestamp=_utc_now_iso(),
    )


# ---------------------------------------------------------------------------
# Preflight
# ---------------------------------------------------------------------------


@router.get("/drones/{drone_id}/preflight", response_model=PreflightResponse)
def read_preflight(
    drone_id: str,
    runtime: ServiceContainer = Depends(get_runtime),
) -> PreflightResponse:
    """Return the current preflight state for one drone."""

    return runtime.preflight_service.get_preflight(drone_id)


# ---------------------------------------------------------------------------
# Fleet health (real — powered by HealthService, W13)
# ---------------------------------------------------------------------------


@router.get("/fleet/health", response_model=FleetHealthSummary)
def read_fleet_health(
    runtime: ServiceContainer = Depends(get_runtime),
) -> FleetHealthSummary:
    """Return aggregate fleet health scores from the health scoring engine."""

    return runtime.health_service.fleet_summary()


@router.get("/drones/{drone_id}/health", response_model=DroneHealthResult)
def read_drone_health(
    drone_id: str,
    runtime: ServiceContainer = Depends(get_runtime),
) -> DroneHealthResult:
    """Return the health score and label for a single drone."""

    result = runtime.health_service.get_drone_health(drone_id)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"Drone {drone_id!r} not found in registry",
        )
    return result


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


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


@router.get("/commands/{cmd_id}", response_model=CommandHistoryItem)
def read_command(
    cmd_id: UUID,
    runtime: ServiceContainer = Depends(get_runtime),
) -> CommandHistoryItem:
    """Return a single command by its ID."""

    record = runtime.command_repo.get(cmd_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Command {cmd_id} not found")
    return record.as_history_item()


@router.post(
    "/commands/{cmd_id}/ack",
    response_model=CommandHistoryItem,
    status_code=status.HTTP_200_OK,
)
def ack_command(
    cmd_id: UUID,
    runtime: ServiceContainer = Depends(get_runtime),
) -> CommandHistoryItem:
    """ACK a command — marks it ACKED and stops the retry loop."""

    result = runtime.command_service.ack_command(cmd_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Command {cmd_id} not found")
    return result


@router.post(
    "/commands/{cmd_id}/nack",
    response_model=CommandHistoryItem,
    status_code=status.HTTP_200_OK,
)
def nack_command(
    cmd_id: UUID,
    reason: str = Query(default="nack"),
    runtime: ServiceContainer = Depends(get_runtime),
) -> CommandHistoryItem:
    """NACK a command — marks it FAILED and stops the retry loop."""

    result = runtime.command_service.nack_command(cmd_id, reason=reason)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Command {cmd_id} not found")
    return result


# ---------------------------------------------------------------------------
# Missions
# ---------------------------------------------------------------------------


@router.post(
    "/missions",
    response_model=MissionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_mission(
    payload: MissionCreateRequest,
    runtime: ServiceContainer = Depends(get_runtime),
) -> MissionResponse:
    """Create a new mission in PLANNING state."""

    return runtime.mission_service.create_mission(payload)


@router.get("/missions", response_model=MissionListResponse)
def list_missions(
    status_filter: MissionStatus | None = Query(default=None, alias="status"),
    runtime: ServiceContainer = Depends(get_runtime),
) -> MissionListResponse:
    """List all missions, optionally filtered by status."""

    items = runtime.mission_service.list_missions(status=status_filter)
    return MissionListResponse(items=items, total=len(items))


@router.get("/missions/{mission_id}", response_model=MissionResponse)
def read_mission(
    mission_id: str,
    runtime: ServiceContainer = Depends(get_runtime),
) -> MissionResponse:
    """Return a single mission by ID."""

    record = runtime.mission_service.get_mission(mission_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Mission {mission_id!r} not found")
    return record


@router.post("/missions/{mission_id}/plan", response_model=MissionResponse)
def plan_mission(
    mission_id: str,
    body: MissionTransitionRequest = MissionTransitionRequest(),
    runtime: ServiceContainer = Depends(get_runtime),
) -> MissionResponse:
    """Advance mission from PLANNING → PLANNED."""

    try:
        return runtime.mission_service.plan_mission(
            mission_id, requested_by=body.requested_by
        )
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/missions/{mission_id}/start", response_model=MissionResponse)
def start_mission(
    mission_id: str,
    body: MissionTransitionRequest = MissionTransitionRequest(),
    runtime: ServiceContainer = Depends(get_runtime),
) -> MissionResponse:
    """Advance mission from PLANNED → ACTIVE."""

    try:
        return runtime.mission_service.start_mission(
            mission_id, requested_by=body.requested_by
        )
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/missions/{mission_id}/pause", response_model=MissionResponse)
def pause_mission(
    mission_id: str,
    body: MissionTransitionRequest = MissionTransitionRequest(),
    runtime: ServiceContainer = Depends(get_runtime),
) -> MissionResponse:
    """Transition ACTIVE → PAUSED."""

    try:
        return runtime.mission_service.pause_mission(
            mission_id, requested_by=body.requested_by
        )
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/missions/{mission_id}/resume", response_model=MissionResponse)
def resume_mission(
    mission_id: str,
    body: MissionTransitionRequest = MissionTransitionRequest(),
    runtime: ServiceContainer = Depends(get_runtime),
) -> MissionResponse:
    """Transition PAUSED → ACTIVE."""

    try:
        return runtime.mission_service.resume_mission(
            mission_id, requested_by=body.requested_by
        )
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/missions/{mission_id}/complete", response_model=MissionResponse)
def complete_mission(
    mission_id: str,
    body: MissionTransitionRequest = MissionTransitionRequest(),
    runtime: ServiceContainer = Depends(get_runtime),
) -> MissionResponse:
    """Transition ACTIVE → COMPLETED."""

    try:
        return runtime.mission_service.complete_mission(
            mission_id, requested_by=body.requested_by
        )
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/missions/{mission_id}/abort", response_model=MissionResponse)
def abort_mission(
    mission_id: str,
    body: MissionTransitionRequest = MissionTransitionRequest(),
    runtime: ServiceContainer = Depends(get_runtime),
) -> MissionResponse:
    """Abort a mission from any non-terminal state."""

    try:
        return runtime.mission_service.abort_mission(
            mission_id,
            requested_by=body.requested_by,
            reason=body.reason,
        )
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# WebSocket  (/ws — outside the /api prefix, registered via ws_router)
# ---------------------------------------------------------------------------


@ws_router.websocket("/ws")
async def websocket_endpoint(
    ws: WebSocket,
    runtime: ServiceContainer = Depends(get_runtime),
) -> None:
    """WebSocket endpoint for real-time command status and drone health events.

    Clients connect to ``ws://host/ws``.  The server pushes JSON messages:

    * ``command_status``  — emitted after every command state transition.
    * ``drone_health``    — emitted after each drone health score update.
    """
    await runtime.ws_manager.connect(ws)
    try:
        while True:
            # Keep the connection alive; the server is the publisher.
            # Ignore any incoming text from the client.
            await ws.receive_text()
    except WebSocketDisconnect:
        runtime.ws_manager.disconnect(ws)
