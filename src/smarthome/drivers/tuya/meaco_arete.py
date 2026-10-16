"""
Tuya LAN Driver for Meaco Arete Two dehumidifier.
Maps raw Tuya data points (DPs) to DehumidifierDevice traits.
"""

from __future__ import annotations

import logging
import threading
from typing import Any

import tinytuya

from smarthome.core.events import (
    CommandDispatchedEvent,
    DeviceStateChangedEvent,
    EventBus,
    TelemetryEvent,
)
from smarthome.core.registry import DeviceRegistry
from smarthome.devices.climate import DehumidifierDevice
from smarthome.drivers.base import Driver

logger = logging.getLogger("TuyaMeacoDriver")


class MeacoAreteTuyaDevice(DehumidifierDevice):
    """
    Concrete implementation of DehumidifierDevice for Meaco Arete Two.
    """

    DP_POWER = "1"
    DP_TARGET_HUMIDITY = "2"
    DP_MODE = "4"
    DP_CHILD_LOCK = "14"
    DP_CURRENT_HUMIDITY = "16"
    DP_OFF_TIMER = "17"
    DP_FAULT_CODE = "19"
    DP_ON_TIMER = "101"

    MODES = ["manual", "sleep", "laundry", "purify"]

    def __init__(
        self,
        device_id: str,
        name: str,
        ip: str,
        local_key: str,
        room: str = "living_room",
        version: float = 3.5,
        event_bus: EventBus | None = None,
    ):
        super().__init__(
            device_id=device_id,
            name=name,
            room=room,
            manufacturer="Meaco",
            model="Arete Two",
        )
        self.ip = ip
        self.local_key = local_key
        self.version = version
        self.event_bus = event_bus

        self._lock = threading.RLock()
        self._is_online = False
        self._cached_dps: dict[str, Any] = {}

        self._client = tinytuya.OutletDevice(
            dev_id=device_id,
            address=ip,
            local_key=local_key,
            version=version,
        )
        self._client.set_version(version)
        self._client.set_socketPersistent(False)
        self._client.set_socketTimeout(5.0)

    # --- Device Lifecycle ---

    @property
    def is_online(self) -> bool:
        return self._is_online

    def refresh(self) -> bool:
        with self._lock:
            try:
                status = self._client.status()
                if isinstance(status, dict) and "dps" in status:
                    new_dps = status["dps"]
                    self._is_online = True
                    self._dispatch_changes(self._cached_dps, new_dps)
                    self._cached_dps = new_dps
                    return True
                else:
                    self._is_online = False
                    logger.warning(
                        "Device '%s' returned invalid status payload: %s", self.name, status
                    )
                    return False
            except Exception as e:
                self._is_online = False
                logger.error("Error refreshing device '%s': %s", self.name, e)
                return False

    def _dispatch_changes(self, old_dps: dict[str, Any], new_dps: dict[str, Any]) -> None:
        if not self.event_bus:
            return

        # Power change
        if old_dps.get(self.DP_POWER) != new_dps.get(self.DP_POWER):
            self.event_bus.publish(
                DeviceStateChangedEvent(
                    device_id=self.id,
                    trait_name="OnOffTrait",
                    property_name="is_on",
                    old_value=old_dps.get(self.DP_POWER),
                    new_value=new_dps.get(self.DP_POWER),
                )
            )

        # Mode change
        if old_dps.get(self.DP_MODE) != new_dps.get(self.DP_MODE):
            self.event_bus.publish(
                DeviceStateChangedEvent(
                    device_id=self.id,
                    trait_name="ModeControlTrait",
                    property_name="current_mode",
                    old_value=old_dps.get(self.DP_MODE),
                    new_value=new_dps.get(self.DP_MODE),
                )
            )

        # Humidity Telemetry
        cur_rh = new_dps.get(self.DP_CURRENT_HUMIDITY)
        if cur_rh is not None and cur_rh != old_dps.get(self.DP_CURRENT_HUMIDITY):
            self.event_bus.publish(
                TelemetryEvent(
                    device_id=self.id,
                    metric="relative_humidity",
                    value=float(cur_rh),
                    unit="%",
                )
            )

    # --- OnOffTrait ---

    @property
    def is_on(self) -> bool:
        return bool(self._cached_dps.get(self.DP_POWER, False))

    def turn_on(self) -> bool:
        return self._send_command(self.DP_POWER, True, "turn_on")

    def turn_off(self) -> bool:
        return self._send_command(self.DP_POWER, False, "turn_off")

    # --- HumiditySensorTrait ---

    @property
    def humidity_percent(self) -> float | None:
        val = self._cached_dps.get(self.DP_CURRENT_HUMIDITY)
        return float(val) if val is not None else None

    # --- HumidityControlTrait ---

    @property
    def target_humidity_percent(self) -> int | None:
        val = self._cached_dps.get(self.DP_TARGET_HUMIDITY)
        return int(val) if val is not None else None

    @property
    def humidity_range(self) -> tuple[int, int]:
        return 30, 80

    def set_target_humidity(self, target_percent: int) -> bool:
        target_percent = max(30, min(80, int(target_percent)))
        return self._send_command(self.DP_TARGET_HUMIDITY, target_percent, "set_target_humidity")

    # --- ModeControlTrait ---

    @property
    def current_mode(self) -> str:
        return str(self._cached_dps.get(self.DP_MODE, "manual"))

    @property
    def supported_modes(self) -> list[str]:
        return list(self.MODES)

    def set_mode(self, mode: str) -> bool:
        mode_str = mode.lower()
        if mode_str not in self.MODES:
            raise ValueError(f"Mode '{mode}' not supported. Options: {self.MODES}")
        return self._send_command(self.DP_MODE, mode_str, "set_mode")

    # --- TankLevelTrait & FaultSensorTrait ---

    @property
    def is_tank_full(self) -> bool:
        fault_code = int(self._cached_dps.get(self.DP_FAULT_CODE, 0))
        return bool(fault_code & 128)

    @property
    def has_fault(self) -> bool:
        fault_code = int(self._cached_dps.get(self.DP_FAULT_CODE, 0))
        return fault_code != 0

    @property
    def fault_description(self) -> str | None:
        fault_code = int(self._cached_dps.get(self.DP_FAULT_CODE, 0))
        if fault_code == 0:
            return None
        if fault_code & 128:
            return "Water tank is full or removed"
        if fault_code & 4:
            return "Defrost cycle active"
        return f"Operational fault code {fault_code}"

    # --- Socket Command Helper ---

    def _send_command(self, dp: str, value: Any, cmd_name: str) -> bool:
        with self._lock:
            try:
                res = self._client.set_value(dp, value)
                success = res is not None and "Error" not in res
                if success:
                    self._cached_dps[dp] = value
                if self.event_bus:
                    self.event_bus.publish(
                        CommandDispatchedEvent(
                            device_id=self.id,
                            command=cmd_name,
                            arguments={"dp": dp, "value": value},
                            success=success,
                        )
                    )
                return success
            except Exception as e:
                logger.error("Failed to send command %s to device '%s': %s", cmd_name, self.name, e)
                return False


class TuyaDriver(Driver):
    """
    Driver managing discovery and lifecycle of Tuya LAN devices.
    """

    def __init__(self, devices_config: list[dict[str, Any]]):
        super().__init__(name="TuyaLANDriver")
        self._configs = devices_config
        self._devices: list[MeacoAreteTuyaDevice] = []

    def setup(self, registry: DeviceRegistry, event_bus: EventBus) -> bool:
        for cfg in self._configs:
            dev = MeacoAreteTuyaDevice(
                device_id=cfg["dev_id"],
                name=cfg.get("name", "Meaco Arete Two"),
                ip=cfg["ip"],
                local_key=cfg["local_key"],
                room=cfg.get("room", "living_room"),
                version=float(cfg.get("version", 3.5)),
                event_bus=event_bus,
            )
            # Perform initial poll
            dev.refresh()
            self._devices.append(dev)
            registry.register(dev)
        return True

    def teardown(self) -> None:
        self._devices.clear()
