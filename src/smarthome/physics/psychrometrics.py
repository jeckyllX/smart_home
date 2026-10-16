"""
Psychrometric and thermodynamic calculations.
Implements the Magnus-Tetens formula for water vapour saturation and thermal boundary gradients.
"""

from __future__ import annotations

import math
from enum import Enum

MAGNUS_A = 17.27
MAGNUS_B = 237.7  # in degrees Celsius


class GlazingType(str, Enum):
    SINGLE = "single"
    DOUBLE = "double"
    TRIPLE = "triple"

    @property
    def temperature_drop_factor(self) -> float:
        """
        Fractional temperature gradient from interior air to interior window glass.
        Single pane: ~0.50, Double pane: ~0.25, Triple pane: ~0.15.
        """
        factors = {
            GlazingType.SINGLE: 0.50,
            GlazingType.DOUBLE: 0.25,
            GlazingType.TRIPLE: 0.15,
        }
        return factors[self]


def calculate_dew_point(temp_c: float, rh_pct: float) -> float:
    """
    Calculate dew point temperature in degrees Celsius using the Magnus-Tetens formula.
    """
    if rh_pct <= 0:
        raise ValueError("Relative humidity must be strictly positive (> 0%).")

    clamped_rh = max(0.001, min(100.0, rh_pct))
    rh_fraction = clamped_rh / 100.0

    alpha = ((MAGNUS_A * temp_c) / (MAGNUS_B + temp_c)) + math.log(rh_fraction)
    dew_point = (MAGNUS_B * alpha) / (MAGNUS_A - alpha)
    return round(dew_point, 2)


def estimate_interior_glass_temp(
    indoor_temp_c: float,
    outdoor_temp_c: float,
    glazing: GlazingType = GlazingType.DOUBLE,
) -> float:
    """
    Estimate the temperature of the interior glass surface.
    """
    delta_t = indoor_temp_c - outdoor_temp_c
    if delta_t <= 0:
        return indoor_temp_c

    factor = glazing.temperature_drop_factor
    glass_temp = indoor_temp_c - (factor * delta_t)
    return round(glass_temp, 2)


def calculate_rh_for_dew_point(temp_c: float, dew_point_c: float) -> float:
    """
    Relative humidity in percent that yields dew_point_c at temp_c.
    Inverse of calculate_dew_point.
    """
    alpha_dew = (MAGNUS_A * dew_point_c) / (MAGNUS_B + dew_point_c)
    alpha_in = (MAGNUS_A * temp_c) / (MAGNUS_B + temp_c)
    rh = 100.0 * math.exp(alpha_dew - alpha_in)
    return max(0.001, min(100.0, rh))


def resolve_safe_dew_point(
    indoor_temp_c: float,
    outdoor_temp_c: float,
    glazing: GlazingType = GlazingType.DOUBLE,
    safety_margin_c: float = 1.5,
) -> float:
    """
    Highest indoor dew point that keeps the interior glass surface at least
    safety_margin_c above the dew point.
    """
    glass_temp = estimate_interior_glass_temp(indoor_temp_c, outdoor_temp_c, glazing)
    return round(glass_temp - safety_margin_c, 2)


def quantize_rh(value: float, step: int, min_rh: int, max_rh: int) -> int:
    """
    Round value to the nearest multiple of step, then clamp to [min_rh, max_rh].
    """
    if step < 1:
        step = 1
    clamped = max(min_rh, min(max_rh, value))
    rounded = int(round(clamped / step)) * step
    return max(min_rh, min(max_rh, rounded))


def calculate_condensation_safe_rh(
    indoor_temp_c: float,
    outdoor_temp_c: float,
    glazing: GlazingType = GlazingType.DOUBLE,
    safety_margin_c: float = 1.5,
    min_rh: int = 40,
    max_rh: int = 65,
) -> int:
    """
    Highest indoor relative humidity (clamped to [min_rh, max_rh]) that keeps the
    indoor dew point safety_margin_c below the interior glass temperature.
    """
    safe_dew_point = resolve_safe_dew_point(indoor_temp_c, outdoor_temp_c, glazing, safety_margin_c)
    safe_target = int(round(calculate_rh_for_dew_point(indoor_temp_c, safe_dew_point)))
    return max(min_rh, min(max_rh, safe_target))
