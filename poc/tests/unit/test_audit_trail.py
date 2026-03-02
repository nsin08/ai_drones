"""Unit + API tests: Audit trail — requested_by is stamped from the operator (W14).

Coverage:
  - AUTH_ENABLED=False (default): requested_by=None in payload → stored as "anonymous"
  - AUTH_ENABLED=False: explicit requested_by in payload → kept as-is
  - Dependency override: injected operator username propagates to stored record
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from poc.v4_mission_control.app import create_app
from poc.v4_mission_control.auth.dependencies import get_current_operator
from poc.v4_mission_control.auth.operator_store import OperatorContext
from poc.v4_mission_control.services.runtime import get_service_container


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_client() -> TestClient:
    container = get_service_container()
    container.command_repo.clear()
    container.event_repo.clear()
    container.mission_repo.clear()
    container.drone_repo.clear()
    return TestClient(create_app())


def _build_client_with_operator(operator: OperatorContext) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_current_operator] = lambda: operator
    container = get_service_container()
    container.command_repo.clear()
    container.event_repo.clear()
    return TestClient(app)


def _admin_operator() -> OperatorContext:
    return OperatorContext(
        operator_id="op-admin-001",
        username="admin",
        role="ADMIN",
        allowed_drones=[],
    )


def _pilot_operator() -> OperatorContext:
    return OperatorContext(
        operator_id="op-pilot-001",
        username="pilot1",
        role="PILOT",
        allowed_drones=[],  # no restriction for this test
    )


def _post_command(client: TestClient, *, drone_id: str = "SIM-001", requested_by: str | None = None) -> dict:
    payload: dict = {"drone_id": drone_id, "command": "TAKEOFF", "params": {"alt_m": 10}}
    if requested_by is not None:
        payload["requested_by"] = requested_by
    resp = client.post("/api/commands", json=payload)
    assert resp.status_code == 202, f"Unexpected {resp.status_code}: {resp.text}"
    return resp.json()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestAuditTrailAnonymous:
    """AUTH_ENABLED=False (default) — operator is ANONYMOUS_ADMIN."""

    def test_no_requested_by_defaults_to_anonymous(self):
        client = _build_client()
        body = _post_command(client)
        cmd_id = body["cmd_id"]
        detail = client.get(f"/api/commands/{cmd_id}").json()
        assert detail["requested_by"] == "anonymous"

    def test_explicit_requested_by_kept_when_anonymous(self):
        """When ANONYMOUS_ADMIN sends the request, explicit requested_by is preserved."""
        client = _build_client()
        body = _post_command(client, requested_by="legacy-system")
        cmd_id = body["cmd_id"]
        detail = client.get(f"/api/commands/{cmd_id}").json()
        assert detail["requested_by"] == "legacy-system"


class TestAuditTrailAuthenticatedOperator:
    """Operator injected via dependency_overrides → username stamps requested_by."""

    def test_admin_operator_stamps_username(self):
        client = _build_client_with_operator(_admin_operator())
        body = _post_command(client)
        cmd_id = body["cmd_id"]
        detail = client.get(f"/api/commands/{cmd_id}").json()
        assert detail["requested_by"] == "admin"

    def test_pilot_operator_stamps_username(self):
        client = _build_client_with_operator(_pilot_operator())
        body = _post_command(client)
        cmd_id = body["cmd_id"]
        detail = client.get(f"/api/commands/{cmd_id}").json()
        assert detail["requested_by"] == "pilot1"

    def test_authenticated_operator_overrides_payload_requested_by(self):
        """When a real operator (non-anonymous) sends a command, their username always wins."""
        client = _build_client_with_operator(_admin_operator())
        body = _post_command(client, requested_by="some-old-value")
        cmd_id = body["cmd_id"]
        detail = client.get(f"/api/commands/{cmd_id}").json()
        # Real operator's username overrides any value in the payload
        assert detail["requested_by"] == "admin"

    def test_multiple_commands_each_stamped(self):
        client = _build_client_with_operator(_pilot_operator())
        ids = [_post_command(client, drone_id="SIM-001")["cmd_id"] for _ in range(3)]
        for cmd_id in ids:
            detail = client.get(f"/api/commands/{cmd_id}").json()
            assert detail["requested_by"] == "pilot1"
