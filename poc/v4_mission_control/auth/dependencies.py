"""FastAPI dependency for authenticating the current operator (W14).

Usage in route functions::

    from ..auth.dependencies import get_current_operator
    from ..auth.operator_store import OperatorContext

    @router.post("/commands")
    def send_command(
        ...,
        operator: OperatorContext = Depends(get_current_operator),
    ):
        ...

Behaviour
---------
* ``AUTH_ENABLED=False`` (default) — returns :data:`.ANONYMOUS_ADMIN` so all
  178 legacy tests continue to pass without modification.
* ``AUTH_ENABLED=True`` — requires a valid ``Authorization: Bearer <token>``
  header.  The token is decoded; the ``sub`` claim is used to look up the
  operator in :class:`InMemoryOperatorStore`.  Raises **HTTP 401** on any
  failure.
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError

from ..config import Settings, get_settings
from ..services.runtime import ServiceContainer, get_service_container
from .jwt import decode_access_token
from .operator_store import ANONYMOUS_ADMIN, OperatorContext

_bearer_scheme = HTTPBearer(auto_error=False)


def get_current_operator(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    settings: Settings = Depends(get_settings),
    runtime: ServiceContainer = Depends(get_service_container),
) -> OperatorContext:
    """Return the authenticated :class:`OperatorContext` for the request.

    When ``AUTH_ENABLED`` is ``False`` the function short-circuits and returns
    :data:`ANONYMOUS_ADMIN` — this preserves backward compatibility for every
    existing test and any caller that has not been updated to send tokens yet.
    """
    if not settings.AUTH_ENABLED:
        return ANONYMOUS_ADMIN

    # --- auth is enabled: validate the Bearer token -----------------------
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header missing",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        claims = decode_access_token(credentials.credentials, settings=settings)
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired token: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    operator_id: str | None = claims.get("sub")
    if not operator_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing 'sub' claim",
            headers={"WWW-Authenticate": "Bearer"},
        )

    operator = runtime.operator_store.get_by_id(operator_id)
    if operator is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Operator not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return operator
