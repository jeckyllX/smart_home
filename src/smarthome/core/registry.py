"""
Central device registry managing smart home entities across rooms and capabilities.
"""

from __future__ import annotations

import logging
import threading
from typing import TypeVar

from smarthome.core.device import Device, DeviceCategory

logger = logging.getLogger("DeviceRegistry")
T = TypeVar("T")


class DeviceRegistry:
    """Thread-safe registry for smart devices."""

    def __init__(self):
        self._lock = threading.RLock()
        self._devices: dict[str, Device] = {}

    def register(self, device: Device) -> None:
        """Register a new device."""
        with self._lock:
            if device.id in self._devices:
                logger.warning("Overwriting existing device with id '%s'", device.id)
            self._devices[device.id] = device
            logger.info(
                "Registered device '%s' (%s, Room: %s)",
                device.name,
                device.category.value,
                device.room,
            )

    def unregister(self, device_id: str) -> Device | None:
        """Remove a device from registry."""
        with self._lock:
            return self._devices.pop(device_id, None)

    def get(self, device_id: str) -> Device | None:
        """Retrieve a device by its ID."""
        with self._lock:
            return self._devices.get(device_id)

    def all_devices(self) -> list[Device]:
        """Return all registered devices."""
        with self._lock:
            return list(self._devices.values())

    def get_by_category(self, category: DeviceCategory) -> list[Device]:
        """Find devices matching a specific category."""
        with self._lock:
            return [d for d in self._devices.values() if d.category == category]

    def get_by_room(self, room: str) -> list[Device]:
        """Find all devices located in a specific room/zone."""
        with self._lock:
            return [d for d in self._devices.values() if d.room.lower() == room.lower()]

    def find_devices_with_trait(self, trait_cls: type[T]) -> list[Device]:
        """Find all devices supporting a particular trait."""
        with self._lock:
            return [d for d in self._devices.values() if d.has_trait(trait_cls)]

    def find_devices_with_trait_in_room(self, room: str, trait_cls: type[T]) -> list[Device]:
        """Find devices in a room that support a specific trait."""
        with self._lock:
            return [
                d
                for d in self._devices.values()
                if d.room.lower() == room.lower() and d.has_trait(trait_cls)
            ]

    def all_rooms(self) -> set[str]:
        """Return list of distinct rooms configured in registry."""
        with self._lock:
            return {d.room for d in self._devices.values()}
