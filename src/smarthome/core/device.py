"""
Core device abstraction and categorization.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, TypeVar

T = TypeVar("T")


class DeviceCategory(str, Enum):
    DEHUMIDIFIER = "dehumidifier"
    CLIMATE_SENSOR = "climate_sensor"
    WEATHER_STATION = "weather_station"
    SWITCH = "switch"
    HEATER = "heater"
    AIR_PURIFIER = "air_purifier"
    GENERIC = "generic"


class Device(ABC):
    """
    Abstract base class for all smart home entities.
    A device can expose multiple capabilities (traits).
    """

    def __init__(
        self,
        device_id: str,
        name: str,
        category: DeviceCategory,
        room: str = "default",
        manufacturer: str = "Generic",
        model: str = "Unknown",
    ):
        self.id = device_id
        self.name = name
        self.category = category
        self.room = room
        self.manufacturer = manufacturer
        self.model = model
        self._traits: dict[type, Any] = {}

    def register_trait(self, trait_cls: type[T], implementation: T) -> None:
        """Register a capability implementation for this device."""
        self._traits[trait_cls] = implementation

    def has_trait(self, trait_cls: type[T]) -> bool:
        """Check whether this device supports a given trait."""
        if trait_cls in self._traits:
            return True
        return isinstance(self, trait_cls)

    def get_trait(self, trait_cls: type[T]) -> T | None:
        """Obtain trait implementation, or None if unsupported."""
        if trait_cls in self._traits:
            return self._traits[trait_cls]
        if isinstance(self, trait_cls):
            return self  # Self-implemented
        return None

    def require_trait(self, trait_cls: type[T]) -> T:
        """Obtain trait implementation or raise TypeError."""
        trait = self.get_trait(trait_cls)
        if trait is None:
            raise TypeError(
                f"Device '{self.name}' ({self.id}) does not support trait {trait_cls.__name__}"
            )
        return trait

    @property
    @abstractmethod
    def is_online(self) -> bool:
        """Check whether device is currently reachable over its network transport."""
        ...

    @abstractmethod
    def refresh(self) -> bool:
        """Poll hardware state and update internal telemetry caches."""
        ...

    def get_summary(self) -> dict[str, Any]:
        """Diagnostic summary of device identity and status."""
        return {
            "id": self.id,
            "name": self.name,
            "category": self.category.value,
            "room": self.room,
            "manufacturer": self.manufacturer,
            "model": self.model,
            "online": self.is_online,
            "traits": [t.__name__ for t in self._traits],
        }
