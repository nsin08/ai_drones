# Acceptance Criteria (MVP)

## Fleet monitoring
- Can simulate >= 20 drones publishing telemetry
- Dashboard consumer can subscribe and see per-drone state updates
- System computes "telemetry stale" correctly

## Roles & groups
- Can create group G01 with 5 drones and assign 5 roles
- Can reassign role on-the-fly and observe update

## Missions
- PATROL: planner emits per-drone plan with route/offset tasks
- ESCORT: planner emits formation offsets around moving asset (simulated)
- PERIMETER_GUARD: planner emits sector hold tasks and rotation suggestions

## Fault simulation
- RF burst loss simulated: telemetry gap event emitted
- GNSS multipath simulated: gps anomaly event emitted
- Battery sag simulated: early low-battery recommendation emitted

## AI-assisted ops
- AI publishes recommendation with evidence + proposed action
- Operator ACK workflow supported via MQTT ack message

## Mission Planner integration (manual)
- Operator can connect to SITL in Mission Planner and execute a plan step (e.g., mission upload / guided goto)
