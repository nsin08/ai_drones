"""Tests for EventReplayService: state reconstruction from the event log."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from poc.v4_mission_control.models import Base
from poc.v4_mission_control.models.drone import DroneSnapshot
from poc.v4_mission_control.models.event import Event
from poc.v4_mission_control.services.event_replay import EventReplayService
from poc.v4_mission_control.events.types import (
    COMMAND_ACKED,
    DRONE_HEALTH_UPDATED,
    DRONE_OFFLINE,
    MISSION_STARTED,
    TELEMETRY_RECEIVED,
)


@pytest.fixture()
def db_session():
    """Yield a SQLite in-memory session for replay tests."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    session: Session = factory()
    yield session
    session.close()
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture()
def replay_service():
    return EventReplayService()


def _add_event(session: Session, drone_id: str, event_type: str, payload: dict) -> None:
    """Helper: append a raw event row directly."""
    evt = Event(
        event_type=event_type,
        aggregate_type="DRONE",
        aggregate_id=drone_id,
        drone_id=drone_id,
        payload_json=payload,
    )
    session.add(evt)
    session.commit()


def test_replay_empty_log_returns_drone_id(db_session, replay_service):
    state = replay_service.rebuild_drone_state("SIM-001", db_session)
    assert state["drone_id"] == "SIM-001"


def test_replay_telemetry_updates_state(db_session, replay_service):
    _add_event(db_session, "SIM-001", TELEMETRY_RECEIVED, {"battery_pct": 76, "gps_sats": 9})
    _add_event(db_session, "SIM-001", TELEMETRY_RECEIVED, {"battery_pct": 74})

    state = replay_service.rebuild_drone_state("SIM-001", db_session)
    assert state["battery_pct"] == 74
    assert state["gps_sats"] == 9  # persisted from first event


def test_replay_health_event_sets_label(db_session, replay_service):
    _add_event(db_session, "SIM-002", DRONE_HEALTH_UPDATED, {"health_score": 0.85, "health_label": "GREEN"})

    state = replay_service.rebuild_drone_state("SIM-002", db_session)
    assert state["health_score"] == 0.85
    assert state["health_label"] == "GREEN"


def test_replay_offline_event_overrides_label(db_session, replay_service):
    _add_event(db_session, "SIM-003", DRONE_HEALTH_UPDATED, {"health_score": 0.9, "health_label": "GREEN"})
    _add_event(db_session, "SIM-003", DRONE_OFFLINE, {})

    state = replay_service.rebuild_drone_state("SIM-003", db_session)
    assert state["health_label"] == "OFFLINE"


def test_replay_command_acked_sets_last_command_status(db_session, replay_service):
    _add_event(db_session, "SIM-004", COMMAND_ACKED, {"command": "ARM", "status": "ACKED"})

    state = replay_service.rebuild_drone_state("SIM-004", db_session)
    assert state["last_command"] == "ARM"
    assert state["last_command_status"] == "ACKED"


def test_replay_uses_snapshot_as_base(db_session, replay_service):
    """Replay starts from snapshot; only applies events after snapshot time."""
    import uuid
    from datetime import datetime, timezone

    drone_id = "SIM-SNAP-001"

    # A "stale" event before snapshot — should NOT appear in state
    _add_event(db_session, drone_id, TELEMETRY_RECEIVED, {"battery_pct": 10})

    # Write a snapshot representing state after the stale event
    from sqlalchemy.orm import Session

    snapshot = DroneSnapshot(
        drone_id=drone_id,
        version_seq=1,
        state_json={"battery_pct": 85, "health_label": "GREEN"},
    )
    db_session.add(snapshot)
    db_session.commit()

    # A fresh event AFTER the snapshot
    _add_event(db_session, drone_id, DRONE_HEALTH_UPDATED, {"health_score": 0.5, "health_label": "YELLOW"})

    state = replay_service.rebuild_drone_state(drone_id, db_session)

    # Should use snapshot base (battery_pct=85) not the stale event (10)
    assert state["battery_pct"] == 85
    # Should apply the post-snapshot event
    assert state["health_label"] == "YELLOW"


def test_replay_count_events(db_session, replay_service):
    for _ in range(7):
        _add_event(db_session, "SIM-006", TELEMETRY_RECEIVED, {"battery_pct": 90})

    count = replay_service.count_events("SIM-006", db_session)
    assert count == 7


def test_replay_isolates_drones(db_session, replay_service):
    """State rebuild for drone A must not include events from drone B."""
    _add_event(db_session, "SIM-A", TELEMETRY_RECEIVED, {"battery_pct": 90})
    _add_event(db_session, "SIM-B", TELEMETRY_RECEIVED, {"battery_pct": 30})

    state_a = replay_service.rebuild_drone_state("SIM-A", db_session)
    assert state_a.get("battery_pct") == 90

    state_b = replay_service.rebuild_drone_state("SIM-B", db_session)
    assert state_b.get("battery_pct") == 30
