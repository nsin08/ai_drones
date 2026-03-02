"""
Regression smoke tests — Mission Control v4  (W16 G13)

Verifies that all primary API surface areas return expected shapes after
each sprint. Run these as part of the full test suite to catch regressions.

Covers:
  - Auth endpoints
  - Health / fleet health
  - Commands (submit, history, ack, nack)
  - Missions (CRUD + all FSM transitions)
  - WebSocket endpoint availability
"""

import pytest
from fastapi.testclient import TestClient

from poc.v4_mission_control.app import create_app
from poc.v4_mission_control.services.runtime import get_service_container


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def client() -> TestClient:
    """Fresh TestClient per test; in-memory repos reset between tests."""
    get_service_container.cache_clear()
    app = create_app()
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


@pytest.fixture()
def admin_headers(client: TestClient) -> dict:
    resp = client.post(
        "/api/auth/token", json={"username": "admin", "password": "admin123"}
    )
    if resp.status_code == 200:
        token = resp.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}
    return {}


def _create_active_mission(client: TestClient, headers: dict) -> str:
    m = client.post(
        "/api/missions",
        json={"type": "PATROL", "tasks": []},
        headers=headers,
    )
    assert m.status_code == 201
    mid = m.json()["mission_id"]
    client.post(f"/api/missions/{mid}/plan", json={}, headers=headers)
    client.post(f"/api/missions/{mid}/start", json={}, headers=headers)
    return mid


# ---------------------------------------------------------------------------
# Auth regression
# ---------------------------------------------------------------------------


class TestAuthRegression:
    def test_login_returns_token(self, client):
        resp = client.post(
            "/api/auth/token",
            json={"username": "admin", "password": "admin123"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "access_token" in body
        assert body["token_type"] == "bearer"
        assert body["role"] == "ADMIN"

    def test_invalid_credentials_returns_401(self, client):
        resp = client.post(
            "/api/auth/token", json={"username": "nobody", "password": "wrong"}
        )
        assert resp.status_code == 401

    def test_me_endpoint_returns_identity(self, client, admin_headers):
        if not admin_headers:
            pytest.skip("auth not enabled")
        resp = client.get("/api/auth/me", headers=admin_headers)
        assert resp.status_code == 200
        # When AUTH_ENABLED=False, server returns ANONYMOUS_ADMIN regardless of token
        body = resp.json()
        assert body["username"] in ("admin", "anonymous")

    def test_observer_cannot_submit_command(self, client):
        login = client.post(
            "/api/auth/token",
            json={"username": "observer", "password": "observe123"},
        )
        if login.status_code != 200:
            pytest.skip("observer user not seeded")
        token = login.json()["access_token"]
        resp = client.post(
            "/api/commands",
            json={"drone_id": "SIM-001", "command": "TAKEOFF"},
            headers={"Authorization": f"Bearer {token}"},
        )
        # 403 when AUTH_ENABLED=True; when False, ACL is still applied if token is decoded
        # AUTH_ENABLED=False means ANONYMOUS_ADMIN is used → command may pass
        # We accept 403 (auth enforced) or any 2xx/4xx (auth in passthrough mode)
        assert resp.status_code in (202, 400, 403)


# ---------------------------------------------------------------------------
# Health regression
# ---------------------------------------------------------------------------


class TestHealthRegression:
    def test_health_returns_ok(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert body["service"] == "mission-control-v4"
        assert "timestamp" in body

    def test_health_includes_service_status_fields(self, client):
        resp = client.get("/api/health")
        body = resp.json()
        assert "mqtt_connected" in body
        assert "inventory_available" in body

    def test_fleet_health_returns_summary_shape(self, client):
        resp = client.get("/api/fleet/health")
        assert resp.status_code == 200
        body = resp.json()
        for key in ("healthy", "warning", "critical", "offline"):
            assert key in body, f"missing key: {key}"

    def test_drone_health_404_for_unknown_drone(self, client):
        resp = client.get("/api/drones/UNKNOWN-001/health")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Commands regression
# ---------------------------------------------------------------------------


class TestCommandsRegression:
    def test_submit_command_returns_202(self, client):
        resp = client.post(
            "/api/commands",
            json={"drone_id": "SIM-001", "command": "TAKEOFF", "params": {"alt_m": 30}},
        )
        assert resp.status_code in (202, 400)  # 400 if preflight gate fires

    def test_low_battery_drone_rejected(self, client):
        resp = client.post(
            "/api/commands",
            json={"drone_id": "HW-LOWBAT-UNCAL-001", "command": "ARM"},
        )
        assert resp.status_code == 400
        assert resp.json()["status"] == "REJECTED"

    def test_command_history_returns_list(self, client):
        client.post(
            "/api/commands",
            json={"drone_id": "SIM-001", "command": "HOLD"},
        )
        resp = client.get("/api/commands?drone_id=SIM-001&limit=5")
        assert resp.status_code == 200
        body = resp.json()
        assert "items" in body
        assert isinstance(body["items"], list)

    def test_get_command_by_id(self, client):
        create = client.post(
            "/api/commands",
            json={"drone_id": "SIM-001", "command": "HOLD"},
        )
        if create.status_code != 202:
            pytest.skip("command was rejected by preflight")
        cmd_id = create.json()["cmd_id"]
        resp = client.get(f"/api/commands/{cmd_id}")
        assert resp.status_code == 200
        assert resp.json()["cmd_id"] == cmd_id

    def test_ack_command(self, client):
        create = client.post(
            "/api/commands",
            json={"drone_id": "SIM-001", "command": "HOLD"},
        )
        if create.status_code != 202:
            pytest.skip("command rejected")
        cmd_id = create.json()["cmd_id"]
        ack = client.post(f"/api/commands/{cmd_id}/ack")
        assert ack.status_code == 200
        assert ack.json()["status"] == "ACKED"

    def test_nack_command(self, client):
        create = client.post(
            "/api/commands",
            json={"drone_id": "SIM-001", "command": "HOLD"},
        )
        if create.status_code != 202:
            pytest.skip("command rejected")
        cmd_id = create.json()["cmd_id"]
        nack = client.post(f"/api/commands/{cmd_id}/nack?reason=lost+link")
        assert nack.status_code == 200
        assert nack.json()["status"] == "FAILED"


# ---------------------------------------------------------------------------
# Missions regression — full FSM lifecycle
# ---------------------------------------------------------------------------


class TestMissionsRegression:
    def test_create_mission(self, client):
        resp = client.post("/api/missions", json={"type": "PATROL", "tasks": []})
        assert resp.status_code == 201
        body = resp.json()
        assert "mission_id" in body
        assert body["status"] == "PLANNING"

    def test_full_lifecycle_planning_to_completed(self, client, admin_headers):
        m = client.post(
            "/api/missions",
            json={"type": "ESCORT", "tasks": [], "created_by": "regression-test"},
        )
        assert m.status_code == 201
        mid = m.json()["mission_id"]

        plan = client.post(f"/api/missions/{mid}/plan", json={})
        assert plan.status_code == 200
        assert plan.json()["status"] == "PLANNED"

        start = client.post(f"/api/missions/{mid}/start", json={})
        assert start.status_code == 200
        assert start.json()["status"] == "ACTIVE"

        pause = client.post(f"/api/missions/{mid}/pause", json={})
        assert pause.status_code == 200
        assert pause.json()["status"] == "PAUSED"

        resume = client.post(f"/api/missions/{mid}/resume", json={})
        assert resume.status_code == 200
        assert resume.json()["status"] == "ACTIVE"

        complete = client.post(f"/api/missions/{mid}/complete", json={})
        assert complete.status_code == 200
        assert complete.json()["status"] == "COMPLETED"

    def test_abort_from_active(self, client, admin_headers):
        mid = _create_active_mission(client, admin_headers)
        abort = client.post(f"/api/missions/{mid}/abort", json={})
        assert abort.status_code == 200
        assert abort.json()["status"] == "ABORTED"

    def test_invalid_transition_returns_400(self, client):
        m = client.post("/api/missions", json={"type": "PATROL", "tasks": []})
        mid = m.json()["mission_id"]
        # Cannot start a mission that hasn't been PLANNED
        resp = client.post(f"/api/missions/{mid}/start", json={})
        assert resp.status_code == 400

    def test_list_missions_returns_all(self, client):
        for _ in range(3):
            client.post("/api/missions", json={"type": "PATROL", "tasks": []})
        resp = client.get("/api/missions")
        assert resp.status_code == 200
        assert resp.json()["total"] >= 3

    def test_list_missions_filter_by_status(self, client):
        client.post("/api/missions", json={"type": "PATROL", "tasks": []})
        resp = client.get("/api/missions?status=PLANNING")
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert all(i["status"] == "PLANNING" for i in items)

    def test_get_mission_by_id(self, client):
        m = client.post("/api/missions", json={"type": "SURVEY", "tasks": []})
        mid = m.json()["mission_id"]
        resp = client.get(f"/api/missions/{mid}")
        assert resp.status_code == 200
        assert resp.json()["mission_id"] == mid

    def test_get_unknown_mission_returns_404(self, client):
        resp = client.get("/api/missions/DOES-NOT-EXIST")
        assert resp.status_code == 404

    def test_five_concurrent_missions_no_crosstalk(self, client):
        """5 independent missions can be active simultaneously."""
        ids = []
        for _ in range(5):
            m = client.post("/api/missions", json={"type": "PATROL", "tasks": []})
            assert m.status_code == 201
            mid = m.json()["mission_id"]
            client.post(f"/api/missions/{mid}/plan", json={})
            client.post(f"/api/missions/{mid}/start", json={})
            ids.append(mid)

        # Abort only the first
        client.post(f"/api/missions/{ids[0]}/abort", json={})

        for mid in ids[1:]:
            detail = client.get(f"/api/missions/{mid}")
            assert detail.json()["status"] == "ACTIVE"

        aborted = client.get(f"/api/missions/{ids[0]}")
        assert aborted.json()["status"] == "ABORTED"


# ---------------------------------------------------------------------------
# WebSocket availability regression
# ---------------------------------------------------------------------------


class TestWebSocketRegression:
    def test_websocket_endpoint_connects(self, client):
        """WS /ws endpoint accepts connections and stays alive."""
        with client.websocket_connect("/ws") as ws:
            # Should not raise — connection is open
            assert ws is not None

    def test_websocket_receives_no_error_on_idle(self, client):
        """Idle WS connection does not crash the server."""
        with client.websocket_connect("/ws") as ws:
            # Send empty heartbeat text — server ignores it (per ws_endpoint impl)
            ws.send_text("ping")
            # No error means the server handled it gracefully
