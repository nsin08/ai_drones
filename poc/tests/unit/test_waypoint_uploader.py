from types import SimpleNamespace
from unittest.mock import MagicMock

from poc.v4_mission_control.repos.event_repo import InMemoryEventRepository
from poc.v4_mission_control.services.waypoint_uploader import WaypointUploader


def test_publish_mission_emits_one_publish_per_assigned_drone():
    mqtt_client = MagicMock()
    mqtt_client.is_connected = True
    events = InMemoryEventRepository()
    uploader = WaypointUploader(event_repo=events, mqtt_client=mqtt_client)

    mission = SimpleNamespace(
        mission_id="mission-1",
        type="PATROL",
        config={"return_to_home": True},
        tasks=[
            SimpleNamespace(
                task_id="task-1",
                drone_ids=["HW-001", "HW-002"],
                waypoints=[{"lat": 1.0, "lon": 2.0, "alt_m": 30}],
            )
        ],
    )

    published = uploader.publish_mission(mission, requested_by="admin")

    assert len(published) == 2
    assert mqtt_client.publish.call_count == 2
    recent = events.list_recent(limit=5)
    assert any(event.event_type == "MISSION_UPLOAD_REQUESTED" for event in recent)


def test_publish_mission_records_skip_when_no_assigned_waypoints():
    mqtt_client = MagicMock()
    mqtt_client.is_connected = False
    events = InMemoryEventRepository()
    uploader = WaypointUploader(event_repo=events, mqtt_client=mqtt_client)

    mission = SimpleNamespace(
        mission_id="mission-2",
        type="PATROL",
        config={},
        tasks=[SimpleNamespace(task_id="task-2", drone_ids=[], waypoints=[])],
    )

    published = uploader.publish_mission(mission)

    assert published == []
    recent = events.list_recent(limit=1)
    assert recent[0].event_type == "MISSION_UPLOAD_SKIPPED"
