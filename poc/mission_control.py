"""
Mission Control Dashboard - Flask Backend

Provides:
- Web UI for mission visualization with Leaflet maps
- Real-time telemetry via WebSocket
- Command interface to disable/enable drones
- Leader election events
"""

from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
import paho.mqtt.client as mqtt
import json
import threading
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'mission-control-secret'
socketio = SocketIO(app, cors_allowed_origins="*")

# Global state
drone_states = {}
mission_traces = {}  # {drone_id: [(lat, lon, timestamp), ...]}
active_drones = set()
leader_history = []  # Track leader changes

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
            drone_states[drone_id] = payload
            active_drones.add(drone_id)
            
            # Store trace for map visualization
            if drone_id not in mission_traces:
                mission_traces[drone_id] = []
            
            mission_traces[drone_id].append({
                "lat": payload.get("latitude", payload.get("lat", 0)),  # Support both field names
                "lon": payload.get("longitude", payload.get("lon", 0)),  # Support both field names
                "alt": payload["altitude_m"],
                "battery": payload["battery_pct"],
                "timestamp": payload["timestamp"],
                "role": payload.get("mission_role", "UNKNOWN")
            })
            
            # Keep last 100 points per drone
            if len(mission_traces[drone_id]) > 100:
                mission_traces[drone_id] = mission_traces[drone_id][-100:]
            
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
    return render_template('mission_control.html')

@app.route('/api/drones')
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
    Disable a drone (simulates failure).
    Publishes command to MQTT for simulator to handle.
    """
    data = request.json
    drone_id = data.get('drone_id')
    
    if not drone_id:
        return jsonify({"error": "drone_id required"}), 400
    
    command = {
        "command": "DISABLE",
        "drone_id": drone_id,
        "timestamp": datetime.now().isoformat()
    }
    
    mqtt_client.publish(f"fleet/{drone_id}/command", json.dumps(command))
    
    return jsonify({
        "status": "success",
        "message": f"Disable command sent to {drone_id}"
    })

@app.route('/api/command/enable', methods=['POST'])
def enable_drone():
    """Re-enable a previously disabled drone."""
    data = request.json
    drone_id = data.get('drone_id')
    
    if not drone_id:
        return jsonify({"error": "drone_id required"}), 400
    
    command = {
        "command": "ENABLE",
        "drone_id": drone_id,
        "timestamp": datetime.now().isoformat()
    }
    
    mqtt_client.publish(f"fleet/{drone_id}/command", json.dumps(command))
    
    return jsonify({
        "status": "success",
        "message": f"Enable command sent to {drone_id}"
    })

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
