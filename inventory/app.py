import json
import os
import threading
import time
from typing import Any, Dict, Optional

import docker
from fastapi import FastAPI, HTTPException
from pymavlink import mavutil
import paho.mqtt.client as mqtt


APP_TITLE = "Drone Inventory Service"

MQTT_HOST = os.getenv("MQTT_HOST", "mosquitto")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_TOPIC_SNAPSHOT = os.getenv("MQTT_TOPIC_SNAPSHOT", "fleet/system/inventory")
MQTT_TOPIC_ITEM_PREFIX = os.getenv("MQTT_TOPIC_ITEM_PREFIX", "fleet/system/inventory/")

DOCKER_NETWORK = os.getenv("DOCKER_NETWORK", "fleet-network")
DRONE_LABEL = os.getenv("DRONE_LABEL", "com.ai_drones.kind=drone")
DRONE_ENDPOINTS = os.getenv("DRONE_ENDPOINTS", "")

MAVLINK_DIALECT = os.getenv("MAVLINK_DIALECT", "ardupilotmega")
MAVLINK_ENDPOINT_TEMPLATE = os.getenv("MAVLINK_ENDPOINT_TEMPLATE", "tcp:{ip}:5760")
MAVLINK_RECV_TIMEOUT = float(os.getenv("MAVLINK_RECV_TIMEOUT", "1.0"))
MAVLINK_MISSION_TIMEOUT = float(os.getenv("MAVLINK_MISSION_TIMEOUT", "5.0"))

SNAPSHOT_INTERVAL_SEC = float(os.getenv("SNAPSHOT_INTERVAL_SEC", "5.0"))
DISCOVERY_INTERVAL_SEC = float(os.getenv("DISCOVERY_INTERVAL_SEC", "5.0"))


app = FastAPI(title=APP_TITLE)

inventory: Dict[str, Dict[str, Any]] = {}
inventory_lock = threading.Lock()

listener_threads: Dict[str, threading.Thread] = {}
listener_stop_flags: Dict[str, threading.Event] = {}
mavlink_connections: Dict[str, Any] = {}
mavlink_targets: Dict[str, tuple[int, int]] = {}
mavlink_lock = threading.Lock()


def _now_ts() -> float:
    return time.time()


def _default_item(drone_id: str, endpoint: str) -> Dict[str, Any]:
    return {
        "drone_id": drone_id,
        "status": "UNKNOWN",
        "health": "UNKNOWN",
        "battery_pct": None,
        "position": {"lat": None, "lon": None, "alt_m": None},
        "velocity_mps": None,
        "mode": None,
        "armed": None,
        "gps_fix": None,
        "satellites_visible": None,
        "last_seen": None,
        "current_role": "UNKNOWN",
        "assigned_mission": None,
        "mavlink_endpoint": endpoint,
        "source": {},
    }


def _merge_item(drone_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
    with inventory_lock:
        item = inventory.get(drone_id)
        if not item:
            endpoint = updates.get("mavlink_endpoint") or "unknown"
            item = _default_item(drone_id, endpoint)
        item.update(updates)
        item["last_seen"] = _now_ts()
        inventory[drone_id] = item
        return item


def _publish_mqtt(topic: str, payload: Dict[str, Any]) -> None:
    try:
        mqtt_client.publish(topic, json.dumps(payload, separators=(",", ":")))
    except Exception:
        pass


def _publish_item(drone_id: str, item: Dict[str, Any]) -> None:
    _publish_mqtt(f"{MQTT_TOPIC_ITEM_PREFIX}{drone_id}", item)


def _publish_snapshot() -> None:
    with inventory_lock:
        snapshot = list(inventory.values())
    _publish_mqtt(MQTT_TOPIC_SNAPSHOT, {"timestamp": _now_ts(), "items": snapshot})


def _publish_telemetry(drone_id: str, item: Dict[str, Any]) -> None:
    position = item.get("position") or {}
    if position.get("lat") is None or position.get("lon") is None:
        return
    battery_pct = item.get("battery_pct")
    if battery_pct is None:
        battery_pct = 100.0
    payload = {
        "drone_id": drone_id,
        "mission_role": item.get("current_role", "UNKNOWN"),
        "latitude": position.get("lat"),
        "longitude": position.get("lon"),
        "altitude_m": position.get("alt_m"),
        "battery_pct": float(battery_pct),
        "velocity_mps": item.get("velocity_mps"),
        "mode": item.get("mode"),
        "status": item.get("status"),
        "timestamp": _now_ts(),
    }
    _publish_mqtt(f"fleet/{drone_id}/telemetry", payload)


def _command_topic_to_drone_id(topic: str) -> Optional[str]:
    parts = topic.split("/")
    if len(parts) >= 3 and parts[0] == "fleet" and parts[-1] == "command":
        return parts[1]
    return None


def _on_mqtt_command(client, userdata, msg):
    try:
        drone_id = _command_topic_to_drone_id(msg.topic)
        if not drone_id:
            return
        payload = json.loads(msg.payload.decode() or "{}")
        command = payload.get("command")
        cmd_id = payload.get("cmd_id")
        if command == "SET_ROLE":
            role = payload.get("role")
            if role:
                item = _merge_item(drone_id, {"current_role": role})
                _publish_item(drone_id, item)
                if cmd_id:
                    ack = {
                        "cmd_id": cmd_id,
                        "drone_id": drone_id,
                        "command": command,
                        "result": "SUCCESS",
                        "timestamp": _now_ts(),
                    }
                    _publish_mqtt("fleet/system/command_ack", ack)
        elif command == "UPLOAD_MISSION":
            waypoints = payload.get("waypoints", [])
            ok = _upload_mission(drone_id, waypoints)
            if cmd_id:
                ack = {
                    "cmd_id": cmd_id,
                    "drone_id": drone_id,
                    "command": command,
                    "result": "SUCCESS" if ok else "FAILED",
                    "timestamp": _now_ts(),
                }
                _publish_mqtt("fleet/system/command_ack", ack)
        elif command == "CLEAR_MISSION":
            ok = _clear_mission(drone_id)
            if cmd_id:
                ack = {
                    "cmd_id": cmd_id,
                    "drone_id": drone_id,
                    "command": command,
                    "result": "SUCCESS" if ok else "FAILED",
                    "timestamp": _now_ts(),
                }
                _publish_mqtt("fleet/system/command_ack", ack)
        elif command in {"HOLD", "RETURN", "DISABLE", "ENABLE", "ARM", "DISARM"}:
            ok = _send_mavlink_command(drone_id, command)
            if cmd_id:
                ack = {
                    "cmd_id": cmd_id,
                    "drone_id": drone_id,
                    "command": command,
                    "result": "SUCCESS" if ok else "FAILED",
                    "timestamp": _now_ts(),
                }
                _publish_mqtt("fleet/system/command_ack", ack)
    except Exception:
        return


def _start_mqtt():
    mqtt_client.on_message = _on_mqtt_command
    mqtt_client.connect(MQTT_HOST, MQTT_PORT, 60)
    mqtt_client.subscribe("fleet/+/command")
    mqtt_client.loop_start()


def _set_status_from_heartbeat(msg) -> Dict[str, Any]:
    return {
        "status": "ACTIVE",
        "mode": msg.custom_mode,
        "armed": bool(msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED),
    }


def _handle_mavlink_message(drone_id: str, msg) -> None:
    updates: Dict[str, Any] = {}
    mtype = msg.get_type()
    if mtype == "HEARTBEAT":
        with mavlink_lock:
            mavlink_targets[drone_id] = (msg.get_srcSystem(), msg.get_srcComponent())
        updates.update(_set_status_from_heartbeat(msg))
    elif mtype == "SYS_STATUS":
        if msg.battery_remaining is not None and msg.battery_remaining >= 0:
            updates["battery_pct"] = float(msg.battery_remaining)
    elif mtype == "GLOBAL_POSITION_INT":
        updates["position"] = {
            "lat": msg.lat / 1e7,
            "lon": msg.lon / 1e7,
            "alt_m": msg.relative_alt / 1000.0,
        }
        updates["velocity_mps"] = (msg.vx ** 2 + msg.vy ** 2 + msg.vz ** 2) ** 0.5 / 100.0
    elif mtype == "GPS_RAW_INT":
        updates["gps_fix"] = int(msg.fix_type)
        updates["satellites_visible"] = int(msg.satellites_visible)

    if updates:
        item = _merge_item(drone_id, updates)
        _publish_item(drone_id, item)
        _publish_telemetry(drone_id, item)


def _send_mavlink_command(drone_id: str, command: str) -> bool:
    with mavlink_lock:
        conn = mavlink_connections.get(drone_id)
        target = mavlink_targets.get(drone_id)
    if not conn or not target:
        return False
    target_sys, target_comp = target
    try:
        if command in {"ENABLE", "ARM"}:
            conn.mav.command_long_send(
                target_sys, target_comp,
                mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
                0, 1, 0, 0, 0, 0, 0, 0
            )
            _merge_item(drone_id, {"status": "ACTIVE"})
        elif command == "DISARM":
            conn.mav.command_long_send(
                target_sys, target_comp,
                mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
                0, 0, 0, 0, 0, 0, 0, 0
            )
        elif command == "DISABLE":
            conn.mav.command_long_send(
                target_sys, target_comp,
                mavutil.mavlink.MAV_CMD_NAV_LAND,
                0, 0, 0, 0, 0, 0, 0, 0
            )
            _merge_item(drone_id, {"status": "DISABLED"})
        elif command == "RETURN":
            conn.mav.command_long_send(
                target_sys, target_comp,
                mavutil.mavlink.MAV_CMD_NAV_RETURN_TO_LAUNCH,
                0, 0, 0, 0, 0, 0, 0, 0
            )
        elif command == "HOLD":
            conn.mav.command_long_send(
                target_sys, target_comp,
                mavutil.mavlink.MAV_CMD_NAV_LOITER_UNLIM,
                0, 0, 0, 0, 0, 0, 0, 0
            )
        else:
            return False
        return True
    except Exception:
        return False


def _clear_mission(drone_id: str) -> bool:
    with inventory_lock:
        endpoint = inventory.get(drone_id, {}).get("mavlink_endpoint")
    if not endpoint:
        return False

    with mavlink_lock:
        target = mavlink_targets.get(drone_id)
    try:
        conn = mavutil.mavlink_connection(
            endpoint,
            dialect=MAVLINK_DIALECT,
            autoreconnect=False,
            source_system=255,
        )
        if not target:
            hb = conn.recv_match(type=["HEARTBEAT"], blocking=True, timeout=MAVLINK_MISSION_TIMEOUT)
            if not hb:
                return False
            target = (hb.get_srcSystem(), hb.get_srcComponent())
            with mavlink_lock:
                mavlink_targets[drone_id] = target

        target_sys, target_comp = target
        conn.mav.mission_clear_all_send(target_sys, target_comp)
        return True
    except Exception:
        return False
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _build_mission_items(waypoints: list[dict]) -> list[dict]:
    items: list[dict] = []
    for index, wp in enumerate(waypoints):
        lat = float(wp["lat"])
        lon = float(wp["lon"])
        alt = float(wp.get("alt_m", 50.0))
        command = int(wp.get("command", mavutil.mavlink.MAV_CMD_NAV_WAYPOINT))
        items.append({
            "seq": index,
            "frame": int(wp.get("frame", mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT)),
            "command": command,
            "current": 1 if index == 0 else 0,
            "autocontinue": 1,
            "param1": float(wp.get("param1", 0)),
            "param2": float(wp.get("param2", 0)),
            "param3": float(wp.get("param3", 0)),
            "param4": float(wp.get("param4", 0)),
            "lat_int": int(lat * 1e7),
            "lon_int": int(lon * 1e7),
            "alt": alt,
        })
    return items


def _upload_mission(drone_id: str, waypoints: list[dict]) -> bool:
    if not waypoints:
        return False

    with inventory_lock:
        endpoint = inventory.get(drone_id, {}).get("mavlink_endpoint")
    if not endpoint:
        return False

    with mavlink_lock:
        target = mavlink_targets.get(drone_id)

    items = _build_mission_items(waypoints)

    try:
        conn = mavutil.mavlink_connection(
            endpoint,
            dialect=MAVLINK_DIALECT,
            autoreconnect=False,
            source_system=255,
        )
        if not target:
            hb = conn.recv_match(type=["HEARTBEAT"], blocking=True, timeout=MAVLINK_MISSION_TIMEOUT)
            if not hb:
                return False
            target = (hb.get_srcSystem(), hb.get_srcComponent())
            with mavlink_lock:
                mavlink_targets[drone_id] = target

        target_sys, target_comp = target
        conn.mav.mission_clear_all_send(target_sys, target_comp)
        time.sleep(0.2)
        conn.mav.mission_count_send(target_sys, target_comp, len(items))

        for _ in range(len(items)):
            req = conn.recv_match(
                type=["MISSION_REQUEST_INT", "MISSION_REQUEST"],
                blocking=True,
                timeout=MAVLINK_MISSION_TIMEOUT,
            )
            if not req:
                return False
            seq = int(req.seq)
            item = items[seq]
            conn.mav.mission_item_int_send(
                target_sys,
                target_comp,
                item["seq"],
                item["frame"],
                item["command"],
                item["current"],
                item["autocontinue"],
                item["param1"],
                item["param2"],
                item["param3"],
                item["param4"],
                item["lat_int"],
                item["lon_int"],
                item["alt"],
            )

        ack = conn.recv_match(type=["MISSION_ACK"], blocking=True, timeout=MAVLINK_MISSION_TIMEOUT)
        if not ack:
            return False
        return int(ack.type) == int(mavutil.mavlink.MAV_MISSION_ACCEPTED)
    except Exception:
        return False
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _mavlink_listener(drone_id: str, endpoint: str, stop_event: threading.Event) -> None:
    while not stop_event.is_set():
        try:
            conn = mavutil.mavlink_connection(
                endpoint,
                dialect=MAVLINK_DIALECT,
                autoreconnect=True,
                source_system=255,
            )
            with mavlink_lock:
                mavlink_connections[drone_id] = conn
            while not stop_event.is_set():
                msg = conn.recv_match(blocking=True, timeout=MAVLINK_RECV_TIMEOUT)
                if msg:
                    _handle_mavlink_message(drone_id, msg)
        except Exception:
            time.sleep(1.0)
        finally:
            with mavlink_lock:
                mavlink_connections.pop(drone_id, None)


def _resolve_ip(networks: Dict[str, Any]) -> Optional[str]:
    if not networks:
        return None
    if DOCKER_NETWORK in networks and networks[DOCKER_NETWORK].get("IPAddress"):
        return networks[DOCKER_NETWORK].get("IPAddress")
    for name, data in networks.items():
        ip = data.get("IPAddress")
        if ip:
            return ip
    return None


def _parse_static_endpoints() -> Dict[str, str]:
    endpoints: Dict[str, str] = {}
    if not DRONE_ENDPOINTS:
        return endpoints
    for entry in DRONE_ENDPOINTS.split(","):
        entry = entry.strip()
        if not entry or "=" not in entry:
            continue
        drone_id, endpoint = entry.split("=", 1)
        drone_id = drone_id.strip()
        endpoint = endpoint.strip()
        if drone_id and endpoint:
            endpoints[drone_id] = endpoint
    return endpoints


def _discover_drones() -> None:
    docker_client = docker.from_env()
    while True:
        try:
            active_ids = set()
            # Static endpoints for hardware or external SITL
            static_endpoints = _parse_static_endpoints()
            for drone_id, endpoint in static_endpoints.items():
                active_ids.add(drone_id)
                if drone_id not in listener_threads:
                    stop_event = threading.Event()
                    listener_stop_flags[drone_id] = stop_event
                    thread = threading.Thread(
                        target=_mavlink_listener,
                        args=(drone_id, endpoint, stop_event),
                        daemon=True,
                    )
                    listener_threads[drone_id] = thread
                    base_updates = {
                        "drone_id": drone_id,
                        "mavlink_endpoint": endpoint,
                        "source": {"static": True},
                    }
                    _merge_item(drone_id, base_updates)
                    thread.start()

            containers = docker_client.containers.list(filters={"label": DRONE_LABEL})
            for container in containers:
                labels = container.labels or {}
                drone_id = labels.get("com.ai_drones.drone_id") or container.name
                networks = container.attrs.get("NetworkSettings", {}).get("Networks", {})
                ip = _resolve_ip(networks)
                if not ip:
                    continue
                endpoint = MAVLINK_ENDPOINT_TEMPLATE.format(ip=ip)
                active_ids.add(drone_id)

                if drone_id not in listener_threads:
                    stop_event = threading.Event()
                    listener_stop_flags[drone_id] = stop_event
                    thread = threading.Thread(
                        target=_mavlink_listener,
                        args=(drone_id, endpoint, stop_event),
                        daemon=True,
                    )
                    listener_threads[drone_id] = thread
                    base_updates = {
                        "drone_id": drone_id,
                        "mavlink_endpoint": endpoint,
                        "source": {
                            "container_id": container.id[:12],
                            "container_name": container.name,
                            "image": container.image.tags[0] if container.image.tags else None,
                            "labels": labels,
                        },
                    }
                    _merge_item(drone_id, base_updates)
                    thread.start()
                else:
                    _merge_item(drone_id, {"mavlink_endpoint": endpoint})

            for drone_id in list(listener_threads.keys()):
                if drone_id not in active_ids:
                    listener_stop_flags[drone_id].set()
                    listener_threads.pop(drone_id, None)
                    listener_stop_flags.pop(drone_id, None)
                    with inventory_lock:
                        inventory.pop(drone_id, None)
        except Exception as e:
            print(f"[inventory] discovery error: {e}")

        time.sleep(DISCOVERY_INTERVAL_SEC)


def _snapshot_loop() -> None:
    while True:
        _publish_snapshot()
        time.sleep(SNAPSHOT_INTERVAL_SEC)


mqtt_client = mqtt.Client()


@app.on_event("startup")
def startup_event():
    _start_mqtt()
    threading.Thread(target=_discover_drones, daemon=True).start()
    threading.Thread(target=_snapshot_loop, daemon=True).start()


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/inventory")
def get_inventory():
    with inventory_lock:
        return list(inventory.values())


@app.get("/inventory/{drone_id}")
def get_inventory_item(drone_id: str):
    with inventory_lock:
        item = inventory.get(drone_id)
    if not item:
        raise HTTPException(status_code=404, detail="Drone not found")
    return item
