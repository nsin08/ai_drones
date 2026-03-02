"""Unit tests: WebSocketManager — W13 G8.

Tests the WebSocket manager's connection lifecycle and broadcast logic
without a running ASGI server.  Async broadcast() is tested via asyncio.run().
"""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from poc.v4_mission_control.ws.manager import WebSocketManager


# ---------------------------------------------------------------------------
# Connection counting
# ---------------------------------------------------------------------------


class TestConnectionManagement:
    def test_initial_connection_count_is_zero(self):
        manager = WebSocketManager()
        assert manager.connection_count == 0

    def test_connect_increments_count(self):
        manager = WebSocketManager()
        mock_ws = AsyncMock()
        asyncio.run(manager.connect(mock_ws))
        assert manager.connection_count == 1

    def test_disconnect_decrements_count(self):
        manager = WebSocketManager()
        mock_ws = AsyncMock()
        asyncio.run(manager.connect(mock_ws))
        manager.disconnect(mock_ws)
        assert manager.connection_count == 0

    def test_disconnect_missing_connection_is_safe(self):
        """Calling disconnect on an unregistered WebSocket must not raise."""
        manager = WebSocketManager()
        mock_ws = MagicMock()
        manager.disconnect(mock_ws)  # should not raise

    def test_multiple_connections_tracked(self):
        manager = WebSocketManager()
        ws1, ws2, ws3 = AsyncMock(), AsyncMock(), AsyncMock()
        asyncio.run(manager.connect(ws1))
        asyncio.run(manager.connect(ws2))
        asyncio.run(manager.connect(ws3))
        assert manager.connection_count == 3
        manager.disconnect(ws2)
        assert manager.connection_count == 2


# ---------------------------------------------------------------------------
# broadcast() — async
# ---------------------------------------------------------------------------


class TestBroadcast:
    def test_broadcast_no_connections_is_safe(self):
        manager = WebSocketManager()
        # Must not raise when there are no listeners
        asyncio.run(manager.broadcast("test_event", {"value": 42}))

    def test_broadcast_sends_correct_json_envelope(self):
        manager = WebSocketManager()
        mock_ws = AsyncMock()
        mock_ws.send_text = AsyncMock()

        async def _run():
            await manager.connect(mock_ws)
            await manager.broadcast("command_status", {"cmd_id": "abc-123", "status": "ACKED"})

        asyncio.run(_run())

        mock_ws.send_text.assert_called_once()
        raw = mock_ws.send_text.call_args[0][0]
        data = json.loads(raw)
        assert data["event"] == "command_status"
        assert data["cmd_id"] == "abc-123"
        assert data["status"] == "ACKED"

    def test_broadcast_delivers_to_all_connections(self):
        manager = WebSocketManager()
        ws1, ws2 = AsyncMock(), AsyncMock()
        ws1.send_text = AsyncMock()
        ws2.send_text = AsyncMock()

        async def _run():
            await manager.connect(ws1)
            await manager.connect(ws2)
            await manager.broadcast("drone_health", {"drone_id": "SIM-001", "label": "GREEN"})

        asyncio.run(_run())
        ws1.send_text.assert_called_once()
        ws2.send_text.assert_called_once()

    def test_broadcast_prunes_dead_connections(self):
        """A connection that raises on send_text is removed from the list."""
        manager = WebSocketManager()
        dead_ws = AsyncMock()
        dead_ws.send_text = AsyncMock(side_effect=RuntimeError("disconnected"))
        good_ws = AsyncMock()
        good_ws.send_text = AsyncMock()

        async def _run():
            await manager.connect(dead_ws)
            await manager.connect(good_ws)
            await manager.broadcast("fleet_telemetry", {"data": "x"})

        asyncio.run(_run())
        assert manager.connection_count == 1
        good_ws.send_text.assert_called_once()


# ---------------------------------------------------------------------------
# broadcast_sync() — thread-safe / no event loop
# ---------------------------------------------------------------------------


class TestBroadcastSync:
    def test_broadcast_sync_no_loop_no_connections_is_safe(self):
        """No loop captured, no connections: broadcast_sync must be silent."""
        manager = WebSocketManager()
        manager.broadcast_sync("test_event", {"x": 1})  # should not raise

    def test_broadcast_sync_no_connections_is_safe_even_with_loop(self):
        """Loop captured but no connections: still a no-op."""
        manager = WebSocketManager()

        async def _capture_loop():
            # Inject fake loop into manager without a real WS
            manager._loop = asyncio.get_running_loop()

        asyncio.run(_capture_loop())
        manager.broadcast_sync("test_event", {"x": 1})  # should not raise

    def test_broadcast_sync_schedules_on_loop(self):
        """When a loop and connections exist, broadcast_sync schedules the coro."""
        manager = WebSocketManager()
        mock_ws = AsyncMock()
        mock_ws.send_text = AsyncMock()

        async def _setup():
            await manager.connect(mock_ws)  # also captures the loop

        asyncio.run(_setup())

        # Now simulate a call from a background thread:
        # run_coroutine_threadsafe returns a concurrent.futures.Future.
        with patch.object(asyncio, "run_coroutine_threadsafe") as mock_rctf:
            manager.broadcast_sync("command_status", {"status": "ACKED"})
            mock_rctf.assert_called_once()
            event_arg = mock_rctf.call_args[0][1]
            assert event_arg is manager._loop
            # Close the unawaited coroutine to suppress RuntimeWarning in GC
            mock_rctf.call_args[0][0].close()
