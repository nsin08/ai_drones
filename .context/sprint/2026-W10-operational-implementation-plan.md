# Sprint 2026-W10

**Dates:** 2026-03-02 to 2026-03-08  
**Document Type:** Operational UI Delivery Plan - phased implementation  
**Recommended Branch:** `feature/w10-operational-ui`  
**Primary References:** `V4_UI_REDESIGN_PROPOSAL.md`, `V4_DEMO_ROADMAP.md`

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
2. `ui/src/socket.js` is already a native `/ws` client, but it still bootstraps from `ui/src/api.js`, which points at legacy endpoints such as `/inventory`, `/home_base`, `/state/snapshot`, and `/mission/*`.
3. `poc/v4_mission_control/api/routes.py` already exposes `/api/auth/token`, `/api/auth/me`, `/api/missions`, `/api/commands`, and `/ws`, but the frontend is not built around those contracts yet.
4. Command routes use `get_current_operator` and `check_command_permission`, but mission create/transition routes do not yet enforce authenticated operator context.
5. The backend mission FSM exists, but there is still no explicit API path for task-to-drone assignment or waypoint upload to the flight controller.

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
- Run the demo environment with `MC_V4_AUTH_ENABLED=true`.

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
- Socket bootstrap no longer depends on missing legacy bootstrap endpoints for its critical path.

**Technical Tasks**

- Frontend: create `ui/src/v4/lib/apiClient.js` (new) with:
  - base URL `/api`
  - token injection from session storage/local storage
  - helpers for `login`, `me`, `listMissions`, `createMission`, `transitionMission`, `listCommands`, `listFleetHealth`
- Frontend: keep `ui/src/api.js` for legacy/v3 code only; stop importing it from new or refactored v4 code paths
- Frontend: update `ui/src/socket.js` bootstrap path so missing legacy endpoints do not break v4 readiness
- Backend: add any missing route adapters only if the v4 UI cannot be cleanly moved to canonical routes

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

- Backend: add mission-specific ACL helpers in `poc/v4_mission_control/auth/acl.py`
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

#### WP-06 Explicit Drone Assignment and Waypoint Upload

**User Story:**  
As an operator, I can assign a mission to a drone and know that the application actually sends the mission waypoints to the flight controller before execution starts.

**Acceptance Criteria**

- The planner exposes explicit drone assignment before mission start
- When only one drone is available, that drone is preselected, not hardcoded
- The mission payload persists assigned drone IDs in task data
- A backend route exists to assign a drone to a task (or mission create accepts finalized assignment)
- Waypoints are uploaded to the flight controller through the application path under test
- If waypoint upload fails, mission start is blocked and the UI shows a concrete failure
- Starting, pausing, resuming, and aborting a mission update both backend state and `missionStore`

**Technical Tasks**

- Backend: add an explicit task assignment route in `poc/v4_mission_control/api/routes.py`
- Backend: add assignment request schema(s) in `poc/v4_mission_control/schemas/mission.py`
- Backend: extend `MissionService` usage to persist task assignment through the route layer
- Backend: introduce `poc/v4_mission_control/services/waypoint_uploader.py` (new) or equivalent mission-execution adapter
- Backend: wire waypoint upload through existing broker/MQTT infrastructure instead of bypassing the command path
- Backend: emit mission/task events after successful upload and on execution state changes
- Frontend: allow selecting a drone from fleet state and include it in mission assignment flow
- Frontend: call mission transition endpoints only after assignment and successful upload

**Primary Files**

- `poc/v4_mission_control/api/routes.py`
- `poc/v4_mission_control/schemas/mission.py`
- `poc/v4_mission_control/services/mission_service.py`
- `poc/v4_mission_control/services/waypoint_uploader.py` (new)
- `poc/v4_mission_control/services/runtime.py`
- `poc/v4_mission_control/infra/mqtt_client.py`
- `ui/src/v4/pages/MissionBuilderPage.jsx`
- `ui/src/v4/pages/MissionsPage.jsx`
- `ui/src/stores/missionStore.js`

---

### Phase 4 - Fleet, Commands, and Operational Visibility (Day 5)

**Objective:** Make fleet and commands first-class operational surfaces, not placeholders.

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
| Mission routes currently lack auth enforcement | High | Treat mission ACL as Phase 2 P0 work, not polish |
| Waypoint upload touches backend, broker, and UI at once | High | Implement one explicit upload adapter with observable success/failure states before adding extra mission types |
| `AUTH_ENABLED=false` remains in default local runs | Medium | Add W10 quickstart steps that explicitly set `MC_V4_AUTH_ENABLED=true` for demo mode |
| One-drone testing hides multi-drone bugs | Medium | Keep assignment explicit and test with seeded `allowed_drones` restrictions even if only one drone is connected |
| Legacy `ui/src/api.js` usage leaks back into v4 pages | Medium | Treat any new import of legacy client into v4 code as a regression |

---

## Success Criteria Checklist

> Update this list as work completes. Mark `[x]` only with test or demo evidence.

### Global Gates

- [ ] New v4 API client is the only client used by v4 pages
- [ ] `MC_V4_AUTH_ENABLED=true` is used in the demo environment
- [ ] Login works for `admin`, `pilot1`, and `observer`
- [ ] One full PATROL mission runs through plan -> assign -> upload -> start -> abort/complete
- [ ] Fleet and Commands remain visible product concepts in the UI
- [ ] End-to-end demo script runs without backend-side manual intervention

### Phase 1 - Contract Alignment and Shell Stability

- [ ] `ui/src/v4/lib/apiClient.js` exists and is wired into v4 pages
- [ ] No v4 page depends on legacy-only `/mission/*` endpoints
- [ ] Dashboard shows mission control actions
- [ ] Mission Builder map tiles render correctly
- [ ] Status pills show visual health state

### Phase 2 - Authentication and RBAC

- [ ] `/login` is a real login form, not a placeholder
- [ ] Protected routes redirect unauthenticated users to `/login`
- [ ] Token persists across refresh
- [ ] `/api/auth/me` hydrates operator role in the UI
- [ ] `OBSERVER` cannot mutate missions or issue commands
- [ ] `PILOT` is restricted to allowed drones
- [ ] Mission routes enforce auth and permission checks

### Phase 3 - Mission Planning, Assignment, and FC Handoff

- [ ] `MissionsPage` and `MissionBuilderPage` share one mission state model
- [ ] Mission assignment is explicit in the UI and backend
- [ ] One-drone mode preselects the available drone without removing assignment semantics
- [ ] Waypoint upload path exists and is invoked before mission start
- [ ] Upload failure blocks mission start and surfaces a real error
- [ ] Mission lifecycle changes are reflected in `missionStore`

### Phase 4 - Fleet, Commands, and Operational Visibility

- [ ] Fleet page supports selection and feeds mission assignment
- [ ] Commands page reads from `/api/commands`
- [ ] Command status states are visually differentiated
- [ ] Settings page shows live health data
- [ ] `ADMIN`, `PILOT`, and `OBSERVER` demo script has been rehearsed

---

## Immediate Next Actions

1. Create the canonical v4 API client and stop adding new v4 logic to `ui/src/api.js`.
2. Replace the placeholder login page and add protected routing.
3. Add mission-route auth enforcement before touching the waypoint upload path.
