"""
Unit tests for SQLite TelemetryStore time-series recording, downsampling, and pruning.
"""

from __future__ import annotations

from pathlib import Path

from smarthome.core.events import CommandDispatchedEvent, DeviceStateChangedEvent, EventBus
from smarthome.storage.history import TelemetryStore


def test_telemetry_store_record_and_query(tmp_path: Path):
    db_file = tmp_path / "test_history.db"
    store = TelemetryStore(db_path=db_file, retention_days=7)

    base_ts = 1_700_000_000.0
    for i in range(10):
        store.record_room_snapshot(
            room="bedroom",
            status={
                "indoor_temp_c": 19.0 + (i * 0.1),
                "indoor_rh_percent": 55.0 + i,
                "effective_outdoor_c": 7.0,
                "dew_point_c": 10.0,
                "safe_dew_point_c": 12.0,
                "safe_target_rh": 55,
            },
            is_on=(i % 2 == 0),
            timestamp=base_ts + (i * 60),
        )

    points = store.get_room_history("bedroom", hours=24.0, max_points=100, now_ts=base_ts + 600)
    assert len(points) == 10
    assert points[0]["indoor_temp_c"] == 19.0
    assert points[0]["is_on"] is True
    assert points[1]["is_on"] is False
    assert points[-1]["indoor_rh_percent"] == 64.0

    # Test downsampling when max_points < len(points)
    downsampled = store.get_room_history("bedroom", hours=24.0, max_points=4, now_ts=base_ts + 600)
    assert len(downsampled) == 4
    assert downsampled[-1]["indoor_rh_percent"] == 64.0

    all_rooms = store.get_all_rooms_history(hours=24.0, now_ts=base_ts + 600)
    assert "bedroom" in all_rooms
    assert len(all_rooms["bedroom"]) == 10

    store.close()


def test_telemetry_store_event_bus_and_pruning():
    store = TelemetryStore(db_path=":memory:", retention_days=2)
    bus = EventBus()
    store.attach_event_bus(bus)

    old_ts = 1_000_000.0
    recent_ts = old_ts + (5 * 86400.0)

    store.record_room_snapshot(
        room="bedroom",
        status={"indoor_temp_c": 18.0, "indoor_rh_percent": 60.0},
        is_on=False,
        timestamp=old_ts,
    )
    bus.publish(
        DeviceStateChangedEvent(
            timestamp=old_ts,
            device_id="dh_1",
            trait_name="OnOffTrait",
            property_name="is_on",
            old_value=False,
            new_value=True,
        )
    )
    bus.publish(
        CommandDispatchedEvent(
            timestamp=recent_ts,
            device_id="dh_1",
            command="set_mode",
            arguments={"mode": "sleep"},
            success=True,
        )
    )

    # Set _last_prune so record_room_snapshot doesn't auto-prune before our explicit prune call
    store._last_prune = recent_ts
    store.record_room_snapshot(
        room="bedroom",
        status={"indoor_temp_c": 20.0, "indoor_rh_percent": 50.0},
        is_on=True,
        timestamp=recent_ts,
    )

    deleted = store.prune_old_records(retention_days=2, now_ts=recent_ts)
    assert deleted == 2  # 1 old room snapshot + 1 old device event

    remaining = store.get_room_history("bedroom", hours=240.0, now_ts=recent_ts)
    assert len(remaining) == 1
    assert remaining[0]["indoor_temp_c"] == 20.0

    store.close()
