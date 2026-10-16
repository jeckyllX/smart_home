"""
Unit tests for CondensationPreventionAutomation.
"""

from smarthome.automations.condensation import CondensationPreventionAutomation
from smarthome.core.events import EventBus
from smarthome.core.registry import DeviceRegistry
from smarthome.drivers.virtual.mock_climate import VirtualClimateSensor, VirtualDehumidifier
from smarthome.physics.psychrometrics import GlazingType


def test_condensation_prevention_adjusts_dehumidifier():
    registry = DeviceRegistry()
    event_bus = EventBus()

    # Outdoor weather sensor in 'outdoor' room
    outdoor = VirtualClimateSensor(
        device_id="out_weather",
        name="Outdoor Sensor",
        room="outdoor",
        initial_temp=-5.0,  # Cold outside (-5°C)
        initial_rh=80.0,
    )
    registry.register(outdoor)

    # Living room sensor and dehumidifier
    indoor_sensor = VirtualClimateSensor(
        device_id="lr_sensor",
        name="Living Room Sensor",
        room="living_room",
        initial_temp=20.0,
        initial_rh=65.0,  # High room humidity
    )
    dehumidifier = VirtualDehumidifier(
        device_id="lr_dehumidifier",
        name="Living Room Dehumidifier",
        room="living_room",
    )
    # Default target starts at 55
    dehumidifier.set_target_humidity(55)

    registry.register(indoor_sensor)
    registry.register(dehumidifier)

    automation = CondensationPreventionAutomation(
        glazing=GlazingType.DOUBLE,
        min_target_rh=40,
        max_target_rh=60,
    )

    logs = automation.evaluate(registry, event_bus)

    # Because outside is -5°C and inside is 20°C:
    # Double glazing glass surface = 20 - 0.25*(25) = 13.75°C
    # Safe dew point is 13.75 - 1.5 = 12.25°C
    # Inverted target RH is ~60%
    assert dehumidifier.target_humidity_percent is not None
    assert dehumidifier.target_humidity_percent <= 60
    assert any("Living Room Dehumidifier" in line for line in logs)


def test_tank_full_skips_adjustment():
    registry = DeviceRegistry()
    event_bus = EventBus()

    outdoor = VirtualClimateSensor(
        device_id="out_weather",
        name="Outdoor Sensor",
        room="outdoor",
        initial_temp=-5.0,
        initial_rh=80.0,
    )
    dehumidifier = VirtualDehumidifier(
        device_id="lr_dehumidifier",
        name="Living Room Dehumidifier",
        room="living_room",
    )
    dehumidifier.set_tank_full(True)

    registry.register(outdoor)
    registry.register(dehumidifier)

    automation = CondensationPreventionAutomation()
    logs = automation.evaluate(registry, event_bus)

    assert any("tank is full" in line for line in logs)


def _room_dehumidifier(target_rh: int = 60) -> VirtualDehumidifier:
    dehumidifier = VirtualDehumidifier(
        device_id="lr_dehumidifier",
        name="Living Room Dehumidifier",
        room="living_room",
    )
    dehumidifier.set_target_humidity(target_rh)
    # Count only the writes the automation makes, not this setup call.
    dehumidifier.set_target_calls = 0
    return dehumidifier


def _living_room_automation(**kwargs) -> CondensationPreventionAutomation:
    defaults = {"target_dew_point_c": 12.0, "min_target_rh": 35, "max_target_rh": 70}
    defaults.update(kwargs)
    return CondensationPreventionAutomation(**defaults)


def test_fixed_dew_point_mode_without_outdoor_sensor():
    registry = DeviceRegistry()
    event_bus = EventBus()

    registry.register(
        VirtualClimateSensor(
            device_id="lr_sensor",
            name="Living Room Sensor",
            room="living_room",
            initial_temp=20.0,
            initial_rh=65.0,
        )
    )
    dehumidifier = _room_dehumidifier(target_rh=45)
    registry.register(dehumidifier)

    # Fixed mode needs no outdoor sensor.
    automation = _living_room_automation()
    logs = automation.evaluate(registry, event_bus)

    # A 12°C dew point at 20°C is ~60.0% RH, snapped to the 5% device step.
    assert dehumidifier.target_humidity_percent == 60
    assert any("SafeDewPoint=12.0" in line for line in logs)
    assert not any("No outdoor temperature" in line for line in logs)


def test_window_mode_requires_outdoor_temperature():
    registry = DeviceRegistry()
    event_bus = EventBus()

    dehumidifier = _room_dehumidifier()
    dehumidifier.set_current_humidity(60.0)
    registry.register(dehumidifier)

    automation = CondensationPreventionAutomation()  # window mode, no target_dew_point_c
    logs = automation.evaluate(registry, event_bus)

    assert any("No outdoor temperature sensor" in line for line in logs)
    assert dehumidifier.set_target_calls == 0


def test_deadband_blocks_move_within_band():
    registry = DeviceRegistry()
    event_bus = EventBus()
    registry.register(
        VirtualClimateSensor(
            device_id="lr_sensor",
            name="Living Room Sensor",
            room="living_room",
            initial_temp=20.0,
            initial_rh=65.0,
        )
    )
    # Raw safe RH is 60.0%; the current target of 55% is inside the 6% deadband.
    dehumidifier = _room_dehumidifier(target_rh=55)
    registry.register(dehumidifier)

    automation = _living_room_automation(rh_deadband=6)
    logs = automation.evaluate(registry, event_bus)

    assert dehumidifier.set_target_calls == 0
    assert dehumidifier.target_humidity_percent == 55
    assert any("within deadband" in line for line in logs)


def test_deadband_allows_move_beyond_band():
    registry = DeviceRegistry()
    event_bus = EventBus()
    registry.register(
        VirtualClimateSensor(
            device_id="lr_sensor",
            name="Living Room Sensor",
            room="living_room",
            initial_temp=20.0,
            initial_rh=65.0,
        )
    )
    dehumidifier = _room_dehumidifier(target_rh=55)
    registry.register(dehumidifier)

    # 60.0% - 55% = 5.0% is at the 5% deadband edge, so the write goes through.
    automation = _living_room_automation(rh_deadband=5)
    automation.evaluate(registry, event_bus)

    assert dehumidifier.set_target_calls == 1
    assert dehumidifier.target_humidity_percent == 60


def test_target_clamped_to_config_and_device_overlap():
    registry = DeviceRegistry()
    event_bus = EventBus()
    registry.register(
        VirtualClimateSensor(
            device_id="lr_sensor",
            name="Living Room Sensor",
            room="living_room",
            initial_temp=20.0,
            initial_rh=65.0,
        )
    )
    dehumidifier = _room_dehumidifier(target_rh=45)
    registry.register(dehumidifier)

    # Raw target is ~60%, capped by max_target_rh to the device step below it.
    automation = _living_room_automation(min_target_rh=40, max_target_rh=50)
    automation.evaluate(registry, event_bus)

    assert dehumidifier.target_humidity_percent == 50


def test_non_overlapping_bounds_are_logged_and_skipped():
    registry = DeviceRegistry()
    event_bus = EventBus()
    registry.register(
        VirtualClimateSensor(
            device_id="lr_sensor",
            name="Living Room Sensor",
            room="living_room",
            initial_temp=20.0,
            initial_rh=65.0,
        )
    )
    dehumidifier = _room_dehumidifier()
    registry.register(dehumidifier)

    # Config min 75% is above the device max of 70%.
    automation = _living_room_automation(min_target_rh=75, max_target_rh=80)
    logs = automation.evaluate(registry, event_bus)

    assert any("do not overlap the device range" in line for line in logs)
    assert dehumidifier.set_target_calls == 0


def test_assumed_temp_and_builtin_sensor_are_logged():
    registry = DeviceRegistry()
    event_bus = EventBus()

    # Dehumidifier only: no separate temperature sensor, so the default is used
    # and the built-in humidity sensor is the fallback.
    dehumidifier = _room_dehumidifier(target_rh=55)
    dehumidifier.set_current_humidity(60.0)
    registry.register(dehumidifier)

    automation = _living_room_automation(target_dew_point_c=14.0)
    logs = automation.evaluate(registry, event_bus)

    assert any("indoor temp assumed" in line for line in logs)
    assert any("built-in sensor" in line for line in logs)
