"""Shared runtime container for the v4 foundation slice."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from functools import lru_cache

from ..auth.operator_store import InMemoryOperatorStore
from ..config import Settings, get_settings
from ..infra.circuit_breaker import CircuitBreaker
from ..infra.mqtt_client import MqttReconnectClient
from ..repos.command_repo import InMemoryCommandRepository, SQLCommandRepository
from ..repos.drone_repo import DroneRepository, InMemoryDroneRepository
from ..repos.event_repo import InMemoryEventRepository, SQLEventRepository
from ..repos.mission_repo import InMemoryMissionRepository, SQLMissionRepository
from ..ws.manager import WebSocketManager
from .commands import CommandService
from .event_replay import EventReplayService
from .health_service import HealthService
from .mission_service import MissionService
from .preflight import PreflightService
from .service_status import ServiceStatusService

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class ServiceContainer:
    """Singleton service container for the v4 app."""

    settings: Settings
    command_repo: InMemoryCommandRepository | SQLCommandRepository
    event_repo: InMemoryEventRepository | SQLEventRepository
    mission_repo: InMemoryMissionRepository | SQLMissionRepository
    drone_repo: InMemoryDroneRepository | DroneRepository
    preflight_service: PreflightService
    command_service: CommandService
    mission_service: MissionService
    event_replay_service: EventReplayService
    health_service: HealthService
    ws_manager: WebSocketManager
    operator_store: InMemoryOperatorStore
    service_status: ServiceStatusService
    inventory_circuit_breaker: CircuitBreaker
    mqtt_client: MqttReconnectClient | None = None


@lru_cache(maxsize=1)
def get_service_container() -> ServiceContainer:
    """Build and cache the v4 service container.

    Uses SQL-backed repositories when settings.USE_DATABASE is True,
    otherwise falls back to in-memory repos (safe for tests without a DB).
    """
    settings = get_settings()

    # ---- Repositories ----------------------------------------------------
    if settings.USE_DATABASE:
        command_repo: InMemoryCommandRepository | SQLCommandRepository = SQLCommandRepository()
        event_repo: InMemoryEventRepository | SQLEventRepository = SQLEventRepository()
        mission_repo: InMemoryMissionRepository | SQLMissionRepository = SQLMissionRepository()
        drone_repo: InMemoryDroneRepository | DroneRepository = DroneRepository()
    else:
        command_repo = InMemoryCommandRepository()
        event_repo = InMemoryEventRepository()
        mission_repo = InMemoryMissionRepository()
        drone_repo = InMemoryDroneRepository()

    # ---- Auth stores -------------------------------------------------------
    operator_store = InMemoryOperatorStore()

    # ---- WebSocket manager -----------------------------------------------
    ws_manager = WebSocketManager()

    # ---- Service status (W15) -------------------------------------------
    service_status = ServiceStatusService(ws_manager=ws_manager)

    # ---- Inventory circuit breaker (W15) --------------------------------
    inventory_circuit_breaker = CircuitBreaker(
        threshold=3,
        reset_timeout=30.0,
        name="inventory",
    )

    # ---- MQTT client (W15) — create but don't connect yet ---------------
    mqtt_client: MqttReconnectClient | None = None
    if settings.MQTT_HOST:
        mqtt_client = MqttReconnectClient(
            host=settings.MQTT_HOST,
            port=settings.MQTT_PORT,
            on_connect=service_status.report_mqtt_connected,
            on_disconnect=service_status.report_mqtt_disconnected,
        )

    # ---- Services --------------------------------------------------------
    preflight_service = PreflightService(settings=settings)

    # ---- Inline MQTT broker adapter for CommandService -------------------
    class _MqttCommandBroker:
        """Minimal MessageBroker shim backed by MqttReconnectClient."""

        def __init__(self, client: MqttReconnectClient | None) -> None:
            self._client = client

        def publish(self, topic: str, payload: dict) -> None:
            if self._client:
                self._client.publish(topic, json.dumps(payload))
            else:
                log.warning("Command publish skipped — no MQTT client (topic=%s)", topic)

        def subscribe(self, *_a, **_kw) -> None:  # managed by runtime
            pass

        def start(self) -> None:
            pass

        def stop(self) -> None:
            pass

    mqtt_broker_adapter = _MqttCommandBroker(mqtt_client)

    command_service = CommandService(
        settings=settings,
        command_repo=command_repo,
        event_repo=event_repo,
        preflight_service=preflight_service,
        broker=mqtt_broker_adapter,
        ws_manager=ws_manager,
    )

    # ---- Wire MQTT subscriptions + WS relay (now command_service exists) -
    if mqtt_client is not None:
        def _on_mqtt_message(topic: str, payload: bytes) -> None:
            try:
                data = json.loads(payload)
            except (json.JSONDecodeError, TypeError):
                log.debug("MQTT non-JSON payload on %s — skipped", topic)
                return

            if "/telemetry" in topic or "/status" in topic:
                ws_manager.broadcast_sync("telemetry_update", data)
            elif topic == "fleet/system/command_ack":
                ws_manager.broadcast_sync("command_ack", data)
                cmd_id_raw = data.get("cmd_id")
                if cmd_id_raw:
                    from uuid import UUID as _UUID
                    try:
                        uid = _UUID(str(cmd_id_raw))
                        if data.get("result") == "OK":
                            command_service.ack_command(uid)
                        else:
                            command_service.nack_command(
                                uid, reason=data.get("detail", "nack")
                            )
                    except Exception:
                        pass

        mqtt_client.set_message_callback(_on_mqtt_message)
        mqtt_client.subscribe("fleet/+/telemetry")
        mqtt_client.subscribe("fleet/+/status")
        mqtt_client.subscribe("fleet/system/command_ack")
        mqtt_client.connect()
    mission_service = MissionService(
        mission_repo=mission_repo,
        event_repo=event_repo,
    )
    event_replay_service = EventReplayService()
    health_service = HealthService(
        settings=settings,
        drone_repo=drone_repo,
        ws_manager=ws_manager,
    )

    return ServiceContainer(
        settings=settings,
        command_repo=command_repo,
        event_repo=event_repo,
        mission_repo=mission_repo,
        drone_repo=drone_repo,
        preflight_service=preflight_service,
        command_service=command_service,
        mission_service=mission_service,
        event_replay_service=event_replay_service,
        health_service=health_service,
        ws_manager=ws_manager,
        operator_store=operator_store,
        service_status=service_status,
        inventory_circuit_breaker=inventory_circuit_breaker,
        mqtt_client=mqtt_client,
    )
