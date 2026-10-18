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
    BatteryLevelTrait,
    HumidityControlTrait,
    HumiditySensorTrait,
    ModeControlTrait,
    OnOffTrait,
    StatusFlagsTrait,
    TankLevelTrait,
    TemperatureSensorTrait,
    resolve_trait,
    trait_names,
)
from smarthome.physics.psychrometrics import quantize_rh

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

    batt = dev.get_trait(BatteryLevelTrait)
    if batt and batt.battery_percent is not None:
        print(f"  Battery Level:      {batt.battery_percent} %")

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

    flags_trait = dev.get_trait(StatusFlagsTrait)
    if flags_trait:
        flags = flags_trait.status_flags
        print(f"  Status Flags:       {', '.join(flags) if flags else 'none'}")
    print()


def _dp_sort_key(key: str) -> tuple[int, str]:
    """Sort numeric data-point ids numerically; non-numeric ids sort last."""
    return (0, key.zfill(6)) if key.isdigit() else (1, key)


def cmd_probe(args):
    app = get_app(args.config)
    dev = app.registry.get(args.device_id)
    if not dev:
        sys.exit(f"Device '{args.device_id}' not found.")

    dev.refresh()
    raw = getattr(dev, "raw_dps", None)
    if raw is None:
        sys.exit(f"Device '{dev.name}' does not expose raw data points.")

    print(f"\n--- Raw Data Points: {dev.name} ({dev.id}) ---")
    for key in sorted(raw, key=_dp_sort_key):
        print(f"  DP {key:<5}= {raw[key]}")

    flags_trait = dev.get_trait(StatusFlagsTrait)
    if flags_trait:
        flags = flags_trait.status_flags
        print(f"\n  Status Flags: {', '.join(flags) if flags else 'none'}")
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

    step = ctrl.humidity_step
    if step > 1:
        snapped = quantize_rh(target, step, min_h, max_h)
        if snapped != target:
            print(f"Note: {target}% is not a multiple of the {step}% step; using {snapped}%.")
            target = snapped

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


def cmd_turn_on(args: argparse.Namespace) -> None:
    app = get_app(args.config)
    dev = app.registry.get(args.device_id)
    if not dev:
        sys.exit(f"Device '{args.device_id}' not found.")

    on_off = dev.get_trait(OnOffTrait)
    if not on_off:
        sys.exit(f"Device '{dev.name}' does not support power on/off.")

    success = on_off.turn_on()
    if success:
        print(f"Turned ON '{dev.name}'.")
    else:
        sys.exit(f"Failed to turn ON '{dev.name}'.")


def cmd_turn_off(args: argparse.Namespace) -> None:
    app = get_app(args.config)
    dev = app.registry.get(args.device_id)
    if not dev:
        sys.exit(f"Device '{args.device_id}' not found.")

    on_off = dev.get_trait(OnOffTrait)
    if not on_off:
        sys.exit(f"Device '{dev.name}' does not support power on/off.")

    success = on_off.turn_off()
    if success:
        print(f"Turned OFF '{dev.name}'.")
    else:
        sys.exit(f"Failed to turn OFF '{dev.name}'.")


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


def cmd_scan_ble(args: argparse.Namespace) -> None:
    from smarthome.drivers.ble.thermopro import scan_for_thermopro_sensors

    timeout = float(args.timeout)
    print(f"\nScanning for ThermoPro BLE sensors ({timeout:.1f}s timeout)...\n")
    devices = scan_for_thermopro_sensors(timeout=timeout)
    if not devices:
        print("No ThermoPro BLE sensors discovered.")
        print("Ensure Bluetooth is enabled and the sensor is powered and in range.\n")
        return

    print(f"Discovered {len(devices)} ThermoPro sensor(s):\n")
    print(
        f"{'MAC Address':<18} | {'Name':<20} | {'Model':<8} | {'RSSI':<8} | "
        f"{'Temp':<8} | {'Humidity':<10} | {'Battery'}"
    )
    print("-" * 90)
    for d in devices:
        mac = d.get("mac", "UNKNOWN")
        name = d.get("name", "Unknown")
        model = d.get("model", "TP35x")
        rssi_val = d.get("rssi")
        rssi = f"{rssi_val} dBm" if rssi_val is not None else "N/A"
        temp = f"{d.get('temperature_celsius', 0.0):.1f} °C"
        humidity = f"{d.get('humidity_percent', 0.0):.0f} %"
        batt = f"{d.get('battery_percent', 0)} %"
        row = (
            f"{mac:<18} | {name:<20} | {model:<8} | {rssi:<8} | {temp:<8} | {humidity:<10} | {batt}"
        )
        print(row)
    print()


def main():
    parser = argparse.ArgumentParser(description="Smart Home Platform CLI")
    parser.add_argument("--config", default="config.json", help="Path to configuration file")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # device / devices subcommand group
    p_device = subparsers.add_parser(
        "device", aliases=["devices"], help="Commands operating on devices"
    )
    dev_subparsers = p_device.add_subparsers(dest="device_command", required=True)

    # device list
    d_list = dev_subparsers.add_parser("list", help="List all registered devices across rooms")
    d_list.set_defaults(func=cmd_list)

    # device status
    d_status = dev_subparsers.add_parser("status", help="Get detailed status of a device")
    d_status.add_argument("device_id", help="Target device ID")
    d_status.set_defaults(func=cmd_status)

    # device turn-on
    d_turn_on = dev_subparsers.add_parser("turn-on", help="Power ON a device")
    d_turn_on.add_argument("device_id", help="Target device ID")
    d_turn_on.set_defaults(func=cmd_turn_on)

    # device turn-off
    d_turn_off = dev_subparsers.add_parser("turn-off", help="Power OFF a device")
    d_turn_off.add_argument("device_id", help="Target device ID")
    d_turn_off.set_defaults(func=cmd_turn_off)

    # device set-target
    d_target = dev_subparsers.add_parser("set-target", help="Adjust target humidity")
    d_target.add_argument("device_id", help="Target device ID")
    d_target.add_argument("humidity", type=int, help="Desired relative humidity percentage")
    d_target.set_defaults(func=cmd_set_target)

    # device set-mode
    d_mode = dev_subparsers.add_parser("set-mode", help="Switch operational mode")
    d_mode.add_argument("device_id", help="Target device ID")
    d_mode.add_argument("mode", help="Operational mode string")
    d_mode.set_defaults(func=cmd_set_mode)

    # device probe
    d_probe = dev_subparsers.add_parser(
        "probe", help="Print the raw data points and status flags of a device"
    )
    d_probe.add_argument("device_id", help="Target device ID")
    d_probe.set_defaults(func=cmd_probe)

    # device find
    d_find = dev_subparsers.add_parser("find", help="Find devices supporting a trait")
    d_find.add_argument(
        "--trait",
        required=True,
        help="Trait name, e.g. HumidityControlTrait or humidity_control",
    )
    d_find.add_argument("--room", help="Restrict results to a room/zone")
    d_find.set_defaults(func=cmd_find)

    # top-level shortcuts
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

    # turn-on
    p_turn_on = subparsers.add_parser("turn-on", help="Power ON a device")
    p_turn_on.add_argument("device_id", help="Target device ID")
    p_turn_on.set_defaults(func=cmd_turn_on)

    # turn-off
    p_turn_off = subparsers.add_parser("turn-off", help="Power OFF a device")
    p_turn_off.add_argument("device_id", help="Target device ID")
    p_turn_off.set_defaults(func=cmd_turn_off)

    # probe
    p_probe = subparsers.add_parser(
        "probe", help="Print the raw data points and status flags of a device"
    )
    p_probe.add_argument("device_id", help="Target device ID")
    p_probe.set_defaults(func=cmd_probe)

    # evaluate
    p_eval = subparsers.add_parser(
        "evaluate", help="Run a single evaluation pass of active automations"
    )
    p_eval.set_defaults(func=cmd_evaluate)

    # daemon
    p_daemon = subparsers.add_parser("daemon", help="Run the smart home automation daemon")
    p_daemon.set_defaults(func=cmd_daemon)

    # scan-ble
    p_scan = subparsers.add_parser(
        "scan-ble", help="Scan for nearby ThermoPro BLE temperature and humidity sensors"
    )
    p_scan.add_argument(
        "--timeout",
        type=float,
        default=12.0,
        help="Scan timeout in seconds (default: 12.0)",
    )
    p_scan.set_defaults(func=cmd_scan_ble)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
