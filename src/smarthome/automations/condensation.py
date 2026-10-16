"""
Multi-room condensation prevention automation.
Reads indoor and outdoor conditions and adjusts dehumidifier target humidity so
the indoor dew point stays below the window glass temperature.
"""

from __future__ import annotations

import logging

from smarthome.automations.base import Automation
from smarthome.core.device import Device
from smarthome.core.events import EventBus
from smarthome.core.registry import DeviceRegistry
from smarthome.core.traits import (
    HumidityControlTrait,
    HumiditySensorTrait,
    TankLevelTrait,
    TemperatureSensorTrait,
)
from smarthome.physics.psychrometrics import (
    GlazingType,
    calculate_condensation_safe_rh,
    calculate_dew_point,
    estimate_interior_glass_temp,
)

logger = logging.getLogger("CondensationAutomation")


class CondensationPreventionAutomation(Automation):
    """
    Room-aware condensation prevention policy.
    Reads each room's climate sensors and dehumidifier, estimates the window glass
    temperature from the outdoor temperature and glazing type, and sets the
    dehumidifier target humidity to a safe value.
    """

    def __init__(
        self,
        name: str = "CondensationPrevention",
        enabled: bool = True,
        outdoor_room: str = "outdoor",
        default_indoor_temp_c: float = 20.0,
        glazing: GlazingType = GlazingType.DOUBLE,
        min_target_rh: int = 40,
        max_target_rh: int = 60,
        safety_margin_c: float = 1.5,
    ):
        super().__init__(name=name, enabled=enabled)
        self.outdoor_room = outdoor_room
        self.default_indoor_temp = default_indoor_temp_c
        self.glazing = glazing
        self.min_target_rh = min_target_rh
        self.max_target_rh = max_target_rh
        self.safety_margin_c = safety_margin_c

    def evaluate(self, registry: DeviceRegistry, event_bus: EventBus) -> list[str]:
        if not self.enabled:
            return ["Condensation automation is disabled."]

        logs: list[str] = []

        # 1. Resolve Outdoor Temperature
        outdoor_temp = self._get_outdoor_temperature(registry)
        if outdoor_temp is None:
            logs.append("No outdoor temperature sensor available. Condensation check skipped.")
            return logs

        # 2. Iterate across all rooms that contain a dehumidifier (HumidityControlTrait)
        dehumidifiers = registry.find_devices_with_trait(HumidityControlTrait)
        if not dehumidifiers:
            logs.append("No dehumidifier devices registered.")
            return logs

        for dehum_dev in dehumidifiers:
            room = dehum_dev.room
            control_trait = dehum_dev.require_trait(HumidityControlTrait)

            # Check if tank full
            tank_trait = dehum_dev.get_trait(TankLevelTrait)
            if tank_trait and tank_trait.is_tank_full:
                logs.append(f"Room '{room}': {dehum_dev.name} tank is full. Skipping adjustment.")
                continue

            # 3. Resolve indoor temperature and humidity for this room
            indoor_temp, indoor_rh = self._get_room_climate(registry, room, dehum_dev)
            if indoor_rh is None:
                logs.append(f"Room '{room}': No indoor humidity telemetry available.")
                continue

            # 4. Psychrometric calculations
            glass_temp = estimate_interior_glass_temp(indoor_temp, outdoor_temp, self.glazing)
            safe_target_rh = calculate_condensation_safe_rh(
                indoor_temp_c=indoor_temp,
                outdoor_temp_c=outdoor_temp,
                glazing=self.glazing,
                safety_margin_c=self.safety_margin_c,
                min_rh=self.min_target_rh,
                max_rh=self.max_target_rh,
            )
            dew_point = calculate_dew_point(indoor_temp, indoor_rh)

            is_at_risk = indoor_rh > safe_target_rh
            current_target = control_trait.target_humidity_percent

            log_entry = (
                f"Room '{room}' ({dehum_dev.name}): In={indoor_temp:.1f}°C/{indoor_rh:.0f}%RH, "
                f"Out={outdoor_temp:.1f}°C, Glass={glass_temp:.1f}°C, "
                f"DewPoint={dew_point:.1f}°C -> "
                f"SafeTarget={safe_target_rh}% (CurrentTarget={current_target}%)"
            )

            # 5. Apply adjustment if target has changed
            if current_target != safe_target_rh:
                success = control_trait.set_target_humidity(safe_target_rh)
                if success:
                    log_entry += f" [ACTION: Set target to {safe_target_rh}%]"
                else:
                    log_entry += f" [ERROR: Failed to update target on {dehum_dev.name}]"

            if is_at_risk:
                log_entry += " [CONDENSATION RISK ACTIVE]"

            logs.append(log_entry)

        return logs

    def _get_outdoor_temperature(self, registry: DeviceRegistry) -> float | None:
        outdoor_devices = registry.get_by_room(self.outdoor_room)
        for dev in outdoor_devices:
            sensor = dev.get_trait(TemperatureSensorTrait)
            if sensor and sensor.temperature_celsius is not None:
                return sensor.temperature_celsius
        return None

    def _get_room_climate(
        self, registry: DeviceRegistry, room: str, fallback_dehumidifier: Device
    ) -> tuple[float, float | None]:
        temp = self.default_indoor_temp
        rh: float | None = None

        # Check for dedicated climate sensors in the room first (e.g. BME280, Zigbee)
        room_devices = registry.get_by_room(room)
        for dev in room_devices:
            if dev.id == fallback_dehumidifier.id:
                continue
            t_trait = dev.get_trait(TemperatureSensorTrait)
            h_trait = dev.get_trait(HumiditySensorTrait)
            if t_trait and t_trait.temperature_celsius is not None:
                temp = t_trait.temperature_celsius
            if h_trait and h_trait.humidity_percent is not None:
                rh = h_trait.humidity_percent

        # Fallback to dehumidifier's built-in humidity sensor if room has no standalone sensor
        if rh is None:
            h_trait = fallback_dehumidifier.get_trait(HumiditySensorTrait)
            if h_trait:
                rh = h_trait.humidity_percent

        return temp, rh
