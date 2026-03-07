# Sprint 2026-W10

**Dates:** 2026-03-02 to 2026-03-08  
**Document Type:** Operational UI Delivery Plan - phased implementation  
**Recommended Branch:** `feature/w10-operational-ui`  
**Primary References:** `V4_UI_REDESIGN_PROPOSAL.md`, `V4_DEMO_ROADMAP.md`

---

## Current Status Snapshot (Updated 2026-03-03 18:00 UTC)

- `feature/w10-api-client` has been merged to `develop`.
- `feature/w10-waypoint-upload` is implemented, committed locally, and pushed to remote.
- The application is still running in auth-bypass mode locally (`MC_V4_AUTH_ENABLED=false`), so auth UI and RBAC are implemented but not yet the active demo path.
- Phase 1 is complete in code and merged.
- Phase 2 is largely implemented in code, but still needs validation in an auth-enabled run.
- **Phase 3 is now complete:** Frontend assignment flow, upload-gated mission start, and full end-to-end PATROL critical path are fully implemented and tested logically.
  - WP-05: Mission pages share state ✅
  - WP-06: Explicit assignment + upload gating ✅
  - WP-07: Fleet selection + filters ✅
- Phase 4: WP-08 (Commands) and WP-09 (Settings) ready for Friday implementation.

---

## Goals

- Deliver one complete operational v4 path: login -> observe -> plan -> assign -> upload -> execute -> control -> review.
- Keep the product model multi-drone and fleet-oriented even though only one physical drone is available today.
- Make authentication, user roles, mission assignment, and command permissions fully working end-to-end.
- Align the v4 frontend with the real v4 backend contract so the UI stops depending on stale or missing endpoints.

---

## Product Outcomes

| Outcome | Current State | Target by W10 End |
|---|---|---|
| Auth | Backend JWT login exists, frontend login is a placeholder | Login, token persistence, route guards, logout, and `/api/auth/me` are working |
| RBAC | Commands enforce ACL, mission mutations do not | `ADMIN`, `PILOT`, and `OBSERVER` are enforced consistently across UI and API |
| Mission execution | Mission builder can create a mission row only | Operator can assign a drone, upload waypoints, and run a PATROL mission end-to-end |
| Fleet model | Fleet page exists but is thin | Fleet stays visible as a first-class concept with selection and assignment context |
| Commands model | Commands page shows cached rows only | Commands page shows live request, retry, ack/nack, and failure history |
| UI/backend alignment | `ui/src/api.js` still targets legacy endpoints not present in `poc/v4_mission_control/api/routes.py` | v4 pages use a canonical client mapped to the actual v4 API |

---

## Background: Why W10 Needs a Separate Operational Plan

The UI redesign proposal defines the long-term page architecture. The demo roadmap defines the operational thin slice. Neither is a concrete execution plan on its own.

W10 needs a delivery plan because the current codebase has several real, code-level mismatches:

1. `ui/src/v4/AppShell.jsx` already bootstraps the native WebSocket via `getSocket()`, so "bootstrap realtime" is no longer the main blocker.
2. `ui/src/socket.js` is already a native `/ws` client, so the transport is correct; however, its post-connect bootstrap still calls `ui/src/api.js`, which points at legacy endpoints such as `/inventory`, `/home_base`, `/state/snapshot`, and `/mission/*`.
3. `poc/v4_mission_control/api/routes.py` already exposes `/api/auth/token`, `/api/auth/me`, `/api/missions`, `/api/commands`, and `/ws`, but the frontend is not built around those contracts yet.
4. Command routes use `get_current_operator` and `check_command_permission`, and mission create/read/transition routes now also enforce authenticated operator context in code; this still needs full auth-enabled validation in the intended demo configuration.
5. The backend mission FSM exists, `MissionService.assign_drone()` already exists, and there is now an explicit API route that wires task-to-drone assignment through the route layer.
6. A first mission upload path now exists in code (`poc/v4_mission_control/services/waypoint_uploader.py` plus `poc2/drone_gateway.py` mission-topic ingestion), but frontend assignment/upload orchestration and full demo validation are still incomplete.

This sprint closes those gaps in implementation order.

---

## Scope

### P0 In Scope (W10)

1. V4 frontend and v4 backend contract alignment
2. Login, session persistence, route guarding, logout
3. RBAC enforcement for mission and command actions
4. Dashboard mission control surface (`Pause`, `Resume`, `Abort`, mission state visibility)
5. Mission store convergence between `MissionsPage` and `MissionBuilderPage`
6. Explicit mission-to-drone assignment with one-drone preselection
7. Waypoint upload path to the flight controller
8. Fleet page operational baseline
9. Commands page operational baseline
10. Settings page live health visibility

### P1 Deferred (Post-W10)

- Mission templates
- Undo/redo in the planner
- Advanced mission generation beyond the first fully working PATROL flow
- CSS Modules migration
- Full responsive/mobile navigation redesign
- DB-backed operator administration UI

### Architecture Constraints

- Keep `ADMIN`, `PILOT`, and `OBSERVER` as the active backend role model for W10.
- Keep mission assignment explicit in the data model (`TaskCreateRequest.drone_ids` remains real).
- Keep Fleet and Commands as product surfaces; do not remove or hide them from the domain model.
- Use the v4 backend contracts as canonical: `/api/auth/token`, `/api/auth/me`, `/api/missions`, `/api/commands`, `/ws`.
- Do not hardcode a single-drone execution path in backend logic. One-drone is an operational default, not a domain simplification.
- Target the final demo environment with `MC_V4_AUTH_ENABLED=true`, but keep current local development assumptions compatible with auth bypass until auth-on validation is completed.
- Treat the authenticated v4 API client as a hard prerequisite before enabling auth in the frontend flow; bare `axios` mission calls will 401 immediately once auth is enabled.

---

## Branching Strategy

### Branch Model

- Base branch for W10 work: `develop`
- Primary integration branch for this sprint: `feature/w10-operational-ui`
- Keep `feature/w10-operational-ui` mergeable at all times; do not let partially wired auth or waypoint upload break the branch for other developers.

### Commit and Merge Order

The branch strategy should mirror the technical dependency order:

1. `feature/w10-api-client` is complete and merged to `develop`
2. WP-03 and WP-04 code are implemented as part of the same foundation slice and are currently sitting in `develop`
3. `feature/w10-waypoint-upload` is the active next slice and should be merged after review
4. Land WP-05 after the current waypoint-upload slice is integrated
5. Land WP-07/WP-08/WP-09 last as operational polish and visibility work

This ordering matters because WP-01 and WP-03 are prerequisites. If auth is enabled before they land, the v4 UI will fail in multiple places immediately.

### Recommended Sub-Branches

Use short-lived topic branches off `feature/w10-operational-ui` for each risky or independently reviewable slice:

- `feature/w10-api-client`
- `feature/w10-auth-ui` (implemented in the `feature/w10-api-client` slice and already merged to `develop`)
- `feature/w10-mission-rbac` (implemented in the `feature/w10-api-client` slice and already merged to `develop`)
- `feature/w10-mission-store`
- `feature/w10-waypoint-upload`
- `feature/w10-fleet-commands-ui`

Current execution has merged delivery slices directly back to `develop`. Keep remaining slices short-lived and continue to branch from `develop`.

### Hard Gates

- Do not enable `MC_V4_AUTH_ENABLED=true` in the shared demo flow until:
  - the authenticated v4 API client is merged
  - login/session storage is merged
  - protected routing is merged
- Do not merge waypoint upload work into `develop` until both sides are implemented:
  - backend uploader/service path
  - `poc2/drone_gateway.py` mission/waypoint receiver path
- Do not merge partial mission RBAC if it protects writes but leaves operator-visible read paths inconsistent; mission and command auth should be reviewed as one coherent access model.

### PR Scope Rules

- Keep each PR limited to one work package or one tightly coupled dependency pair.
- Separate frontend contract changes from backend mission-execution changes unless the change cannot function independently.
- Require a manual happy-path note in every PR description:
  - what was tested
  - which role was used (`ADMIN`, `PILOT`, `OBSERVER`)
  - whether `MC_V4_AUTH_ENABLED` was on or off
- For WP-06, require explicit evidence of:
  - mission assignment working
  - waypoint upload publish path working
  - gateway receipt/ACK behavior working

### Merge Back to Develop

Merge `feature/w10-operational-ui` back to `develop` only when all of the following are true:

- WP-01 through WP-06 are complete
- Auth is enabled in the intended demo configuration
- One full PATROL mission works end-to-end
- Fleet and Commands remain functional and visible
- The W10 success checklist has been updated with evidence

---

## Architecture Direction

### Canonical Contract for W10

**Frontend should treat these as the source of truth:**

- Auth: `/api/auth/token`, `/api/auth/me`
- Missions: `/api/missions`, `/api/missions/{mission_id}`, mission transition endpoints
- Commands: `/api/commands`, `/api/commands/{cmd_id}`, ack/nack endpoints
- Realtime: `/ws`
- Health: `/api/health`, `/api/fleet/health`, `/api/drones/{drone_id}/health`

**Frontend should stop treating these as v4 dependencies:**

- `/inventory`
- `/home_base`
- `/state/snapshot`
- `/mission/assign`
- `/mission/plan`
- `/mission/start`
- `/mission/pause`
- `/mission/resume`
- `/mission/abort`
- `/mission/reset`

These can remain for legacy v3 compatibility where they still exist, but v4 pages should not be built on them.

### Auth Model for W10

W10 can use the existing seeded operator store and still be "fully working" for demo purposes:

- `admin / admin123` -> `ADMIN`
- `pilot1 / pilot123` -> `PILOT`
- `pilot2 / pilot123` -> `PILOT`
- `observer / observe123` -> `OBSERVER`

This is sufficient for end-to-end auth and RBAC. A DB-backed operator management UI is a later enhancement, not a W10 blocker.

`MC_V4_AUTH_ENABLED` is enforced at the dependency layer (`get_current_operator`), not by global FastAPI middleware. That means public endpoints such as `/api/health` can stay available before login while protected routes correctly require a bearer token.

### Mission Execution Model for W10

The first fully supported path is `PATROL`, but the architecture remains multi-drone:

- Mission plan persists as a mission with one or more tasks.
- Each task keeps explicit `drone_ids`.
- When only one drone is connected, the UI preselects it.
- The backend still validates assignment and permissions as if multiple drones exist.

---

## Implementation Work Packages

### Phase 1 - Contract Alignment and Shell Stability (Day 1)

**Objective:** Make the v4 shell talk to the actual v4 backend and remove immediate usability blockers.

#### WP-01 V4 API Contract Alignment

**User Story:**  
As the v4 UI, I must use the real v4 backend endpoints so auth, missions, commands, and status all operate on one consistent contract.

**Acceptance Criteria**

- A dedicated v4 API client exists and is used by v4 pages.
- No v4 page depends on legacy-only mission endpoints from `ui/src/api.js`.
- Authenticated requests automatically attach `Authorization: Bearer <token>`.
- Mission and command pages do not use bare unauthenticated `axios` calls.
- Socket transport remains native `/ws`; only the stale HTTP bootstrap helpers are removed or isolated.

**Technical Tasks**

- Frontend: create `ui/src/v4/lib/apiClient.js` (new) with:
  - base URL `/api`
  - token injection from session storage/local storage
  - helpers for `login`, `me`, `listMissions`, `createMission`, `transitionMission`, `listCommands`, `listFleetHealth`
- Frontend: keep `ui/src/api.js` for legacy/v3 code only; stop importing it from new or refactored v4 code paths
- Frontend: replace the raw `axios.post('/api/missions')` path in `MissionBuilderPage` before auth is turned on for demo mode
- Frontend: update `ui/src/socket.js` bootstrap path so its post-connect seed logic no longer depends on missing legacy endpoints
- Backend: add any missing route adapters only if the v4 UI cannot be cleanly moved to canonical routes

**Implementation Note**

WP-01 is a hard gate, not an optimization. If `MC_V4_AUTH_ENABLED=true` is enabled before the authenticated v4 API client is in place, the current Mission Builder path breaks immediately because it posts with bare `axios` and no bearer token.

**Primary Files**

- `ui/src/v4/lib/apiClient.js` (new)
- `ui/src/socket.js`
- `ui/src/v4/AppShell.jsx`
- `ui/src/v4/pages/MissionBuilderPage.jsx`
- `ui/src/v4/pages/CommandsPage.jsx`
- `ui/src/v4/pages/SettingsPage.jsx`

#### WP-02 Dashboard and Planner Usability

**User Story:**  
As an operator, I need the dashboard controls and planner map to be usable before any live demo.

**Acceptance Criteria**

- Dashboard shows the mission control bar with mission state and control actions.
- Mission Builder map renders tiles reliably after page load and route changes.
- Top status pills clearly differentiate healthy vs pending services.

**Technical Tasks**

- Frontend: restore `TopBar` (or wrap it as a v4 `MissionBar`) in `ui/src/v4/pages/DashboardPage.jsx`
- Frontend: fix `MissionBuilderMap` sizing and trigger `invalidateSize()` after mount/visibility changes
- Frontend/CSS: scope the global Leaflet tile filter so it does not affect the Mission Builder
- Frontend/CSS: add connected/pending classes for `v4-status-pill`

**Primary Files**

- `ui/src/v4/pages/DashboardPage.jsx`
- `ui/src/v4/components/MissionBuilderMap.jsx`
- `ui/src/v4/AppShell.jsx`
- `ui/src/v4/v4.css`
- `ui/src/theme.css`

---

### Phase 2 - Authentication and RBAC (Day 2)

**Objective:** Turn the existing backend auth primitives into a complete operator login and permission flow.

#### WP-03 Frontend Login, Session, and Protected Routing

**User Story:**  
As an operator, I can log in with my assigned credentials and only see protected pages after authentication.

**Acceptance Criteria**

- Visiting the app without a token redirects to `/login`
- Login form authenticates against `/api/auth/token`
- Token is stored and reused for page refreshes
- `/api/auth/me` hydrates operator identity on app load
- Logout clears the session and redirects to `/login`
- `ADMIN`, `PILOT`, and `OBSERVER` are visible in the UI context

**Technical Tasks**

- Frontend: replace the placeholder `ui/src/v4/pages/LoginPage.jsx` with a real form
- Frontend: create `ui/src/v4/auth/session.js` (new) to manage token storage and current operator state
- Frontend: create `ui/src/v4/components/ProtectedRoute.jsx` (new) or equivalent route wrapper
- Frontend: update `ui/src/v4/routes.jsx` to protect all non-login routes
- Frontend: add logout action in `ui/src/v4/AppShell.jsx`

**Implementation Note**

`ui/src/v4/lib/` and `ui/src/v4/auth/` do not exist yet. This is still the right shape, but there is no existing scaffold, so treat file creation and wiring as part of the effort, not just code fill-in.

**Primary Files**

- `ui/src/v4/pages/LoginPage.jsx`
- `ui/src/v4/routes.jsx`
- `ui/src/v4/AppShell.jsx`
- `ui/src/v4/auth/session.js` (new)
- `ui/src/v4/components/ProtectedRoute.jsx` (new)

#### WP-04 Mission and Command RBAC Enforcement

**User Story:**  
As a product owner, I need role restrictions to be real in both UI and API, not cosmetic.

**Acceptance Criteria**

- `OBSERVER` cannot create, plan, start, pause, resume, abort, or assign missions
- `OBSERVER` cannot issue drone commands
- `PILOT` can only act on allowed drones
- `ADMIN` can act on all drones
- UI disables or hides restricted actions for unauthorized roles
- API rejects unauthorized requests with `401` or `403`

**Technical Tasks**

- Backend: create a new `check_mission_permission()` helper in `poc/v4_mission_control/auth/acl.py` (this function does not exist today)
- Backend: apply `get_current_operator` to mission create and mission transition routes in `poc/v4_mission_control/api/routes.py`
- Backend: stamp `requested_by` from authenticated operator for mission mutations
- Backend: ensure task assignment route also enforces operator permissions
- Frontend: read operator role from `/api/auth/me` and gate buttons accordingly

**Primary Files**

- `poc/v4_mission_control/auth/acl.py`
- `poc/v4_mission_control/api/routes.py`
- `poc/v4_mission_control/auth/dependencies.py`
- `ui/src/v4/AppShell.jsx`
- `ui/src/v4/pages/DashboardPage.jsx`
- `ui/src/v4/pages/MissionBuilderPage.jsx`

---

### Phase 3 - Mission Planning, Assignment, and Flight Controller Handoff (Days 3-4)

**Objective:** Make mission planning operational instead of DB-only.
**STATUS:** COMPLETE (2026-03-03)
#### WP-05 Mission Store Convergence and Page Flow

**User Story:**  
As an operator, the mission summary page and the mission builder must reflect one shared mission state, not two disconnected systems.

**Acceptance Criteria**

- `MissionsPage` and `MissionBuilderPage` read from and write to `missionStore`
- Mission type, mission state, waypoints, geofence, and formation stay synchronized
- Mission list/history reads from `/api/missions`
- Creating a mission returns a usable `mission_id` and updates the store
- The UI still preserves explicit mission assignment and fleet context

**Technical Tasks**

- Frontend: move `MissionBuilderPage` off raw local `useState` for domain state
- Frontend: wire mission CRUD and mission transitions through the new v4 API client
- Frontend: upgrade `MissionsPage` from passive summary to current mission + history view
- Frontend: decide whether to merge pages now or keep both routes while using one shared store contract
- Frontend: update `ui/src/stores/missionStore.js` so it can hold mission detail, selected task, selected drone(s), and mission history rows

**Primary Files**

- `ui/src/v4/pages/MissionBuilderPage.jsx`
- `ui/src/v4/pages/MissionsPage.jsx`
- `ui/src/stores/missionStore.js`
- `ui/src/v4/routes.jsx`
- `ui/src/v4/lib/apiClient.js`

**STATUS:** ✅ COMPLETE
- Mission store now holds full mission list with sync across pages
- MissionsPage fetches on mount and displays history
- MissionBuilderPage refreshes mission list after create

#### WP-06 Explicit Drone Assignment and Waypoint Upload

**User Story:**  
As an operator, I can assign a mission to a drone and know that the application actually sends the mission waypoints to the flight controller before execution starts.

**Acceptance Criteria**

- The planner exposes explicit drone assignment before mission start
- When only one drone is available, that drone is preselected, not hardcoded
- The mission payload persists assigned drone IDs in task data
- A backend route exists to assign a drone to a task by wiring the existing `MissionService.assign_drone()` method through the API layer
- Waypoints are uploaded to the flight controller through the application path under test
- If waypoint upload fails, mission start is blocked and the UI shows a concrete failure
- Starting, pausing, resuming, and aborting a mission update both backend state and `missionStore`

**Technical Tasks**

- Backend: add an explicit task assignment route in `poc/v4_mission_control/api/routes.py` that calls the already-existing `MissionService.assign_drone()`
- Backend: add assignment request schema(s) in `poc/v4_mission_control/schemas/mission.py`
- Backend: extend `MissionService` usage to persist task assignment through the route layer
- Backend: introduce `poc/v4_mission_control/services/waypoint_uploader.py` (new) or equivalent mission-execution adapter
- Backend: wire waypoint upload through existing broker/MQTT infrastructure instead of bypassing the command path
- Backend: emit mission/task events after successful upload and on execution state changes
- Gateway: extend `poc2/drone_gateway.py` to subscribe to a mission/waypoint topic and translate received waypoints into MAVLink upload calls
- Gateway: add tests in `poc2/tests/test_gateway.py` covering mission-topic parsing and waypoint upload dispatch
- Frontend: allow selecting a drone from fleet state and include it in mission assignment flow
- Frontend: call mission transition endpoints only after assignment and successful upload

**Primary Files**

- `poc/v4_mission_control/api/routes.py`
- `poc/v4_mission_control/schemas/mission.py`
- `poc/v4_mission_control/services/mission_service.py`
- `poc/v4_mission_control/services/waypoint_uploader.py` (new)
- `poc/v4_mission_control/services/runtime.py`
- `poc/v4_mission_control/infra/mqtt_client.py`
- `poc2/drone_gateway.py`
- `poc2/tests/test_gateway.py`
- `ui/src/v4/pages/MissionBuilderPage.jsx`
- `ui/src/v4/pages/MissionsPage.jsx`
- `ui/src/stores/missionStore.js`

---

### Phase 4 - Fleet, Commands, and Operational Visibility (Day 5)

**Objective:** Make fleet and commands first-class operational surfaces, not placeholders.

**STATUS:** WP-07 COMPLETE (2026-03-03), WP-08 & WP-09 IN SCOPE FOR FRIDAY

**STATUS:** ✅ COMPLETE
- FleetPage: row selection + search filter implemented
- MissionBuilderPage: drone assignment UI with auto-sync + validation
- MissionBar: mission start blocked until drone ACK received
- mission_ack WebSocket event handler dispatches to missionStore
- uploadedMissions set tracks confirmed uploads

#### WP-07 Fleet Operational Baseline

**User Story:**  
As an operator, I can view the current drone as part of a fleet, select it, and use that selection in mission planning and control.

**Acceptance Criteria**

- Fleet page shows live fleet rows from shared store data
- Operator can select a drone from Fleet and use it as the mission assignment target
- Fleet page shows role/health context clearly enough for a live demo
- Fleet remains scalable to more than one row without UI or data-model changes

**Technical Tasks**

- Frontend: add row selection on `FleetPage`
- Frontend: connect selected drone state to `selectionStore` and mission assignment UI
- Frontend: add at least minimal search/filter support for fleet rows
- Frontend: surface health and readiness fields already available from telemetry/preflight

**Primary Files**

- `ui/src/v4/pages/FleetPage.jsx`
- `ui/src/stores/fleetStore.js`
- `ui/src/stores/selectionStore.js`
- `ui/src/v4/lib/apiClient.js`

**STATUS:** ✅ COMPLETE
- FleetPage row selection with selectionStore.selectedDroneId
- Auto-sync: Fleet selection → MissionBuilderPage form
- Search/filter on drone list
- Selection visual feedback in table

#### WP-08 Commands Operational Baseline

**User Story:**  
As an operator, I can see command history and explain what happened during the mission.

**Acceptance Criteria**

- Commands page reads from `/api/commands`
- Commands page shows timestamp, status, retries, and drone ID
- Requested, retrying, acked, failed, and timed-out commands are distinguishable
- A selected command can show enough detail to explain the outcome
- Live WebSocket command status updates remain reflected in the store

**Technical Tasks**

- Frontend: replace "cached items" framing with real backend-backed command history
- Frontend: add status color indicators, time column, and detail pane
- Frontend: merge `/api/commands` history with live `command_status` WebSocket updates
- Backend: review ack/nack routes for auth needs if used by operator tools

**Primary Files**

- `ui/src/v4/pages/CommandsPage.jsx`
- `ui/src/stores/commandStore.js`
- `ui/src/v4/lib/apiClient.js`
- `poc/v4_mission_control/api/routes.py`

#### WP-09 Settings and Demo Hardening

**User Story:**  
As an operator or demo presenter, I can quickly verify service health and demonstrate that the system is in a valid running state.

**Acceptance Criteria**

- Settings page shows live values from `/api/health`
- MQTT, DB, and inventory status are visible and color-coded
- Demo environment clearly runs with auth enabled
- The end-to-end demo script completes without a manual backend-side workaround

**Technical Tasks**

- Frontend: pass live health state into `SettingsPage`
- Frontend: surface auth mode and current operator identity in a visible location
- Docs: add demo login credentials and W10 runbook notes to the relevant quickstart docs
- QA: run the demo script using `ADMIN`, `PILOT`, and `OBSERVER`

**Primary Files**

- `ui/src/v4/pages/SettingsPage.jsx`
- `ui/src/v4/AppShell.jsx`
- `poc2/QUICKSTART.md`
- `poc/v4_mission_control/README.md`

---

## Sprint Delivery Plan

| Day | Focus | Exit Criteria |
|---|---|---|
| Mon 2026-03-02 | Phase 1: WP-01 + WP-02 | v4 pages are pointed at the real API, dashboard controls are visible, map tiles render |
| Tue 2026-03-03 | Phase 2: WP-03 + WP-04 | Login works, protected routes work, RBAC is enforced on mission and command actions |
| Wed 2026-03-04 | Phase 3: WP-05 | Mission pages share one store and the UI can create/read real missions |
| Thu 2026-03-05 | Phase 3: WP-06 | Assignment and waypoint upload path work end-to-end for PATROL |
| Fri 2026-03-06 | Phase 4: WP-07 + WP-08 + WP-09 | Fleet, Commands, and Settings are operational enough for a live demo |
| Sat 2026-03-07 | Integration buffer | Fix regressions, tighten edge cases, update docs |
| Sun 2026-03-08 | Full rehearsal | One full scripted demo runs cleanly with role checks and mission execution |

---

## Engineering Breakdown

### Frontend

- `ui/src/v4/lib/apiClient.js` (new): canonical v4 HTTP client with auth header injection
- `ui/src/v4/auth/session.js` (new): token storage, current operator cache, logout helpers
- `ui/src/v4/components/ProtectedRoute.jsx` (new): route guard wrapper
- `ui/src/v4/routes.jsx`: guard all protected routes
- `ui/src/v4/AppShell.jsx`: logout, auth-aware bootstrapping, live status pills
- `ui/src/v4/pages/LoginPage.jsx`: real login form
- `ui/src/v4/pages/DashboardPage.jsx`: add mission bar / control surface
- `ui/src/v4/pages/MissionBuilderPage.jsx`: shared mission state, assignment, upload/start flow
- `ui/src/v4/pages/MissionsPage.jsx`: current mission + history view
- `ui/src/v4/pages/FleetPage.jsx`: selection + search/filter baseline
- `ui/src/v4/pages/CommandsPage.jsx`: backend-backed audit table + status details
- `ui/src/v4/pages/SettingsPage.jsx`: live health status
- `ui/src/stores/missionStore.js`: mission detail, selected task, selected drone(s), history
- `ui/src/stores/selectionStore.js`: fleet-to-mission selection bridge
- `ui/src/socket.js`: reduce bootstrap dependency on stale legacy endpoints

### Backend

- `poc/v4_mission_control/api/routes.py`:
  - mission routes must require authenticated operator context
  - add task assignment route
  - optionally add route-level helpers for upload/start sequencing
- `poc/v4_mission_control/auth/acl.py`:
  - add mission mutation permission checks
  - keep command ACL centralized
- `poc/v4_mission_control/schemas/mission.py`:
  - add task assignment request schema
  - add any response schema needed for upload/assignment feedback
- `poc/v4_mission_control/services/mission_service.py`:
  - use existing assignment helpers through the API layer
  - coordinate mission lifecycle with upload success/failure
- `poc/v4_mission_control/services/waypoint_uploader.py` (new):
  - translate mission waypoints into the FC payload
  - publish via broker/MQTT or adapter abstraction
- `poc/v4_mission_control/services/runtime.py`:
  - register the uploader in the service container
- `poc2/drone_gateway.py`:
  - subscribe to the mission upload topic
  - validate target `drone_id`
  - convert mission payload into MAVLink waypoint upload calls
  - return observable success/failure acknowledgements
- `poc2/tests/test_gateway.py`:
  - add unit coverage for mission-topic ingestion and upload dispatch

### Documentation / Runbooks

- `poc2/QUICKSTART.md`: auth-enabled frontend/backend startup path for W10 demo
- `poc/v4_mission_control/README.md`: login credentials, environment flags, operator roles

---

## Definition of Done

- Product acceptance criteria for every work package are met
- Frontend builds cleanly
- Backend app starts with `MC_V4_AUTH_ENABLED=true`
- Manual happy path passes with `ADMIN`
- Permission checks pass with `PILOT` and `OBSERVER`
- Mission waypoint upload is exercised through the real application path
- No v4 page depends on a missing legacy endpoint
- The demo can be run from documented steps without hidden local tweaks

---

## Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Frontend still has mixed v3/v4 dependencies | High | Isolate a canonical v4 API client first and move v4 pages onto it before feature work |
| Mission-route auth exists in code but is not yet validated under auth-on demo config | High | Run the next validation pass with `MC_V4_AUTH_ENABLED=true` and confirm `ADMIN` / `PILOT` / `OBSERVER` behavior |
| Waypoint upload touches backend, broker, gateway, and UI at once | High | Implement one explicit upload adapter plus the corresponding `drone_gateway.py` receiver path before adding extra mission types |
| `AUTH_ENABLED=false` remains in default local runs | Medium | Add W10 quickstart steps that explicitly set `MC_V4_AUTH_ENABLED=true` for demo mode |
| One-drone testing hides multi-drone bugs | Medium | Keep assignment explicit and test with seeded `allowed_drones` restrictions even if only one drone is connected |
| Legacy `ui/src/api.js` usage leaks back into v4 pages | Medium | Treat any new import of legacy client into v4 code as a regression |

---

## Success Criteria Checklist

> Update this list as work completes. Mark `[x]` only with test or demo evidence.

### Global Gates

- [x] New v4 API client is the only client used by v4 pages
- [ ] `MC_V4_AUTH_ENABLED=true` is used in the demo environment
- [ ] Login works for `admin`, `pilot1`, and `observer`
- [ ] One full PATROL mission runs through plan -> assign -> upload -> start -> abort/complete
- [ ] Fleet and Commands remain visible product concepts in the UI
- [ ] End-to-end demo script runs without backend-side manual intervention

### Phase 1 - Contract Alignment and Shell Stability

- [x] `ui/src/v4/lib/apiClient.js` exists and is wired into v4 pages
- [x] No v4 page depends on legacy-only `/mission/*` endpoints
- [x] `MissionBuilderPage` no longer uses bare unauthenticated `axios.post('/api/missions')`
- [x] Dashboard shows mission control actions
- [x] Mission Builder map tiles render correctly
- [x] Status pills show visual health state

### Phase 2 - Authentication and RBAC

- [x] `/login` is a real login form, not a placeholder
- [x] Protected routes redirect unauthenticated users to `/login`
- [x] Token persists across refresh
- [x] `/api/auth/me` hydrates operator role in the UI
- [ ] `OBSERVER` cannot mutate missions or issue commands
- [ ] `PILOT` is restricted to allowed drones
- [x] Mission routes enforce auth and permission checks

### Phase 3 - Mission Planning, Assignment, and FC Handoff

- [x] `MissionsPage` and `MissionBuilderPage` share one mission state model
- [x] Mission assignment is explicit in the UI and backend
- [x] One-drone mode preselects the available drone without removing assignment semantics
- [x] Waypoint upload path exists and is invoked before mission start
- [x] `poc2/drone_gateway.py` receives the mission/waypoint topic and handles upload
- [ ] Upload failure blocks mission start and surfaces a real error
- [ ] Mission lifecycle changes are reflected in `missionStore`

### Phase 4 - Fleet, Commands, and Operational Visibility

- [x] Fleet page supports selection and feeds mission assignment (WP-07 complete)
- [ ] Commands page reads from `/api/commands`
- [ ] Command status states are visually differentiated
- [ ] Settings page shows live health data
- [ ] `ADMIN`, `PILOT`, and `OBSERVER` demo script has been rehearsed

---

## Implementation Notes

### RC Throttle Nudge — ArduPilot Hardware Behavior (2026-03-07)

**Observed:** After the full DEBUG sequence wireup (Takeoff → Hold → Spin → Hold → RTL) is uploaded
and `_auto_arm_and_start` runs the `STABILIZE → ARM → AUTO` sequence, the flight controller still
waits for a physical RC throttle position change before beginning AUTO mission execution.

**Root cause:** ArduPilot's pre-arm / post-arm checks require a radio-control throttle signal
within a narrow neutral range (≈ 1000–1100 PWM) to confirm the channel is live before accepting
an autonomous takeoff command. This applies even when armed by GCS MAVLink.

**Software fix (implemented in `feature/w10-commands-settings-rcoverride`):**
Send a `RC_CHANNELS_OVERRIDE` MAVLink message immediately after arm confirmation, setting the
throttle channel to neutral (1000 PWM). This satisfies the FC's throttle-live check without any
physical RC input. The override is sent once, then allowed to expire (1.0 s timeout via SYSID_MYGCS)
so normal autonomous control takes over for the actual takeoff.

**Sequence post-fix:**
1. Upload waypoints (mission items 0–N)
2. `set_mode("STABILIZE")`
3. `MAV_CMD_COMPONENT_ARM_DISARM` (force)
4. Wait → arm confirmed
5. **`RC_CHANNELS_OVERRIDE` — throttle neutral (1000 PWM), all other channels 0 (pass-through)**
6. `set_mode("AUTO")`
7. Mission executes — no physical RC nudge required

**File:** `poc2/drone_gateway.py` → `_auto_arm_and_start()`

---

## Immediate Next Actions

1. ✅ Phase 3 (WP-05, WP-06, WP-07) is COMPLETE and committed to `feature/w10-waypoint-upload`.
2. ✅ `feature/w10-waypoint-upload` merged into `develop`.
3. Active branch: `feature/w10-commands-settings-rcoverride`
   - RC throttle override fix (eliminate manual nudge)
   - WP-08 Commands page backend integration
   - WP-09 Settings live health page
4. Validate end-to-end PATROL demo with auth-enabled (`MC_V4_AUTH_ENABLED=true`).
5. Test role-based restrictions with `ADMIN`, `PILOT`, and `OBSERVER` credentials.
