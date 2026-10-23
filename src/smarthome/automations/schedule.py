"""
Time-based profile and quiet hours automation.
Applies sleep or quiet operational modes to devices in designated rooms during the night,
and enforces active exclusion windows.
"""

from __future__ import annotations

import logging
from datetime import datetime
from datetime import time as dtime

from smarthome.automations.base import Automation
from smarthome.config.schema import ExclusionWindowConfig
from smarthome.core.events import EventBus
from smarthome.core.registry import DeviceRegistry
from smarthome.core.traits import ModeControlTrait, OnOffTrait

logger = logging.getLogger("QuietScheduleAutomation")

WEEKDAY_NAMES = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


class QuietScheduleAutomation(Automation):
    """
    Switches devices in the configured rooms to a night mode during the quiet
    window, and back to the day mode outside it. Also enforces exclusion windows
    where devices are actively powered OFF.
    """

    def __init__(
        self,
        name: str = "QuietHours",
        enabled: bool = True,
        start_time: str = "23:00",
        end_time: str = "07:00",
        rooms: list[str] | None = None,
        night_mode: str = "sleep",
        day_mode: str = "manual",
        night_days: list[str] | None = None,
        all_day_sleep_days: list[str] | None = None,
        exclusion_windows: list[ExclusionWindowConfig] | None = None,
    ):
        super().__init__(name=name, enabled=enabled)
        self.start_time = start_time
        self.end_time = end_time
        self.rooms = rooms  # None means all rooms
        self.night_mode = night_mode
        self.day_mode = day_mode
        self.night_days = [d.lower() for d in (night_days or WEEKDAY_NAMES)]
        self.all_day_sleep_days = [d.lower() for d in (all_day_sleep_days or [])]
        self.exclusion_windows = list(exclusion_windows or [])

    def is_room_excluded(
        self, room: str, now: datetime | None = None
    ) -> tuple[bool, ExclusionWindowConfig | None]:
        """
        Check whether a room is currently inside an active exclusion window.
        """
        if not self.enabled:
            return False, None

        dt = now or datetime.now()
        weekday = WEEKDAY_NAMES[dt.weekday()]
        cur_time = dt.time()

        for window in self.exclusion_windows:
            if not window.enabled:
                continue
            if window.rooms and room.lower() not in [r.lower() for r in window.rooms]:
                continue
            if weekday not in [d.lower() for d in window.days]:
                continue
            if self._is_in_window(window.start_time, window.end_time, cur_time):
                return True, window

        return False, None

    def evaluate(
        self, registry: DeviceRegistry, event_bus: EventBus, current_dt: datetime | None = None
    ) -> list[str]:
        if not self.enabled:
            return ["Quiet hours automation is disabled."]

        now = current_dt or datetime.now()
        weekday = WEEKDAY_NAMES[now.weekday()]
        logs: list[str] = []

        # 1. Enforce active exclusion windows on OnOff devices
        power_devices = registry.find_devices_with_trait(OnOffTrait)
        for dev in power_devices:
            is_excluded, window = self.is_room_excluded(dev.room, now)
            if is_excluded and window is not None:
                on_off_trait = dev.require_trait(OnOffTrait)
                if on_off_trait.is_on:
                    success = on_off_trait.turn_off()
                    if success:
                        logs.append(
                            f"Room '{dev.room}': {dev.name} turned OFF "
                            f"(Exclusion '{window.label}' {window.start_time}-{window.end_time})."
                        )
                    else:
                        logs.append(
                            f"Room '{dev.room}': Failed to turn OFF {dev.name} for exclusion."
                        )

        # 2. Determine target operational mode
        if weekday in self.all_day_sleep_days:
            is_night = True
            profile_label = "All-Day Sleep"
        elif weekday in self.night_days and self._is_in_window(
            self.start_time, self.end_time, now.time()
        ):
            is_night = True
            profile_label = "Night"
        else:
            is_night = False
            profile_label = "Day"

        target_mode = self.night_mode if is_night else self.day_mode

        # 3. Synchronize operational mode
        mode_devices = registry.find_devices_with_trait(ModeControlTrait)
        for dev in mode_devices:
            if self.rooms and dev.room.lower() not in [r.lower() for r in self.rooms]:
                continue

            mode_trait = dev.require_trait(ModeControlTrait)
            if target_mode not in mode_trait.supported_modes:
                continue

            if mode_trait.current_mode != target_mode:
                success = mode_trait.set_mode(target_mode)
                if success:
                    logs.append(
                        f"Room '{dev.room}': {dev.name} switched to '{target_mode}' "
                        f"({profile_label} profile)."
                    )
                else:
                    logs.append(
                        f"Room '{dev.room}': Failed to switch {dev.name} to '{target_mode}'."
                    )

        if not logs:
            logs.append(f"Quiet hours evaluated (Active={profile_label}, all profiles in sync).")

        return logs

    @staticmethod
    def _is_in_window(start_str: str, end_str: str, current: dtime) -> bool:
        start = datetime.strptime(start_str, "%H:%M").time()
        end = datetime.strptime(end_str, "%H:%M").time()
        if start <= end:
            return start <= current <= end
        return current >= start or current <= end
