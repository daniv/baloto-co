import datetime

from babel.dates import format_date


def abbreviated_date(dte: datetime.date) -> str:
    """Format a date as an abbreviated Spanish string (`dd-MMM-yyyy`).

    Produces a compact date representation suitable for table columns or
    filenames.  The month is shown as a three-letter Spanish abbreviation.

    **Example output**: `"27-jul-2026"`

    :param dte: The date to format.
    :returns: The formatted date string.
    """
    return format_date(date=dte, format="dd-MMM-yyyy", locale="es")


def long_date(dte: datetime.date) -> str:
    """Format a date as a long Spanish string (`d 'de' MMMM 'de' y`).

    Produces a human-friendly date representation with the full month name.
    The result is title-cased and articles are lower-cased for readability.

    **Example output**: `"27 de Julio de 2026"`

    :param dte: The date to format.
    :returns: The formatted date string.
    """
    formatted = format_date(date=dte, format="d 'de' MMMM 'de' y", locale="es")
    return formatted.title().replace(" De ", " de ")


def full_date(dte: datetime.date) -> str:
    """Format a date as a full Spanish string (`EEEE, dd 'de' MMMM 'de' y`).

    Produces the most verbose date representation including the weekday name.
    The result is title-cased and articles are lower-cased for readability.

    **Example output**: `"Lunes, 27 de Julio de 2026"`

    :param dte: The date to format.
    :returns: The formatted date string.
    """
    formatted = format_date(date=dte, format="EEEE, dd 'de' MMMM 'de' y", locale="es")
    return formatted.title().replace(" De ", " de ")
