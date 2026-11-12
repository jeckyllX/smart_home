"""
Tests for Manual Override / Hold timer preventing automations from fighting manual changes.
"""

from __future__ import annotations

from datetime import datetime

from smarthome.app import SmartHomeApplication
from smarthome.automations.condensation import CondensationPreventionAutomation
from smarthome.automations.schedule import QuietScheduleAutomation
from smarthome.config.schema import SmartHomeConfig
from smarthome.drivers.virtual.mock_climate import VirtualClimateSensor, VirtualDehumidifier


def test_manual_override_prevents_schedule_and_condensation_changes():
    cfg = SmartHomeConfig.from_dict(
        {
            "location": {"latitude": 0.0, "longitude": 0.0, "city": "Test City"},
            "condensation": {
                "enabled": True,
                "target_dew_point_c": 10.0,
                "manual_override_minutes": 120,
            },
            "quiet_schedule": {
                "enabled": True,
                "start_time": "23:00",
                "end_time": "07:00",
                "night_mode": "sleep",
                "day_mode": "manual",
            },
        }
    )
    app = SmartHomeApplication(cfg, refresh_on_init=False)

    dehum = VirtualDehumidifier(
        device_id="dh_bed",
        name="Bedroom Dehumidifier",
        room="bedroom",
    )
    sensor = VirtualClimateSensor(
        device_id="sensor_bed",
        name="Bedroom Sensor",
        room="bedroom",
        initial_temp=20.0,
        initial_rh=65.0,
    )
    app.registry.register(dehum)
    app.registry.register(sensor)

    # User manually switches dehumidifier to 'laundry' mode and target 40%
    ok1, _ = app.execute_device_command("dh_bed", "set_mode", mode="laundry")
    ok2, _ = app.execute_device_command("dh_bed", "set_target", humidity=40)
    assert ok1 is True and ok2 is True
    assert dehum.current_mode == "laundry"
    assert dehum.target_humidity_percent == 40

    is_held, rem = app.is_device_overridden("dh_bed")
    assert is_held is True
    assert rem > 3600

    # Evaluate schedule and condensation during night hours while hold is active
    night_dt = datetime.fromtimestamp(app._manual_overrides["dh_bed"] - 1800)
    for auto in app.automations:
        if isinstance(auto, (QuietScheduleAutomation, CondensationPreventionAutomation)):
            logs = auto.evaluate(app.registry, app.event_bus, current_dt=night_dt)
            assert any("MANUAL HOLD" in entry for entry in logs)

    # Mode and target RH must remain untouched by automations
    assert dehum.current_mode == "laundry"
    assert dehum.target_humidity_percent == 40

    # Clear manual override -> next evaluation applies automation rules
    ok_clear, _ = app.execute_device_command("dh_bed", "clear_override")
    assert ok_clear is True
    assert app.is_device_overridden("dh_bed")[0] is False


def test_manual_override_takes_precedence_over_exclusion_window():
    cfg = SmartHomeConfig.from_dict(
        {
            "location": {"latitude": 0.0, "longitude": 0.0, "city": "Test City"},
            "condensation": {
                "enabled": True,
                "target_dew_point_c": 10.0,
                "manual_override_minutes": 120,
            },
            "quiet_schedule": {
                "enabled": True,
                "exclusion_windows": [
                    {
                        "label": "Night Silence",
                        "start_time": "00:00",
                        "end_time": "23:59",
                        "days": ["mon", "tue", "wed", "thu", "fri", "sat", "sun"],
                        "rooms": ["bedroom"],
                        "enabled": True,
                    }
                ],
            },
        }
    )
    app = SmartHomeApplication(cfg, refresh_on_init=False)

    dehum = VirtualDehumidifier(
        device_id="dh_bed",
        name="Bedroom Dehumidifier",
        room="bedroom",
    )
    dehum.turn_off()
    sensor = VirtualClimateSensor(
        device_id="sensor_bed",
        name="Bedroom Sensor",
        room="bedroom",
        initial_temp=20.0,
        initial_rh=65.0,
    )
    app.registry.register(dehum)
    app.registry.register(sensor)

    # User manually turns ON the dehumidifier during an active exclusion window
    ok, _ = app.execute_device_command("dh_bed", "turn_on")
    assert ok is True
    assert dehum.is_on is True

    # Both QuietScheduleAutomation and CondensationPreventionAutomation must respect the manual hold
    now_dt = datetime.fromtimestamp(app._manual_overrides["dh_bed"] - 1800)
    for auto in app.automations:
        if isinstance(auto, (QuietScheduleAutomation, CondensationPreventionAutomation)):
            logs = auto.evaluate(app.registry, app.event_bus, current_dt=now_dt)
            assert any("MANUAL HOLD" in entry for entry in logs)

    assert dehum.is_on is True


def test_update_config_preserves_cooldown_and_alert_state():
    from smarthome.automations.alerts import HealthAlertAutomation

    cfg = SmartHomeConfig.from_dict(
        {
            "location": {"latitude": 0.0, "longitude": 0.0, "city": "Test City"},
            "condensation": {"enabled": True, "target_dew_point_c": 10.0},
            "alerts": {"enabled": True},
        }
    )
    app = SmartHomeApplication(cfg, refresh_on_init=False)

    cond_auto = next(a for a in app.automations if isinstance(a, CondensationPreventionAutomation))
    alert_auto = next(a for a in app.automations if isinstance(a, HealthAlertAutomation))
    cond_auto._last_power_change["dh_bed"] = 12345.0
    alert_auto._last_notified["tank_full:dh_bed"] = 67890.0

    app.update_config({"condensation": {"min_target_rh": 45}})

    new_cond = next(a for a in app.automations if isinstance(a, CondensationPreventionAutomation))
    new_alert = next(a for a in app.automations if isinstance(a, HealthAlertAutomation))
    assert new_cond._last_power_change.get("dh_bed") == 12345.0
    assert new_alert._last_notified.get("tank_full:dh_bed") == 67890.0
