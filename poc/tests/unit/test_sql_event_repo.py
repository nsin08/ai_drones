"""Tests for SQLEventRepository using SQLite in-memory.

Covers:
- append-only semantics
- list_recent filtering
- snapshot trigger (every EVENT_SNAPSHOT_INTERVAL events per drone)
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from poc.v4_mission_control.models import Base
from poc.v4_mission_control.repos.event_repo import SQLEventRepository
from poc.v4_mission_control.events.types import (
    COMMAND_REQUESTED,
    TELEMETRY_RECEIVED,
    DRONE_HEALTH_UPDATED,
)


@pytest.fixture()
def sqlite_session_factory():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    yield factory
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture()
def repo(sqlite_session_factory):
    r = SQLEventRepository(session_factory=sqlite_session_factory)
    r._snapshot_interval = 5  # lower threshold to make snapshot tests fast
    return r


def test_sql_event_repo_append_returns_stored_event(repo):
    stored = repo.append(
        event_type=COMMAND_REQUESTED,
        aggregate_type="COMMAND",
        aggregate_id="cmd-001",
        drone_id="SIM-001",
        payload_json={"command": "ARM"},
    )
    assert stored.event_id is not None
    assert stored.event_type == COMMAND_REQUESTED
    assert stored.drone_id == "SIM-001"


def test_sql_event_repo_list_recent_all(repo):
    for i in range(3):
        repo.append(
            event_type=TELEMETRY_RECEIVED,
            aggregate_type="DRONE",
            aggregate_id="SIM-001",
            drone_id="SIM-001",
            payload_json={"battery_pct": 90 - i},
        )
    items = repo.list_recent(limit=10)
    assert len(items) == 3


def test_sql_event_repo_list_recent_filtered_by_drone(repo):
    repo.append(event_type=TELEMETRY_RECEIVED, aggregate_type="DRONE", aggregate_id="SIM-001", drone_id="SIM-001", payload_json={})
    repo.append(event_type=TELEMETRY_RECEIVED, aggregate_type="DRONE", aggregate_id="SIM-002", drone_id="SIM-002", payload_json={})
    repo.append(event_type=TELEMETRY_RECEIVED, aggregate_type="DRONE", aggregate_id="SIM-001", drone_id="SIM-001", payload_json={})

    items = repo.list_recent(drone_id="SIM-001", limit=10)
    assert len(items) == 2
    assert all(item.drone_id == "SIM-001" for item in items)


def test_sql_event_repo_clear_raises(repo):
    with pytest.raises(NotImplementedError):
        repo.clear()


def test_sql_event_repo_snapshot_triggered_at_interval(repo, sqlite_session_factory):
    """Snapshot is written after exactly snapshot_interval events for a drone."""
    from poc.v4_mission_control.models.drone import DroneSnapshot

    drone_id = "SIM-SNAP-001"
    interval = repo._snapshot_interval  # 5 in fixture

    for i in range(interval):
        repo.append(
            event_type=TELEMETRY_RECEIVED,
            aggregate_type="DRONE",
            aggregate_id=drone_id,
            drone_id=drone_id,
            payload_json={"battery_pct": 80},
        )

    # After exactly `interval` events, one snapshot should exist
    session = sqlite_session_factory()
    try:
        snapshots = session.query(DroneSnapshot).filter(DroneSnapshot.drone_id == drone_id).all()
        assert len(snapshots) == 1
        assert snapshots[0].version_seq == interval
    finally:
        session.close()


def test_sql_event_repo_snapshot_not_triggered_before_interval(repo, sqlite_session_factory):
    """Snapshot is NOT written before the interval threshold."""
    from poc.v4_mission_control.models.drone import DroneSnapshot

    drone_id = "SIM-NOSNAP-001"
    interval = repo._snapshot_interval  # 5

    for i in range(interval - 1):
        repo.append(
            event_type=TELEMETRY_RECEIVED,
            aggregate_type="DRONE",
            aggregate_id=drone_id,
            drone_id=drone_id,
            payload_json={"battery_pct": 80},
        )

    session = sqlite_session_factory()
    try:
        count = session.query(DroneSnapshot).filter(DroneSnapshot.drone_id == drone_id).count()
        assert count == 0
    finally:
        session.close()
