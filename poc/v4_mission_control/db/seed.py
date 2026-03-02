"""Database seed script for Mission Control v4 (W11 deferred → W12).

Usage:
    python -m poc.v4_mission_control.db.seed

Creates:
    - 12 SIM drones  (SIM-001 … SIM-012)
    - 2 HW drones    (HW-001, HW-002)
    - 2 sample missions (PLANNING and ACTIVE)
"""

import sys
from datetime import datetime, timezone
from uuid import uuid4

from .session import db_session as get_session
from ..models.drone import Drone, DroneSnapshot
from ..models.mission import Mission, Task


_SIM_DRONES = [f"SIM-{i:03d}" for i in range(1, 13)]
_HW_DRONES = ["HW-001", "HW-002"]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _seed_drones(db) -> None:
    existing = {row.drone_id for row in db.query(Drone).all()}
    now = _utc_now()

    for drone_id in _SIM_DRONES + _HW_DRONES:
        if drone_id in existing:
            continue
        drone_type = "SIM" if drone_id.startswith("SIM") else "HW"
        db.add(
            Drone(
                drone_id=drone_id,
                env=drone_type,
                last_telemetry_json={"seeded": True},
            )
        )
    db.flush()
    print(f"  Drones: {len(_SIM_DRONES + _HW_DRONES)} defined, {len(existing)} already existed")


def _seed_missions(db) -> None:
    existing_count = db.query(Mission).count()
    if existing_count > 0:
        print(f"  Missions: {existing_count} already exist, skipping")
        return

    now = _utc_now()

    # Mission 1 — PLANNING
    m1_id = str(uuid4())
    db.add(
        Mission(
            mission_id=m1_id,
            type="RECON",
            status="PLANNING",
            created_by="seed-script",
            config_json={"priority": "low"},
        )
    )
    for i, drone_id in enumerate(["SIM-001", "SIM-002"], start=1):
        db.add(
            Task(
                task_id=str(uuid4()),
                mission_id=m1_id,
                type="WAYPOINT",
                state="PLANNED",
                drone_ids_json=[drone_id],
                waypoints_json=[{"lat": 51.5 + i * 0.01, "lon": -0.1}],
                formation=None,
            )
        )

    # Mission 2 — ACTIVE
    m2_id = str(uuid4())
    db.add(
        Mission(
            mission_id=m2_id,
            type="PATROL",
            status="ACTIVE",
            created_by="seed-script",
            config_json={"priority": "high"},
            started_at=now,
        )
    )
    for drone_id in ["SIM-003", "SIM-004", "SIM-005"]:
        db.add(
            Task(
                task_id=str(uuid4()),
                mission_id=m2_id,
                type="PATROL_LEG",
                state="ACTIVE",
                drone_ids_json=[drone_id],
                waypoints_json=[],
                formation="LINE",
            )
        )

    db.flush()
    print("  Missions: 2 created (RECON/PLANNING, PATROL/ACTIVE)")


def run_seed() -> None:
    print("Running seed…")
    with get_session() as db:
        _seed_drones(db)
        _seed_missions(db)
    print("Seed complete.")


if __name__ == "__main__":
    run_seed()
