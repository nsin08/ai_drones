"""
Locust load-test suite for Mission Control v4.

Simulates realistic operator + dashboard traffic against a running v4 backend.

Usage (local):
    cd poc
    locust -f tests/load/locustfile.py --host=http://localhost:5000 \
           --users 50 --spawn-rate 5 --run-time 60s --headless

Targets (for DoD sign-off):
    - 50 concurrent users
    - 100 events/sec sustained
    - p99 response latency < 100 ms
    - 0% failure rate on green-path endpoints

Drone ID pools:
    SIM-001 … SIM-050   (simulated fleet)
"""

import json
import random
import time

from locust import HttpUser, between, task

# ---------------------------------------------------------------------------
# Shared data pools
# ---------------------------------------------------------------------------

_SIM_DRONES = [f"SIM-{i:03d}" for i in range(1, 51)]
_COMMANDS = ["TAKEOFF", "LAND", "HOLD", "RTL", "WAYPOINT_NAV"]
_MISSION_TYPES = ["PATROL", "ESCORT", "SURVEY"]
_OPERATORS = [
    ("admin", "admin-secret"),
    ("pilot1", "pilot1-secret"),
    ("pilot2", "pilot2-secret"),
]


def _random_drone() -> str:
    return random.choice(_SIM_DRONES)


def _random_waypoints(n: int = 3) -> list[dict]:
    base_lat, base_lng = 28.6139, 77.209
    return [
        {"lat": base_lat + random.uniform(-0.01, 0.01),
         "lng": base_lng + random.uniform(-0.01, 0.01),
         "alt_m": random.randint(20, 100)}
        for _ in range(n)
    ]


# ---------------------------------------------------------------------------
# Dashboard user — polling endpoints (no auth required)
# ---------------------------------------------------------------------------

class DashboardUser(HttpUser):
    """Simulates a read-only monitoring dashboard polling health data.

    Represents the majority of traffic in a real deployment.
    Weight 3 = 3× more dashboard users than operator users.
    """

    weight = 3
    wait_time = between(0.5, 2.0)

    @task(4)
    def poll_health(self):
        """Heartbeat check — most frequent task."""
        with self.client.get("/api/health", catch_response=True) as resp:
            if resp.status_code == 200:
                resp.success()
            else:
                resp.failure(f"health check failed: {resp.status_code}")

    @task(3)
    def poll_fleet_health(self):
        """Fleet health summary — dashboard overview panel."""
        with self.client.get("/api/fleet/health", catch_response=True) as resp:
            if resp.status_code == 200:
                resp.success()
            else:
                resp.failure(f"fleet health failed: {resp.status_code}")

    @task(2)
    def list_missions(self):
        """Mission list — used by active-mission table."""
        with self.client.get("/api/missions", catch_response=True) as resp:
            if resp.status_code == 200:
                resp.success()

    @task(1)
    def list_commands(self):
        """Command history — audit / log panel."""
        drone = _random_drone()
        with self.client.get(
            f"/api/commands?drone_id={drone}&limit=20", catch_response=True
        ) as resp:
            if resp.status_code == 200:
                resp.success()

    @task(1)
    def read_drone_health(self):
        """Single-drone health — detail panel click."""
        drone = _random_drone()
        with self.client.get(
            f"/api/drones/{drone}/health", catch_response=True
        ) as resp:
            # 404 is OK — drone may not be registered; only 5xx counts as failure
            if resp.status_code < 500:
                resp.success()
            else:
                resp.failure(f"unexpected {resp.status_code}")


# ---------------------------------------------------------------------------
# Operator user — authenticated, creates missions + submits commands
# ---------------------------------------------------------------------------

class OperatorUser(HttpUser):
    """Simulates a PILOT or ADMIN operator actively managing the fleet."""

    weight = 1
    wait_time = between(1.0, 5.0)

    def on_start(self):
        """Obtain a JWT token at session start."""
        username, password = random.choice(_OPERATORS)
        resp = self.client.post(
            "/api/auth/token",
            json={"username": username, "password": password},
        )
        if resp.status_code == 200:
            self._token = resp.json().get("access_token", "")
            self._headers = {"Authorization": f"Bearer {self._token}"}
        else:
            # Fallback: anonymous (auth disabled in dev/test)
            self._token = ""
            self._headers = {}

        self._created_missions: list[str] = []

    @task(3)
    def submit_command(self):
        """Submit a TAKEOFF or HOLD command to a random SIM drone."""
        drone = _random_drone()
        cmd = random.choice(["TAKEOFF", "HOLD", "LAND"])
        payload = {"drone_id": drone, "command": cmd}
        if cmd == "TAKEOFF":
            payload["params"] = {"alt_m": random.randint(20, 80)}

        with self.client.post(
            "/api/commands",
            json=payload,
            headers=self._headers,
            catch_response=True,
        ) as resp:
            # 202 = accepted; 400 = rejected (preflight fail) — both valid
            if resp.status_code in (202, 400):
                resp.success()
            else:
                resp.failure(f"unexpected {resp.status_code}")

    @task(2)
    def create_mission(self):
        """Create a PATROL mission with 3 random waypoints."""
        mission_type = random.choice(_MISSION_TYPES)
        payload = {
            "type": mission_type,
            "created_by": "locust-operator",
            "config": {"env": "sim"},
            "tasks": [
                {
                    "type": "WAYPOINT_NAV",
                    "waypoints": _random_waypoints(3),
                    "formation": random.choice(["V", "LINE", "CIRCLE"]),
                }
            ],
        }
        with self.client.post(
            "/api/missions",
            json=payload,
            headers=self._headers,
            catch_response=True,
        ) as resp:
            if resp.status_code == 201:
                try:
                    mission_id = resp.json().get("mission_id")
                    if mission_id:
                        self._created_missions.append(mission_id)
                except Exception:
                    pass
                resp.success()
            else:
                resp.failure(f"mission create failed: {resp.status_code} {resp.text[:80]}")

    @task(1)
    def advance_mission(self):
        """Drive a previously created mission through plan → start."""
        if not self._created_missions:
            return
        mission_id = random.choice(self._created_missions)

        # Try to plan it (idempotent failures are OK — mission may already be past PLANNING)
        with self.client.post(
            f"/api/missions/{mission_id}/plan",
            json={},
            headers=self._headers,
            catch_response=True,
        ) as resp:
            if resp.status_code < 500:
                resp.success()

        time.sleep(0.05)

        with self.client.post(
            f"/api/missions/{mission_id}/start",
            json={},
            headers=self._headers,
            catch_response=True,
        ) as resp:
            if resp.status_code < 500:
                resp.success()

    @task(1)
    def read_command_history(self):
        """Query recent command history for a random drone."""
        drone = _random_drone()
        with self.client.get(
            f"/api/commands?drone_id={drone}&limit=10",
            headers=self._headers,
            catch_response=True,
        ) as resp:
            if resp.status_code == 200:
                resp.success()
