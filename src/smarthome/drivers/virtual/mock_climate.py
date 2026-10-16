"""
Virtual and simulation devices for testing multi-device topologies.
"""

from __future__ import annotations

from smarthome.devices.climate import ClimateSensorDevice, DehumidifierDevice
from smarthome.physics.psychrometrics import quantize_rh


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

    HUMIDITY_RANGE = (35, 70)
    HUMIDITY_STEP = 5

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
        self._status_flags: set[str] = set()
        # Number of times set_target_humidity was called; used by tests.
        self.set_target_calls = 0

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
        return self.HUMIDITY_RANGE

    @property
    def humidity_step(self) -> int:
        return self.HUMIDITY_STEP

    def set_target_humidity(self, target_percent: int) -> bool:
        low, high = self.HUMIDITY_RANGE
        self._target_rh = quantize_rh(int(target_percent), self.HUMIDITY_STEP, low, high)
        self.set_target_calls += 1
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
    def status_flags(self) -> tuple[str, ...]:
        return tuple(sorted(self._status_flags))

    def set_status_flags(self, *flags: str) -> None:
        self._status_flags = set(flags)

    @property
    def is_tank_full(self) -> bool:
        return "tankfull" in self._status_flags

    def set_tank_full(self, full: bool) -> None:
        if full:
            self._status_flags.add("tankfull")
        else:
            self._status_flags.discard("tankfull")

    def set_current_humidity(self, rh_pct: float) -> None:
        self._current_rh = rh_pct
