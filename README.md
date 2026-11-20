# Smart Home Automation Platform

Climate control for a Raspberry Pi. Each device exposes capabilities as
runtime-checkable `typing.Protocol` traits (`OnOffTrait`, `HumidityControlTrait`,
`HumiditySensorTrait`, `TemperatureSensorTrait`, `TemperatureForecastTrait`,
`ModeControlTrait`, `TankLevelTrait`, `StatusFlagsTrait`, `BatteryLevelTrait`).
Automations select devices by trait and room.

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
      └── OpenMeteoWeatherDevice - Nearest physical METAR + Open-Meteo forecast
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
- `weather/open_meteo.py` — `OpenMeteoDriver` queries `aviationweather.gov` for
  the nearest physical METAR station observation (live outdoor temperature and
  humidity) and falls back to or pairs with the Open-Meteo HTTP API for the
  24h hourly temperature forecast (`TemperatureForecastTrait`, 900 s cache).
  Exposes `StatusFlagsTrait` (`Physical (<ICAO>)` or `Forecast Model`) and
  registers `OpenMeteoWeatherDevice` in the `outdoor` room.
- `virtual/mock_climate.py` — `VirtualClimateSensor` and `VirtualDehumidifier` for
  tests and local runs without hardware.

### `src/smarthome/automations/`
- `CondensationPreventionAutomation` (`condensation.py`) — for each room that has a
  dehumidifier, resolves a safe indoor dew point and sets the target humidity so the
  room stays below it. When multiple climate sensors are in the same room, it
  aggregates to the worst-case conditions (minimum room temperature and maximum
  humidity). In window mode it estimates the interior glass temperature from the
  effective outdoor temperature (the lower of current outdoor temperature and the
  `lookahead_hours` forecast minimum) and the glazing type; in fixed mode it uses
  `target_dew_point_c`. The target is clamped to the overlap of configured bounds
  and device range, snapped to the device step, and only written when the move
  exceeds `rh_deadband`. With `auto_power`, it turns the dehumidifier ON/OFF around
  the target using `turn_on_offset_rh`, `turn_off_offset_rh`, and a
  `min_cycle_seconds` compressor cooldown, while respecting `manual_override_minutes`
  holds and active exclusion windows. Uses `physics/psychrometrics.py`.
- `QuietScheduleAutomation` (`schedule.py`) — switches devices in the selected
  rooms to `night_mode` (default `sleep`) during the configured time window or on
  `all_day_sleep_days`, and back to `day_mode` (default `manual`) outside it
  (filtered by `night_days`). Also evaluates `exclusion_windows` that block power
  during configured hours/days.
- `AlertAutomation` (`alerts.py`) — checks registered devices for offline state,
  `tankfull` flags, and low battery (`low_battery_threshold_percent`), logging
  alerts and optionally sending cooldown-throttled JSON POSTs to `webhook_url`.

### `src/smarthome/storage/history.py`
`TelemetryStore` writes SQLite history (`history.db`) for `room_history` (indoor
temp/RH, outdoor temp, dew point, safe dew point, target RH, `is_on`, `is_defrost`)
and `device_events` (state changes and dispatched commands), and prunes records
older than `history_retention_days`.

### `src/smarthome/web/`
- `server.py` — HTTP API and background web server (`web.host`, `web.port`,
  default `8765`) started alongside `daemon` or standalone via `web`. Exposes
  `/api/status`, `/api/history`, `/api/config`, and `/api/control`.
- `ui.py` & `static/` (`index.html`, `styles.css`, `app.js`) — single-page
  dashboard showing outdoor summary strip, live room/device cards, condensation
  safety badges, interactive 6h–7d SVG climate charts (`ON` in blue, `Defrost`
  in purple, risk shading in red), manual override controls, and config editor.

### `src/smarthome/physics/psychrometrics.py`
Magnus-Tetens dew point and its inverse (`calculate_dew_point`,
`calculate_rh_for_dew_point`), the interior glass temperature estimate, the safe
dew point (`resolve_safe_dew_point`), the maximum safe indoor relative humidity
(`calculate_condensation_safe_rh`), and humidity setpoint snapping
(`quantize_rh`).

---

## CLI

The CLI is installed at `.venv/bin/smarthome`.

### Device subcommands (`device` or `devices`)
All device operations can be invoked under the `device` (or `devices`) subcommand, requiring the target `device_id` as parameter:

```bash
# List all registered devices across rooms
.venv/bin/smarthome device list

# Read telemetry and active traits
.venv/bin/smarthome device status <device_id>

# Power ON or OFF
.venv/bin/smarthome device turn-on <device_id>
.venv/bin/smarthome device turn-off <device_id>

# Set target humidity (snaps to device step)
.venv/bin/smarthome device set-target <device_id> 50

# Set operating mode
.venv/bin/smarthome device set-mode <device_id> sleep

# Inspect raw Tuya data points and status flags
.venv/bin/smarthome device probe <device_id>

# Find devices supporting a trait
.venv/bin/smarthome device find --trait HumidityControlTrait
```

Top-level shortcuts (`smarthome list`, `smarthome status <device_id>`, `smarthome turn-on <device_id>`, etc.) are also supported.

### Scan for BLE sensors
```bash
# Scan for nearby ThermoPro TP35x/TP39x sensors and display MAC, signal, temp, RH, battery
.venv/bin/smarthome scan-ble
.venv/bin/smarthome scan-ble --timeout 15
```

### Run automations & web dashboard
```bash
.venv/bin/smarthome evaluate                    # one evaluation cycle
.venv/bin/smarthome daemon                      # loop until stopped (starts web UI if enabled)
.venv/bin/smarthome daemon --no-web             # loop without web server
.venv/bin/smarthome web --host 0.0.0.0 --port 8765  # run web dashboard + polling loop
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
