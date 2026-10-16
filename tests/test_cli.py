"""
Unit tests for the CLI trait-query command and trait resolver.
"""

import argparse

import pytest

from smarthome import cli
from smarthome.core.registry import DeviceRegistry
from smarthome.core.traits import (
    HumidityControlTrait,
    OnOffTrait,
    resolve_trait,
    trait_names,
)
from smarthome.drivers.virtual.mock_climate import VirtualClimateSensor, VirtualDehumidifier


class _FakeApp:
    """Minimal stand-in for SmartHomeApplication, avoiding real driver/network setup."""

    def __init__(self, registry: DeviceRegistry) -> None:
        self.registry = registry


def _registry() -> DeviceRegistry:
    registry = DeviceRegistry()
    registry.register(
        VirtualDehumidifier(device_id="dh_lr", name="LR Dehumidifier", room="living_room")
    )
    registry.register(
        VirtualClimateSensor(device_id="sens_br", name="Bedroom Sensor", room="bedroom")
    )
    return registry


def _install_app(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli, "get_app", lambda config: _FakeApp(_registry()))


def test_resolve_trait_accepts_name_and_snake_case():
    assert resolve_trait("HumidityControlTrait") is HumidityControlTrait
    assert resolve_trait("humidity_control") is HumidityControlTrait
    assert resolve_trait("humidity_control_trait") is HumidityControlTrait
    assert resolve_trait("OnOff") is OnOffTrait
    assert resolve_trait("  on_off  ") is OnOffTrait


def test_resolve_trait_unknown_returns_none():
    assert resolve_trait("not_a_trait") is None


def test_trait_names_lists_canonical_names():
    names = trait_names()
    assert "HumidityControlTrait" in names
    assert all(name.endswith("Trait") for name in names)


def test_cmd_find_filters_by_trait(monkeypatch, capsys):
    _install_app(monkeypatch)
    cli.cmd_find(argparse.Namespace(config="config.json", trait="humidity_control", room=None))
    out = capsys.readouterr().out

    assert "dh_lr" in out
    assert "sens_br" not in out


def test_cmd_find_filters_by_trait_and_room(monkeypatch, capsys):
    _install_app(monkeypatch)
    cli.cmd_find(argparse.Namespace(config="config.json", trait="humidity_sensor", room="bedroom"))
    out = capsys.readouterr().out

    assert "sens_br" in out
    assert "dh_lr" not in out


def test_cmd_find_unknown_trait_exits(monkeypatch):
    _install_app(monkeypatch)
    with pytest.raises(SystemExit):
        cli.cmd_find(argparse.Namespace(config="config.json", trait="bogus", room=None))
