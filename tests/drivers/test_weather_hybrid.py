"""
Unit tests for the Hybrid Weather Driver (METAR live station + Open-Meteo forecast).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from smarthome.drivers.weather.open_meteo import OpenMeteoWeatherDevice


def test_hybrid_weather_uses_nearest_physical_station():
    # Generic synthetic coordinates
    dev = OpenMeteoWeatherDevice(
        device_id="weather_outdoor",
        name="Outdoor Weather",
        latitude=10.0,
        longitude=20.0,
    )

    open_meteo_mock = {
        "current": {"temperature_2m": 7.2, "relative_humidity_2m": 88.0},
        "hourly": {"temperature_2m": [7.0, 6.8, 6.5, 6.0, 5.5]},
    }

    # Two physical stations: Station FAR1 (~150km away) and Station NEAR (~15km away)
    aviation_mock = [
        {
            "icaoId": "FAR1",
            "lat": 11.5,
            "lon": 21.5,
            "temp": 4.0,
            "dewp": 3.0,
        },
        {
            "icaoId": "NEAR",
            "lat": 10.1,
            "lon": 20.1,
            "temp": 2.0,
            "dewp": 2.0,
        },
    ]

    def mock_requests_get(url: str, *args, **kwargs):
        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.status_code = 200
        if "api.open-meteo.com" in url:
            mock_resp.json.return_value = open_meteo_mock
        elif "aviationweather.gov" in url:
            mock_resp.json.return_value = aviation_mock
        return mock_resp

    with patch("requests.get", side_effect=mock_requests_get):
        ok = dev.refresh(force=True)
        assert ok is True

    # Real physical ground temperature from closest station (NEAR) must override model
    assert dev.temperature_celsius == 2.0
    assert dev.humidity_percent == 100.0  # dew point 2.0 at temp 2.0 is 100% RH
    assert dev.station_source == "Physical (NEAR)"
    assert dev.status_flags == ("Physical (NEAR)",)

    # 12h forecast from Open-Meteo is preserved
    assert dev.min_forecast_temperature(12) == 5.5
    assert dev.hourly_temperature_forecast_celsius == (7.0, 6.8, 6.5, 6.0, 5.5)


def test_hybrid_weather_falls_back_to_open_meteo_when_metar_fails():
    dev = OpenMeteoWeatherDevice(
        device_id="weather_outdoor",
        name="Outdoor Weather",
        latitude=0.0,
        longitude=0.0,
    )

    open_meteo_mock = {
        "current": {"temperature_2m": 12.5, "relative_humidity_2m": 65.0},
        "hourly": {"temperature_2m": [12.0, 11.5, 11.0]},
    }

    def mock_requests_get(url: str, *args, **kwargs):
        mock_resp = MagicMock()
        if "api.open-meteo.com" in url:
            mock_resp.ok = True
            mock_resp.status_code = 200
            mock_resp.json.return_value = open_meteo_mock
            return mock_resp
        else:
            # Aviation weather fails (e.g. 500 error or network issue)
            mock_resp.ok = False
            mock_resp.status_code = 500
            return mock_resp

    with patch("requests.get", side_effect=mock_requests_get):
        ok = dev.refresh(force=True)
        assert ok is True

    # Falls back gracefully to Open-Meteo model values
    assert dev.temperature_celsius == 12.5
    assert dev.humidity_percent == 65.0
    assert dev.station_source == "Open-Meteo Model"
    assert dev.status_flags == ("Open-Meteo Model",)
    assert dev.min_forecast_temperature(3) == 11.0
