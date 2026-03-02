"""Unit + API tests: ACL helpers and command permission enforcement (W14).

Coverage:
  - check_command_permission: OBSERVER, PILOT (restricted/unrestricted), ADMIN
  - require_admin: passes for ADMIN, raises for PILOT/OBSERVER
  - API: OBSERVER → 403, PILOT unassigned → 403, PILOT assigned → 202, ADMIN → 202
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from poc.v4_mission_control.app import create_app
from poc.v4_mission_control.auth.acl import check_command_permission, require_admin
from poc.v4_mission_control.auth.dependencies import get_current_operator
from poc.v4_mission_control.auth.operator_store import OperatorContext
from poc.v4_mission_control.services.runtime import get_service_container


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _observer() -> OperatorContext:
    return OperatorContext(
        operator_id="op-obs",
        username="observer",
        role="OBSERVER",
        allowed_drones=[],
    )


def _pilot_restricted(drones: list[str]) -> OperatorContext:
    return OperatorContext(
        operator_id="op-pilot",
        username="pilot1",
        role="PILOT",
        allowed_drones=drones,
    )


def _pilot_unrestricted() -> OperatorContext:
    return OperatorContext(
        operator_id="op-pilot-all",
        username="pilotall",
        role="PILOT",
        allowed_drones=[],  # empty = no restriction
    )


def _admin() -> OperatorContext:
    return OperatorContext(
        operator_id="op-adm",
        username="admin",
        role="ADMIN",
        allowed_drones=[],
    )


def _build_client() -> TestClient:
    container = get_service_container()
    container.command_repo.clear()
    container.event_repo.clear()
    container.mission_repo.clear()
    container.drone_repo.clear()
    return TestClient(create_app())


# ---------------------------------------------------------------------------
# check_command_permission unit tests
# ---------------------------------------------------------------------------

class TestCheckCommandPermission:
    def test_observer_raises_403(self):
        with pytest.raises(HTTPException) as exc_info:
            check_command_permission(_observer(), "SIM-001")
        assert exc_info.value.status_code == 403
        assert "read-only" in exc_info.value.detail.lower()

    def test_pilot_raises_403_for_unassigned_drone(self):
        pilot = _pilot_restricted(["SIM-001", "SIM-002"])
        with pytest.raises(HTTPException) as exc_info:
            check_command_permission(pilot, "SIM-007")
        assert exc_info.value.status_code == 403
        assert "SIM-007" in exc_info.value.detail

    def test_pilot_can_command_assigned_drone(self):
        pilot = _pilot_restricted(["SIM-001", "SIM-002"])
        check_command_permission(pilot, "SIM-001")  # should not raise

    def test_pilot_unrestricted_allows_any_drone(self):
        pilot = _pilot_unrestricted()
        check_command_permission(pilot, "SIM-099")  # no restriction

    def test_admin_can_command_any_drone(self):
        check_command_permission(_admin(), "SIM-001")  # no raise
        check_command_permission(_admin(), "HW-001")   # no raise


class TestRequireAdmin:
    def test_admin_passes(self):
        require_admin(_admin())  # no raise

    def test_pilot_raises_403(self):
        with pytest.raises(HTTPException) as exc_info:
            require_admin(_pilot_unrestricted())
        assert exc_info.value.status_code == 403

    def test_observer_raises_403(self):
        with pytest.raises(HTTPException) as exc_info:
            require_admin(_observer())
        assert exc_info.value.status_code == 403


# ---------------------------------------------------------------------------
# API-level ACL tests via dependency override
# ---------------------------------------------------------------------------

class TestCommandACLviaAPI:
    """Override get_current_operator to inject different roles and verify API responses."""

    def _client_with_operator(self, operator: OperatorContext) -> TestClient:
        app = create_app()
        app.dependency_overrides[get_current_operator] = lambda: operator
        container = get_service_container()
        container.command_repo.clear()
        container.event_repo.clear()
        return TestClient(app)

    def test_observer_gets_403_on_command(self):
        client = self._client_with_operator(_observer())
        resp = client.post(
            "/api/commands",
            json={"drone_id": "SIM-001", "command": "TAKEOFF", "params": {"alt_m": 10}},
        )
        assert resp.status_code == 403

    def test_pilot_unassigned_gets_403(self):
        pilot = _pilot_restricted(["SIM-001", "SIM-002"])
        client = self._client_with_operator(pilot)
        resp = client.post(
            "/api/commands",
            json={"drone_id": "SIM-007", "command": "TAKEOFF", "params": {"alt_m": 10}},
        )
        assert resp.status_code == 403

    def test_pilot_assigned_gets_202(self):
        pilot = _pilot_restricted(["SIM-001", "SIM-002"])
        client = self._client_with_operator(pilot)
        resp = client.post(
            "/api/commands",
            json={"drone_id": "SIM-001", "command": "TAKEOFF", "params": {"alt_m": 10}},
        )
        assert resp.status_code == 202

    def test_admin_can_command_any_drone(self):
        client = self._client_with_operator(_admin())
        resp = client.post(
            "/api/commands",
            json={"drone_id": "SIM-001", "command": "TAKEOFF", "params": {"alt_m": 10}},
        )
        assert resp.status_code == 202
