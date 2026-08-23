"""Shared rich console instances for terminal output."""

from rich.console import Console

console = Console(color_system="truecolor", force_terminal=True)
error_console = Console(color_system="256", force_terminal=True, stderr=True)
