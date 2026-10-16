"""
Open-Meteo weather driver that registers an outdoor ClimateSensorDevice.
"""

from __future__ import annotations

import logging
import threading
import time

import requests

from smarthome.core.device import DeviceCategory
from smarthome.core.events import EventBus, TelemetryEvent
from smarthome.core.registry import DeviceRegistry
from smarthome.devices.climate import ClimateSensorDevice
from smarthome.drivers.base import Driver

logger = logging.getLogger("OpenMeteoDriver")


class OpenMeteoWeatherDevice(ClimateSensorDevice):
    """
    Virtual outdoor weather station backed by Open-Meteo public API.
    """

    ENDPOINT = "https://api.open-meteo.com/v1/forecast"

    def __init__(
        self,
        device_id: str,
        name: str,
        latitude: float,
        longitude: float,
        room: str = "outdoor",
        cache_ttl_seconds: int = 900,
        event_bus: EventBus | None = None,
    ):
        super().__init__(
            device_id=device_id,
            name=name,
            room=room,
            category=DeviceCategory.WEATHER_STATION,
            manufacturer="Open-Meteo",
            model="Virtual Station",
        )
        self.latitude = latitude
        self.longitude = longitude
        self.cache_ttl = cache_ttl_seconds
        self.event_bus = event_bus

        self._lock = threading.Lock()
        self._last_fetch = 0.0
        self._temp_c: float | None = None
        self._rh_pct: float | None = None
        self._is_online = False

    @property
    def is_online(self) -> bool:
        return self._is_online

    @property
    def temperature_celsius(self) -> float | None:
        return self._temp_c

    @property
    def humidity_percent(self) -> float | None:
        return self._rh_pct

    def refresh(self) -> bool:
        now = time.time()
        with self._lock:
            if self._temp_c is not None and (now - self._last_fetch < self.cache_ttl):
                return True

        try:
            params = {
                "latitude": str(self.latitude),
                "longitude": str(self.longitude),
                "current": "temperature_2m,relative_humidity_2m",
            }
            resp = requests.get(self.ENDPOINT, params=params, timeout=5.0)
            resp.raise_for_status()
            current = resp.json().get("current", {})
            temp = current.get("temperature_2m")
            rh = current.get("relative_humidity_2m")

            if temp is not None and rh is not None:
                with self._lock:
                    self._temp_c = float(temp)
                    self._rh_pct = float(rh)
                    self._last_fetch = now
                    self._is_online = True

                if self.event_bus:
                    self.event_bus.publish(
                        TelemetryEvent(
                            device_id=self.id,
                            metric="temperature",
                            value=self._temp_c,
                            unit="°C",
                        )
                    )
                    self.event_bus.publish(
                        TelemetryEvent(
                            device_id=self.id,
                            metric="relative_humidity",
                            value=self._rh_pct,
                            unit="%",
                        )
                    )
                return True
        except Exception as e:
            logger.warning("Error fetching weather for %s: %s", self.name, e)
            with self._lock:
                self._is_online = False
            return False
        return False


class OpenMeteoDriver(Driver):
    """
    Driver initializing Open-Meteo weather station devices.
    """

    def __init__(self, latitude: float, longitude: float, name: str = "Outdoor Weather"):
        super().__init__(name="OpenMeteoDriver")
        self.latitude = latitude
        self.longitude = longitude
        self.station_name = name
        self._device: OpenMeteoWeatherDevice | None = None

    def setup(self, registry: DeviceRegistry, event_bus: EventBus) -> bool:
        dev = OpenMeteoWeatherDevice(
            device_id="weather_outdoor",
            name=self.station_name,
            latitude=self.latitude,
            longitude=self.longitude,
            room="outdoor",
            event_bus=event_bus,
        )
        dev.refresh()
        self._device = dev
        registry.register(dev)
        return True

    def teardown(self) -> None:
        self._device = None
