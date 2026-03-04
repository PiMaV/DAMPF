# test_key_lut.py - Unit tests for key_lut module

import pytest
from key_lut import (
    unit_scale,
    unit_to_exponent,
    exponent_to_unit,
    convert_val_to_si,
    format_val_unit,
    is_quantitative_val,
    get_unit_info,
)


def test_unit_scale():
    assert unit_scale("us") == 1e-6
    assert unit_scale("ms") == 1e-3
    assert unit_scale("s") == 1.0
    assert unit_scale("mm") == 1e-3
    assert unit_scale("m") == 1.0
    assert unit_scale("V") == 1.0


def test_unit_to_exponent():
    assert unit_to_exponent("us") == -6
    assert unit_to_exponent("ms") == -3
    assert unit_to_exponent("s") == 0
    assert unit_to_exponent("mm") == -3
    assert unit_to_exponent("m") == 0


def test_exponent_to_unit():
    assert exponent_to_unit("s", -6) == "us"
    assert exponent_to_unit("s", -3) == "ms"
    assert exponent_to_unit("s", 0) == "s"
    assert exponent_to_unit("m", -3) == "mm"
    assert exponent_to_unit("%", -3) == "%"


def test_convert_val_to_si():
    assert convert_val_to_si(500, "us") == 0.0005
    assert convert_val_to_si(10, "mm") == 0.01


def test_format_val_unit():
    assert format_val_unit({"val": 500, "unit": "us"}) == "500 us"
    assert format_val_unit(42) == "42"
    assert format_val_unit(None) == ""


def test_is_quantitative_val():
    assert is_quantitative_val({"val": 500, "unit": "us"}) is True
    assert is_quantitative_val(42) is False
    assert is_quantitative_val("text") is False


def test_get_unit_info():
    info = get_unit_info("exposure")
    assert info is not None
    assert info[0] == "s"
    info = get_unit_info("lengths")
    assert info is not None
    assert info[0] == "m"
    assert get_unit_info("unknown_key") is None
