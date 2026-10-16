"""
Time-based profile and quiet hours automation.
Applies sleep or quiet operational modes to devices in designated rooms during the night.
"""

from __future__ import annotations

import logging
from datetime import datetime
from datetime import time as dtime

from smarthome.automations.base import Automation
from smarthome.core.events import EventBus
from smarthome.core.registry import DeviceRegistry
from smarthome.core.traits import ModeControlTrait

logger = logging.getLogger("QuietScheduleAutomation")


class QuietScheduleAutomation(Automation):
    """
    Switches devices in the configured rooms to a night mode during the quiet
    window, and back to the day mode outside it.
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
    ):
        super().__init__(name=name, enabled=enabled)
        self.start_time = start_time
        self.end_time = end_time
        self.rooms = rooms  # None means all rooms
        self.night_mode = night_mode
        self.day_mode = day_mode

    def evaluate(
        self, registry: DeviceRegistry, event_bus: EventBus, current_dt: datetime | None = None
    ) -> list[str]:
        if not self.enabled:
            return ["Quiet hours automation is disabled."]

        now = current_dt or datetime.now()
        is_night = self._is_in_window(self.start_time, self.end_time, now.time())
        target_mode = self.night_mode if is_night else self.day_mode

        logs: list[str] = []
        mode_devices = registry.find_devices_with_trait(ModeControlTrait)

        for dev in mode_devices:
            if self.rooms and dev.room.lower() not in [r.lower() for r in self.rooms]:
                continue

            trait = dev.require_trait(ModeControlTrait)
            if target_mode not in trait.supported_modes:
                continue

            if trait.current_mode != target_mode:
                success = trait.set_mode(target_mode)
                state_str = "Night" if is_night else "Day"
                if success:
                    logs.append(
                        f"Room '{dev.room}': {dev.name} switched to '{target_mode}' "
                        f"({state_str} profile)."
                    )
                else:
                    logs.append(
                        f"Room '{dev.room}': Failed to switch {dev.name} to '{target_mode}'."
                    )

        if not logs:
            logs.append(
                f"Quiet hours evaluated (Active={'Night' if is_night else 'Day'}, "
                "all profiles in sync)."
            )

        return logs

    @staticmethod
    def _is_in_window(start_str: str, end_str: str, current: dtime) -> bool:
        start = datetime.strptime(start_str, "%H:%M").time()
        end = datetime.strptime(end_str, "%H:%M").time()
        if start <= end:
            return start <= current <= end
        return current >= start or current <= end
