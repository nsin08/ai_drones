"""Canonical Socket.IO / WebSocket event names and reuse boundary constants."""

FLEET_TELEMETRY_EVENT = "fleet_telemetry"
COMMAND_STATUS_EVENT = "command_status"
DRONE_HEALTH_EVENT = "drone_health"  # W13: broadcast after health score update
SYSTEM_ALERT_EVENT = "system_alert"
MISSION_STATE_EVENT = "mission_state"
SERVICE_STATUS_EVENT = "service_status"

SOCKET_EVENT_NAMES = (
    FLEET_TELEMETRY_EVENT,
    COMMAND_STATUS_EVENT,
    DRONE_HEALTH_EVENT,
    SYSTEM_ALERT_EVENT,
    MISSION_STATE_EVENT,
    SERVICE_STATUS_EVENT,
)

V3_REUSE_BOUNDARY = {
    "allowed": (
        "poc.src.domain.telemetry",
        "poc.src.ports.message_broker",
        "poc.src.adapters.memory_broker",
    ),
    "blocked": (
        "poc.mission_control_v3 Flask routes",
        "v3 module-level in-memory state",
        "v3 response payload shapes not explicitly pinned for v4",
    ),
}
