# Mission Control v4 Interface Storyboard

**Document Type:** UI Source of Truth  
**Status:** Active  
**Last Updated:** 2026-03-01  
**Companion Doc:** `V4_ARCHITECTURE.md`

---

## Purpose

This document defines the v4 UI direction.

It is aligned to current priorities:

- Functional mission control first
- Hardware safety first
- Router and page structure are required in v4
- Authentication and authorization are planned, but are not the first delivery gate
- Multi-mission is visible in the UI model, but not functionally enabled in the first delivery slice

This file and `V4_ARCHITECTURE.md` are the only v4 source-of-truth docs.

---

## Product Positioning

### What v4 is now

- A development-track system aimed to become production-ready
- A safer, more structured replacement path for the current v3 single-page shell
- A functional operator console focused on command safety, telemetry clarity, persistence, and deployment separation

### What v4 is not yet

- Not full production hardening
- Not full multi-mission execution
- Not full admin platform
- Not full identity platform

---

## UI Priorities

### P0

- Router and page shell migration
- Dashboard command flow
- Fleet health visibility
- Mission planning UI for single active mission workflows
- Command history and feedback timeline
- Environment visibility (SIM vs HARDWARE) as deployment state

### P1

- Auth UI and login gating
- Settings for operator and thresholds
- Multi-mission presentation

### Deferred

- Password reset
- Email invite flows
- API key management
- Backup and restore UI
- Full multi-mission execution controls

---

## Routing Baseline

v4 must stop treating routing as optional. The first frontend change is the app-shell split.

```jsx
<BrowserRouter>
  <Routes>
    <Route element={<AppShell />}>
      <Route index element={<Navigate to="/dashboard" replace />} />
      <Route path="dashboard" element={<DashboardPage />} />
      <Route path="missions" element={<MissionsPage />} />
      <Route path="fleet" element={<FleetPage />} />
      <Route path="commands" element={<CommandsPage />} />
      <Route path="settings" element={<SettingsPage />} />
    </Route>
    <Route path="login" element={<LoginPage />} />
  </Routes>
</BrowserRouter>
```

### Notes

- `AppShell` owns socket connection lifecycle and shared layout
- `TopBar` remains persistent across authenticated routes
- Deep links are required for `/missions`, `/fleet`, and `/commands`
- Route-level auth guards can be introduced later without changing the route map

---

## UI State Assumptions

- Existing Zustand stores remain global
- Socket connection is created once in `AppShell`
- Data remains real-time via Socket.IO for now
- REST remains the source for history, filtering, and page hydration

This keeps v4 incremental instead of forcing a full client rewrite.

---

## Safety Rules Shown In UI

The UI must reflect one normalized safety policy everywhere.

### Normalized Defaults

- `BATTERY_ARM_MIN_PCT = 10`
- `GPS_ARM_MIN_SATS = 4`
- `STALE_TIMEOUT_SEC = 30`
- `COMMAND_ACK_TIMEOUT_SEC = 5`
- `COMMAND_MAX_RETRIES = 3`
- Retry backoff: `1s, 2s, 4s`

### Command Rules

- `ARM` is blocked if battery is below 10%
- `ARM` is blocked if GPS satellites are below 4
- `ARM` is blocked if EKF is unhealthy
- `ARM` is blocked if the drone is already armed
- Queued commands must never auto-run without revalidation

### Health Colors

- `GREEN`: score `>= 0.70`
- `YELLOW`: score `>= 0.30` and `< 0.70`
- `RED`: score `< 0.30`
- `GREY`: stale or offline

---

## Environment Model

The UI must match the deployment model already present in ops:

- `ops/docker-compose.yml` is the simulator-oriented stack
- `ops/docker-compose.hardware.yml` is the hardware integration stack

Therefore:

- Environment is a deployment-level mode, not a runtime operator toggle
- The UI shows the current environment as a read-only badge from backend config
- Optional UI filtering by source is allowed, but it must not switch the backend between SIM and HARDWARE

### UI Behavior

- Show `SIM` or `HARDWARE` badge in `TopBar`
- Show clear label on fleet cards: `SIM-*` vs `HW-*`
- Reject any UI pattern that implies an operator can flip the running backend between environments

---

## Page Storyboards

### 1. `/dashboard` - Live Operations

**Purpose:** Command drones safely and monitor live telemetry.

**Primary users:** Pilot, Observer

**Core layout**

```text
+-------------------------------------------------------------------+
| TopBar: Logo | Dashboard | Missions | Fleet | Commands | Settings |
| Env: HARDWARE | MQTT: Connected | User | Role | Logout            |
+-----------+-------------------------------------+-----------------+
| Left      | CenterMap                           | Right           |
| Fleet     | live drones, trails, mission area   | Quick actions   |
| Roster    | waypoint preview, home marker        | Command queue   |
| Health    |                                     | Alerts          |
+-----------+-------------------------------------+-----------------+
| BottomStrip: altitude | battery | event timeline                  |
+-------------------------------------------------------------------+
```

**P0 features**

- Live drone markers
- Fleet health badges
- Preflight modal before `ARM`
- Command feedback states: `REQUESTED`, `RETRYING`, `ACKED`, `FAILED`
- Alert modal for battery critical, signal loss, EKF unhealthy

**Not in first functional slice**

- True concurrent multi-mission controls

---

### 2. `/missions` - Mission Planning

**Purpose:** Build and save mission plans.

**Primary users:** Planner, Pilot

**Scope for first delivery**

- Single mission planning and editing
- Save and load mission templates
- Visual mission history

**Important constraint**

- The UI may show future-ready multi-mission concepts, but active execution remains single-mission first
- If multi-mission cards are shown, label them as future or read-only where needed

**Core layout**

```text
+-------------------------------------------------------------------+
| TopBar                                                            |
+-------------------------------------------------------------------+
| Active Mission Summary                                            |
| One active mission card with status, ETA, pause, abort            |
+-------------------------------------------------------------------+
| Mission Builder                                                   |
| Type | Formation | Altitude                                       |
| Map for waypoint editing | Assigned drones                        |
| Geofence tools | Validation | Save template | Start planned        |
+-------------------------------------------------------------------+
| Mission History                                                   |
| Filterable list of prior missions                                 |
+-------------------------------------------------------------------+
```

**P0 features**

- Add waypoint by click
- Drag waypoint to adjust
- Draw geofence
- Formation selector
- Save mission
- Load mission
- Undo and redo

**P1 features**

- Estimated battery consumption
- Task decomposition preview
- Multi-mission list view

---

### 3. `/fleet` - Fleet Health

**Purpose:** Inspect drone readiness and health.

**Primary users:** Supervisor, Maintenance

**Core layout**

```text
+-------------------------------------------------------------------+
| TopBar                                                            |
+-------------------------------------------------------------------+
| Fleet summary: total | green | yellow | red | offline             |
+-------------------------------------------------------------------+
| Drone cards / expandable rows                                     |
| Health score | telemetry | preflight snapshot | source | actions   |
+-------------------------------------------------------------------+
| Aggregates: battery trend | GPS count | signal | EKF issues        |
+-------------------------------------------------------------------+
```

**P0 features**

- Health score per drone
- Preflight snapshot panel
- Environment/source label
- Fast operator visibility for unsafe drones

**P1 features**

- Bulk maintenance actions

---

### 4. `/commands` - Command History

**Purpose:** Show persistent command audit and detailed command outcomes.

**Primary users:** Pilot, Admin

**Core layout**

```text
+-------------------------------------------------------------------+
| TopBar                                                            |
+-------------------------------------------------------------------+
| Filters: drone | status | command | date | operator               |
+-------------------------------------------------------------------+
| Command log table                                                 |
| Time | Command ID | Drone | Command | Status | Retries | Operator |
+-------------------------------------------------------------------+
| Command detail                                                    |
| Timeline: requested -> sent -> acked -> state changed             |
| Preflight values | ACL result | failure reason                    |
+-------------------------------------------------------------------+
```

**P0 features**

- Persistent history
- Filters
- Retry visibility
- Failure reason display
- Detail timeline

**P1 features**

- CSV export
- Resend controls for privileged roles

---

### 5. `/settings` - System Settings

**Purpose:** Show deployment config and expose only the minimum useful controls.

**Primary users:** Admin

This page must be intentionally narrow in the first version.

**P0 features**

- Read-only environment display
- MQTT / database / inventory health indicators
- Threshold display and edit for safety values
- Optional basic operator list when auth is enabled

**Deferred from storyboard v1**

- Invite by email
- Password reset workflow
- API keys
- Backup/restore UI
- Full user CRUD lifecycle

**Core layout**

```text
+-------------------------------------------------------------------+
| TopBar                                                            |
+-------------------------------------------------------------------+
| Deployment                                                        |
| Environment: SIM or HARDWARE (read-only from backend config)      |
| MQTT | Database | Inventory status                                |
+-------------------------------------------------------------------+
| Safety thresholds                                                 |
| Battery arm min | GPS arm min | stale timeout | retries | timeout |
+-------------------------------------------------------------------+
| Operators (optional, basic)                                       |
| username | role | assigned scope                                  |
+-------------------------------------------------------------------+
```

---

## Component Reuse Strategy

| Page | TopBar | CenterMap | FleetRoster | CommandQueue | BottomStrip |
|------|--------|-----------|-------------|--------------|-------------|
| `/dashboard` | Yes | Yes | Yes | Yes | Yes |
| `/missions` | Yes | Yes | Yes | No | No |
| `/fleet` | Yes | No | Yes | No | No |
| `/commands` | Yes | No | Optional filter only | No | No |
| `/settings` | Yes | No | No | No | No |

### Notes

- `CenterMap` becomes dual-mode: monitor mode and edit mode
- `TopBar` gains route navigation and environment badge
- `CommandQueue` remains primarily dashboard-scoped

---

## Delivery Sequence

### Phase 1: Router Foundation

1. Install and wire `react-router-dom`
2. Create `AppShell`
3. Move current `App.jsx` behavior into `DashboardPage`
4. Keep Socket.IO connection in `AppShell`

### Phase 2: Page Extraction

1. Extract `FleetPage`
2. Extract `CommandsPage`
3. Extract `MissionsPage`
4. Add minimal `SettingsPage`

### Phase 3: Functional UI

1. Mission builder interactions
2. Fleet health presentation
3. Command timeline detail
4. Threshold display and environment badge

### Phase 4: Auth Layer

1. Add `LoginPage`
2. Add route protection
3. Add role-based UI visibility

This ordering is required. Router migration is not optional and cannot be left implicit.

---

## Suggested Code Layout

To reduce v3 risk, prefer side-by-side v4 implementation instead of overwriting the current shell immediately.

### Frontend

- `ui/src/v4/AppShell.jsx`
- `ui/src/v4/pages/`
- `ui/src/v4/components/`
- `ui/src/v4/routes.jsx`

### Backend

- `poc/v4_mission_control/` for new backend package
- Keep `poc/mission_control_v3.py` unchanged during early v4 development

This is the safest way to avoid v3 regression while the v4 contract is still moving.

---

## Source Links

- Architecture: `V4_ARCHITECTURE.md`
- Current UI entrypoint: `ui/src/App.jsx`
- Current deployment stacks: `ops/docker-compose.yml`, `ops/docker-compose.hardware.yml`
