"""Numeric helpers for encoding lottery number combinations."""


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
