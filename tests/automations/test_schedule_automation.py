"""
Unit tests for QuietScheduleAutomation.
"""

from datetime import datetime

from smarthome.automations.schedule import QuietScheduleAutomation
from smarthome.core.events import EventBus
from smarthome.core.registry import DeviceRegistry
from smarthome.drivers.virtual.mock_climate import VirtualDehumidifier


def test_quiet_hours_switches_to_sleep_at_night():
    registry = DeviceRegistry()
    event_bus = EventBus()

    dehum = VirtualDehumidifier(device_id="dh_bedroom", name="Bedroom Unit", room="bedroom")
    dehum.set_mode("manual")
    registry.register(dehum)

    automation = QuietScheduleAutomation(
        start_time="23:00",
        end_time="07:00",
        night_mode="sleep",
        day_mode="manual",
    )

    # Simulate night time 01:30
    night_time = datetime(2026, 10, 16, 1, 30)
    automation.evaluate(registry, event_bus, current_dt=night_time)
    assert dehum.current_mode == "sleep"

    # Simulate day time 14:00
    day_time = datetime(2026, 10, 16, 14, 0)
    automation.evaluate(registry, event_bus, current_dt=day_time)
    assert dehum.current_mode == "manual"


def test_exclusion_window_actively_turns_off_running_dehumidifier():
    from smarthome.config.schema import ExclusionWindowConfig

    registry = DeviceRegistry()
    event_bus = EventBus()

    dehum = VirtualDehumidifier(device_id="dh_bedroom", name="Bedroom Unit", room="bedroom")
    dehum.turn_on()
    assert dehum.is_on is True
    registry.register(dehum)

    exclusion = ExclusionWindowConfig(
        label="Deep Sleep",
        start_time="00:00",
        end_time="07:00",
        days=["fri"],
        rooms=["bedroom"],
        enabled=True,
    )

    automation = QuietScheduleAutomation(
        start_time="23:00",
        end_time="07:00",
        exclusion_windows=[exclusion],
    )

    # 2026-10-16 is a Friday at 03:00
    friday_night = datetime(2026, 10, 16, 3, 0)
    logs = automation.evaluate(registry, event_bus, current_dt=friday_night)

    assert dehum.is_on is False
    assert any("turned OFF (Exclusion 'Deep Sleep'" in line for line in logs)


def test_all_day_sleep_days_keeps_sleep_mode_during_daytime():
    registry = DeviceRegistry()
    event_bus = EventBus()

    dehum = VirtualDehumidifier(device_id="dh_bedroom", name="Bedroom Unit", room="bedroom")
    dehum.set_mode("manual")
    registry.register(dehum)

    automation = QuietScheduleAutomation(
        start_time="23:00",
        end_time="07:00",
        all_day_sleep_days=["sun"],
    )

    # 2026-10-18 is a Sunday at 14:00 (daytime)
    sunday_afternoon = datetime(2026, 10, 18, 14, 0)
    automation.evaluate(registry, event_bus, current_dt=sunday_afternoon)

    assert dehum.current_mode == "sleep"


def test_night_days_filter():
    registry = DeviceRegistry()
    event_bus = EventBus()

    dehum = VirtualDehumidifier(device_id="dh_bedroom", name="Bedroom Unit", room="bedroom")
    dehum.set_mode("manual")
    registry.register(dehum)

    # Only apply night mode on weekdays, not weekends
    automation = QuietScheduleAutomation(
        start_time="23:00",
        end_time="07:00",
        night_days=["mon", "tue", "wed", "thu", "fri"],
    )

    # 2026-10-18 is a Sunday at 02:00
    sunday_night = datetime(2026, 10, 18, 2, 0)
    automation.evaluate(registry, event_bus, current_dt=sunday_night)

    # Because Sunday is not in night_days, it should remain in day_mode ("manual")
    assert dehum.current_mode == "manual"
