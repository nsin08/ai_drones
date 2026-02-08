import os
import importlib

import pytest


@pytest.fixture(scope="module")
def mc():
    os.environ["DISABLE_MQTT"] = "1"
    import poc.mission_control_v3 as module
    module = importlib.reload(module)
    module.mqtt_client.publish = lambda *args, **kwargs: None
    return module


@pytest.fixture(autouse=True)
def _clear_state(mc):
    mc.drone_states.clear()
    mc.drone_last_seen.clear()
    mc.mission_assignments.clear()
    mc.commands.clear()
    mc.events.clear()
    mc.mission_state = "IDLE"
    mc.mission_id = None
    mc.mission_type = None
    mc.mission_plan.clear()
    mc.mission_config.clear()


def test_normalize_item_maps_fields(mc):
    item = {
        "drone_id": "SIM-001",
        "battery": 77.5,
        "position": {"lat": 1.23, "lon": 4.56, "alt_m": 12.0},
        "status": "ACTIVE",
        "mode": "AUTO",
    }
    out = mc._normalize_item("SIM-001", item, last_seen=100.0, stale=False, source="SWARMSIM")
    assert out["battery_pct"] == 77.5
    assert out["position"]["lat"] == 1.23
    assert out["position"]["lon"] == 4.56
    assert out["position"]["alt_m"] == 12.0
    assert out["latitude"] == 1.23
    assert out["source"] == "SWARMSIM"


def test_inventory_endpoint_returns_items(mc):
    mc.drone_states["SIM-001"] = {
        "drone_id": "SIM-001",
        "latitude": 10.0,
        "longitude": 20.0,
        "altitude_m": 30.0,
        "battery_pct": 90.0,
        "mode": "AUTO",
        "status": "ACTIVE",
    }
    mc.drone_last_seen["SIM-001"] = 100.0
    client = mc.app.test_client()
    resp = client.get("/api/inventory")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "items" in data
    assert any(d["drone_id"] == "SIM-001" for d in data["items"])


def test_bulk_command_creates_group(mc):
    client = mc.app.test_client()
    resp = client.post("/api/command/bulk/hold", json={"drone_ids": ["SIM-001", "SIM-002"]})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["requested"] == 2
    assert "cmd_group_id" in data


def test_state_snapshot_includes_items(mc):
    mc.drone_states["SIM-001"] = {"drone_id": "SIM-001", "latitude": 1.0, "longitude": 2.0}
    mc.drone_last_seen["SIM-001"] = 100.0
    client = mc.app.test_client()
    resp = client.get("/api/state/snapshot")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "items" in data
    assert any(d["drone_id"] == "SIM-001" for d in data["items"])


def test_home_base_endpoint(mc):
    client = mc.app.test_client()
    resp = client.get("/api/home_base")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "lat" in data and "lon" in data

    resp2 = client.post("/api/home_base", json={"lat": 1.1, "lon": 2.2, "alt_m": 3, "reset": True})
    assert resp2.status_code == 200
    data2 = resp2.get_json()
    assert data2["lat"] == 1.1
    assert data2["lon"] == 2.2
