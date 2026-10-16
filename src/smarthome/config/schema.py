"""
Typed configuration schemas and loader for Smart Home platform.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from smarthome.physics.psychrometrics import GlazingType


@dataclass
class LocationConfig:
    latitude: float = 0.0
    longitude: float = 0.0
    city: str = "Unknown"


@dataclass
class CondensationAutomationConfig:
    enabled: bool = True
    glazing: GlazingType = GlazingType.DOUBLE
    default_indoor_temp_c: float = 20.0
    min_target_rh: int = 40
    max_target_rh: int = 60
    safety_margin_c: float = 1.5


@dataclass
class QuietScheduleAutomationConfig:
    enabled: bool = True
    start_time: str = "23:00"
    end_time: str = "07:00"
    rooms: list[str] | None = None
    night_mode: str = "sleep"
    day_mode: str = "manual"


@dataclass
class SmartHomeConfig:
    location: LocationConfig = field(default_factory=LocationConfig)
    tuya_devices: list[dict[str, Any]] = field(default_factory=list)
    condensation: CondensationAutomationConfig = field(default_factory=CondensationAutomationConfig)
    quiet_schedule: QuietScheduleAutomationConfig = field(
        default_factory=QuietScheduleAutomationConfig
    )
    polling_interval_seconds: int = 60

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SmartHomeConfig:
        # Location
        loc_data = data.get("location", {})
        location = LocationConfig(
            latitude=float(loc_data.get("latitude", 0.0)),
            longitude=float(loc_data.get("longitude", 0.0)),
            city=str(loc_data.get("city", "Unknown")),
        )

        # Tuya Devices
        tuya_devices = []
        if "device" in data:
            # Single device format compatibility
            dev = dict(data["device"])
            dev.setdefault("room", "living_room")
            dev.setdefault("name", "Meaco Arete Two")
            tuya_devices.append(dev)
        elif "devices" in data:
            for d in data["devices"]:
                if d.get("type", "tuya") == "tuya":
                    tuya_devices.append(d)

        # Condensation (canonical keys first, legacy aliases as fallback)
        cond_data = data.get("condensation", data.get("condensation_prevention", {}))
        glazing_str = cond_data.get("glazing", "double").lower()
        try:
            glazing = GlazingType(glazing_str)
        except ValueError:
            glazing = GlazingType.DOUBLE

        condensation = CondensationAutomationConfig(
            enabled=bool(cond_data.get("enabled", True)),
            glazing=glazing,
            default_indoor_temp_c=float(
                cond_data.get(
                    "default_indoor_temp_c",
                    cond_data.get("estimated_indoor_temp_c", 20.0),
                )
            ),
            min_target_rh=int(cond_data.get("min_target_rh", 40)),
            max_target_rh=int(cond_data.get("max_target_rh", 60)),
            safety_margin_c=float(cond_data.get("safety_margin_c", 1.5)),
        )

        # Quiet Schedule (canonical key first, legacy alias as fallback)
        sched_data = data.get("quiet_schedule", data.get("night_schedule", {}))
        quiet_schedule = QuietScheduleAutomationConfig(
            enabled=bool(sched_data.get("enabled", True)),
            start_time=str(sched_data.get("start_time", "23:00")),
            end_time=str(sched_data.get("end_time", "07:00")),
            rooms=sched_data.get("rooms"),
            night_mode=str(sched_data.get("night_mode", "sleep")),
            day_mode=str(sched_data.get("day_mode", "manual")),
        )

        return cls(
            location=location,
            tuya_devices=tuya_devices,
            condensation=condensation,
            quiet_schedule=quiet_schedule,
            polling_interval_seconds=int(data.get("polling_interval_seconds", 60)),
        )

    @classmethod
    def from_file(cls, path: str | Path) -> SmartHomeConfig:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data)
