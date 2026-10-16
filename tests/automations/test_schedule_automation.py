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
