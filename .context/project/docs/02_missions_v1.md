# Mission Types & Workflows v1

**Last Updated:** February 1, 2026  
**Scope:** MVP missions (PATROL, ESCORT, PERIMETER_GUARD)

---

## Overview

A **mission** is an **operator intent** that specifies:
- **Mission type** (PATROL | ESCORT | PERIMETER_GUARD)
- **Group** (list of drone IDs + role assignments)
- **Parameters** (route, asset, sector, speed, duration, etc.)

The **Group Planner** converts this intent into **per-drone plans** (lists of MAVLink commands/waypoints) and publishes them over MQTT for execution.

---

## Mission Type: PATROL

**Purpose:** Linear route surveillance with formation discipline.

### Definition

```python
{
  "mission_id": "M001",
  "type": "PATROL",
  "group_id": "G01",
  "route": [
    {"lat": 40.7128, "lon": -74.0060},  # Start
    {"lat": 40.7200, "lon": -74.0150},  # Waypoint 2
    {"lat": 40.7100, "lon": -74.0100}   # Return
  ],
  "speed_mps": 10.0,
  "parameters": {
    "loiter_time_sec": 30,
    "height_agl_m": 50
  }
}
```

### Planner Output (per-drone plan)

For a PATROL mission with group `[drone_1 (LEADER), drone_2 (WINGMAN), drone_3 (SCOUT)]`:

**drone_1 (LEADER):**
```
1. Takeoff (height_agl_m)
2. Goto (route[0]) at speed_mps
3. Goto (route[1]) at speed_mps
4. Loiter (loiter_time_sec)
5. Goto (route[2]) at speed_mps
6. Land
```

**drone_2 (WINGMAN):**
```
1. Takeoff
2. Goto (route[0] + offset: [+50m, 0]) — maintain flank position
3. Goto (route[1] + offset: [+50m, 0])
4. Loiter (loiter_time_sec)
5. Goto (route[2] + offset: [+50m, 0])
6. Land
```

**drone_3 (SCOUT):**
```
1. Takeoff
2. Goto (route[0] + offset: [+100m, +100m]) — wider arc
3. Goto (route[1] + offset: [+100m, +100m])
4. Loiter (loiter_time_sec)
5. Goto (route[2] + offset: [+100m, +100m])
6. Land
```

### Safety Rules

- LEADER flies closest to nominal route
- WINGMAN maintains strict formation (breach triggers alert)
- SCOUT has wider tolerance but must stay within geofence
- All drones monitor battery; if any falls below threshold, group transitions to RTL

### Expected Telemetry

- `fleet/{id}/telemetry` — periodic position, speed, battery, heading
- `fleet/{id}/events` — waypoint reached, mode change, low battery
- `fleet/groups/{group_id}/status` — group formation integrity, RTL readiness

---

## Mission Type: ESCORT

**Purpose:** Formation flight around a moving asset (e.g., VIP transport, mobile asset).

### Definition

```python
{
  "mission_id": "M002",
  "type": "ESCORT",
  "group_id": "G01",
  "asset": {
    "id": "ASSET_A",
    "topic": "fleet/assets/ASSET_A/position"  # Subscribe for live updates
  },
  "formation": {
    "shape": "box",  # or "circle", "line"
    "spacing_m": 30
  },
  "parameters": {
    "height_agl_m": 75,
    "maintain_distance_m": 50,
    "speed_follow_mps": null  # Adaptive to asset
  }
}
```

### Planner Output (per-drone plan)

For ESCORT with roles [POINT_MAN, WINGMAN, WINGMAN, SCOUT]:

**POINT_MAN (forward):**
```
1. Takeoff
2. Subscribe to fleet/assets/ASSET_A/position
3. Maintain position [asset.lat + 50m_north, asset.lon] at height_agl_m
4. If asset moves > 5 m/s, adjust to keep 50 m ahead
5. Monitor battery
6. RTL on abort
```

**WINGMAN (left flank):**
```
1. Takeoff
2. Subscribe to fleet/assets/ASSET_A/position
3. Maintain position [asset.lat, asset.lon - 30m_west] at height_agl_m
4. Follow asset lateral movement
5. Strict formation adherence (alert on > 10m deviation)
6. RTL on abort
```

**WINGMAN (right flank):**
```
1. Takeoff
2. Subscribe to fleet/assets/ASSET_A/position
3. Maintain position [asset.lat, asset.lon + 30m_east] at height_agl_m
4. Follow asset lateral movement
5. Strict formation adherence (alert on > 10m deviation)
6. RTL on abort
```

**SCOUT (wide rear):**
```
1. Takeoff
2. Subscribe to fleet/assets/ASSET_A/position
3. Maintain position [asset.lat - 100m_south, asset.lon] at height_agl_m
4. Monitor rear approach vector (early warning for threats)
5. Wider tolerance for position (50 m deviation ok)
6. RTL on abort
```

### Safety Rules

- Asset position updates must be **fresh** (< 2 sec old); stale data triggers safe hold
- If any drone loses comms > 30 sec, formation breaks and units RTL independently
- Battery threshold for ESCORT is **higher** (avoid formation breakup mid-task)
- POINT_MAN has highest risk tolerance; WINGMAN has lowest

### Expected Telemetry

- `fleet/{id}/telemetry` — real-time drone position relative to asset
- `fleet/assets/{asset_id}/position` — asset location (mocked or from external feed)
- `fleet/groups/{group_id}/formation_integrity` — distance to leader, spacing breaches
- `fleet/{id}/events` — comms loss, formation breach, battery critical

---

## Mission Type: PERIMETER_GUARD

**Purpose:** Sector-based surveillance with rotation/relief pattern.

### Definition

```python
{
  "mission_id": "M003",
  "type": "PERIMETER_GUARD",
  "group_id": "G01",
  "perimeter": {
    "center": {"lat": 40.7150, "lon": -74.0100},
    "radius_m": 500,
    "sectors": 4  # Divide perimeter into 4 sectors
  },
  "parameters": {
    "height_agl_m": 60,
    "speed_mps": 8,
    "loiter_time_per_sector_sec": 120,
    "relief_interval_min": 30  # Rotate drones every 30 min
  }
}
```

### Planner Output (per-drone plan)

For PERIMETER_GUARD with 4 sectors and drones [drone_1, drone_2, drone_3, drone_4, drone_5]:

**Sector assignment (Batch 1, 0–30 min):**

| Drone | Sector | Role | Loiter Points |
|-------|--------|------|---|
| drone_1 | Sector 0 (North) | LEADER | [corner 0, corner 1] |
| drone_2 | Sector 1 (East) | WINGMAN | [corner 1, corner 2] |
| drone_3 | Sector 2 (South) | WINGMAN | [corner 2, corner 3] |
| drone_4 | Sector 3 (West) | SCOUT | [corner 3, corner 0] |
| drone_5 | Staging (center) | LEADER | Loiter at perimeter center |

**drone_1 (Sector 0, first 30 min):**
```
1. Takeoff
2. Goto corner_0 (NW of perimeter)
3. Loiter (120 sec)
4. Goto corner_1 (NE of perimeter)
5. Loiter (120 sec)
6. Repeat until relief_interval_min reached
7. Return to staging point
```

**drone_5 (Staging, monitoring):**
```
1. Takeoff
2. Loiter at perimeter center
3. Monitor all sector drones for health
4. Alert on battery/comms/anomalies
5. At relief_interval_min, issue handoff signal
6. Land or transition to next duty
```

### Relief Pattern (30 min intervals)

- At t=30 min: drone_1 returns to staging, drone_5 assumes Sector 0 (LEADER)
- At t=60 min: drone_2 returns to staging, drone_1 assumes Sector 1 (WINGMAN)
- Cycle continues until mission abort or manual override

### Safety Rules

- **Single sector breach** → alert operator, but continue
- **Two+ sectors unmonitored** → mission aborts (perimeter integrity lost)
- **Any drone battery < threshold** → immediate relief, no waiting for interval
- **Comms loss on active sector** → staging drone takes over within 10 sec

### Expected Telemetry

- `fleet/{id}/telemetry` — per-sector drone position and status
- `fleet/groups/{group_id}/perimeter_status` — coverage (which sectors monitored), relief timer
- `fleet/{id}/events` — sector entry/exit, relief handoff, battery alert
- `fleet/groups/{group_id}/events` — perimeter breach alerts, sector coverage loss

---

## Mission State Machine

```
┌──────────┐
│ CREATED  │  (operator submits mission)
└─────┬────┘
      │
      ▼
┌──────────────┐
│ PLANNED      │  (planner converts to per-drone plans)
└─────┬────────┘
      │
      ▼
┌──────────────┐
│ ARMED        │  (drones arm, preflight checks pass)
└─────┬────────┘
      │
      ▼
┌──────────────┐
│ IN_PROGRESS  │  (drones executing waypoints)
└─────┬────────┘
      │
      ├─────────────────────────┐
      │                         │
      ▼                         ▼
┌──────────────┐        ┌──────────────┐
│ SUSPENDED    │        │ ABORT        │  (operator or fault triggers RTL)
└─────┬────────┘        └──────┬───────┘
      │                        │
      ▼                        ▼
┌──────────────────────────────────────┐
│ RECOVERED / COMPLETED                │
└──────────────────────────────────────┘
```

### Transition Rules

| From | To | Trigger | Owner |
|------|----|---------|----|
| CREATED | PLANNED | Planner validates intent + group | System |
| PLANNED | ARMED | Operator confirms, drones preflight ok | Operator + System |
| ARMED | IN_PROGRESS | Drones report "armed" state | System |
| IN_PROGRESS | SUSPENDED | Operator pause request | Operator |
| SUSPENDED | IN_PROGRESS | Operator resume request | Operator |
| IN_PROGRESS | ABORT | Comms loss > 60 sec OR fault severity high | System (auto) + Operator (manual) |
| ABORT | RECOVERED | All drones safe on ground or RTL complete | System |

---

## Mission Abort Criteria (Auto-Triggered)

1. **Comms Loss > 60 seconds** on > 50% of group drones → RTL all
2. **Geofence Breach** by > 2 drones → RTL all
3. **Battery Critical** on LEADER → RTL all
4. **Perimeter Coverage Loss** (PERIMETER_GUARD only) → RTL all
5. **Formation Integrity Loss** (ESCORT only, > 50% spacing breach) → RTL all

---

## Mission Log & Audit Trail

Every mission records:
```
{
  "mission_id": "M001",
  "timestamps": {
    "created": "2026-02-01T10:00:00Z",
    "planned": "2026-02-01T10:01:00Z",
    "armed": "2026-02-01T10:02:00Z",
    "in_progress": "2026-02-01T10:03:00Z",
    "completed": "2026-02-01T10:30:00Z"
  },
  "group_id": "G01",
  "drones": ["drone_1", "drone_2", "drone_3"],
  "events": [
    {"time": "10:05:00", "type": "waypoint_reached", "drone_id": "drone_1", "wp_index": 1},
    {"time": "10:12:00", "type": "battery_alert", "drone_id": "drone_2", "battery_pct": 25},
    {"time": "10:30:00", "type": "mission_complete", "drones_landed": 3}
  ],
  "decisions": [
    {"time": "10:12:00", "type": "relief_initiated", "outgoing": "drone_1", "incoming": "drone_5"}
  ]
}
```

---

## Next Steps

- [ ] Implement `group_planner.py` with PATROL, ESCORT, PERIMETER_GUARD logic
- [ ] Add per-mission telemetry validators (geofence, formation, perimeter coverage)
- [ ] Build mission state machine enforcement
- [ ] Create test scenarios for all three mission types
- [ ] Document operator workflows for each mission type
