"""
Unit tests for the Meaco Arete Two Tuya driver.

These exercise the pure status-flag decoding and the reported humidity range and
step; they do not connect to a device.
"""

from smarthome.drivers.tuya.meaco_arete import MeacoAreteTuyaDevice, decode_status_flags


def _device() -> MeacoAreteTuyaDevice:
    return MeacoAreteTuyaDevice(
        device_id="dev_1",
        name="Test Unit",
        ip="192.0.2.1",
        local_key="1234567890123456",
    )


def test_decode_status_flags_bit_map():
    assert decode_status_flags(0) == ()
    assert decode_status_flags(1) == ("tankfull",)
    assert decode_status_flags(2) == ("defrost",)
    assert decode_status_flags(128) == ("wet",)
    assert decode_status_flags(3) == ("tankfull", "defrost")
    assert decode_status_flags(1 | 4) == ("tankfull", "E1")


def test_wet_flag_is_not_tank_full():
    # DP 19 = 128 reports 'wet', which is the built-in sensor reading above 70%.
    dev = _device()
    dev._cached_dps["19"] = 128
    assert dev.status_flags == ("wet",)
    assert dev.is_tank_full is False

    dev._cached_dps["19"] = 1
    assert dev.status_flags == ("tankfull",)
    assert dev.is_tank_full is True


def test_humidity_range_and_step():
    dev = _device()
    assert dev.humidity_range == (35, 70)
    assert dev.humidity_step == 5


def test_missing_status_dp_is_empty():
    dev = _device()
    assert dev.status_flags == ()
