"""
SmartHomeApplication coordinator and runtime.
Owns the registry, drivers, event bus, and active automations.
"""

from __future__ import annotations

import logging
import signal
import threading
import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from smarthome.web.server import SmartHomeWebServer

from smarthome.automations.base import Automation
from smarthome.automations.condensation import CondensationPreventionAutomation
from smarthome.automations.schedule import QuietScheduleAutomation
from smarthome.config.schema import SmartHomeConfig
from smarthome.core.events import EventBus
from smarthome.core.registry import DeviceRegistry
from smarthome.core.traits import (
    BatteryLevelTrait,
    HumidityControlTrait,
    HumiditySensorTrait,
    ModeControlTrait,
    OnOffTrait,
    StatusFlagsTrait,
    TankLevelTrait,
    TemperatureForecastTrait,
    TemperatureSensorTrait,
)
from smarthome.drivers.ble.thermopro import ThermoProDriver
from smarthome.drivers.tuya.meaco_arete import TuyaDriver
from smarthome.drivers.weather.open_meteo import OpenMeteoDriver

logger = logging.getLogger("SmartHomeApp")


class SmartHomeApplication:
    """
    Top-level application container coordinating the smart home platform.
    """

    def __init__(self, config: SmartHomeConfig):
        self.config = config
        self.registry = DeviceRegistry()
        self.event_bus = EventBus()
        self.automations: list[Automation] = []
        self._lock = threading.RLock()
        self._running = False
        self._web_server: SmartHomeWebServer | None = None

        self.last_evaluation_logs: list[str] = []
        self.last_evaluation_time: float | None = None

        self._setup_drivers()
        self._setup_automations()

    def _setup_drivers(self) -> None:
        # Weather driver
        loc = self.config.location
        weather_driver = OpenMeteoDriver(
            latitude=loc.latitude,
            longitude=loc.longitude,
            name=f"Weather Station ({loc.city})",
        )
        weather_driver.setup(self.registry, self.event_bus)

        # Tuya driver
        if self.config.tuya_devices:
            tuya_driver = TuyaDriver(self.config.tuya_devices)
            tuya_driver.setup(self.registry, self.event_bus)

        # ThermoPro BLE driver
        if self.config.ble_devices:
            ble_driver = ThermoProDriver(self.config.ble_devices)
            ble_driver.setup(self.registry, self.event_bus)

    def _setup_automations(self) -> None:
        with self._lock:
            self.automations.clear()

            # 1. Quiet Hours / Day-of-Week / Exclusion Schedule
            s_cfg = self.config.quiet_schedule
            schedule_auto: QuietScheduleAutomation | None = None
            if s_cfg.enabled:
                schedule_auto = QuietScheduleAutomation(
                    start_time=s_cfg.start_time,
                    end_time=s_cfg.end_time,
                    rooms=s_cfg.rooms,
                    night_mode=s_cfg.night_mode,
                    day_mode=s_cfg.day_mode,
                    night_days=s_cfg.night_days,
                    all_day_sleep_days=s_cfg.all_day_sleep_days,
                    exclusion_windows=s_cfg.exclusion_windows,
                )
                self.automations.append(schedule_auto)

            # 2. Condensation Prevention & Sensor-Driven Power
            c_cfg = self.config.condensation
            if c_cfg.enabled:
                condensation_auto = CondensationPreventionAutomation(
                    glazing=c_cfg.glazing,
                    default_indoor_temp_c=c_cfg.default_indoor_temp_c,
                    min_target_rh=c_cfg.min_target_rh,
                    max_target_rh=c_cfg.max_target_rh,
                    safety_margin_c=c_cfg.safety_margin_c,
                    target_dew_point_c=c_cfg.target_dew_point_c,
                    rh_deadband=c_cfg.rh_deadband,
                    lookahead_hours=c_cfg.lookahead_hours,
                    auto_power=c_cfg.auto_power,
                    turn_on_offset_rh=c_cfg.turn_on_offset_rh,
                    turn_off_offset_rh=c_cfg.turn_off_offset_rh,
                    min_cycle_seconds=c_cfg.min_cycle_seconds,
                    exclusion_checker=(schedule_auto.is_room_excluded if schedule_auto else None),
                )
                self.automations.append(condensation_auto)

    def evaluate_cycle(self) -> list[str]:
        """Poll telemetry across all devices and run registered automations thread-safely."""
        with self._lock:
            # 1. Refresh devices
            for dev in self.registry.all_devices():
                try:
                    dev.refresh()
                except Exception as e:
                    logger.warning("Error refreshing device %s: %s", dev.name, e)

            # 2. Run automations
            results: list[str] = []
            for auto in self.automations:
                try:
                    logs = auto.evaluate(self.registry, self.event_bus)
                    results.extend(logs)
                except Exception as e:
                    logger.error("Error evaluating %s: %s", auto.name, e, exc_info=True)
                    results.append(f"ERROR: {auto.name} failed: {e}")

            self.last_evaluation_logs = list(results)
            self.last_evaluation_time = time.time()
            return results

    def update_config(self, updated_dict: dict[str, Any]) -> None:
        """Apply modified configuration, persist to disk, and reconfigure automations."""
        with self._lock:
            # Merge updated_dict onto current config to preserve unedited keys
            merged = self.config.to_dict()
            for k, v in updated_dict.items():
                if isinstance(v, dict) and isinstance(merged.get(k), dict):
                    merged[k].update(v)
                else:
                    merged[k] = v

            raw_path = self.config.raw_path
            new_cfg = SmartHomeConfig.from_dict(merged)
            new_cfg.raw_path = raw_path

            self.config = new_cfg
            self._setup_automations()

            if self.config.raw_path:
                try:
                    self.config.save()
                    logger.info("Saved configuration updates to %s", self.config.raw_path)
                except Exception as e:
                    logger.error("Failed to save config to disk: %s", e)

            # Run immediate evaluation pass with new rules
            self.evaluate_cycle()

    def execute_device_command(
        self, device_id: str, action: str, **kwargs: Any
    ) -> tuple[bool, str]:
        """Execute a manual control command on a device."""
        with self._lock:
            dev = self.registry.get(device_id)
            if not dev:
                return False, f"Device '{device_id}' not found."

            if action == "turn_on":
                on_off = dev.get_trait(OnOffTrait)
                if not on_off:
                    return False, f"Device '{dev.name}' does not support power on/off."
                ok = on_off.turn_on()
                return ok, f"Turned ON '{dev.name}'" if ok else f"Failed to turn ON '{dev.name}'"

            elif action == "turn_off":
                on_off = dev.get_trait(OnOffTrait)
                if not on_off:
                    return False, f"Device '{dev.name}' does not support power on/off."
                ok = on_off.turn_off()
                return ok, f"Turned OFF '{dev.name}'" if ok else f"Failed to turn OFF '{dev.name}'"

            elif action == "set_target":
                h_ctrl = dev.get_trait(HumidityControlTrait)
                if not h_ctrl:
                    return False, f"Device '{dev.name}' does not support humidity control."
                target = int(kwargs.get("humidity", 55))
                ok = h_ctrl.set_target_humidity(target)
                msg = (
                    f"Target set to {target}% on '{dev.name}'"
                    if ok
                    else f"Failed to set target on '{dev.name}'"
                )
                return ok, msg

            elif action == "set_mode":
                m_ctrl = dev.get_trait(ModeControlTrait)
                if not m_ctrl:
                    return False, f"Device '{dev.name}' does not support mode control."
                mode = str(kwargs.get("mode", "manual"))
                ok = m_ctrl.set_mode(mode)
                msg = (
                    f"Mode set to '{mode}' on '{dev.name}'"
                    if ok
                    else f"Failed to set mode on '{dev.name}'"
                )
                return ok, msg

            elif action == "refresh":
                dev.refresh()
                return True, f"Refreshed '{dev.name}'"

            return False, f"Unknown action '{action}'"

    def get_dashboard_state(self) -> dict[str, Any]:
        """Generate a complete snapshot of devices, metrics, and room psychrometrics."""
        with self._lock:
            devices_by_room: dict[str, list[dict[str, Any]]] = {}
            for room in self.registry.all_rooms():
                devices_by_room[room] = []

            # Find active condensation automation for computing room status
            cond_auto: CondensationPreventionAutomation | None = None
            for auto in self.automations:
                if isinstance(auto, CondensationPreventionAutomation):
                    cond_auto = auto
                    break

            for dev in self.registry.all_devices():
                room = dev.room
                if room not in devices_by_room:
                    devices_by_room[room] = []

                on_off = dev.get_trait(OnOffTrait)
                t_sensor = dev.get_trait(TemperatureSensorTrait)
                h_sensor = dev.get_trait(HumiditySensorTrait)
                h_ctrl = dev.get_trait(HumidityControlTrait)
                m_ctrl = dev.get_trait(ModeControlTrait)
                tank = dev.get_trait(TankLevelTrait)
                batt = dev.get_trait(BatteryLevelTrait)
                flags = dev.get_trait(StatusFlagsTrait)
                t_forecast = dev.get_trait(TemperatureForecastTrait)

                dev_summary: dict[str, Any] = {
                    "id": dev.id,
                    "name": dev.name,
                    "room": dev.room,
                    "category": dev.category.value,
                    "is_online": dev.is_online,
                    "is_on": on_off.is_on if on_off else None,
                    "temperature_celsius": t_sensor.temperature_celsius if t_sensor else None,
                    "humidity_percent": h_sensor.humidity_percent if h_sensor else None,
                    "target_humidity_percent": h_ctrl.target_humidity_percent if h_ctrl else None,
                    "humidity_range": list(h_ctrl.humidity_range) if h_ctrl else None,
                    "humidity_step": h_ctrl.humidity_step if h_ctrl else None,
                    "current_mode": m_ctrl.current_mode if m_ctrl else None,
                    "supported_modes": m_ctrl.supported_modes if m_ctrl else [],
                    "is_tank_full": tank.is_tank_full if tank else None,
                    "battery_percent": batt.battery_percent if batt else None,
                    "status_flags": list(flags.status_flags) if flags else [],
                    "forecast_12h_min": (
                        t_forecast.min_forecast_temperature(12) if t_forecast else None
                    ),
                }
                devices_by_room[room].append(dev_summary)

            # Compute room psychrometrics
            room_psychrometrics: dict[str, Any] = {}
            if cond_auto:
                for dehum in self.registry.find_devices_with_trait(HumidityControlTrait):
                    r_status = cond_auto.compute_room_status(self.registry, dehum.room, dehum)
                    room_psychrometrics[dehum.room] = r_status

            return {
                "rooms": devices_by_room,
                "psychrometrics": room_psychrometrics,
                "last_evaluation_time": self.last_evaluation_time,
                "last_evaluation_logs": self.last_evaluation_logs,
                "config": {
                    "condensation": self.config.condensation.to_dict(),
                    "quiet_schedule": self.config.quiet_schedule.to_dict(),
                    "polling_interval_seconds": self.config.polling_interval_seconds,
                    "web": self.config.web.to_dict(),
                },
            }

    def start(
        self,
        run_web: bool = True,
        host: str | None = None,
        port: int | None = None,
    ) -> None:
        """Start daemon loop and optionally start the embedded web server."""
        self._running = True
        self._register_signals()

        if run_web and self.config.web.enabled:
            from smarthome.web.server import SmartHomeWebServer

            bind_host = host or self.config.web.host
            bind_port = port or self.config.web.port
            self._web_server = SmartHomeWebServer(self, host=bind_host, port=bind_port)
            self._web_server.start_background()

        interval = max(10, self.config.polling_interval_seconds)
        logger.info(
            "Smart Home System initialized. Monitoring %d device(s) across %d room(s).",
            len(self.registry.all_devices()),
            len(self.registry.all_rooms()),
        )

        while self._running:
            try:
                cycle_logs = self.evaluate_cycle()
                for log_msg in cycle_logs:
                    logger.info("[Automation] %s", log_msg)
            except Exception as e:
                logger.error("Error during automation cycle: %s", e, exc_info=True)

            for _ in range(interval):
                if not self._running:
                    break
                time.sleep(1.0)

        if self._web_server:
            self._web_server.stop()
        logger.info("Smart Home System shut down cleanly.")

    def stop(self) -> None:
        self._running = False
        if self._web_server:
            self._web_server.stop()

    def _register_signals(self) -> None:
        def handle_signal(sig, frame):
            logger.info("Received termination signal (%s). Exiting...", sig)
            self.stop()

        signal.signal(signal.SIGINT, handle_signal)
        signal.signal(signal.SIGTERM, handle_signal)
