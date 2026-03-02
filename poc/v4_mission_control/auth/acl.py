"""Role-based access control helpers (W14).

These are thin guard functions — they raise :class:`fastapi.HTTPException`
if the given :class:`OperatorContext` does not have permission.  They are
called explicitly by route handlers or by :class:`CommandService` (env guard).

Permission Model
----------------
ADMIN
    Full access to all drones and admin endpoints.
PILOT
    May issue commands.  If ``allowed_drones`` is non-empty the pilot is
    restricted to those drone IDs.  An empty list means *all* drones.
OBSERVER
    Read-only.  Cannot issue commands or mutate missions.
"""

from __future__ import annotations

from fastapi import HTTPException, status

from .operator_store import OperatorContext


def check_command_permission(
    operator: OperatorContext,
    drone_id: str,
) -> None:
    """Assert the operator may send commands to *drone_id*.

    Raises
    ------
    HTTPException(403)
        If the operator is an OBSERVER, or is a PILOT whose allowed-drone list
        does not contain *drone_id*.
    """
    if operator.role == "OBSERVER":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="OBSERVER role is read-only and cannot issue commands",
        )

    if (
        operator.role == "PILOT"
        and operator.allowed_drones  # empty list → no restriction
        and drone_id not in operator.allowed_drones
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Operator '{operator.username}' is not assigned to drone '{drone_id}'"
            ),
        )


def require_admin(operator: OperatorContext) -> None:
    """Assert the operator has the ADMIN role.

    Raises
    ------
    HTTPException(403)
        If the operator is not ADMIN.
    """
    if operator.role != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="ADMIN role required",
        )
