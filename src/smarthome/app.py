"""
SmartHomeApplication coordinator and runtime.
Owns the registry, drivers, event bus, and active automations.
"""

from __future__ import annotations

import logging
import signal
import time

from smarthome.automations.base import Automation
from smarthome.automations.condensation import CondensationPreventionAutomation
from smarthome.automations.schedule import QuietScheduleAutomation
from smarthome.config.schema import SmartHomeConfig
from smarthome.core.events import EventBus
from smarthome.core.registry import DeviceRegistry
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
        self._running = False

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
        # Condensation Prevention
        c_cfg = self.config.condensation
        if c_cfg.enabled:
            self.automations.append(
                CondensationPreventionAutomation(
                    glazing=c_cfg.glazing,
                    default_indoor_temp_c=c_cfg.default_indoor_temp_c,
                    min_target_rh=c_cfg.min_target_rh,
                    max_target_rh=c_cfg.max_target_rh,
                    safety_margin_c=c_cfg.safety_margin_c,
                    target_dew_point_c=c_cfg.target_dew_point_c,
                    rh_deadband=c_cfg.rh_deadband,
                )
            )

        # Quiet Hours Schedule
        s_cfg = self.config.quiet_schedule
        if s_cfg.enabled:
            self.automations.append(
                QuietScheduleAutomation(
                    start_time=s_cfg.start_time,
                    end_time=s_cfg.end_time,
                    rooms=s_cfg.rooms,
                    night_mode=s_cfg.night_mode,
                    day_mode=s_cfg.day_mode,
                )
            )

    def evaluate_cycle(self) -> list[str]:
        """Poll telemetry across all devices and run registered automations."""
        # 1. Refresh devices
        for dev in self.registry.all_devices():
            dev.refresh()

        # 2. Run automations
        results: list[str] = []
        for auto in self.automations:
            logs = auto.evaluate(self.registry, self.event_bus)
            results.extend(logs)
        return results

    def start(self) -> None:
        """Start daemon loop with graceful signal handling."""
        self._running = True
        self._register_signals()

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

        logger.info("Smart Home System shut down cleanly.")

    def stop(self) -> None:
        self._running = False

    def _register_signals(self) -> None:
        def handle_signal(sig, frame):
            logger.info("Received termination signal (%s). Exiting...", sig)
            self.stop()

        signal.signal(signal.SIGINT, handle_signal)
        signal.signal(signal.SIGTERM, handle_signal)
