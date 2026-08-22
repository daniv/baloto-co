def numbers_to_hex(n1: int, n2: int, n3: int, n4: int, n5: int, size: int) -> str:
    """Convert 5 lottery numbers to an uppercase hexadecimal bitmap.

    Builds a boolean array of length *size* where each index corresponds to a
    drawn number minus one.  `True` values at those indices are serialised
    as `"1"` and the rest as `"0"`, forming a binary string that is then
    converted to its hexadecimal equivalent.  Leading zeros are not preserved.

    :param n1: The first drawn number (1 … *size*).
    :param n2: The second drawn number (1 … *size*).
    :param n3: The third drawn number (1 … *size*).
    :param n4: The fourth drawn number (1 … *size*).
    :param n5: The fifth drawn number (1 … *size*).
    :param size: Bitmap length — must be 39 or 43.
    :returns: Uppercase hex string without the `"0x"` prefix.
    :raises ValueError: If *size* is not 39 or 43, or if any *nX* is outside
        the 1 … *size* range.
    """
    if size not in (39, 43):
        msg = f"size must be 39 or 43, got {size}"
        raise ValueError(msg)

    for idx, val in enumerate((n1, n2, n3, n4, n5), start=1):
        if val < 1 or val > size:
            msg = f"n{idx} must be between 1 and {size}, got {val}"
            raise ValueError(msg)

    bool_array = [False] * size
    bool_array[n1 - 1] = True
    bool_array[n2 - 1] = True
    bool_array[n3 - 1] = True
    bool_array[n4 - 1] = True
    bool_array[n5 - 1] = True

    binary_string = "".join("1" if value else "0" for value in bool_array)
    return format(int(binary_string, 2), "X")
