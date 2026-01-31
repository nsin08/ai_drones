"""
Mission Control Dashboard - Flask Backend

Provides:
- Web UI for mission visualization with Leaflet maps
- Real-time telemetry via WebSocket
- Command interface with request/acknowledge strategy
- Leader election events
- Mission isolation and configuration
"""

from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
import paho.mqtt.client as mqtt
import json
import threading
from datetime import datetime
import uuid

app = Flask(__name__)
app.config['SECRET_KEY'] = 'mission-control-secret'
socketio = SocketIO(app, cors_allowed_origins="*")

# Global state
current_mission = None  # Track active mission (PATROL, ESCORT, PERIMETER_GUARD)
mission_config = {
    # "PATROL": {"drone_count": 5, "team_type": "PATROL"},
    # "ESCORT": {"drone_count": 5, "team_type": "ESCORT"},
    # "PERIMETER_GUARD": {"drone_count": 5, "team_type": "PERIMETER"},
}
drone_states = {}  # Only drones from current mission
mission_traces = {}  # {drone_id: [(lat, lon, alt, battery, timestamp), ...]}
altitude_history = {}  # {drone_id: [(timestamp, altitude_m), ...]}
active_drones = set()
leader_history = []  # Track leader changes
command_status = {}  # {cmd_id: {"drone_id": "...", "command": "...", "status": "REQUESTED|ACK|FAILED", "timestamp": ...}}
pending_commands = {}  # {cmd_id: command_data}  Commands awaiting acknowledgment

# MQTT client
mqtt_client = mqtt.Client()

def on_mqtt_connect(client, userdata, flags, rc):
    """Subscribe to all fleet telemetry on MQTT connect."""
    print(f"✅ MQTT Connected: {rc}")
    client.subscribe("fleet/+/telemetry")
    client.subscribe("fleet/+/leader_election")
    client.subscribe("fleet/+/status")

def on_mqtt_message(client, userdata, msg):
    """Handle incoming MQTT messages and broadcast to WebSocket clients."""
    try:
        topic = msg.topic
        payload = json.loads(msg.payload.decode())
        
        if "telemetry" in topic:
            drone_id = payload.get("drone_id")
            mission_type = payload.get("mission_type")
            
            # Mission isolation: only track drones from current mission
            if current_mission and mission_type != current_mission:
                return
            
            drone_states[drone_id] = payload
            active_drones.add(drone_id)
            
            # Store trace for map visualization
            if drone_id not in mission_traces:
                mission_traces[drone_id] = []
            
            lat = payload.get("latitude", payload.get("lat", 0))
            lon = payload.get("longitude", payload.get("lon", 0))
            alt = payload.get("altitude_m", 0)
            
            mission_traces[drone_id].append({
                "lat": lat,
                "lon": lon,
                "alt": alt,
                "battery": payload.get("battery_pct", 0),
                "timestamp": payload.get("timestamp", datetime.now().timestamp()),
                "role": payload.get("mission_role", "UNKNOWN")
            })
            
            # Keep last 100 points per drone
            if len(mission_traces[drone_id]) > 100:
                mission_traces[drone_id] = mission_traces[drone_id][-100:]
            
            # Track altitude history for chart
            if drone_id not in altitude_history:
                altitude_history[drone_id] = []
            
            altitude_history[drone_id].append({
                "timestamp": payload.get("timestamp", datetime.now().timestamp()),
                "altitude_m": alt
            })
            
            # Keep last 500 altitude points per drone
            if len(altitude_history[drone_id]) > 500:
                altitude_history[drone_id] = altitude_history[drone_id][-500:]
            
            # Broadcast to all connected web clients
            socketio.emit('telemetry_update', payload)
        
        elif "leader_election" in topic:
            leader_history.append({
                "timestamp": datetime.now().isoformat(),
                "event": payload
            })
            socketio.emit('leader_election', payload)
        
        elif "status" in topic:
            socketio.emit('status_update', payload)
        
        elif "command_ack" in topic:
            # Handle command acknowledgment
            cmd_id = payload.get("cmd_id")
            if cmd_id in command_status:
                command_status[cmd_id]["status"] = "ACK"
                command_status[cmd_id]["result"] = payload.get("result", "SUCCESS")
                command_status[cmd_id]["ack_timestamp"] = payload.get("timestamp", datetime.now().isoformat())
                socketio.emit('command_ack', command_status[cmd_id])
    
    except Exception as e:
        print(f"❌ Error processing MQTT message: {e}")

mqtt_client.on_connect = on_mqtt_connect
mqtt_client.on_message = on_mqtt_message

def start_mqtt():
    """Start MQTT client in background thread."""
    mqtt_client.connect("localhost", 1883, 60)
    mqtt_client.loop_forever()

# Start MQTT listener
mqtt_thread = threading.Thread(target=start_mqtt, daemon=True)
mqtt_thread.start()

@app.route('/')
def index():
    """Serve the mission control dashboard."""
    return render_template('mission_control_v2.html')

@app.route('/api/missions', methods=['GET'])
def get_missions():
    """Get available missions and their configuration."""
    return jsonify({
        "available_missions": ["PATROL", "ESCORT", "PERIMETER_GUARD"],
        "current_mission": current_mission,
        "mission_config": mission_config,
        "drone_counts": {
            "PATROL": mission_config.get("PATROL", {}).get("drone_count", 5),
            "ESCORT": mission_config.get("ESCORT", {}).get("drone_count", 5),
            "PERIMETER_GUARD": mission_config.get("PERIMETER_GUARD", {}).get("drone_count", 5),
        }
    })

@app.route('/api/select-mission', methods=['POST'])
def select_mission():
    """Select active mission and clear previous mission data."""
    global current_mission, drone_states, mission_traces, altitude_history
    
    data = request.json
    mission_type = data.get('mission_type')
    drone_count = data.get('drone_count', 5)
    team_type = data.get('team_type', mission_type)  # Formation type
    
    if mission_type not in ["PATROL", "ESCORT", "PERIMETER_GUARD"]:
        return jsonify({"error": "Invalid mission type"}), 400
    
    # Clear previous mission data
    drone_states = {}
    mission_traces = {}
    altitude_history = {}
    active_drones.clear()
    
    # Set new mission
    current_mission = mission_type
    mission_config[mission_type] = {
        "drone_count": drone_count,
        "team_type": team_type
    }
    
    # Broadcast mission change to all clients
    socketio.emit('mission_changed', {
        "mission_type": mission_type,
        "drone_count": drone_count,
        "team_type": team_type,
        "timestamp": datetime.now().isoformat()
    })
    
    return jsonify({
        "status": "success",
        "message": f"Mission switched to {mission_type} with {drone_count} drones",
        "current_mission": current_mission
    })

@app.route('/api/configure-drones', methods=['POST'])
def configure_drones():
    """Configure drone count and team type for a mission."""
    global mission_config
    
    data = request.json
    mission_type = data.get('mission_type')
    drone_count = data.get('drone_count', 5)
    team_type = data.get('team_type')
    
    if mission_type not in ["PATROL", "ESCORT", "PERIMETER_GUARD"]:
        return jsonify({"error": "Invalid mission type"}), 400
    
    if not (1 <= drone_count <= 10):
        return jsonify({"error": "Drone count must be 1-10"}), 400
    
    mission_config[mission_type] = {
        "drone_count": drone_count,
        "team_type": team_type or mission_type
    }
    
    socketio.emit('config_updated', {
        "mission_type": mission_type,
        "drone_count": drone_count,
        "team_type": team_type
    })
    
    return jsonify({
        "status": "success",
        "message": f"Configured {mission_type}: {drone_count} drones, team type {team_type}"
    })

@app.route('/api/altitude-chart')
def get_altitude_chart():
    """Get altitude history for all drones (for Chart.js)."""
    return jsonify(altitude_history)


def get_drones():
    """Get current state of all drones."""
    return jsonify(drone_states)

@app.route('/api/traces')
def get_traces():
    """Get movement traces for all drones."""
    return jsonify(mission_traces)

@app.route('/api/command/disable', methods=['POST'])
def disable_drone():
    """
    Disable a drone (request/acknowledge strategy).
    """
    data = request.json
    drone_id = data.get('drone_id')
    
    if not drone_id:
        return jsonify({"error": "drone_id required"}), 400
    
    cmd_id = str(uuid.uuid4())
    command = {
        "cmd_id": cmd_id,
        "command": "DISABLE",
        "drone_id": drone_id,
        "timestamp": datetime.now().isoformat()
    }
    
    # Track command status
    command_status[cmd_id] = {
        "cmd_id": cmd_id,
        "command": "DISABLE",
        "drone_id": drone_id,
        "status": "REQUESTED",
        "request_timestamp": datetime.now().isoformat()
    }
    
    pending_commands[cmd_id] = command
    mqtt_client.publish(f"fleet/{drone_id}/command", json.dumps(command))
    
    # Broadcast command request to UI
    socketio.emit('command_requested', command_status[cmd_id])
    
    return jsonify({
        "cmd_id": cmd_id,
        "status": "requested",
        "message": f"Disable command sent to {drone_id} (awaiting acknowledgment)"
    })

@app.route('/api/command/enable', methods=['POST'])
def enable_drone():
    """Re-enable a previously disabled drone (request/acknowledge strategy)."""
    data = request.json
    drone_id = data.get('drone_id')
    
    if not drone_id:
        return jsonify({"error": "drone_id required"}), 400
    
    cmd_id = str(uuid.uuid4())
    command = {
        "cmd_id": cmd_id,
        "command": "ENABLE",
        "drone_id": drone_id,
        "timestamp": datetime.now().isoformat()
    }
    
    # Track command status
    command_status[cmd_id] = {
        "cmd_id": cmd_id,
        "command": "ENABLE",
        "drone_id": drone_id,
        "status": "REQUESTED",
        "request_timestamp": datetime.now().isoformat()
    }
    
    pending_commands[cmd_id] = command
    mqtt_client.publish(f"fleet/{drone_id}/command", json.dumps(command))
    
    # Broadcast command request to UI
    socketio.emit('command_requested', command_status[cmd_id])
    
    return jsonify({
        "cmd_id": cmd_id,
        "status": "requested",
        "message": f"Enable command sent to {drone_id} (awaiting acknowledgment)"
    })

@app.route('/api/command/status/<cmd_id>')
def get_command_status(cmd_id):
    """Get status of a specific command."""
    if cmd_id not in command_status:
        return jsonify({"error": "Command not found"}), 404
    
    return jsonify(command_status[cmd_id])

@app.route('/api/leader_history')
def get_leader_history():
    """Get history of leader elections."""
    return jsonify(leader_history)

@socketio.on('connect')
def handle_connect():
    """Client connected to WebSocket."""
    print("✅ Client connected")
    # Send current state immediately
    emit('initial_state', {
        "drones": drone_states,
        "traces": mission_traces
    })

@socketio.on('disconnect')
def handle_disconnect():
    """Client disconnected from WebSocket."""
    print("❌ Client disconnected")

if __name__ == '__main__':
    print("=" * 70)
    print("🎮 MISSION CONTROL DASHBOARD")
    print("=" * 70)
    print("Dashboard: http://localhost:5000")
    print("Connecting to MQTT: localhost:1883")
    print("=" * 70)
    
    socketio.run(app, host='0.0.0.0', port=5000, debug=True, allow_unsafe_werkzeug=True)
