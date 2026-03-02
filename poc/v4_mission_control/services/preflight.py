"""Preflight service for calibration-aware command safety."""

from datetime import datetime, timezone

from ..config import Settings
from ..schemas.preflight import PreflightResponse, SensorHealth


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class PreflightService:
    """Stub preflight provider used until live telemetry is wired in."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def get_preflight(self, drone_id: str) -> PreflightResponse:
        tokens = self._tokenize(drone_id)
        calibration_required = "UNCAL" in tokens
        sensor_health = SensorHealth(
            gyro_ok="GYROFAIL" not in tokens and "UNCAL" not in tokens,
            accel_ok="ACCELFAIL" not in tokens and "UNCAL" not in tokens,
            compass_ok="COMPASSFAIL" not in tokens and "UNCAL" not in tokens,
            ekf_ok="EKFBAD" not in tokens,
        )

        prearm_failures: list[str] = []
        if "GYROFAIL" in tokens:
            prearm_failures.append("PreArm: Gyros not calibrated")
        if "COMPASSFAIL" in tokens:
            prearm_failures.append("PreArm: Compass not calibrated")
        if calibration_required:
            prearm_failures.append("PreArm: Accel calibration required")
        if "SAFETYLOCK" in tokens:
            prearm_failures.append("PreArm: Hardware safety switch")

        return PreflightResponse(
            drone_id=drone_id,
            prearm_ok=not prearm_failures,
            calibration_required=calibration_required,
            battery_pct=self._battery_pct(tokens),
            gps_sats=self._gps_sats(tokens),
            armed="ARMED" in tokens,
            mode="STANDBY",
            prearm_failures=prearm_failures,
            sensor_health=sensor_health,
            last_calibrated_at=None if calibration_required else _utc_now_iso(),
            timestamp=_utc_now_iso(),
        )

    def arm_rejection_reasons(self, preflight: PreflightResponse) -> list[str]:
        """Return canonical ARM rejection reasons for the current snapshot."""

        reasons: list[str] = []
        if preflight.battery_pct < self._settings.BATTERY_ARM_MIN_PCT:
            reasons.append("battery below minimum threshold")
        if preflight.gps_sats < self._settings.GPS_ARM_MIN_SATS:
            reasons.append("gps satellites below minimum threshold")
        if not preflight.sensor_health.ekf_ok:
            reasons.append("ekf unhealthy")
        if preflight.armed:
            reasons.append("drone already armed")
        if not preflight.prearm_ok:
            reasons.append("prearm checks failed")
        if preflight.calibration_required:
            reasons.append("calibration required")
        if not preflight.sensor_health.gyro_ok:
            reasons.append("gyro health check failed")
        if not preflight.sensor_health.accel_ok:
            reasons.append("accelerometer health check failed")
        if not preflight.sensor_health.compass_ok:
            reasons.append("compass health check failed")
        reasons.extend(preflight.prearm_failures)
        return list(dict.fromkeys(reasons))

    def _battery_pct(self, tokens: set[str]) -> int:
        if "LOWBAT" in tokens:
            return max(self._settings.BATTERY_ARM_MIN_PCT - 2, 0)
        return 100

    def _gps_sats(self, tokens: set[str]) -> int:
        if "NOGPS" in tokens:
            return 0
        if "LOWGPS" in tokens:
            return max(self._settings.GPS_ARM_MIN_SATS - 1, 0)
        return 8

    @staticmethod
    def _tokenize(drone_id: str) -> set[str]:
        return {
            token
            for token in drone_id.replace("_", "-").upper().split("-")
            if token
        }
