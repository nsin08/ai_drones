"""WebSocket connection manager for Mission Control v4 (G8).

Manages active WebSocket connections and provides thread-safe broadcast
so synchronous background threads (e.g. the command retry loop) can push
events to all connected browser clients without deadlocking the event loop.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class WebSocketManager:
    """Manages active WebSocket client connections.

    Usage
    -----
    Async context (route handler / coroutine):
        await manager.connect(ws)
        await manager.broadcast(event_name, payload_dict)

    Sync / threaded context (retry loop, service callbacks):
        manager.broadcast_sync(event_name, payload_dict)

    Thread-safety
    -------------
    The ``_active`` list is mutated only from the asyncio event loop
    thread (inside coroutines).  ``broadcast_sync`` schedules a
    coroutine on that loop via ``run_coroutine_threadsafe`` so it is
    safe to call from any thread.
    """

    def __init__(self) -> None:
        self._active: list[WebSocket] = []
        # Captured the first time a WebSocket is accepted; used by
        # broadcast_sync to schedule coroutines from background threads.
        self._loop: asyncio.AbstractEventLoop | None = None

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    async def connect(self, ws: WebSocket) -> None:
        """Accept a new WebSocket connection and register it."""
        if self._loop is None:
            try:
                self._loop = asyncio.get_running_loop()
            except RuntimeError:
                pass
        await ws.accept()
        self._active.append(ws)
        logger.debug("WS connected; active=%d", len(self._active))

    def disconnect(self, ws: WebSocket) -> None:
        """Remove a connection (safe to call if already absent)."""
        try:
            self._active.remove(ws)
        except ValueError:
            pass
        logger.debug("WS disconnected; active=%d", len(self._active))

    # ------------------------------------------------------------------
    # Broadcast
    # ------------------------------------------------------------------

    async def broadcast(self, event: str, payload: dict[str, Any]) -> None:
        """Send a JSON message to **all** connected clients.

        The envelope is ``{"event": "<name>", ...payload}``.
        Dead connections are silently pruned.
        """
        if not self._active:
            return

        message = json.dumps({"event": event, **payload})
        dead: list[WebSocket] = []
        for ws in list(self._active):
            try:
                await ws.send_text(message)
            except Exception as exc:  # pragma: no cover
                logger.debug("WS send failed (%s); pruning", exc)
                dead.append(ws)
        for ws in dead:  # pragma: no cover
            self.disconnect(ws)

    def broadcast_sync(self, event: str, payload: dict[str, Any]) -> None:
        """Thread-safe broadcast from a **synchronous** context.

        Schedules ``broadcast()`` on the stored event loop when one is
        available.  If no loop has been captured yet (no WebSocket client
        has connected, or running in a pure-sync unit test), the call is
        silently dropped — this is intentional; there is nothing to
        broadcast to.
        """
        if not self._active or self._loop is None:
            return
        try:
            asyncio.run_coroutine_threadsafe(
                self.broadcast(event, payload), self._loop
            )
        except RuntimeError:  # pragma: no cover
            # Loop closed / not running — drop silently
            pass

    # ------------------------------------------------------------------
    # Inspection helpers (tests / monitoring)
    # ------------------------------------------------------------------

    @property
    def connection_count(self) -> int:
        """Number of currently active WebSocket connections."""
        return len(self._active)
