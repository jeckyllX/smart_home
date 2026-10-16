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
