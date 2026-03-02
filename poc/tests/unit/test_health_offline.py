"""Unit tests: HealthService OFFLINE detection — W13 G7.

A drone not seen within STALE_TIMEOUT_SEC must be labelled OFFLINE
regardless of the telemetry values stored in its record.
"""

from datetime import datetime, timedelta, timezone

from poc.v4_mission_control.config import Settings
from poc.v4_mission_control.repos.drone_repo import InMemoryDroneRepository
from poc.v4_mission_control.services.health_service import HealthService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_STALE = 30  # seconds


def _settings() -> Settings:
    return Settings(
        SERVICE_NAME="test",
        ENVIRONMENT="SIM",
        BATTERY_ARM_MIN_PCT=10,
        GPS_ARM_MIN_SATS=4,
        STALE_TIMEOUT_SEC=_STALE,
        COMMAND_ACK_TIMEOUT_SEC=5,
        COMMAND_MAX_RETRIES=3,
        USE_DATABASE=False,
    )


def _service(repo: InMemoryDroneRepository) -> HealthService:
    return HealthService(settings=_settings(), drone_repo=repo, ws_manager=None)


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# OFFLINE tests
# ---------------------------------------------------------------------------


class TestOfflineDetection:
    def test_drone_never_seen_is_offline(self):
        """A drone with no last_seen_at is OFFLINE regardless of telemetry."""
        repo = InMemoryDroneRepository()
        repo.upsert(
            drone_id="SIM-001",
            last_seen_at=None,
            last_telemetry_json={"battery_pct": 100, "gps_sats": 8, "ekf_ok": True},
        )
        svc = _service(repo)
        result = svc.get_drone_health("SIM-001")
        assert result is not None
        assert result.label == "OFFLINE"
        assert result.score == 0.0

    def test_drone_stale_beyond_timeout_is_offline(self):
        """last_seen_at older than STALE_TIMEOUT_SEC  → OFFLINE."""
        repo = InMemoryDroneRepository()
        repo.upsert(
            drone_id="SIM-002",
            last_seen_at=_now() - timedelta(seconds=_STALE + 1),
            last_telemetry_json={"battery_pct": 100, "gps_sats": 8, "ekf_ok": True},
        )
        svc = _service(repo)
        result = svc.get_drone_health("SIM-002")
        assert result is not None
        assert result.label == "OFFLINE"

    def test_drone_exactly_at_timeout_boundary_is_offline(self):
        """Exactly at the stale boundary (seconds ≈ STALE_TIMEOUT_SEC).

        At this boundary two outcomes are possible depending on clock precision:
        - If seconds_since > stale_timeout  → OFFLINE
        - If seconds_since == stale_timeout  → signal_score = 0.0 → score = 0.0 → RED
        Both are valid; the test asserts neither GREEN nor YELLOW is returned.
        """
        repo = InMemoryDroneRepository()
        repo.upsert(
            drone_id="SIM-003",
            last_seen_at=_now() - timedelta(seconds=_STALE),
            last_telemetry_json={"battery_pct": 100, "gps_sats": 8, "ekf_ok": True},
        )
        svc = _service(repo)
        result = svc.get_drone_health("SIM-003")
        assert result is not None
        assert result.label in {"OFFLINE", "RED"}

    def test_drone_just_seen_is_not_offline(self):
        """last_seen_at 1 second ago is well within the window."""
        repo = InMemoryDroneRepository()
        repo.upsert(
            drone_id="SIM-004",
            last_seen_at=_now() - timedelta(seconds=1),
            last_telemetry_json={"battery_pct": 100, "gps_sats": 8, "ekf_ok": True},
        )
        svc = _service(repo)
        result = svc.get_drone_health("SIM-004")
        assert result is not None
        assert result.label != "OFFLINE"

    def test_offline_label_persisted_to_repo(self):
        """OFFLINE label is written back to the repository."""
        repo = InMemoryDroneRepository()
        repo.upsert(
            drone_id="SIM-005",
            last_seen_at=_now() - timedelta(seconds=_STALE + 60),
            last_telemetry_json={},
        )
        svc = _service(repo)
        svc.get_drone_health("SIM-005")
        d = repo.get("SIM-005")
        assert d is not None
        assert d.health_label == "OFFLINE"
        assert d.health_score == 0.0

    def test_offline_battery_and_gps_still_populated(self):
        """Even for OFFLINE drones, telemetry values are surfaced in the result."""
        repo = InMemoryDroneRepository()
        repo.upsert(
            drone_id="SIM-006",
            last_seen_at=None,
            last_telemetry_json={"battery_pct": 55, "gps_sats": 7, "ekf_ok": False},
        )
        svc = _service(repo)
        result = svc.get_drone_health("SIM-006")
        assert result is not None
        assert result.battery_pct == 55.0
        assert result.gps_sats == 7
