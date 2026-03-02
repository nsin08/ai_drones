# V4 Demo Roadmap — Operational Thin Slice

**Author:** AI Agent (Codex)  
**Date:** 2026-03-03  
**Scope:** Delivery roadmap for a real demoable v4 system  
**Status:** Draft for execution

---

## 1. Purpose

This document is the demo-focused companion to `V4_UI_REDESIGN_PROPOSAL.md`.

The redesign proposal remains the reference for long-term UI structure and consolidation. This roadmap is the reference for the **next working demo**: a thin but real operational slice that must function correctly end-to-end.

Current constraint: only **1 physical drone** is available today.  
Strategic requirement: the application must still preserve the **multi-drone / fleet / mission** model because more drones will be added later.

This means the demo should be **single-drone in operations**, but **not single-drone in architecture**.

---

## 2. Non-Negotiables

The demo roadmap must not remove or weaken these core concepts:

1. Fleet remains a first-class concept.
2. Commands remain a first-class concept.
3. Mission planning remains assignment-aware, even if the default selected drone is the only connected drone.
4. Authentication must work end-to-end.
5. User roles / permissions must work end-to-end.
6. Mission plans must be persisted, reviewable, and executable.
7. Backend and UI must keep the domain model multi-drone capable.

The correct approach is:

- Keep the fleet model.
- Keep the command model.
- Keep mission-to-drone assignment in the data flow.
- Use the current one-drone reality only to simplify defaults and test coverage, not to delete capability.

The wrong approach is:

- Hiding or removing Fleet/Commands as product concepts.
- Converting mission assignment into a hardcoded single-drone assumption.
- Treating auth/RBAC as optional for the demo.

---

## 3. Demo Definition

The system is "demoable" only when the following workflow works with a real operator and a real drone:

1. User logs in successfully.
2. User role is enforced correctly (UI actions and backend permissions match).
3. Dashboard shows live telemetry and current service status.
4. Fleet view shows the connected drone as part of a fleet model.
5. Operator can create or edit a mission plan.
6. Operator can assign the mission to a drone.
7. Waypoints are uploaded to the flight controller.
8. Mission execution starts and state updates are visible in real time.
9. Operator can issue mission and vehicle commands (`Pause`, `Resume`, `Abort`, `Return`, etc.) according to role permissions.
10. Mission completion or abort is reflected in mission history and current state.

If any of the above is missing, the system may be "partially working," but it is not yet a complete demo.

---

## 4. Scope Principles

### 4.1 Keep the domain complete

Even for a one-drone demo, the following entities should remain explicit in the backend and UI:

- `User`
- `Role`
- `Drone`
- `Fleet`
- `MissionPlan`
- `MissionExecution`
- `Command`
- `Telemetry`

The demo should prove that these concepts already work together, not hide them.

### 4.2 Simplify defaults, not architecture

Allowed simplifications:

- Preselect the only connected drone in mission assignment.
- Reduce test scenarios to one active aircraft.
- Keep the fleet table small because only one row is currently real.

Not allowed:

- Removing assignment from the mission data model.
- Removing Fleet or Commands pages from the product direction.
- Disabling role-based action gating.
- Replacing mission execution with "DB write only."

### 4.3 Thin slice over polish

The demo must prioritize correctness over visual completion:

- Real execution path before cosmetic redesign.
- Working permissions before layout polish.
- Working command lifecycle before advanced filters.
- Stable PATROL flow before additional mission templates.

---

## 5. Demo-Required Functional Areas

### 5.1 Authentication and Roles

These must be fully working for the demo:

- Login flow
- Session/token handling
- Route protection
- Backend authorization checks
- Role-aware action visibility

Minimum role behaviors:

- `Admin`: full access, including configuration and mission override actions
- `Operator`: can plan, assign, launch, pause, resume, abort, and issue allowed drone commands
- `Viewer`: read-only access to telemetry, fleet state, mission state, and history

The demo should show that unauthorized actions are both:

- Hidden or disabled in the UI
- Rejected by backend policy if invoked directly

### 5.2 Fleet and Commands

Fleet and Commands are still in scope for the demo. They do not need every future enhancement, but they must be operational.

Fleet must support:

- Live drone presence/state
- Selection of a drone
- Role/health visibility
- Assignment target for missions

Commands must support:

- Issuing core commands to the assigned drone
- Showing command status
- Showing acknowledgements / failures
- Showing enough history to explain what happened during the demo

### 5.3 Mission Planning and Execution

Mission planning must be fully connected to execution.

Required path:

1. Create or edit a mission plan
2. Assign it to a drone
3. Persist it in the backend
4. Upload waypoints to the flight controller
5. Start mission execution
6. Reflect mission state back to shared state/UI
7. Support operator interruption (`Pause`, `Resume`, `Abort`, `Return`)

For the first demo, `PATROL` is the required mission type.

Other mission types can remain present in the domain model, but they should not block the PATROL flow from becoming fully operational.

---

## 6. Recommended Execution Order

### Phase 1 — Operator Control Surface (1–2 days)

Goal: make the operator-facing shell trustworthy during a live demo.

| Task | Priority | Outcome |
|------|----------|---------|
| Confirm and keep WebSocket bootstrap stable in `AppShell` | Critical | Live telemetry, fleet, mission, and command updates remain available |
| Restore `TopBar` / mission control bar on Dashboard | Critical | Operator can pause, resume, abort, and see mission state |
| Fix Mission Builder map tile rendering | Critical | Route planning is usable |
| Add status pill color coding | High | Service health is legible in real time |
| Ensure Fleet and Commands links remain available in nav | High | Product model remains visibly fleet-oriented |

### Phase 2 — Mission Execution Path (2–4 days)

Goal: make mission planning actually fly.

| Task | Priority | Outcome |
|------|----------|---------|
| Wire Mission Builder to shared `missionStore` | Critical | Planning, dashboard, and mission state are synchronized |
| Keep explicit mission-to-drone assignment in the flow | Critical | Architecture remains multi-drone ready |
| Preselect the only connected drone when fleet size is 1 | High | Faster demo flow without removing assignment semantics |
| Implement waypoint upload to the flight controller | Critical | Mission plan becomes executable |
| Reflect FC acceptance / mission status transitions into `missionStore` | Critical | UI shows real lifecycle, not guessed state |
| Keep PATROL as the first fully supported mission flow | High | One complete thin slice is operational |

### Phase 3 — Authentication and RBAC Hardening (1–2 days)

Goal: make the demo valid from a security and operations standpoint.

| Task | Priority | Outcome |
|------|----------|---------|
| Implement or finish login flow | Critical | Users can authenticate cleanly |
| Enforce route guards across v4 pages | Critical | Unauthenticated access is blocked |
| Enforce role checks for mission and drone commands | Critical | Admin/Operator/Viewer behavior is real |
| Audit backend authorization on mission, command, and settings endpoints | Critical | UI and backend permissions match |
| Show role-aware UI states | High | Demo clearly communicates permission boundaries |

### Phase 4 — Demo Readiness Pass (1–2 days)

Goal: remove the remaining failures that can break a live demo.

| Task | Priority | Outcome |
|------|----------|---------|
| Verify Fleet page reflects current drone and can scale to more rows | High | One drone today, no redesign needed when more appear |
| Verify Commands page shows live command lifecycle clearly | High | Operator can explain actions taken during the demo |
| Wire Settings to live health data | Medium | Useful service visibility during the demo |
| Reduce obvious inline-style/theme mismatches | Medium | UI looks intentional without blocking function |
| Run a scripted end-to-end operator rehearsal | Critical | Demo path is repeatable under time pressure |

---

## 7. Acceptance Criteria

The demo is ready when all of the following are true:

1. A user can log in and remain authenticated across the session.
2. Viewer cannot execute mission/drone actions.
3. Operator can create, assign, upload, and execute a PATROL mission.
4. Admin can perform all operator actions plus privileged actions.
5. The assigned drone receives uploaded waypoints from the application path under test.
6. Dashboard telemetry updates while the mission is active.
7. Fleet view still represents the drone as a fleet member, not a special-case singleton.
8. Commands view shows command request and acknowledgement/failure history.
9. Abort/Return works from the operator control surface.
10. Mission completion/abort is visible in mission state and history.

---

## 8. Explicit Deferrals

These can wait until after the first complete demo, as long as they do not break the core flow:

- Advanced mission templates
- Undo/redo in the planner
- Drag-to-reorder waypoints on-map
- Full CSS architecture cleanup
- Native visual redesign parity across every page
- Mobile-first navigation polish

These are **not** deferrals:

- Fleet model
- Commands model
- Mission assignment
- Authentication
- User roles / RBAC
- Flight-controller waypoint upload

---

## 9. Relationship to the UI Redesign Proposal

Use the documents this way:

- `V4_UI_REDESIGN_PROPOSAL.md`: long-term product/UI structure and page architecture
- `V4_DEMO_ROADMAP.md`: short-term execution reference for the next real demo

The demo roadmap should override the redesign proposal only for sequencing and delivery order. It should not redefine the long-term product model.
