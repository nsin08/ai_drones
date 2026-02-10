# V3 Mission Control SPA - UI Spec (React + Vite)

**Last Updated:** February 7, 2026  
**Scope:** Visual layout, component tree, data flow, and operator workflow for the v3 Mission Control SPA.

**Single source of truth:** This doc is the UI source of truth for V3. API + mission protocols are in:
- `.context/project/docs/19_v3_api_contract.md`
- `.context/project/docs/20_v3_mission_planning_protocol.md`
- `.context/project/docs/21_v3_command_state_machine.md`
- `.context/project/docs/22_v3_swarm_behavior.md`

---

## 0) UI Progress Tracker

- [ ] SPA scaffolded (React + Vite) with dark theme
- [ ] Map renders + layers toggle (tiles, trails, overlays)
- [ ] Fleet roster (inventory + telemetry-only) + selection
- [ ] Per-drone commands + command queue (ACK/FAILED/TIMEOUT)
- [ ] Bulk swarm commands (1 confirm + `cmd_group_id` progress)
- [ ] Mission planning tools (PATROL waypoints, PERIMETER geofence, ESCORT route)
- [ ] Visual formation break states (HOLD/RTL/LAND) on map + roster

---

## 1) Layout (3-panel + timeline)

**Top Bar (global status)**
- Mission state, active drones, alerts, link status, time.
- Global actions: **Pause / Resume / Abort** (confirm required).

**Left Panel (Mission + Fleet)**
1) Mission Setup
   - Mission type (PATROL / ESCORT / PERIMETER)
   - Params: duration, speed, altitude band
   - Formation template
2) Fleet Roster
   - List of drones with battery, mode, status
   - Multi-select (swarm actions)
3) Roles & Assign
   - Bulk role assignment + apply

**Center Panel (Map)**
- Live map with:
  - Role-colored markers
  - Trails
  - Geofence
  - Planned route/waypoints
- Click drone -> mini card (battery, mode, last seen)

**Right Panel (Commands + Events)**
1) Command Queue
   - Pending / ACK / Failed
2) Quick Actions
   - HOLD / RETURN / LAND
   - Individual + swarm (confirm for bulk)
3) Recommendations (optional)
   - Approve / Ignore
4) Leader Controls (when mission_state=PAUSED)
   - Reassign LEADER (dropdown) -> `/api/mission/reassign_leader`

**Bottom Strip (Timeline + Charts)**
- Altitude + battery trends
- Mission events timeline (faults, role changes, warnings)

---

## 2) Mission Planning Tools (Map)

Mission planning is done directly on the map with simple draw/edit tools. The output of planning is used to publish per-drone `UPLOAD_MISSION` commands (SITL/hardware) or to drive SwarmSim behavior (demo scale).

**Common map tools**
- Add waypoint (click-to-drop), drag-to-move, delete
- Draw polyline (route), draw polygon (geofence), edit geometry
- Undo/redo (nice-to-have), clear/reset

**PATROL**
- Operator creates a waypoint list on the map (minimum: 2 waypoints).
- Left panel shows an editable waypoint table (lat/lon/alt + optional speed/loiter).
- Plan preview overlays:
  - Waypoint markers + route polyline
  - Formation preview (role-based offsets) for selected swarm

**PERIMETER**
- Operator draws a geofence polygon on the map.
- System previews sector assignments (optional) and patrol loops for GUARD/SCOUT roles.
- Validation: polygon must be non-self-intersecting; minimum area threshold (configurable).

**ESCORT**
- Operator draws an asset route polyline (or selects a live asset feed later).
- Operator selects formation template (box/circle/line) + spacing.
- Plan preview overlays:
  - Asset route
  - Leader path + follower offset paths

**Plan/Start actions (UI)**
- `Plan`: dry-run preview + validation errors in UI.
- `Start`: publishes per-drone missions/commands and switches UI to "execute/monitor" mode.

---

## 3) Fleet Roster + Inventory

**Roster sources**
- Initial load: `GET /api/inventory` (known drones + metadata).
- Realtime: `telemetry_update` adds/refreshes drones; drones not present in inventory are shown as "telemetry-only".

**What the operator can do**
- Multi-select drones for swarm actions.
- Filter by role/status/battery/last_seen.
- Assign roles:
  - Per-drone role dropdown
  - Bulk role assignment for selected drones (manual confirm not required for SET_ROLE)

**Swarm actions**
- Selected swarm actions target either the current selection or "all active".
- Bulk actions require 1 manual confirm and show group progress via `cmd_group_id`.

---

## 4) Component Tree (React)

- `AppShell`
  - `TopBar`
  - `LeftPanel`
    - `MissionSetupCard`
    - `FleetRoster`
    - `RoleAssignment`
  - `CenterMap`
    - `DroneMarkers`
    - `RouteOverlay`
    - `GeofenceOverlay`
  - `RightPanel`
    - `CommandQueue`
    - `QuickActions`
    - `RecommendationFeed` (optional)
  - `BottomStrip`
    - `AltitudeChart`
    - `BatteryChart`
    - `EventTimeline`
  - `ConfirmDialog` (global)

---

## 5) Client State (Redux/Zustand)

**Core slices**
- `missions`: current mission, params, status
- `fleet`: drones (telemetry + inventory)
- `selection`: selected drones (for swarm actions)
- `commands`: pending/acked/failed commands
- `events`: warnings, faults, timeline entries
- `ui`: dialogs, filters, map options

---

## 6) Data Flow (Realtime)

**Socket/WebSocket**
- `telemetry_update` -> update `fleet`
- `command_ack` -> update `commands`
- `mission_changed` -> reset UI state
- `leader_election` -> update `events`
 - `mission_changed` includes `mission_state` for top bar

**REST**
- `GET /api/missions`
- `POST /api/mission/assign`
- `POST /api/command/{hold|return|disable|enable|set_role}`
- `GET /api/inventory`

---

## 7) Command Confirmation + Formation Break

**Confirm required**
- DISABLE/LAND, RETURN/RTL, CLEAR_MISSION
- Any **bulk** (swarm) command

**One-click**
- HOLD
- ARM/ENABLE
- SET_ROLE

**Bulk commands**
- UI shows 1 confirm for N drones
- Backend publishes N commands with shared `cmd_group_id`

### 7.1) Confirmation Dialog UX

**Trigger**
- Any bulk command
- Any destructive single command (DISABLE/LAND, RETURN/RTL, CLEAR_MISSION)

**Dialog content**
- Title: "Confirm {COMMAND}"
- Body: "Send {COMMAND} to {N} drones? This action {effect}."
- Drone list: show first 5, then "+N more"
- Buttons: [Cancel] [Confirm]

**Behavior**
- Esc key / outside click -> Cancel
- Confirm sends immediately (no debounce)
- Auto-closes on response or after 2s (if backend does not respond)

**Formation break (per-drone)**
- If a single drone is commanded HOLD/RETURN/LAND, that drone exits formation; the rest continue unless the operator triggers a replan.
- UI reflects this immediately on ACK and/or subsequent telemetry:
  - Marker ring/icon reflects mode (HOLD / RTL / LAND)
  - Trail style switches to "out-of-formation"
  - Roster shows an "OUT OF FORMATION" chip + last command result

**Late ACK display**
- If `command_ack.late=true`, show a "LATE ACK" badge and keep the TIMEOUT warning for operator clarity.

---

## 8) Visual Design

**Style**
- Dark theme, neon accents (cyan, magenta, amber)
- Role colors consistent across map + list + charts

**Visual priorities**
1) Map clarity
2) Fleet health visibility
3) Command confidence (ACK vs FAILED)

---

## 9) Demo Mode (SwarmSim + SITL)

**SwarmSim**
- Feeds 10-17 drones (visual density)
- Same MQTT topics as SITL

**SITL**
- 3-5 drones for "real" MAVLink control

---

## 10) Open Implementation Notes

- Tile source: OSM in online mode; local tiles later.
- Ensure map updates don't block UI (debounce updates).
- Cap per-drone trail length (e.g., last 100 points).
