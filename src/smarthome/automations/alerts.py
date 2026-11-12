"""
Trait-based health, tank-full, and low-battery alert automation.
Monitors TankLevelTrait, BatteryLevelTrait, and device connectivity,
exposes active alerts for the dashboard, and optionally dispatches webhooks.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, Callable

import requests

from smarthome.automations.base import Automation
from smarthome.core.events import EventBus
from smarthome.core.registry import DeviceRegistry
from smarthome.core.traits import BatteryLevelTrait, TankLevelTrait

logger = logging.getLogger("HealthAlertAutomation")


@dataclass(frozen=True)
class HealthAlert:
    """Structured active alert item."""

    key: str
    severity: str  # "critical" | "warning"
    device_id: str
    device_name: str
    room: str
    message: str
    timestamp: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "severity": self.severity,
            "device_id": self.device_id,
            "device_name": self.device_name,
            "room": self.room,
            "message": self.message,
            "timestamp": self.timestamp,
        }


class HealthAlertAutomation(Automation):
    """
    Evaluates device traits to detect actionable system alerts:
      - Water tank full (TankLevelTrait)
      - Low sensor battery (BatteryLevelTrait)
    Optionally posts newly triggered alerts to a webhook URL with cooldown deduplication.
    """

    def __init__(
        self,
        name: str = "HealthAlerts",
        enabled: bool = True,
        low_battery_threshold_percent: int = 20,
        webhook_url: str | None = None,
        webhook_cooldown_minutes: int = 60,
        webhook_sender: Callable[[str, dict[str, Any]], bool] | None = None,
    ):
        super().__init__(name=name, enabled=enabled)
        self.low_battery_threshold_percent = low_battery_threshold_percent
        self.webhook_url = webhook_url
        self.webhook_cooldown_seconds = max(60, webhook_cooldown_minutes * 60)
        self._webhook_sender = webhook_sender or self._default_webhook_sender
        self._active_alerts: list[HealthAlert] = []
        self._last_notified: dict[str, float] = {}

    @property
    def active_alerts(self) -> list[dict[str, Any]]:
        """List of currently active alert dictionaries."""
        return [a.to_dict() for a in self._active_alerts]

    def evaluate(
        self,
        registry: DeviceRegistry,
        event_bus: EventBus,
        now_ts: float | None = None,
    ) -> list[str]:
        if not self.enabled:
            self._active_alerts = []
            return []

        ts = now_ts if now_ts is not None else time.time()
        alerts: list[HealthAlert] = []
        logs: list[str] = []

        # 1. Check water tank status on all devices with TankLevelTrait
        for dev in registry.find_devices_with_trait(TankLevelTrait):
            tank = dev.require_trait(TankLevelTrait)
            if tank.is_tank_full:
                alert = HealthAlert(
                    key=f"tank_full:{dev.id}",
                    severity="critical",
                    device_id=dev.id,
                    device_name=dev.name,
                    room=dev.room,
                    message=(
                        f"{dev.name} ({dev.room}): Water tank is FULL — "
                        "empty tank to resume dehumidification."
                    ),
                    timestamp=ts,
                )
                alerts.append(alert)
                logs.append(f"[ALERT: CRITICAL] {alert.message}")

        # 2. Check battery levels on all devices with BatteryLevelTrait
        for dev in registry.find_devices_with_trait(BatteryLevelTrait):
            batt = dev.require_trait(BatteryLevelTrait)
            pct = batt.battery_percent
            if pct is not None and pct <= self.low_battery_threshold_percent:
                alert = HealthAlert(
                    key=f"low_battery:{dev.id}",
                    severity="warning",
                    device_id=dev.id,
                    device_name=dev.name,
                    room=dev.room,
                    message=f"{dev.name} ({dev.room}): Battery low ({pct}%).",
                    timestamp=ts,
                )
                alerts.append(alert)
                logs.append(f"[ALERT: WARNING] {alert.message}")

        # 3. Check device connectivity
        for dev in registry.all_devices():
            if not dev.is_online:
                alert = HealthAlert(
                    key=f"offline:{dev.id}",
                    severity="warning",
                    device_id=dev.id,
                    device_name=dev.name,
                    room=dev.room,
                    message=f"{dev.name} ({dev.room}): Device is offline or unreachable.",
                    timestamp=ts,
                )
                alerts.append(alert)
                logs.append(f"[ALERT: WARNING] {alert.message}")

        self._active_alerts = alerts

        # 4. Dispatch webhook notifications for newly triggered / cooldown-expired alerts
        if self.webhook_url and alerts:
            for alert in alerts:
                last_sent = self._last_notified.get(alert.key)
                if last_sent is None or (ts - last_sent) >= self.webhook_cooldown_seconds:
                    payload = {
                        "title": f"SmartHome {alert.severity.upper()} Alert",
                        "text": alert.message,
                        "message": alert.message,
                        "alert": alert.to_dict(),
                    }
                    if self._webhook_sender(self.webhook_url, payload):
                        self._last_notified[alert.key] = ts
                        logs.append(f"Dispatched webhook notification for '{alert.key}'.")

        return logs

    @staticmethod
    def _default_webhook_sender(url: str, payload: dict[str, Any]) -> bool:
        try:
            resp = requests.post(url, json=payload, timeout=5.0)
            resp.raise_for_status()
            return True
        except Exception as e:
            logger.warning("Failed to dispatch alert webhook to %s: %s", url, e)
            return False
