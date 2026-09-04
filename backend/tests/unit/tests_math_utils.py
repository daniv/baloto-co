"""
Verify deterministic lottery-number encoding utilities.

The module tests conversion of validated number combinations into stable
hexadecimal identifiers. It covers representative combinations, boundary
values, output consistency, and invalid input scenarios used by result schemas.
"""

import pytest
from app.shared.math_utils import abbreviate_pesos, numbers_to_hex


@pytest.mark.unit
def test_numbers_to_hex_typical() -> None:
    """
    Verify typical medium-range numbers produce the correct hex bitmap.

    Draw (5, 12, 18, 25, 33) with a 43-position bitmap must yield the
    expected hex string 4082040400.
    """
    result = numbers_to_hex([5, 12, 18, 25, 33], 43)
    assert result == "4082040400", "Unexpected numbers_to_hex output."


@pytest.mark.unit
def test_numbers_to_hex_min_values() -> None:
    """
    Verify the lowest possible numbers (1-5) produce the correct hex bitmap.

    The first five bitmap positions are set to True, translating to
    hex 7C000000000 for a 43-position bitmap.
    """
    result = numbers_to_hex([1, 2, 3, 4, 5], 43)
    assert result == "7C000000000", "Unexpected numbers_to_hex output."


@pytest.mark.unit
def test_numbers_to_hex_max_values_size_39() -> None:
    """
    Verify the highest valid numbers for size=39 produce the correct hex bitmap.

    Numbers (35-39) with a 39-position bitmap set only the last five bits.
    Leading zeros are dropped, so the result is 1F.
    """
    result = numbers_to_hex([35, 36, 37, 38, 39], 39)
    assert result == "1F", "Unexpected numbers_to_hex output."


@pytest.mark.unit
def test_numbers_to_hex_max_values_size_43() -> None:
    """
    Verify the highest valid numbers for size=43 produce a correct hex bitmap.

    Numbers (35-38, 43) create a non-trailing bitmap that preserves a
    middle zero gap, producing hex 1E1.
    """
    result = numbers_to_hex([35, 36, 37, 38, 43], 43)
    assert result == "1E1", "Unexpected numbers_to_hex output."


@pytest.mark.unit
def test_numbers_to_hex_spread_size_43() -> None:
    """
    Verify spread numbers across a 43-position bitmap produce the correct hex.

    Numbers (1, 10, 20, 30, 40) exercise non-consecutive positions.
    """
    result = numbers_to_hex([1, 10, 20, 30, 40], 43)
    assert result == "40200802008", "Unexpected numbers_to_hex output."


@pytest.mark.unit
def test_numbers_to_hex_mid_range_size_39() -> None:
    """
    Verify mid-range numbers with a 39-position bitmap produce the correct hex.

    Numbers (5, 10, 15, 20, 25) test a 39-length bitmap with non-edge values.
    """
    result = numbers_to_hex([5, 10, 15, 20, 25], 39)
    assert result == "421084000", "Unexpected numbers_to_hex output."


@pytest.mark.unit
@pytest.mark.parametrize(
    ("n1", "n2", "n3", "n4", "n5", "size", "expected_msg"),
    [
        pytest.param(0, 2, 3, 4, 5, 43, r"n1 must be between 1 and 43", id="n1_below_1"),
        pytest.param(-1, 2, 3, 4, 5, 43, r"n1 must be between 1 and 43", id="n1_negative"),
        pytest.param(1, 2, 3, 4, 44, 43, r"n5 must be between 1 and 43", id="n5_above_43"),
        pytest.param(1, 2, 3, 4, 5, 0, r"size must be 39 or 43", id="size_zero"),
        pytest.param(1, 2, 3, 4, 5, 50, r"size must be 39 or 43", id="size_invalid"),
        pytest.param(40, 41, 42, 43, 44, 39, r"n1 must be between 1 and 39", id="n1_above_39"),
    ],
)
def test_numbers_to_hex_invalid_input_raises_error(
    n1: int, n2: int, n3: int, n4: int, n5: int, size: int, expected_msg: str
) -> None:
    """
    Verify invalid inputs raise ValueError with a descriptive message.

    Covers numbers below 1, above size, and invalid size values (not 39 or 43).
    """
    with pytest.raises(ValueError, match=expected_msg):
        numbers_to_hex([n1, n2, n3, n4, n5], size)


@pytest.mark.unit
def test_abbreviate_pesos_millions() -> None:
    """
    Verify a whole number of millions formats as a dollar-prefixed M amount.

    ``120_000_000 pesos`` must render as ``"$120M"``.
    """
    result = abbreviate_pesos(120_000_000)
    assert result == "$120M", "Unexpected abbreviate_pesos output."


@pytest.mark.unit
def test_abbreviate_pesos_billions_in_millions() -> None:
    """
    Verify billions render as a grouped millions figure with an M suffix.

    ``2_500_000_000 pesos`` is 2500 million and must render as ``"$2.500M"``.
    """
    result = abbreviate_pesos(2_500_000_000)
    assert result == "$2.500M", "Unexpected abbreviate_pesos output."
