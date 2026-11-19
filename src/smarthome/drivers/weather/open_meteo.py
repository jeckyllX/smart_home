"""
Open-Meteo weather driver that registers an outdoor ClimateSensorDevice.
"""

from __future__ import annotations

import logging
import math
import threading
import time
from typing import Any

import requests

from smarthome.core.device import DeviceCategory
from smarthome.core.events import EventBus, TelemetryEvent
from smarthome.core.registry import DeviceRegistry
from smarthome.core.traits import StatusFlagsTrait, TemperatureForecastTrait
from smarthome.devices.climate import ClimateSensorDevice
from smarthome.drivers.base import Driver
from smarthome.physics.psychrometrics import calculate_rh_for_dew_point

logger = logging.getLogger("OpenMeteoDriver")


class OpenMeteoWeatherDevice(ClimateSensorDevice, TemperatureForecastTrait, StatusFlagsTrait):
    """
    Hybrid outdoor weather station combining:
    1. Real-world physical ground observations from the nearest airport station (METAR).
    2. Numerical weather prediction forecast from Open-Meteo for 24h predictive lookahead.
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

        self.register_trait(TemperatureForecastTrait, self)
        self.register_trait(StatusFlagsTrait, self)

        self._lock = threading.Lock()
        self._last_fetch = 0.0
        self._temp_c: float | None = None
        self._rh_pct: float | None = None
        self._hourly_temps_c: tuple[float, ...] = ()
        self._station_source: str = "Initializing"
        self._is_online = False

    @property
    def is_online(self) -> bool:
        with self._lock:
            return self._is_online

    @property
    def temperature_celsius(self) -> float | None:
        with self._lock:
            return self._temp_c

    @property
    def humidity_percent(self) -> float | None:
        with self._lock:
            return self._rh_pct

    @property
    def hourly_temperature_forecast_celsius(self) -> tuple[float, ...]:
        with self._lock:
            return self._hourly_temps_c

    @property
    def status_flags(self) -> tuple[str, ...]:
        with self._lock:
            if self._station_source:
                return (self._station_source,)
            return ()

    @property
    def station_source(self) -> str:
        with self._lock:
            return self._station_source

    def min_forecast_temperature(self, hours: int) -> float | None:
        if hours <= 0:
            return None
        with self._lock:
            if not self._hourly_temps_c:
                return None
            return min(self._hourly_temps_c[:hours])

    def update_location(self, latitude: float, longitude: float, name: str) -> bool:
        """Atomically update coordinates and display name; return True if location changed."""
        with self._lock:
            loc_changed = (
                self.latitude != latitude or self.longitude != longitude or self.name != name
            )
            self.latitude = latitude
            self.longitude = longitude
            self.name = name
            return loc_changed

    def _fetch_nearest_metar(
        self, lat: float | None = None, lon: float | None = None
    ) -> tuple[float | None, float | None, str | None]:
        """
        Query aviationweather.gov for the nearest physical airport weather station
        around (lat, lon).
        Returns (temp_c, rh_pct, source_label) or (None, None, None) on failure.
        """
        try:
            if lat is None or lon is None:
                with self._lock:
                    lat = self.latitude if lat is None else lat
                    lon = self.longitude if lon is None else lon
            # Search within ~80 km bounding box
            d_lat = 0.75
            d_lon = 1.0
            bbox = f"{lat - d_lat:.4f},{lon - d_lon:.4f},{lat + d_lat:.4f},{lon + d_lon:.4f}"
            url = f"https://aviationweather.gov/api/data/metar?bbox={bbox}&format=json"
            headers = {"User-Agent": "SmartHome/1.0"}
            resp = requests.get(url, headers=headers, timeout=5.0)
            if not resp.ok:
                return None, None, None

            data = resp.json()
            if not isinstance(data, list) or not data:
                return None, None, None

            candidates = [
                s
                for s in data
                if isinstance(s, dict)
                and s.get("temp") is not None
                and s.get("lat") is not None
                and s.get("lon") is not None
            ]
            if not candidates:
                return None, None, None

            cos_lat = math.cos(math.radians(lat))

            def dist_sq(s: dict[str, Any]) -> float:
                return (float(s["lat"]) - lat) ** 2 + ((float(s["lon"]) - lon) * cos_lat) ** 2

            nearest = min(candidates, key=dist_sq)
            station_id = str(nearest.get("icaoId") or "METAR")
            source_label = f"Physical ({station_id})"
            temp_c = float(nearest["temp"])

            # Compute or extract RH from temp and dew point
            rh_pct: float | None = None
            dewp = nearest.get("dewp")
            if dewp is not None:
                try:
                    dewp_c = float(dewp)
                    rh_pct = calculate_rh_for_dew_point(temp_c, dewp_c)
                    rh_pct = max(0.0, min(100.0, rh_pct))
                except Exception:
                    rh_pct = None

            return temp_c, rh_pct, source_label
        except Exception as e:
            logger.debug("Nearest physical station lookup skipped: %s", e)
            return None, None, None

    def refresh(self, force: bool = False) -> bool:
        now = time.time()
        with self._lock:
            if not force and self._temp_c is not None and (now - self._last_fetch < self.cache_ttl):
                return True
            lat = self.latitude
            lon = self.longitude
            station_name = self.name

        om_temp: float | None = None
        om_rh: float | None = None
        hourly_temps: tuple[float, ...] = ()
        try:
            params = {
                "latitude": str(lat),
                "longitude": str(lon),
                "current": "temperature_2m,relative_humidity_2m",
                "hourly": "temperature_2m",
                "forecast_hours": "24",
            }
            resp = requests.get(self.ENDPOINT, params=params, timeout=5.0)
            resp.raise_for_status()
            data = resp.json()
            current = data.get("current", {})
            hourly = data.get("hourly", {})
            raw_temp = current.get("temperature_2m")
            raw_rh = current.get("relative_humidity_2m")
            raw_hourly = hourly.get("temperature_2m", [])
            hourly_temps = tuple(float(t) for t in raw_hourly if t is not None)
            if raw_temp is not None:
                om_temp = float(raw_temp)
            if raw_rh is not None:
                om_rh = float(raw_rh)
        except Exception as e:
            logger.warning("Error fetching Open-Meteo weather for %s: %s", station_name, e)

        obs_temp, obs_rh, obs_source = self._fetch_nearest_metar(lat, lon)

        temp_c: float | None = None
        rh_pct: float | None = None
        source = "Initializing"

        if obs_temp is not None:
            temp_c = obs_temp
            rh_pct = obs_rh if obs_rh is not None else om_rh
            source = obs_source or "Physical (METAR)"
        elif om_temp is not None:
            temp_c = om_temp
            rh_pct = om_rh
            source = "Open-Meteo Model"
        else:
            with self._lock:
                self._is_online = False
            return False

        fetch_ts = time.time()
        with self._lock:
            self._temp_c = temp_c
            self._rh_pct = rh_pct
            self._hourly_temps_c = hourly_temps
            self._station_source = source
            self._last_fetch = fetch_ts
            self._is_online = True

        if self.event_bus:
            self.event_bus.publish(
                TelemetryEvent(
                    device_id=self.id,
                    metric="temperature",
                    value=temp_c,
                    unit="°C",
                )
            )
            if rh_pct is not None:
                self.event_bus.publish(
                    TelemetryEvent(
                        device_id=self.id,
                        metric="relative_humidity",
                        value=rh_pct,
                        unit="%",
                    )
                )
        return True


class OpenMeteoDriver(Driver):
    """
    Driver initializing Open-Meteo weather station devices.
    """

    def __init__(
        self,
        latitude: float,
        longitude: float,
        name: str = "Outdoor Weather",
        refresh_on_setup: bool = True,
    ):
        super().__init__(name="OpenMeteoDriver")
        self.latitude = latitude
        self.longitude = longitude
        self.station_name = name
        self.refresh_on_setup = refresh_on_setup
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
        if self.refresh_on_setup:
            dev.refresh()
        self._device = dev
        registry.register(dev)
        return True

    def teardown(self) -> None:
        self._device = None
