"""JWT token utilities for Mission Control v4 (W14).

Provides ``create_access_token()`` and ``decode_access_token()`` backed by
``python-jose``.  The secret key and algorithm come from :class:`Settings`
so they can be swapped in without touching this module.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt

from ..config import Settings


def create_access_token(
    *,
    settings: Settings,
    operator_id: str,
    username: str,
    role: str,
    allowed_drones: list[str] | None = None,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    """Encode and sign a JWT access token.

    Parameters
    ----------
    settings:
        v4 Settings instance (provides secret key, algorithm, and TTL).
    operator_id:
        Primary key of the operator — stored as ``sub`` claim.
    username:
        Human-readable login name.
    role:
        ``ADMIN`` | ``PILOT`` | ``OBSERVER``
    allowed_drones:
        List of drone IDs this PILOT is allowed to command.
    extra_claims:
        Any additional claims to merge into the payload.
    """
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)

    payload: dict[str, Any] = {
        "sub": operator_id,
        "username": username,
        "role": role,
        "allowed_drones": allowed_drones or [],
        "iat": now,
        "exp": expire,
    }
    if extra_claims:
        payload.update(extra_claims)

    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(
    token: str,
    *,
    settings: Settings,
) -> dict[str, Any]:
    """Decode and verify a JWT access token.

    Returns the raw claims dictionary on success.

    Raises
    ------
    jose.JWTError
        If the token is expired, has an invalid signature, or is malformed.
    """
    return jwt.decode(
        token,
        settings.JWT_SECRET_KEY,
        algorithms=[settings.JWT_ALGORITHM],
    )
