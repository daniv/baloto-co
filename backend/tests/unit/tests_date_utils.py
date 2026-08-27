"""
Verify Spanish date-formatting helpers used by lottery result schemas.

The module tests abbreviated, long, and full date representations across
representative calendar values. It ensures formatting remains consistent,
localized, and suitable for API responses and computed schema properties.
"""

from datetime import date

import pytest
from app.shared.date_utils import abbreviated_date, full_date, long_date


@pytest.mark.unit
def test_abbreviated_date_format() -> None:
    """
    Verify that abbreviated_date returns dd-MMM-yyyy format.

    A mid-year date must produce the expected day-month-year pattern with
    a three-letter Spanish month abbreviation.
    """
    result = abbreviated_date(date(2026, 7, 27))
    assert result == "27-jul-2026", "Unexpected abbreviated_date output."


@pytest.mark.unit
def test_abbreviated_date_leading_zero() -> None:
    """
    Verify that single-digit days get a leading zero in abbreviated_date.

    The dd format specifier must zero-pad the day of the month.
    """
    result = abbreviated_date(date(2026, 3, 5))
    assert result == "05-mar-2026", "Unexpected abbreviated_date output."


@pytest.mark.unit
def test_abbreviated_date_end_of_year() -> None:
    """
    Verify abbreviated_date handles the last day of December correctly.

    The month abbreviation for December in Spanish locale must be dic.
    """
    result = abbreviated_date(date(2026, 12, 31))
    assert result == "31-dic-2026", "Unexpected abbreviated_date output."


@pytest.mark.unit
def test_long_date_format() -> None:
    """
    Verify that long_date returns d de MMMM de y format.

    The full month name must appear in Spanish, title-cased, with lower-case
    propositions (de).
    """
    result = long_date(date(2026, 7, 27))
    assert result == "27 de Julio de 2026", "Unexpected long_date output."


@pytest.mark.unit
def test_long_date_single_digit_day() -> None:
    """
    Verify that long_date does NOT zero-pad the day.

    The d format specifier (without dd) must keep the day as a
    single digit when applicable.
    """
    result = long_date(date(2026, 3, 5))
    assert result == "5 de Marzo de 2026", "Unexpected long_date output."


@pytest.mark.unit
def test_full_date_format() -> None:
    """
    Verify that full_date returns EEEE, dd de MMMM de y format.

    The weekday name must appear in Spanish, followed by the full date with
    a leading zero on the day and lower-case propositions.
    """
    result = full_date(date(2026, 7, 27))
    assert result == "Lunes, 27 de Julio de 2026", "Unexpected full_date output."


@pytest.mark.unit
def test_full_date_single_digit_day() -> None:
    """
    Verify that full_date zero-pads the day with dd.

    Unlike long_date, the full format uses dd so single-digit days
    must include a leading zero.
    """
    result = full_date(date(2026, 3, 5))
    assert result == "Jueves, 05 de Marzo de 2026", "Unexpected full_date output."
