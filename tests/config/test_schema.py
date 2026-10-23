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
            "lookahead_hours": 8,
        },
    }
    cfg = SmartHomeConfig.from_dict(payload)
    assert cfg.condensation.target_dew_point_c == 12.5
    assert cfg.condensation.rh_deadband == 3
    assert cfg.condensation.lookahead_hours == 8


def test_condensation_new_keys_default():
    payload = {"location": {"latitude": 0.0, "longitude": 0.0, "city": "Unknown"}}
    cfg = SmartHomeConfig.from_dict(payload)
    assert cfg.condensation.target_dew_point_c is None
    assert cfg.condensation.rh_deadband == 5
    assert cfg.condensation.lookahead_hours == 12


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


def test_config_web_and_auto_power_and_exclusion_keys():
    payload = {
        "location": {"latitude": 0.0, "longitude": 0.0, "city": "Test City"},
        "devices": [
            {
                "type": "tuya",
                "ip": "192.168.1.10",
                "dev_id": "dev_1",
                "local_key": "1234567890123456",
                "room": "bedroom",
            }
        ],
        "condensation": {
            "enabled": True,
            "auto_power": True,
            "turn_on_offset_rh": 3.0,
            "turn_off_offset_rh": 1.5,
            "min_cycle_seconds": 300,
        },
        "quiet_schedule": {
            "enabled": True,
            "night_days": ["mon", "tue", "wed"],
            "all_day_sleep_days": ["sun"],
            "exclusion_windows": [
                {
                    "label": "Night Silence",
                    "start_time": "01:00",
                    "end_time": "06:00",
                    "days": ["sat", "sun"],
                    "rooms": ["bedroom"],
                    "enabled": True,
                }
            ],
        },
        "web": {
            "enabled": True,
            "host": "127.0.0.1",
            "port": 9000,
        },
    }
    cfg = SmartHomeConfig.from_dict(payload)
    assert cfg.condensation.auto_power is True
    assert cfg.condensation.turn_on_offset_rh == 3.0
    assert cfg.condensation.turn_off_offset_rh == 1.5
    assert cfg.condensation.min_cycle_seconds == 300

    assert cfg.quiet_schedule.night_days == ["mon", "tue", "wed"]
    assert cfg.quiet_schedule.all_day_sleep_days == ["sun"]
    assert len(cfg.quiet_schedule.exclusion_windows) == 1
    assert cfg.quiet_schedule.exclusion_windows[0].label == "Night Silence"
    assert cfg.quiet_schedule.exclusion_windows[0].rooms == ["bedroom"]

    assert cfg.web.enabled is True
    assert cfg.web.host == "127.0.0.1"
    assert cfg.web.port == 9000


def test_config_roundtrip_save_and_load(tmp_path):
    config_file = tmp_path / "config.json"
    payload = {
        "location": {"latitude": 0.0, "longitude": 0.0, "city": "Test City"},
        "devices": [
            {
                "type": "tuya",
                "ip": "192.168.1.10",
                "dev_id": "dev_1",
                "local_key": "1234567890123456",
                "room": "bedroom",
            }
        ],
        "condensation": {
            "enabled": True,
            "auto_power": True,
            "turn_on_offset_rh": 2.5,
        },
        "quiet_schedule": {
            "enabled": True,
            "all_day_sleep_days": ["sat", "sun"],
            "exclusion_windows": [
                {
                    "label": "Deep Sleep",
                    "start_time": "00:00",
                    "end_time": "07:00",
                    "days": ["mon"],
                    "rooms": ["bedroom"],
                    "enabled": True,
                }
            ],
        },
        "web": {"enabled": True, "port": 8888},
    }
    cfg = SmartHomeConfig.from_dict(payload)
    cfg.save(config_file)

    loaded = SmartHomeConfig.from_file(config_file)
    assert loaded.condensation.auto_power is True
    assert loaded.condensation.turn_on_offset_rh == 2.5
    assert loaded.quiet_schedule.all_day_sleep_days == ["sat", "sun"]
    assert loaded.quiet_schedule.exclusion_windows[0].label == "Deep Sleep"
    assert loaded.web.port == 8888
