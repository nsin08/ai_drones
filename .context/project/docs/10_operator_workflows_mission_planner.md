# Operator Workflows (Mission Planner)

## SITL workflow (no hardware)
Mission Planner supports SITL simulation via its Simulation tab, allowing mission testing without a real vehicle.  [ref]

Operator steps:
1) Start Simulation (choose vehicle type/frame)
2) Connect (UDP)
3) Arm/takeoff in a safe mode
4) Load a mission (waypoints)
5) Start mission, observe behavior

## Executing AI plans (MVP manual execution)
1) Subscribe to fleet/groups/<groupId>/plan/<intentId>
2) Review per-drone tasks
3) In Mission Planner:
   - set mode (GUIDED/AUTO as appropriate)
   - upload mission or set guided target
4) Publish ACK:
   - fleet/acks/<intentId> with decision EXECUTED and notes
