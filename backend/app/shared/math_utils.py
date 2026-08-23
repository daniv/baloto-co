"""Numeric helpers for encoding lottery number combinations."""

from babel.numbers import NumberFormatError, format_decimal, parse_number


def numbers_to_hex(numbers: list[int], size: int) -> str:
    """
    Convert drawn lottery numbers to an uppercase hexadecimal bitmap.

    Builds a boolean array of length *size* where each index corresponds to a
    drawn number minus one.  `True` values at those indices are serialised
    as `"1"` and the rest as `"0"`, forming a binary string that is then
    converted to its hexadecimal equivalent.  Leading zeros are not preserved.

    :param numbers: The drawn numbers (each 1 … *size*).
    :param size: Bitmap length — must be 39 or 43.
    :returns: Uppercase hex string without the `"0x"` prefix.
    :raises ValueError: If *size* is not 39 or 43, or if any number in
        *numbers* is outside the 1 … *size* range.
    """
    if size not in (39, 43):
        msg = f"size must be 39 or 43, got {size}"
        raise ValueError(msg)

    for idx, val in enumerate(numbers, start=1):
        if val < 1 or val > size:
            msg = f"n{idx} must be between 1 and {size}, got {val}"
            raise ValueError(msg)

    bool_array = [False] * size
    for val in numbers:
        bool_array[val - 1] = True

    binary_string = "".join("1" if value else "0" for value in bool_array)
    return format(int(binary_string, 2), "X")


def parse_millions_to_pesos(localized_millions: str) -> int:
    """
    Convert a Spanish-formatted amount in millions into pesos.

    A value such as ``"46.400"`` is converted into ``46_400_000_000``.

    :param localized_millions: Spanish-formatted amount expressed in millions.
    :return: Complete amount expressed in pesos.
    :raises ValueError: If the supplied value is not a valid Spanish-formatted integer.
    """
    return es_localized_to_int(localized_millions) * 1_000_000


def es_localized_to_int(value: str) -> int:
    """
    Convert a Spanish-formatted integer into an integer.

    A value such as ``"2.679"`` is converted into ``2679``.

    :param value: Spanish-formatted integer text.
    :return: Parsed integer.
    :raises ValueError: If the value is empty or is not a valid
        Spanish-formatted integer.
    """
    normalized_value = value.strip()

    if not normalized_value:
        error_message = "The localized integer value cannot be empty."
        raise ValueError(error_message)

    try:
        return int(parse_number(normalized_value, locale="es"))
    except NumberFormatError as error:
        error_message = f"Invalid Spanish-formatted integer: {value!r}."
        raise ValueError(error_message) from error


def int_to_localized_es(value: int) -> str:
    """
    Convert an integer into localized numeric text.

    An integer such as ``2679`` is formatted as ``"2.679"`` when the Spanish
    locale is used.

    :param value: Integer to format.
    :return: Localized integer representation.
    """
    return format_decimal(
        value,
        format="#,##0",
        locale="es",
        decimal_quantization=False,
        group_separator=True,
    )
