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
class ExclusionWindowConfig:
    label: str = "Exclusion Window"
    start_time: str = "00:00"
    end_time: str = "07:00"
    days: list[str] = field(
        default_factory=lambda: ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
    )
    rooms: list[str] | None = None
    enabled: bool = True

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "label": self.label,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "days": list(self.days),
            "enabled": self.enabled,
        }
        if self.rooms is not None:
            data["rooms"] = list(self.rooms)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExclusionWindowConfig:
        days_raw = data.get("days")
        if isinstance(days_raw, list):
            days = [str(d).lower() for d in days_raw]
        else:
            days = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

        rooms_raw = data.get("rooms")
        rooms = [str(r) for r in rooms_raw] if isinstance(rooms_raw, list) else None

        return cls(
            label=str(data.get("label", "Exclusion Window")),
            start_time=str(data.get("start_time", "00:00")),
            end_time=str(data.get("end_time", "07:00")),
            days=days,
            rooms=rooms,
            enabled=bool(data.get("enabled", True)),
        )


@dataclass
class CondensationAutomationConfig:
    enabled: bool = True
    glazing: GlazingType = GlazingType.DOUBLE
    default_indoor_temp_c: float = 20.0
    min_target_rh: int = 40
    max_target_rh: int = 60
    safety_margin_c: float = 1.5
    target_dew_point_c: float | None = None
    rh_deadband: int = 5
    lookahead_hours: int = 12
    auto_power: bool = True
    turn_on_offset_rh: float = 2.0
    turn_off_offset_rh: float = 2.0
    min_cycle_seconds: int = 600

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "glazing": self.glazing.value,
            "default_indoor_temp_c": self.default_indoor_temp_c,
            "min_target_rh": self.min_target_rh,
            "max_target_rh": self.max_target_rh,
            "safety_margin_c": self.safety_margin_c,
            "target_dew_point_c": self.target_dew_point_c,
            "rh_deadband": self.rh_deadband,
            "lookahead_hours": self.lookahead_hours,
            "auto_power": self.auto_power,
            "turn_on_offset_rh": self.turn_on_offset_rh,
            "turn_off_offset_rh": self.turn_off_offset_rh,
            "min_cycle_seconds": self.min_cycle_seconds,
        }


@dataclass
class QuietScheduleAutomationConfig:
    enabled: bool = True
    start_time: str = "23:00"
    end_time: str = "07:00"
    rooms: list[str] | None = None
    night_mode: str = "sleep"
    day_mode: str = "manual"
    night_days: list[str] = field(
        default_factory=lambda: ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
    )
    all_day_sleep_days: list[str] = field(default_factory=list)
    exclusion_windows: list[ExclusionWindowConfig] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "enabled": self.enabled,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "night_mode": self.night_mode,
            "day_mode": self.day_mode,
            "night_days": list(self.night_days),
            "all_day_sleep_days": list(self.all_day_sleep_days),
            "exclusion_windows": [w.to_dict() for w in self.exclusion_windows],
        }
        if self.rooms is not None:
            data["rooms"] = list(self.rooms)
        return data


@dataclass
class WebServerConfig:
    enabled: bool = True
    host: str = "0.0.0.0"
    port: int = 8765

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "host": self.host,
            "port": self.port,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WebServerConfig:
        return cls(
            enabled=bool(data.get("enabled", True)),
            host=str(data.get("host", "0.0.0.0")),
            port=int(data.get("port", 8765)),
        )


@dataclass
class SmartHomeConfig:
    location: LocationConfig = field(default_factory=LocationConfig)
    tuya_devices: list[dict[str, Any]] = field(default_factory=list)
    ble_devices: list[dict[str, Any]] = field(default_factory=list)
    condensation: CondensationAutomationConfig = field(default_factory=CondensationAutomationConfig)
    quiet_schedule: QuietScheduleAutomationConfig = field(
        default_factory=QuietScheduleAutomationConfig
    )
    web: WebServerConfig = field(default_factory=WebServerConfig)
    polling_interval_seconds: int = 60
    raw_path: Path | None = None

    def to_dict(self) -> dict[str, Any]:
        all_devices: list[dict[str, Any]] = []
        for d in self.tuya_devices:
            entry = dict(d)
            entry["type"] = "tuya"
            all_devices.append(entry)
        for d in self.ble_devices:
            entry = dict(d)
            entry.setdefault("type", "thermopro_ble")
            all_devices.append(entry)

        return {
            "devices": all_devices,
            "location": {
                "latitude": self.location.latitude,
                "longitude": self.location.longitude,
                "city": self.location.city,
            },
            "condensation": self.condensation.to_dict(),
            "quiet_schedule": self.quiet_schedule.to_dict(),
            "web": self.web.to_dict(),
            "polling_interval_seconds": self.polling_interval_seconds,
        }

    def save(self, path: str | Path | None = None) -> None:
        target = Path(path) if path else self.raw_path
        if not target:
            raise ValueError("No file path specified to save SmartHomeConfig.")

        target = target.resolve()
        temp_target = target.with_suffix(f"{target.suffix}.tmp")
        payload = self.to_dict()
        with open(temp_target, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=4)
            f.write("\n")
        temp_target.replace(target)
        self.raw_path = target

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SmartHomeConfig:
        # Location
        loc_data = data.get("location", {})
        location = LocationConfig(
            latitude=float(loc_data.get("latitude", 0.0)),
            longitude=float(loc_data.get("longitude", 0.0)),
            city=str(loc_data.get("city", "Unknown")),
        )

        # Devices (Tuya and BLE)
        tuya_devices = []
        ble_devices = []
        if "device" in data:
            # Single device format compatibility
            dev = dict(data["device"])
            dev.setdefault("room", "living_room")
            dev.setdefault("name", "Meaco Arete Two")
            tuya_devices.append(dev)
        if "devices" in data and isinstance(data["devices"], list):
            for d in data["devices"]:
                dev_type = d.get("type", "tuya")
                if dev_type == "tuya":
                    tuya_devices.append(d)
                elif dev_type in ("thermopro_ble", "ble"):
                    ble_devices.append(d)

        # Allow explicit top-level ble_devices list as well
        if "ble_devices" in data and isinstance(data["ble_devices"], list):
            ble_devices.extend(data["ble_devices"])

        # Condensation (canonical keys first, legacy aliases as fallback)
        cond_data = data.get("condensation", data.get("condensation_prevention", {}))
        glazing_str = cond_data.get("glazing", "double").lower()
        try:
            glazing = GlazingType(glazing_str)
        except ValueError:
            glazing = GlazingType.DOUBLE

        target_dew_point_raw = cond_data.get("target_dew_point_c")
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
            target_dew_point_c=(
                float(target_dew_point_raw) if target_dew_point_raw is not None else None
            ),
            rh_deadband=int(cond_data.get("rh_deadband", 5)),
            lookahead_hours=max(0, int(cond_data.get("lookahead_hours", 12))),
            auto_power=bool(cond_data.get("auto_power", True)),
            turn_on_offset_rh=float(cond_data.get("turn_on_offset_rh", 2.0)),
            turn_off_offset_rh=float(cond_data.get("turn_off_offset_rh", 2.0)),
            min_cycle_seconds=int(cond_data.get("min_cycle_seconds", 600)),
        )

        # Quiet Schedule (canonical key first, legacy alias as fallback)
        sched_data = data.get("quiet_schedule", data.get("night_schedule", {}))
        night_days_raw = sched_data.get("night_days")
        if isinstance(night_days_raw, list):
            night_days = [str(d).lower() for d in night_days_raw]
        else:
            night_days = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

        all_day_sleep_days_raw = sched_data.get("all_day_sleep_days", [])
        if isinstance(all_day_sleep_days_raw, list):
            all_day_sleep_days = [str(d).lower() for d in all_day_sleep_days_raw]
        else:
            all_day_sleep_days = []

        raw_exclusions = sched_data.get("exclusion_windows", [])
        exclusion_windows: list[ExclusionWindowConfig] = []
        if isinstance(raw_exclusions, list):
            for item in raw_exclusions:
                if isinstance(item, dict):
                    exclusion_windows.append(ExclusionWindowConfig.from_dict(item))

        quiet_schedule = QuietScheduleAutomationConfig(
            enabled=bool(sched_data.get("enabled", True)),
            start_time=str(sched_data.get("start_time", "23:00")),
            end_time=str(sched_data.get("end_time", "07:00")),
            rooms=sched_data.get("rooms"),
            night_mode=str(sched_data.get("night_mode", "sleep")),
            day_mode=str(sched_data.get("day_mode", "manual")),
            night_days=night_days,
            all_day_sleep_days=all_day_sleep_days,
            exclusion_windows=exclusion_windows,
        )

        # Web server config
        web_data = data.get("web", {})
        web = WebServerConfig.from_dict(web_data)

        return cls(
            location=location,
            tuya_devices=tuya_devices,
            ble_devices=ble_devices,
            condensation=condensation,
            quiet_schedule=quiet_schedule,
            web=web,
            polling_interval_seconds=int(data.get("polling_interval_seconds", 60)),
        )

    @classmethod
    def from_file(cls, path: str | Path) -> SmartHomeConfig:
        p = Path(path).resolve()
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
        cfg = cls.from_dict(data)
        cfg.raw_path = p
        return cfg
