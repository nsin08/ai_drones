"""
Mission Control V3 - Flask Backend

V3 API contract implementation with:
- Mission state machine (IDLE -> PLANNING -> PLANNED -> ACTIVE -> PAUSED -> COMPLETED/ABORTED)
- Bulk command endpoints
- Command timeout tracking with late ACK support
- State snapshot for Socket.IO reconnect recovery
- Leader reassignment endpoint
- Unified /api/command/<verb> endpoint
"""

from flask import Flask, request, jsonify, send_from_directory
from flask_socketio import SocketIO, emit
import paho.mqtt.client as mqtt
import json
import threading
import requests
from datetime import datetime
import uuid
import time
import os
import socket as sock

# ---------------------------------------------------------------------------
# App + SocketIO
# ---------------------------------------------------------------------------
app = Flask(__name__, static_folder='../ui/dist', static_url_path='')
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'v3-mission-control')
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
INVENTORY_URL = os.getenv("INVENTORY_URL", "http://localhost:8001")
ACK_TIMEOUT_SEC = int(os.getenv("ACK_TIMEOUT_SEC", "10"))
START_ACK_TIMEOUT_SEC = int(os.getenv("START_ACK_TIMEOUT_SEC", "5"))
STALE_SEC = int(os.getenv("STALE_SEC", "30"))
DISABLE_MQTT = os.getenv("DISABLE_MQTT", "0") == "1"
HOME_BASE_LAT = float(os.getenv("HOME_BASE_LAT", "28.6139"))
HOME_BASE_LON = float(os.getenv("HOME_BASE_LON", "77.2090"))
HOME_BASE_ALT = float(os.getenv("HOME_BASE_ALT", "0"))

VALID_COMMANDS = {"hold", "return", "disable", "enable", "arm", "disarm", "set_role", "land", "clear_mission", "resume"}
VALID_MISSIONS = {"PATROL", "ESCORT", "PERIMETER"}

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------
# Mission state machine: IDLE -> PLANNING -> PLANNED -> ACTIVE -> PAUSED -> COMPLETED/ABORTED
mission_state = "IDLE"
mission_id = None
mission_type = None
mission_config = {}
mission_plan = {}            # {waypoints, geofence, asset_route, formation, ...}
mission_assignments = {}     # {drone_id: role}

# Drone telemetry
drone_states = {}            # {drone_id: last_telemetry_payload}
drone_last_seen = {}         # {drone_id: epoch_timestamp}

# Command tracking
commands = {}                # {cmd_id: {cmd_id, cmd_group_id, command, drone_id, status, ...}}
_cmd_lock = threading.Lock()

# Leader history
leader_history = []

# Event log (ring buffer)
events = []
MAX_EVENTS = 200

# Home base
home_base = {"lat": HOME_BASE_LAT, "lon": HOME_BASE_LON, "alt_m": HOME_BASE_ALT}


def _emit_event(etype, message, **extra):
    """Append event and broadcast."""
    now_epoch = time.time()
    ev = {"type": etype, "message": message, "timestamp": now_epoch, "ts": now_epoch, **extra}
    events.append(ev)
    if len(events) > MAX_EVENTS:
        events.pop(0)
    socketio.emit('event', ev)


def _set_mission_state(new_state, reason=""):
    """Transition mission FSM and broadcast."""
    global mission_state
    old = mission_state
    mission_state = new_state
    _emit_event("INFO", f"Mission state: {old} -> {new_state}. {reason}".strip())
    socketio.emit('mission_changed', {
        "mission_id": mission_id,
        "mission_type": mission_type,
        "mission_state": new_state,
        "mission_config": mission_config,
        "drone_count": len(mission_assignments),
        "timestamp": datetime.now().isoformat(),
    })

# ---------------------------------------------------------------------------
# Inventory helpers
# ---------------------------------------------------------------------------
def _source_for(drone_id: str) -> str:
    if drone_id.startswith("SIM-"):
        return "SWARMSIM"
    if drone_id.startswith("SITL-") or "ops-drone" in drone_id:
        return "SITL"
    if drone_id.startswith("HW-"):
        return "EDGE_AGENT"
    return "UNKNOWN"


def _extract_position(state: dict):
    position = state.get("position") or {}
    lat = state.get("latitude", state.get("lat", position.get("lat")))
    lon = state.get("longitude", state.get("lon", position.get("lon")))
    alt = state.get("altitude_m", state.get("altitude", position.get("alt_m")))
    return lat, lon, alt


def _normalize_source(value, drone_id: str) -> str:
    if isinstance(value, str) and value:
        return value
    return _source_for(drone_id)


def _normalize_item(drone_id: str, state: dict, last_seen=None, stale=None, source=None):
    state = state or {}
    lat, lon, alt = _extract_position(state)
    battery_pct = state.get("battery_pct")
    if battery_pct is None:
        battery_pct = state.get("battery")
    if battery_pct is None:
        battery_pct = 0

    mission_role = state.get("mission_role") or state.get("current_role") or mission_assignments.get(drone_id, "")
    velocity_mps = state.get("velocity_mps")
    if velocity_mps is None:
        velocity_mps = state.get("velocity", state.get("speed_mps", 0))

    last_seen = last_seen if last_seen is not None else state.get("last_seen", 0)
    if stale is None:
        stale = False
        if last_seen:
            stale = (time.time() - last_seen) > STALE_SEC

    status = state.get("status", "ACTIVE")
    if stale:
        status = "STALE"

    item = {
        "drone_id": drone_id,
        "status": status,
        "battery_pct": battery_pct,
        "position": {"lat": lat, "lon": lon, "alt_m": alt},
        "mode": state.get("mode", "IDLE"),
        "armed": state.get("armed", False),
        "current_role": state.get("current_role", mission_role),
        "mission_role": mission_role,
        "velocity_mps": velocity_mps,
        "gps_fix": state.get("gps_fix", 0),
        "satellites_visible": state.get("satellites_visible"),
        "last_seen": last_seen,
        "stale": stale,
        "source": _normalize_source(source if source is not None else state.get("source"), drone_id),
        # Backward-compatible fields for UI
        "latitude": lat,
        "longitude": lon,
        "altitude_m": alt,
    }
    return item

# ---------------------------------------------------------------------------
# Command helpers
# ---------------------------------------------------------------------------
def _send_command(verb, drone_id, extras=None):
    """Create, track, and publish a single command. Returns cmd dict."""
    cmd_id = str(uuid.uuid4())
    now_iso = datetime.now().isoformat()
    now_epoch = time.time()

    cmd = {
        "cmd_id": cmd_id,
        "command": verb.upper(),
        "drone_id": drone_id,
        "status": "REQUESTED",
        "request_timestamp": now_iso,
        "sent_epoch": now_epoch,
        "timestamp": now_epoch,
        **(extras or {}),
    }

    with _cmd_lock:
        commands[cmd_id] = cmd

    # Publish to MQTT
    mqtt_payload = {
        "cmd_id": cmd_id,
        "command": verb.upper(),
        "drone_id": drone_id,
        "timestamp": time.time(),
        **(extras or {}),
    }
    mqtt_client.publish(f"fleet/{drone_id}/command", json.dumps(mqtt_payload))

    # Broadcast to UI
    socketio.emit('command_requested', cmd)

    return cmd


def _resolve_ack(payload):
    """Process a command_ack from MQTT."""
    cmd_id = payload.get("cmd_id")
    if not cmd_id:
        return
    with _cmd_lock:
        cmd = commands.get(cmd_id)
        if not cmd:
            return
        result = payload.get("result", "SUCCESS")
        now_epoch = time.time()
        sent = cmd.get("sent_epoch", now_epoch)
        late = (now_epoch - sent) > ACK_TIMEOUT_SEC

        if cmd.get("status") == "TIMED_OUT":
            if result in ("SUCCESS", "OK"):
                cmd["status"] = "COMPLETED_LATE"
            else:
                cmd["status"] = "FAILED_LATE"
        else:
            if result in ("SUCCESS", "OK"):
                cmd["status"] = "ACKED"
            else:
                cmd["status"] = "FAILED"

        cmd["late"] = late
        cmd["ack_timestamp"] = payload.get("timestamp", now_epoch)
        cmd["result"] = result
        cmd["timestamp"] = payload.get("timestamp", now_epoch)

    socketio.emit('command_ack', cmd)

    if late:
        _emit_event("WARN", f"Late ACK for {cmd['command']} -> {cmd['drone_id']} (cmd_id={cmd_id[:8]})")


def _check_timeouts():
    """Background thread: mark REQUESTED commands as TIMED_OUT after ACK_TIMEOUT_SEC."""
    while True:
        time.sleep(2)
        now = time.time()
        timed_out = []
        with _cmd_lock:
            for cid, c in commands.items():
                if c["status"] == "REQUESTED" and (now - c.get("sent_epoch", now)) > ACK_TIMEOUT_SEC:
                    c["status"] = "TIMED_OUT"
                    c["result"] = "TIMEOUT"
                    c["timestamp"] = now
                    c["late"] = False
                    timed_out.append(dict(c))
        for c in timed_out:
            socketio.emit('command_ack', c)
            _emit_event("WARN", f"Command {c['command']} -> {c['drone_id']} timed out")


timeout_thread = threading.Thread(target=_check_timeouts, daemon=True)
timeout_thread.start()

# ---------------------------------------------------------------------------
# MQTT
# ---------------------------------------------------------------------------
mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
mqtt_client.reconnect_delay_set(min_delay=1, max_delay=30)


def on_mqtt_connect(client, userdata, flags, reason_code, properties=None):
    print(f"MQTT connected (rc={reason_code})")
    client.subscribe("fleet/+/telemetry")
    client.subscribe("fleet/+/leader_election")
    client.subscribe("fleet/+/status")
    client.subscribe("fleet/system/command_ack")
    client.subscribe("fleet/system/event")


def on_mqtt_message(client, userdata, msg):
    try:
        topic = msg.topic
        payload = json.loads(msg.payload.decode())

        if "telemetry" in topic:
            _handle_telemetry(payload)
        elif "leader_election" in topic:
            _handle_leader_election(payload)
        elif "command_ack" in topic:
            _resolve_ack(payload)
        elif "system/event" in topic:
            etype = payload.get("type", "INFO")
            msg = payload.get("message", "Event")
            extra = dict(payload)
            extra.pop("type", None)
            extra.pop("message", None)
            _emit_event(etype, msg, **extra)
        elif "status" in topic:
            socketio.emit('status_update', payload)
    except Exception as e:
        print(f"MQTT error: {e}")


def _handle_telemetry(payload):
    drone_id = payload.get("drone_id")
    if not drone_id:
        return

    drone_states[drone_id] = payload
    drone_last_seen[drone_id] = time.time()

    socketio.emit('telemetry_update', payload)


def _handle_leader_election(payload):
    leader_history.append({
        "timestamp": datetime.now().isoformat(),
        "event": payload,
    })
    socketio.emit('leader_election', payload)
    _emit_event("INFO", f"Leader election: {payload.get('leader_id', '?')}")


mqtt_client.on_connect = on_mqtt_connect
mqtt_client.on_message = on_mqtt_message


def start_mqtt():
    if DISABLE_MQTT:
        return
    backoff = 1
    while True:
        try:
            mqtt_client.connect(MQTT_HOST, MQTT_PORT, 60)
            mqtt_client.loop_forever(retry_first_connection=True)
        except (ConnectionRefusedError, OSError, sock.error) as e:
            print(f"MQTT connect error: {e}")
        except Exception as e:
            print(f"MQTT unexpected: {e}")
        time.sleep(backoff)
        backoff = min(backoff * 2, 30)


if not DISABLE_MQTT:
    mqtt_thread = threading.Thread(target=start_mqtt, daemon=True)
    mqtt_thread.start()

# ---------------------------------------------------------------------------
# Serve SPA (production build)
# ---------------------------------------------------------------------------
@app.route('/')
def serve_spa():
    return send_from_directory(app.static_folder, 'index.html')


@app.errorhandler(404)
def fallback(e):
    """SPA client-side routing fallback."""
    return send_from_directory(app.static_folder, 'index.html')

# ---------------------------------------------------------------------------
# REST: Inventory (proxy)
# ---------------------------------------------------------------------------
@app.route('/api/inventory', methods=['GET'])
def get_inventory():
    """Return merged inventory + live telemetry."""
    now = time.time()
    page = int(request.args.get("page", 1))
    page_size = int(request.args.get("page_size", 50))
    page_size = max(1, min(page_size, 200))

    # Build from live drone_states
    roster = []
    for did, state in drone_states.items():
        last_seen = drone_last_seen.get(did, 0)
        stale = (now - last_seen) > STALE_SEC
        roster.append(_normalize_item(did, state, last_seen=last_seen, stale=stale, source=_source_for(did)))
    # Optionally merge upstream inventory
    try:
        resp = requests.get(f"{INVENTORY_URL}/inventory", timeout=2)
        if resp.ok:
            upstream = resp.json()
            upstream_list = upstream if isinstance(upstream, list) else upstream.get("items", upstream.get("drones", []))
            live_ids = {d["drone_id"] for d in roster}
            for item in upstream_list:
                did = item.get("drone_id")
                if not did or did in live_ids:
                    continue
                last_seen = item.get("last_seen")
                stale = True
                if last_seen:
                    stale = (now - last_seen) > STALE_SEC
                roster.append(_normalize_item(did, item, last_seen=last_seen, stale=stale, source=item.get("source")))
    except Exception:
        pass  # Upstream unavailable; serve live only

    # Pagination (optional)
    total = len(roster)
    start = (page - 1) * page_size
    end = start + page_size
    paged = roster[start:end]

    return jsonify({
        "items": paged,
        "drones": paged,  # backward-compat for UI
        "page": page,
        "page_size": page_size,
        "total": total,
    })


@app.route('/api/inventory/<drone_id>', methods=['GET'])
def get_drone(drone_id):
    now = time.time()
    state = drone_states.get(drone_id)
    if state:
        last_seen = drone_last_seen.get(drone_id, 0)
        stale = (now - last_seen) > STALE_SEC
        return jsonify(_normalize_item(drone_id, state, last_seen=last_seen, stale=stale, source=_source_for(drone_id)))

    # Fallback to inventory service
    try:
        resp = requests.get(f"{INVENTORY_URL}/inventory/{drone_id}", timeout=2)
        if resp.ok:
            item = resp.json()
            last_seen = item.get("last_seen")
            stale = True
            if last_seen:
                stale = (now - last_seen) > STALE_SEC
            return jsonify(_normalize_item(drone_id, item, last_seen=last_seen, stale=stale, source=item.get("source")))
    except Exception:
        pass

    return jsonify({"error": "Drone not found"}), 404

# ---------------------------------------------------------------------------
# REST: Missions
# ---------------------------------------------------------------------------
@app.route('/api/missions', methods=['GET'])
def get_missions():
    return jsonify({
        "available_missions": list(VALID_MISSIONS),
        "mission_state": mission_state,
        "mission_id": mission_id,
        "mission_type": mission_type,
        "drone_count": len(mission_assignments),
        "mission_config": mission_config,
        "assignments": mission_assignments,
    })


@app.route('/api/home_base', methods=['GET', 'POST'])
def home_base_endpoint():
    """Get or set home base. POST publishes to MQTT for SwarmSim."""
    global home_base
    if request.method == 'GET':
        return jsonify(home_base)

    data = request.json or {}
    lat = data.get("lat", home_base.get("lat"))
    lon = data.get("lon", home_base.get("lon"))
    alt_m = data.get("alt_m", home_base.get("alt_m", 0))
    reset = bool(data.get("reset", True))
    home_base = {"lat": float(lat), "lon": float(lon), "alt_m": float(alt_m)}

    payload = {"lat": home_base["lat"], "lon": home_base["lon"], "alt_m": home_base["alt_m"], "reset": reset}
    try:
        mqtt_client.publish("fleet/system/home_base", json.dumps(payload))
    except Exception:
        pass

    _emit_event("INFO", f"Home base set: {home_base['lat']:.5f}, {home_base['lon']:.5f}")
    return jsonify(home_base)


@app.route('/api/mission/assign', methods=['POST'])
def assign_mission():
    """Assign drones + roles to a mission. Transitions IDLE -> PLANNING."""
    global mission_state, mission_type, mission_id

    data = request.json or {}
    mtype = data.get('mission_type')
    drone_ids = data.get('drone_ids', [])
    role_map = data.get('role_map', {})

    if not mtype or mtype not in VALID_MISSIONS:
        return jsonify({"error": f"Invalid mission_type. Must be one of {list(VALID_MISSIONS)}"}), 400
    if not drone_ids:
        return jsonify({"error": "drone_ids required"}), 400

    if mission_state not in ("IDLE", "PLANNING"):
        return jsonify({"error": f"Cannot assign in state {mission_state}"}), 409

    mission_type = mtype
    if not mission_id:
        mission_id = f"M-{uuid.uuid4().hex[:6].upper()}"

    for did in drone_ids:
        role = role_map.get(did, "WINGMAN")
        mission_assignments[did] = role
        # Send SET_ROLE command
        _send_command("SET_ROLE", did, extras={"role": role})

    if mission_state == "IDLE":
        _set_mission_state("PLANNING", f"Mission {mission_id} ({mtype})")

    return jsonify({
        "status": "success",
        "mission_id": mission_id,
        "mission_type": mtype,
        "assigned": len(drone_ids),
    })


@app.route('/api/mission/plan', methods=['POST'])
def plan_mission():
    """Validate and store a mission plan. Transitions PLANNING -> PLANNED."""
    global mission_plan

    data = request.json or {}
    mtype = data.get('mission_type', mission_type)
    plan = data.get('plan') or {}
    # accept either top-level or nested plan payloads
    waypoints = plan.get('waypoints', data.get('waypoints', []))
    geofence = plan.get('geofence', data.get('geofence', []))
    asset_route = plan.get('asset_route', data.get('asset_route', []))
    formation = plan.get('formation', data.get('formation', {"shape": "BOX", "spacing_m": 30}))
    if isinstance(formation, str):
        formation = {"shape": formation, "spacing_m": 30}

    if mission_state not in ("PLANNING", "PLANNED"):
        return jsonify({"error": f"Cannot plan in state {mission_state}"}), 409

    # Basic validation per mission type
    if mtype == "PATROL" and len(waypoints) < 2:
        return jsonify({"error": "PATROL requires at least 2 waypoints"}), 400
    if mtype == "PERIMETER" and len(geofence) < 3:
        return jsonify({"error": "PERIMETER requires at least 3 geofence points"}), 400
    if mtype == "ESCORT" and len(asset_route) < 2:
        return jsonify({"error": "ESCORT requires at least 2 asset route points"}), 400
    # Formation size validation (demo-grade)
    if mtype == "ESCORT":
        shape = formation.get("shape", "BOX")
        max_drones = 8 if shape == "BOX" else None
        if max_drones and len(mission_assignments) > max_drones:
            return jsonify({"error": f"{shape} formation supports max {max_drones} drones"}), 400

    mission_plan = {
        "mission_type": mtype,
        "waypoints": waypoints,
        "geofence": geofence,
        "asset_route": asset_route,
        "formation": formation,
    }
    mission_config.update(data.get('config', {}))

    _set_mission_state("PLANNED", "Plan validated")

    return jsonify({"status": "success", "mission_plan": mission_plan})


@app.route('/api/mission/start', methods=['POST'])
def start_mission():
    """Start the planned mission. PLANNED -> ACTIVE. Publishes UPLOAD_MISSION to each drone."""
    global mission_state

    if mission_state != "PLANNED":
        return jsonify({"error": f"Cannot start in state {mission_state}. Must be PLANNED."}), 409

    # Send UPLOAD_MISSION to each assigned drone
    cmd_ids = []
    # Determine spawn point (first waypoint / geofence / asset_route)
    spawn_point = None
    if mission_plan.get("waypoints"):
        wp0 = mission_plan["waypoints"][0]
        if isinstance(wp0, dict):
            spawn_point = {"lat": wp0.get("lat"), "lon": wp0.get("lon"), "alt_m": wp0.get("alt_m", 0)}
        else:
            spawn_point = {"lat": wp0[0], "lon": wp0[1], "alt_m": 0}
    elif mission_plan.get("geofence"):
        gp0 = mission_plan["geofence"][0]
        if isinstance(gp0, dict):
            spawn_point = {"lat": gp0.get("lat"), "lon": gp0.get("lon"), "alt_m": gp0.get("alt_m", 0)}
        else:
            spawn_point = {"lat": gp0[0], "lon": gp0[1], "alt_m": 0}
    elif mission_plan.get("asset_route"):
        ap0 = mission_plan["asset_route"][0]
        if isinstance(ap0, dict):
            spawn_point = {"lat": ap0.get("lat"), "lon": ap0.get("lon"), "alt_m": ap0.get("alt_m", 0)}
        else:
            spawn_point = {"lat": ap0[0], "lon": ap0[1], "alt_m": 0}

    for did, role in mission_assignments.items():
        cmd = _send_command("UPLOAD_MISSION", did, extras={
            "mission_id": mission_id,
            "mission_type": mission_type,
            "waypoints": mission_plan.get("waypoints", []),
            "geofence": mission_plan.get("geofence", []),
            "asset_route": mission_plan.get("asset_route", []),
            "formation": mission_plan.get("formation", "BOX"),
            "role": role,
            "start_from_first_wp": True,
            "spawn_point": spawn_point,
        })
        cmd_ids.append(cmd["cmd_id"])

    # Wait for ACKs up to START_ACK_TIMEOUT_SEC
    deadline = time.time() + START_ACK_TIMEOUT_SEC
    results = {}
    while time.time() < deadline and len(results) < len(cmd_ids):
        with _cmd_lock:
            for cid in cmd_ids:
                if cid in results:
                    continue
                status = commands.get(cid, {}).get("status")
                if status in ("ACKED", "FAILED", "TIMED_OUT"):
                    results[cid] = status
        time.sleep(0.1)

    started = sum(1 for cid in cmd_ids if results.get(cid) == "ACKED")
    failed = len(cmd_ids) - started
    errors = []
    for cid in cmd_ids:
        status = results.get(cid)
        if status and status != "ACKED":
            errors.append({"cmd_id": cid, "status": status})
        if status is None:
            errors.append({"cmd_id": cid, "status": "TIMEOUT"})

    _set_mission_state("ACTIVE", "Mission started, commands uploaded")

    return jsonify({
        "status": "success",
        "mission_id": mission_id,
        "mission_state": "ACTIVE",
        "started": started,
        "failed": failed,
        "errors": errors,
    })


@app.route('/api/mission/pause', methods=['POST'])
def pause_mission():
    """ACTIVE -> PAUSED."""
    if mission_state != "ACTIVE":
        return jsonify({"error": f"Cannot pause in state {mission_state}"}), 409
    # Send HOLD to all assigned drones
    for did in mission_assignments:
        _send_command("HOLD", did)
    _set_mission_state("PAUSED", "Operator paused")
    return jsonify({"status": "success", "mission_state": "PAUSED"})


@app.route('/api/mission/resume', methods=['POST'])
def resume_mission():
    """PAUSED -> ACTIVE."""
    if mission_state != "PAUSED":
        return jsonify({"error": f"Cannot resume in state {mission_state}"}), 409
    # Re-upload mission to resume
    for did, role in mission_assignments.items():
        _send_command("UPLOAD_MISSION", did, extras={
            "mission_id": mission_id,
            "mission_type": mission_type,
            "waypoints": mission_plan.get("waypoints", []),
            "role": role,
        })
    _set_mission_state("ACTIVE", "Operator resumed")
    return jsonify({"status": "success", "mission_state": "ACTIVE"})


@app.route('/api/mission/abort', methods=['POST'])
def abort_mission():
    """ACTIVE|PAUSED -> ABORTED. Sends RETURN to all drones."""
    if mission_state not in ("ACTIVE", "PAUSED"):
        return jsonify({"error": f"Cannot abort in state {mission_state}"}), 409
    for did in mission_assignments:
        _send_command("RETURN", did)
    _set_mission_state("ABORTED", "Operator abort")
    return jsonify({"status": "success", "mission_state": "ABORTED"})


@app.route('/api/mission/reassign_leader', methods=['POST'])
def reassign_leader():
    """Reassign LEADER role to a new drone. PAUSED -> ACTIVE."""
    data = request.json or {}
    new_leader_id = data.get('new_leader_id')

    if not new_leader_id:
        return jsonify({"error": "new_leader_id required"}), 400
    if new_leader_id not in mission_assignments:
        return jsonify({"error": f"{new_leader_id} not assigned to this mission"}), 400
    if mission_state not in ("PAUSED", "ACTIVE"):
        return jsonify({"error": f"Cannot reassign leader in state {mission_state}"}), 409

    # Demote current leader(s)
    for did, role in mission_assignments.items():
        if role == "LEADER" and did != new_leader_id:
            mission_assignments[did] = "WINGMAN"
            _send_command("SET_ROLE", did, extras={"role": "WINGMAN"})

    # Promote new leader
    mission_assignments[new_leader_id] = "LEADER"
    _send_command("SET_ROLE", new_leader_id, extras={"role": "LEADER"})

    _emit_event("INFO", f"Leader reassigned to {new_leader_id}")

    if mission_state == "PAUSED":
        _set_mission_state("ACTIVE", f"Leader reassigned to {new_leader_id}")

    return jsonify({
        "status": "success",
        "new_leader_id": new_leader_id,
        "mission_state": mission_state,
    })


@app.route('/api/mission/reset', methods=['POST'])
def reset_mission():
    """Reset mission to IDLE. Clear all state."""
    global mission_state, mission_id, mission_type, mission_plan, mission_assignments
    mission_state = "IDLE"
    mission_id = None
    mission_type = None
    mission_plan = {}
    mission_assignments = {}
    drone_states.clear()
    drone_last_seen.clear()
    _emit_event("INFO", "Mission reset to IDLE")
    socketio.emit('mission_changed', {
        "mission_state": "IDLE", "mission_type": None, "mission_id": None,
        "timestamp": datetime.now().isoformat(),
    })
    return jsonify({"status": "success", "mission_state": "IDLE"})

# ---------------------------------------------------------------------------
# REST: Commands (single + bulk)
# ---------------------------------------------------------------------------
@app.route('/api/command/<verb>', methods=['POST'])
def single_command(verb):
    """Send a single command to one drone."""
    verb_lower = verb.lower()
    if verb_lower not in VALID_COMMANDS:
        return jsonify({"error": f"Unknown command: {verb}. Valid: {list(VALID_COMMANDS)}"}), 400

    data = request.json or {}
    drone_id = data.get('drone_id')
    if not drone_id:
        return jsonify({"error": "drone_id required"}), 400

    extras = {}
    if verb_lower == "set_role":
        role = data.get('role')
        if not role:
            return jsonify({"error": "role required for set_role"}), 400
        extras["role"] = role

    cmd = _send_command(verb_lower, drone_id, extras=extras)

    # Formation-break: if LEADER is held/returned/landed, pause mission
    if verb_lower in ("hold", "return", "land"):
        if mission_assignments.get(drone_id) == "LEADER" and mission_state == "ACTIVE":
            _set_mission_state("PAUSED", f"Leader {drone_id} {verb_lower} - formation break")
    if verb_lower == "resume":
        if mission_assignments.get(drone_id) == "LEADER" and mission_state == "PAUSED":
            _set_mission_state("ACTIVE", f"Leader {drone_id} resumed")

    return jsonify({"cmd_id": cmd["cmd_id"], "status": "REQUESTED"})


@app.route('/api/command/bulk/<verb>', methods=['POST'])
def bulk_command(verb):
    """Send a command to multiple drones at once."""
    verb_lower = verb.lower()
    if verb_lower not in VALID_COMMANDS:
        return jsonify({"error": f"Unknown command: {verb}"}), 400

    data = request.json or {}
    drone_ids = data.get('drone_ids', [])
    if not drone_ids:
        return jsonify({"error": "drone_ids required"}), 400

    cmd_group_id = str(uuid.uuid4())
    extras = {"cmd_group_id": cmd_group_id}
    if verb_lower == "set_role":
        extras["role"] = data.get("role", "WINGMAN")

    results = []
    for did in drone_ids:
        cmd = _send_command(verb_lower, did, extras=dict(extras))
        results.append({"drone_id": did, "cmd_id": cmd["cmd_id"]})

    # Formation-break check for bulk hold/return/land
    if verb_lower in ("hold", "return", "land"):
        for did in drone_ids:
            if mission_assignments.get(did) == "LEADER" and mission_state == "ACTIVE":
                _set_mission_state("PAUSED", f"Leader {did} {verb_lower} - formation break (bulk)")
                break
    if verb_lower == "resume" and mission_state == "PAUSED":
        for did in drone_ids:
            if mission_assignments.get(did) == "LEADER":
                _set_mission_state("ACTIVE", f"Leader {did} resumed (bulk)")
                break

    return jsonify({
        "cmd_group_id": cmd_group_id,
        "requested": len(results),
        "failed": 0,
        "errors": [],
    })

# ---------------------------------------------------------------------------
# REST: State snapshot (for reconnect recovery)
# ---------------------------------------------------------------------------
@app.route('/api/state/snapshot', methods=['GET'])
def state_snapshot():
    """Full state snapshot for UI recovery after Socket.IO reconnect."""
    now = time.time()
    roster = []
    for did, state in drone_states.items():
        last_seen = drone_last_seen.get(did, 0)
        stale = (now - last_seen) > STALE_SEC
        roster.append(_normalize_item(did, state, last_seen=last_seen, stale=stale, source=_source_for(did)))

    recent_cmds = []
    with _cmd_lock:
        for c in commands.values():
            cmd = dict(c)
            if "timestamp" not in cmd or cmd["timestamp"] is None:
                cmd["timestamp"] = cmd.get("ack_timestamp", cmd.get("sent_epoch", now))
            recent_cmds.append(cmd)

    return jsonify({
        "mission": {
            "mission_id": mission_id,
            "mission_type": mission_type,
            "mission_state": mission_state,
            "drone_count": len(mission_assignments),
            "mission_config": mission_config,
            "plan": mission_plan,
            "assignments": mission_assignments,
        },
        "home_base": home_base,
        "drones": roster,
        "items": roster,
        "commands": recent_cmds[-50:],
        "events": events[-50:],
        "leader_history": leader_history[-20:],
    })

# ---------------------------------------------------------------------------
# Socket.IO
# ---------------------------------------------------------------------------
@socketio.on('connect')
def handle_connect():
    print("Client connected")
    emit('mission_changed', {
        "mission_id": mission_id,
        "mission_type": mission_type,
        "mission_state": mission_state,
        "timestamp": datetime.now().isoformat(),
    })


@socketio.on('disconnect')
def handle_disconnect():
    print("Client disconnected")

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == '__main__':
    print("=" * 70)
    print("MISSION CONTROL V3")
    print("=" * 70)
    print("  API:  http://localhost:5000/api/")
    print("  SPA:  http://localhost:5000/")
    print(f"  MQTT: {MQTT_HOST}:{MQTT_PORT}")
    print("=" * 70)
    socketio.run(app, host='0.0.0.0', port=5000, debug=True, allow_unsafe_werkzeug=True)
