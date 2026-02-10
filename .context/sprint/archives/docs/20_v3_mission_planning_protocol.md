# V3 Mission Planning Protocol

**Last Updated:** February 7, 2026  
**Scope:** Defines JSON payloads and conversion rules for PATROL, PERIMETER, and ESCORT planning in V3. This is the source of truth for mission planning inputs and outputs.

---

## 1) Mission Intent Envelope

All mission plans are sent as a mission intent (used by `/api/mission/plan`).

```json
{
  "mission_type": "PATROL|PERIMETER|ESCORT",
  "group_id": "G01",
  "drone_ids": ["D001","D002"],
  "plan": { }
}
```

**Planner responsibility**
- Mission Control (backend/planner) is the source of truth for formation offsets and per-drone waypoint generation.
- UI only captures raw geometry + parameters and requests a preview.

---

## 1.1) Mission Lifecycle (States)

**States**
- `IDLE` -> no active mission
- `PLANNING` -> operator editing plan
- `PLANNED` -> plan validated, ready to start
- `ACTIVE` -> mission executing
- `PAUSED` -> mission paused (e.g., leader break)
- `ABORTED` -> mission stopped by operator/system
- `COMPLETED` -> mission finished

**State transitions (minimal)**
- `IDLE` -> `PLANNING` on new plan draft
- `PLANNING` -> `PLANNED` on successful `/api/mission/plan`
- `PLANNED` -> `ACTIVE` on `/api/mission/start`
- `ACTIVE` -> `PAUSED` on leader break or operator pause
- `PAUSED` -> `ACTIVE` on `/api/mission/reassign_leader` or operator resume
- `ACTIVE` -> `COMPLETED` on mission completion
- `ACTIVE` -> `ABORTED` on operator abort or safety event

**mission_changed event**
- Emitted on any state change with `mission_state` set to the new state.

---

## 2) PATROL

**Input**
```json
{
  "type": "PATROL",
  "waypoints": [
    {"lat": 28.6139, "lon": 77.2090, "alt_m": 50.0},
    {"lat": 28.6200, "lon": 77.2150, "alt_m": 50.0}
  ],
  "speed_mps": 10.0,
  "loiter_sec": 10
}
```

**Validation**
- Minimum 2 waypoints
- Altitude defaults to 50m if not provided

**Planner Output (per-drone)**
- Leader uses the base route
- Wingman/Scout/Point/Relay get offsets based on role

---

## 3) PERIMETER

**Input**
```json
{
  "type": "PERIMETER",
  "geofence": [
    {"lat": 28.6139, "lon": 77.2090},
    {"lat": 28.6139, "lon": 77.2150},
    {"lat": 28.6200, "lon": 77.2150},
    {"lat": 28.6200, "lon": 77.2090}
  ],
  "alt_m": 60.0,
  "patrol_mode": "LOOP",
  "sectors": 4
}
```

**Validation**
- Polygon must be non-self-intersecting
- Minimum 3 points
- Optional area threshold (configurable)

**Conversion rule (geofence -> patrol path)**
- Planner computes a perimeter loop along the polygon boundary.
- Drones are assigned evenly across `sectors` in clockwise order.
- If `drones > sectors`, multiple drones share a sector (round-robin).
- If `drones < sectors`, only the first `drones` sectors are used.
- For irregular polygons, sector boundaries are based on perimeter length (equal-length segments).
- Each drone gets a waypoint subset corresponding to its sector.

---

## 4) ESCORT

**Input**
```json
{
  "type": "ESCORT",
  "asset_route": [
    {"lat": 28.6139, "lon": 77.2090},
    {"lat": 28.6180, "lon": 77.2140}
  ],
  "formation": {
    "shape": "BOX|CIRCLE|LINE",
    "spacing_m": 30
  },
  "alt_m": 75.0
}
```

**Validation**
- Minimum 2 route points
- `spacing_m` must be > 0
- Formation size validation:
  - BOX: supports up to 8 drones (corners + mid-sides)
  - LINE: supports any number
  - CIRCLE: supports any number (spacing may shrink if too many)

**Planner rule (formation offsets)**
- Mission Control calculates per-role offsets from the asset route.
- Leader stays on the route; wingmen/scouts/point/relay follow role offsets.

---

## 5) Per-Drone Upload Shape

Planner output is translated to `UPLOAD_MISSION` params for each drone:

```json
{
  "command": "UPLOAD_MISSION",
  "params": {
    "waypoints": [
      {"lat": 28.6139, "lon": 77.2090, "alt_m": 50.0}
    ]
  }
}
```
