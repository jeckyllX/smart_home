# Smart Home Automation Platform

Climate control for a Raspberry Pi. Each device exposes capabilities as
runtime-checkable `typing.Protocol` traits (`OnOffTrait`, `HumidityControlTrait`,
`HumiditySensorTrait`, `TemperatureSensorTrait`, `ModeControlTrait`,
`TankLevelTrait`, `StatusFlagsTrait`, `BatteryLevelTrait`). Automations select
devices by trait and room.

---

## Installation

Requires Python 3.9+. Install it in editable mode (the package uses a `src/`
layout):

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
```

Dependencies are declared in `pyproject.toml` and listed in `requirements.txt`
and `requirements-dev.txt`.

Copy the example and fill in your values:

```bash
cp config.example.json config.json
```

Configure your devices in `devices: [...]` (or the legacy single `device: {...}` format).
See `config.example.json` for the full shape including Tuya dehumidifiers, ThermoPro BLE
sensors, locations, and automations.

---

## Architecture

```
┌──────────────────────┐
│     CLI / systemd    │
└──────────┬───────────┘
           ▼
┌──────────────────────┐        ┌──────────────┐
│ SmartHomeApplication │───────▶│   EventBus   │
└──────────┬───────────┘        └──────────────┘
           ▼
┌──────────────────────┐
│    DeviceRegistry    │
└──────────┬───────────┘
           ▼
      Device (abstract base)
      ├── MeacoAreteTuyaDevice   - Tuya LAN protocol 3.5
      ├── ThermoProBleDevice     - Bleak BLE broadcast listener (TP350/TP357/TP358)
      └── OpenMeteoWeatherDevice - Open-Meteo HTTP API
```

`app.py` builds the drivers and the active automations. `cli.py` is the entry
point (`smarthome.cli:main`).

---

## Modules

### `src/smarthome/core/`
- `traits.py` — device capability interfaces (`typing.Protocol`).
- `device.py` — `Device` base class and `DeviceCategory`; trait lookup via
  `register_trait`/`has_trait`/`get_trait`/`require_trait`.
- `registry.py` — stores devices and queries them by room and by trait.
- `events.py` — event bus for state changes and telemetry.

### `src/smarthome/devices/`
Base classes that combine traits for a device category:
`DehumidifierDevice`, `ClimateSensorDevice`, `SmartSwitchDevice`.

### `src/smarthome/drivers/`
The `core`, `devices`, and `automations` layers are shared across device models.
Each driver targets one device model and maps its protocol to those traits.

- `tuya/meaco_arete.py` — `TuyaDriver` talks to Meaco Arete Two dehumidifiers over
  the local Tuya protocol (v3.5) and produces `MeacoAreteTuyaDevice`. Holds the
  model's data-point IDs, mode names, humidity range (35-70% in 5% steps), and
  status-flag names (DP 19 bitmap: `tankfull`, `defrost`, `E1`, `E2`, `L2`, `L3`,
  `L4`, `wet`). The `wet` flag tracks the built-in sensor reading above 70%; that
  sensor reads high and the flag is also set while the device is off, so it is
  informational.
- `ble/thermopro.py` — `ThermoProDriver` coordinates `ThermoProScannerHub` and
  registers `ThermoProBleDevice` instances (exposing `TemperatureSensorTrait`,
  `HumiditySensorTrait`, and `BatteryLevelTrait`). Passively parses BLE manufacturer
  advertisement broadcasts without pairing for TP350, TP357, TP358, and TP39x sensors.
- `weather/open_meteo.py` — `OpenMeteoDriver` reads temperature and humidity from
  the Open-Meteo HTTP API (900 s cache) and registers `OpenMeteoWeatherDevice` in
  the `outdoor` room.
- `virtual/mock_climate.py` — `VirtualClimateSensor` and `VirtualDehumidifier` for
  tests and local runs without hardware.

### `src/smarthome/automations/`
- `CondensationPreventionAutomation` — for each room that has a dehumidifier,
  resolves a safe indoor dew point and sets the target humidity so the room stays
  below it. When multiple climate sensors are in the same room, it aggregates to
  the worst-case conditions (minimum room temperature and maximum humidity).
  In window mode it estimates the interior glass temperature from the
  outdoor temperature and the glazing type; in fixed mode it uses the configured
  `target_dew_point_c` and needs no outdoor sensor. The target is clamped to the
  overlap of the configured bounds and the device range, snapped to the device
  step, and only written when the move exceeds `rh_deadband`. Uses the
  Magnus-Tetens formulas in `physics/psychrometrics.py`.
- `QuietScheduleAutomation` — switches devices in the selected rooms to the night
  mode (default `sleep`) during a configured time window, and back to the day mode
  (default `manual`) outside it.

### `src/smarthome/physics/psychrometrics.py`
Magnus-Tetens dew point and its inverse (`calculate_dew_point`,
`calculate_rh_for_dew_point`), the interior glass temperature estimate, the safe
dew point (`resolve_safe_dew_point`), the maximum safe indoor relative humidity
(`calculate_condensation_safe_rh`), and humidity setpoint snapping
(`quantize_rh`).

---

## CLI

The CLI is installed at `.venv/bin/smarthome`.

### List devices
```bash
.venv/bin/smarthome list
```

### Find devices by trait
```bash
# Trait class name or snake_case identifier both work
.venv/bin/smarthome find --trait HumidityControlTrait
.venv/bin/smarthome find --trait humidity_control --room bedroom
```

### Read device telemetry
```bash
.venv/bin/smarthome status <device_id>
.venv/bin/smarthome status weather_outdoor
```

### Print raw data points
```bash
# Raw Tuya data points and the decoded status flags, for a Tuya device
.venv/bin/smarthome probe <device_id>
```

### Set target humidity or mode
```bash
# Works on any device that supports HumidityControlTrait
.venv/bin/smarthome set-target <device_id> 50

# Works on any device that supports ModeControlTrait
.venv/bin/smarthome set-mode <device_id> sleep
```

### Scan for BLE sensors
```bash
# Scan for nearby ThermoPro TP35x/TP39x sensors and display MAC, signal, temp, RH, battery
.venv/bin/smarthome scan-ble
.venv/bin/smarthome scan-ble --timeout 15
```

### Run automations
```bash
.venv/bin/smarthome evaluate   # one evaluation cycle
.venv/bin/smarthome daemon     # loop until stopped
```

---

## Development

```bash
.venv/bin/ruff check .          # lint
.venv/bin/ruff format --check . # formatting
.venv/bin/mypy src              # type check
.venv/bin/pytest                # test suite
```

Run from the repo root.

---

## Deployment

`install.sh` installs a systemd user unit that runs the daemon from this project
directory, reloads the user manager, and enables it:

```bash
python3 -m venv .venv
.venv/bin/pip install -e .
./install.sh
```

```bash
systemctl --user status smart_home.service
journalctl --user -u smart_home.service -f
```

To keep the daemon running after logout: `sudo loginctl enable-linger "$USER"`.
