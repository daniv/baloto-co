"""Spanish-language date parsing and formatting helpers."""

import datetime

import dateparser
from babel.dates import format_date


def abbreviated_date(dte: datetime.date) -> str:
    """
    Format a date as an abbreviated Spanish string (`dd-MMM-yyyy`).

    Produces a compact date representation suitable for table columns or
    filenames.  The month is shown as a three-letter Spanish abbreviation.

    **Example output**: `"27-jul-2026"`

    :param dte: The date to format.
    :returns: The formatted date string.
    """
    return format_date(date=dte, format="dd-MMM-yyyy", locale="es")


def long_date(dte: datetime.date) -> str:
    """
    Format a date as a long Spanish string (`d 'de' MMMM 'de' y`).

    Produces a human-friendly date representation with the full month name.
    The result is title-cased and articles are lower-cased for readability.

    **Example output**: `"27 de Julio de 2026"`

    :param dte: The date to format.
    :returns: The formatted date string.
    """
    formatted = format_date(date=dte, format="d 'de' MMMM 'de' y", locale="es")
    return formatted.title().replace(" De ", " de ")


def full_date(dte: datetime.date) -> str:
    """
    Format a date as a full Spanish string (`EEEE, dd 'de' MMMM 'de' y`).

    Produces the most verbose date representation including the weekday name.
    The result is title-cased and articles are lower-cased for readability.

    **Example output**: `"Lunes, 27 de Julio de 2026"`

    :param dte: The date to format.
    :returns: The formatted date string.
    """
    formatted = format_date(date=dte, format="EEEE, dd 'de' MMMM 'de' y", locale="es")
    return formatted.title().replace(" De ", " de ")


def parse_spanish_date(value: object) -> datetime.date:
    """
    Parse a Spanish-language date string into a date.

    :param value: Raw date as provided by the caller (e.g. "3 de
        enero de 2026").
    :returns: The parsed date.
    :raises ValueError: If the value cannot be parsed as a date.
    :raises TypeError: If the value is not a string or datetime.date.
    """
    if isinstance(value, datetime.date):
        return value
    if not isinstance(value, str):
        message = "game_date must be a string or datetime.date"
        raise TypeError(message)

    parsed = dateparser.parse(value, languages=["es"], settings={"DATE_ORDER": "DMY", "STRICT_PARSING": True})

    if parsed is None:
        message = f"Invalid Spanish date: {value!r}. Expected a value such as '7 de Julio de 2026'."
        raise ValueError(message)

    return parsed.date()
