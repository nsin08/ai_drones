# Roles v1 (7 Roles)

These are *behavior templates* and constraints, not permissions.

## Role: LEADER
Purpose: coordinates group pace, holds mission context, assigns/updates formation parameters.
Constraints:
- prefers stable link quality
- prioritizes mission completion and safety
Outputs:
- group intent refinement (speed, formation, waypoint cadence)

## Role: POINT_MAN
Purpose: advances ahead of group, detects hazards, triggers early warnings.
Constraints:
- must maintain higher reserve threshold (e.g., RTL earlier)
- higher risk tolerance but bounded by policy
Outputs:
- hazard events (GPS anomaly, wind/fault indications, obstacle flags if available)

## Role: WINGMAN
Purpose: maintains formation offset, covers flanks, maintains visual/coverage buffer.
Constraints:
- strict formation adherence unless safety overrides
Outputs:
- formation integrity metrics (distance-to-leader, spacing breaches)

## Role: SCOUT
Purpose: wider sweep / recon, early situational awareness.
Constraints:
- may operate at different altitude band
- must not compromise comms or geofence policy
Outputs:
- coverage status and “area searched” progress

## Role: RELAY
Purpose: maximize comms reliability, act as bridge node, monitor link health.
Constraints:
- prioritizes link quality and stability
- often holds position at optimal comms location
Outputs:
- link quality metrics, “telemetry gap risk” alerts

## Role: GUARD
Purpose: static or slow-move perimeter watch, sector coverage and alerting.
Constraints:
- maintains assigned sector boundaries
- prioritizes stability and detection over speed
Outputs:
- perimeter breach alerts, sector coverage health

## Role: CARGO
Purpose: payload delivery and logistics support.
Constraints:
- follows payload safety constraints (shock, temp, tilt as applicable)
- prioritizes safe route and landing precision
Outputs:
- payload status, delivery milestones, landing approach health

## Role invariants (all roles)
- Never override ArduPilot safety failsafes
- Never execute irreversible actions without approval gate (MVP)
- Always publish:
  - role status
  - role health
  - role-specific KPIs
