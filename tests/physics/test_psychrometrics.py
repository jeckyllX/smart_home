"""
Unit tests for psychrometric calculations and glazing models.
"""

import pytest

from smarthome.physics.psychrometrics import (
    GlazingType,
    calculate_condensation_safe_rh,
    calculate_dew_point,
    estimate_interior_glass_temp,
)


def test_dew_point_standard_conditions():
    # At 20°C and 50% RH, standard dew point is ~9.3°C
    dp = calculate_dew_point(20.0, 50.0)
    assert 9.0 <= dp <= 9.5


def test_dew_point_at_100_percent():
    # At 100% RH, dew point equals dry-bulb temperature
    dp = calculate_dew_point(15.0, 100.0)
    assert abs(dp - 15.0) < 0.2


def test_dew_point_invalid_rh():
    with pytest.raises(ValueError):
        calculate_dew_point(20.0, 0.0)


def test_estimate_glass_temp():
    # 20°C indoor, 0°C outdoor.
    # Double glazing factor = 0.25 -> drop is 0.25 * 20 = 5°C -> glass is 15°C
    glass = estimate_interior_glass_temp(20.0, 0.0, GlazingType.DOUBLE)
    assert glass == 15.0

    # Single glazing factor = 0.50 -> drop is 10°C -> glass is 10°C
    glass_single = estimate_interior_glass_temp(20.0, 0.0, GlazingType.SINGLE)
    assert glass_single == 10.0


def test_condensation_safe_target_subzero_outdoor():
    safe_target = calculate_condensation_safe_rh(
        indoor_temp_c=20.0,
        outdoor_temp_c=-10.0,
        glazing=GlazingType.DOUBLE,
        safety_margin_c=1.5,
        min_rh=40,
        max_rh=65,
    )
    assert 54 <= safe_target <= 58


def test_condensation_safe_clamped():
    safe_target = calculate_condensation_safe_rh(
        indoor_temp_c=20.0,
        outdoor_temp_c=15.0,
        glazing=GlazingType.DOUBLE,
        min_rh=40,
        max_rh=60,
    )
    assert safe_target == 60
