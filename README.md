# Drone Fleet Ops MVP (MQTT + Mission Control + Fault Models)

**Last reviewed:** February 1, 2026

This repo contains a **no-hardware** MVP/PoC for drone fleet operations concepts:

- A **fault-model PoC** built with **TDD + hexagonal architecture** (`poc/src/domain/*` + tests).
- A minimal **Mission Control UI** (`poc/mission_control.py`) to visualize and command a simulated fleet over MQTT.
- An **integration demo** (`integration/demo_mqtt.py`) that uses a simpler topic namespace for quick MQTT testing.
- A **presentation suite** for technical + executive audiences (`docs/presentations/00_INDEX.md`).

## What you can demo (today)

- **Fault models** (PoC): RF loss bursts, GNSS multipath, EKF unhealthy, thrust shortfall, battery sag.
- **Fleet telemetry loop**: simulated drones publish to MQTT (`fleet/...`), mission control subscribes and renders in a browser.
- **Command/ACK flow**: mission control publishes `fleet/{id}/command`, companion/sim publishes `fleet/system/command_ack`.

## Repo map (key)

- `docs/presentations/00_INDEX.md` — start here for the full presentation suite.
- `poc/` — PoC domain models + tests + `mission_simulator.py` + `mission_control.py`.
- `integration/` — MQTT integration demo using the `ai_drones/...` topic prefix.
- `ops/` — local stack via Docker Compose (Mosquitto + InfluxDB + Grafana + Telegraf).
- `.context/` — working notes, plans, and draft docs (not required to run the PoC).

## Quick start (Windows)

1) Start infrastructure:
   - `cd ops`
   - `docker compose up -d`

2) Run PoC tests:
   - `cd ..\\poc`
   - `python -m venv .venv`
   - `.venv\\Scripts\\activate`
   - `pip install -r requirements.txt`
   - `pytest tests\\unit -q`

3) Optional: run Mission Control + simulator (uses `fleet/...` topics):
   - Terminal A: `python mission_simulator.py`
   - Terminal B: `python mission_control.py` then open `http://localhost:5000`

## Topic namespaces (important)

- `fleet/...` — used by the PoC mission simulator + mission control + ops ingestion (`ops/telegraf.conf`).
- `ai_drones/...` — used by `integration/demo_mqtt.py` (quick MQTT demo pattern).
