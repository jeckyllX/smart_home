"""
Multi-room condensation prevention automation.
Reads indoor and outdoor conditions and adjusts dehumidifier target humidity so
the indoor dew point stays below the window glass temperature, or below a fixed
target dew point.
"""

from __future__ import annotations

import logging
from typing import NamedTuple

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
    calculate_dew_point,
    calculate_rh_for_dew_point,
    quantize_rh,
    resolve_safe_dew_point,
)

logger = logging.getLogger("CondensationAutomation")


class _RoomClimate(NamedTuple):
    temp_c: float
    rh: float | None
    temp_assumed: bool
    rh_from_builtin: bool


class CondensationPreventionAutomation(Automation):
    """
    Room-aware condensation prevention policy.

    For each room with a dehumidifier, resolves a safe indoor dew point and sets
    the dehumidifier target humidity so the indoor air stays below it. The safe
    dew point is either the configured ``target_dew_point_c`` (fixed mode) or the
    estimated interior glass temperature minus ``safety_margin_c`` (window mode,
    which needs an outdoor temperature).
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
        target_dew_point_c: float | None = None,
        rh_deadband: int = 5,
    ):
        super().__init__(name=name, enabled=enabled)
        self.outdoor_room = outdoor_room
        self.default_indoor_temp = default_indoor_temp_c
        self.glazing = glazing
        self.min_target_rh = min_target_rh
        self.max_target_rh = max_target_rh
        self.safety_margin_c = safety_margin_c
        self.target_dew_point_c = target_dew_point_c
        self.rh_deadband = rh_deadband

    def evaluate(self, registry: DeviceRegistry, event_bus: EventBus) -> list[str]:
        if not self.enabled:
            return ["Condensation automation is disabled."]

        logs: list[str] = []

        # 1. Outdoor temperature is only needed in window mode.
        outdoor_temp: float | None = None
        if self.target_dew_point_c is None:
            outdoor_temp = self._get_outdoor_temperature(registry)
            if outdoor_temp is None:
                logs.append(
                    "No outdoor temperature sensor available. Set 'target_dew_point_c' "
                    "or add an outdoor sensor. Condensation check skipped."
                )
                return logs

        # 2. Iterate across all rooms that contain a dehumidifier.
        dehumidifiers = registry.find_devices_with_trait(HumidityControlTrait)
        if not dehumidifiers:
            logs.append("No dehumidifier devices registered.")
            return logs

        for dehum_dev in dehumidifiers:
            room = dehum_dev.room
            control_trait = dehum_dev.require_trait(HumidityControlTrait)

            tank_trait = dehum_dev.get_trait(TankLevelTrait)
            if tank_trait and tank_trait.is_tank_full:
                logs.append(f"Room '{room}': {dehum_dev.name} tank is full. Skipping adjustment.")
                continue

            climate = self._get_room_climate(registry, room, dehum_dev)
            if climate.rh is None:
                logs.append(f"Room '{room}': No indoor humidity telemetry available.")
                continue
            indoor_temp = climate.temp_c
            indoor_rh = climate.rh

            # 3. Resolve the safe dew point for the active mode.
            if self.target_dew_point_c is not None:
                safe_dew_point = self.target_dew_point_c
                source = f"fixed {safe_dew_point:.1f}°C"
            else:
                assert outdoor_temp is not None
                safe_dew_point = resolve_safe_dew_point(
                    indoor_temp, outdoor_temp, self.glazing, self.safety_margin_c
                )
                source = f"window Out={outdoor_temp:.1f}°C"

            # 4. Convert to a humidity target, clamp to the overlap of the configured
            #    bounds and the device range, then snap to the device step.
            raw_safe_rh = calculate_rh_for_dew_point(indoor_temp, safe_dew_point)
            dev_min, dev_max = control_trait.humidity_range
            step = control_trait.humidity_step
            low = max(self.min_target_rh, dev_min)
            high = min(self.max_target_rh, dev_max)
            if low > high:
                logs.append(
                    f"Room '{room}': configured target bounds "
                    f"[{self.min_target_rh}, {self.max_target_rh}] do not overlap the "
                    f"device range ({dev_min}, {dev_max}). Skipping adjustment."
                )
                continue
            safe_target_rh = quantize_rh(raw_safe_rh, step, low, high)

            current_target = control_trait.target_humidity_percent
            indoor_dew_point = calculate_dew_point(indoor_temp, indoor_rh)

            log_entry = (
                f"Room '{room}' ({dehum_dev.name}): In={indoor_temp:.1f}°C/{indoor_rh:.0f}%RH, "
                f"SafeDewPoint={safe_dew_point:.1f}°C [{source}], "
                f"DewPoint={indoor_dew_point:.1f}°C, "
                f"SafeRH={raw_safe_rh:.1f}% -> Target={safe_target_rh}% "
                f"(device {dev_min}-{dev_max} step {step}, CurrentTarget={current_target}%)"
            )

            if climate.temp_assumed:
                log_entry += f" [indoor temp assumed {self.default_indoor_temp:.1f}°C]"
            if climate.rh_from_builtin:
                log_entry += " [humidity from built-in sensor, reads high]"

            # 5. Write only when the move exceeds the deadband, so a value near a step
            #    boundary does not flip back and forth between two targets.
            within_deadband = (
                current_target is not None and abs(raw_safe_rh - current_target) < self.rh_deadband
            )
            if within_deadband:
                log_entry += f" [within deadband {self.rh_deadband}%]"
            elif safe_target_rh != current_target:
                success = control_trait.set_target_humidity(safe_target_rh)
                if success:
                    log_entry += f" [ACTION: Set target to {safe_target_rh}%]"
                else:
                    log_entry += f" [ERROR: Failed to update target on {dehum_dev.name}]"
            else:
                log_entry += " [no change]"

            if indoor_rh > raw_safe_rh:
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
    ) -> _RoomClimate:
        room_temps: list[float] = []
        room_rhs: list[float] = []

        # Prefer dedicated climate sensors in the room over the dehumidifier's own.
        for dev in registry.get_by_room(room):
            if dev.id == fallback_dehumidifier.id:
                continue
            t_trait = dev.get_trait(TemperatureSensorTrait)
            h_trait = dev.get_trait(HumiditySensorTrait)
            if t_trait and t_trait.temperature_celsius is not None:
                room_temps.append(t_trait.temperature_celsius)
            if h_trait and h_trait.humidity_percent is not None:
                room_rhs.append(h_trait.humidity_percent)

        if room_temps:
            temp = min(room_temps)
            temp_assumed = False
        else:
            temp = self.default_indoor_temp
            temp_assumed = True

        if room_rhs:
            rh = max(room_rhs)
            rh_from_builtin = False
        else:
            # Fall back to the dehumidifier's built-in sensor.
            h_trait = fallback_dehumidifier.get_trait(HumiditySensorTrait)
            if h_trait and h_trait.humidity_percent is not None:
                rh = h_trait.humidity_percent
                rh_from_builtin = True
            else:
                rh = None
                rh_from_builtin = False

        return _RoomClimate(temp, rh, temp_assumed, rh_from_builtin)
