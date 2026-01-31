# Drone Fleet Ops MVP (ArduPilot + Mission Planner + MQTT + AI Advisory)

## 1. What this MVP is
A local, no-hardware MVP that demonstrates **fleet + group + role-based drone ops** using **MQTT telemetry**, a **planner** that turns mission intents into per-role plans, and an **AI (rules-based in v1)** that publishes **recommendations** (not direct flight commands). Execution is **human/GCS-driven** (Mission Planner), which keeps the MVP safe and credible.

## 2. What you can demo (no real drones)
1) **Individual drones with roles (5)**: LEADER, POINT_MAN, WINGMAN, SCOUT, RELAY  
2) **Group control**: create group G01, assign roles, publish mission intent → get per-drone plans  
3) **Fleet control**: run 12+ simulated drones, monitor telemetry, faults, alerts, recommendations  
4) **Missions v1**: PATROL / ESCORT / PERIMETER_GUARD  
5) **Realistic “missing hardware” effects via fault injection**:
   - RF loss bursts + jitter
   - GNSS multipath symptoms (pos jumps + HDOP spikes)
   - EKF unhealthy flags
   - thrust shortfall symptoms
   - battery sag curves

## 3. Architecture (MVP)
- `fleet_simulator.py` publishes **raw telemetry** → `raw/fleet/<droneId>/telemetry`
- `fault_injector.py` subscribes raw telemetry, injects faults, publishes **normalized telemetry**:
  - `fleet/<droneId>/telemetry`
  - `fleet/<droneId>/events`
- `group_planner.py` consumes group intents + roles + members, emits plans:
  - `fleet/groups/<groupId>/plan/<intentId>`
  - `fleet/<droneId>/plan/<intentId>`
- `asset_simulator.py` publishes moving asset feed for ESCORT:
  - `assets/<assetId>/pos`
- `simple_rules_ai.py` consumes telemetry/events, publishes **recommendations**:
  - `fleet/<droneId>/ai/recommendation`
  - `fleet/groups/<groupId>/ai/recommendation`

> Safety: MVP is **advisory-only**. AI never publishes direct MAVLink/flight commands.

## 4. Repo map
- `docs/12_example_intents.md` – ready-to-publish JSON intents (PATROL/ESCORT/PERIMETER_GUARD)
- `docs/14_mqttcool_steps.md` – exact mqtt.cool subscribe/publish steps for demos
- `ops/` – local mosquitto via docker-compose
- `sim/` – simulators + injector + planner + AI

## 5. Prereqs (Windows)
- Docker Desktop (for Mosquitto broker)
- Python 3.11+ (venv)
- (Optional) Mission Planner installed (for SITL/manual execution)

## 6. Run (local, no drones)
### 6.1 Start MQTT broker
1) `cd ops`
2) `docker compose up -d`

### 6.2 Create venv and install deps
1) `cd sim`
2) `python -m venv .venv`
3) `.venv\Scripts\activate`
4) `pip install -r requirements.txt`

### 6.3 Start the pipeline (open 5 terminals)
1) Raw fleet (12 drones):
   - `python fleet_simulator.py --broker localhost --drones 12 --hz 1`
2) Fault injector:
   - `python fault_injector.py --broker localhost --config config.example.json`
3) Group planner:
   - `python group_planner.py --broker localhost`
4) AI recommender:
   - `python simple_rules_ai.py --broker localhost`
5) Asset sim (for ESCORT demo):
   - `python asset_simulator.py --broker localhost --asset-id ASSET-TRUCK-07 --hz 1 --speed-mps 8 --radius-m 200`

## 7. Demo workflow (mqtt.cool)
1) Connect mqtt.cool to `localhost:1883`
2) Subscribe to:
   - `fleet/+/telemetry`, `fleet/+/events`, `fleet/+/ai/recommendation`
   - `fleet/groups/+/plan/+`, `fleet/groups/+/ai/recommendation`
   - `assets/+/pos`
3) Publish retained:
   - `fleet/groups/G01/members` (5 drones)
   - `fleet/D001..D005/role` (5 roles)
4) Publish one intent to `fleet/groups/G01/intent`:
   - PATROL / ESCORT / PERIMETER_GUARD (see docs/12_example_intents.md)
5) Observe:
   - plans appear under `fleet/groups/G01/plan/<intentId>`
   - telemetry continues; faults/events show up; AI emits recommendations

## 8. Optional: Mission Planner (manual execution)
Use Mission Planner’s simulation/SITL to execute a plan step manually (GUIDED goto / mission upload). This proves “AI recommends → human executes” without hardware.

## 9. MVP success criteria (high-level)
- Plans generated correctly for all 3 missions
- Fault injection triggers events and AI recommendations
- Group roles influence plan structure
- Works with >=20 simulated drones without instability
