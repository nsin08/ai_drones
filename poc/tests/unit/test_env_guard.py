"""Unit tests: Environment guard in CommandService (W14 G9).

DRONE_ENV=SIM  → reject commands to HARDWARE drones (not starting with SIM-)
DRONE_ENV=HARDWARE → reject commands to SIM drones (starting with SIM-)
DRONE_ENV=ALL  → no env restriction (default for tests)

Also tests that _command_topic uses MQTT_TOPIC_PREFIX from settings.
"""

from __future__ import annotations

import pytest

from poc.v4_mission_control.config import Settings
from poc.v4_mission_control.repos.command_repo import InMemoryCommandRepository
from poc.v4_mission_control.repos.event_repo import InMemoryEventRepository
from poc.v4_mission_control.schemas.command import CommandRequest, CommandStatus
from poc.v4_mission_control.services.commands import CommandService
from poc.v4_mission_control.services.preflight import PreflightService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _settings(**overrides) -> Settings:
    defaults = {
        "SERVICE_NAME": "test",
        "ENVIRONMENT": "SIM",
        "USE_DATABASE": False,
        "COMMAND_MAX_RETRIES": 3,
        "COMMAND_RETRY_BACKOFF_SEC": (0, 0, 0),
        "COMMAND_ACK_TIMEOUT_SEC": 0,
        "DRONE_ENV": "ALL",          # override in tests
        "MQTT_TOPIC_PREFIX": "fleet/sim",
    }
    defaults.update(overrides)
    return Settings(**defaults)


def _make_service(settings: Settings) -> tuple[CommandService, InMemoryCommandRepository]:
    command_repo = InMemoryCommandRepository()
    event_repo = InMemoryEventRepository()
    preflight_service = PreflightService(settings=settings)
    svc = CommandService(
        settings=settings,
        command_repo=command_repo,
        event_repo=event_repo,
        preflight_service=preflight_service,
    )
    return svc, command_repo


def _cmd(drone_id: str, command: str = "TAKEOFF") -> CommandRequest:
    return CommandRequest(drone_id=drone_id, command=command, params={"alt_m": 10})


# ---------------------------------------------------------------------------
# _env_guard via submit_command
# ---------------------------------------------------------------------------


class TestEnvGuardSIM:
    """DRONE_ENV=SIM should reject HW drones."""

    def setup_method(self):
        self.svc, self.repo = _make_service(_settings(DRONE_ENV="SIM"))

    def test_sim_drone_passes_env_guard(self):
        result = self.svc.submit_command(_cmd("SIM-001"), start_retry_thread=False)
        # Should be ACCEPTED (not rejected due to env)
        from poc.v4_mission_control.schemas.command import CommandAcceptedResponse
        assert isinstance(result, CommandAcceptedResponse)

    def test_hw_drone_rejected_by_env_guard(self):
        from poc.v4_mission_control.schemas.command import CommandRejectedResponse
        result = self.svc.submit_command(_cmd("HW-001"), start_retry_thread=False)
        assert isinstance(result, CommandRejectedResponse)
        assert "SIM" in result.rejection_reason
        assert "HW-001" in result.rejection_reason

    def test_hw_drone_stored_as_rejected(self):
        self.svc.submit_command(_cmd("HW-001"), start_retry_thread=False)
        records = self.repo.list_recent(drone_id="HW-001", limit=10)
        assert records[0].status == CommandStatus.REJECTED


class TestEnvGuardHARDWARE:
    """DRONE_ENV=HARDWARE should reject SIM drones."""

    def setup_method(self):
        self.svc, self.repo = _make_service(_settings(DRONE_ENV="HARDWARE"))

    def test_sim_drone_rejected(self):
        from poc.v4_mission_control.schemas.command import CommandRejectedResponse
        result = self.svc.submit_command(_cmd("SIM-001"), start_retry_thread=False)
        assert isinstance(result, CommandRejectedResponse)
        assert "HARDWARE" in result.rejection_reason
        assert "SIM-001" in result.rejection_reason

    def test_hw_drone_passes(self):
        from poc.v4_mission_control.schemas.command import CommandAcceptedResponse
        result = self.svc.submit_command(_cmd("HW-001"), start_retry_thread=False)
        assert isinstance(result, CommandAcceptedResponse)


class TestEnvGuardALL:
    """DRONE_ENV=ALL should never block based on env."""

    def setup_method(self):
        self.svc, _ = _make_service(_settings(DRONE_ENV="ALL"))

    def test_sim_drone_passes(self):
        from poc.v4_mission_control.schemas.command import CommandAcceptedResponse
        assert isinstance(
            self.svc.submit_command(_cmd("SIM-001"), start_retry_thread=False),
            CommandAcceptedResponse,
        )

    def test_hw_drone_passes(self):
        from poc.v4_mission_control.schemas.command import CommandAcceptedResponse
        assert isinstance(
            self.svc.submit_command(_cmd("HW-001"), start_retry_thread=False),
            CommandAcceptedResponse,
        )


class TestEnvGuardCasing:
    """DRONE_ENV comparison should be case-insensitive."""

    def test_lowercase_sim_setting(self):
        svc, _ = _make_service(_settings(DRONE_ENV="sim"))
        from poc.v4_mission_control.schemas.command import CommandRejectedResponse
        result = svc.submit_command(_cmd("HW-001"), start_retry_thread=False)
        assert isinstance(result, CommandRejectedResponse)

    def test_mixed_case_drone_id(self):
        """Drone ID comparison is case-insensitive: sim-001 treated as SIM drone."""
        svc, _ = _make_service(_settings(DRONE_ENV="SIM"))
        from poc.v4_mission_control.schemas.command import CommandAcceptedResponse
        result = svc.submit_command(_cmd("sim-001"), start_retry_thread=False)
        assert isinstance(result, CommandAcceptedResponse)


# ---------------------------------------------------------------------------
# _command_topic uses MQTT_TOPIC_PREFIX
# ---------------------------------------------------------------------------


class TestCommandTopic:
    def test_default_prefix(self):
        svc, _ = _make_service(_settings(MQTT_TOPIC_PREFIX="fleet/sim"))
        assert svc._command_topic("SIM-001") == "fleet/sim/SIM-001/command"

    def test_hardware_prefix(self):
        svc, _ = _make_service(_settings(MQTT_TOPIC_PREFIX="fleet/hw"))
        assert svc._command_topic("HW-001") == "fleet/hw/HW-001/command"

    def test_trailing_slash_stripped(self):
        svc, _ = _make_service(_settings(MQTT_TOPIC_PREFIX="fleet/hw/"))
        assert svc._command_topic("HW-001") == "fleet/hw/HW-001/command"

    def test_custom_prefix(self):
        svc, _ = _make_service(_settings(MQTT_TOPIC_PREFIX="drones/prod"))
        assert svc._command_topic("HW-007") == "drones/prod/HW-007/command"
