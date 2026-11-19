"""
SmartHomeApplication coordinator and runtime.
Owns the registry, drivers, event bus, and active automations.
"""

from __future__ import annotations

import logging
import signal
import threading
import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from smarthome.web.server import SmartHomeWebServer

from smarthome.automations.alerts import HealthAlertAutomation
from smarthome.automations.base import Automation
from smarthome.automations.condensation import CondensationPreventionAutomation
from smarthome.automations.schedule import QuietScheduleAutomation
from smarthome.config.schema import SmartHomeConfig
from smarthome.core.events import EventBus
from smarthome.core.registry import DeviceRegistry
from smarthome.core.traits import (
    BatteryLevelTrait,
    HumidityControlTrait,
    HumiditySensorTrait,
    ModeControlTrait,
    OnOffTrait,
    StatusFlagsTrait,
    TankLevelTrait,
    TemperatureForecastTrait,
    TemperatureSensorTrait,
)
from smarthome.drivers.ble.thermopro import ThermoProDriver
from smarthome.drivers.tuya.meaco_arete import TuyaDriver
from smarthome.drivers.weather.open_meteo import OpenMeteoDriver, OpenMeteoWeatherDevice
from smarthome.storage.history import TelemetryStore

logger = logging.getLogger("SmartHomeApp")

EDITABLE_CONFIG_KEYS = frozenset(
    {
        "condensation",
        "quiet_schedule",
        "alerts",
        "location",
        "polling_interval_seconds",
    }
)


class SmartHomeApplication:
    """
    Top-level application container coordinating the smart home platform.
    """

    def __init__(
        self,
        config: SmartHomeConfig,
        refresh_on_init: bool = True,
        history_store: TelemetryStore | None = None,
    ):
        self.config = config
        self.refresh_on_init = refresh_on_init
        self.registry = DeviceRegistry()
        self.event_bus = EventBus()
        self.automations: list[Automation] = []
        self._lock = threading.RLock()
        self._eval_lock = threading.Lock()
        self._running = False
        self._closed = False
        self._web_server: SmartHomeWebServer | None = None
        self._manual_overrides: dict[str, float] = {}
        self._last_power_change: dict[str, float] = {}

        if history_store is not None:
            self.history_store = history_store
        else:
            db_path = (
                config.history_db_path
                if (config.raw_path is not None or config.history_db_path != "history.db")
                else ":memory:"
            )
            self.history_store = TelemetryStore(
                db_path=db_path,
                retention_days=config.history_retention_days,
            )
        self.history_store.attach_event_bus(self.event_bus)
        self._restore_runtime_state()

        self.last_evaluation_logs: list[str] = []
        self.last_evaluation_time: float | None = None

        self._setup_drivers()
        self._setup_automations()

    def _restore_runtime_state(self) -> None:
        """Restore active manual holds and compressor cooldown timestamps from storage."""
        now = time.time()
        try:
            for key, val in self.history_store.get_state_by_prefix("override:").items():
                dev_id = key[len("override:") :]
                if isinstance(val, (int, float)) and float(val) > now:
                    self._manual_overrides[dev_id] = float(val)
                else:
                    self.history_store.delete_state(key)

            for key, val in self.history_store.get_state_by_prefix("power_change:").items():
                dev_id = key[len("power_change:") :]
                if isinstance(val, (int, float)):
                    self._last_power_change[dev_id] = float(val)
        except Exception as e:
            logger.warning("Failed to restore runtime state: %s", e)

    def _setup_drivers(self) -> None:
        # Weather driver
        loc = self.config.location
        weather_driver = OpenMeteoDriver(
            latitude=loc.latitude,
            longitude=loc.longitude,
            name=f"Weather Station ({loc.city})",
            refresh_on_setup=self.refresh_on_init,
        )
        weather_driver.setup(self.registry, self.event_bus)

        # Tuya driver
        if self.config.tuya_devices:
            tuya_driver = TuyaDriver(
                self.config.tuya_devices,
                refresh_on_setup=self.refresh_on_init,
            )
            tuya_driver.setup(self.registry, self.event_bus)

        # ThermoPro BLE driver
        if self.config.ble_devices:
            ble_driver = ThermoProDriver(
                self.config.ble_devices,
                refresh_on_setup=self.refresh_on_init,
            )
            ble_driver.setup(self.registry, self.event_bus)

    def set_manual_override(
        self, device_id: str, minutes: float, now_ts: float | None = None
    ) -> float:
        """Place a device on manual hold for `minutes`, preventing automation changes."""
        now = now_ts if now_ts is not None else time.time()
        until_ts = now + max(0.0, minutes * 60.0)
        with self._lock:
            if minutes <= 0:
                self._manual_overrides.pop(device_id, None)
                if not self._closed:
                    self.history_store.delete_state(f"override:{device_id}")
                return 0.0
            self._manual_overrides[device_id] = until_ts
            if not self._closed:
                self.history_store.set_state(f"override:{device_id}", until_ts)
            return until_ts

    def clear_manual_override(self, device_id: str) -> None:
        """Clear any active manual hold for a device, resuming automatic control."""
        with self._lock:
            self._manual_overrides.pop(device_id, None)
            if not self._closed:
                self.history_store.delete_state(f"override:{device_id}")

    def is_device_overridden(self, device_id: str, now_ts: float | None = None) -> tuple[bool, int]:
        """Return (is_overridden, remaining_seconds) for a device."""
        now = now_ts if now_ts is not None else time.time()
        with self._lock:
            until_ts = self._manual_overrides.get(device_id)
            if until_ts is None:
                return False, 0
            rem = int(until_ts - now)
            if rem <= 0:
                self._manual_overrides.pop(device_id, None)
                if not self._closed:
                    self.history_store.delete_state(f"override:{device_id}")
                return False, 0
            return True, rem

    def record_power_change(self, device_id: str, ts: float | None = None) -> None:
        """Record the latest compressor power transition timestamp for cooldown tracking."""
        ts_val = ts if ts is not None else time.time()
        with self._lock:
            self._last_power_change[device_id] = ts_val
            for auto in self.automations:
                if isinstance(auto, CondensationPreventionAutomation):
                    auto._last_power_change[device_id] = ts_val
            if not self._closed:
                self.history_store.set_state(f"power_change:{device_id}", ts_val)

    def _setup_automations(self) -> None:
        with self._lock:
            # Preserve runtime cooldown/alert state across config reloads
            prev_power_change: dict[str, float] = dict(self._last_power_change)
            prev_last_notified: dict[str, float] = {}
            prev_active_alerts = []
            for existing in self.automations:
                if isinstance(existing, CondensationPreventionAutomation):
                    prev_power_change.update(existing._last_power_change)
                elif isinstance(existing, HealthAlertAutomation):
                    prev_last_notified = dict(existing._last_notified)
                    prev_active_alerts = list(existing._active_alerts)
            self._last_power_change.update(prev_power_change)

            self.automations.clear()

            # 1. Quiet Hours / Day-of-Week / Exclusion Schedule
            s_cfg = self.config.quiet_schedule
            schedule_auto: QuietScheduleAutomation | None = None
            if s_cfg.enabled:
                schedule_auto = QuietScheduleAutomation(
                    start_time=s_cfg.start_time,
                    end_time=s_cfg.end_time,
                    rooms=s_cfg.rooms,
                    night_mode=s_cfg.night_mode,
                    day_mode=s_cfg.day_mode,
                    night_days=s_cfg.night_days,
                    all_day_sleep_days=s_cfg.all_day_sleep_days,
                    exclusion_windows=s_cfg.exclusion_windows,
                    override_checker=self.is_device_overridden,
                    on_power_change=self.record_power_change,
                )
                self.automations.append(schedule_auto)

            # 2. Condensation Prevention & Sensor-Driven Power
            c_cfg = self.config.condensation
            if c_cfg.enabled:
                condensation_auto = CondensationPreventionAutomation(
                    glazing=c_cfg.glazing,
                    default_indoor_temp_c=c_cfg.default_indoor_temp_c,
                    min_target_rh=c_cfg.min_target_rh,
                    max_target_rh=c_cfg.max_target_rh,
                    safety_margin_c=c_cfg.safety_margin_c,
                    target_dew_point_c=c_cfg.target_dew_point_c,
                    rh_deadband=c_cfg.rh_deadband,
                    lookahead_hours=c_cfg.lookahead_hours,
                    auto_power=c_cfg.auto_power,
                    turn_on_offset_rh=c_cfg.turn_on_offset_rh,
                    turn_off_offset_rh=c_cfg.turn_off_offset_rh,
                    min_cycle_seconds=c_cfg.min_cycle_seconds,
                    exclusion_checker=(schedule_auto.is_room_excluded if schedule_auto else None),
                    override_checker=self.is_device_overridden,
                    on_power_change=self.record_power_change,
                )
                condensation_auto._last_power_change = dict(prev_power_change)
                self.automations.append(condensation_auto)

            # 3. Health, Tank-Full & Low-Battery Alerts
            a_cfg = self.config.alerts
            if a_cfg.enabled:
                alert_auto = HealthAlertAutomation(
                    low_battery_threshold_percent=a_cfg.low_battery_threshold_percent,
                    webhook_url=a_cfg.webhook_url,
                    webhook_cooldown_minutes=a_cfg.webhook_cooldown_minutes,
                )
                alert_auto._last_notified = prev_last_notified
                alert_auto._active_alerts = prev_active_alerts
                self.automations.append(alert_auto)

    def evaluate_cycle(self) -> list[str]:
        """
        Poll telemetry and run automations without holding the global state lock
        across network/hardware I/O, then update state and record room history.
        """
        with self._eval_lock:
            with self._lock:
                devices = list(self.registry.all_devices())
                automations = list(self.automations)

            # 1. Refresh devices outside the global lock so Web UI requests never stall
            for dev in devices:
                try:
                    dev.refresh()
                except Exception as e:
                    logger.warning("Error refreshing device %s: %s", dev.name, e)

            # 2. Evaluate automations outside self._lock (Tuya TCP + webhooks run here)
            results: list[str] = []
            cond_auto: CondensationPreventionAutomation | None = None
            for auto in automations:
                if isinstance(auto, CondensationPreventionAutomation):
                    cond_auto = auto
                try:
                    logs = auto.evaluate(self.registry, self.event_bus)
                    results.extend(logs)
                except Exception as e:
                    logger.error("Error evaluating %s: %s", auto.name, e, exc_info=True)
                    results.append(f"ERROR: {auto.name} failed: {e}")

            now_ts = time.time()

            # 3. Update dashboard logs and record historical room psychrometric snapshot
            with self._lock:
                self.last_evaluation_logs = list(results)
                self.last_evaluation_time = now_ts

                if cond_auto:
                    rooms_to_record = [
                        r
                        for r in self.registry.all_rooms()
                        if r != "outdoor"
                        and any(
                            dev.has_trait(TemperatureSensorTrait)
                            or dev.has_trait(HumiditySensorTrait)
                            or dev.has_trait(HumidityControlTrait)
                            for dev in self.registry.get_by_room(r)
                        )
                    ]
                    for room in rooms_to_record:
                        try:
                            dehum = next(
                                (
                                    d
                                    for d in self.registry.find_devices_with_trait(
                                        HumidityControlTrait
                                    )
                                    if d.room == room
                                ),
                                None,
                            )
                            r_status = cond_auto.compute_room_status(self.registry, room, dehum)
                            on_off = dehum.get_trait(OnOffTrait) if dehum else None
                            is_on = on_off.is_on if on_off else None
                            flags = dehum.get_trait(StatusFlagsTrait) if dehum else None
                            is_defrost = (
                                ("defrost" in flags.status_flags) if flags is not None else None
                            )
                            self.history_store.record_room_snapshot(
                                room=room,
                                status=r_status,
                                is_on=is_on,
                                is_defrost=is_defrost,
                                timestamp=now_ts,
                            )
                        except Exception as e:
                            logger.warning("Failed to record history snapshot for %s: %s", room, e)

            return results

    def update_config(self, updated_dict: dict[str, Any]) -> None:
        """Apply modified configuration, persist to disk, and reconfigure automations."""
        if not isinstance(updated_dict, dict):
            raise ValueError("Configuration update payload must be a JSON object.")

        disallowed = sorted(set(updated_dict.keys()) - EDITABLE_CONFIG_KEYS)
        if disallowed:
            raise ValueError(f"Unsupported or read-only config section(s): {', '.join(disallowed)}")

        weather_to_refresh: OpenMeteoWeatherDevice | None = None
        with self._lock:
            # Merge updated_dict onto current config to preserve unedited keys
            merged = self.config.to_dict()
            for k, v in updated_dict.items():
                if isinstance(v, dict) and isinstance(merged.get(k), dict):
                    merged[k].update(v)
                else:
                    merged[k] = v

            raw_path = self.config.raw_path
            new_cfg = SmartHomeConfig.from_dict(merged)
            new_cfg.raw_path = raw_path

            if raw_path:
                new_cfg.save()
                logger.info("Saved configuration updates to %s", raw_path)

            self.config = new_cfg
            self._setup_automations()

            # Update live weather station if location changed
            weather_dev = self.registry.get("weather_outdoor")
            if isinstance(weather_dev, OpenMeteoWeatherDevice):
                loc_changed = weather_dev.update_location(
                    new_cfg.location.latitude,
                    new_cfg.location.longitude,
                    f"Weather Station ({new_cfg.location.city})",
                )
                if loc_changed:
                    weather_to_refresh = weather_dev

        # Perform network/hardware I/O outside self._lock
        if weather_to_refresh is not None:
            weather_to_refresh.refresh(force=True)

        # Run immediate evaluation pass with new rules
        self.evaluate_cycle()

    def execute_device_command(
        self, device_id: str, action: str, **kwargs: Any
    ) -> tuple[bool, str]:
        """Execute a manual control command on a device and manage manual hold timers."""
        with self._lock:
            dev = self.registry.get(device_id)
            if not dev:
                return False, f"Device '{device_id}' not found."

        default_hold = float(
            kwargs.get("hold_minutes", self.config.condensation.manual_override_minutes)
        )

        if action == "set_override":
            mins = float(kwargs.get("minutes", self.config.condensation.manual_override_minutes))
            self.set_manual_override(device_id, mins)
            return True, f"Manual hold set for {int(mins)} min on '{dev.name}'"

        elif action == "clear_override":
            self.clear_manual_override(device_id)
            return True, f"Resumed automatic control on '{dev.name}'"

        elif action == "turn_on":
            on_off = dev.get_trait(OnOffTrait)
            if not on_off:
                return False, f"Device '{dev.name}' does not support power on/off."
            ok = on_off.turn_on()
            if ok:
                self.record_power_change(device_id)
                if default_hold > 0:
                    self.set_manual_override(device_id, default_hold)
            return ok, f"Turned ON '{dev.name}'" if ok else f"Failed to turn ON '{dev.name}'"

        elif action == "turn_off":
            on_off = dev.get_trait(OnOffTrait)
            if not on_off:
                return False, f"Device '{dev.name}' does not support power on/off."
            ok = on_off.turn_off()
            if ok:
                self.record_power_change(device_id)
                if default_hold > 0:
                    self.set_manual_override(device_id, default_hold)
            return ok, f"Turned OFF '{dev.name}'" if ok else f"Failed to turn OFF '{dev.name}'"

        elif action == "set_target":
            h_ctrl = dev.get_trait(HumidityControlTrait)
            if not h_ctrl:
                return False, f"Device '{dev.name}' does not support humidity control."
            target = int(kwargs.get("humidity", 55))
            ok = h_ctrl.set_target_humidity(target)
            if ok and default_hold > 0:
                self.set_manual_override(device_id, default_hold)
            msg = (
                f"Target set to {target}% on '{dev.name}'"
                if ok
                else f"Failed to set target on '{dev.name}'"
            )
            return ok, msg

        elif action == "set_mode":
            m_ctrl = dev.get_trait(ModeControlTrait)
            if not m_ctrl:
                return False, f"Device '{dev.name}' does not support mode control."
            mode = str(kwargs.get("mode", "manual"))
            ok = m_ctrl.set_mode(mode)
            if ok and default_hold > 0:
                self.set_manual_override(device_id, default_hold)
            msg = (
                f"Mode set to '{mode}' on '{dev.name}'"
                if ok
                else f"Failed to set mode on '{dev.name}'"
            )
            return ok, msg

        elif action == "refresh":
            dev.refresh()
            return True, f"Refreshed '{dev.name}'"

        return False, f"Unknown action '{action}'"

    def get_dashboard_state(self) -> dict[str, Any]:
        """Generate a complete snapshot of devices, metrics, alerts, and room psychrometrics."""
        with self._lock:
            devices_by_room: dict[str, list[dict[str, Any]]] = {}
            for room in self.registry.all_rooms():
                devices_by_room[room] = []

            # Find active automations for computing room status and alerts
            cond_auto: CondensationPreventionAutomation | None = None
            alert_auto: HealthAlertAutomation | None = None
            for auto in self.automations:
                if isinstance(auto, CondensationPreventionAutomation):
                    cond_auto = auto
                elif isinstance(auto, HealthAlertAutomation):
                    alert_auto = auto

            now_ts = time.time()
            lookahead_h = max(1, self.config.condensation.lookahead_hours or 12)
            for dev in self.registry.all_devices():
                room = dev.room
                if room not in devices_by_room:
                    devices_by_room[room] = []

                on_off = dev.get_trait(OnOffTrait)
                t_sensor = dev.get_trait(TemperatureSensorTrait)
                h_sensor = dev.get_trait(HumiditySensorTrait)
                h_ctrl = dev.get_trait(HumidityControlTrait)
                m_ctrl = dev.get_trait(ModeControlTrait)
                tank = dev.get_trait(TankLevelTrait)
                batt = dev.get_trait(BatteryLevelTrait)
                flags = dev.get_trait(StatusFlagsTrait)
                t_forecast = dev.get_trait(TemperatureForecastTrait)
                is_overridden, override_rem = self.is_device_overridden(dev.id, now_ts)

                dev_summary: dict[str, Any] = {
                    "id": dev.id,
                    "name": dev.name,
                    "room": dev.room,
                    "category": dev.category.value,
                    "is_online": dev.is_online,
                    "is_on": on_off.is_on if on_off else None,
                    "temperature_celsius": t_sensor.temperature_celsius if t_sensor else None,
                    "humidity_percent": h_sensor.humidity_percent if h_sensor else None,
                    "target_humidity_percent": h_ctrl.target_humidity_percent if h_ctrl else None,
                    "humidity_range": list(h_ctrl.humidity_range) if h_ctrl else None,
                    "humidity_step": h_ctrl.humidity_step if h_ctrl else None,
                    "current_mode": m_ctrl.current_mode if m_ctrl else None,
                    "supported_modes": m_ctrl.supported_modes if m_ctrl else [],
                    "is_tank_full": tank.is_tank_full if tank else None,
                    "battery_percent": batt.battery_percent if batt else None,
                    "status_flags": list(flags.status_flags) if flags else [],
                    "forecast_12h_min": (
                        t_forecast.min_forecast_temperature(lookahead_h) if t_forecast else None
                    ),
                    "forecast_lookahead_hours": lookahead_h if t_forecast else None,
                    "is_overridden": is_overridden,
                    "override_remaining_seconds": override_rem,
                }
                devices_by_room[room].append(dev_summary)

            # Compute room psychrometrics
            room_psychrometrics: dict[str, Any] = {}
            if cond_auto:
                rooms_to_compute = [
                    r
                    for r in self.registry.all_rooms()
                    if r != "outdoor"
                    and any(
                        dev.has_trait(TemperatureSensorTrait)
                        or dev.has_trait(HumiditySensorTrait)
                        or dev.has_trait(HumidityControlTrait)
                        for dev in self.registry.get_by_room(r)
                    )
                ]
                for room in rooms_to_compute:
                    dehum = next(
                        (
                            d
                            for d in self.registry.find_devices_with_trait(HumidityControlTrait)
                            if d.room == room
                        ),
                        None,
                    )
                    r_status = cond_auto.compute_room_status(self.registry, room, dehum)
                    room_psychrometrics[room] = r_status

            active_alerts = alert_auto.active_alerts if alert_auto else []

            return {
                "rooms": devices_by_room,
                "psychrometrics": room_psychrometrics,
                "alerts": active_alerts,
                "last_evaluation_time": self.last_evaluation_time,
                "last_evaluation_logs": self.last_evaluation_logs,
                "config": {
                    "condensation": self.config.condensation.to_dict(),
                    "quiet_schedule": self.config.quiet_schedule.to_dict(),
                    "alerts": self.config.alerts.to_dict(),
                    "polling_interval_seconds": self.config.polling_interval_seconds,
                    "web": self.config.web.to_dict(),
                },
            }

    def start(
        self,
        run_web: bool = True,
        host: str | None = None,
        port: int | None = None,
    ) -> None:
        """Start daemon loop and optionally start the embedded web server."""
        self._running = True
        self._register_signals()

        if run_web and self.config.web.enabled:
            from smarthome.web.server import SmartHomeWebServer

            bind_host = host or self.config.web.host
            bind_port = port or self.config.web.port
            self._web_server = SmartHomeWebServer(self, host=bind_host, port=bind_port)
            self._web_server.start_background()

        interval = max(10, self.config.polling_interval_seconds)
        logger.info(
            "Smart Home System initialized. Monitoring %d device(s) across %d room(s).",
            len(self.registry.all_devices()),
            len(self.registry.all_rooms()),
        )

        try:
            while self._running:
                try:
                    cycle_logs = self.evaluate_cycle()
                    for log_msg in cycle_logs:
                        logger.info("[Automation] %s", log_msg)
                except Exception as e:
                    logger.error("Error during automation cycle: %s", e, exc_info=True)

                for _ in range(interval):
                    if not self._running:
                        break
                    time.sleep(1.0)
        finally:
            self.stop()
            logger.info("Smart Home System shut down cleanly.")

    def stop(self) -> None:
        with self._lock:
            self._running = False
            if self._closed:
                return
            self._closed = True
            web_server = self._web_server
            self._web_server = None

        if web_server:
            web_server.stop()
        self.history_store.close()

    def _register_signals(self) -> None:
        def handle_signal(sig, frame):
            # Signal handlers must stay async-signal-safe: only set the loop exit flag.
            self._running = False

        signal.signal(signal.SIGINT, handle_signal)
        signal.signal(signal.SIGTERM, handle_signal)
