"""API/integration tests: command status WebSocket events — W13 G8.

Verifies that each command state transition (REQUESTED, REJECTED, ACKED,
NACKED) calls ws_manager.broadcast_sync() with the correct COMMAND_STATUS_EVENT
payload.  The shared runtime ws_manager is patched in-process, so no real
WebSocket connection is required.

Also verifies the /ws endpoint is accessible via TestClient.
"""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from poc.v4_mission_control.app import create_app
from poc.v4_mission_control.schemas.socket_events import COMMAND_STATUS_EVENT
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


# ---------------------------------------------------------------------------
# /ws endpoint connectivity
# ---------------------------------------------------------------------------


class TestWebSocketEndpoint:
    def test_ws_endpoint_accepts_connection(self):
        """/ws should accept a WebSocket connection and stay alive."""
        client = _build_client()
        with client.websocket_connect("/ws") as ws:
            # Connection accepted; just verify we can reach this point
            # The server won't push anything until an event fires.
            pass  # clean disconnect on context exit


# ---------------------------------------------------------------------------
# Command state transitions trigger broadcast_sync
# ---------------------------------------------------------------------------


class TestCommandStatusBroadcast:
    def test_accepted_command_broadcasts_command_status(self):
        """POST /api/commands → accepted path emits a WS broadcast."""
        client = _build_client()
        container = get_service_container()

        with patch.object(container.ws_manager, "broadcast_sync") as mock_bcast:
            resp = client.post(
                "/api/commands",
                json={"drone_id": "SIM-001", "command": "TAKEOFF", "params": {"alt_m": 10}},
            )
            assert resp.status_code == 202

        mock_bcast.assert_called()
        event_name, payload = mock_bcast.call_args[0]
        assert event_name == COMMAND_STATUS_EVENT
        assert payload["drone_id"] == "SIM-001"
        assert "status" in payload
        assert "cmd_id" in payload

    def test_rejected_command_broadcasts_command_status(self):
        """ARM with low battery → REJECTED state must still broadcast."""
        client = _build_client()
        container = get_service_container()

        with patch.object(container.ws_manager, "broadcast_sync") as mock_bcast:
            resp = client.post(
                "/api/commands",
                json={"drone_id": "HW-LOWBAT-UNCAL-001", "command": "ARM"},
            )
            assert resp.status_code == 400  # rejected

        mock_bcast.assert_called()
        event_name, payload = mock_bcast.call_args[0]
        assert event_name == COMMAND_STATUS_EVENT
        assert payload["status"] == "REJECTED"

    def test_ack_command_broadcasts_acked_status(self):
        """POST /api/commands/{id}/ack broadcasts ACKED status."""
        client = _build_client()
        container = get_service_container()

        # Submit first (no retry thread so test is fast)
        with patch.object(container.ws_manager, "broadcast_sync"):
            post = client.post(
                "/api/commands",
                json={"drone_id": "SIM-001", "command": "TAKEOFF"},
            )
        cmd_id = post.json()["cmd_id"]

        with patch.object(container.ws_manager, "broadcast_sync") as mock_bcast:
            ack = client.post(f"/api/commands/{cmd_id}/ack")
            assert ack.status_code == 200

        mock_bcast.assert_called()
        event_name, payload = mock_bcast.call_args[0]
        assert event_name == COMMAND_STATUS_EVENT
        assert payload["status"] == "ACKED"
        assert payload["cmd_id"] == cmd_id

    def test_nack_command_broadcasts_failed_status(self):
        """POST /api/commands/{id}/nack broadcasts FAILED status."""
        client = _build_client()
        container = get_service_container()

        with patch.object(container.ws_manager, "broadcast_sync"):
            post = client.post(
                "/api/commands",
                json={"drone_id": "SIM-001", "command": "LAND"},
            )
        cmd_id = post.json()["cmd_id"]

        with patch.object(container.ws_manager, "broadcast_sync") as mock_bcast:
            nack = client.post(f"/api/commands/{cmd_id}/nack?reason=test-nack")
            assert nack.status_code == 200

        mock_bcast.assert_called()
        event_name, payload = mock_bcast.call_args[0]
        assert event_name == COMMAND_STATUS_EVENT
        assert payload["status"] == "FAILED"
