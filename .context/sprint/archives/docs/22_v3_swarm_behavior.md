# V3 Swarm Behavior Spec (Demo-First)

**Last Updated:** February 7, 2026  
**Scope:** Defines expected swarm behavior for SwarmSim and UI visualization in the V3 demo.

---

## 1) Formation Model (Demo)

**Offsets**
- LEADER: on route
- WINGMAN: +/- lateral offset
- SCOUT: wider offset arc
- POINT_MAN: forward offset
- RELAY: trailing or anchor offset

**Offset defaults**
- `spacing_m`: 30
- `scout_multiplier`: 2x spacing
- `point_multiplier`: 1.5x spacing

---

## 2) Mission Behavior

**PATROL**
- Drones follow waypoint list with role-based offsets.

**PERIMETER**
- Drones circulate along geofence boundary.
- Each drone covers a sector based on index.

**ESCORT**
- Drones follow the asset route with formation offsets.

---

## 3) Formation Break Rules (Per-Drone)

If a single drone receives **HOLD / RETURN / LAND**:
- That drone exits formation immediately.
- Remaining drones continue the mission (no auto-replan in demo).
- UI shows "OUT OF FORMATION" on that drone.

**Leader behavior**
- If LEADER is commanded HOLD/RETURN/LAND:
  - Mission status switches to "PAUSED"
  - UI prompts operator to reassign LEADER or issue ABORT
  - No automatic RTL for the swarm in demo mode

---

## 4) Swarm Integrity Threshold (Demo)

- If > 40% drones are OUT OF FORMATION for > 10 seconds:
  - Emit an "FORMATION_COMPROMISED" event (UI warning)
  - No automatic command; operator decides

---

## 5) Command Latency (SwarmSim)

- Simulated latency: 100-300 ms (random)
- Command ACKs always issued unless `SIM_FAIL_RATE` > 0
- Optional failure rate for demo realism (default 0%)

---

## 6) Motion Model (Demo-Grade)

**Waypoint navigation**
- Linear interpolation between waypoints at constant speed
- Instant heading changes (no turn rate limit for demo)
- Instant acceleration to cruise speed (no physics)

**Telemetry publishing**
- Rate: 1 Hz per drone (reduce to 0.5 Hz if >15 drones)
- Jitter: ±50 ms random offset per drone (avoid sync bursts)
- Payload size target: ~250 bytes per message (JSON)

**Performance budget**
- 17 drones x 1 Hz x 250 bytes ≈ 4.25 KB/sec telemetry
- Target: <100 ms Socket.IO emit latency under demo load
- Throttle: if client ACK lag >200 ms, reduce telemetry rate by 50%

---

## 7) Battery Simulation (Demo Realism)

- Battery drains at ~0.5% per minute of flight
- Start battery at 85-95% (randomized)
- Emit low-battery warning if <20%
- No recharge logic in demo

---

## 8) Behavior Tests (Demo Acceptance)

- SwarmSim can run 10-17 drones on a laptop without >1s UI lag.
- Per-drone HOLD shows immediate visual break + ACK.
- Leader HOLD pauses mission and prompts reassign.
