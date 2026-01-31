# Windows Simulation & Mocks (No Physical Drones)

You have 3 realistic options on Windows:

## Option A (Fastest): Pure MQTT Mock Fleet
Use sim/ scripts to publish telemetry and faults.
This validates: dashboards, alerts, analytics, AI recommendations, group/fleet orchestration logic.

Run:
- ops/docker compose up -d
- sim/fleet_simulator.py
- sim/fault_injector.py
- sim/simple_rules_ai.py

## Option B (Easiest "ArduPilot behavior"): Mission Planner Simulation
Mission Planner has a built-in Simulation tab to run SITL and fly missions without hardware.
This is ideal for learning missions + parameter effects without risk.
(See ArduPilot Mission Planner Simulation docs.)  [ref]

## Option C (Most controllable, recommended): ArduPilot SITL on Windows via WSL2
ArduPilot recommends running SITL under WSL on Windows.  [ref]
This gives you:
- closer-to-real ArduPilot behavior
- easier multi-vehicle setups
- ability to add simulated failure modes (per ArduPilot SITL docs)  [ref]

### C1) Setup outline (WSL2)
1) Install WSL2 + Ubuntu
2) Follow ArduPilot SITL on Windows (WSL) guide to build and run sim_vehicle.py. [ref]
3) Start SITL (Copter) with map/console.
4) Connect Mission Planner via UDP (typically 14550). [ref]

### C2) Multi-vehicle (fleet without drones)
Preferred approach: run multiple SITL instances and treat each as a droneId.
You can connect Mission Planner to one at a time for execution, while your bridge/sim publishes all to MQTT.

### C3) Simulating the "missing parameters" (without 3D)
Use software fault injection in the telemetry pipeline:
- RF loss/jitter: drop/delay telemetry messages
- GNSS multipath: inject position jumps + hdop spikes
- EKF issues: inject ekf_ok=false events
- thrust shortfall: flatten climb rate and raise current draw
- battery sag: nonlinear battery curve with load

This is what ops systems and AI use to make decisions.

[ref] Mission Planner Simulation: ArduPilot docs
[ref] SITL on Windows using WSL: ArduPilot dev docs
[ref] Using SITL for ArduPilot testing (failure modes): ArduPilot dev docs
[ref] Mission Planner connects to SITL over UDP (14550 typical): ArduPilot/Mission Planner docs
