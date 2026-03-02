"""Drone health scoring engine for Mission Control v4 (G7 — Sprint W13).

Formula (from plan S4-005):

    battery_score  = battery_pct / 100.0
    gps_score      = min(gps_sats / 8.0, 1.0)
    ekf_score      = 1.0 if ekf_ok else 0.0
    signal_score   = max(0.0, 1.0 - (seconds_since_last_seen / STALE_TIMEOUT_SEC))
    score          = min(battery_score, gps_score, ekf_score, signal_score)

Labels:
    OFFLINE  if seconds_since_last_seen > STALE_TIMEOUT_SEC
    GREEN    if score >= 0.7
    YELLOW   if 0.3 <= score < 0.7
    RED      if score < 0.3
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from ..config import Settings
from ..schemas.health import DroneHealthResult, FleetHealthSummary
from ..schemas.socket_events import DRONE_HEALTH_EVENT

if TYPE_CHECKING:
    from ..repos.drone_repo import DroneRepository, InMemoryDroneRepository
    from ..ws.manager import WebSocketManager

logger = logging.getLogger(__name__)

# -------------------------------------------------------------------------
# Scoring constants
# -------------------------------------------------------------------------

_GPS_FULL_SATS: int = 8
_GREEN_THRESHOLD: float = 0.7
_YELLOW_THRESHOLD: float = 0.3


class HealthService:
    """Compute and persist drone health scores, and broadcast via WebSocket.

    Works with both :class:`~poc.v4_mission_control.repos.drone_repo.DroneRepository`
    (SQL) and
    :class:`~poc.v4_mission_control.repos.drone_repo.InMemoryDroneRepository`
    (tests) — they share the same public interface.
    """

    def __init__(
        self,
        *,
        settings: Settings,
        drone_repo: DroneRepository | InMemoryDroneRepository,
        ws_manager: WebSocketManager | None = None,
    ) -> None:
        self._settings = settings
        self._drone_repo = drone_repo
        self._ws = ws_manager

    # ------------------------------------------------------------------
    # Core scoring
    # ------------------------------------------------------------------

    def score_drone(self, drone: Any) -> DroneHealthResult:
        """Compute a health score and label for one drone.

        Persists ``health_score`` / ``health_label`` back to the repository
        and broadcasts a ``drone_health`` WebSocket event.

        Parameters
        ----------
        drone:
            Any object that exposes the ``Drone`` ORM interface:
            ``drone_id``, ``last_seen_at``, ``last_telemetry_json``.
        """
        tele: dict[str, Any] = drone.last_telemetry_json or {}
        battery_pct: float = float(tele.get("battery_pct", 0.0))
        gps_sats: int = int(tele.get("gps_sats", 0))
        ekf_ok: bool = bool(tele.get("ekf_ok", False))

        # ---- signal / staleness -------------------------------------------
        now = datetime.now(timezone.utc)
        stale_timeout: float = float(self._settings.STALE_TIMEOUT_SEC)

        last_seen: datetime | None = drone.last_seen_at
        if last_seen is not None and last_seen.tzinfo is None:
            last_seen = last_seen.replace(tzinfo=timezone.utc)

        seconds_since: float = (
            stale_timeout + 1.0
            if last_seen is None
            else (now - last_seen).total_seconds()
        )

        # ---- OFFLINE check ------------------------------------------------
        if seconds_since > stale_timeout:
            result = DroneHealthResult(
                drone_id=drone.drone_id,
                score=0.0,
                label="OFFLINE",
                battery_pct=battery_pct,
                gps_sats=gps_sats,
                ekf_ok=ekf_ok,
                last_seen_at=last_seen.isoformat() if last_seen else None,
            )
            self._persist_and_broadcast(drone.drone_id, result)
            return result

        # ---- composite score components -----------------------------------
        battery_score: float = battery_pct / 100.0
        gps_score: float = min(gps_sats / float(_GPS_FULL_SATS), 1.0)
        ekf_score: float = 1.0 if ekf_ok else 0.0
        signal_score: float = max(0.0, 1.0 - (seconds_since / stale_timeout))

        score: float = min(battery_score, gps_score, ekf_score, signal_score)

        if score >= _GREEN_THRESHOLD:
            label = "GREEN"
        elif score >= _YELLOW_THRESHOLD:
            label = "YELLOW"
        else:
            label = "RED"

        result = DroneHealthResult(
            drone_id=drone.drone_id,
            score=round(score, 4),
            label=label,
            battery_pct=battery_pct,
            gps_sats=gps_sats,
            ekf_ok=ekf_ok,
            last_seen_at=last_seen.isoformat() if last_seen else None,
        )
        self._persist_and_broadcast(drone.drone_id, result)
        return result

    # ------------------------------------------------------------------
    # Convenience accessors
    # ------------------------------------------------------------------

    def get_drone_health(self, drone_id: str) -> DroneHealthResult | None:
        """Score a single drone by ID.  Returns ``None`` if not registered."""
        drone = self._drone_repo.get(drone_id)
        if drone is None:
            return None
        return self.score_drone(drone)

    def fleet_summary(self) -> FleetHealthSummary:
        """Score every registered drone and return aggregate counts."""
        drones = self._drone_repo.list_all()

        healthy = warning = critical = offline = 0
        details: list[dict[str, Any]] = []

        for drone in drones:
            result = self.score_drone(drone)
            match result.label:
                case "GREEN":
                    healthy += 1
                case "YELLOW":
                    warning += 1
                case "RED":
                    critical += 1
                case "OFFLINE":
                    offline += 1

            details.append(result.model_dump())

        return FleetHealthSummary(
            healthy=healthy,
            warning=warning,
            critical=critical,
            offline=offline,
            details=details,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _persist_and_broadcast(self, drone_id: str, result: DroneHealthResult) -> None:
        """Write updated health fields to the repo and broadcast via WS."""
        self._drone_repo.upsert(
            drone_id=drone_id,
            health_score=result.score,
            health_label=result.label,
        )

        if self._ws is not None:
            self._ws.broadcast_sync(
                DRONE_HEALTH_EVENT,
                {
                    "drone_id": result.drone_id,
                    "score": result.score,
                    "label": result.label,
                    "battery_pct": result.battery_pct,
                    "gps_sats": result.gps_sats,
                },
            )
