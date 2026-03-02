"""Tests for SQLCommandRepository using SQLite in-memory.

These tests verify the SQL-backed command repo works end-to-end
without requiring a live PostgreSQL instance.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from poc.v4_mission_control.models import Base
from poc.v4_mission_control.repos.command_repo import SQLCommandRepository
from poc.v4_mission_control.schemas.command import CommandStatus


@pytest.fixture()
def sqlite_session_factory():
    """Yield a sessionmaker backed by an in-memory SQLite database."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    yield factory
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture()
def repo(sqlite_session_factory):
    return SQLCommandRepository(session_factory=sqlite_session_factory)


def test_sql_command_repo_create_requested(repo):
    stored = repo.create(
        drone_id="SIM-001",
        command="TAKEOFF",
        status=CommandStatus.REQUESTED,
        params_json={"alt_m": 20},
    )
    assert stored.cmd_id is not None
    assert stored.drone_id == "SIM-001"
    assert stored.command == "TAKEOFF"
    assert stored.status == CommandStatus.REQUESTED
    assert stored.attempt_count == 0


def test_sql_command_repo_create_rejected(repo):
    stored = repo.create(
        drone_id="HW-001",
        command="ARM",
        status=CommandStatus.REJECTED,
        rejection_reason="battery below minimum threshold",
        mark_completed=True,
    )
    assert stored.status == CommandStatus.REJECTED
    assert stored.rejection_reason == "battery below minimum threshold"
    assert stored.completed_at is not None


def test_sql_command_repo_list_recent_all(repo):
    repo.create(drone_id="SIM-001", command="TAKEOFF", status=CommandStatus.REQUESTED)
    repo.create(drone_id="SIM-002", command="LAND", status=CommandStatus.REQUESTED)
    items = repo.list_recent(limit=10)
    assert len(items) == 2


def test_sql_command_repo_list_recent_filtered_by_drone(repo):
    repo.create(drone_id="SIM-001", command="TAKEOFF", status=CommandStatus.REQUESTED)
    repo.create(drone_id="SIM-002", command="LAND", status=CommandStatus.REQUESTED)
    repo.create(drone_id="SIM-001", command="HOLD", status=CommandStatus.REQUESTED)

    items = repo.list_recent(drone_id="SIM-001", limit=10)
    assert len(items) == 2
    assert all(item.drone_id == "SIM-001" for item in items)


def test_sql_command_repo_list_recent_respects_limit(repo):
    for i in range(5):
        repo.create(drone_id="SIM-001", command="HOLD", status=CommandStatus.REQUESTED)
    items = repo.list_recent(limit=3)
    assert len(items) == 3


def test_sql_command_repo_clear_raises(repo):
    with pytest.raises(NotImplementedError):
        repo.clear()


def test_sql_command_repo_as_history_item(repo):
    stored = repo.create(
        drone_id="SIM-001",
        command="ARM",
        status=CommandStatus.REQUESTED,
        params_json={"mode": "GUIDED"},
        requested_by="pilot1",
    )
    item = stored.as_history_item()
    assert item.drone_id == "SIM-001"
    assert item.command == "ARM"
    assert item.status == CommandStatus.REQUESTED
