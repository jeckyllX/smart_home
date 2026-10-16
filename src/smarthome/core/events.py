"""
Typed event bus system for smart home event dispatch and telemetry streams.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, TypeVar

logger = logging.getLogger("EventBus")

E = TypeVar("E", bound="Event")


@dataclass(frozen=True)
class Event:
    """Base event payload."""

    timestamp: float = field(default_factory=time.time)


@dataclass(frozen=True)
class DeviceStateChangedEvent(Event):
    """Fired when an internal property or trait state changes."""

    device_id: str = ""
    trait_name: str = ""
    property_name: str = ""
    old_value: Any = None
    new_value: Any = None


@dataclass(frozen=True)
class TelemetryEvent(Event):
    """Fired on periodic sensor readings."""

    device_id: str = ""
    metric: str = ""
    value: float = 0.0
    unit: str = ""


@dataclass(frozen=True)
class CommandDispatchedEvent(Event):
    """Fired when a control action is transmitted to a device."""

    device_id: str = ""
    command: str = ""
    arguments: dict[str, Any] = field(default_factory=dict)
    success: bool = False


class EventBus:
    """Thread-safe event distributor."""

    def __init__(self):
        self._lock = threading.RLock()
        self._subscribers: dict[type[Event], list[Callable[[Any], None]]] = {}
        self._global_subscribers: list[Callable[[Event], None]] = []

    def subscribe(self, event_type: type[E], handler: Callable[[E], None]) -> None:
        """Register listener for a specific event type."""
        with self._lock:
            if event_type not in self._subscribers:
                self._subscribers[event_type] = []
            self._subscribers[event_type].append(handler)

    def subscribe_all(self, handler: Callable[[Event], None]) -> None:
        """Register listener for all events."""
        with self._lock:
            self._global_subscribers.append(handler)

    def publish(self, event: Event) -> None:
        """Publish an event to all interested subscribers."""
        with self._lock:
            handlers = list(self._subscribers.get(type(event), []))
            global_handlers = list(self._global_subscribers)

        for handler in handlers:
            try:
                handler(event)
            except Exception as e:
                logger.error("Error in event handler %s: %s", handler, e, exc_info=True)

        for g_handler in global_handlers:
            try:
                g_handler(event)
            except Exception as e:
                logger.error("Error in global event handler %s: %s", g_handler, e, exc_info=True)
