"""
Base class for automations.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from smarthome.core.events import EventBus
from smarthome.core.registry import DeviceRegistry


class Automation(ABC):
    """
    Abstract automation rule.
    Operates over the device registry and traits.
    """

    def __init__(self, name: str, enabled: bool = True):
        self.name = name
        self.enabled = enabled

    @abstractmethod
    def evaluate(self, registry: DeviceRegistry, event_bus: EventBus) -> list[str]:
        """
        Evaluate conditions against device traits across rooms and dispatch actions.
        Returns a list of human-readable decision summaries.
        """
        ...
