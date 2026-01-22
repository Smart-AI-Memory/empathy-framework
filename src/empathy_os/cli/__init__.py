"""Unified CLI for Empathy Framework.

A single entry point for all Empathy Framework commands using Typer.

Usage:
    empathy --help                    # Show all commands
    empathy memory status             # Memory control panel
    empathy provider                  # Show provider config
    empathy scan .                    # Scan codebase
    empathy morning                   # Start-of-day briefing

Copyright 2025 Smart-AI-Memory
Licensed under Fair Source License 0.9
"""

import subprocess
import sys
from pathlib import Path

import typer

# Re-export legacy CLI functions for backward compatibility
# These functions are defined in the sibling cli.py module (now cli_legacy)
# Tests and other code may import them from empathy_os.cli
try:
    # Import from the legacy module using relative import workaround
    # Since this package shadows cli.py, we need to import it explicitly
    import importlib.util
    import os

    _legacy_cli_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "cli.py")
    if os.path.exists(_legacy_cli_path):
        _spec = importlib.util.spec_from_file_location("cli_legacy", _legacy_cli_path)
        _cli_legacy = importlib.util.module_from_spec(_spec)
        _spec.loader.exec_module(_cli_legacy)

        # Re-export legacy functions
        cmd_info = _cli_legacy.cmd_info
        cmd_init = _cli_legacy.cmd_init
        cmd_version = _cli_legacy.cmd_version
        cmd_validate = _cli_legacy.cmd_validate
        cmd_patterns_list = _cli_legacy.cmd_patterns_list
        cmd_patterns_export = _cli_legacy.cmd_patterns_export
        cmd_metrics_show = _cli_legacy.cmd_metrics_show
        cmd_state_list = _cli_legacy.cmd_state_list
        cmd_run = _cli_legacy.cmd_run
        cmd_inspect = _cli_legacy.cmd_inspect
        cmd_export = _cli_legacy.cmd_export
        cmd_import = _cli_legacy.cmd_import
        cmd_wizard = _cli_legacy.cmd_wizard
        cmd_cheatsheet = _cli_legacy.cmd_cheatsheet
        cmd_frameworks = _cli_legacy.cmd_frameworks
        main_legacy = _cli_legacy.main

        # Export for backward compatibility
        __all__ = [
            "app",
            "main",
            "cmd_info",
            "cmd_init",
            "cmd_version",
            "cmd_validate",
            "cmd_patterns_list",
            "cmd_patterns_export",
            "cmd_metrics_show",
            "cmd_state_list",
            "cmd_run",
            "cmd_inspect",
            "cmd_export",
            "cmd_import",
            "cmd_wizard",
            "cmd_cheatsheet",
            "cmd_frameworks",
        ]
except Exception:
    # If legacy import fails, functions won't be available
    # Tests will fail but the new CLI will still work
    pass

from empathy_os.cli.commands import inspection, utilities
from empathy_os.cli.commands.memory import memory_app
from empathy_os.cli.commands.provider import provider_app
from empathy_os.cli.core import console, get_empathy_version, version_callback

# Create the main Typer app
app = typer.Typer(
    name="empathy",
    help="Empathy Framework - Predictive AI-Developer Collaboration",
    no_args_is_help=True,
    rich_markup_mode="rich",
)

# Register command group apps
app.add_typer(memory_app, name="memory")
app.add_typer(provider_app, name="provider")


@app.callback()
def callback(
    version: bool = typer.Option(
        None,
        "--version",
        "-v",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit",
    ),
) -> None:
    """Empathy Framework - Predictive AI-Developer Collaboration

    The AI collaboration framework that predicts problems before they happen.

    [bold]Quick Start:[/bold]
        empathy morning         Start-of-day briefing
        empathy health          Quick health check
        empathy ship            Pre-commit validation

    [bold]Memory:[/bold]
        empathy memory status   Check memory system status
        empathy memory start    Start Redis server

    [bold]Provider:[/bold]
        empathy provider        Show current provider config
        empathy provider --set hybrid   Configure provider

    [bold]Inspection:[/bold]
        empathy scan .          Scan codebase for issues
        empathy inspect .       Deep inspection with SARIF output
    """


# =============================================================================
# SCAN/INSPECT COMMANDS (top-level)
# =============================================================================


@app.command("scan")
def scan(
    path: Path = Path("."),
    format_out: str = "text",
    fix: bool = False,
    staged: bool = False,
) -> None:
    """Scan codebase for issues."""
    inspection.scan(path, format_out, fix, staged)


@app.command("inspect")
def inspect_cmd(
    path: Path = Path("."),
    format_out: str = "text",
) -> None:
    """Deep inspection with code analysis."""
    inspection.inspect_cmd(path, format_out)


# =============================================================================
# UTILITY COMMANDS (top-level)
# =============================================================================


@app.command("sync-claude")
def sync_claude(source: str = "patterns") -> None:
    """Sync patterns to Claude Code memory."""
    utilities.sync_claude(source)


@app.command("cheatsheet")
def cheatsheet() -> None:
    """Show quick reference for all commands."""
    utilities.cheatsheet()


@app.command("dashboard")
def dashboard() -> None:
    """Launch visual dashboard."""
    utilities.dashboard()


@app.command("costs")
def costs() -> None:
    """View API cost tracking."""
    utilities.costs()


@app.command("init")
def init() -> None:
    """Create a new configuration file."""
    utilities.init()


@app.command("status")
def status() -> None:
    """What needs attention now."""
    utilities.status()


# =============================================================================
# WORKFLOW COMMANDS (delegate to legacy CLI for now)
# These will be extracted in Phase 2b
# =============================================================================


@app.command("morning")
def morning() -> None:
    """Start-of-day briefing with patterns, git context, and priorities."""
    subprocess.run([sys.executable, "-m", "empathy_os.cli", "morning"], check=False)


@app.command("ship")
def ship(
    tests_only: bool = False,
    security_only: bool = False,
    skip_sync: bool = False,
) -> None:
    """Pre-commit validation (lint, format, tests, security)."""
    args = [sys.executable, "-m", "empathy_os.cli", "ship"]
    if tests_only:
        args.append("--tests-only")
    if security_only:
        args.append("--security-only")
    if skip_sync:
        args.append("--skip-sync")
    subprocess.run(args, check=False)


@app.command("health")
def health(
    deep: bool = False,
    fix: bool = False,
) -> None:
    """Quick health check (lint, types, tests)."""
    args = [sys.executable, "-m", "empathy_os.cli", "health"]
    if deep:
        args.append("--deep")
    if fix:
        args.append("--fix")
    subprocess.run(args, check=False)


@app.command("fix-all")
def fix_all() -> None:
    """Fix all lint and format issues."""
    subprocess.run([sys.executable, "-m", "empathy_os.cli", "fix-all"], check=False)


@app.command("learn")
def learn(analyze: int = 20) -> None:
    """Learn patterns from commit history."""
    subprocess.run(
        [sys.executable, "-m", "empathy_os.cli", "learn", "--analyze", str(analyze)],
        check=False,
    )


@app.command("run")
def run_repl() -> None:
    """Start interactive REPL mode."""
    subprocess.run([sys.executable, "-m", "empathy_os.cli", "run"], check=False)


# =============================================================================
# REMAINING COMMAND GROUPS
# Import directly from cli_unified.py for now - will be extracted later
# =============================================================================

# Import and register remaining command groups from cli_unified.py
# These are imported here to keep the transition incremental
try:
    from empathy_os.cli_unified import (
        orchestrate_app,
        progressive_app,
        service_app,
        telemetry_app,
        tier_app,
        wizard_app,
        workflow_app,
    )

    app.add_typer(wizard_app, name="wizard")
    app.add_typer(workflow_app, name="workflow")
    app.add_typer(orchestrate_app, name="orchestrate")
    app.add_typer(telemetry_app, name="telemetry")
    app.add_typer(service_app, name="service")
    app.add_typer(progressive_app, name="progressive")
    app.add_typer(tier_app, name="tier")
except ImportError:
    # cli_unified.py may not have these exports yet
    pass

# Register meta-workflow if available
try:
    from empathy_os.meta_workflows.cli_meta_workflows import meta_workflow_app

    app.add_typer(meta_workflow_app, name="meta-workflow")
except ImportError:
    pass


def main() -> None:
    """Entry point for the unified CLI."""
    app()


if __name__ == "__main__":
    main()
