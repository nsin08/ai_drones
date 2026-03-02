from fastapi.testclient import TestClient

from poc.v4_mission_control.app import create_app
from poc.v4_mission_control.services.runtime import get_service_container


def _build_client() -> TestClient:
    container = get_service_container()
    container.command_repo.clear()
    container.event_repo.clear()
    return TestClient(create_app())


def test_v4_health_endpoint_boots():
    client = _build_client()
    response = client.get("/api/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["service"] == "mission-control-v4"
    assert payload["environment"] in {"SIM", "HARDWARE"}


def test_v4_arm_rejects_when_stub_preflight_is_unsafe():
    client = _build_client()
    response = client.post(
        "/api/commands",
        json={"drone_id": "HW-LOWBAT-UNCAL-001", "command": "ARM"},
    )
    assert response.status_code == 400
    payload = response.json()
    assert payload["status"] == "REJECTED"
    assert "battery below minimum threshold" in payload["rejection_reason"]
    assert "calibration required" in payload["rejection_reason"]


def test_v4_command_history_lists_recent_commands():
    client = _build_client()
    create_response = client.post(
        "/api/commands",
        json={"drone_id": "SIM-001", "command": "TAKEOFF", "params": {"alt_m": 15}},
    )
    assert create_response.status_code == 202

    history_response = client.get("/api/commands")
    assert history_response.status_code == 200
    payload = history_response.json()
    assert payload["items"]
    assert payload["items"][0]["drone_id"] == "SIM-001"
    assert payload["items"][0]["command"] == "TAKEOFF"
