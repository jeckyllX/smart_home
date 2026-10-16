"""
Unit tests for DeviceRegistry, Traits, and EventBus.
"""

from smarthome.core.events import DeviceStateChangedEvent, EventBus
from smarthome.core.registry import DeviceRegistry
from smarthome.core.traits import HumidityControlTrait, HumiditySensorTrait
from smarthome.drivers.virtual.mock_climate import VirtualClimateSensor, VirtualDehumidifier


def test_device_registry_operations():
    registry = DeviceRegistry()
    dehum = VirtualDehumidifier(
        device_id="dh_1", name="Living Room Dehumidifier", room="living_room"
    )
    sensor = VirtualClimateSensor(device_id="sens_1", name="Bedroom Sensor", room="bedroom")

    registry.register(dehum)
    registry.register(sensor)

    assert len(registry.all_devices()) == 2
    assert len(registry.all_rooms()) == 2
    assert "living_room" in registry.all_rooms()
    assert "bedroom" in registry.all_rooms()

    # Query by room
    lr_devs = registry.get_by_room("living_room")
    assert len(lr_devs) == 1
    assert lr_devs[0].id == "dh_1"

    # Query by trait
    dehum_devs = registry.find_devices_with_trait(HumidityControlTrait)
    assert len(dehum_devs) == 1
    assert dehum_devs[0].id == "dh_1"

    sensors = registry.find_devices_with_trait(HumiditySensorTrait)
    # Both virtual sensor and virtual dehumidifier expose HumiditySensorTrait
    assert len(sensors) == 2


def test_virtual_dehumidifier_quantizes_target_to_step():
    dehum = VirtualDehumidifier(device_id="dh_q", name="Quantiser", room="living_room")
    dehum.set_target_humidity(47)
    assert dehum.target_humidity_percent == 45
    dehum.set_target_humidity(10)
    assert dehum.target_humidity_percent == 35
    dehum.set_target_humidity(90)
    assert dehum.target_humidity_percent == 70
    assert dehum.humidity_range == (35, 70)
    assert dehum.humidity_step == 5


def test_event_bus():
    bus = EventBus()
    received_events = []

    def on_state_change(evt: DeviceStateChangedEvent):
        received_events.append(evt)

    bus.subscribe(DeviceStateChangedEvent, on_state_change)

    event = DeviceStateChangedEvent(
        device_id="dh_1",
        trait_name="OnOffTrait",
        property_name="is_on",
        old_value=False,
        new_value=True,
    )
    bus.publish(event)

    assert len(received_events) == 1
    assert received_events[0].property_name == "is_on"
    assert received_events[0].new_value is True
