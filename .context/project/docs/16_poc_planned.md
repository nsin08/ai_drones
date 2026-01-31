Here’s a **POC tech stack** that is **ready-to-demo**, integrates cleanly, and supports **simulation without real drones**. It’s the “MVP demo stack” we’ve been building toward, but tightened into a **POC blueprint** with **what runs where**, **why it exists**, and **demo flow**.

---

## 1) POC Goal (what you should be able to demonstrate)

1. **Simulate a fleet** (10–50 drones) producing telemetry
2. Stream telemetry via **MQTT**
3. Run **fault simulation** (RF loss, GNSS multipath symptoms, EKF unhealthy, thrust shortfall, battery sag)
4. Issue **group intents** (PATROL / ESCORT / PERIMETER_GUARD)
5. Auto-generate **per-role/per-drone plans**
6. Publish **AI recommendations** (advisory only)
7. Optionally show **Mission Planner SITL** to execute a step manually (human-in-loop)

---

## 2) POC Tech Stack by layers (MVP demo direction)

### 2.1 Simulation layer (no drones)

**Default (fast, deterministic)**

* ✅ Python Mock Fleet Simulator (your `fleet_simulator.py`)
* ✅ Python Asset Simulator (for ESCORT)
* ✅ Python Fault Injector (symptom-level realism)

**Optional (more “ArduPilot-real”)**

* ✅ Mission Planner SITL (Windows) for 1 vehicle demo execution
  ArduPilot docs confirm Mission Planner is a GCS and supports SITL simulation workflows.
* ✅ ArduPilot SITL via WSL2 (if you want multi-vehicle realism later)

### 2.2 Ground control layer (human execution)

* ✅ **Mission Planner** (Windows) for manual execution and realism “look”
  ArduPilot describes Mission Planner as a GCS, Windows-only.

### 2.3 Messaging layer (real-time bus)

* ✅ MQTT broker: **Eclipse Mosquitto** (local Docker)
* ✅ Debug UI: **mqtt.cool test client** (publish/subscribe, demos, testing)

### 2.4 Fleet services layer (your “ops platform”)

* ✅ Group Planner (`group_planner.py`)
* ✅ Rules AI Recommender (`simple_rules_ai.py`) — advisory only
* ✅ Topics + JSON schemas (contracts)
* ✅ Operator ACKs via MQTT (optional)

### 2.5 Optional dashboard layer (nice demo polish)

Pick one:

1. **Grafana + InfluxDB** (fast time-series charts)
2. **Node-RED dashboard** (quick UI + flows)
3. Simple web UI (FastAPI + websocket + chart)

For a POC, Node-RED is often the quickest “wow demo”.

---

## 3) “POC components” (exact processes you’ll run)

### 3.1 Required processes (100% POC)

1. Mosquitto broker (docker)
2. `fleet_simulator.py` (raw telemetry)
3. `fault_injector.py` (realism symptoms)
4. `group_planner.py` (intent → plan)
5. `simple_rules_ai.py` (telemetry/events → recommendation)
6. `asset_simulator.py` (ESCORT asset movement)

### 3.2 Optional processes (extra realism)

7. Mission Planner SITL (manual execution demonstration)

---

## 4) Why this stack is “readily demonstrable”

Because it needs only:

* Docker
* Python
* A browser (mqtt.cool)
* Mission Planner (already installed)

No cloud. No drones. No RF hardware.

---

## 5) POC Demo Script (what you do in front of someone)

### 5.1 Setup (2 minutes)

1. Start Mosquitto
2. Start all Python services
3. Open mqtt.cool and subscribe to:

   * `fleet/+/telemetry`
   * `fleet/+/events`
   * `fleet/+/ai/recommendation`
   * `fleet/groups/+/plan/+`
   * `assets/+/pos`

### 5.2 Fleet comes alive (30 seconds)

* Show 12 drones streaming telemetry
* Show periodic fault events (GNSS multipath, RF burst)

### 5.3 Create group + roles (30 seconds)

* Publish retained:

  * `fleet/groups/G01/members`
  * roles for D001..D005

### 5.4 Publish mission intent (1 minute)

* PATROL intent → planner publishes group plan + per-drone plans
* Show:

  * LEADER has FOLLOW_PATH
  * RELAY has ANCHOR_RELAY
  * others have offsets/sectors

### 5.5 Show AI-assisted ops (1 minute)

* Wait for a fault window:

  * AI recommends HOLD/RTL/REDUCE_SPEED with evidence
* Publish ACK (optional)

### 5.6 Optional “Mission Planner moment” (2 minutes)

* Run Mission Planner SITL
* Execute a simple action manually (GUIDED goto / takeoff / RTL) to prove human-in-loop integration

This is exactly aligned with your stated operating model.

---

## 6) POC Integration Points (clear boundaries)

### 6.1 MQTT is the backbone

* **Telemetry**: `fleet/<droneId>/telemetry`
* **Events**: `fleet/<droneId>/events`
* **Intents**: `fleet/groups/<groupId>/intent`
* **Plans**: `fleet/groups/<groupId>/plan/<intentId>`
* **Recommendations**: `fleet/<droneId>/ai/recommendation`

### 6.2 Mission Planner is execution-only in POC

* In the POC: Mission Planner is a **human tool**
* Later: you can add a guarded executor (MAVSDK/MAVLink) after approval

---

## 7) POC “done” checklist (pass/fail)

1. ✅ Can simulate ≥ 12 drones for 10 minutes without crashes
2. ✅ Can inject at least 3 fault types and observe events
3. ✅ Can publish PATROL intent and receive plans
4. ✅ Can run ESCORT with moving asset feed and get plans
5. ✅ AI produces at least 3 recommendation types with evidence
6. ✅ Operator can ACK a recommendation via MQTT
7. (Optional) ✅ Mission Planner SITL runs and you can execute a step manually

---

## 8) Recommended “POC default choices”

To keep it simple and demo-ready:

1. **Mosquitto** (local Docker)
2. **mqtt.cool** for publish/subscribe UI testing
3. **Python scripts** for sim + injection + planner + AI
4. **Mission Planner** for optional SITL + manual execution moment

---

If you want, I can also provide a **single command launcher** for Windows (PowerShell script) that starts:

* docker compose
* 5 python processes
  and prints the exact mqtt.cool subscriptions + publish payloads for the demo.
