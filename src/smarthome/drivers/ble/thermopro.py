"""
Bluetooth Low Energy (BLE) driver for ThermoPro TP35x/TP39x climate sensors.
Supports TP350, TP357, TP358, and related BLE indoor thermometers.
"""

from __future__ import annotations

import asyncio
import logging
import struct
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable

from smarthome.core.device import DeviceCategory
from smarthome.core.events import EventBus, TelemetryEvent
from smarthome.core.registry import DeviceRegistry
from smarthome.core.traits import BatteryLevelTrait
from smarthome.devices.climate import ClimateSensorDevice
from smarthome.drivers.base import Driver

logger = logging.getLogger("ThermoProDriver")

# Known ThermoPro family prefixes for advertising local names
THERMOPRO_NAME_PREFIXES = ("TP35", "TP39")

# Map 2-bit battery state to percentage (verified on TP35x hardware)
BATTERY_LEVEL_MAP: dict[int, int] = {
    0: 1,
    1: 50,
    2: 100,
    3: 100,
}


@dataclass(frozen=True)
class ThermoProReading:
    """Decoded telemetry reading from a ThermoPro BLE advertisement."""

    temperature_celsius: float
    humidity_percent: float
    battery_percent: int
    model: str = "TP35x"


def normalize_mac(mac: str) -> str:
    """Normalize MAC address string to uppercase with standard colons."""
    cleaned = mac.strip().upper().replace("-", ":")
    parts = cleaned.split(":")
    if len(parts) == 6 and all(len(p) <= 2 for p in parts):
        return ":".join(p.zfill(2) for p in parts)
    return cleaned


def decode_thermopro_advertisement(
    local_name: str | None,
    manufacturer_data: dict[int, bytes] | None,
) -> ThermoProReading | None:
    """
    Passively parse temperature, humidity, and battery from a ThermoPro BLE advertisement.

    ThermoPro TP35x/TP39x packets place a 6+ byte structure across the 2-byte company ID
    and manufacturer payload bytes:
      data[1:3]: signed 16-bit little-endian integer in tenths of °C
      data[3]:   unsigned 8-bit integer relative humidity in %
      data[4]:   lower two bits represent battery level (0=low, 1=med, 2=full)
    """
    if not manufacturer_data:
        return None

    # Filter by advertised name if present
    name = (local_name or "").strip()
    if name and not any(name.startswith(prefix) for prefix in THERMOPRO_NAME_PREFIXES):
        return None

    # Reconstruct combined manufacturer data (company ID little-endian + payload)
    last_id = list(manufacturer_data.keys())[-1]
    raw_payload = manufacturer_data[last_id]
    data = int(last_id).to_bytes(2, byteorder="little") + raw_payload

    if len(data) < 6:
        return None

    temp_humi = data[1:4]
    # Filter out uninitialized / invalid sensor readings
    if temp_humi == b"\xff\xff\xff":
        return None

    try:
        temp_raw, humi_raw = struct.unpack("<hB", temp_humi)
    except struct.error:
        return None

    temp_c = round(temp_raw / 10.0, 1)
    humidity_pct = float(humi_raw)

    # Basic physical sanity check (-40C to 70C, 0 to 100% RH)
    if not (-40.0 <= temp_c <= 70.0 and 0.0 <= humidity_pct <= 100.0):
        return None

    battery_state = data[4] & 0x03
    battery_pct = BATTERY_LEVEL_MAP.get(battery_state, 100)

    model = name.split()[0] if name else "TP35x"
    return ThermoProReading(
        temperature_celsius=temp_c,
        humidity_percent=humidity_pct,
        battery_percent=battery_pct,
        model=model,
    )


async def _bleak_scan_async(
    timeout: float,
    target_macs: set[str],
) -> dict[str, ThermoProReading]:
    """Execute asynchronous BLE advertisement scan via bleak."""
    from bleak import BleakScanner
    from bleak.backends.device import BLEDevice
    from bleak.backends.scanner import AdvertisementData

    readings: dict[str, ThermoProReading] = {}
    stop_event = asyncio.Event()

    def detection_callback(device: BLEDevice, adv_data: AdvertisementData) -> None:
        mac = normalize_mac(device.address)
        reading = decode_thermopro_advertisement(
            adv_data.local_name or device.name,
            adv_data.manufacturer_data,
        )
        if reading is not None:
            readings[mac] = reading
            # Early exit if all expected devices have reported
            if target_macs and target_macs.issubset(readings.keys()):
                stop_event.set()

    scanner = BleakScanner(detection_callback=detection_callback)
    await scanner.start()
    try:
        await asyncio.wait_for(stop_event.wait(), timeout=timeout)
    except asyncio.TimeoutError:
        pass
    finally:
        await scanner.stop()

    return readings


def default_ble_scanner(timeout: float, target_macs: set[str]) -> dict[str, ThermoProReading]:
    """Default synchronous wrapper around bleak BLE scanning."""
    try:
        return asyncio.run(_bleak_scan_async(timeout, target_macs))
    except Exception as e:
        logger.warning("BLE scan failed or Bluetooth adapter unavailable: %s", e)
        return {}


class ThermoProScannerHub:
    """
    Shared scan hub coordinating BLE discovery and caching across multiple sensors.
    Ensures a single scan pass updates all registered ThermoPro devices.
    """

    def __init__(
        self,
        scan_timeout_seconds: float = 12.0,
        cache_ttl_seconds: float = 30.0,
        scan_backend: Callable[[float, set[str]], dict[str, ThermoProReading]] | None = None,
    ):
        self.scan_timeout_seconds = scan_timeout_seconds
        self.cache_ttl_seconds = cache_ttl_seconds
        self._scan_backend = scan_backend or default_ble_scanner

        self._lock = threading.Lock()
        self._registered_macs: set[str] = set()
        self._cache: dict[str, ThermoProReading] = {}
        self._last_scan_time: float = 0.0

    def register_mac(self, mac: str) -> None:
        with self._lock:
            self._registered_macs.add(normalize_mac(mac))

    def get_reading(self, mac: str) -> ThermoProReading | None:
        norm_mac = normalize_mac(mac)
        now = time.time()
        with self._lock:
            cache_valid = (now - self._last_scan_time) < self.cache_ttl_seconds
            if cache_valid and norm_mac in self._cache:
                return self._cache[norm_mac]

        # Trigger a fresh scan for all registered sensors
        self.scan_all()

        with self._lock:
            return self._cache.get(norm_mac)

    def scan_all(self) -> dict[str, ThermoProReading]:
        """Perform scan pass and update internal reading cache."""
        with self._lock:
            targets = set(self._registered_macs)

        results = self._scan_backend(self.scan_timeout_seconds, targets)

        with self._lock:
            self._cache.update(results)
            self._last_scan_time = time.time()
            return dict(self._cache)


class ThermoProBleDevice(ClimateSensorDevice, BatteryLevelTrait):
    """
    ClimateSensorDevice representing a physical ThermoPro BLE thermometer/hygrometer.
    Also exposes BatteryLevelTrait.
    """

    def __init__(
        self,
        device_id: str,
        mac: str,
        name: str = "ThermoPro Sensor",
        room: str = "living_room",
        model: str = "TP35x",
        scanner_hub: ThermoProScannerHub | None = None,
        event_bus: EventBus | None = None,
    ):
        super().__init__(
            device_id=device_id,
            name=name,
            room=room,
            category=DeviceCategory.CLIMATE_SENSOR,
            manufacturer="ThermoPro",
            model=model,
        )
        self.mac = normalize_mac(mac)
        self.scanner_hub = scanner_hub or ThermoProScannerHub()
        self.event_bus = event_bus

        # Register BatteryLevelTrait
        self.register_trait(BatteryLevelTrait, self)

        self._lock = threading.Lock()
        self._temp_c: float | None = None
        self._rh_pct: float | None = None
        self._battery_pct: int | None = None
        self._is_online = False

        self.scanner_hub.register_mac(self.mac)

    @property
    def is_online(self) -> bool:
        return self._is_online

    @property
    def temperature_celsius(self) -> float | None:
        return self._temp_c

    @property
    def humidity_percent(self) -> float | None:
        return self._rh_pct

    @property
    def battery_percent(self) -> int | None:
        return self._battery_pct

    def refresh(self) -> bool:
        reading = self.scanner_hub.get_reading(self.mac)
        with self._lock:
            if reading is None:
                self._is_online = False
                return False

            self._temp_c = reading.temperature_celsius
            self._rh_pct = reading.humidity_percent
            self._battery_pct = reading.battery_percent
            self._is_online = True
            if reading.model and reading.model != "TP35x":
                self.model = reading.model

        if self.event_bus:
            self.event_bus.publish(
                TelemetryEvent(
                    device_id=self.id,
                    metric="temperature",
                    value=reading.temperature_celsius,
                    unit="°C",
                )
            )
            self.event_bus.publish(
                TelemetryEvent(
                    device_id=self.id,
                    metric="relative_humidity",
                    value=reading.humidity_percent,
                    unit="%",
                )
            )
            self.event_bus.publish(
                TelemetryEvent(
                    device_id=self.id,
                    metric="battery",
                    value=float(reading.battery_percent),
                    unit="%",
                )
            )
        return True


class ThermoProDriver(Driver):
    """
    Driver managing discovery, registration, and scanning of ThermoPro BLE climate sensors.
    """

    def __init__(
        self,
        devices_config: list[dict[str, Any]],
        scanner_hub: ThermoProScannerHub | None = None,
    ):
        super().__init__(name="ThermoProBleDriver")
        self._configs = devices_config
        self._scanner_hub = scanner_hub or ThermoProScannerHub()
        self._devices: list[ThermoProBleDevice] = []

    def setup(self, registry: DeviceRegistry, event_bus: EventBus) -> bool:
        for cfg in self._configs:
            raw_mac = cfg.get("mac")
            if not raw_mac:
                logger.warning("Skipping ThermoPro BLE device with missing 'mac': %s", cfg)
                continue

            mac = normalize_mac(raw_mac)
            default_id = f"thermopro_{mac.replace(':', '').lower()[-4:]}"
            dev_id = str(cfg.get("id") or default_id)
            name = str(cfg.get("name") or f"ThermoPro ({mac[-5:]})")
            room = str(cfg.get("room") or "living_room")
            model = str(cfg.get("model") or "TP35x")

            device = ThermoProBleDevice(
                device_id=dev_id,
                mac=mac,
                name=name,
                room=room,
                model=model,
                scanner_hub=self._scanner_hub,
                event_bus=event_bus,
            )
            self._devices.append(device)
            registry.register(device)

        # Trigger single scan pass to initialize all registered devices
        if self._devices:
            self._scanner_hub.scan_all()
            for dev in self._devices:
                dev.refresh()

        return True

    def teardown(self) -> None:
        self._devices.clear()


async def _scan_for_thermopro_async(timeout: float) -> list[dict[str, Any]]:
    """Scan for all advertising ThermoPro devices in range."""
    from bleak import BleakScanner
    from bleak.backends.device import BLEDevice
    from bleak.backends.scanner import AdvertisementData

    discovered: dict[str, dict[str, Any]] = {}

    def callback(device: BLEDevice, adv_data: AdvertisementData) -> None:
        mac = normalize_mac(device.address)
        reading = decode_thermopro_advertisement(
            adv_data.local_name or device.name,
            adv_data.manufacturer_data,
        )
        if reading is not None:
            discovered[mac] = {
                "mac": mac,
                "name": adv_data.local_name or device.name or "ThermoPro",
                "model": reading.model,
                "rssi": adv_data.rssi,
                "temperature_celsius": reading.temperature_celsius,
                "humidity_percent": reading.humidity_percent,
                "battery_percent": reading.battery_percent,
            }

    scanner = BleakScanner(detection_callback=callback)
    await scanner.start()
    try:
        await asyncio.sleep(timeout)
    finally:
        await scanner.stop()

    return list(discovered.values())


def scan_for_thermopro_sensors(timeout: float = 12.0) -> list[dict[str, Any]]:
    """Utility function to scan for all ThermoPro BLE sensors in range."""
    try:
        return asyncio.run(_scan_for_thermopro_async(timeout))
    except Exception as e:
        logger.error("Error scanning for ThermoPro sensors: %s", e)
        return []
