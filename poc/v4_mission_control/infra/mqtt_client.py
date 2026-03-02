"""MQTT client with automatic reconnect backoff — W15 G11.

Wraps ``paho-mqtt`` with an exponential-ish backoff reconnect loop that
runs on a daemon thread.  Callers register ``on_connect`` / ``on_disconnect``
callbacks; the client itself does *not* hold framework state.

Backoff schedule (seconds): ``[1, 5, 30]`` cycling indefinitely.

Usage::

    def on_up():   service_status.report_mqtt_connected()
    def on_down(): service_status.report_mqtt_disconnected()

    client = MqttReconnectClient("localhost", 1883,
                                 on_connect=on_up, on_disconnect=on_down)
    client.connect()
"""

from __future__ import annotations

import itertools
import logging
import threading
import time
from typing import Callable

import paho.mqtt.client as _paho

log = logging.getLogger(__name__)

# Default backoff schedule in seconds — cycling via itertools.cycle
DEFAULT_BACKOFF_SCHEDULE: list[float] = [1.0, 5.0, 30.0]


class MqttReconnectClient:
    """Paho MQTT wrapper with automatic reconnect backoff.

    Parameters
    ----------
    host:
        Broker hostname or IP.
    port:
        Broker port (default 1883).
    on_connect:
        Called (no args) when the connection is established or re-established.
    on_disconnect:
        Called (no args) when the connection drops.
    backoff_schedule:
        Sequence of wait times (seconds) cycled through between reconnect
        attempts.  Defaults to ``[1, 5, 30]``.
    client_id:
        Optional MQTT client ID.
    """

    def __init__(
        self,
        host: str,
        port: int = 1883,
        *,
        on_connect: Callable[[], None] | None = None,
        on_disconnect: Callable[[], None] | None = None,
        backoff_schedule: list[float] | None = None,
        client_id: str = "",
    ) -> None:
        self.host = host
        self.port = port
        self._on_connect_cb = on_connect
        self._on_disconnect_cb = on_disconnect
        self._backoff_schedule = backoff_schedule or DEFAULT_BACKOFF_SCHEDULE

        self._client = _paho.Client(
            _paho.CallbackAPIVersion.VERSION2,
            client_id=client_id,
        )
        self._client.on_connect = self._paho_on_connect
        self._client.on_disconnect = self._paho_on_disconnect

        self._connected = False
        self._running = False
        self._lock = threading.Lock()
        self._reconnect_thread: threading.Thread | None = None
        self._subscriptions: list[tuple[str, int]] = []
        self._message_cb: Callable | None = None
        self._client.on_message = self._paho_on_message

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def is_connected(self) -> bool:
        with self._lock:
            return self._connected

    def connect(self) -> None:
        """Attempt initial connection; start the reconnect loop if it fails."""
        self._running = True
        if not self._try_connect():
            self.start_reconnect_loop()

    def publish(self, topic: str, payload: str | bytes, qos: int = 0) -> None:
        if not self.is_connected:
            log.warning("MQTT publish skipped — not connected (topic=%s)", topic)
            return
        self._client.publish(topic, payload, qos=qos)

    def subscribe(self, topic: str, qos: int = 0) -> None:
        """Register a topic subscription.  Re-subscribed automatically on reconnect."""
        self._subscriptions.append((topic, qos))
        if self.is_connected:
            self._client.subscribe(topic, qos)
            log.debug("MQTT subscribed: %s", topic)

    def set_message_callback(self, cb: Callable) -> None:
        """Register a callback invoked for every received message.

        Signature: ``cb(topic: str, payload: bytes) -> None``.
        """
        self._message_cb = cb

    def start_reconnect_loop(self) -> None:
        """Spawn the background reconnect thread (idempotent)."""
        with self._lock:
            if self._reconnect_thread and self._reconnect_thread.is_alive():
                return
            t = threading.Thread(
                target=self._reconnect_loop,
                daemon=True,
                name="mqtt-reconnect",
            )
            self._reconnect_thread = t
        t.start()

    def disconnect(self) -> None:
        """Cleanly shut down the client and stop the reconnect loop."""
        self._running = False
        with self._lock:
            self._connected = False
        try:
            self._client.loop_stop()
            self._client.disconnect()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Paho callbacks
    # ------------------------------------------------------------------

    def _paho_on_connect(self, client, userdata, flags, reason_code, properties):  # noqa: ANN001
        with self._lock:
            self._connected = True
        log.info("MQTT connected (rc=%s)", reason_code)
        # Re-apply subscriptions after every (re)connect
        for topic, qos in self._subscriptions:
            client.subscribe(topic, qos)
            log.debug("MQTT re-subscribed: %s", topic)
        if self._on_connect_cb:
            try:
                self._on_connect_cb()
            except Exception:
                log.exception("on_connect callback raised")

    def _paho_on_disconnect(self, client, userdata, flags, reason_code, properties):  # noqa: ANN001
        with self._lock:
            was_connected = self._connected
            self._connected = False
        if was_connected:
            log.warning("MQTT disconnected (rc=%s) — starting reconnect loop", reason_code)
            if self._on_disconnect_cb:
                try:
                    self._on_disconnect_cb()
                except Exception:
                    log.exception("on_disconnect callback raised")
            self.start_reconnect_loop()

    # ------------------------------------------------------------------
    # Reconnect loop (runs on daemon thread)
    # ------------------------------------------------------------------

    def _paho_on_message(self, client, userdata, msg):  # noqa: ANN001
        """Dispatch incoming MQTT messages to the registered callback."""
        if self._message_cb:
            try:
                self._message_cb(msg.topic, msg.payload)
            except Exception:
                log.exception("message_cb raised for topic=%s", msg.topic)

    def _try_connect(self) -> bool:
        """Single connection attempt. Returns ``True`` on success."""
        try:
            self._client.connect(self.host, self.port)
            self._client.loop_start()
            return True
        except Exception as exc:
            log.debug("MQTT connect attempt failed: %s", exc)
            return False

    def _reconnect_loop(self) -> None:
        """Retry connection with cyclic backoff until connected or stopped."""
        for delay in itertools.cycle(self._backoff_schedule):
            if not self._running:
                return
            with self._lock:
                already = self._connected
            if already:
                return

            log.debug("MQTT reconnect attempt (backoff=%.1fs)…", delay)
            if self._try_connect():
                return  # paho on_connect will fire and update state

            with self._lock:
                self._connected = False

            time.sleep(delay)
