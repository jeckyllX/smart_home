"""
Device traits / capabilities.
Defines fine-grained behaviors and telemetry interfaces.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class OnOffTrait(Protocol):
    """Capability to be turned on or off."""

    @property
    def is_on(self) -> bool:
        """Returns True if device is actively powered on."""
        ...

    def turn_on(self) -> bool:
        """Command the device to power ON."""
        ...

    def turn_off(self) -> bool:
        """Command the device to power OFF."""
        ...


@runtime_checkable
class TemperatureSensorTrait(Protocol):
    """Capability to measure ambient dry-bulb temperature."""

    @property
    def temperature_celsius(self) -> float | None:
        """Returns current temperature in degrees Celsius."""
        ...


@runtime_checkable
class HumiditySensorTrait(Protocol):
    """Capability to measure ambient relative humidity."""

    @property
    def humidity_percent(self) -> float | None:
        """Returns current relative humidity (0.0 to 100.0)."""
        ...


@runtime_checkable
class HumidityControlTrait(Protocol):
    """Capability to regulate or set target ambient relative humidity."""

    @property
    def target_humidity_percent(self) -> int | None:
        """Returns the current humidistat target percentage."""
        ...

    @property
    def humidity_range(self) -> tuple[int, int]:
        """Returns allowed (min, max) target relative humidity bounds."""
        ...

    @property
    def humidity_step(self) -> int:
        """Returns the increment in percent between allowed targets (1 = no step)."""
        ...

    def set_target_humidity(self, target_percent: int) -> bool:
        """Adjust humidistat setpoint."""
        ...


@runtime_checkable
class ModeControlTrait(Protocol):
    """Capability to switch operational profiles/modes."""

    @property
    def current_mode(self) -> str:
        """Returns identifier of active mode."""
        ...

    @property
    def supported_modes(self) -> list[str]:
        """Returns list of allowed operational mode strings."""
        ...

    def set_mode(self, mode: str) -> bool:
        """Switch to another operational mode."""
        ...


@runtime_checkable
class TankLevelTrait(Protocol):
    """Capability to report water collection reservoir state."""

    @property
    def is_tank_full(self) -> bool:
        """Returns True if the collection reservoir is at capacity or removed."""
        ...


@runtime_checkable
class StatusFlagsTrait(Protocol):
    """Capability to report named status flags from the device."""

    @property
    def status_flags(self) -> tuple[str, ...]:
        """
        Names of the flags the device currently reports, or an empty tuple.
        Flag names are driver-defined (for example 'tankfull', 'defrost', 'wet').
        """
        ...


ALL_TRAITS: tuple[type, ...] = (
    OnOffTrait,
    TemperatureSensorTrait,
    HumiditySensorTrait,
    HumidityControlTrait,
    ModeControlTrait,
    TankLevelTrait,
    StatusFlagsTrait,
)


def resolve_trait(name: str) -> type | None:
    """
    Resolve a trait class from its class name or snake_case identifier.
    Accepts e.g. "HumidityControlTrait", "humidity_control", "humidity_control_trait".
    Returns None if no trait matches.
    """
    normalized = name.strip().lower().replace("_", "").removesuffix("trait")
    for trait in ALL_TRAITS:
        if trait.__name__.lower().removesuffix("trait") == normalized:
            return trait
    return None


def trait_names() -> list[str]:
    """Return the canonical class names of all known traits."""
    return [trait.__name__ for trait in ALL_TRAITS]
