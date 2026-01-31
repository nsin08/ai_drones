# Mission Control Dashboard Demo Guide

## Overview

The Mission Control Dashboard is an interactive web interface for monitoring and controlling drone fleet operations in real-time. It features:

- **Live Map Visualization**: Drone positions with movement traces
- **Command Interface**: Disable/enable drones to test resilience
- **Leader Election**: Automatic failover when leader fails
- **Real-time Updates**: WebSocket streaming of telemetry

## Quick Start

### 1. Start Infrastructure

```bash
cd ops
docker compose up -d
```

Verify all services are healthy:
```bash
docker compose ps
```

Expected output:
- mosquitto-broker: Up (port 1883)
- influxdb: Up (port 8086)
- grafana: Up (port 3000)
- telegraf: Up

### 2. Start Mission Control Dashboard

```bash
cd poc
pip install flask flask-socketio flask-cors paho-mqtt  # First time only
python mission_control.py
```

The dashboard will start on http://localhost:5000

### 3. Start a Mission

In a new terminal:

```bash
cd poc
python mission_simulator.py --mission escort --duration 300
```

Or run all missions sequentially:

```bash
python mission_simulator.py --mission all --duration 120
```

## Dashboard Features

### Map View

- **Drone Markers**: Colored circles showing current position
  - Red = LEADER
  - Green = WINGMAN
  - Yellow = POINT_MAN
  - Cyan = GUARD
  - Purple = SCOUT

- **Movement Traces**: Colored lines showing path history (last 100 positions)

- **Popups**: Click a marker to see:
  - Drone ID
  - Current role
  - Battery level
  - Altitude

### Control Panel

**Connection Status**: Shows connection to backend (green = connected)

**Leader Status**: Displays current leader, battery, and altitude

**Active Drones List**: Shows all drones with:
- Drone ID and role badge
- Battery level (color-coded: green >70%, yellow 40-70%, red <40%)
- Altitude
- Status (ACTIVE/DISABLED)
- Disable/Enable buttons

**Leader Election History**: Shows chronological list of leadership changes

## Demo Scenarios

### Scenario 1: ESCORT Mission Leader Failure

**Objective**: Demonstrate automatic leader election when protecting a moving asset

**Steps**:

1. Start ESCORT mission:
   ```bash
   python mission_simulator.py --mission escort --duration 300
   ```

2. Open dashboard: http://localhost:5000

3. Wait 30 seconds for mission to stabilize and formation to establish

4. In the control panel, locate **ESCORT-01** (should be marked as LEADER with red badge)

5. Click **Disable** button for ESCORT-01

**Expected Results**:

- ⚠️ Console shows: "Command received: DISABLE ESCORT-01"
- 🎯 Console shows: "Leader election: ESCORT-XX (battery: Y%) promoted from WINGMAN to LEADER"
- Map: ESCORT-01 marker disappears or moves to land position
- Map: New leader marker turns red
- Formation: Remaining drones adjust positions to track asset from new leader
- Control Panel: New leader appears in "Leader Status" section
- History: Leader election event appears at top of history list

**Key Observations**:

- Election is battery-based (highest battery becomes leader)
- Formation maintains asset protection even with one drone down
- No mission disruption - asset continues moving northeast

### Scenario 2: PERIMETER_GUARD Sector Coverage

**Objective**: Demonstrate coverage rebalancing when a sector guard fails

**Steps**:

1. Start PERIMETER_GUARD mission:
   ```bash
   python mission_simulator.py --mission perimeter --duration 300
   ```

2. Open dashboard: http://localhost:5000

3. Wait for perimeter formation to establish (drones rotating around center point)

4. Identify a WINGMAN or SCOUT drone covering a sector (e.g., GUARD-02)

5. Click **Disable** button for that drone

**Expected Results**:

- Console shows: "Command received: DISABLE GUARD-XX"
- Map: Disabled drone marker disappears
- Formation: Remaining drones continue rotating, maintaining coverage
- If LEADER disabled: New leader elected, remains at center
- If GUARD disabled: Perimeter guards adjust rotation to maintain coverage

**Key Observations**:

- LEADER (GUARD-01) coordinates from center position
- WINGMAN and SCOUT drones maintain sector coverage through rotation
- POINT_MAN continues roving the boundary for mobile threats
- System remains operational with degraded coverage

### Scenario 3: Multiple Failures and Recovery

**Objective**: Test system resilience under cascading failures

**Steps**:

1. Start PATROL mission:
   ```bash
   python mission_simulator.py --mission patrol --duration 300
   ```

2. Wait 30 seconds for waypoint progression

3. Disable PATROL-01 (LEADER)
   - New leader elected (likely PATROL-02 POINT_MAN)

4. Wait 20 seconds

5. Disable new leader
   - Another leader elected from remaining drones

6. Re-enable PATROL-01
   - Drone rejoins mission but does NOT automatically reclaim leadership

**Expected Results**:

- Each disable triggers instant leader election
- Formation adapts to current leader position
- Mission continues toward waypoints
- Re-enabled drones rejoin with original role (not LEADER)
- Leader history shows multiple transitions

**Key Observations**:

- Leadership is "sticky" - once elected, leader keeps role until disabled
- Original leader does not reclaim role on re-enable (prevents thrashing)
- Formation is leader-relative (POINT_MAN ahead, WINGMAN flanks, SCOUT sweeps)

## Mission Types

### PATROL Mission

**Formation**:
- LEADER: Follows waypoint route
- POINT_MAN: Runs 60m ahead, probes path
- 2x WINGMAN: Flank leader on left/right 40m back
- SCOUT: Sweeps 100m radius around formation

**Test Focus**:
- Waypoint navigation with formation
- Leader election impact on route following
- POINT_MAN promotion to LEADER (forward position maintained)

### ESCORT Mission

**Formation**:
- LEADER: Tracks protected asset directly
- 2x WINGMAN: Wedge formation 30m ahead, offset left/right
- POINT_MAN: Probes 100m ahead on asset heading
- RELAY: Maintains comms anchor 50m behind

**Test Focus**:
- Asset-relative positioning
- Leader election during asset movement
- Protection envelope maintained despite failures

### PERIMETER_GUARD Mission

**Formation**:
- LEADER: Coordinator at perimeter center (70m altitude)
- 3x GUARD (WINGMAN/SCOUT): Rotate through 120° sectors at 500m radius
- POINT_MAN: Fast rove around boundary (watches for mobile threats)

**Test Focus**:
- Sector coverage with reduced force
- Leader coordination role (doesn't move)
- Rotation adjustment when guard disabled

## Technical Architecture

```
Browser (Leaflet Map + WebSocket Client)
           ↕
Flask Server (http://localhost:5000)
    ├── REST API (/api/command/disable, /api/command/enable)
    ├── WebSocket (telemetry_update, leader_election, status_update)
    └── MQTT Subscriber (fleet/+/telemetry, fleet/+/leader_election)
           ↕
Mosquitto Broker (localhost:1883)
           ↑
Mission Simulator
    ├── Publishes telemetry (1 Hz per drone)
    ├── Subscribes to commands (fleet/+/command)
    └── Publishes leader elections (fleet/system/leader_election)
```

## Data Flow

### Telemetry Updates
1. Simulator publishes to `fleet/{drone_id}/telemetry` (1 Hz)
2. Mission Control backend receives via MQTT subscription
3. Backend updates `drone_states` and `mission_traces` dictionaries
4. Backend broadcasts via WebSocket: `socketio.emit('telemetry_update', {...})`
5. Frontend JavaScript receives event, updates map marker position
6. Frontend adds position to trace polyline (keeps last 100 points)

### Command Execution
1. User clicks "Disable" button in dashboard
2. Frontend sends POST to `/api/command/disable` with `{drone_id: 'ESCORT-01'}`
3. Backend publishes MQTT to `fleet/ESCORT-01/command` with `{command: 'DISABLE'}`
4. Simulator receives command via MQTT subscription
5. Simulator disables drone (status='DISABLED', mode='LAND')
6. If drone was LEADER, simulator elects new leader (highest battery)
7. Simulator publishes status update to `fleet/ESCORT-01/status`
8. Simulator publishes leader election to `fleet/system/leader_election`
9. Backend receives both MQTT messages, broadcasts via WebSocket
10. Frontend updates drone list and leader status display

### Leader Election Logic (Simulator)
```python
def _elect_new_leader(mission_type):
    # Get all active non-leader drones in this mission
    candidates = [d for d in drones 
                 if d.status == 'ACTIVE' 
                 and d.mission_role != 'LEADER'
                 and d.mission_type == mission_type]
    
    # Elect highest battery
    new_leader = max(candidates, key=lambda d: d.battery_pct)
    new_leader.mission_role = 'LEADER'
    
    # Publish election event
    publish({
        'old_leader': old_leader_id,
        'new_leader': new_leader.drone_id,
        'reason': 'LEADER_DISABLED',
        'battery_pct': new_leader.battery_pct
    })
```

## Monitoring Points

### Mission Control Dashboard
- **URL**: http://localhost:5000
- **Purpose**: Interactive command and control
- **View**: Real-time map with traces, drone list, command interface
- **Update Rate**: WebSocket events (instant), REST polling (3-5s)

### Grafana Dashboard
- **URL**: http://localhost:3000
- **Purpose**: Analytics and visualization
- **View**: Time-series graphs, gauges, tables, mission breakdown
- **Update Rate**: 1 second auto-refresh
- **Panels**: Battery trends, mission pie chart, fleet table, fault counter

## Troubleshooting

### "No drones on map"

Check:
1. Is mission simulator running? `ps aux | grep mission_simulator` or check terminal
2. Is MQTT broker healthy? `docker compose ps` (mosquitto should be "Up")
3. Check browser console (F12) for WebSocket connection errors
4. Verify mission control logs show "MQTT Connected: 0"

### "Disable button does nothing"

Check:
1. Open browser console (F12) and look for POST errors
2. Verify mission control logs show "Command received: DISABLE..."
3. Check simulator logs for command processing
4. Verify MQTT subscription in simulator: should show "fleet/+/command"

### "Leader election not happening"

Check:
1. Did you disable the current LEADER? (Look for red badge in control panel)
2. Are there other ACTIVE drones available? (All must not be disabled)
3. Check simulator console for election messages: "Leader election: ..."
4. Verify leader_election topic subscription in mission control
5. Check browser console for `leader_election` WebSocket event

### "Traces not appearing"

- Traces need time to build (at least 10-20 seconds)
- Try clicking "Disable" then "Enable" a drone to force trace update
- Check `/api/traces` REST endpoint: http://localhost:5000/api/traces
- Verify trace storage in mission_control.py `mission_traces` dictionary

## Performance Notes

- Dashboard supports multiple missions simultaneously
- Trace storage: Last 100 positions per drone (~10-20 KB per drone)
- WebSocket updates: ~5 messages/second with 5 drones
- Map rendering: Smooth up to ~20 active drones with traces
- MQTT load: 5 messages/second (telemetry) + events

## Next Steps

After completing demos:

1. **Review Grafana**: http://localhost:3000
   - Compare mission analytics with real-time dashboard
   - Check battery drain trends
   - View mission completion statistics

2. **Review Logs**:
   - Simulator console: Mission events, faults, elections
   - Mission control console: MQTT messages, WebSocket connections
   - Docker logs: `docker compose logs mosquitto-broker`

3. **Experiment**:
   - Disable multiple drones in sequence
   - Re-enable drones and observe formation adjustment
   - Run multiple missions back-to-back (`--mission all`)
   - Inject faults by reducing battery manually in code

4. **Extend**:
   - Add new mission types (SEARCH_RESCUE, SURVEILLANCE)
   - Implement custom leader election strategies (proximity, altitude)
   - Add waypoint editing in dashboard
   - Create mission replay from stored traces

## References

- Architecture: [MVP_TECH_STACK_START_HERE.md](../MVP_TECH_STACK_START_HERE.md)
- MQTT Schema: [MQTT_SCHEMA.md](./MQTT_SCHEMA.md)
- Grafana Setup: [../ops/GRAFANA_SETUP.md](../ops/GRAFANA_SETUP.md)
- Mission Simulator: [../poc/mission_simulator.py](../poc/mission_simulator.py)
- Mission Control: [../poc/mission_control.py](../poc/mission_control.py)

---

**Prepared**: 2026-01-31  
**Version**: 1.0  
**Status**: Production Demo Ready ✅
