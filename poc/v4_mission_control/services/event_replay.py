"""Event replay service for reconstructing drone state from the event log."""

from typing import Any

from sqlalchemy.orm import Session


class EventReplayService:
    """Rebuilds the last-known state of a drone by replaying its event log.

    Uses the most recent DroneSnapshot as a base (if one exists) then
    applies subsequent events — bounding replay cost to at most
    EVENT_SNAPSHOT_INTERVAL events.
    """

    def rebuild_drone_state(
        self,
        drone_id: str,
        session: Session,
    ) -> dict[str, Any]:
        """Return the reconstructed state dict for a drone.

        Resolution order:
        1. Find the latest DroneSnapshot for this drone (most recent version_seq).
        2. Load all Event rows created after that snapshot (or all events if none).
        3. Apply each event to the state dict in chronological order.
        4. Return the merged state.
        """
        from ..models.drone import DroneSnapshot
        from ..models.event import Event

        # Step 1: find best snapshot baseline
        snapshot = (
            session.query(DroneSnapshot)
            .filter(DroneSnapshot.drone_id == drone_id)
            .order_by(DroneSnapshot.version_seq.desc())
            .first()
        )

        state: dict[str, Any] = {}
        skip_count: int = 0

        if snapshot:
            state = dict(snapshot.state_json or {})
            # version_seq == number of events that existed when the snapshot was
            # written (per _maybe_snapshot / manual writes in tests).  Slicing by
            # position is immune to timestamp-collision issues that arise when
            # snapshot.created_at and a subsequent event share the same microsecond.
            skip_count = snapshot.version_seq

        # Step 2: load ALL events for this drone in chronological order, then
        # skip the first `skip_count` (already captured in the snapshot).
        all_events = (
            session.query(Event)
            .filter(Event.drone_id == drone_id)
            .order_by(Event.created_at.asc())
            .all()
        )
        events = all_events[skip_count:]

        # Step 3: apply events
        for event in events:
            state = self._apply(state, event)

        state["drone_id"] = drone_id
        return state

    @staticmethod
    def _apply(state: dict[str, Any], event: Any) -> dict[str, Any]:
        """Fold a single event into the current state dict."""
        from ..events.types import (
            COMMAND_ACKED,
            COMMAND_FAILED,
            COMMAND_REJECTED,
            COMMAND_REQUESTED,
            COMMAND_RETRYING,
            COMMAND_TIMED_OUT,
            DRONE_HEALTH_UPDATED,
            DRONE_OFFLINE,
            DRONE_REGISTERED,
            MISSION_ABORTED,
            MISSION_COMPLETED,
            MISSION_PAUSED,
            MISSION_RESUMED,
            MISSION_STARTED,
            TELEMETRY_RECEIVED,
        )

        payload: dict[str, Any] = event.payload_json or {}
        t = event.event_type

        if t == TELEMETRY_RECEIVED:
            state.update(payload)

        elif t == DRONE_REGISTERED:
            state.setdefault("env", payload.get("env", "SIM"))
            state["registered_at"] = event.created_at.isoformat()

        elif t == DRONE_HEALTH_UPDATED:
            state["health_score"] = payload.get("health_score")
            state["health_label"] = payload.get("health_label")

        elif t == DRONE_OFFLINE:
            state["health_label"] = "OFFLINE"

        elif t in (COMMAND_REQUESTED, COMMAND_RETRYING, COMMAND_ACKED, COMMAND_TIMED_OUT):
            state["last_command"] = payload.get("command")
            state["last_command_status"] = payload.get("status", t)

        elif t in (COMMAND_REJECTED, COMMAND_FAILED):
            state["last_command_status"] = payload.get("status", t)

        elif t in (MISSION_STARTED, MISSION_PAUSED, MISSION_RESUMED,
                   MISSION_COMPLETED, MISSION_ABORTED):
            state["mission_status"] = t

        return state

    def count_events(self, drone_id: str, session: Session) -> int:
        """Return the total number of events recorded for a drone."""
        from ..models.event import Event

        return session.query(Event).filter(Event.drone_id == drone_id).count()
