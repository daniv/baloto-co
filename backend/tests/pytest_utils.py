"""Provide reusable pytest helpers for marker filtering and debugger detection."""

import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

    import pytest


def get_skiplist(
    item: pytest.Item,
    values: Sequence[str],
    value_name: str,
) -> list[str]:
    """
    Determine which values should be skipped based on pytest markers.

    :param item: Pytest test item or collection node containing the markers.
    :param values: Supported values to evaluate against the markers.
    :param value_name: Value category, such as ``browser`` or ``game``.
    :return: Values excluded by the applicable pytest marker.
    """
    skipped_values: list[str] = []

    only_marker = item.get_closest_marker(f"only_{value_name}")
    if only_marker:
        skipped_values = list(values)
        skipped_values.remove(only_marker.args[0])

    skip_marker = item.get_closest_marker(f"skip_{value_name}")
    if skip_marker:
        skipped_values.append(skip_marker.args[0])

    return skipped_values


def is_debugger_attached() -> bool:
    """
    Check whether a debugger is currently attached.

    :return: True when a debugger is attached; otherwise, False.
    """
    pydevd = sys.modules.get("pydevd")
    if not pydevd or not hasattr(pydevd, "get_global_debugger"):
        return False

    debugger = pydevd.get_global_debugger()
    if not debugger or not hasattr(debugger, "is_attached"):
        return False

    return debugger.is_attached()
