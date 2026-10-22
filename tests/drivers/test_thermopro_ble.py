"""
Unit tests for the ThermoPro BLE climate sensor driver, decoder, hub, and device.
"""

from __future__ import annotations

import struct
from unittest.mock import MagicMock

from smarthome.core.events import EventBus, TelemetryEvent
from smarthome.core.registry import DeviceRegistry
from smarthome.core.traits import (
    BatteryLevelTrait,
    HumiditySensorTrait,
    TemperatureSensorTrait,
)
from smarthome.drivers.ble.thermopro import (
    ThermoProBleDevice,
    ThermoProDriver,
    ThermoProReading,
    ThermoProScannerHub,
    decode_thermopro_advertisement,
    normalize_mac,
)


def _make_adv_data(
    temp_c: float,
    humidity: int,
    battery_code: int = 2,
) -> tuple[int, bytes]:
    """Helper to construct manufacturer data tuple matching ThermoPro payload."""
    temp_raw = int(round(temp_c * 10))
    temp_bytes = struct.pack("<h", temp_raw)
    company_id = int.from_bytes(bytes([0x00, temp_bytes[0]]), byteorder="little")
    payload = bytes([temp_bytes[1], humidity, battery_code & 0x03, 0x00])
    return company_id, payload


def test_normalize_mac():
    assert normalize_mac("a4:c1:38:12:34:56") == "A4:C1:38:12:34:56"
    assert normalize_mac("a4-c1-38-12-34-56") == "A4:C1:38:12:34:56"
    assert normalize_mac("  A4:C1:38:12:34:56  ") == "A4:C1:38:12:34:56"
    assert normalize_mac("a4:c1:38:1:2:3") == "A4:C1:38:01:02:03"


def test_decode_advertisement_valid():
    cid, payload = _make_adv_data(temp_c=21.5, humidity=55, battery_code=2)
    reading = decode_thermopro_advertisement("TP350 (1234)", {cid: payload})

    assert reading is not None
    assert reading.temperature_celsius == 21.5
    assert reading.humidity_percent == 55.0
    assert reading.battery_percent == 100
    assert reading.model == "TP350"


def test_decode_advertisement_negative_temp_and_low_battery():
    cid, payload = _make_adv_data(temp_c=-5.2, humidity=75, battery_code=0)
    reading = decode_thermopro_advertisement("TP357 (5678)", {cid: payload})

    assert reading is not None
    assert reading.temperature_celsius == -5.2
    assert reading.humidity_percent == 75.0
    assert reading.battery_percent == 1
    assert reading.model == "TP357"


def test_decode_advertisement_medium_battery():
    cid, payload = _make_adv_data(temp_c=18.0, humidity=45, battery_code=1)
    reading = decode_thermopro_advertisement("TP358 (9012)", {cid: payload})

    assert reading is not None
    assert reading.battery_percent == 50
    assert reading.model == "TP358"


def test_decode_advertisement_filters_unmatched_names():
    cid, payload = _make_adv_data(temp_c=20.0, humidity=50, battery_code=2)
    # Name not starting with TP<digit> or ThermoPro
    assert decode_thermopro_advertisement("RandomDevice", {cid: payload}) is None
    # TP-Link devices must be rejected
    assert decode_thermopro_advertisement("TP-Link_SmartPlug_1234", {cid: payload}) is None


def test_decode_advertisement_future_models_accepted():
    cid, payload = _make_adv_data(temp_c=22.0, humidity=40, battery_code=2)
    # Future models like TP360 or TP400 should be accepted
    reading_360 = decode_thermopro_advertisement("TP360 (A1B2)", {cid: payload})
    assert reading_360 is not None
    assert reading_360.model == "TP360"

    reading_400 = decode_thermopro_advertisement("TP400 (C3D4)", {cid: payload})
    assert reading_400 is not None
    assert reading_400.model == "TP400"


def test_decode_advertisement_allows_none_name():
    cid, payload = _make_adv_data(temp_c=20.0, humidity=50, battery_code=2)
    reading = decode_thermopro_advertisement(None, {cid: payload})
    assert reading is not None
    assert reading.temperature_celsius == 20.0
    assert reading.model == "TP35x"


def test_decode_advertisement_uninitialized_bytes():
    # If temp and humidity bytes are 0xFFFFFF
    cid = int.from_bytes(bytes([0x00, 0xFF]), byteorder="little")
    payload = bytes([0xFF, 0xFF, 0x02, 0x00])
    reading = decode_thermopro_advertisement("TP350", {cid: payload})
    assert reading is None


def test_decode_advertisement_short_payload():
    reading = decode_thermopro_advertisement("TP350", {1: b"\x01\x02"})
    assert reading is None


def test_decode_advertisement_out_of_range():
    # Temperature out of physical bounds (> 70 C)
    cid, payload = _make_adv_data(temp_c=85.0, humidity=50, battery_code=2)
    reading = decode_thermopro_advertisement("TP350", {cid: payload})
    assert reading is None

    # Humidity out of bounds (> 100%)
    cid, payload = _make_adv_data(temp_c=20.0, humidity=105, battery_code=2)
    reading = decode_thermopro_advertisement("TP350", {cid: payload})
    assert reading is None


def test_scanner_hub_caching_and_coordination():
    scan_count = 0

    def mock_backend(timeout: float, targets: set[str]) -> dict[str, ThermoProReading]:
        nonlocal scan_count
        scan_count += 1
        return {
            "A4:C1:38:12:34:56": ThermoProReading(
                temperature_celsius=22.0,
                humidity_percent=50.0,
                battery_percent=100,
                model="TP350",
            ),
            "A4:C1:38:65:43:21": ThermoProReading(
                temperature_celsius=19.5,
                humidity_percent=60.0,
                battery_percent=50,
                model="TP357",
            ),
        }

    hub = ThermoProScannerHub(
        scan_timeout_seconds=5.0,
        cache_ttl_seconds=30.0,
        scan_backend=mock_backend,
    )

    hub.register_mac("a4:c1:38:12:34:56")
    hub.register_mac("a4:c1:38:65:43:21")

    # First fetch triggers scan
    reading1 = hub.get_reading("A4:C1:38:12:34:56")
    assert reading1 is not None
    assert reading1.temperature_celsius == 22.0
    assert scan_count == 1

    # Second fetch for other device within TTL uses cached reading without rescanning
    reading2 = hub.get_reading("A4:C1:38:65:43:21")
    assert reading2 is not None
    assert reading2.temperature_celsius == 19.5
    assert scan_count == 1

    # Invalidate cache by setting last scan time back
    hub._last_scan_time = 0.0
    reading1_rescan = hub.get_reading("A4:C1:38:12:34:56")
    assert reading1_rescan is not None
    assert scan_count == 2


def test_thermopro_ble_device_traits_and_refresh():
    reading = ThermoProReading(
        temperature_celsius=21.2,
        humidity_percent=54.0,
        battery_percent=100,
        model="TP350",
    )
    mock_hub = MagicMock(spec=ThermoProScannerHub)
    mock_hub.get_reading.return_value = reading

    event_bus = EventBus()
    events_received: list[TelemetryEvent] = []
    event_bus.subscribe(TelemetryEvent, events_received.append)

    device = ThermoProBleDevice(
        device_id="tp_living",
        mac="A4:C1:38:12:34:56",
        name="Living Room Sensor",
        room="living_room",
        model="TP350",
        scanner_hub=mock_hub,
        event_bus=event_bus,
    )

    # Verify traits exposed
    assert device.has_trait(TemperatureSensorTrait)
    assert device.has_trait(HumiditySensorTrait)
    assert device.has_trait(BatteryLevelTrait)

    t_trait = device.get_trait(TemperatureSensorTrait)
    h_trait = device.get_trait(HumiditySensorTrait)
    b_trait = device.get_trait(BatteryLevelTrait)
    assert t_trait is not None
    assert h_trait is not None
    assert b_trait is not None

    # Initially offline before refresh
    assert not device.is_online
    assert t_trait.temperature_celsius is None

    # Refresh
    success = device.refresh()
    assert success is True
    assert device.is_online is True
    assert t_trait.temperature_celsius == 21.2
    assert h_trait.humidity_percent == 54.0
    assert b_trait.battery_percent == 100

    # Verify telemetry events published
    metrics = {e.metric: e.value for e in events_received}
    assert metrics.get("temperature") == 21.2
    assert metrics.get("relative_humidity") == 54.0
    assert metrics.get("battery") == 100.0


def test_thermopro_ble_device_refresh_offline():
    mock_hub = MagicMock(spec=ThermoProScannerHub)
    mock_hub.get_reading.return_value = None

    device = ThermoProBleDevice(
        device_id="tp_offline",
        mac="A4:C1:38:00:00:00",
        scanner_hub=mock_hub,
    )
    success = device.refresh()
    assert success is False
    assert device.is_online is False
    assert device.temperature_celsius is None


def test_thermopro_driver_setup_and_registration():
    configs = [
        {
            "id": "tp_1",
            "name": "ThermoPro 1",
            "mac": "A4:C1:38:11:11:11",
            "room": "living_room",
            "model": "TP350",
        },
        {
            "id": "tp_2",
            "name": "ThermoPro 2",
            "mac": "A4:C1:38:22:22:22",
            "room": "bedroom",
            "model": "TP357",
        },
        {
            # Invalid config missing MAC
            "id": "tp_invalid",
            "name": "Invalid Sensor",
        },
    ]

    mock_hub = MagicMock(spec=ThermoProScannerHub)
    driver = ThermoProDriver(devices_config=configs, scanner_hub=mock_hub)
    registry = DeviceRegistry()
    event_bus = EventBus()

    success = driver.setup(registry, event_bus)
    assert success is True

    # 2 valid devices registered
    assert len(registry.all_devices()) == 2
    dev1 = registry.get("tp_1")
    dev2 = registry.get("tp_2")
    assert dev1 is not None and dev1.room == "living_room"
    assert dev2 is not None and dev2.room == "bedroom"

    driver.teardown()
    assert len(driver._devices) == 0
