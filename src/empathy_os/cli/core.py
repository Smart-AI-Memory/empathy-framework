"""Core utilities for Empathy Framework CLI.

Shared utilities, console configuration, and helper functions used across
all CLI command modules.

Copyright 2025 Smart-AI-Memory
Licensed under Fair Source License 0.9
"""

from importlib.metadata import version as get_version

import typer
from rich.console import Console

# Shared Rich console instance for all CLI commands
console = Console()


def get_empathy_version() -> str:
    """Get the installed version of empathy-framework."""
    try:
        return get_version("empathy-framework")
    except Exception:  # noqa: BLE001
        # INTENTIONAL: Version detection fallback for dev installs
        return "dev"


def version_callback(value: bool) -> None:
    """Show version and exit."""
    if value:
        console.print(f"[bold blue]Empathy Framework[/bold blue] v{get_empathy_version()}")
        raise typer.Exit()
