"""
Unit tests for the CLI trait-query command and trait resolver.
"""

import argparse

import pytest

from smarthome import cli
from smarthome.core.registry import DeviceRegistry
from smarthome.core.traits import (
    BatteryLevelTrait,
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
    sensor = VirtualClimateSensor(device_id="sens_br", name="Bedroom Sensor", room="bedroom")

    # Register BatteryLevelTrait on the sensor to test battery display
    class _BatteryImpl:
        battery_percent = 85

    sensor.register_trait(BatteryLevelTrait, _BatteryImpl())
    registry.register(sensor)
    return registry


def _install_app(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli, "get_app", lambda config: _FakeApp(_registry()))


def test_resolve_trait_accepts_name_and_snake_case():
    assert resolve_trait("HumidityControlTrait") is HumidityControlTrait
    assert resolve_trait("humidity_control") is HumidityControlTrait
    assert resolve_trait("humidity_control_trait") is HumidityControlTrait
    assert resolve_trait("BatteryLevelTrait") is BatteryLevelTrait
    assert resolve_trait("battery_level") is BatteryLevelTrait
    assert resolve_trait("OnOff") is OnOffTrait
    assert resolve_trait("  on_off  ") is OnOffTrait


def test_resolve_trait_unknown_returns_none():
    assert resolve_trait("not_a_trait") is None


def test_trait_names_lists_canonical_names():
    names = trait_names()
    assert "HumidityControlTrait" in names
    assert "BatteryLevelTrait" in names
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


def test_cmd_status_displays_battery_level(monkeypatch, capsys):
    _install_app(monkeypatch)
    cli.cmd_status(argparse.Namespace(config="config.json", device_id="sens_br"))
    out = capsys.readouterr().out

    assert "Bedroom Sensor" in out
    assert "Battery Level:      85 %" in out


def test_cmd_scan_ble_discovered_devices(monkeypatch, capsys):
    def mock_scan(timeout):
        return [
            {
                "mac": "A4:C1:38:12:34:56",
                "name": "TP350 (1234)",
                "model": "TP350",
                "rssi": -65,
                "temperature_celsius": 21.4,
                "humidity_percent": 55.0,
                "battery_percent": 100,
            }
        ]

    import smarthome.drivers.ble.thermopro as tp_module

    monkeypatch.setattr(tp_module, "scan_for_thermopro_sensors", mock_scan)

    cli.cmd_scan_ble(argparse.Namespace(timeout=5.0))
    out = capsys.readouterr().out

    assert "Discovered 1 ThermoPro sensor(s):" in out
    assert "A4:C1:38:12:34:56" in out
    assert "TP350 (1234)" in out
    assert "21.4 °C" in out
    assert "55 %" in out
    assert "100 %" in out


def test_cmd_scan_ble_no_devices(monkeypatch, capsys):
    import smarthome.drivers.ble.thermopro as tp_module

    monkeypatch.setattr(tp_module, "scan_for_thermopro_sensors", lambda timeout: [])

    cli.cmd_scan_ble(argparse.Namespace(timeout=2.0))
    out = capsys.readouterr().out

    assert "No ThermoPro BLE sensors discovered." in out


def test_cmd_turn_on_and_off(monkeypatch, capsys):
    _install_app(monkeypatch)
    cli.cmd_turn_on(argparse.Namespace(config="config.json", device_id="dh_lr"))
    out = capsys.readouterr().out
    assert "Turned ON 'LR Dehumidifier'." in out

    cli.cmd_turn_off(argparse.Namespace(config="config.json", device_id="dh_lr"))
    out = capsys.readouterr().out
    assert "Turned OFF 'LR Dehumidifier'." in out


def test_cli_device_subcommands(monkeypatch, capsys):
    _install_app(monkeypatch)

    # device list
    monkeypatch.setattr("sys.argv", ["smarthome", "device", "list"])
    cli.main()
    out = capsys.readouterr().out
    assert "LR Dehumidifier" in out
    assert "Bedroom Sensor" in out

    # devices list (alias)
    monkeypatch.setattr("sys.argv", ["smarthome", "devices", "list"])
    cli.main()
    out = capsys.readouterr().out
    assert "LR Dehumidifier" in out

    # device turn-on
    monkeypatch.setattr("sys.argv", ["smarthome", "device", "turn-on", "dh_lr"])
    cli.main()
    out = capsys.readouterr().out
    assert "Turned ON 'LR Dehumidifier'." in out

    # device turn-off
    monkeypatch.setattr("sys.argv", ["smarthome", "device", "turn-off", "dh_lr"])
    cli.main()
    out = capsys.readouterr().out
    assert "Turned OFF 'LR Dehumidifier'." in out
