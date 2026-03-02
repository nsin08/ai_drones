"""In-memory operator store and OperatorContext model for Mission Control v4 (W14).

``OperatorContext`` is the lightweight, request-scoped representation of an
authenticated operator that flows through FastAPI dependencies and ACL checks.
It is intentionally decoupled from the SQLAlchemy ``Operator`` ORM model so
that unit tests can run without a database.

``InMemoryOperatorStore`` is pre-seeded with three accounts:

    admin   / admin123   — ADMIN role   (no restrictions)
    pilot1  / pilot123   — PILOT role   (allowed: SIM-001 … SIM-006)
    pilot2  / pilot123   — PILOT role   (allowed: SIM-007 … SIM-012)
    observer/ observe123 — OBSERVER role (read-only)
"""

from __future__ import annotations

from dataclasses import dataclass, field

from passlib.context import CryptContext

_pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


@dataclass
class OperatorContext:
    """Request-scoped operator identity resolved from a JWT."""

    operator_id: str
    username: str
    role: str  # OBSERVER | PILOT | ADMIN
    allowed_drones: list[str] = field(default_factory=list)
    """Drone IDs this PILOT is permitted to command.  Empty → no restriction."""


# ---------------------------------------------------------------------------
# In-memory store (used when USE_DATABASE=False, i.e. unit tests)
# ---------------------------------------------------------------------------

@dataclass
class _StoredOperator:
    operator_id: str
    username: str
    role: str
    hashed_password: str
    allowed_drones: list[str] = field(default_factory=list)


_SEED_OPERATORS: list[tuple[str, str, str, list[str]]] = [
    # (operator_id,       username,   plain_pw,     allowed_drones)
    ("op-admin-001",   "admin",    "admin123",   []),
    ("op-pilot-001",   "pilot1",   "pilot123",   [f"SIM-{i:03d}" for i in range(1, 7)]),
    ("op-pilot-002",   "pilot2",   "pilot123",   [f"SIM-{i:03d}" for i in range(7, 13)]),
    ("op-observe-001", "observer", "observe123", []),
]


class InMemoryOperatorStore:
    """Seeded in-memory credential store for unit tests."""

    def __init__(self) -> None:
        self._by_username: dict[str, _StoredOperator] = {}
        self._by_id: dict[str, _StoredOperator] = {}
        for op_id, username, plain, drones in _SEED_OPERATORS:
            hashed = _pwd_ctx.hash(plain)
            stored = _StoredOperator(
                operator_id=op_id,
                username=username,
                role="ADMIN" if "admin" in op_id else (
                    "PILOT" if "pilot" in op_id else "OBSERVER"
                ),
                hashed_password=hashed,
                allowed_drones=drones,
            )
            self._by_username[username] = stored
            self._by_id[op_id] = stored

    # ------------------------------------------------------------------
    # Public API (mirrors what a SQLOperatorStore would expose)
    # ------------------------------------------------------------------

    def authenticate(self, username: str, password: str) -> OperatorContext | None:
        """Verify credentials and return an OperatorContext, or None."""
        stored = self._by_username.get(username)
        if stored is None:
            return None
        if not _pwd_ctx.verify(password, stored.hashed_password):
            return None
        return OperatorContext(
            operator_id=stored.operator_id,
            username=stored.username,
            role=stored.role,
            allowed_drones=list(stored.allowed_drones),
        )

    def get_by_id(self, operator_id: str) -> OperatorContext | None:
        """Return an OperatorContext by operator_id, or None."""
        stored = self._by_id.get(operator_id)
        if stored is None:
            return None
        return OperatorContext(
            operator_id=stored.operator_id,
            username=stored.username,
            role=stored.role,
            allowed_drones=list(stored.allowed_drones),
        )


# ---------------------------------------------------------------------------
# Sentinel — used when AUTH_ENABLED=False (legacy / bypass mode)
# ---------------------------------------------------------------------------

ANONYMOUS_ADMIN = OperatorContext(
    operator_id="anonymous",
    username="anonymous",
    role="ADMIN",
    allowed_drones=[],
)
