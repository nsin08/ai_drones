"""API integration tests: Mission endpoints + ACK/NACK commands — W12.

Uses FastAPI TestClient with the in-memory service container
(USE_DATABASE=False, which is the default for tests).
"""

from fastapi.testclient import TestClient

from poc.v4_mission_control.app import create_app
from poc.v4_mission_control.services.runtime import get_service_container


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _build_client() -> TestClient:
    """Return a fresh TestClient with cleared in-memory state."""
    container = get_service_container()
    container.command_repo.clear()
    container.event_repo.clear()
    container.mission_repo.clear()
    return TestClient(create_app())


# ---------------------------------------------------------------------------
# Command GET / ACK / NACK
# ---------------------------------------------------------------------------


class TestCommandAckNack:
    def test_get_command_by_id(self):
        client = _build_client()
        post = client.post(
            "/api/commands",
            json={"drone_id": "SIM-001", "command": "TAKEOFF", "params": {"alt_m": 10}},
        )
        assert post.status_code == 202
        cmd_id = post.json()["cmd_id"]

        resp = client.get(f"/api/commands/{cmd_id}")
        assert resp.status_code == 200
        assert resp.json()["cmd_id"] == cmd_id

    def test_get_nonexistent_command_returns_404(self):
        client = _build_client()
        from uuid import uuid4
        resp = client.get(f"/api/commands/{uuid4()}")
        assert resp.status_code == 404

    def test_ack_command(self):
        client = _build_client()
        post = client.post(
            "/api/commands",
            json={"drone_id": "SIM-001", "command": "TAKEOFF"},
        )
        assert post.status_code == 202
        cmd_id = post.json()["cmd_id"]

        ack = client.post(f"/api/commands/{cmd_id}/ack")
        assert ack.status_code == 200
        assert ack.json()["status"] == "ACKED"

    def test_nack_command(self):
        client = _build_client()
        post = client.post(
            "/api/commands",
            json={"drone_id": "SIM-001", "command": "TAKEOFF"},
        )
        assert post.status_code == 202
        cmd_id = post.json()["cmd_id"]

        nack = client.post(f"/api/commands/{cmd_id}/nack?reason=drone+offline")
        assert nack.status_code == 200
        assert nack.json()["status"] == "FAILED"

    def test_ack_nonexistent_returns_404(self):
        client = _build_client()
        from uuid import uuid4
        resp = client.post(f"/api/commands/{uuid4()}/ack")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Mission CRUD
# ---------------------------------------------------------------------------


class TestMissionCreate:
    def test_create_mission_returns_201(self):
        client = _build_client()
        resp = client.post(
            "/api/missions",
            json={
                "type": "RECON",
                "tasks": [{"type": "WAYPOINT", "drone_ids": ["SIM-001"]}],
                "created_by": "test",
            },
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["status"] == "PLANNING"
        assert body["type"] == "RECON"
        assert len(body["tasks"]) == 1

    def test_create_mission_gives_unique_ids(self):
        client = _build_client()
        r1 = client.post("/api/missions", json={"type": "A", "tasks": []})
        r2 = client.post("/api/missions", json={"type": "B", "tasks": []})
        assert r1.json()["mission_id"] != r2.json()["mission_id"]

    def test_get_mission(self):
        client = _build_client()
        post = client.post("/api/missions", json={"type": "RECON", "tasks": []})
        mid = post.json()["mission_id"]

        resp = client.get(f"/api/missions/{mid}")
        assert resp.status_code == 200
        assert resp.json()["mission_id"] == mid

    def test_get_nonexistent_mission_returns_404(self):
        client = _build_client()
        resp = client.get("/api/missions/no-such-id")
        assert resp.status_code == 404

    def test_list_missions(self):
        client = _build_client()
        client.post("/api/missions", json={"type": "RECON", "tasks": []})
        client.post("/api/missions", json={"type": "PATROL", "tasks": []})

        resp = client.get("/api/missions")
        assert resp.status_code == 200
        assert resp.json()["total"] == 2

    def test_list_missions_filtered_by_status(self):
        client = _build_client()
        post = client.post("/api/missions", json={"type": "RECON", "tasks": []})
        mid = post.json()["mission_id"]
        client.post(f"/api/missions/{mid}/plan")
        client.post(f"/api/missions/{mid}/start")  # → ACTIVE

        client.post("/api/missions", json={"type": "PATROL", "tasks": []})  # stays PLANNING

        resp = client.get("/api/missions?status=ACTIVE")
        body = resp.json()
        assert body["total"] == 1
        assert body["items"][0]["status"] == "ACTIVE"


# ---------------------------------------------------------------------------
# Mission FSM via API
# ---------------------------------------------------------------------------


class TestMissionFsmApi:
    def _create(self, client: TestClient) -> str:
        resp = client.post("/api/missions", json={"type": "RECON", "tasks": []})
        assert resp.status_code == 201
        return resp.json()["mission_id"]

    def test_plan_mission(self):
        client = _build_client()
        mid = self._create(client)
        resp = client.post(f"/api/missions/{mid}/plan")
        assert resp.status_code == 200
        assert resp.json()["status"] == "PLANNED"

    def test_start_mission(self):
        client = _build_client()
        mid = self._create(client)
        client.post(f"/api/missions/{mid}/plan")
        resp = client.post(f"/api/missions/{mid}/start")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ACTIVE"

    def test_pause_and_resume_mission(self):
        client = _build_client()
        mid = self._create(client)
        client.post(f"/api/missions/{mid}/plan")
        client.post(f"/api/missions/{mid}/start")
        pause = client.post(f"/api/missions/{mid}/pause")
        assert pause.json()["status"] == "PAUSED"
        resume = client.post(f"/api/missions/{mid}/resume")
        assert resume.json()["status"] == "ACTIVE"

    def test_complete_mission(self):
        client = _build_client()
        mid = self._create(client)
        client.post(f"/api/missions/{mid}/plan")
        client.post(f"/api/missions/{mid}/start")
        resp = client.post(f"/api/missions/{mid}/complete")
        assert resp.json()["status"] == "COMPLETED"

    def test_abort_mission(self):
        client = _build_client()
        mid = self._create(client)
        resp = client.post(f"/api/missions/{mid}/abort", json={"reason": "operator request"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "ABORTED"

    def test_invalid_transition_returns_400(self):
        """PLANNING → ACTIVE should return 400 (must go PLANNING → PLANNED first)."""
        client = _build_client()
        mid = self._create(client)
        resp = client.post(f"/api/missions/{mid}/start")
        assert resp.status_code == 400

    def test_cannot_abort_completed_mission(self):
        client = _build_client()
        mid = self._create(client)
        client.post(f"/api/missions/{mid}/plan")
        client.post(f"/api/missions/{mid}/start")
        client.post(f"/api/missions/{mid}/complete")
        resp = client.post(f"/api/missions/{mid}/abort")
        assert resp.status_code == 400
