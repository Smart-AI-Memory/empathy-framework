"""Multi-model provider configuration commands.

Commands for managing provider settings, registry, costs, and telemetry.

Copyright 2025 Smart-AI-Memory
Licensed under Fair Source License 0.9
"""

import subprocess
import sys

import typer

# Create the provider Typer app
provider_app = typer.Typer(help="Multi-model provider configuration")


@provider_app.callback(invoke_without_command=True)
def provider_show(
    ctx: typer.Context,
    set_provider: str | None = None,
    interactive: bool = False,
    format_out: str = "table",
) -> None:
    """Show or configure provider settings."""
    if ctx.invoked_subcommand is not None:
        return

    args = [sys.executable, "-m", "empathy_os.models.cli", "provider"]
    if set_provider:
        args.extend(["--set", set_provider])
    if interactive:
        args.append("--interactive")
    if format_out != "table":
        args.extend(["-f", format_out])

    subprocess.run(args, check=False)


@provider_app.command("registry")
def provider_registry(
    provider_filter: str | None = None,
) -> None:
    """Show all available models in the registry."""
    args = [sys.executable, "-m", "empathy_os.models.cli", "registry"]
    if provider_filter:
        args.extend(["--provider", provider_filter])
    subprocess.run(args, check=False)


@provider_app.command("costs")
def provider_costs(
    input_tokens: int = 10000,
    output_tokens: int = 2000,
) -> None:
    """Estimate costs for token usage."""
    subprocess.run(
        [
            sys.executable,
            "-m",
            "empathy_os.models.cli",
            "costs",
            "--input-tokens",
            str(input_tokens),
            "--output-tokens",
            str(output_tokens),
        ],
        check=False,
    )


@provider_app.command("telemetry")
def provider_telemetry(
    summary: bool = False,
    costs: bool = False,
    providers: bool = False,
) -> None:
    """View telemetry and analytics."""
    args = [sys.executable, "-m", "empathy_os.models.cli", "telemetry"]
    if summary:
        args.append("--summary")
    if costs:
        args.append("--costs")
    if providers:
        args.append("--providers")
    subprocess.run(args, check=False)
