"""Unified CLI for Empathy Framework

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
from importlib.metadata import version as get_version
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel

# Create the main Typer app
app = typer.Typer(
    name="empathy",
    help="Empathy Framework - Predictive AI-Developer Collaboration",
    no_args_is_help=True,
    rich_markup_mode="rich",
)

console = Console()


def get_empathy_version() -> str:
    """Get the installed version of empathy-framework."""
    try:
        return get_version("empathy-framework")
    except Exception:
        return "dev"


def version_callback(value: bool):
    """Show version and exit."""
    if value:
        console.print(f"[bold blue]Empathy Framework[/bold blue] v{get_empathy_version()}")
        raise typer.Exit()


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
):
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
# MEMORY SUBCOMMAND GROUP
# =============================================================================

memory_app = typer.Typer(help="Memory system control panel")
app.add_typer(memory_app, name="memory")


@memory_app.command("status")
def memory_status():
    """Check memory system status (Redis, patterns, stats)."""
    # Delegate to the existing CLI
    subprocess.run([sys.executable, "-m", "empathy_os.memory.control_panel", "status"], check=False)


@memory_app.command("start")
def memory_start():
    """Start Redis server for short-term memory."""
    subprocess.run([sys.executable, "-m", "empathy_os.memory.control_panel", "start"], check=False)


@memory_app.command("stop")
def memory_stop():
    """Stop Redis server."""
    subprocess.run([sys.executable, "-m", "empathy_os.memory.control_panel", "stop"], check=False)


@memory_app.command("stats")
def memory_stats():
    """Show memory statistics."""
    subprocess.run([sys.executable, "-m", "empathy_os.memory.control_panel", "stats"], check=False)


@memory_app.command("patterns")
def memory_patterns():
    """List stored patterns."""
    subprocess.run(
        [sys.executable, "-m", "empathy_os.memory.control_panel", "patterns", "--list"], check=False
    )


# =============================================================================
# PROVIDER SUBCOMMAND GROUP
# =============================================================================

provider_app = typer.Typer(help="Multi-model provider configuration")
app.add_typer(provider_app, name="provider")


@provider_app.callback(invoke_without_command=True)
def provider_show(
    ctx: typer.Context,
    set_provider: str | None = None,
    interactive: bool = False,
    format_out: str = "table",
):
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
):
    """Show all available models in the registry."""
    args = [sys.executable, "-m", "empathy_os.models.cli", "registry"]
    if provider_filter:
        args.extend(["--provider", provider_filter])
    subprocess.run(args, check=False)


@provider_app.command("costs")
def provider_costs(
    input_tokens: int = 10000,
    output_tokens: int = 2000,
):
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
):
    """View telemetry and analytics."""
    args = [sys.executable, "-m", "empathy_os.models.cli", "telemetry"]
    if summary:
        args.append("--summary")
    if costs:
        args.append("--costs")
    if providers:
        args.append("--providers")
    subprocess.run(args, check=False)


# =============================================================================
# SCAN COMMAND
# =============================================================================


@app.command("scan")
def scan(
    path: Path = Path("."),
    format_out: str = "text",
    fix: bool = False,
    staged: bool = False,
):
    """Scan codebase for issues."""
    args = ["empathy-scan", str(path)]
    if format_out != "text":
        args.extend(["--format", format_out])
    if fix:
        args.append("--fix")
    if staged:
        args.append("--staged")

    result = subprocess.run(args, check=False, capture_output=False)
    if result.returncode != 0:
        console.print("[yellow]Note: empathy-scan may not be installed[/yellow]")
        console.print("Install with: pip install empathy-framework[software]")


# =============================================================================
# INSPECT COMMAND
# =============================================================================


@app.command("inspect")
def inspect_cmd(
    path: Path = Path("."),
    format_out: str = "text",
):
    """Deep inspection with code analysis."""
    args = ["empathy-inspect", str(path)]
    if format_out != "text":
        args.extend(["--format", format_out])

    result = subprocess.run(args, check=False, capture_output=False)
    if result.returncode != 0:
        console.print("[yellow]Note: empathy-inspect may not be installed[/yellow]")
        console.print("Install with: pip install empathy-framework[software]")


# =============================================================================
# SYNC-CLAUDE COMMAND
# =============================================================================


@app.command("sync-claude")
def sync_claude(
    source: str = "patterns",
):
    """Sync patterns to Claude Code memory."""
    subprocess.run(["empathy-sync-claude", "--source", source], check=False)


# =============================================================================
# WORKFLOW COMMANDS (delegate to legacy CLI)
# =============================================================================


@app.command("morning")
def morning():
    """Start-of-day briefing with patterns, git context, and priorities."""
    subprocess.run([sys.executable, "-m", "empathy_os.cli", "morning"], check=False)


@app.command("ship")
def ship(
    tests_only: bool = False,
    security_only: bool = False,
    skip_sync: bool = False,
):
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
):
    """Quick health check (lint, types, tests)."""
    args = [sys.executable, "-m", "empathy_os.cli", "health"]
    if deep:
        args.append("--deep")
    if fix:
        args.append("--fix")
    subprocess.run(args, check=False)


@app.command("fix-all")
def fix_all():
    """Fix all lint and format issues."""
    subprocess.run([sys.executable, "-m", "empathy_os.cli", "fix-all"], check=False)


@app.command("learn")
def learn(
    analyze: int = 20,
):
    """Learn patterns from commit history."""
    subprocess.run(
        [sys.executable, "-m", "empathy_os.cli", "learn", "--analyze", str(analyze)], check=False
    )


@app.command("run")
def run_repl():
    """Start interactive REPL mode."""
    subprocess.run([sys.executable, "-m", "empathy_os.cli", "run"], check=False)


# =============================================================================
# WIZARD COMMANDS
# =============================================================================

wizard_app = typer.Typer(help="AI Development Wizards")
app.add_typer(wizard_app, name="wizard")


@wizard_app.command("list")
def wizard_list():
    """List all available wizards."""
    subprocess.run([sys.executable, "-m", "empathy_os.cli", "frameworks"], check=False)


@wizard_app.command("run")
def wizard_run(
    name: str = typer.Argument(..., help="Wizard name to run"),
    path: Path = Path("."),
):
    """Run a specific wizard on your codebase."""
    console.print(f"[yellow]Running wizard:[/yellow] {name} on {path}")
    # Delegate to empathy-scan with wizard filter
    subprocess.run(["empathy-scan", str(path), "--wizards", name], check=False)


@wizard_app.command("create")
def wizard_create(
    name: str = typer.Argument(..., help="Wizard name (snake_case)"),
    domain: str = typer.Option(
        ..., "--domain", "-d", help="Domain (healthcare, finance, software)"
    ),
    wizard_type: str = typer.Option(
        "domain", "--type", "-t", help="Wizard type (domain, coach, ai)"
    ),
    methodology: str = typer.Option(
        "pattern", "--methodology", "-m", help="Methodology (pattern, tdd)"
    ),
    patterns: str | None = typer.Option(
        None, "--patterns", "-p", help="Comma-separated pattern IDs"
    ),
    interactive: bool = typer.Option(
        False, "--interactive", "-i", help="Interactive pattern selection"
    ),
):
    """Create a new wizard using Wizard Factory (12x faster)."""
    cmd = [
        sys.executable,
        "-m",
        "scaffolding",
        "create",
        name,
        "--domain",
        domain,
        "--type",
        wizard_type,
        "--methodology",
        methodology,
    ]
    if patterns:
        cmd.extend(["--patterns", patterns])
    if interactive:
        cmd.append("--interactive")
    subprocess.run(cmd, check=False)


@wizard_app.command("list-patterns")
def wizard_list_patterns():
    """List all available wizard patterns."""
    subprocess.run([sys.executable, "-m", "scaffolding", "list-patterns"], check=False)


@wizard_app.command("generate-tests")
def wizard_generate_tests(
    wizard_id: str = typer.Argument(..., help="Wizard ID"),
    patterns: str = typer.Option(..., "--patterns", "-p", help="Comma-separated pattern IDs"),
    output: Path | None = typer.Option(None, "--output", "-o", help="Output directory"),
):
    """Generate tests for a wizard."""
    cmd = [sys.executable, "-m", "test_generator", "generate", wizard_id, "--patterns", patterns]
    if output:
        cmd.extend(["--output", str(output)])
    subprocess.run(cmd, check=False)


@wizard_app.command("analyze")
def wizard_analyze(
    wizard_id: str = typer.Argument(..., help="Wizard ID"),
    patterns: str = typer.Option(..., "--patterns", "-p", help="Wizard ID"),
    json_output: bool = typer.Option(False, "--json", help="Output JSON format"),
):
    """Analyze wizard risk and get coverage recommendations."""
    cmd = [sys.executable, "-m", "test_generator", "analyze", wizard_id, "--patterns", patterns]
    if json_output:
        cmd.append("--json")
    subprocess.run(cmd, check=False)


# =============================================================================
# WORKFLOW SUBCOMMAND GROUP
# =============================================================================

workflow_app = typer.Typer(help="Multi-model workflows")
app.add_typer(workflow_app, name="workflow")


@workflow_app.command("list")
def workflow_list():
    """List available multi-model workflows."""
    subprocess.run([sys.executable, "-m", "empathy_os.cli", "workflow", "list"], check=False)


@workflow_app.command("run")
def workflow_run(
    name: str = typer.Argument(..., help="Workflow name"),
    path: Path = typer.Option(Path("."), "--path", "-p", help="Target path for workflow"),
    input_json: str = typer.Option(None, "--input", "-i", help="JSON input for workflow (overrides --path)"),
    use_recommended_tier: bool = False,
    health_score_threshold: int = 95,
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Run a multi-model workflow.

    Examples:
        empathy workflow run code-review --path ./src
        empathy workflow run test-gen --input '{"path": ".", "file_types": [".py"]}'
    """
    # Determine input JSON - explicit --input takes precedence over --path
    if input_json:
        workflow_input = input_json
    else:
        workflow_input = f'{{"path": "{path}"}}'

    cmd = [
        sys.executable,
        "-m",
        "empathy_os.cli",
        "workflow",
        "run",
        name,
        "--input",
        workflow_input,
    ]

    if use_recommended_tier:
        cmd.append("--use-recommended-tier")

    if health_score_threshold != 95:
        cmd.extend(["--health-score-threshold", str(health_score_threshold)])

    if json_output:
        cmd.append("--json")

    subprocess.run(cmd, check=False)


@workflow_app.command("create")
def workflow_create(
    name: str = typer.Argument(..., help="Workflow name (kebab-case, e.g., bug-scanner)"),
    description: str = typer.Option(None, "--description", "-d", help="Workflow description"),
    patterns: str = typer.Option(None, "--patterns", "-p", help="Comma-separated pattern IDs"),
    stages: str = typer.Option(None, "--stages", "-s", help="Comma-separated stage names"),
    tier_map: str = typer.Option(
        None, "--tier-map", "-t", help="Tier map (e.g., analyze:CHEAP,process:CAPABLE)"
    ),
    output: Path = typer.Option(None, "--output", "-o", help="Output directory"),
):
    """Create a new workflow using Workflow Factory (12x faster)."""
    cmd = [sys.executable, "-m", "workflow_scaffolding", "create", name]
    if description:
        cmd.extend(["--description", description])
    if patterns:
        cmd.extend(["--patterns", patterns])
    if stages:
        cmd.extend(["--stages", stages])
    if tier_map:
        cmd.extend(["--tier-map", tier_map])
    if output:
        cmd.extend(["--output", str(output)])
    subprocess.run(cmd, check=False)


@workflow_app.command("list-patterns")
def workflow_list_patterns():
    """List available workflow patterns."""
    subprocess.run([sys.executable, "-m", "workflow_scaffolding", "list-patterns"], check=False)


@workflow_app.command("recommend")
def workflow_recommend(
    workflow_type: str = typer.Argument(
        ..., help="Workflow type (code-analysis, simple, multi-agent, etc.)"
    ),
):
    """Recommend patterns for a workflow type."""
    subprocess.run(
        [sys.executable, "-m", "workflow_scaffolding", "recommend", workflow_type], check=False
    )


# =============================================================================
# ORCHESTRATE SUBCOMMAND GROUP (Meta-Orchestration v4.0)
# =============================================================================

orchestrate_app = typer.Typer(help="Meta-orchestration workflows (v4.0)")
app.add_typer(orchestrate_app, name="orchestrate")


@orchestrate_app.command("health-check")
def orchestrate_health_check(
    mode: str = typer.Option("daily", "--mode", "-m", help="Check mode: daily, weekly, release"),
    project_root: Path = typer.Option(Path("."), "--project-root", "-p", help="Project root path"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Run orchestrated health check with adaptive agent teams.

    Modes:
        daily: Quick parallel check (3 agents: Security, Coverage, Quality)
        weekly: Comprehensive parallel (5 agents: adds Performance, Docs)
        release: Deep refinement (6 agents: adds Architecture)

    The results are automatically saved to .empathy/health.json which can be
    viewed in the Empathy VS Code extension's health dashboard.
    """
    import asyncio

    from empathy_os.workflows.orchestrated_health_check import OrchestratedHealthCheckWorkflow

    async def run_health_check():
        workflow = OrchestratedHealthCheckWorkflow(mode=mode)
        report = await workflow.execute(project_root=str(project_root))

        if json_output:
            import json

            console.print(json.dumps(report.to_dict(), indent=2))
        else:
            # Beautiful console output
            console.print("\n[bold cyan]🏥 HEALTH CHECK REPORT[/bold cyan]")
            console.print("=" * 60)

            # Health score with color coding
            score_color = (
                "green"
                if report.overall_health_score >= 80
                else "yellow" if report.overall_health_score >= 60 else "red"
            )
            console.print(
                f"\n[bold {score_color}]Health Score: {report.overall_health_score}/100 (Grade: {report.grade})[/bold {score_color}]"
            )
            console.print(f"[dim]Trend: {report.trend}[/dim]")
            console.print(f"[dim]Duration: {report.execution_time:.2f}s[/dim]")

            # Issues
            if report.issues:
                console.print(f"\n[bold red]⚠️  Issues Found ({len(report.issues)}):[/bold red]")
                for issue in report.issues[:5]:
                    console.print(f"  • {issue}")

            # Recommendations
            if report.recommendations:
                console.print("\n[bold yellow]💡 Next Steps:[/bold yellow]")
                for rec in report.recommendations[:10]:  # Show more recommendations
                    console.print(f"  {rec}")

            console.print("\n" + "=" * 60)

            # Show VS Code dashboard info
            health_file = Path(project_root) / ".empathy" / "health.json"
            console.print(f"\n📁 Health data saved to: [cyan]{health_file}[/cyan]")

            # Try to open VS Code health panel
            console.print("\n🔄 Opening Health Panel in VS Code...")
            try:
                import subprocess

                # Use VS Code CLI to trigger the health panel (run in background)
                subprocess.Popen(
                    ["code", "--command", "empathy.openHealthPanel"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                console.print(
                    "   [dim]If VS Code is already open, the Health Panel will appear automatically.[/dim]"
                )
                console.print(
                    "   [dim]If not, open VS Code and the panel will show updated data.[/dim]"
                )
            except FileNotFoundError:
                console.print("\n💡 [yellow]To view in VS Code:[/yellow]")
                console.print("   1. Open this project in VS Code")
                console.print("   2. Install the Empathy VS Code extension")
                console.print("   3. Run: code --command empathy.openHealthPanel")
                console.print("   [dim]Or the panel will auto-refresh if already open[/dim]")
            except Exception:  # noqa: BLE001
                # INTENTIONAL: Best-effort VS Code integration, don't fail if it doesn't work
                console.print(
                    "\n💡 [dim]View in VS Code Health Panel (auto-refreshes every 30s)[/dim]"
                )

        return report

    try:
        asyncio.run(run_health_check())
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1)


@orchestrate_app.command("release-prep")
def orchestrate_release_prep(
    project_root: Path = typer.Option(Path("."), "--project-root", "-p", help="Project root path"),
    min_coverage: float = typer.Option(80.0, "--min-coverage", help="Minimum test coverage %"),
    min_quality: float = typer.Option(7.0, "--min-quality", help="Minimum quality score (0-10)"),
    max_critical: int = typer.Option(0, "--max-critical", help="Max critical issues allowed"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Run orchestrated release preparation with parallel validation.

    Runs 4 agents in parallel:
        - Security Auditor (vulnerability scan)
        - Test Coverage Analyzer (gap analysis)
        - Code Quality Reviewer (best practices)
        - Documentation Writer (completeness check)
    """
    import asyncio

    from empathy_os.workflows.orchestrated_release_prep import OrchestratedReleasePrepWorkflow

    async def run_release_prep():
        workflow = OrchestratedReleasePrepWorkflow(
            quality_gates={
                "min_coverage": min_coverage,
                "min_quality_score": min_quality,
                "max_critical_issues": max_critical,
            }
        )
        report = await workflow.execute(path=str(project_root))

        if json_output:
            import json

            console.print(json.dumps(report.to_dict(), indent=2))
        else:
            console.print("\n[bold cyan]📋 RELEASE PREPARATION REPORT[/bold cyan]")
            console.print("=" * 60)

            approval_color = "green" if report.approved else "red"
            approval_emoji = "✅" if report.approved else "❌"
            console.print(
                f"\n[bold {approval_color}]{approval_emoji} {'APPROVED' if report.approved else 'NOT APPROVED'}[/bold {approval_color}]"
            )
            console.print(f"[dim]Confidence: {report.confidence}[/dim]")
            console.print(f"[dim]Duration: {report.total_duration:.2f}s[/dim]")

            # Quality gates
            console.print("\n[bold]Quality Gates:[/bold]")
            for gate in report.quality_gates:
                gate_emoji = "✅" if gate.passed else "❌"
                console.print(
                    f"  {gate_emoji} {gate.name}: {gate.actual:.1f} (threshold: {gate.threshold:.1f})"
                )

            # Blockers
            if report.blockers:
                console.print("\n[bold red]🚫 Blockers:[/bold red]")
                for blocker in report.blockers:
                    console.print(f"  • {blocker}")

            # Warnings
            if report.warnings:
                console.print("\n[bold yellow]⚠️  Warnings:[/bold yellow]")
                for warning in report.warnings:
                    console.print(f"  • {warning}")

            console.print("\n" + "=" * 60)

        return report

    try:
        asyncio.run(run_release_prep())
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1)


@orchestrate_app.command("test-coverage")
def orchestrate_test_coverage(
    project_root: Path = typer.Option(Path("."), "--project-root", "-p", help="Project root path"),
    target: float = typer.Option(90.0, "--target", "-t", help="Target coverage percentage"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Run orchestrated test coverage boost with sequential stages.

    Runs 3 stages sequentially:
        1. Coverage Analyzer → Identify gaps
        2. Test Generator → Create tests
        3. Test Validator → Verify coverage
    """
    import asyncio

    from empathy_os.workflows.test_coverage_boost import TestCoverageBoostWorkflow

    async def run_test_coverage():
        workflow = TestCoverageBoostWorkflow(target_coverage=target)
        report = await workflow.execute(project_root=str(project_root))

        if json_output:
            import json

            console.print(json.dumps(report.to_dict(), indent=2))
        else:
            console.print("\n[bold cyan]🧪 TEST COVERAGE BOOST REPORT[/bold cyan]")
            console.print("=" * 60)

            success_color = "green" if report.success else "red"
            success_emoji = "✅" if report.success else "❌"
            console.print(
                f"\n[bold {success_color}]{success_emoji} {'SUCCESS' if report.success else 'FAILED'}[/bold {success_color}]"
            )
            console.print(f"[dim]Initial: {report.initial_coverage:.1f}%[/dim]")
            console.print(f"[dim]Final: {report.final_coverage:.1f}%[/dim]")
            console.print(f"[dim]Improvement: +{report.improvement:.1f}%[/dim]")
            console.print(f"[dim]Duration: {report.total_duration:.2f}s[/dim]")

            # Stage results
            console.print("\n[bold]Stage Results:[/bold]")
            for i, stage in enumerate(report.stage_results, 1):
                stage_emoji = "✅" if stage["success"] else "❌"
                console.print(f"  {stage_emoji} Stage {i}: {stage.get('description', 'N/A')}")

            console.print("\n" + "=" * 60)

        return report

    try:
        asyncio.run(run_test_coverage())
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1)


# =============================================================================
# TELEMETRY SUBCOMMAND GROUP
# =============================================================================

telemetry_app = typer.Typer(help="View and manage local usage telemetry")
app.add_typer(telemetry_app, name="telemetry")


@telemetry_app.command("show")
def telemetry_show(
    limit: int = typer.Option(20, "--limit", "-l", help="Number of entries to show"),
    days: int | None = typer.Option(None, "--days", "-d", help="Only show last N days"),
):
    """Show recent LLM calls and usage stats."""
    args = [sys.executable, "-m", "empathy_os.cli", "telemetry", "show", "--limit", str(limit)]
    if days:
        args.extend(["--days", str(days)])
    subprocess.run(args, check=False)


@telemetry_app.command("savings")
def telemetry_savings(
    days: int = typer.Option(30, "--days", "-d", help="Number of days to analyze"),
):
    """Calculate cost savings vs baseline (all PREMIUM)."""
    subprocess.run(
        [sys.executable, "-m", "empathy_os.cli", "telemetry", "savings", "--days", str(days)],
        check=False,
    )


@telemetry_app.command("compare")
def telemetry_compare(
    period1: int = typer.Option(7, "--period1", "-p1", help="First period in days"),
    period2: int = typer.Option(30, "--period2", "-p2", help="Second period in days"),
):
    """Compare usage across two time periods."""
    subprocess.run(
        [
            sys.executable,
            "-m",
            "empathy_os.cli",
            "telemetry",
            "compare",
            "--period1",
            str(period1),
            "--period2",
            str(period2),
        ],
        check=False,
    )


@telemetry_app.command("export")
def telemetry_export(
    format_type: str = typer.Option("json", "--format", "-f", help="Export format (json, csv)"),
    output: Path | None = typer.Option(None, "--output", "-o", help="Output file path"),
    days: int | None = typer.Option(None, "--days", "-d", help="Only export last N days"),
):
    """Export telemetry data to JSON or CSV."""
    args = [sys.executable, "-m", "empathy_os.cli", "telemetry", "export", "--format", format_type]
    if output:
        args.extend(["--output", str(output)])
    if days:
        args.extend(["--days", str(days)])
    subprocess.run(args, check=False)


@telemetry_app.command("reset")
def telemetry_reset(
    confirm: bool = typer.Option(False, "--confirm", help="Confirm deletion"),
):
    """Clear all telemetry data (use with caution)."""
    args = [sys.executable, "-m", "empathy_os.cli", "telemetry", "reset"]
    if confirm:
        args.append("--confirm")
    subprocess.run(args, check=False)


# =============================================================================
# SERVICE SUBCOMMAND GROUP (Cross-Session Communication)
# =============================================================================

service_app = typer.Typer(help="Cross-session coordination service")
app.add_typer(service_app, name="service")


@service_app.command("start")
def service_start(
    daemon: bool = typer.Option(False, "--daemon", "-d", help="Run as daemon (auto-start on connect)"),
):
    """Start the cross-session coordination service.

    The service enables communication between multiple Claude Code sessions
    via Redis-backed short-term memory.

    Requires Redis to be running (empathy memory start).
    """
    from empathy_os.redis_config import get_redis_memory

    try:
        memory = get_redis_memory()

        if memory.use_mock:
            console.print("[yellow]⚠️  Cross-session service requires Redis.[/yellow]")
            console.print("[dim]Start Redis with: empathy memory start[/dim]")
            console.print("[dim]Or set REDIS_HOST/REDIS_PORT environment variables[/dim]")
            raise typer.Exit(code=1)

        from empathy_os.memory.cross_session import BackgroundService

        service = BackgroundService(memory, auto_start_on_connect=daemon)

        if service.start():
            console.print("[bold green]✅ Cross-session service started[/bold green]")
            status = service.get_status()
            console.print(f"[dim]Agent ID: {status['agent_id']}[/dim]")
            console.print(f"[dim]Active sessions: {status['active_sessions']}[/dim]")

            if daemon:
                console.print("[dim]Running in daemon mode (press Ctrl+C to stop)[/dim]")
                try:
                    import time
                    while service.is_running:
                        time.sleep(1)
                except KeyboardInterrupt:
                    service.stop()
                    console.print("\n[dim]Service stopped[/dim]")
        else:
            console.print("[yellow]⚠️  Service already running (or couldn't acquire lock)[/yellow]")
            console.print("[dim]Use 'empathy service status' to check[/dim]")

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1)


@service_app.command("stop")
def service_stop():
    """Stop the cross-session coordination service."""
    from empathy_os.redis_config import get_redis_memory

    try:
        memory = get_redis_memory()

        if memory.use_mock:
            console.print("[yellow]No service to stop (mock mode)[/yellow]")
            return

        # Check if service is running and signal it to stop
        client = memory._client
        if client:
            from empathy_os.memory.cross_session import KEY_SERVICE_LOCK

            lock_holder = client.get(KEY_SERVICE_LOCK)
            if lock_holder:
                client.delete(KEY_SERVICE_LOCK)
                console.print("[green]✅ Service stop signal sent[/green]")
            else:
                console.print("[dim]No service currently running[/dim]")
        else:
            console.print("[yellow]Redis not connected[/yellow]")

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1)


@service_app.command("status")
def service_status(
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Show cross-session service status and active sessions."""
    import json as json_mod

    from empathy_os.redis_config import get_redis_memory

    try:
        memory = get_redis_memory()

        if memory.use_mock:
            status = {
                "mode": "mock",
                "cross_session_available": False,
                "message": "Cross-session requires Redis",
            }
            if json_output:
                console.print(json_mod.dumps(status, indent=2))
            else:
                console.print("[yellow]⚠️  Mock mode - cross-session not available[/yellow]")
                console.print("[dim]Start Redis: empathy memory start[/dim]")
            return

        from empathy_os.memory.cross_session import (
            KEY_ACTIVE_AGENTS,
            KEY_SERVICE_HEARTBEAT,
            KEY_SERVICE_LOCK,
            SessionInfo,
        )

        client = memory._client
        if not client:
            console.print("[red]Redis not connected[/red]")
            raise typer.Exit(code=1)

        # Check service status
        service_lock = client.get(KEY_SERVICE_LOCK)
        service_heartbeat = client.get(KEY_SERVICE_HEARTBEAT)

        # Get active sessions
        all_agents = client.hgetall(KEY_ACTIVE_AGENTS)
        sessions = []
        for agent_id, data in all_agents.items():
            try:
                if isinstance(agent_id, bytes):
                    agent_id = agent_id.decode()
                if isinstance(data, bytes):
                    data = data.decode()
                info = SessionInfo.from_dict(json_mod.loads(data))
                if not info.is_stale:
                    sessions.append(info.to_dict())
            except (json_mod.JSONDecodeError, KeyError, ValueError):
                pass

        status = {
            "mode": "redis",
            "cross_session_available": True,
            "service_running": bool(service_lock),
            "service_pid": service_lock.decode() if isinstance(service_lock, bytes) else service_lock,
            "last_heartbeat": service_heartbeat.decode() if isinstance(service_heartbeat, bytes) else service_heartbeat,
            "active_sessions": len(sessions),
            "sessions": sessions,
        }

        if json_output:
            console.print(json_mod.dumps(status, indent=2))
        else:
            console.print()
            console.print("[bold cyan]CROSS-SESSION SERVICE STATUS[/bold cyan]")
            console.print("=" * 50)
            console.print()

            if status["service_running"]:
                console.print("[green]● Service Running[/green]")
                console.print(f"[dim]  PID: {status['service_pid']}[/dim]")
                if status["last_heartbeat"]:
                    console.print(f"[dim]  Last heartbeat: {status['last_heartbeat']}[/dim]")
            else:
                console.print("[yellow]○ Service Not Running[/yellow]")
                console.print("[dim]  Start with: empathy service start[/dim]")

            console.print()
            console.print(f"[bold]Active Sessions:[/bold] {status['active_sessions']}")

            if sessions:
                console.print()
                for session in sessions:
                    session_type = session.get("session_type", "unknown")
                    agent_id = session.get("agent_id", "unknown")
                    tier = session.get("access_tier", "unknown")
                    emoji = "🤖" if session_type == "claude" else "⚙️" if session_type == "service" else "👷"
                    console.print(f"  {emoji} {agent_id}")
                    console.print(f"     [dim]Type: {session_type} | Tier: {tier}[/dim]")

            console.print()
            console.print("=" * 50)

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1)


@service_app.command("sessions")
def service_sessions():
    """List all active cross-session agents."""
    import json as json_mod

    from empathy_os.redis_config import get_redis_memory

    try:
        memory = get_redis_memory()

        if memory.use_mock:
            console.print("[yellow]No sessions (mock mode)[/yellow]")
            return

        from empathy_os.memory.cross_session import KEY_ACTIVE_AGENTS, SessionInfo

        client = memory._client
        if not client:
            console.print("[red]Redis not connected[/red]")
            return

        all_agents = client.hgetall(KEY_ACTIVE_AGENTS)

        if not all_agents:
            console.print("[dim]No active sessions[/dim]")
            return

        console.print()
        console.print("[bold]Active Cross-Session Agents[/bold]")
        console.print("-" * 60)

        for agent_id, data in all_agents.items():
            try:
                if isinstance(agent_id, bytes):
                    agent_id = agent_id.decode()
                if isinstance(data, bytes):
                    data = data.decode()

                info = SessionInfo.from_dict(json_mod.loads(data))

                if info.is_stale:
                    status_str = "[red]STALE[/red]"
                else:
                    status_str = "[green]ACTIVE[/green]"

                console.print(f"\n{agent_id}")
                console.print(f"  Status: {status_str}")
                console.print(f"  Type: {info.session_type.value}")
                console.print(f"  Tier: {info.access_tier.name}")
                console.print(f"  Started: {info.started_at.isoformat()}")
                console.print(f"  Last heartbeat: {info.last_heartbeat.isoformat()}")
                if info.capabilities:
                    console.print(f"  Capabilities: {', '.join(info.capabilities)}")

            except (json_mod.JSONDecodeError, KeyError, ValueError) as e:
                console.print(f"\n{agent_id}: [red]Invalid data[/red] - {e}")

        console.print()

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1)


# =============================================================================
# META-WORKFLOW SUBCOMMAND GROUP
# =============================================================================

try:
    from empathy_os.meta_workflows.cli_meta_workflows import meta_workflow_app
    app.add_typer(meta_workflow_app, name="meta-workflow")
except ImportError as e:
    # Meta-workflow system is optional/experimental
    import logging
    logging.getLogger(__name__).debug(f"Meta-workflow CLI not available: {e}")


# =============================================================================
# PROGRESSIVE WORKFLOW SUBCOMMAND GROUP
# =============================================================================

progressive_app = typer.Typer(help="Progressive tier escalation workflows")
app.add_typer(progressive_app, name="progressive")


@progressive_app.command("list")
def progressive_list(
    storage_path: str = typer.Option(
        None,
        "--storage-path",
        help="Path to progressive workflow storage (default: .empathy/progressive_runs)",
    ),
):
    """List all saved progressive workflow results."""
    from argparse import Namespace

    from empathy_os.workflows.progressive.cli import cmd_list_results

    args = Namespace(storage_path=storage_path)
    cmd_list_results(args)


@progressive_app.command("show")
def progressive_show(
    task_id: str = typer.Argument(..., help="Task ID to display"),
    storage_path: str = typer.Option(
        None,
        "--storage-path",
        help="Path to progressive workflow storage (default: .empathy/progressive_runs)",
    ),
    json_output: bool = typer.Option(False, "--json", help="Output in JSON format"),
):
    """Show detailed report for a specific task."""
    from argparse import Namespace

    from empathy_os.workflows.progressive.cli import cmd_show_report

    args = Namespace(task_id=task_id, storage_path=storage_path, json=json_output)
    cmd_show_report(args)


@progressive_app.command("analytics")
def progressive_analytics(
    storage_path: str = typer.Option(
        None,
        "--storage-path",
        help="Path to progressive workflow storage (default: .empathy/progressive_runs)",
    ),
    json_output: bool = typer.Option(False, "--json", help="Output in JSON format"),
):
    """Show cost optimization analytics."""
    from argparse import Namespace

    from empathy_os.workflows.progressive.cli import cmd_analytics

    args = Namespace(storage_path=storage_path, json=json_output)
    cmd_analytics(args)


@progressive_app.command("cleanup")
def progressive_cleanup(
    storage_path: str = typer.Option(
        None,
        "--storage-path",
        help="Path to progressive workflow storage (default: .empathy/progressive_runs)",
    ),
    retention_days: int = typer.Option(
        30, "--retention-days", help="Number of days to retain results (default: 30)"
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Show what would be deleted without actually deleting",
    ),
):
    """Clean up old progressive workflow results."""
    from argparse import Namespace

    from empathy_os.workflows.progressive.cli import cmd_cleanup

    args = Namespace(
        storage_path=storage_path, retention_days=retention_days, dry_run=dry_run
    )
    cmd_cleanup(args)


# =============================================================================
# TIER RECOMMENDATION SUBCOMMAND GROUP
# =============================================================================

tier_app = typer.Typer(help="Intelligent tier recommendations for cascading workflows")
app.add_typer(tier_app, name="tier")


@tier_app.command("recommend")
def tier_recommend(
    description: str = typer.Argument(..., help="Description of the bug or task"),
    files: str = typer.Option(None, "--files", "-f", help="Comma-separated list of affected files"),
    complexity: int = typer.Option(None, "--complexity", "-c", help="Manual complexity hint 1-10"),
):
    """Get intelligent tier recommendation for a bug/task."""
    from empathy_os.tier_recommender import TierRecommender

    recommender = TierRecommender()

    # Get recommendation
    result = recommender.recommend(
        bug_description=description,
        files_affected=files.split(",") if files else None,
        complexity_hint=complexity,
    )

    # Display results
    console.print()
    console.print("=" * 60)
    console.print("  [bold]TIER RECOMMENDATION[/bold]")
    console.print("=" * 60)
    console.print()
    console.print(f"  [dim]Bug/Task:[/dim] {description}")
    console.print()
    console.print(f"  📍 [bold]Recommended Tier:[/bold] {result.tier}")
    console.print(f"  🎯 [bold]Confidence:[/bold] {result.confidence * 100:.1f}%")
    console.print(f"  💰 [bold]Expected Cost:[/bold] ${result.expected_cost:.3f}")
    console.print(f"  🔄 [bold]Expected Attempts:[/bold] {result.expected_attempts:.1f}")
    console.print()
    console.print("  📊 [bold]Reasoning:[/bold]")
    console.print(f"     {result.reasoning}")
    console.print()

    if result.fallback_used:
        console.print("  ⚠️  [yellow]No historical data - using conservative default[/yellow]")
        console.print()
        console.print("  💡 [dim]Tip: As more patterns are collected, recommendations[/dim]")
        console.print("     [dim]will become more accurate and personalized.[/dim]")
    else:
        console.print(f"  ✅ Based on {result.similar_patterns_count} similar patterns")

    console.print()
    console.print("=" * 60)
    console.print()


@tier_app.command("stats")
def tier_stats():
    """Show tier pattern learning statistics."""
    from empathy_os.tier_recommender import TierRecommender

    recommender = TierRecommender()
    stats = recommender.get_stats()

    if stats.get("total_patterns") == 0:
        console.print()
        console.print("  [yellow]No patterns loaded yet.[/yellow]")
        console.print()
        console.print("  💡 [dim]Patterns are collected automatically as you use")
        console.print("     cascading workflows. Run a few workflows first.[/dim]")
        console.print()
        return

    # Display statistics
    console.print()
    console.print("=" * 60)
    console.print("  [bold]TIER PATTERN LEARNING STATS[/bold]")
    console.print("=" * 60)
    console.print()
    console.print(f"  [bold]Total Patterns:[/bold] {stats['total_patterns']}")
    console.print(f"  [bold]Avg Savings:[/bold] {stats['avg_savings_percent']}%")
    console.print()
    console.print("  [bold]TIER DISTRIBUTION[/bold]")
    console.print("  " + "-" * 40)

    tier_dist = stats["patterns_by_tier"]
    total = stats["total_patterns"]
    max_bar_width = 20

    for tier in ["CHEAP", "CAPABLE", "PREMIUM"]:
        count = tier_dist.get(tier, 0)
        percent = (count / total * 100) if total > 0 else 0
        bar_width = int(percent / 100 * max_bar_width)
        bar = "█" * bar_width
        console.print(f"  {tier:<12} {count:>2} ({percent:>5.1f}%) {bar}")

    console.print()
    console.print("  [bold]BUG TYPE DISTRIBUTION[/bold]")
    console.print("  " + "-" * 40)

    for bug_type, count in sorted(
        stats["bug_type_distribution"].items(), key=lambda x: x[1], reverse=True
    ):
        percent = (count / total * 100) if total > 0 else 0
        console.print(f"  {bug_type:<20} {count:>2} ({percent:>5.1f}%)")

    console.print()
    console.print("=" * 60)
    console.print()


# =============================================================================
# UTILITY COMMANDS
# =============================================================================


@app.command("cheatsheet")
def cheatsheet():
    """Show quick reference for all commands."""
    console.print(
        Panel.fit(
            """[bold]Getting Started[/bold]
  empathy morning           Start-of-day briefing
  empathy health            Quick health check
  empathy ship              Pre-commit validation
  empathy run               Interactive REPL

[bold]Memory System[/bold]
  empathy memory status     Check Redis & patterns
  empathy memory start      Start Redis server
  empathy memory patterns   List stored patterns

[bold]Cross-Session Service[/bold]
  empathy service start     Start coordination service
  empathy service status    Show service & sessions
  empathy service sessions  List active agents

[bold]Provider Config[/bold]
  empathy provider          Show current config
  empathy provider --set hybrid    Use best-of-breed
  empathy provider registry        List all models

[bold]Code Inspection[/bold]
  empathy scan .            Scan for issues
  empathy inspect .         Deep analysis (SARIF)
  empathy fix-all           Auto-fix everything

[bold]Pattern Learning[/bold]
  empathy learn --analyze 20    Learn from commits
  empathy sync-claude           Sync to Claude Code

[bold]Workflows[/bold]
  empathy workflow list     Show available workflows
  empathy workflow run <name>   Execute a workflow
  empathy workflow create <name> -p <patterns>  Create workflow (12x faster)
  empathy workflow list-patterns                List available patterns

[bold]Wizards[/bold]
  empathy wizard list       Show available wizards
  empathy wizard run <name> Execute a wizard
  empathy wizard create <name> -d <domain>  Create wizard (12x faster)
  empathy wizard list-patterns              List available patterns

[bold]Usage Telemetry[/bold]
  empathy telemetry show    View recent LLM calls & costs
  empathy telemetry savings Calculate cost savings (tier routing)
  empathy telemetry export  Export usage data (JSON/CSV)""",
            title="[bold blue]Empathy Framework Cheatsheet[/bold blue]",
        ),
    )


@app.command("dashboard")
def dashboard():
    """Launch visual dashboard."""
    subprocess.run([sys.executable, "-m", "empathy_os.cli", "dashboard"], check=False)


@app.command("costs")
def costs():
    """View API cost tracking."""
    subprocess.run([sys.executable, "-m", "empathy_os.cli", "costs"], check=False)


@app.command("init")
def init():
    """Create a new configuration file."""
    subprocess.run([sys.executable, "-m", "empathy_os.cli", "init"], check=False)


@app.command("status")
def status():
    """What needs attention now."""
    subprocess.run([sys.executable, "-m", "empathy_os.cli", "status"], check=False)


def main():
    """Entry point for the unified CLI."""
    app()


if __name__ == "__main__":
    main()
