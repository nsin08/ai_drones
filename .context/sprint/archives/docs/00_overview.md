# Project Overview: AI-Enabled Drone Fleet Operations MVP

**Last Updated:** February 1, 2026  
**Status:** PoC / MVP Phase  
**Repository:** https://github.com/nsin08/ai_drones

---

## Vision

Build a **software platform for autonomous drone fleet operations** that:
- Simulates multiple drones (10–50+) without hardware
- Coordinates group missions with **role-based autonomy**
- Injects realistic fault modes (RF loss, GNSS multipath, EKF health, battery sag, thrust shortfall)
- Provides **AI-assisted recommendations** (advisory, not autonomous action)
- Demonstrates operator workflows via **Mission Planner SITL** integration

---

## Core Concepts

### 1. Fleet Simulation (No Drones Required)
- Python-based **mock fleet simulator** generates realistic telemetry streams
- **Fault injector** overlays symptom-level faults (not detailed physics)
- MQTT broker relays all events to monitoring and planning layers

### 2. Role-Based Autonomy
Each drone is assigned a **behavior template**:
- **LEADER** — coordinates group pace, holds mission context
- **POINT_MAN** — advances ahead, detects hazards, early warnings
- **WINGMAN** — maintains formation, covers flanks
- **SCOUT** — wider sweep, recon, situational awareness

Roles define **outputs** (what each drone shares) and **constraints** (e.g., battery reserve, maneuver bounds).

### 3. Mission Types (Planner → Plans)
- **PATROL** — linear route, per-drone waypoints with offsets
- **ESCORT** — formation around a moving asset
- **PERIMETER_GUARD** — sector hold + rotation

The **Group Planner** converts an operator intent (mission type + group definition) into per-drone plans and distributes via MQTT.

### 4. AI Recommendations (Advisory)
A **simple rules-based AI** monitors telemetry and fault events, then publishes:
- **Evidence** (what triggered the recommendation)
- **Proposed action** (e.g., "increase RTL battery threshold," "redistribute load," "retreat to safe zone")
- **Confidence** (if applicable)

Operator **ACKs** recommendations via MQTT; system logs all decisions (audit trail).

### 5. Human-in-the-Loop (Mission Planner SITL)
Operator can optionally launch **Mission Planner SITL** on Windows to:
- Visualize a single drone or group
- Execute a mission step manually (upload, guided goto, etc.)
- Demonstrate "realistic" GCS workflow

---

## Tech Stack Layers

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Presentation** | Web Dashboard / Grafana / Mission Planner | Monitoring & manual execution |
| **Application** | Flask (mission control backend) | Command routing, lifecycle mgmt |
| **Messaging** | MQTT (Mosquitto broker) | Pub/sub real-time events |
| **Persistence** | InfluxDB, PostgreSQL, File Storage | Telemetry, mission logs, audit trail |
| **Edge** | ArduPilot autopilot (flight control) | Stabilization, navigation, safety |

---

## Key Artifacts

- **`.context/project/docs/`** — This folder: architecture, missions, roles, safety gates, test plan, runbooks
- **`poc/`** — PoC implementation: domain models, tests, simulators, mission control UI
- **`ops/`** — Docker Compose stack (Mosquitto, InfluxDB, Grafana, Telegraf)
- **`docs/presentations/`** — Technical + executive presentations
- **`integration/`** — MQTT integration demo (simplified topic namespace)

---

## What You Can Demo Today

✅ **Fault models** — RF loss bursts, GNSS multipath, EKF unhealthy, thrust shortfall, battery sag  
✅ **Fleet telemetry loop** — Simulated drones → MQTT → Mission Control UI  
✅ **Command/ACK flow** — Operator command → drone acknowledgment  
✅ **Group missions** — PATROL, ESCORT, PERIMETER_GUARD  
✅ **AI recommendations** — Advisory telemetry analysis + proposed actions  
✅ **Optional Mission Planner SITL** — Manual execution moment (Windows)

---

## Key Decisions (Why This Approach?)

1. **Python + Hexagonal Architecture** → TDD-friendly, domain-focused, testable
2. **MQTT** → Light weight, pub/sub model fits distributed agents naturally
3. **No real drones** → Fast iteration, reproducible faults, no hardware risk
4. **Role templates** → Scale to many drones without per-drone configuration
5. **AI advisory only** → Humans retain authority; system builds trust incrementally

---

## Next Steps

- [ ] Complete fault model tests (coverage > 90%)
- [ ] Finalize group planner logic for all three mission types
- [ ] Build Mission Control UI (browser dashboard)
- [ ] Demo to stakeholders
- [ ] Plan MVP release (real drone integration, production MQTT broker, cloud-based GCS)

---

## Quick Links

- [Architecture & System Design](./03_architecture.md)
- [Mission Types & Workflows](./02_missions_v1.md)
- [Role Definitions](./01_roles_v1.md)
- [MQTT Topic Taxonomy](./04_mqtt_topics.md)
- [Safety Gates & Constraints](./06_safety_and_gates.md)
- [Demo Runbook](./13_demo_runbook.md)
