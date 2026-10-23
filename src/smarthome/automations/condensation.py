"""
Multi-room condensation prevention automation.
Reads indoor and outdoor conditions and adjusts dehumidifier target humidity so
the indoor dew point stays below the window glass temperature, or below a fixed
target dew point. Also supports sensor-driven automatic power control (with hysteresis
and compressor protection cooldown) and exclusion window coordination.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Any, Callable, NamedTuple

from smarthome.automations.base import Automation
from smarthome.core.device import Device
from smarthome.core.events import EventBus
from smarthome.core.registry import DeviceRegistry
from smarthome.core.traits import (
    HumidityControlTrait,
    HumiditySensorTrait,
    OnOffTrait,
    TankLevelTrait,
    TemperatureForecastTrait,
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
    the dehumidifier target humidity so the indoor air stays below it. Can also
    drive dehumidifier power (turn ON/OFF) using the room's external climate sensor,
    hysteresis offsets, and minimum compressor cycle protection.
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
        lookahead_hours: int = 12,
        auto_power: bool = True,
        turn_on_offset_rh: float = 2.0,
        turn_off_offset_rh: float = 2.0,
        min_cycle_seconds: int = 600,
        exclusion_checker: Callable[[str, datetime | None], tuple[bool, Any]] | None = None,
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
        self.lookahead_hours = lookahead_hours
        self.auto_power = auto_power
        self.turn_on_offset_rh = turn_on_offset_rh
        self.turn_off_offset_rh = turn_off_offset_rh
        self.min_cycle_seconds = min_cycle_seconds
        self.exclusion_checker = exclusion_checker
        self._last_power_change: dict[str, float] = {}

    def compute_room_status(
        self,
        registry: DeviceRegistry,
        room: str,
        dehum_dev: Device,
        current_dt: datetime | None = None,
    ) -> dict[str, Any]:
        """
        Inspect live psychrometrics and setpoint calculation for a room
        without modifying hardware or device state.
        """
        climate = self._get_room_climate(registry, room, dehum_dev)
        indoor_temp = climate.temp_c
        indoor_rh = climate.rh

        effective_outdoor, current_outdoor, forecast_min = self._resolve_outdoor_temperature(
            registry
        )

        dew_point = calculate_dew_point(indoor_temp, indoor_rh) if indoor_rh is not None else None

        safe_dew_point: float | None = None
        raw_safe_rh: float | None = None
        safe_target_rh: int | None = None

        if self.target_dew_point_c is not None:
            safe_dew_point = self.target_dew_point_c
        elif effective_outdoor is not None:
            safe_dew_point = resolve_safe_dew_point(
                indoor_temp, effective_outdoor, self.glazing, self.safety_margin_c
            )

        if safe_dew_point is not None:
            raw_safe_rh = calculate_rh_for_dew_point(indoor_temp, safe_dew_point)
            control_trait = dehum_dev.get_trait(HumidityControlTrait)
            dev_min, dev_max = (
                control_trait.humidity_range
                if control_trait
                else (self.min_target_rh, self.max_target_rh)
            )
            step = control_trait.humidity_step if control_trait else 5
            low = max(self.min_target_rh, dev_min)
            high = min(self.max_target_rh, dev_max)
            if low <= high:
                safe_target_rh = quantize_rh(raw_safe_rh, step, low, high)

        is_excluded = False
        exclusion_label = None
        if self.exclusion_checker:
            is_excluded, ex_obj = self.exclusion_checker(room, current_dt)
            if is_excluded and ex_obj:
                exclusion_label = getattr(ex_obj, "label", "Exclusion")

        now_ts = current_dt.timestamp() if current_dt else time.time()
        last_change = self._last_power_change.get(dehum_dev.id, 0.0)
        cooldown_left = max(0.0, self.min_cycle_seconds - (now_ts - last_change))

        target_base = safe_target_rh or 55
        turn_on_rh = target_base + self.turn_on_offset_rh
        turn_off_rh = target_base - self.turn_off_offset_rh

        return {
            "indoor_temp_c": indoor_temp,
            "indoor_rh_percent": indoor_rh,
            "temp_assumed": climate.temp_assumed,
            "rh_from_builtin": climate.rh_from_builtin,
            "outdoor_temp_c": current_outdoor,
            "outdoor_forecast_min_c": forecast_min,
            "effective_outdoor_c": effective_outdoor,
            "dew_point_c": dew_point,
            "safe_dew_point_c": safe_dew_point,
            "raw_safe_rh_percent": raw_safe_rh,
            "safe_target_rh": safe_target_rh,
            "turn_on_threshold_rh": turn_on_rh,
            "turn_off_threshold_rh": turn_off_rh,
            "is_excluded": is_excluded,
            "exclusion_label": exclusion_label,
            "cooldown_remaining_seconds": cooldown_left,
        }

    def evaluate(
        self,
        registry: DeviceRegistry,
        event_bus: EventBus,
        current_dt: datetime | None = None,
    ) -> list[str]:
        if not self.enabled:
            return ["Condensation automation is disabled."]

        logs: list[str] = []

        # 1. Outdoor temperature is only needed in window mode.
        outdoor_temp: float | None = None
        source_desc: str = ""
        if self.target_dew_point_c is None:
            effective_outdoor, current_outdoor, forecast_min = self._resolve_outdoor_temperature(
                registry
            )
            if effective_outdoor is None:
                logs.append(
                    "No outdoor temperature sensor available. Set 'target_dew_point_c' "
                    "or add an outdoor sensor. Condensation check skipped."
                )
                return logs
            outdoor_temp = effective_outdoor
            if (
                current_outdoor is not None
                and forecast_min is not None
                and self.lookahead_hours > 0
            ):
                source_desc = (
                    f"window Out={current_outdoor:.1f}°C, "
                    f"{self.lookahead_hours}hMin={forecast_min:.1f}°C"
                )
            elif current_outdoor is not None:
                source_desc = f"window Out={current_outdoor:.1f}°C"
            else:
                source_desc = f"window Out={outdoor_temp:.1f}°C"

        # 2. Iterate across all rooms that contain a dehumidifier.
        dehumidifiers = registry.find_devices_with_trait(HumidityControlTrait)
        if not dehumidifiers:
            logs.append("No dehumidifier devices registered.")
            return logs

        now_ts = current_dt.timestamp() if current_dt else time.time()

        for dehum_dev in dehumidifiers:
            room = dehum_dev.room
            control_trait = dehum_dev.require_trait(HumidityControlTrait)

            # Check exclusion window first
            is_excluded = False
            ex_label = ""
            if self.exclusion_checker:
                is_excluded, ex_obj = self.exclusion_checker(room, current_dt)
                if is_excluded:
                    ex_label = getattr(ex_obj, "label", "Exclusion")

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
                source = source_desc

            # 4. Convert to a humidity target, clamp to bounds, snap to step
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

            if is_excluded:
                log_entry += f" [EXCLUDED: '{ex_label}' - power blocked]"
                logs.append(log_entry)
                continue

            # 5. Target setpoint adjustment (with deadband)
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

            # 6. Sensor-driven Auto Power Control
            on_off = dehum_dev.get_trait(OnOffTrait)
            if self.auto_power and on_off:
                turn_on_threshold = safe_target_rh + self.turn_on_offset_rh
                turn_off_threshold = safe_target_rh - self.turn_off_offset_rh

                last_change = self._last_power_change.get(dehum_dev.id, 0.0)
                elapsed = now_ts - last_change
                cooldown_ready = elapsed >= self.min_cycle_seconds

                if not on_off.is_on and indoor_rh >= turn_on_threshold:
                    if cooldown_ready:
                        if on_off.turn_on():
                            self._last_power_change[dehum_dev.id] = now_ts
                            log_entry += (
                                f" [ACTION: Auto Turned ON (RH {indoor_rh:.0f}% >= "
                                f"{turn_on_threshold:.1f}%)]"
                            )
                        else:
                            log_entry += f" [ERROR: Failed to turn ON {dehum_dev.name}]"
                    else:
                        cooldown_rem = int(self.min_cycle_seconds - elapsed)
                        log_entry += f" [turn-on pending: cooldown {cooldown_rem}s]"

                elif on_off.is_on and indoor_rh <= turn_off_threshold:
                    if cooldown_ready:
                        if on_off.turn_off():
                            self._last_power_change[dehum_dev.id] = now_ts
                            log_entry += (
                                f" [ACTION: Auto Turned OFF (RH {indoor_rh:.0f}% <= "
                                f"{turn_off_threshold:.1f}%)]"
                            )
                        else:
                            log_entry += f" [ERROR: Failed to turn OFF {dehum_dev.name}]"
                    else:
                        cooldown_rem = int(self.min_cycle_seconds - elapsed)
                        log_entry += f" [turn-off pending: cooldown {cooldown_rem}s]"

            if indoor_rh > raw_safe_rh:
                log_entry += " [CONDENSATION RISK ACTIVE]"

            logs.append(log_entry)

        return logs

    def _resolve_outdoor_temperature(
        self, registry: DeviceRegistry
    ) -> tuple[float | None, float | None, float | None]:
        outdoor_devices = registry.get_by_room(self.outdoor_room)
        current_temp: float | None = None
        forecast_min: float | None = None

        for dev in outdoor_devices:
            if current_temp is None:
                sensor = dev.get_trait(TemperatureSensorTrait)
                if sensor and sensor.temperature_celsius is not None:
                    current_temp = sensor.temperature_celsius

            if self.lookahead_hours > 0 and forecast_min is None:
                forecaster = dev.get_trait(TemperatureForecastTrait)
                if forecaster:
                    forecast_min = forecaster.min_forecast_temperature(self.lookahead_hours)

        effective_temp: float | None
        if current_temp is not None and forecast_min is not None:
            effective_temp = min(current_temp, forecast_min)
        elif current_temp is not None:
            effective_temp = current_temp
        else:
            effective_temp = forecast_min

        return effective_temp, current_temp, forecast_min

    def _get_outdoor_temperature(self, registry: DeviceRegistry) -> float | None:
        effective, _, _ = self._resolve_outdoor_temperature(registry)
        return effective

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
