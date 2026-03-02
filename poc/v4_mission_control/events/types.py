"""Event types constants for the v4 event log.

All event_type values written to the events table must come from this module.
Adding a new event type here is the single authoritative change required.
"""

# ---------------------------------------------------------------------------
# Command lifecycle
# ---------------------------------------------------------------------------
COMMAND_REQUESTED = "COMMAND_REQUESTED"
COMMAND_RETRYING = "COMMAND_RETRYING"
COMMAND_ACKED = "COMMAND_ACKED"
COMMAND_FAILED = "COMMAND_FAILED"
COMMAND_TIMED_OUT = "COMMAND_TIMED_OUT"
COMMAND_REJECTED = "COMMAND_REJECTED"

# ---------------------------------------------------------------------------
# Telemetry
# ---------------------------------------------------------------------------
TELEMETRY_RECEIVED = "TELEMETRY_RECEIVED"

# ---------------------------------------------------------------------------
# Mission lifecycle
# ---------------------------------------------------------------------------
MISSION_CREATED = "MISSION_CREATED"
MISSION_STARTED = "MISSION_STARTED"
MISSION_PAUSED = "MISSION_PAUSED"
MISSION_RESUMED = "MISSION_RESUMED"
MISSION_COMPLETED = "MISSION_COMPLETED"
MISSION_ABORTED = "MISSION_ABORTED"

# ---------------------------------------------------------------------------
# Task lifecycle
# ---------------------------------------------------------------------------
TASK_ASSIGNED = "TASK_ASSIGNED"
TASK_STARTED = "TASK_STARTED"
TASK_COMPLETED = "TASK_COMPLETED"
TASK_FAILED = "TASK_FAILED"
TASK_ABORTED = "TASK_ABORTED"

# ---------------------------------------------------------------------------
# Drone registry
# ---------------------------------------------------------------------------
DRONE_REGISTERED = "DRONE_REGISTERED"
DRONE_HEALTH_UPDATED = "DRONE_HEALTH_UPDATED"
DRONE_OFFLINE = "DRONE_OFFLINE"

# ---------------------------------------------------------------------------
# Convenience sets for validation
# ---------------------------------------------------------------------------
COMMAND_EVENTS = frozenset(
    {
        COMMAND_REQUESTED,
        COMMAND_RETRYING,
        COMMAND_ACKED,
        COMMAND_FAILED,
        COMMAND_TIMED_OUT,
        COMMAND_REJECTED,
    }
)

MISSION_EVENTS = frozenset(
    {
        MISSION_CREATED,
        MISSION_STARTED,
        MISSION_PAUSED,
        MISSION_RESUMED,
        MISSION_COMPLETED,
        MISSION_ABORTED,
    }
)

ALL_EVENT_TYPES = COMMAND_EVENTS | MISSION_EVENTS | frozenset(
    {
        TELEMETRY_RECEIVED,
        TASK_ASSIGNED,
        TASK_STARTED,
        TASK_COMPLETED,
        TASK_FAILED,
        TASK_ABORTED,
        DRONE_REGISTERED,
        DRONE_HEALTH_UPDATED,
        DRONE_OFFLINE,
    }
)
