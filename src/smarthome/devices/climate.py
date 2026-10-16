"""
Climate device base classes.
"""

from __future__ import annotations

from abc import ABC

from smarthome.core.device import Device, DeviceCategory
from smarthome.core.traits import (
    FaultSensorTrait,
    HumidityControlTrait,
    HumiditySensorTrait,
    ModeControlTrait,
    OnOffTrait,
    TankLevelTrait,
    TemperatureSensorTrait,
)


class DehumidifierDevice(
    Device,
    OnOffTrait,
    HumidityControlTrait,
    HumiditySensorTrait,
    ModeControlTrait,
    TankLevelTrait,
    FaultSensorTrait,
    ABC,
):
    """
    Abstract dehumidifier device.
    """

    def __init__(
        self,
        device_id: str,
        name: str,
        room: str = "default",
        manufacturer: str = "Generic",
        model: str = "Dehumidifier",
    ):
        super().__init__(
            device_id=device_id,
            name=name,
            category=DeviceCategory.DEHUMIDIFIER,
            room=room,
            manufacturer=manufacturer,
            model=model,
        )
        # Register traits for runtime lookup
        self.register_trait(OnOffTrait, self)
        self.register_trait(HumidityControlTrait, self)
        self.register_trait(HumiditySensorTrait, self)
        self.register_trait(ModeControlTrait, self)
        self.register_trait(TankLevelTrait, self)
        self.register_trait(FaultSensorTrait, self)


class ClimateSensorDevice(Device, TemperatureSensorTrait, HumiditySensorTrait, ABC):
    """
    Abstract climate sensor (indoor thermometer or outdoor weather station).
    """

    def __init__(
        self,
        device_id: str,
        name: str,
        room: str = "default",
        category: DeviceCategory = DeviceCategory.CLIMATE_SENSOR,
        manufacturer: str = "Generic",
        model: str = "Sensor",
    ):
        super().__init__(
            device_id=device_id,
            name=name,
            category=category,
            room=room,
            manufacturer=manufacturer,
            model=model,
        )
        self.register_trait(TemperatureSensorTrait, self)
        self.register_trait(HumiditySensorTrait, self)
