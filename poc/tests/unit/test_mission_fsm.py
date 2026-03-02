"""Unit tests: Mission FSM transitions — W12.

Tests that valid transitions proceed and invalid transitions raise ValueError.
"""

import pytest

from poc.v4_mission_control.repos.event_repo import InMemoryEventRepository
from poc.v4_mission_control.repos.mission_repo import InMemoryMissionRepository
from poc.v4_mission_control.schemas.mission import MissionCreateRequest, MissionStatus, TaskCreateRequest
from poc.v4_mission_control.services.mission_service import MissionService


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _make_service() -> tuple[MissionService, InMemoryMissionRepository, InMemoryEventRepository]:
    repo = InMemoryMissionRepository()
    events = InMemoryEventRepository()
    svc = MissionService(mission_repo=repo, event_repo=events)
    return svc, repo, events


def _create(svc: MissionService) -> str:
    req = MissionCreateRequest(
        type="RECON",
        tasks=[TaskCreateRequest(type="WAYPOINT", drone_ids=["SIM-001"])],
        created_by="test",
    )
    resp = svc.create_mission(req)
    return resp.mission_id


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


class TestCreateMission:
    def test_new_mission_is_in_planning(self):
        svc, _, _ = _make_service()
        mid = _create(svc)
        m = svc.get_mission(mid)
        assert m is not None
        assert m.status == MissionStatus.PLANNING

    def test_new_mission_has_tasks(self):
        svc, _, _ = _make_service()
        mid = _create(svc)
        m = svc.get_mission(mid)
        assert m is not None
        assert len(m.tasks) == 1

    def test_create_emits_mission_created_event(self):
        svc, _, events = _make_service()
        _create(svc)
        types = [e.event_type for e in events._events]
        assert "MISSION_CREATED" in types


# ---------------------------------------------------------------------------
# Valid transitions
# ---------------------------------------------------------------------------


class TestValidTransitions:
    def test_planning_to_planned(self):
        svc, _, _ = _make_service()
        mid = _create(svc)
        m = svc.plan_mission(mid)
        assert m.status == MissionStatus.PLANNED

    def test_planned_to_active(self):
        svc, _, _ = _make_service()
        mid = _create(svc)
        svc.plan_mission(mid)
        m = svc.start_mission(mid)
        assert m.status == MissionStatus.ACTIVE

    def test_active_to_paused(self):
        svc, _, _ = _make_service()
        mid = _create(svc)
        svc.plan_mission(mid)
        svc.start_mission(mid)
        m = svc.pause_mission(mid)
        assert m.status == MissionStatus.PAUSED

    def test_paused_to_active(self):
        svc, _, _ = _make_service()
        mid = _create(svc)
        svc.plan_mission(mid)
        svc.start_mission(mid)
        svc.pause_mission(mid)
        m = svc.resume_mission(mid)
        assert m.status == MissionStatus.ACTIVE

    def test_active_to_completed(self):
        svc, _, _ = _make_service()
        mid = _create(svc)
        svc.plan_mission(mid)
        svc.start_mission(mid)
        m = svc.complete_mission(mid)
        assert m.status == MissionStatus.COMPLETED

    def test_any_non_terminal_to_aborted(self):
        for i, (advance, expected_from) in enumerate([
            (lambda svc, mid: None, "PLANNING"),
            (lambda svc, mid: svc.plan_mission(mid), "PLANNED"),
            (lambda svc, mid: (svc.plan_mission(mid), svc.start_mission(mid)), "ACTIVE"),
        ]):
            svc, _, _ = _make_service()
            mid = _create(svc)
            advance(svc, mid)
            m = svc.abort_mission(mid, reason="test abort")
            assert m.status == MissionStatus.ABORTED, f"Expected abort from {expected_from}"

    def test_transitions_emit_events(self):
        svc, _, events = _make_service()
        mid = _create(svc)
        svc.plan_mission(mid)
        svc.start_mission(mid)
        types = {e.event_type for e in events._events}
        assert "MISSION_PLANNED" in types
        assert "MISSION_ACTIVE" in types


# ---------------------------------------------------------------------------
# Invalid transitions
# ---------------------------------------------------------------------------


class TestInvalidTransitions:
    def test_cannot_start_from_planning(self):
        """PLANNING → ACTIVE is invalid (must go PLANNING → PLANNED → ACTIVE)."""
        svc, _, _ = _make_service()
        mid = _create(svc)
        with pytest.raises(ValueError, match="Cannot transition"):
            svc.start_mission(mid)

    def test_cannot_pause_from_planning(self):
        svc, _, _ = _make_service()
        mid = _create(svc)
        with pytest.raises(ValueError, match="Cannot transition"):
            svc.pause_mission(mid)

    def test_cannot_abort_completed_mission(self):
        svc, _, _ = _make_service()
        mid = _create(svc)
        svc.plan_mission(mid)
        svc.start_mission(mid)
        svc.complete_mission(mid)
        with pytest.raises(ValueError, match="Cannot transition"):
            svc.abort_mission(mid)

    def test_cannot_resume_from_active(self):
        """resume (PAUSED→ACTIVE) is invalid if already ACTIVE."""
        svc, _, _ = _make_service()
        mid = _create(svc)
        svc.plan_mission(mid)
        svc.start_mission(mid)
        with pytest.raises(ValueError, match="Cannot transition"):
            svc.resume_mission(mid)

    def test_transition_nonexistent_mission_raises_key_error(self):
        svc, _, _ = _make_service()
        with pytest.raises(KeyError):
            svc.start_mission("no-such-id")


# ---------------------------------------------------------------------------
# List / filter
# ---------------------------------------------------------------------------


class TestListMissions:
    def test_list_all_returns_all(self):
        svc, _, _ = _make_service()
        _create(svc)
        _create(svc)
        assert len(svc.list_missions()) == 2

    def test_list_filtered_by_status(self):
        svc, _, _ = _make_service()
        mid = _create(svc)
        svc.plan_mission(mid)
        svc.start_mission(mid)  # ACTIVE

        _create(svc)  # second stays in PLANNING

        active_missions = svc.list_missions(status=MissionStatus.ACTIVE)
        assert len(active_missions) == 1
        assert active_missions[0].status == MissionStatus.ACTIVE


# ---------------------------------------------------------------------------
# Concurrent missions
# ---------------------------------------------------------------------------


class TestConcurrentMissions:
    def test_two_missions_active_simultaneously(self):
        """Two separate missions can be ACTIVE at the same time with no cross-talk."""
        svc, _, _ = _make_service()
        mid1 = _create(svc)
        mid2 = _create(svc)

        svc.plan_mission(mid1)
        svc.start_mission(mid1)
        svc.plan_mission(mid2)
        svc.start_mission(mid2)

        m1 = svc.get_mission(mid1)
        m2 = svc.get_mission(mid2)
        assert m1.status == MissionStatus.ACTIVE
        assert m2.status == MissionStatus.ACTIVE

    def test_aborting_one_mission_does_not_affect_other(self):
        svc, _, _ = _make_service()
        mid1 = _create(svc)
        mid2 = _create(svc)
        svc.plan_mission(mid1)
        svc.start_mission(mid1)
        svc.plan_mission(mid2)
        svc.start_mission(mid2)

        svc.abort_mission(mid1)

        m1 = svc.get_mission(mid1)
        m2 = svc.get_mission(mid2)
        assert m1.status == MissionStatus.ABORTED
        assert m2.status == MissionStatus.ACTIVE
