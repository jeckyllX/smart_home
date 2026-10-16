"""
Driver base contract for hardware transports and service integrations.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from smarthome.core.events import EventBus
from smarthome.core.registry import DeviceRegistry


class Driver(ABC):
    """
    Abstract driver managing connections to external hardware buses,
    LAN protocols, or cloud APIs.
    """

    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def setup(self, registry: DeviceRegistry, event_bus: EventBus) -> bool:
        """Initialize driver, discover devices, and register them."""
        ...

    @abstractmethod
    def teardown(self) -> None:
        """Release sockets and disconnect."""
        ...
