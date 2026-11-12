"""
Unit tests for HealthAlertAutomation (tank-full, low-battery, and webhook cooldown).
"""

from __future__ import annotations

from typing import Any

from smarthome.automations.alerts import HealthAlertAutomation
from smarthome.core.events import EventBus
from smarthome.core.registry import DeviceRegistry
from smarthome.core.traits import BatteryLevelTrait
from smarthome.drivers.virtual.mock_climate import VirtualClimateSensor, VirtualDehumidifier


class _BatteryClimateSensor(VirtualClimateSensor, BatteryLevelTrait):
    def __init__(self, device_id: str, name: str, room: str, battery: int):
        super().__init__(device_id=device_id, name=name, room=room)
        self._battery = battery
        self.register_trait(BatteryLevelTrait, self)

    @property
    def battery_percent(self) -> int | None:
        return self._battery


def test_health_alerts_tank_full_and_low_battery_and_webhook_cooldown():
    registry = DeviceRegistry()
    bus = EventBus()

    dehum = VirtualDehumidifier(
        device_id="dh_bed",
        name="Bedroom Dehumidifier",
        room="bedroom",
    )
    dehum.set_tank_full(True)
    sensor_low = _BatteryClimateSensor(
        device_id="tp_bed",
        name="Bedroom Sensor",
        room="bedroom",
        battery=10,
    )
    sensor_ok = _BatteryClimateSensor(
        device_id="tp_living",
        name="Living Sensor",
        room="living_room",
        battery=100,
    )
    registry.register(dehum)
    registry.register(sensor_low)
    registry.register(sensor_ok)

    sent_webhooks: list[tuple[str, dict[str, Any]]] = []

    def fake_sender(url: str, payload: dict[str, Any]) -> bool:
        sent_webhooks.append((url, payload))
        return True

    auto = HealthAlertAutomation(
        low_battery_threshold_percent=20,
        webhook_url="https://example.test/webhook",
        webhook_cooldown_minutes=60,
        webhook_sender=fake_sender,
    )

    # First pass at t=1000 triggers both alerts and sends 2 webhooks
    logs1 = auto.evaluate(registry, bus, now_ts=1000.0)
    assert len(auto.active_alerts) == 2
    keys = {a["key"] for a in auto.active_alerts}
    assert "tank_full:dh_bed" in keys
    assert "low_battery:tp_bed" in keys
    assert len(sent_webhooks) == 2
    assert any("Water tank is FULL" in line for line in logs1)

    # Second pass 5 minutes later (within 60m cooldown) keeps active alerts without re-sending
    auto.evaluate(registry, bus, now_ts=1300.0)
    assert len(auto.active_alerts) == 2
    assert len(sent_webhooks) == 2

    # Third pass 61 minutes later re-sends webhook
    auto.evaluate(registry, bus, now_ts=1000.0 + 3660.0)
    assert len(sent_webhooks) == 4

    # Tank emptied -> only low battery alert remains
    dehum.set_tank_full(False)
    auto.evaluate(registry, bus, now_ts=5000.0)
    assert len(auto.active_alerts) == 1
    assert auto.active_alerts[0]["key"] == "low_battery:tp_bed"


def test_health_alerts_offline_device():
    registry = DeviceRegistry()
    bus = EventBus()

    offline_sensor = VirtualClimateSensor(
        device_id="tp_offline",
        name="Offline Sensor",
        room="bedroom",
    )
    offline_sensor._online = False
    registry.register(offline_sensor)

    auto = HealthAlertAutomation()
    logs = auto.evaluate(registry, bus, now_ts=1000.0)
    assert len(auto.active_alerts) == 1
    assert auto.active_alerts[0]["key"] == "offline:tp_offline"
    assert auto.active_alerts[0]["severity"] == "warning"
    assert any("offline" in line.lower() for line in logs)
