"""
Universal Smart Home Command Line Interface.
Query and command heterogeneous IoT devices across rooms.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from smarthome.app import SmartHomeApplication
from smarthome.config.schema import SmartHomeConfig
from smarthome.core.traits import (
    HumidityControlTrait,
    HumiditySensorTrait,
    ModeControlTrait,
    OnOffTrait,
    TankLevelTrait,
    TemperatureSensorTrait,
    resolve_trait,
    trait_names,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


def get_app(config_path: str) -> SmartHomeApplication:
    p = Path(config_path)
    if not p.exists():
        sys.exit(f"Error: Config file '{config_path}' not found.")
    cfg = SmartHomeConfig.from_file(p)
    return SmartHomeApplication(cfg)


def cmd_list(args):
    app = get_app(args.config)
    devices = app.registry.all_devices()
    rooms = len(app.registry.all_rooms())
    print(f"\nRegistered Smart Home Devices ({len(devices)} total across {rooms} rooms):\n")
    print(f"{'ID':<20} | {'Name':<24} | {'Room':<14} | {'Category':<16} | {'Online'}")
    print("-" * 88)
    for d in devices:
        status_str = "ONLINE" if d.is_online else "OFFLINE"
        print(f"{d.id:<20} | {d.name:<24} | {d.room:<14} | {d.category.value:<16} | {status_str}")
    print()


def cmd_find(args: argparse.Namespace) -> None:
    trait_cls = resolve_trait(args.trait)
    if trait_cls is None:
        sys.exit(f"Unknown trait '{args.trait}'. Available traits: {', '.join(trait_names())}")

    app = get_app(args.config)
    if args.room:
        devices = app.registry.find_devices_with_trait_in_room(args.room, trait_cls)
        scope = f" in room '{args.room}'"
    else:
        devices = app.registry.find_devices_with_trait(trait_cls)
        scope = ""

    print(f"\nDevices supporting {trait_cls.__name__}{scope} ({len(devices)}):\n")
    print(f"{'ID':<20} | {'Name':<24} | {'Room':<14} | {'Category':<16} | {'Online'}")
    print("-" * 88)
    for d in devices:
        status_str = "ONLINE" if d.is_online else "OFFLINE"
        print(f"{d.id:<20} | {d.name:<24} | {d.room:<14} | {d.category.value:<16} | {status_str}")
    print()


def cmd_status(args):
    app = get_app(args.config)
    dev = app.registry.get(args.device_id)
    if not dev:
        sys.exit(f"Device '{args.device_id}' not found.")

    dev.refresh()
    print(f"\n--- Device Details: {dev.name} ({dev.id}) ---")
    print(f"  Manufacturer:       {dev.manufacturer}")
    print(f"  Model:              {dev.model}")
    print(f"  Category:           {dev.category.value}")
    print(f"  Room / Zone:        {dev.room}")
    print(f"  Online Status:      {dev.is_online}")

    # Print the traits the device exposes
    on_off = dev.get_trait(OnOffTrait)
    if on_off:
        print(f"  Power State:        {'ON' if on_off.is_on else 'OFF'}")

    t_sensor = dev.get_trait(TemperatureSensorTrait)
    if t_sensor and t_sensor.temperature_celsius is not None:
        print(f"  Temperature:        {t_sensor.temperature_celsius:.1f} °C")

    h_sensor = dev.get_trait(HumiditySensorTrait)
    if h_sensor and h_sensor.humidity_percent is not None:
        print(f"  Relative Humidity:  {h_sensor.humidity_percent:.0f} %")

    h_ctrl = dev.get_trait(HumidityControlTrait)
    if h_ctrl and h_ctrl.target_humidity_percent is not None:
        print(
            f"  Target Humidity:    {h_ctrl.target_humidity_percent} % "
            f"(Range: {h_ctrl.humidity_range})"
        )

    mode_ctrl = dev.get_trait(ModeControlTrait)
    if mode_ctrl:
        print(
            f"  Current Mode:       {mode_ctrl.current_mode} (Options: {mode_ctrl.supported_modes})"
        )

    tank = dev.get_trait(TankLevelTrait)
    if tank:
        print(f"  Tank Full:          {tank.is_tank_full}")
    print()


def cmd_set_target(args):
    app = get_app(args.config)
    dev = app.registry.get(args.device_id)
    if not dev:
        sys.exit(f"Device '{args.device_id}' not found.")

    ctrl = dev.get_trait(HumidityControlTrait)
    if not ctrl:
        sys.exit(f"Device '{dev.name}' does not support humidity control.")

    target = int(args.humidity)
    min_h, max_h = ctrl.humidity_range
    if not (min_h <= target <= max_h):
        sys.exit(f"Target humidity must be between {min_h}% and {max_h}%.")

    success = ctrl.set_target_humidity(target)
    if success:
        print(f"Set target humidity for '{dev.name}' to {target}%.")
    else:
        sys.exit(f"Failed to set target humidity on '{dev.name}'.")


def cmd_set_mode(args):
    app = get_app(args.config)
    dev = app.registry.get(args.device_id)
    if not dev:
        sys.exit(f"Device '{args.device_id}' not found.")

    mode_ctrl = dev.get_trait(ModeControlTrait)
    if not mode_ctrl:
        sys.exit(f"Device '{dev.name}' does not support mode selection.")

    success = mode_ctrl.set_mode(args.mode)
    if success:
        print(f"Set operational mode for '{dev.name}' to '{args.mode}'.")
    else:
        sys.exit(f"Failed to set mode '{args.mode}' on '{dev.name}'.")


def cmd_evaluate(args):
    app = get_app(args.config)
    print("\n--- Running Automation Evaluation Cycle ---")
    logs = app.evaluate_cycle()
    for entry in logs:
        print(f"  * {entry}")
    print()


def cmd_daemon(args):
    app = get_app(args.config)
    app.start()


def main():
    parser = argparse.ArgumentParser(description="Smart Home Platform CLI")
    parser.add_argument("--config", default="config.json", help="Path to configuration file")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # list
    p_list = subparsers.add_parser("list", help="List all registered devices across rooms")
    p_list.set_defaults(func=cmd_list)

    # find
    p_find = subparsers.add_parser("find", help="Find devices supporting a trait")
    p_find.add_argument(
        "--trait",
        required=True,
        help="Trait name, e.g. HumidityControlTrait or humidity_control",
    )
    p_find.add_argument("--room", help="Restrict results to a room/zone")
    p_find.set_defaults(func=cmd_find)

    # status
    p_status = subparsers.add_parser("status", help="Get detailed status of a device")
    p_status.add_argument("device_id", help="Target device ID")
    p_status.set_defaults(func=cmd_status)

    # set-target
    p_target = subparsers.add_parser("set-target", help="Adjust target humidity")
    p_target.add_argument("device_id", help="Target device ID")
    p_target.add_argument("humidity", type=int, help="Desired relative humidity percentage")
    p_target.set_defaults(func=cmd_set_target)

    # set-mode
    p_mode = subparsers.add_parser("set-mode", help="Switch operational mode")
    p_mode.add_argument("device_id", help="Target device ID")
    p_mode.add_argument("mode", help="Operational mode string")
    p_mode.set_defaults(func=cmd_set_mode)

    # evaluate
    p_eval = subparsers.add_parser(
        "evaluate", help="Run a single evaluation pass of active automations"
    )
    p_eval.set_defaults(func=cmd_evaluate)

    # daemon
    p_daemon = subparsers.add_parser("daemon", help="Run the smart home automation daemon")
    p_daemon.set_defaults(func=cmd_daemon)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
