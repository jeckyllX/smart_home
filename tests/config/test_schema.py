"""
Unit tests for SmartHomeConfig schema parsing and validation.
"""

from smarthome.config.schema import SmartHomeConfig
from smarthome.physics.psychrometrics import GlazingType


def test_config_accepts_legacy_aliases():
    legacy_payload = {
        "device": {
            "ip": "192.0.2.10",
            "dev_id": "dev_1",
            "local_key": "1234567890123456",
            "version": 3.5,
        },
        "location": {
            "latitude": 0.0,
            "longitude": 0.0,
            "city": "Unknown",
        },
        "condensation_prevention": {
            "enabled": True,
            "glazing": "double",
            "estimated_indoor_temp_c": 21.0,
            "min_target_rh": 40,
            "max_target_rh": 60,
        },
        "night_schedule": {
            "enabled": True,
            "start_time": "22:30",
            "end_time": "06:30",
            "night_mode": "sleep",
            "day_mode": "manual",
        },
    }
    cfg = SmartHomeConfig.from_dict(legacy_payload)
    assert len(cfg.tuya_devices) == 1
    assert cfg.tuya_devices[0]["ip"] == "192.0.2.10"
    assert cfg.condensation.glazing == GlazingType.DOUBLE
    assert cfg.condensation.default_indoor_temp_c == 21.0
    assert cfg.quiet_schedule.night_mode == "sleep"


def test_config_accepts_canonical_keys():
    payload = {
        "location": {"latitude": 0.0, "longitude": 0.0, "city": "Unknown"},
        "condensation": {
            "enabled": True,
            "glazing": "triple",
            "default_indoor_temp_c": 19.5,
        },
        "quiet_schedule": {
            "enabled": True,
            "start_time": "22:00",
            "end_time": "06:00",
            "night_mode": "sleep",
            "day_mode": "manual",
        },
    }
    cfg = SmartHomeConfig.from_dict(payload)
    assert cfg.condensation.glazing == GlazingType.TRIPLE
    assert cfg.condensation.default_indoor_temp_c == 19.5
    assert cfg.quiet_schedule.start_time == "22:00"


def test_smarthome_config_from_dict_multi_device_format():
    multi_device_payload = {
        "location": {
            "latitude": 0.0,
            "longitude": 0.0,
            "city": "Unknown",
        },
        "devices": [
            {
                "type": "tuya",
                "ip": "192.0.2.10",
                "dev_id": "dev_1",
                "local_key": "1234567890123456",
                "room": "living_room",
                "name": "Arete 2 Dehumidifier",
            },
            {
                "type": "tuya",
                "ip": "192.0.2.11",
                "dev_id": "dev_2",
                "local_key": "1234567890123456",
                "room": "bedroom",
                "name": "Bedroom Dehumidifier",
            },
        ],
        "condensation": {
            "enabled": True,
            "glazing": "triple",
        },
    }
    cfg = SmartHomeConfig.from_dict(multi_device_payload)
    assert len(cfg.tuya_devices) == 2
    assert cfg.tuya_devices[0]["room"] == "living_room"
    assert cfg.tuya_devices[1]["room"] == "bedroom"
    assert cfg.condensation.glazing == GlazingType.TRIPLE


def test_condensation_new_keys_parsed():
    payload = {
        "location": {"latitude": 0.0, "longitude": 0.0, "city": "Unknown"},
        "condensation": {
            "enabled": True,
            "target_dew_point_c": 12.5,
            "rh_deadband": 3,
        },
    }
    cfg = SmartHomeConfig.from_dict(payload)
    assert cfg.condensation.target_dew_point_c == 12.5
    assert cfg.condensation.rh_deadband == 3


def test_condensation_new_keys_default():
    payload = {"location": {"latitude": 0.0, "longitude": 0.0, "city": "Unknown"}}
    cfg = SmartHomeConfig.from_dict(payload)
    assert cfg.condensation.target_dew_point_c is None
    assert cfg.condensation.rh_deadband == 5


def test_smarthome_config_ble_devices_in_devices_list():
    payload = {
        "location": {"latitude": 0.0, "longitude": 0.0, "city": "Unknown"},
        "devices": [
            {
                "type": "tuya",
                "ip": "192.0.2.10",
                "dev_id": "dev_1",
                "local_key": "1234567890123456",
                "room": "living_room",
                "name": "Dehumidifier",
            },
            {
                "type": "thermopro_ble",
                "id": "tp_lr",
                "mac": "A4:C1:38:12:34:56",
                "room": "living_room",
                "name": "Living Room Thermometer",
                "model": "TP350",
            },
            {
                "type": "ble",
                "id": "tp_br",
                "mac": "A4:C1:38:65:43:21",
                "room": "bedroom",
                "model": "TP357",
            },
        ],
    }
    cfg = SmartHomeConfig.from_dict(payload)
    assert len(cfg.tuya_devices) == 1
    assert len(cfg.ble_devices) == 2
    assert cfg.ble_devices[0]["mac"] == "A4:C1:38:12:34:56"
    assert cfg.ble_devices[0]["model"] == "TP350"
    assert cfg.ble_devices[1]["room"] == "bedroom"


def test_smarthome_config_top_level_ble_devices():
    payload = {
        "location": {"latitude": 0.0, "longitude": 0.0, "city": "Unknown"},
        "device": {
            "ip": "192.0.2.10",
            "dev_id": "dev_1",
            "local_key": "1234567890123456",
        },
        "ble_devices": [
            {
                "id": "tp_sensor",
                "mac": "A4:C1:38:99:99:99",
                "room": "kitchen",
            }
        ],
    }
    cfg = SmartHomeConfig.from_dict(payload)
    assert len(cfg.tuya_devices) == 1
    assert len(cfg.ble_devices) == 1
    assert cfg.ble_devices[0]["id"] == "tp_sensor"
    assert cfg.ble_devices[0]["room"] == "kitchen"
