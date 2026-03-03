"""Role-based access control helpers (W14)."""

from __future__ import annotations

from fastapi import HTTPException, status

from .operator_store import OperatorContext


def _check_drone_scope(
    operator: OperatorContext,
    drone_ids: list[str] | None,
    *,
    allow_observer: bool,
    action_label: str,
) -> None:
    if operator.role == "OBSERVER" and not allow_observer:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"OBSERVER role is read-only and cannot {action_label}",
        )

    if operator.role != "PILOT" or not operator.allowed_drones:
        return

    requested_ids = {drone_id for drone_id in (drone_ids or []) if drone_id}
    disallowed = sorted(requested_ids.difference(operator.allowed_drones))
    if not disallowed:
        return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=(
            f"Operator '{operator.username}' is not assigned to drone(s): "
            f"{', '.join(disallowed)}"
        ),
    )


def check_command_permission(
    operator: OperatorContext,
    drone_id: str,
) -> None:
    """Assert the operator may send commands to *drone_id*."""

    _check_drone_scope(
        operator,
        [drone_id],
        allow_observer=False,
        action_label="issue commands",
    )


def check_mission_permission(
    operator: OperatorContext,
    drone_ids: list[str] | None = None,
    *,
    write: bool,
) -> None:
    """Assert the operator may read or mutate a mission scoped to *drone_ids*."""

    _check_drone_scope(
        operator,
        drone_ids,
        allow_observer=not write,
        action_label="modify missions" if write else "view this mission",
    )


def require_admin(operator: OperatorContext) -> None:
    """Assert the operator has the ADMIN role."""

    if operator.role != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="ADMIN role required",
        )
