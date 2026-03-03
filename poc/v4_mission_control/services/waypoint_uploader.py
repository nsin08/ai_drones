"""Mission waypoint publisher for the v4 demo slice."""

from __future__ import annotations

import json
from typing import Any

from ..infra.mqtt_client import MqttReconnectClient
from ..repos.event_repo import InMemoryEventRepository, SQLEventRepository
from ..schemas.mission import MissionResponse


class WaypointUploader:
    """Publish assigned mission waypoints to drone-specific MQTT topics."""

    def __init__(
        self,
        *,
        event_repo: InMemoryEventRepository | SQLEventRepository,
        mqtt_client: MqttReconnectClient | None = None,
    ) -> None:
        self._event_repo = event_repo
        self._mqtt_client = mqtt_client

    def publish_mission(
        self,
        mission: MissionResponse,
        *,
        requested_by: str | None = None,
    ) -> list[dict[str, Any]]:
        """Publish each assigned task with waypoints to every target drone."""

        published: list[dict[str, Any]] = []

        for task in mission.tasks:
            if not task.drone_ids or not task.waypoints:
                continue

            for drone_id in task.drone_ids:
                payload = {
                    "action": "UPLOAD",
                    "mission_id": mission.mission_id,
                    "mission_type": mission.type,
                    "task_id": task.task_id,
                    "drone_id": drone_id,
                    "waypoints": task.waypoints,
                    "config": mission.config or {},
                }
                published.append(payload)
                self._publish(drone_id, payload, requested_by=requested_by)

        if not published:
            self._event_repo.append(
                event_type="MISSION_UPLOAD_SKIPPED",
                aggregate_type="MISSION",
                aggregate_id=mission.mission_id,
                mission_id=mission.mission_id,
                severity="WARNING",
                payload_json={"reason": "no_assigned_waypoints"},
                requested_by=requested_by,
            )

        return published

    def _publish(
        self,
        drone_id: str,
        payload: dict[str, Any],
        *,
        requested_by: str | None,
    ) -> None:
        topic = self._mission_topic(drone_id)
        event_type = "MISSION_UPLOAD_DEFERRED"
        severity = "WARNING"
        publish_mode = "noop"

        if self._mqtt_client and self._mqtt_client.is_connected:
            self._mqtt_client.publish(topic, json.dumps(payload))
            event_type = "MISSION_UPLOAD_REQUESTED"
            severity = None
            publish_mode = "broker"

        self._event_repo.append(
            event_type=event_type,
            aggregate_type="MISSION",
            aggregate_id=payload["mission_id"],
            mission_id=payload["mission_id"],
            drone_id=drone_id,
            severity=severity,
            payload_json={
                "topic": topic,
                "task_id": payload["task_id"],
                "publish_mode": publish_mode,
                "waypoint_count": len(payload["waypoints"]),
            },
            requested_by=requested_by,
        )

    @staticmethod
    def _mission_topic(drone_id: str) -> str:
        return f"fleet/{drone_id}/mission"
