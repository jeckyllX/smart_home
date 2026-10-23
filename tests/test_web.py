"""
Integration tests for the embedded Smart Home Web Server and REST API.
"""

from __future__ import annotations

import json
import urllib.request
from pathlib import Path

from smarthome.app import SmartHomeApplication
from smarthome.config.schema import SmartHomeConfig
from smarthome.drivers.virtual.mock_climate import VirtualClimateSensor, VirtualDehumidifier
from smarthome.web.server import SmartHomeWebServer


def _setup_test_app(tmp_path: Path) -> SmartHomeApplication:
    config_file = tmp_path / "config.json"
    payload = {
        "location": {"latitude": 0.0, "longitude": 0.0, "city": "Test City"},
        "devices": [
            {
                "type": "tuya",
                "ip": "127.0.0.1",
                "dev_id": "test_dh",
                "local_key": "secret1234567890",
                "room": "bedroom",
                "name": "Bedroom Dehumidifier",
            }
        ],
        "condensation": {"enabled": True, "target_dew_point_c": 11.0},
        "quiet_schedule": {"enabled": True},
        "web": {"enabled": True, "port": 0},
    }
    cfg = SmartHomeConfig.from_dict(payload)
    cfg.save(config_file)

    app = SmartHomeApplication(cfg)

    # Register virtual test devices into registry for deterministic test control
    dehum = VirtualDehumidifier(
        device_id="test_dh",
        name="Bedroom Dehumidifier",
        room="bedroom",
    )
    sensor = VirtualClimateSensor(
        device_id="test_sensor",
        name="Bedroom Sensor",
        room="bedroom",
        initial_temp=21.0,
        initial_rh=58.0,
    )
    app.registry.register(dehum)
    app.registry.register(sensor)

    return app


def test_web_server_endpoints(tmp_path: Path):
    app = _setup_test_app(tmp_path)
    # Bind to ephemeral port (port 0) on localhost
    server = SmartHomeWebServer(app, host="127.0.0.1", port=0)
    server.start_background()

    try:
        # Determine allocated port
        assert server._server is not None
        assigned_port = server._server.server_port
        base_url = f"http://127.0.0.1:{assigned_port}"

        # 1. Test GET / (HTML dashboard)
        req = urllib.request.Request(f"{base_url}/")
        with urllib.request.urlopen(req) as resp:
            assert resp.status == 200
            content = resp.read().decode("utf-8")
            assert "SmartHome Climate" in content
            assert "Live" in content

        # 2. Test GET /api/state
        req = urllib.request.Request(f"{base_url}/api/state")
        with urllib.request.urlopen(req) as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode("utf-8"))
            assert "rooms" in data
            assert "bedroom" in data["rooms"]
            assert "psychrometrics" in data

        # 3. Test GET /api/config (local_key must be redacted)
        req = urllib.request.Request(f"{base_url}/api/config")
        with urllib.request.urlopen(req) as resp:
            assert resp.status == 200
            cfg_data = json.loads(resp.read().decode("utf-8"))
            assert "devices" in cfg_data
            assert cfg_data["devices"][0]["local_key"] == "********"

        # 4. Test POST /api/devices/<id>/command
        cmd_payload = json.dumps({"action": "set_target", "humidity": 50}).encode("utf-8")
        req = urllib.request.Request(
            f"{base_url}/api/devices/test_dh/command",
            data=cmd_payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req) as resp:
            assert resp.status == 200
            cmd_resp = json.loads(resp.read().decode("utf-8"))
            assert cmd_resp["success"] is True

        dehum = app.registry.get("test_dh")
        assert dehum is not None
        assert dehum.target_humidity_percent == 50

        # 5. Test PUT /api/config
        update_payload = json.dumps(
            {
                "condensation": {"min_target_rh": 45, "max_target_rh": 65},
                "quiet_schedule": {"all_day_sleep_days": ["sat"]},
            }
        ).encode("utf-8")
        req = urllib.request.Request(
            f"{base_url}/api/config",
            data=update_payload,
            headers={"Content-Type": "application/json"},
            method="PUT",
        )
        with urllib.request.urlopen(req) as resp:
            assert resp.status == 200
            put_resp = json.loads(resp.read().decode("utf-8"))
            assert put_resp["success"] is True

        assert app.config.condensation.min_target_rh == 45
        assert app.config.condensation.max_target_rh == 65
        assert app.config.quiet_schedule.all_day_sleep_days == ["sat"]

        # 6. Test POST /api/evaluate
        req = urllib.request.Request(f"{base_url}/api/evaluate", data=b"{}", method="POST")
        with urllib.request.urlopen(req) as resp:
            assert resp.status == 200
            eval_resp = json.loads(resp.read().decode("utf-8"))
            assert eval_resp["success"] is True
            assert isinstance(eval_resp["logs"], list)

    finally:
        server.stop()
