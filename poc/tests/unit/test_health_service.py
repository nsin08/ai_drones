"""Unit tests: HealthService score_drone() — W13 G7.

Tests all four score components plus boundary conditions at 0.3 and 0.7.
Uses InMemoryDroneRepository so no DB is required.
"""

from datetime import datetime, timedelta, timezone

import pytest

from poc.v4_mission_control.config import Settings
from poc.v4_mission_control.repos.drone_repo import InMemoryDroneRepository
from poc.v4_mission_control.services.health_service import HealthService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _settings(**overrides) -> Settings:
    base = {
        "SERVICE_NAME": "test",
        "ENVIRONMENT": "SIM",
        "BATTERY_ARM_MIN_PCT": 10,
        "GPS_ARM_MIN_SATS": 4,
        "STALE_TIMEOUT_SEC": 30,
        "COMMAND_ACK_TIMEOUT_SEC": 5,
        "COMMAND_MAX_RETRIES": 3,
        "USE_DATABASE": False,
    }
    base.update(overrides)
    return Settings(**base)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _service(repo: InMemoryDroneRepository, **setting_overrides) -> HealthService:
    return HealthService(
        settings=_settings(**setting_overrides),
        drone_repo=repo,
        ws_manager=None,  # no WS in unit tests
    )


def _insert(
    repo: InMemoryDroneRepository,
    drone_id: str,
    *,
    battery_pct: float = 100.0,
    gps_sats: int = 8,
    ekf_ok: bool = True,
    seconds_ago: float = 0.0,
) -> None:
    repo.upsert(
        drone_id=drone_id,
        last_seen_at=_now() - timedelta(seconds=seconds_ago),
        last_telemetry_json={
            "battery_pct": battery_pct,
            "gps_sats": gps_sats,
            "ekf_ok": ekf_ok,
        },
    )


# ---------------------------------------------------------------------------
# Battery score
# ---------------------------------------------------------------------------


class TestBatteryScore:
    def test_full_battery_scores_1(self):
        repo = InMemoryDroneRepository()
        svc = _service(repo)
        _insert(repo, "D1", battery_pct=100.0, gps_sats=8, ekf_ok=True)
        result = svc.get_drone_health("D1")
        assert result is not None
        assert result.score == 1.0
        assert result.label == "GREEN"

    def test_battery_10_pct_scores_0_1_label_red(self):
        repo = InMemoryDroneRepository()
        svc = _service(repo)
        _insert(repo, "D1", battery_pct=10.0, gps_sats=8, ekf_ok=True)
        result = svc.get_drone_health("D1")
        assert result is not None
        assert result.score < 0.3  # battery_score = 0.1 => min = 0.1
        assert result.label == "RED"

    def test_battery_0_pct_scores_0_label_red(self):
        repo = InMemoryDroneRepository()
        svc = _service(repo)
        _insert(repo, "D1", battery_pct=0.0, gps_sats=8, ekf_ok=True)
        result = svc.get_drone_health("D1")
        assert result is not None
        assert result.score == 0.0
        assert result.label == "RED"

    def test_battery_70_pct_is_green_boundary(self):
        """70% battery with perfect GPS/EKF/signal → score = 0.7 → GREEN."""
        repo = InMemoryDroneRepository()
        svc = _service(repo)
        _insert(repo, "D1", battery_pct=70.0, gps_sats=8, ekf_ok=True)
        result = svc.get_drone_health("D1")
        assert result is not None
        assert result.score == pytest.approx(0.7)
        assert result.label == "GREEN"

    def test_battery_30_pct_is_yellow_boundary(self):
        """30% battery with perfect GPS/EKF/signal → score = 0.3 → YELLOW."""
        repo = InMemoryDroneRepository()
        svc = _service(repo)
        _insert(repo, "D1", battery_pct=30.0, gps_sats=8, ekf_ok=True)
        result = svc.get_drone_health("D1")
        assert result is not None
        assert result.score == pytest.approx(0.3)
        assert result.label == "YELLOW"

    def test_battery_29_pct_is_red(self):
        """29% battery → score < 0.3 → RED."""
        repo = InMemoryDroneRepository()
        svc = _service(repo)
        _insert(repo, "D1", battery_pct=29.9, gps_sats=8, ekf_ok=True)
        result = svc.get_drone_health("D1")
        assert result is not None
        assert result.score < 0.3
        assert result.label == "RED"


# ---------------------------------------------------------------------------
# GPS score
# ---------------------------------------------------------------------------


class TestGpsScore:
    def test_8_or_more_sats_full_score(self):
        repo = InMemoryDroneRepository()
        svc = _service(repo)
        _insert(repo, "D1", gps_sats=8)
        assert svc.get_drone_health("D1").score == 1.0  # type: ignore[union-attr]

    def test_9_sats_clamped_to_1(self):
        """More than 8 sats is still capped at 1.0."""
        repo = InMemoryDroneRepository()
        svc = _service(repo)
        _insert(repo, "D1", gps_sats=12)
        assert svc.get_drone_health("D1").score == 1.0  # type: ignore[union-attr]

    def test_0_sats_label_red(self):
        repo = InMemoryDroneRepository()
        svc = _service(repo)
        _insert(repo, "D1", battery_pct=100.0, gps_sats=0, ekf_ok=True)
        result = svc.get_drone_health("D1")
        assert result is not None
        assert result.score == 0.0
        assert result.label == "RED"

    def test_4_sats_scores_half(self):
        repo = InMemoryDroneRepository()
        svc = _service(repo)
        _insert(repo, "D1", battery_pct=100.0, gps_sats=4, ekf_ok=True)
        result = svc.get_drone_health("D1")
        assert result is not None
        assert result.score == pytest.approx(0.5)
        assert result.label == "YELLOW"


# ---------------------------------------------------------------------------
# EKF score
# ---------------------------------------------------------------------------


class TestEkfScore:
    def test_ekf_false_scores_0(self):
        repo = InMemoryDroneRepository()
        svc = _service(repo)
        _insert(repo, "D1", battery_pct=100.0, gps_sats=8, ekf_ok=False)
        result = svc.get_drone_health("D1")
        assert result is not None
        assert result.score == 0.0
        assert result.label == "RED"

    def test_ekf_true_does_not_degrade_perfect_drone(self):
        repo = InMemoryDroneRepository()
        svc = _service(repo)
        _insert(repo, "D1", battery_pct=100.0, gps_sats=8, ekf_ok=True)
        result = svc.get_drone_health("D1")
        assert result is not None
        assert result.score == 1.0


# ---------------------------------------------------------------------------
# Composite (min rule)
# ---------------------------------------------------------------------------


class TestCompositeScore:
    def test_weakest_component_dominates(self):
        """Battery=50%, GPS=8sat, EKF=True, signal=full → score = 0.5."""
        repo = InMemoryDroneRepository()
        svc = _service(repo)
        _insert(repo, "D1", battery_pct=50.0, gps_sats=8, ekf_ok=True)
        result = svc.get_drone_health("D1")
        assert result is not None
        assert result.score == pytest.approx(0.5)
        assert result.label == "YELLOW"

    def test_health_label_persisted_to_repo(self):
        """score_drone upserts health_score + health_label back into the repo."""
        repo = InMemoryDroneRepository()
        svc = _service(repo)
        _insert(repo, "D1", battery_pct=100.0, gps_sats=8, ekf_ok=True)
        svc.score_drone(repo.get("D1"))
        d = repo.get("D1")
        assert d is not None
        assert d.health_score == 1.0
        assert d.health_label == "GREEN"

    def test_get_drone_health_returns_none_for_unknown(self):
        repo = InMemoryDroneRepository()
        svc = _service(repo)
        assert svc.get_drone_health("DOES-NOT-EXIST") is None
