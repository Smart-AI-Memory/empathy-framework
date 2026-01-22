"""Memory system control panel commands.

Commands for managing Redis-backed short-term memory system.

Copyright 2025 Smart-AI-Memory
Licensed under Fair Source License 0.9
"""

import subprocess
import sys

import typer

# Create the memory Typer app
memory_app = typer.Typer(help="Memory system control panel")


@memory_app.command("status")
def memory_status() -> None:
    """Check memory system status (Redis, patterns, stats)."""
    subprocess.run(
        [sys.executable, "-m", "empathy_os.memory.control_panel", "status"], check=False
    )


@memory_app.command("start")
def memory_start() -> None:
    """Start Redis server for short-term memory."""
    subprocess.run(
        [sys.executable, "-m", "empathy_os.memory.control_panel", "start"], check=False
    )


@memory_app.command("stop")
def memory_stop() -> None:
    """Stop Redis server."""
    subprocess.run(
        [sys.executable, "-m", "empathy_os.memory.control_panel", "stop"], check=False
    )


@memory_app.command("stats")
def memory_stats() -> None:
    """Show memory statistics."""
    subprocess.run(
        [sys.executable, "-m", "empathy_os.memory.control_panel", "stats"], check=False
    )


@memory_app.command("patterns")
def memory_patterns() -> None:
    """List stored patterns."""
    subprocess.run(
        [sys.executable, "-m", "empathy_os.memory.control_panel", "patterns", "--list"],
        check=False,
    )
