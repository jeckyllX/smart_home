"""
Virtual and simulation devices for testing multi-device topologies.
"""

from __future__ import annotations

from smarthome.devices.climate import ClimateSensorDevice, DehumidifierDevice


class VirtualClimateSensor(ClimateSensorDevice):
    """
    Simulated climate sensor with manually adjustable temperature and humidity.
    """

    def __init__(
        self,
        device_id: str,
        name: str,
        room: str = "living_room",
        initial_temp: float = 20.0,
        initial_rh: float = 55.0,
    ):
        super().__init__(
            device_id=device_id,
            name=name,
            room=room,
            manufacturer="Virtual",
            model="SimulatedSensor",
        )
        self._temp = initial_temp
        self._rh = initial_rh
        self._online = True

    @property
    def is_online(self) -> bool:
        return self._online

    def refresh(self) -> bool:
        return True

    @property
    def temperature_celsius(self) -> float | None:
        return self._temp

    @property
    def humidity_percent(self) -> float | None:
        return self._rh

    def set_environment(self, temp_c: float, rh_pct: float) -> None:
        """Helper to simulate environmental changes."""
        self._temp = temp_c
        self._rh = rh_pct


class VirtualDehumidifier(DehumidifierDevice):
    """
    Simulated dehumidifier appliance for integration testing.
    """

    def __init__(
        self,
        device_id: str,
        name: str,
        room: str = "living_room",
    ):
        super().__init__(
            device_id=device_id,
            name=name,
            room=room,
            manufacturer="Virtual",
            model="SimulatedDehumidifier",
        )
        self._is_on = True
        self._target_rh = 55
        self._current_rh = 60.0
        self._mode = "manual"
        self._tank_full = False

    @property
    def is_online(self) -> bool:
        return True

    def refresh(self) -> bool:
        return True

    @property
    def is_on(self) -> bool:
        return self._is_on

    def turn_on(self) -> bool:
        self._is_on = True
        return True

    def turn_off(self) -> bool:
        self._is_on = False
        return True

    @property
    def humidity_percent(self) -> float | None:
        return self._current_rh

    @property
    def target_humidity_percent(self) -> int | None:
        return self._target_rh

    @property
    def humidity_range(self) -> tuple[int, int]:
        return 30, 80

    def set_target_humidity(self, target_percent: int) -> bool:
        self._target_rh = max(30, min(80, target_percent))
        return True

    @property
    def current_mode(self) -> str:
        return self._mode

    @property
    def supported_modes(self) -> list[str]:
        return ["manual", "sleep", "laundry", "purify"]

    def set_mode(self, mode: str) -> bool:
        if mode in self.supported_modes:
            self._mode = mode
            return True
        return False

    @property
    def is_tank_full(self) -> bool:
        return self._tank_full

    def set_tank_full(self, full: bool) -> None:
        self._tank_full = full

    @property
    def has_fault(self) -> bool:
        return self._tank_full

    @property
    def fault_description(self) -> str | None:
        return "Tank full" if self._tank_full else None
