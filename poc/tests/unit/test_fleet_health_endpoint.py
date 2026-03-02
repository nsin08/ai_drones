"""API tests: GET /api/fleet/health + GET /api/drones/{id}/health — W13 G7.

Uses the in-memory service container (USE_DATABASE=False) with test drones
inserted via drone_repo.upsert().
"""

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from poc.v4_mission_control.app import create_app
from poc.v4_mission_control.services.runtime import get_service_container


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _build_client() -> TestClient:
    """Return a TestClient with a clean in-memory state."""
    container = get_service_container()
    container.command_repo.clear()
    container.event_repo.clear()
    container.mission_repo.clear()
    container.drone_repo.clear()
    return TestClient(create_app())


def _insert_drone(
    drone_id: str,
    *,
    battery_pct: float = 100.0,
    gps_sats: int = 8,
    ekf_ok: bool = True,
    seconds_ago: float = 0.0,
) -> None:
    """Insert a drone directly into the shared drone_repo."""
    container = get_service_container()
    container.drone_repo.upsert(
        drone_id=drone_id,
        last_seen_at=_now() - timedelta(seconds=seconds_ago),
        last_telemetry_json={
            "battery_pct": battery_pct,
            "gps_sats": gps_sats,
            "ekf_ok": ekf_ok,
        },
    )


# ---------------------------------------------------------------------------
# Fleet health summary
# ---------------------------------------------------------------------------


class TestFleetHealthEndpoint:
    def test_empty_fleet_returns_all_zeros(self):
        client = _build_client()
        resp = client.get("/api/fleet/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["healthy"] == 0
        assert data["warning"] == 0
        assert data["critical"] == 0
        assert data["offline"] == 0
        assert data["details"] == []

    def test_one_green_drone(self):
        client = _build_client()
        _insert_drone("SIM-001", battery_pct=100.0, gps_sats=8, ekf_ok=True)
        resp = client.get("/api/fleet/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["healthy"] == 1
        assert data["warning"] == 0
        assert data["critical"] == 0
        assert data["offline"] == 0

    def test_mixed_fleet_counts(self):
        """Insert drones in GREEN, YELLOW, RED and OFFLINE states."""
        client = _build_client()
        # GREEN: battery high, GPS full, EKF ok, fresh
        _insert_drone("SIM-GREEN", battery_pct=100.0, gps_sats=8, ekf_ok=True)
        # YELLOW: ~50% battery, GPS full, EKF ok
        _insert_drone("SIM-YELLOW", battery_pct=50.0, gps_sats=8, ekf_ok=True)
        # RED: very low battery → score < 0.3
        _insert_drone("SIM-RED", battery_pct=10.0, gps_sats=8, ekf_ok=True)
        # OFFLINE: not seen within stale window
        _insert_drone("SIM-OFFLINE", battery_pct=100.0, gps_sats=8, ekf_ok=True, seconds_ago=120)

        resp = client.get("/api/fleet/health")
        assert resp.status_code == 200
        data = resp.json()

        assert data["healthy"] == 1
        assert data["warning"] == 1
        assert data["critical"] == 1
        assert data["offline"] == 1
        assert len(data["details"]) == 4

    def test_details_contain_drone_ids(self):
        client = _build_client()
        _insert_drone("SIM-A")
        _insert_drone("SIM-B")
        resp = client.get("/api/fleet/health")
        assert resp.status_code == 200
        ids = {d["drone_id"] for d in resp.json()["details"]}
        assert "SIM-A" in ids
        assert "SIM-B" in ids


# ---------------------------------------------------------------------------
# Per-drone health endpoint
# ---------------------------------------------------------------------------


class TestDroneHealthEndpoint:
    def test_drone_health_returns_score_and_label(self):
        client = _build_client()
        _insert_drone("SIM-001", battery_pct=100.0, gps_sats=8, ekf_ok=True)
        resp = client.get("/api/drones/SIM-001/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["drone_id"] == "SIM-001"
        assert "score" in data
        assert data["label"] in {"GREEN", "YELLOW", "RED", "OFFLINE"}

    def test_drone_health_low_battery_label_red(self):
        """A drone with battery_pct < 10 must score < 0.3 → RED."""
        client = _build_client()
        _insert_drone("SIM-LOWBAT", battery_pct=5.0, gps_sats=8, ekf_ok=True)
        resp = client.get("/api/drones/SIM-LOWBAT/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["score"] < 0.3
        assert data["label"] == "RED"

    def test_drone_health_unknown_drone_returns_404(self):
        client = _build_client()
        resp = client.get("/api/drones/UNKNOWN-XYZ/health")
        assert resp.status_code == 404

    def test_drone_health_response_schema(self):
        """Verify the response contains all expected schema fields."""
        client = _build_client()
        _insert_drone("SIM-SCHEMA")
        resp = client.get("/api/drones/SIM-SCHEMA/health")
        assert resp.status_code == 200
        data = resp.json()
        for key in ("drone_id", "score", "label", "battery_pct", "gps_sats", "ekf_ok"):
            assert key in data, f"Missing field: {key}"
