# V4 UI Redesign — Analysis & Proposal

**Author:** AI Agent (Copilot)  
**Date:** 2026-01-31  
**Scope:** Analysis only — no code changes  
**Status:** Draft for review

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Current State Audit](#2-current-state-audit)
3. [Critical Issues](#3-critical-issues)
4. [Page-by-Page Analysis](#4-page-by-page-analysis)
5. [Proposed Information Architecture](#5-proposed-information-architecture)
6. [Proposed Page Designs](#6-proposed-page-designs)
7. [Cross-Cutting Improvements](#7-cross-cutting-improvements)
8. [Implementation Priority](#8-implementation-priority)
9. [Migration Strategy](#9-migration-strategy)

---

## 1. Executive Summary

The v4 UI was built incrementally across sprints W10–W15: a routed shell (`AppShell`) was wrapped around the existing v3 single-page dashboard, and five new pages were added (Missions, Mission Builder, Fleet, Commands, Settings). The result is **two disconnected systems** running side-by-side:

| Aspect | v3 (Dashboard embed) | v4 (routed pages) |
|--------|----------------------|---------------------|
| Real-time data | Socket.IO → Zustand stores | Stores exist but **socket is never initialized** |
| Mission planning | Full flow (drone select → plan → start) | Isolated local state, POST only |
| Fleet interaction | Searchable roster with selection, role changes | Read-only health table |
| Commands | Live queue with status dots, ack badges | Static history table |
| Map | Full Leaflet with drone markers, trails, overlays | Fixed-height map with gray tile bug |

**The v4 pages are currently a downgrade from v3.** The proposal below consolidates the best of both into a coherent, operator-focused UI.

---

## 2. Current State Audit

### 2.1 Technology Stack

| Component | Library | Version |
|-----------|---------|---------|
| Framework | React | 18.x |
| Routing | React Router | v6 |
| State | Zustand | 6 stores (fleet, command, mission, event, selection, ui) |
| Maps | Leaflet + React-Leaflet | 1.9 / 4.x |
| Charts | Recharts | (altitude, battery) |
| HTTP | Axios | (api.js shared client) |
| Real-time | Socket.IO client | **NOT initialized in v4 tree** |
| Build | Vite | dev proxy configured |
| CSS | Global CSS (theme.css + App.css + v4.css) | No modules, no scoping |

### 2.2 Current Navigation Structure

```
/                → redirect → /dashboard
/dashboard       → v3 embedded (LeftPanel + CenterMap + RightPanel + BottomStrip)
/missions        → read-only mission summary (Zustand missionStore)
/mission-builder → standalone planner (local useState, axios.post)
/fleet           → health table (Zustand fleetStore)
/commands        → command history table (Zustand commandStore)
/settings        → static config display (constants only)
/login           → placeholder (no form)
```

### 2.3 Component Inventory

**Actively functional (v3 origin):**
- `CenterMap` — full Leaflet map with drone markers, trails, planning overlays, click-to-add waypoints
- `FleetRoster` — searchable/filterable drone list with selection, role changes, battery indicators
- `MissionSetup` — mission type selection, home base, Plan/Start/Reset flow
- `QuickActions` — HOLD, RETURN, ARM, DISARM, etc. with confirmation dialogs
- `CommandQueue` — live command feed with status dots, late-ack badges, time-since
- `BottomStrip` — tabbed charts (Altitude, Battery, Events)
- `TopBar` — mission state badge, drone counts, Pause/Resume/Abort buttons

**Partially functional (v4 new):**
- `MissionBuilderMap` — Leaflet map for waypoint/geofence creation (gray tile bug)
- `WaypointList` — ordered list with reorder/delete/altitude
- `GeofenceEditor` — point list with delete/clear
- `FormationSelector` — shape + spacing picker

**Placeholder / static (v4 new):**
- `MissionsPage` — shows stale store values, no interactivity
- `SettingsPage` — hardcoded safety thresholds, no live data
- `LoginPage` — no form, no auth flow

### 2.4 Zustand Stores

| Store | Populated by | Consumers (v3) | Consumers (v4) |
|-------|-------------|-----------------|-----------------|
| `fleetStore` | socket.io `telemetry_update` | CenterMap, FleetRoster, TopBar, BottomStrip, QuickActions, MissionSetup | FleetPage |
| `commandStore` | socket.io `command_ack`, `command_requested` | CommandQueue | CommandsPage |
| `missionStore` | socket.io `mission_changed` + API calls | MissionSetup, CenterMap, TopBar, BottomStrip | MissionsPage |
| `eventStore` | socket.io `event` | BottomStrip (Events tab) | — |
| `selectionStore` | user clicks | FleetRoster, CenterMap, QuickActions, MissionSetup | — |
| `uiStore` | user actions | ConfirmDialog, FleetRoster, TopBar | — |

---

## 3. Critical Issues

### 3.1 Showstoppers

| # | Issue | Impact | Root Cause |
|---|-------|--------|------------|
| **S1** | **WebSocket never initialized** | All Zustand stores remain empty; no real-time telemetry, commands, or events stream to any v4 page | `getSocket()` was called in `App.jsx` `useEffect`, but `main.jsx` now renders `V4Routes` instead of `App` — socket bootstrap is lost |
| **S2** | **v3 TopBar not rendered** | Pause/Resume/Abort mission controls are inaccessible; mission state badge is gone | `DashboardPage` renders `LeftPanel + CenterMap + RightPanel + BottomStrip` but omits `TopBar` |
| **S3** | **Mission Builder gray tiles** | Map area shows gray squares instead of tiles, making the builder unusable | Fixed 420px container height + no Leaflet `invalidateSize()` call + global `filter: brightness(0.7)` on `.leaflet-tile-pane` from theme.css |

### 3.2 Architectural Issues

| # | Issue | Impact |
|---|-------|--------|
| **A1** | **Two disconnected mission planning systems** | Dashboard's `MissionSetup` uses Zustand `missionStore` (Plan → Start). Mission Builder uses isolated `useState` and `axios.post`. They don't share state — creating a mission in one has no effect in the other. |
| **A2** | **Duplicate map implementations** | `CenterMap` (v3, full-featured) and `MissionBuilderMap` (v4, minimal) serve overlapping purposes with incompatible data flows |
| **A3** | **Inconsistent mission types** | v3: PATROL, PERIMETER, ESCORT. v4 Builder: PATROL, ESCORT, SURVEY, DELIVERY. No canonical source. |
| **A4** | **Inconsistent formation defaults** | `missionStore`: `{ shape: 'BOX', spacing_m: 30 }`. Mission Builder: `{ shape: 'V', spacing_m: 5 }` |
| **A5** | **Inconsistent map centers** | CenterMap: `[28.6139, 77.209]` (New Delhi). MissionBuilderMap: `[32.08, 34.78]` (Tel Aviv). Should be configurable per deployment. |
| **A6** | **Global CSS without scoping** | Both `App.css` (v3) and `v4.css` loaded globally. Leaflet tile filter in `theme.css` bleeds into Mission Builder map. |

### 3.3 UX Issues

| # | Issue | Details |
|---|-------|---------|
| **U1** | **No cross-page navigation** | No "Create Mission" button on Missions page linking to Builder. No drill-down from Fleet table rows. Pages are siloed. |
| **U2** | **FleetPage is a downgrade** | Loses: searchable filter, click-to-select, role changes, OOF indicators, battery color bar. Gains: health band summary (GREEN/YELLOW/RED/OFFLINE) — but that's it. |
| **U3** | **CommandsPage loses v3 features** | No status color dots, no late-ack badges, no time-since display, no clear button. |
| **U4** | **MissionsPage redundancy** | Overlaps with both the Dashboard's MissionSetup panel and the Mission Builder page. Shows stale store data with no actions. |
| **U5** | **Status pills have no color coding** | "MQTT: Connected" and "MQTT: Pending" look identical. No green/red dot or background change. |
| **U6** | **No mobile/responsive nav** | Topbar nav items wrap on narrow screens but there's no hamburger menu or drawer. |
| **U7** | **SettingsPage shows stale constants** | AppShell already polls `/api/health` but doesn't pass service status down. Settings shows placeholder text instead of live MQTT/DB status. |
| **U8** | **LoginPage placeholder** | No login form, no redirect-after-login, no token management. AUTH_ENABLED defaults to `false` so this is low priority but confusing if discovered. |

---

## 4. Page-by-Page Analysis

### 4.1 Dashboard (`/dashboard`)

**Current:** Renders the entire v3 app (minus TopBar) inside the v4 shell.

**What works:**
- Full Leaflet map with live drone markers, trails, and planning overlays
- Fleet roster with search, selection, and role management
- Quick actions panel with confirmation dialogs
- Bottom strip with altitude/battery charts and event timeline
- Command queue with status tracking

**What's broken/missing:**
- TopBar absent → no Pause/Resume/Abort, no mission state badge, no drone count
- Socket.IO not initialized → all stores empty → all panels show "no data"
- The page description says "The existing v3 monitoring stack is mounted here while the routed v4 shell is built out" — this was always intended as temporary

**Verdict:** The v3 components are **excellent** when socket.io is running, but the v4 shell broke the bootstrap path. The TopBar omission removes critical operational controls.

### 4.2 Missions (`/missions`)

**Current:** Four metric cards (Type, State, Waypoints, Geofence Points) + three info cards (Formation, Waypoint Editing placeholder, Templates placeholder) + placeholder text for History.

**What works:**
- Clean layout with metric grid
- Reads directly from shared `missionStore`

**What's broken/missing:**
- No actions (can't create, edit, pause, abort)
- Data comes from `missionStore` which is empty without socket.io
- Redundant with both Dashboard's MissionSetup and Mission Builder
- No mission list/history table
- "Waypoint Editing" and "Templates" cards are plain text placeholders

**Verdict:** This page adds no value over Dashboard or Mission Builder. Should be either **consolidated into Mission Builder** (as a "current/history" tab) or removed entirely.

### 4.3 Mission Builder (`/mission-builder`)

**Current:** Click-to-add map + waypoint list + geofence editor + formation selector + submit button.

**What works:**
- Point-in-polygon geofence validation
- Mode toggle (waypoint vs geofence click)
- Altitude editing per waypoint
- Submit with success/error toast
- Clean 2-column layout below map

**What's broken/missing:**
- **Gray tiles** — Leaflet sizing bug (showstopper for usability)
- Uses `useState` not `missionStore` — completely disconnected from Dashboard
- No drone assignment step (who flies the mission?)
- No home base selection
- Different mission types than v3 (SURVEY and DELIVERY added, PERIMETER removed)
- Different formation defaults (V/5m vs BOX/30m)
- Uses raw `axios.post` not the shared `api.js` client
- No undo/redo
- No template save/load
- Mode toggle uses inline styles (not themed, jarring light buttons on dark UI)

**Verdict:** Good functional skeleton but needs: (1) tile fix, (2) shared state integration, (3) drone assignment workflow, (4) visual consistency with dark theme.

### 4.4 Fleet (`/fleet`)

**Current:** Summary metrics (Green/Yellow/Red/Offline counts) + table (Drone, Health, Battery, GPS, Mode, Source).

**What works:**
- Health normalization logic (status string → battery level → age-based fallback)
- Health band color coding with CSS classes
- Deferred rendering for high-frequency updates
- Summary metrics give a quick fleet overview

**What's broken/missing:**
- No click-to-select (FleetRoster has this)
- No search/filter (FleetRoster has this)
- No role display or role change (FleetRoster has this)
- No OOF (out-of-formation) indicator
- No battery color bar (FleetRoster has this)
- No navigation to drone detail view
- Data is empty without socket.io

**Verdict:** Structurally sound but feature-sparse compared to `FleetRoster`. Should incorporate the v3 roster's interaction features (search, select, role) while keeping the cleaner v4 table layout.

### 4.5 Commands (`/commands`)

**Current:** Table (Command ID, Drone, Command, Status, Retries) + placeholder text for Detail Pane.

**What works:**
- Sorted by timestamp (newest first)
- Shows retry count
- Deferred rendering

**What's broken/missing:**
- No status color dots (CommandQueue has colored status indicators)
- No late-ack badges
- No time-since display
- No clear/dismiss functionality
- No click-to-expand detail view
- No filtering by drone, status, or command type
- No timestamp column
- Data is empty without socket.io

**Verdict:** Barely functional. Should merge the visual richness of `CommandQueue` with the tabular layout and add filtering + detail expansion.

### 4.6 Settings (`/settings`)

**Current:** Two sections — Deployment (3 cards: Environment, MQTT placeholder, DB placeholder) + Safety Thresholds (6 cards showing constants).

**What works:**
- Clean card grid layout
- Safety threshold display is useful reference

**What's broken/missing:**
- MQTT and DB cards show placeholder text, NOT live status (even though AppShell already has this data)
- Safety thresholds are read-only constants — no ability to override for deployment
- No connection test button
- No MQTT topic configuration
- No user management

**Verdict:** Should at minimum display the live service status from the health poll. Making thresholds editable requires backend support (future).

### 4.7 Login (`/login`)

**Current:** Centered card with title and "placeholder" text.

**What works:** Nothing — it's a stub.

**Verdict:** Low priority since `AUTH_ENABLED` defaults to `false`. Should be implemented when auth is turned on.

---

## 5. Proposed Information Architecture

### 5.1 Page Consolidation

**Current: 7 pages** → **Proposed: 5 pages**

```
CURRENT                              PROPOSED
─────────────────────────────        ─────────────────────────────
/dashboard    (v3 iframe)       →    /dashboard    (unified ops center)
/missions     (read-only)       →    ╳ REMOVED — absorbed into Mission Builder
/mission-builder (isolated)     →    /missions     (plan + monitor + history)
/fleet        (basic table)     →    /fleet        (enhanced roster + detail)
/commands     (basic table)     →    /commands     (filterable + detail pane)
/settings     (static)          →    /settings     (live status + config)
/login        (stub)            →    /login        (form, when auth enabled)
```

### 5.2 Navigation Labels

```
┌─────────────────────────────────────────────────────────────────────────┐
│ MISSION CONTROL v4                                                     │
│                                                                        │
│  [Dashboard]  [Missions]  [Fleet]  [Commands]  [Settings]              │
│                                                                        │
│  ● MQTT: Connected    ● DB: Connected    ● Inv: Connected    Env: SIM │
└─────────────────────────────────────────────────────────────────────────┘
```

- "Missions" replaces both "Missions" and "Mission Builder" — one page with tabs (Plan / Active / History)
- Status pills get colored dots (green = connected, red = pending/error)

### 5.3 Data Flow Architecture

```
                        ┌──────────────┐
                        │  WebSocket   │  ← Native WS at /ws (v4 backend)
                        │  Bootstrap   │     OR Socket.IO (v3 compat)
                        └──────┬───────┘
                               │
                    ┌──────────┼──────────┐
                    ▼          ▼          ▼
              ┌──────────┐ ┌────────┐ ┌────────┐
              │fleetStore│ │cmdStore│ │evtStore│  ← Zustand (shared)
              └────┬─────┘ └───┬────┘ └───┬────┘
                   │           │          │
         ┌─────────┼───────────┼──────────┼─────────┐
         ▼         ▼           ▼          ▼         ▼
    Dashboard   Missions    Fleet    Commands   Settings
```

**Key change:** A single `useDataBootstrap()` hook in `AppShell` initializes the WebSocket connection (or Socket.IO) and wires it to Zustand stores. All pages consume from stores. No page uses local state for domain data.

---

## 6. Proposed Page Designs

### 6.1 Dashboard — Unified Operations Center

**Purpose:** Real-time situational awareness. The primary view during active operations.

```
┌─────────────────────────────────────────────────────────────────────┐
│ ┌─ MISSION BAR ──────────────────────────────────────────────────┐  │
│ │  ● PATROL  │  STATE: ACTIVE  │  6/12 drones  │  [Pause] [Abort] │
│ └────────────────────────────────────────────────────────────────┘  │
│                                                                     │
│ ┌──────────────────┐ ┌────────────────────────────┐ ┌────────────┐ │
│ │  FLEET ROSTER    │ │       LIVE MAP             │ │  ACTIONS   │ │
│ │                  │ │                            │ │            │ │
│ │  🔍 search       │ │   (full-height Leaflet)    │ │  [HOLD]    │ │
│ │  ☑ drone-01 ●    │ │   - Drone markers          │ │  [RETURN]  │ │
│ │  ☑ drone-02 ●    │ │   - Trails                 │ │  [ARM]     │ │
│ │  ☐ drone-03 ●    │ │   - Waypoint overlays      │ │  [DISARM]  │ │
│ │  ☐ drone-04 ●    │ │   - Geofence polygon       │ │            │ │
│ │  ...             │ │   - Home base star          │ │  Leader:   │ │
│ │                  │ │                            │ │  [Reassign]│ │
│ │  [Select All]    │ │                            │ │            │ │
│ └──────────────────┘ └────────────────────────────┘ └────────────┘ │
│                                                                     │
│ ┌─ TELEMETRY STRIP ────────────────────────────────────────────────┐│
│ │  [Altitude ▼] [Battery ▼] [Events ▼] [Commands ▼]               ││
│ │  ┌──────────────────────────────────────────────────────────┐    ││
│ │  │  (chart or event list based on selected tab)             │    ││
│ │  └──────────────────────────────────────────────────────────┘    ││
│ └──────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────┘
```

**Changes from current:**
1. **Restore TopBar** as "Mission Bar" — integrated into the page (not a separate component above the nav)
2. **Add "Commands" tab** to BottomStrip — shows live command queue inline (replaces navigating away)
3. **Socket.IO bootstrapped** at AppShell level — stores populated on app mount
4. **Remove "Live Operations" header** — the mission bar IS the header; don't waste vertical space

### 6.2 Missions — Plan + Monitor + History

**Purpose:** Complete mission lifecycle — build, monitor, review.

```
┌─────────────────────────────────────────────────────────────────────┐
│  MISSIONS                                                           │
│  [ Plan ]  [ Active ]  [ History ]          ← tab bar               │
│                                                                     │
│  ═══════════════════════════════════════════════════════════════     │
│                                                                     │
│  PLAN TAB:                                                          │
│  ┌──────────────────────────────┐  ┌──────────────────────────────┐ │
│  │         MISSION MAP          │  │  CONFIGURATION               │ │
│  │                              │  │                              │ │
│  │   (Leaflet — reuses         │  │  Type: [PATROL ▼]            │ │
│  │    CenterMap component       │  │  Formation: [V ▼] 15m       │ │
│  │    in planning mode)         │  │  Home Base: [Set on map]     │ │
│  │                              │  │                              │ │
│  │   Click: add waypoint        │  │  ─────────────────────────── │ │
│  │   Shift+click: geofence      │  │  WAYPOINTS (3)              │ │
│  │                              │  │  1. 32.080, 34.780  30m  [×]│ │
│  │   [Waypoint mode]            │  │  2. 32.082, 34.782  30m  [×]│ │
│  │   [Geofence mode]            │  │  3. 32.081, 34.779  30m  [×]│ │
│  │                              │  │  [↕ drag to reorder]        │ │
│  │                              │  │                              │ │
│  │                              │  │  ─────────────────────────── │ │
│  │                              │  │  GEOFENCE (4 pts) [Clear]   │ │
│  │                              │  │  ─────────────────────────── │ │
│  │                              │  │  ASSIGN DRONES              │ │
│  │                              │  │  ☑ drone-01  ☑ drone-02     │ │
│  │                              │  │  ☐ drone-03  ☐ drone-04     │ │
│  │                              │  │  [Select from Fleet →]      │ │
│  └──────────────────────────────┘  │                              │ │
│                                    │  ⚠ 1 waypoint outside fence │ │
│                                    │                              │ │
│  [Save as Template]                │  [Plan Mission]  [Start ▶]  │ │
│                                    └──────────────────────────────┘ │
│                                                                     │
│  ═══════════════════════════════════════════════════════════════     │
│                                                                     │
│  ACTIVE TAB:                                                        │
│  (Shows current mission progress — state, drone positions,          │
│   completion %, with Pause/Abort controls)                          │
│                                                                     │
│  HISTORY TAB:                                                       │
│  (Paginated table: Mission ID, Type, State, Drones, Created,       │
│   Duration, with click-to-expand detail view)                       │
└─────────────────────────────────────────────────────────────────────┘
```

**Key decisions:**
1. **Consolidate** MissionsPage + MissionBuilderPage into one tabbed page
2. **Reuse `CenterMap`** in planning mode instead of separate `MissionBuilderMap` — eliminates duplicate map, inherits tile fallback logic, uses shared constants
3. **Use `missionStore`** not local state — mission plan is visible across Dashboard
4. **Add drone assignment** step — currently Mission Builder doesn't select which drones fly
5. **60/40 split** map vs config panel (not full-width map that forces scrolling)
6. **Dark-themed buttons** — remove the light-colored inline-style buttons that clash with the dark UI

### 6.3 Fleet — Enhanced Roster + Detail Panel

**Purpose:** Fleet management, health monitoring, individual drone drill-down.

```
┌─────────────────────────────────────────────────────────────────────┐
│  FLEET                                          12 drones tracked   │
│                                                                     │
│  ┌─ SUMMARY BAND ──────────────────────────────────────────────┐   │
│  │  🟢 8 Green    🟡 2 Yellow    🔴 1 Red    ⚪ 1 Offline       │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌─ FILTER BAR ─────────────────────────────────────────────────┐  │
│  │  🔍 Search...   │  Health: [All ▼]  │  Role: [All ▼]  │ Sort │  │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌─ TABLE ──────────────────────────────────┐  ┌─ DETAIL ────────┐ │
│  │  Drone    Health  Battery  Role   GPS    │  │  drone-02       │ │
│  │  ─────────────────────────────────────── │  │                 │ │
│  │  drone-01  🟢     87%      SCOUT   12   │  │  Health: 🟡     │ │
│  │ ▶drone-02  🟡     45%      RELAY    9   │  │  Battery: 45%   │ │
│  │  drone-03  🟢     92%      SCOUT   14   │  │  Lat: 32.0801   │ │
│  │  drone-04  🔴     12%      GUARD    6   │  │  Lng: 34.7782   │ │
│  │  drone-05  🟢     78%      LEADER  11   │  │  Alt: 30m       │ │
│  │  ...                                     │  │  Mode: GUIDED   │ │
│  │                                          │  │  Role: [RELAY ▼]│ │
│  │                                          │  │  OOF: No        │ │
│  │                                          │  │                 │ │
│  │                                          │  │  [HOLD] [RTL]   │ │
│  │                                          │  │  [ARM] [DISARM] │ │
│  └──────────────────────────────────────────┘  └─────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

**Key decisions:**
1. **Click-to-select** with detail panel slide-in (master-detail pattern)
2. **Merge FleetRoster features**: search, role dropdown, battery color, OOF indicator
3. **Filter bar**: by health band, role, free-text search
4. **Quick actions** in the detail panel — scoped to the selected drone
5. **Link to Dashboard** — "View on Map" button centers the dashboard map on that drone

### 6.4 Commands — Filterable Audit Log + Detail Pane

**Purpose:** Command audit trail with filtering and detail expansion.

```
┌─────────────────────────────────────────────────────────────────────┐
│  COMMANDS                                        47 cached items    │
│                                                                     │
│  ┌─ FILTER BAR ─────────────────────────────────────────────────┐  │
│  │  🔍 Search...  │ Drone: [All ▼]  │ Status: [All ▼]  │ [Clear]│  │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌─ TABLE ──────────────────────────────────────────────────────┐  │
│  │  Status  Command   Drone     Retries   Time        Age      │  │
│  │  ────────────────────────────────────────────────────────────│  │
│  │  🟢 ACK  HOLD      drone-02  0         14:32:05    2m ago   │  │
│  │  🟡 PEND RETURN    drone-05  1         14:31:58    2m ago   │  │
│  │  🔴 FAIL ARM       drone-04  3         14:30:12    4m ago   │  │
│  │  🟢 ACK  DISARM    drone-01  0         14:28:44    6m ago   │  │
│  │  ⚠ LATE  HOLD      drone-03  0         14:27:30    7m ago   │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  ┌─ DETAIL ────────────────────────────────────────────────────┐   │
│  │  Command ID: cmd-47281                                       │   │
│  │  Issued: 14:32:05.234    Acked: 14:32:05.891  (657ms)       │   │
│  │  Preflight: Battery 87%, GPS 12 sats, Mode GUIDED           │   │
│  │  Failure reason: —                                           │   │
│  └──────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

**Key decisions:**
1. **Add columns:** Timestamp, Age (time-since), Status color dot
2. **Filter bar:** by drone, status (ACK/PENDING/FAILED/LATE), free-text
3. **Click-to-expand** detail row with full command lifecycle
4. **Late-ack badge** (⚠) for commands exceeding `ACK_TIMEOUT_SEC`
5. **Clear old** button linked to `commandStore.clearOld()`

### 6.5 Settings — Live Status + Config

**Purpose:** System health overview and configurable parameters.

```
┌─────────────────────────────────────────────────────────────────────┐
│  SETTINGS                                        Env: SIM           │
│                                                                     │
│  ┌─ SERVICE STATUS ────────────────────────────────────────────┐   │
│  │  MQTT          ● Connected   broker: mosquitto:1883  [Test] │   │
│  │  Database      ● Connected   engine: PostgreSQL      [Test] │   │
│  │  Inventory     ● Connected   drones: 12              [Test] │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌─ SAFETY THRESHOLDS ─────────────────────────────────────────┐   │
│  │  Battery Arm Min   25%     GPS Arm Min      6 sats          │   │
│  │  Stale Timeout     30s     Ack Timeout      10s             │   │
│  │  Max Retries       3       Retry Backoff    2s, 4s, 8s      │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌─ MAP CONFIGURATION ─────────────────────────────────────────┐   │
│  │  Tile Server     OpenStreetMap                               │   │
│  │  Default Center  [28.6139, 77.209]                           │   │
│  │  Default Zoom    14                                          │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

**Key decisions:**
1. **Live service status** from AppShell's `/api/health` poll — pass via React context or prop
2. **[Test] buttons** — trigger an on-demand health check with result feedback
3. **Map configuration** — read-only display of the configured tile server and center point
4. Safety thresholds remain read-only until backend supports updates

---

## 7. Cross-Cutting Improvements

### 7.1 WebSocket Bootstrap (Priority: CRITICAL)

**Problem:** `getSocket()` from `socket.js` is never called in the v4 render tree.

**Proposed fix:**
```
AppShell.jsx
  └── useEffect(() => { getSocket(); }, [])
```
One line. This connects Socket.IO, which triggers the `onConnect` handler in `socket.js` that fetches inventory + snapshot + missions and wires telemetry/command/event handlers to Zustand stores.

**Alternative (v4-native):** Replace Socket.IO with a native WebSocket client connecting to `/ws` (the v4 backend already broadcasts on this path). This is cleaner long-term but requires rewriting the event handlers.

### 7.2 Status Pill Color Coding

**Current:** Text-only ("MQTT: Connected" / "MQTT: Pending")

**Proposed:** Add a colored dot before the label.

```css
.v4-status-pill--connected::before { background: #61d095; }  /* green */
.v4-status-pill--pending::before   { background: #f97360; }  /* red */
```

Apply `v4-status-pill--connected` or `v4-status-pill--pending` class dynamically.

### 7.3 Responsive Design

**Current:** Only one `@media (max-width: 900px)` rule adjusting padding.

**Proposed:**
- **< 768px:** Stack Dashboard panels vertically (roster, map, actions). Hamburger nav menu.
- **768–1200px:** 2-column Dashboard (roster+actions collapse into sidebar). Full nav visible.
- **> 1200px:** 3-column Dashboard as designed.

### 7.4 CSS Architecture

**Current:** 3 global CSS files (theme.css, App.css, v4.css) with no scoping.

**Proposed (incremental):**
1. **Short-term:** Keep the existing CSS files. Add `data-v4` attribute to v4 containers. Scope `.leaflet-tile-pane { filter: ... }` under `.app-body` so it doesn't bleed into Mission Builder.
2. **Long-term:** Migrate to CSS Modules (`.module.css`) per component. Vite supports this natively.

### 7.5 Map Configuration Centralization

**Current:** Two different `MAP_CENTER` constants in two files.

**Proposed:** Single `MAP_CONFIG` object in `v4/constants.js`:
```js
export const MAP_CONFIG = {
  center: [28.6139, 77.209],  // or read from env
  zoom: 14,
  tileUrl: import.meta.env.VITE_TILE_URL || 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
};
```

All maps import from this single source.

### 7.6 Mission Type / Formation Unification

**Proposed canonical set:**

| Mission Type | Description | Planning Input |
|-------------|-------------|----------------|
| PATROL | Waypoint navigation loop | Waypoints + Geofence |
| PERIMETER | Geofence boundary sweep | Geofence polygon |
| ESCORT | Follow an asset route | Asset route + Formation |
| SURVEY | Area coverage scan | Geofence area + cell size |

Formation defaults: `{ shape: 'V', spacing_m: 15 }` (compromise between 5m and 30m).

### 7.7 Dark Theme Consistency

The Mission Builder uses inline `style={}` with light colors (`#e5e7eb`, `#374151`, `#1d4ed8`) that clash with the dark military theme. All interactive elements should use CSS custom properties:

```css
.v4-btn           { background: var(--v4-surface); color: var(--v4-text); border: 1px solid var(--v4-border); }
.v4-btn--primary  { background: var(--v4-accent); color: var(--v4-bg); }
.v4-btn--active   { background: var(--v4-accent); color: var(--v4-bg); }
.v4-btn--danger   { background: var(--v4-danger); color: #fff; }
```

---

## 8. Implementation Priority

### Phase 1 — Fix Showstoppers (1–2 days)

| Task | Effort | Impact |
|------|--------|--------|
| Bootstrap WebSocket in AppShell (`getSocket()`) | 1 line | Unlocks ALL real-time data across all pages |
| Restore TopBar/Mission Bar on Dashboard | Small | Restores Pause/Resume/Abort controls |
| Fix Mission Builder map tiles (`invalidateSize()`) | Small | Mission Builder becomes usable |
| Add status pill color coding | Small | Visual clarity for service health |

### Phase 2 — Page Consolidation (3–5 days)

| Task | Effort | Impact |
|------|--------|--------|
| Merge Missions + Mission Builder into tabbed page | Medium | Eliminates redundancy, unified workflow |
| Wire Mission Builder to `missionStore` (replace useState) | Medium | Dashboard sees missions from Builder and vice versa |
| Add drone assignment step to Mission Builder | Medium | Completes the planning workflow |
| Enhance Fleet page (search, filter, detail panel) | Medium | Replaces v3 FleetRoster functionality |
| Enhance Commands page (filter, status dots, timestamps) | Medium | Replaces v3 CommandQueue functionality |

### Phase 3 — Polish & Refinement (2–3 days)

| Task | Effort | Impact |
|------|--------|--------|
| Wire Settings to live health data | Small | Settings becomes useful |
| Centralize map configuration | Small | Eliminates inconsistencies |
| Unify mission types + formations | Small | Eliminates v3/v4 divergence |
| Dark-theme all inline styles | Small | Visual consistency |
| Add hamburger nav for mobile | Medium | Responsive improvement |
| Add cross-page navigation links | Small | UX flow between pages |

### Phase 4 — Advanced Features (future sprints)

| Task | Effort | Impact |
|------|--------|--------|
| Migrate Socket.IO → native WebSocket | Medium | Reduce dependencies, use v4 backend's `/ws` |
| CSS Modules migration | Medium | Eliminate global CSS conflicts |
| Login page implementation | Medium | Auth support when enabled |
| Mission templates (save/load) | Medium | Operator productivity |
| Undo/redo in Mission Builder | Medium | Error recovery |
| Drag-to-reorder waypoints on map | Medium | Better map interaction |

---

## 9. Migration Strategy

### Principle: Incremental replacement, not big-bang rewrite

The v3 components (`CenterMap`, `FleetRoster`, `MissionSetup`, etc.) are **battle-tested** and feature-rich. The v4 pages should **adopt and enhance** them rather than rewriting from scratch.

### Step 1: Bootstrap real-time data
Add `getSocket()` call in `AppShell.useEffect`. This immediately makes all v3 components work inside the v4 shell AND populates the Zustand stores that v4 pages consume. Zero risk, massive unlock.

### Step 2: Promote TopBar into v4 Mission Bar
Create a `MissionBar` v4 component that wraps the same store hooks as `TopBar` but uses v4 CSS classes. Render it in `DashboardPage` above the `app-body` grid.

### Step 3: Refactor Mission Builder to use stores
Replace `useState` calls with `missionStore` actions. Replace `axios.post` with `api.js` calls. Import `CenterMap` in planning mode instead of `MissionBuilderMap`. Add the Plan tab, Active tab, and History tab.

### Step 4: Enhance Fleet and Commands incrementally
Port interaction features from `FleetRoster` and `CommandQueue` into the v4 pages, applying v4 CSS classes. Keep the v3 components alive in Dashboard for backward compatibility until parity is reached.

### Step 5: Remove v3 embedding
Once all v4 pages reach feature parity with the v3 components, the DashboardPage can drop the v3 imports and render native v4 components. At that point, `App.css` and the v3 component files can be removed.

---

## Appendix A: File Reference

| File | Role | Action |
|------|------|--------|
| `ui/src/main.jsx` | Entry point, imports CSS + `V4Routes` | Add `socket.js` import or move bootstrap to AppShell |
| `ui/src/v4/AppShell.jsx` | Shell with nav + health poll | Add `getSocket()` call, pass service status via context |
| `ui/src/v4/routes.jsx` | React Router config | Remove `/missions` route, rename `/mission-builder` → `/missions` |
| `ui/src/v4/pages/DashboardPage.jsx` | v3 embed | Add MissionBar component above `app-body` |
| `ui/src/v4/pages/MissionBuilderPage.jsx` | Standalone planner | Refactor to tabbed page using `missionStore` |
| `ui/src/v4/pages/MissionsPage.jsx` | Read-only summary | DELETE — absorbed into refactored Mission Builder |
| `ui/src/v4/pages/FleetPage.jsx` | Health table | Add search, filter, detail panel, role controls |
| `ui/src/v4/pages/CommandsPage.jsx` | Command table | Add filter, status dots, timestamps, detail pane |
| `ui/src/v4/pages/SettingsPage.jsx` | Static config | Wire to live health data from AppShell |
| `ui/src/v4/v4.css` | v4 design tokens | Add button classes, status pill colors, responsive breakpoints |
| `ui/src/v4/constants.js` | v4 config | Add `MAP_CONFIG`, unify mission types |
| `ui/src/socket.js` | Socket.IO client | Keep as-is; called from AppShell |
| `ui/src/App.css` | v3 styles | Keep until v3 components are replaced |
| `ui/src/theme.css` | CSS reset + dark theme | Scope `.leaflet-tile-pane` filter to `.app-body` |

---

## Appendix B: Wireframe Legend

```
●  Status dot (colored: green/yellow/red)
🟢 🟡 🔴 ⚪  Health indicators
☑ ☐  Checkbox (selected/unselected)
▶  Selected/active row indicator
▼  Dropdown indicator
[Button]  Action button
→  Navigation link
⚠  Warning indicator
```
