"""
Power device base classes.
"""

from __future__ import annotations

from abc import ABC

from smarthome.core.device import Device, DeviceCategory
from smarthome.core.traits import OnOffTrait


class SmartSwitchDevice(Device, OnOffTrait, ABC):
    """
    Abstract controllable power switch, plug, or relay.
    """

    def __init__(
        self,
        device_id: str,
        name: str,
        room: str = "default",
        manufacturer: str = "Generic",
        model: str = "Smart Switch",
    ):
        super().__init__(
            device_id=device_id,
            name=name,
            category=DeviceCategory.SWITCH,
            room=room,
            manufacturer=manufacturer,
            model=model,
        )
        self.register_trait(OnOffTrait, self)
