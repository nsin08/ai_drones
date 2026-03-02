"""Unit + API tests: JWT token creation and the POST /api/auth/token endpoint (W14).

Coverage:
  - InMemoryOperatorStore.authenticate / get_by_id
  - create_access_token / decode_access_token round-trip
  - POST /api/auth/token  → 200 with JWT on success, 401 on bad credentials
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from jose import JWTError

from poc.v4_mission_control.app import create_app
from poc.v4_mission_control.auth.jwt import create_access_token, decode_access_token
from poc.v4_mission_control.auth.operator_store import (
    ANONYMOUS_ADMIN,
    InMemoryOperatorStore,
    OperatorContext,
)
from poc.v4_mission_control.config import Settings
from poc.v4_mission_control.services.runtime import get_service_container


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _settings(**overrides) -> Settings:
    defaults = {
        "SERVICE_NAME": "test",
        "ENVIRONMENT": "SIM",
        "USE_DATABASE": False,
        "JWT_SECRET_KEY": "test-secret-key-for-unit-tests",
    }
    defaults.update(overrides)
    return Settings(**defaults)


def _build_client() -> TestClient:
    container = get_service_container()
    container.command_repo.clear()
    container.event_repo.clear()
    container.mission_repo.clear()
    container.drone_repo.clear()
    return TestClient(create_app())


# ---------------------------------------------------------------------------
# InMemoryOperatorStore tests
# ---------------------------------------------------------------------------


class TestInMemoryOperatorStore:
    def setup_method(self):
        self.store = InMemoryOperatorStore()

    def test_authenticate_admin_success(self):
        op = self.store.authenticate("admin", "admin123")
        assert op is not None
        assert op.username == "admin"
        assert op.role == "ADMIN"
        assert op.operator_id == "op-admin-001"

    def test_authenticate_pilot_success(self):
        op = self.store.authenticate("pilot1", "pilot123")
        assert op is not None
        assert op.role == "PILOT"
        assert "SIM-001" in op.allowed_drones

    def test_authenticate_observer_success(self):
        op = self.store.authenticate("observer", "observe123")
        assert op is not None
        assert op.role == "OBSERVER"

    def test_authenticate_wrong_password(self):
        assert self.store.authenticate("admin", "wrong") is None

    def test_authenticate_unknown_user(self):
        assert self.store.authenticate("nobody", "pass") is None

    def test_authenticate_empty_password(self):
        assert self.store.authenticate("admin", "") is None

    def test_get_by_id_found(self):
        op = self.store.get_by_id("op-admin-001")
        assert op is not None
        assert op.username == "admin"

    def test_get_by_id_missing(self):
        assert self.store.get_by_id("nonexistent-id") is None

    def test_pilot2_restricted_to_second_half(self):
        op = self.store.authenticate("pilot2", "pilot123")
        assert op is not None
        assert "SIM-007" in op.allowed_drones
        assert "SIM-001" not in op.allowed_drones

    def test_anonymous_admin_sentinel(self):
        assert ANONYMOUS_ADMIN.role == "ADMIN"
        assert ANONYMOUS_ADMIN.username == "anonymous"
        assert ANONYMOUS_ADMIN.operator_id == "anonymous"


# ---------------------------------------------------------------------------
# JWT utilities tests
# ---------------------------------------------------------------------------


class TestJWT:
    def setup_method(self):
        self.settings = _settings()

    def test_round_trip(self):
        token = create_access_token(
            settings=self.settings,
            operator_id="op-admin-001",
            username="admin",
            role="ADMIN",
            allowed_drones=[],
        )
        claims = decode_access_token(token, settings=self.settings)
        assert claims["sub"] == "op-admin-001"
        assert claims["username"] == "admin"
        assert claims["role"] == "ADMIN"
        assert claims["allowed_drones"] == []

    def test_token_contains_exp_and_iat(self):
        token = create_access_token(
            settings=self.settings,
            operator_id="x",
            username="x",
            role="PILOT",
        )
        claims = decode_access_token(token, settings=self.settings)
        assert "exp" in claims
        assert "iat" in claims

    def test_allowed_drones_in_claims(self):
        token = create_access_token(
            settings=self.settings,
            operator_id="op-pilot-001",
            username="pilot1",
            role="PILOT",
            allowed_drones=["SIM-001", "SIM-002"],
        )
        claims = decode_access_token(token, settings=self.settings)
        assert claims["allowed_drones"] == ["SIM-001", "SIM-002"]

    def test_decode_wrong_key_raises(self):
        token = create_access_token(
            settings=self.settings,
            operator_id="x",
            username="x",
            role="ADMIN",
        )
        bad_settings = _settings(JWT_SECRET_KEY="completely-different-secret")
        with pytest.raises(JWTError):
            decode_access_token(token, settings=bad_settings)

    def test_extra_claims_propagated(self):
        token = create_access_token(
            settings=self.settings,
            operator_id="x",
            username="x",
            role="ADMIN",
            extra_claims={"custom": "value"},
        )
        claims = decode_access_token(token, settings=self.settings)
        assert claims["custom"] == "value"


# ---------------------------------------------------------------------------
# API tests: POST /api/auth/token
# ---------------------------------------------------------------------------


class TestLoginEndpoint:
    def test_admin_login_returns_token(self):
        client = _build_client()
        resp = client.post("/api/auth/token", json={"username": "admin", "password": "admin123"})
        assert resp.status_code == 200
        body = resp.json()
        assert "access_token" in body
        assert body["token_type"] == "bearer"
        assert body["role"] == "ADMIN"
        assert body["operator_id"] == "op-admin-001"
        assert body["username"] == "admin"
        # Token is non-trivial
        assert len(body["access_token"]) > 20

    def test_pilot_login_returns_token(self):
        client = _build_client()
        resp = client.post("/api/auth/token", json={"username": "pilot1", "password": "pilot123"})
        assert resp.status_code == 200
        assert resp.json()["role"] == "PILOT"

    def test_wrong_password_returns_401(self):
        client = _build_client()
        resp = client.post("/api/auth/token", json={"username": "admin", "password": "bad"})
        assert resp.status_code == 401

    def test_unknown_user_returns_401(self):
        client = _build_client()
        resp = client.post("/api/auth/token", json={"username": "ghost", "password": "x"})
        assert resp.status_code == 401

    def test_me_endpoint_without_auth_returns_anonymous(self):
        """With AUTH_ENABLED=False (default), /api/auth/me returns ANONYMOUS_ADMIN."""
        client = _build_client()
        resp = client.get("/api/auth/me")
        assert resp.status_code == 200
        body = resp.json()
        assert body["username"] == "anonymous"
        assert body["role"] == "ADMIN"
