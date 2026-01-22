"""CLI commands for meta-workflow system.

Provides command-line interface for:
- Listing available workflow templates
- Running meta-workflows
- Viewing analytics and insights
- Managing execution history

Usage:
    empathy meta-workflow list-templates
    empathy meta-workflow run <template_id>
    empathy meta-workflow analytics [template_id]
    empathy meta-workflow list-runs
    empathy meta-workflow show <run_id>

Created: 2026-01-17
"""

from datetime import datetime, timedelta
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree

from empathy_os.config import _validate_file_path
from empathy_os.meta_workflows import (
    MetaWorkflow,
    PatternLearner,
    TemplateRegistry,
    list_execution_results,
    load_execution_result,
)
from empathy_os.meta_workflows.intent_detector import IntentDetector

# Create Typer app for meta-workflow commands
meta_workflow_app = typer.Typer(
    name="meta-workflow",
    help="Meta-workflow system for dynamic agent team generation",
    no_args_is_help=True,
)

console = Console()


# =============================================================================
# Template Commands
# =============================================================================


@meta_workflow_app.command("list-templates")
def list_templates(
    storage_dir: str = typer.Option(
        ".empathy/meta_workflows/templates",
        "--storage-dir",
        "-d",
        help="Templates storage directory",
    ),
):
    """List all available workflow templates.

    Shows template metadata including:
    - Template ID and name
    - Description
    - Estimated cost range
    - Number of questions and agent rules
    """
    try:
        registry = TemplateRegistry(storage_dir=storage_dir)
        template_ids = registry.list_templates()

        if not template_ids:
            console.print("[yellow]No templates found.[/yellow]")
            console.print(f"\nLooking in: {storage_dir}")
            console.print("\nCreate templates by running workflow wizard or")
            console.print("placing template JSON files in the templates directory.")
            return

        # Count built-in vs user templates
        builtin_count = sum(1 for t in template_ids if registry.is_builtin(t))
        user_count = len(template_ids) - builtin_count

        console.print(f"\n[bold]Available Templates[/bold] ({len(template_ids)} total)")
        console.print(f"  [cyan]📦 Built-in:[/cyan] {builtin_count}  [green]👤 User:[/green] {user_count}\n")

        # Show migration hint for users coming from Crew workflows
        if builtin_count > 0:
            console.print("[dim]💡 Tip: Built-in templates replace deprecated Crew workflows.[/dim]")
            console.print("[dim]   See: empathy meta-workflow migrate --help[/dim]\n")

        for template_id in template_ids:
            template = registry.load_template(template_id)

            if template:
                # Add badge for built-in templates
                is_builtin = registry.is_builtin(template_id)
                badge = "[cyan]📦 BUILT-IN[/cyan]" if is_builtin else "[green]👤 USER[/green]"

                # Create info panel
                info_lines = [
                    f"[bold]{template.name}[/bold] {badge}",
                    f"[dim]{template.description}[/dim]",
                    "",
                    f"ID: {template.template_id}",
                    f"Version: {template.version}",
                    f"Author: {template.author}",
                    f"Tags: {', '.join(template.tags)}",
                    "",
                    f"Questions: {len(template.form_schema.questions)}",
                    f"Agent Rules: {len(template.agent_composition_rules)}",
                    "",
                    f"Est. Cost: ${template.estimated_cost_range[0]:.2f}-${template.estimated_cost_range[1]:.2f}",
                    f"Est. Duration: ~{template.estimated_duration_minutes} min",
                ]

                # Add quick start command
                info_lines.append("")
                info_lines.append(f"[bold]Quick Start:[/bold] empathy meta-workflow run {template_id}")

                console.print(Panel("\n".join(info_lines), border_style="blue" if is_builtin else "green"))
                console.print()

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1)


@meta_workflow_app.command("inspect")
def inspect_template(
    template_id: str = typer.Argument(..., help="Template ID to inspect"),
    storage_dir: str = typer.Option(
        ".empathy/meta_workflows/templates",
        "--storage-dir",
        "-d",
        help="Templates storage directory",
    ),
    show_rules: bool = typer.Option(
        False,
        "--show-rules",
        "-r",
        help="Show agent composition rules",
    ),
):
    """Inspect a specific template in detail.

    Shows comprehensive template information including:
    - Form questions and types
    - Agent composition rules (optional)
    - Configuration mappings
    """
    try:
        registry = TemplateRegistry(storage_dir=storage_dir)
        template = registry.load_template(template_id)

        if not template:
            console.print(f"[red]Template not found:[/red] {template_id}")
            raise typer.Exit(code=1)

        # Header
        console.print(f"\n[bold cyan]Template: {template.name}[/bold cyan]")
        console.print(f"[dim]{template.description}[/dim]\n")

        # Form Schema
        console.print("[bold]Form Questions:[/bold]")
        form_tree = Tree("📋 Questions")

        for i, question in enumerate(template.form_schema.questions, 1):
            question_text = f"[cyan]{question.text}[/cyan]"
            q_node = form_tree.add(f"{i}. {question_text}")
            q_node.add(f"ID: {question.id}")
            q_node.add(f"Type: {question.type.value}")
            if question.options:
                options_str = ", ".join(question.options[:3])
                if len(question.options) > 3:
                    options_str += f", ... ({len(question.options) - 3} more)"
                q_node.add(f"Options: {options_str}")
            if question.required:
                q_node.add("[yellow]Required[/yellow]")
            if question.default:
                q_node.add(f"Default: {question.default}")

        console.print(form_tree)

        # Agent Composition Rules (optional)
        if show_rules:
            console.print(f"\n[bold]Agent Composition Rules:[/bold] ({len(template.agent_composition_rules)})\n")

            for i, rule in enumerate(template.agent_composition_rules, 1):
                rule_lines = [
                    f"[bold cyan]{i}. {rule.role}[/bold cyan]",
                    f"   Base Template: {rule.base_template}",
                    f"   Tier Strategy: {rule.tier_strategy.value}",
                    f"   Tools: {', '.join(rule.tools) if rule.tools else 'None'}",
                ]

                if rule.required_responses:
                    rule_lines.append(f"   Required When: {rule.required_responses}")

                if rule.config_mapping:
                    rule_lines.append(f"   Config Mapping: {len(rule.config_mapping)} fields")

                console.print("\n".join(rule_lines))
                console.print()

        # Summary
        console.print("\n[bold]Summary:[/bold]")
        console.print(f"  Questions: {len(template.form_schema.questions)}")
        console.print(f"  Agent Rules: {len(template.agent_composition_rules)}")
        console.print(f"  Estimated Cost: ${template.estimated_cost_range[0]:.2f}-${template.estimated_cost_range[1]:.2f}")
        console.print()

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1)


# =============================================================================
# Plan Generation Commands (Claude Code Integration)
# =============================================================================


@meta_workflow_app.command("plan")
def generate_plan_cmd(
    template_id: str = typer.Argument(..., help="Template ID to generate plan for"),
    output_format: str = typer.Option(
        "markdown",
        "--format",
        "-f",
        help="Output format: markdown, skill, or json",
    ),
    output_file: str = typer.Option(
        None,
        "--output",
        "-o",
        help="Output file path (default: stdout)",
    ),
    use_defaults: bool = typer.Option(
        True,
        "--use-defaults/--interactive",
        help="Use default values or ask interactively",
    ),
    install_skill: bool = typer.Option(
        False,
        "--install",
        "-i",
        help="Install as Claude Code skill in .claude/commands/",
    ),
):
    """Generate execution plan for Claude Code (no API costs).

    This generates a plan that can be executed by Claude Code using your
    Max subscription instead of making API calls.

    Output formats:
    - markdown: Human-readable plan to paste into Claude Code
    - skill: Claude Code skill format for .claude/commands/
    - json: Structured format for programmatic use

    Examples:
        empathy meta-workflow plan release-prep
        empathy meta-workflow plan release-prep --format skill --install
        empathy meta-workflow plan test-coverage-boost -o plan.md
        empathy meta-workflow plan manage-docs --format json
    """
    try:
        from empathy_os.meta_workflows.plan_generator import generate_plan

        # Load template
        console.print(f"\n[bold]Generating plan for:[/bold] {template_id}")
        registry = TemplateRegistry()
        template = registry.load_template(template_id)

        if not template:
            console.print(f"[red]Template not found:[/red] {template_id}")
            raise typer.Exit(code=1)

        # Collect responses if interactive
        form_responses = None
        if not use_defaults and template.form_schema.questions:
            console.print("\n[bold]Configuration:[/bold]")
            form_responses = {}
            for question in template.form_schema.questions:
                if question.options:
                    # Multiple choice
                    console.print(f"\n{question.text}")
                    for i, opt in enumerate(question.options, 1):
                        default_mark = " (default)" if opt == question.default else ""
                        console.print(f"  {i}. {opt}{default_mark}")
                    choice = typer.prompt("Choice", default="1")
                    try:
                        idx = int(choice) - 1
                        form_responses[question.id] = question.options[idx]
                    except (ValueError, IndexError):
                        form_responses[question.id] = question.default or question.options[0]
                else:
                    # Yes/No or text
                    default = question.default or "Yes"
                    response = typer.prompt(question.text, default=default)
                    form_responses[question.id] = response

        # Generate plan
        plan_content = generate_plan(
            template_id=template_id,
            form_responses=form_responses,
            use_defaults=use_defaults,
            output_format=output_format,
        )

        # Handle output
        if install_skill:
            # Install as Claude Code skill
            skill_dir = Path(".claude/commands")
            skill_dir.mkdir(parents=True, exist_ok=True)
            skill_path = skill_dir / f"{template_id}.md"

            # Convert to skill format if not already
            if output_format != "skill":
                plan_content = generate_plan(
                    template_id=template_id,
                    form_responses=form_responses,
                    use_defaults=use_defaults,
                    output_format="skill",
                )

            validated_skill_path = _validate_file_path(str(skill_path))
            validated_skill_path.write_text(plan_content)
            console.print(f"\n[green]✓ Installed as Claude Code skill:[/green] {validated_skill_path}")
            console.print(f"\nRun with: [bold]/project:{template_id}[/bold]")

        elif output_file:
            # Write to file
            validated_output = _validate_file_path(output_file)
            validated_output.write_text(plan_content)
            console.print(f"\n[green]✓ Plan saved to:[/green] {validated_output}")

        else:
            # Print to stdout
            console.print("\n" + "=" * 60)
            console.print(plan_content)
            console.print("=" * 60)

        # Show usage hints
        console.print("\n[bold]Usage Options:[/bold]")
        console.print("1. Copy prompts into Claude Code conversation")
        console.print("2. Install as skill with: --install")
        console.print("3. Use with Claude Code Task tool")
        console.print("\n[dim]Cost: $0 (uses your Max subscription)[/dim]")

    except ImportError:
        console.print("[red]Plan generator not available.[/red]")
        console.print("This feature requires the plan_generator module.")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[red]Error generating plan:[/red] {e}")
        raise typer.Exit(code=1)


# =============================================================================
# Execution Commands
# =============================================================================


@meta_workflow_app.command("run")
def run_workflow(
    template_id: str = typer.Argument(..., help="Template ID to execute"),
    mock: bool = typer.Option(
        True,
        "--mock/--real",
        help="Use mock execution (for testing)",
    ),
    use_memory: bool = typer.Option(
        False,
        "--use-memory",
        "-m",
        help="Enable memory integration for enhanced analytics",
    ),
    use_defaults: bool = typer.Option(
        False,
        "--use-defaults",
        "-d",
        help="Use default values instead of asking questions (non-interactive mode)",
    ),
    user_id: str = typer.Option(
        "cli_user",
        "--user-id",
        "-u",
        help="User ID for memory integration",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        "-j",
        help="Output result as JSON (for programmatic use)",
    ),
):
    """Execute a meta-workflow from template.

    This will:
    1. Load the template
    2. Ask form questions interactively (or use defaults with --use-defaults)
    3. Generate dynamic agent team
    4. Execute agents (mock or real)
    5. Save results (files + optional memory)
    6. Display summary

    Examples:
        empathy meta-workflow run release-prep
        empathy meta-workflow run test-coverage-boost --real
        empathy meta-workflow run manage-docs --use-defaults
        empathy meta-workflow run release-prep --json --use-defaults
    """
    import json

    try:
        # Load template
        if not json_output:
            console.print(f"\n[bold]Loading template:[/bold] {template_id}")
        registry = TemplateRegistry()
        template = registry.load_template(template_id)

        if not template:
            if json_output:
                print(json.dumps({"success": False, "error": f"Template not found: {template_id}"}))
            else:
                console.print(f"[red]Template not found:[/red] {template_id}")
            raise typer.Exit(code=1)

        if not json_output:
            console.print(f"[green]✓[/green] {template.name}")

        # Setup memory if requested
        pattern_learner = None
        if use_memory:
            if not json_output:
                console.print("\n[bold]Initializing memory integration...[/bold]")
            from empathy_os.memory.unified import UnifiedMemory

            try:
                memory = UnifiedMemory(user_id=user_id)
                pattern_learner = PatternLearner(memory=memory)
                if not json_output:
                    console.print("[green]✓[/green] Memory enabled")
            except Exception as e:
                if not json_output:
                    console.print(f"[yellow]Warning:[/yellow] Memory initialization failed: {e}")
                    console.print("[yellow]Continuing without memory integration[/yellow]")

        # Create workflow
        workflow = MetaWorkflow(
            template=template,
            pattern_learner=pattern_learner,
        )

        # Execute (will ask questions via AskUserQuestion unless --use-defaults)
        if not json_output:
            console.print("\n[bold]Executing workflow...[/bold]")
            console.print(f"Mode: {'Mock' if mock else 'Real'}")
            if use_defaults:
                console.print("[cyan]Using default values (non-interactive)[/cyan]")

        result = workflow.execute(mock_execution=mock, use_defaults=use_defaults)

        # JSON output mode - print result as JSON and exit
        if json_output:
            output = {
                "run_id": result.run_id,
                "template_id": template_id,
                "timestamp": result.timestamp,
                "success": result.success,
                "error": result.error,
                "total_cost": result.total_cost,
                "total_duration": result.total_duration,
                "agents_created": len(result.agents_created),
                "form_responses": {
                    "template_id": result.form_responses.template_id,
                    "responses": result.form_responses.responses,
                    "timestamp": result.form_responses.timestamp,
                    "response_id": result.form_responses.response_id,
                },
                "agent_results": [
                    {
                        "agent_id": ar.agent_id,
                        "role": ar.role,
                        "success": ar.success,
                        "cost": ar.cost,
                        "duration": ar.duration,
                        "tier_used": ar.tier_used,
                        "output": ar.output,
                        "error": ar.error,
                    }
                    for ar in result.agent_results
                ],
            }
            print(json.dumps(output))
            return

        # Display summary (normal mode)
        console.print("\n[bold green]Execution Complete![/bold green]\n")

        summary_lines = [
            f"[bold]Run ID:[/bold] {result.run_id}",
            f"[bold]Status:[/bold] {'✅ Success' if result.success else '❌ Failed'}",
            "",
            f"[bold]Agents Created:[/bold] {len(result.agents_created)}",
            f"[bold]Agents Executed:[/bold] {len(result.agent_results)}",
            f"[bold]Total Cost:[/bold] ${result.total_cost:.2f}",
            f"[bold]Duration:[/bold] {result.total_duration:.1f}s",
        ]

        if result.error:
            summary_lines.append(f"\n[bold red]Error:[/bold red] {result.error}")

        console.print(Panel("\n".join(summary_lines), title="Execution Summary", border_style="green"))

        # Show agents
        console.print("\n[bold]Agents Executed:[/bold]\n")

        for agent_result in result.agent_results:
            status = "✅" if agent_result.success else "❌"
            console.print(
                f"  {status} [cyan]{agent_result.role}[/cyan] "
                f"(tier: {agent_result.tier_used}, cost: ${agent_result.cost:.2f})"
            )

        # Show where results saved
        console.print("\n[bold]Results saved to:[/bold]")
        console.print(f"  📁 Files: .empathy/meta_workflows/executions/{result.run_id}/")
        if use_memory and pattern_learner and pattern_learner.memory:
            console.print("  🧠 Memory: Long-term storage")

        console.print(f"\n[dim]View details: empathy meta-workflow show {result.run_id}[/dim]")
        console.print()

    except Exception as e:
        if json_output:
            print(json.dumps({"success": False, "error": str(e)}))
        else:
            console.print(f"\n[red]Error:[/red] {e}")
            import traceback
            traceback.print_exc()
        raise typer.Exit(code=1)


@meta_workflow_app.command("ask")
def natural_language_run(
    request: str = typer.Argument(..., help="Natural language description of what you need"),
    auto_run: bool = typer.Option(
        False,
        "--auto",
        "-a",
        help="Automatically run if high confidence match (>60%)",
    ),
    mock: bool = typer.Option(
        True,
        "--mock/--real",
        help="Use mock execution (for testing)",
    ),
    use_defaults: bool = typer.Option(
        True,
        "--use-defaults/--interactive",
        "-d/-i",
        help="Use default values (non-interactive)",
    ),
):
    """Create agent teams using natural language.

    Analyzes your request and suggests appropriate agent teams.
    Use --auto to automatically run the best match.

    Examples:
        empathy meta-workflow ask "I need to prepare for a release"
        empathy meta-workflow ask "improve my test coverage" --auto --real
        empathy meta-workflow ask "check if documentation is up to date"
    """
    try:
        detector = IntentDetector()
        matches = detector.detect(request)

        if not matches:
            console.print("\n[yellow]I couldn't identify a matching agent team for your request.[/yellow]")
            console.print("\n[bold]Available agent teams:[/bold]")
            console.print("  • [cyan]release-prep[/cyan] - Security, testing, code quality, documentation checks")
            console.print("  • [cyan]test-coverage-boost[/cyan] - Analyze and improve test coverage")
            console.print("  • [cyan]test-maintenance[/cyan] - Test lifecycle management")
            console.print("  • [cyan]manage-docs[/cyan] - Documentation sync and gap detection")
            console.print("\n[dim]Try: empathy meta-workflow run <template-id>[/dim]\n")
            return

        # Show detected matches
        console.print(f"\n[bold]Analyzing:[/bold] \"{request}\"\n")

        best_match = matches[0]
        confidence_pct = int(best_match.confidence * 100)

        # If auto-run and high confidence, run immediately
        if auto_run and best_match.confidence >= 0.6:
            console.print(f"[bold green]Auto-detected:[/bold green] {best_match.template_name} ({confidence_pct}% confidence)")
            console.print(f"[dim]{best_match.description}[/dim]\n")
            console.print(f"[bold]Running {best_match.template_id}...[/bold]\n")

            # Run the workflow
            run_workflow(
                template_id=best_match.template_id,
                mock=mock,
                use_memory=False,
                use_defaults=use_defaults,
                user_id="cli_user",
            )
            return

        # Show suggestions
        console.print("[bold]Suggested Agent Teams:[/bold]\n")

        for i, match in enumerate(matches[:3], 1):
            confidence = int(match.confidence * 100)
            style = "green" if match.confidence >= 0.6 else "yellow" if match.confidence >= 0.4 else "dim"

            console.print(f"  {i}. [{style}]{match.template_name}[/{style}] ({confidence}% match)")
            console.print(f"     [dim]{match.description}[/dim]")
            if match.matched_keywords:
                keywords = ", ".join(match.matched_keywords[:5])
                console.print(f"     [dim]Matched: {keywords}[/dim]")
            console.print(f"     Run: [cyan]empathy meta-workflow run {match.template_id}[/cyan]")
            console.print()

        # Prompt to run best match
        if best_match.confidence >= 0.5:
            console.print("[bold]Quick Run:[/bold] Use [cyan]--auto[/cyan] to automatically run the best match")
            console.print(f"[dim]Example: empathy meta-workflow ask \"{request}\" --auto --real[/dim]\n")

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1)


@meta_workflow_app.command("detect")
def detect_intent(
    request: str = typer.Argument(..., help="Natural language request to analyze"),
    threshold: float = typer.Option(
        0.3,
        "--threshold",
        "-t",
        help="Minimum confidence threshold (0.0-1.0)",
    ),
):
    """Detect intent from natural language without running.

    Useful for testing what agent teams would be suggested for a given request.

    Examples:
        empathy meta-workflow detect "check security vulnerabilities"
        empathy meta-workflow detect "generate more tests" --threshold 0.5
    """
    try:
        detector = IntentDetector()
        matches = detector.detect(request, threshold=threshold)

        console.print(f"\n[bold]Intent Analysis:[/bold] \"{request}\"\n")
        console.print(f"[dim]Threshold: {threshold:.0%}[/dim]\n")

        if not matches:
            console.print("[yellow]No matches above threshold.[/yellow]\n")
            return

        # Create table
        table = Table(show_header=True)
        table.add_column("Template", style="cyan")
        table.add_column("Confidence", justify="right")
        table.add_column("Matched Keywords")
        table.add_column("Would Auto-Run?")

        for match in matches:
            confidence = f"{match.confidence:.0%}"
            keywords = ", ".join(match.matched_keywords[:4])
            auto_run = "✅ Yes" if match.confidence >= 0.6 else "❌ No"

            table.add_row(
                match.template_id,
                confidence,
                keywords or "-",
                auto_run,
            )

        console.print(table)
        console.print()

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1)


# =============================================================================
# Analytics Commands
# =============================================================================


@meta_workflow_app.command("analytics")
def show_analytics(
    template_id: str | None = typer.Argument(
        None,
        help="Template ID to analyze (optional, all if not specified)",
    ),
    min_confidence: float = typer.Option(
        0.5,
        "--min-confidence",
        "-c",
        help="Minimum confidence threshold (0.0-1.0)",
    ),
    use_memory: bool = typer.Option(
        False,
        "--use-memory",
        "-m",
        help="Use memory-enhanced analytics",
    ),
):
    """Show pattern learning analytics and recommendations.

    Displays:
    - Execution statistics
    - Tier performance insights
    - Cost analysis
    - Recommendations
    """
    try:
        # Initialize pattern learner
        pattern_learner = PatternLearner()

        if use_memory:
            console.print("[bold]Initializing memory-enhanced analytics...[/bold]\n")
            from empathy_os.memory.unified import UnifiedMemory
            memory = UnifiedMemory(user_id="cli_analytics")
            pattern_learner = PatternLearner(memory=memory)

        # Generate report
        report = pattern_learner.generate_analytics_report(template_id=template_id)

        # Display summary
        summary = report["summary"]

        console.print("\n[bold cyan]Meta-Workflow Analytics Report[/bold cyan]")
        if template_id:
            console.print(f"[dim]Template: {template_id}[/dim]")
        console.print()

        summary_table = Table(show_header=False, box=None)
        summary_table.add_column("Metric", style="bold")
        summary_table.add_column("Value")

        summary_table.add_row("Total Runs", str(summary["total_runs"]))
        summary_table.add_row(
            "Successful",
            f"{summary['successful_runs']} ({summary['success_rate']:.0%})"
        )
        summary_table.add_row("Total Cost", f"${summary['total_cost']:.2f}")
        summary_table.add_row("Avg Cost/Run", f"${summary['avg_cost_per_run']:.2f}")
        summary_table.add_row("Total Agents", str(summary["total_agents_created"]))
        summary_table.add_row("Avg Agents/Run", f"{summary['avg_agents_per_run']:.1f}")

        console.print(Panel(summary_table, title="Summary", border_style="cyan"))

        # Recommendations
        recommendations = report.get("recommendations", [])
        if recommendations:
            console.print("\n[bold]Recommendations:[/bold]\n")
            for rec in recommendations:
                console.print(f"  {rec}")

        # Insights
        insights = report.get("insights", {})

        if insights.get("tier_performance"):
            console.print("\n[bold]Tier Performance:[/bold]\n")
            for insight in insights["tier_performance"][:5]:  # Top 5
                console.print(f"  • {insight['description']}")
                console.print(f"    [dim]Confidence: {insight['confidence']:.0%} (n={insight['sample_size']})[/dim]")

        if insights.get("cost_analysis"):
            console.print("\n[bold]Cost Analysis:[/bold]\n")
            for insight in insights["cost_analysis"]:
                console.print(f"  • {insight['description']}")

                # Tier breakdown
                breakdown = insight['data'].get('tier_breakdown', {})
                if breakdown:
                    console.print("\n  [dim]By Tier:[/dim]")
                    for tier, stats in breakdown.items():
                        console.print(
                            f"    {tier}: ${stats['avg']:.2f} avg "
                            f"(${stats['total']:.2f} total, {stats['count']} runs)"
                        )

        if insights.get("failure_analysis"):
            console.print("\n[bold yellow]Failure Analysis:[/bold yellow]\n")
            for insight in insights["failure_analysis"]:
                console.print(f"  ⚠️  {insight['description']}")

        console.print()

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1)


# =============================================================================
# Execution History Commands
# =============================================================================


@meta_workflow_app.command("list-runs")
def list_runs(
    template_id: str | None = typer.Option(
        None,
        "--template",
        "-t",
        help="Filter by template ID",
    ),
    limit: int = typer.Option(
        10,
        "--limit",
        "-n",
        help="Maximum number of results",
    ),
):
    """List execution history.

    Shows recent workflow executions with:
    - Run ID and timestamp
    - Template name
    - Success status
    - Cost and duration
    """
    try:
        run_ids = list_execution_results()

        if not run_ids:
            console.print("[yellow]No execution results found.[/yellow]")
            return

        console.print(f"\n[bold]Recent Executions[/bold] (showing {min(limit, len(run_ids))} of {len(run_ids)}):\n")

        # Create table
        table = Table(show_header=True)
        table.add_column("Run ID", style="cyan")
        table.add_column("Template")
        table.add_column("Status")
        table.add_column("Cost", justify="right")
        table.add_column("Duration", justify="right")
        table.add_column("Timestamp")

        count = 0
        for run_id in run_ids[:limit]:
            try:
                result = load_execution_result(run_id)

                # Filter by template if specified
                if template_id and result.template_id != template_id:
                    continue

                status = "✅" if result.success else "❌"
                cost = f"${result.total_cost:.2f}"
                duration = f"{result.total_duration:.1f}s"

                # Parse timestamp
                try:
                    ts = datetime.fromisoformat(result.timestamp)
                    timestamp = ts.strftime("%Y-%m-%d %H:%M")
                except Exception:
                    timestamp = result.timestamp[:16]

                table.add_row(
                    run_id,
                    result.template_id,
                    status,
                    cost,
                    duration,
                    timestamp,
                )

                count += 1

            except Exception as e:
                console.print(f"[yellow]Warning:[/yellow] Failed to load {run_id}: {e}")
                continue

        if count == 0:
            if template_id:
                console.print(f"[yellow]No executions found for template: {template_id}[/yellow]")
            else:
                console.print("[yellow]No valid execution results found.[/yellow]")
            return

        console.print(table)
        console.print("\n[dim]View details: empathy meta-workflow show <run_id>[/dim]\n")

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1)


@meta_workflow_app.command("show")
def show_execution(
    run_id: str = typer.Argument(..., help="Run ID to display"),
    format: str = typer.Option(
        "text",
        "--format",
        "-f",
        help="Output format (text or json)",
    ),
):
    """Show detailed execution report.

    Displays comprehensive information about a specific workflow execution:
    - Form responses
    - Agents created and executed
    - Cost breakdown
    - Success/failure details
    """
    try:
        result = load_execution_result(run_id)

        if format == "json":
            # JSON output
            print(result.to_json())
            return

        # Text format (default)
        console.print(f"\n[bold cyan]Execution Report: {run_id}[/bold cyan]\n")

        # Status
        status = "✅ Success" if result.success else "❌ Failed"
        console.print(f"[bold]Status:[/bold] {status}")
        console.print(f"[bold]Template:[/bold] {result.template_id}")
        console.print(f"[bold]Timestamp:[/bold] {result.timestamp}")

        if result.error:
            console.print(f"\n[bold red]Error:[/bold red] {result.error}\n")

        # Summary
        console.print("\n[bold]Summary:[/bold]")
        console.print(f"  Agents Created: {len(result.agents_created)}")
        console.print(f"  Agents Executed: {len(result.agent_results)}")
        console.print(f"  Total Cost: ${result.total_cost:.2f}")
        console.print(f"  Duration: {result.total_duration:.1f}s")

        # Form Responses
        console.print("\n[bold]Form Responses:[/bold]\n")
        for key, value in result.form_responses.responses.items():
            console.print(f"  [cyan]{key}:[/cyan] {value}")

        # Agents
        console.print("\n[bold]Agents Executed:[/bold]\n")
        for i, agent_result in enumerate(result.agent_results, 1):
            status_emoji = "✅" if agent_result.success else "❌"
            console.print(f"  {i}. {status_emoji} [cyan]{agent_result.role}[/cyan]")
            console.print(f"     Tier: {agent_result.tier_used}")
            console.print(f"     Cost: ${agent_result.cost:.2f}")
            console.print(f"     Duration: {agent_result.duration:.1f}s")
            if agent_result.error:
                console.print(f"     [red]Error: {agent_result.error}[/red]")
            console.print()

        # Cost breakdown
        console.print("[bold]Cost Breakdown by Tier:[/bold]\n")
        tier_costs = {}
        for agent_result in result.agent_results:
            tier = agent_result.tier_used
            tier_costs[tier] = tier_costs.get(tier, 0.0) + agent_result.cost

        for tier, cost in sorted(tier_costs.items()):
            console.print(f"  {tier}: ${cost:.2f}")

        console.print()

    except FileNotFoundError:
        console.print(f"[red]Execution not found:[/red] {run_id}")
        console.print("\n[dim]List available runs: empathy meta-workflow list-runs[/dim]")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1)


# =============================================================================
# Maintenance Commands
# =============================================================================


@meta_workflow_app.command("cleanup")
def cleanup_executions(
    older_than_days: int = typer.Option(
        30,
        "--older-than",
        "-d",
        help="Delete executions older than N days",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Show what would be deleted without deleting",
    ),
    template_id: str | None = typer.Option(
        None,
        "--template",
        "-t",
        help="Filter by template ID",
    ),
):
    """Clean up old execution results.

    Deletes execution directories older than the specified number of days.
    Use --dry-run to preview what would be deleted.
    """
    try:
        cutoff_date = datetime.now() - timedelta(days=older_than_days)

        run_ids = list_execution_results()

        if not run_ids:
            console.print("[yellow]No execution results found.[/yellow]")
            return

        to_delete = []

        for run_id in run_ids:
            try:
                result = load_execution_result(run_id)

                # Filter by template if specified
                if template_id and result.template_id != template_id:
                    continue

                # Parse timestamp
                ts = datetime.fromisoformat(result.timestamp)

                if ts < cutoff_date:
                    to_delete.append((run_id, result, ts))

            except Exception as e:
                console.print(f"[yellow]Warning:[/yellow] Failed to load {run_id}: {e}")
                continue

        if not to_delete:
            console.print(
                f"[green]No executions older than {older_than_days} days found.[/green]"
            )
            return

        # Show what will be deleted
        console.print(f"\n[bold]Executions to delete:[/bold] ({len(to_delete)})\n")

        table = Table(show_header=True)
        table.add_column("Run ID", style="cyan")
        table.add_column("Template")
        table.add_column("Age (days)", justify="right")
        table.add_column("Cost", justify="right")

        total_cost_saved = 0.0
        for run_id, result, ts in to_delete:
            age_days = (datetime.now() - ts).days
            table.add_row(
                run_id,
                result.template_id,
                str(age_days),
                f"${result.total_cost:.2f}",
            )
            total_cost_saved += result.total_cost

        console.print(table)
        console.print(f"\nTotal cost represented: ${total_cost_saved:.2f}")

        if dry_run:
            console.print("\n[yellow]DRY RUN - No files deleted[/yellow]")
            console.print(f"Run without --dry-run to delete {len(to_delete)} executions")
            return

        # Confirm deletion
        if not typer.confirm(f"\nDelete {len(to_delete)} execution(s)?"):
            console.print("[yellow]Cancelled[/yellow]")
            return

        # Delete
        import shutil
        deleted = 0
        for run_id, _, _ in to_delete:
            try:
                run_dir = Path.home() / ".empathy" / "meta_workflows" / "executions" / run_id
                if run_dir.exists():
                    shutil.rmtree(run_dir)
                    deleted += 1
            except Exception as e:
                console.print(f"[red]Failed to delete {run_id}:[/red] {e}")

        console.print(f"\n[green]✓ Deleted {deleted} execution(s)[/green]\n")

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1)


# =============================================================================
# Memory Search Commands
# =============================================================================


@meta_workflow_app.command("search-memory")
def search_memory(
    query: str = typer.Argument(..., help="Search query for patterns"),
    pattern_type: str | None = typer.Option(
        None,
        "--type",
        "-t",
        help="Filter by pattern type (e.g., 'meta_workflow_execution')",
    ),
    limit: int = typer.Option(
        10,
        "--limit",
        "-l",
        help="Maximum number of results to return",
    ),
    user_id: str = typer.Option(
        "cli_user",
        "--user-id",
        "-u",
        help="User ID for memory access",
    ),
):
    """Search memory for patterns using keyword matching.

    Searches long-term memory for patterns matching the query.
    Uses relevance scoring: exact phrase (10 pts), keyword in content (2 pts),
    keyword in metadata (1 pt).

    Examples:
        empathy meta-workflow search-memory "successful workflow"
        empathy meta-workflow search-memory "test coverage" --type meta_workflow_execution
        empathy meta-workflow search-memory "error" --limit 20
    """
    try:
        from empathy_os.memory.unified import UnifiedMemory

        console.print(f"\n[bold]Searching memory for:[/bold] '{query}'")
        if pattern_type:
            console.print(f"[dim]Pattern type: {pattern_type}[/dim]")
        console.print()

        # Initialize memory
        memory = UnifiedMemory(user_id=user_id)

        # Search
        results = memory.search_patterns(
            query=query,
            pattern_type=pattern_type,
            limit=limit,
        )

        if not results:
            console.print("[yellow]No matching patterns found.[/yellow]\n")
            return

        # Display results
        console.print(f"[green]Found {len(results)} matching pattern(s):[/green]\n")

        for i, pattern in enumerate(results, 1):
            panel = Panel(
                f"[bold]Pattern ID:[/bold] {pattern.get('pattern_id', 'N/A')}\n"
                f"[bold]Type:[/bold] {pattern.get('pattern_type', 'N/A')}\n"
                f"[bold]Classification:[/bold] {pattern.get('classification', 'N/A')}\n\n"
                f"[bold]Content:[/bold]\n{str(pattern.get('content', 'N/A'))[:200]}...\n\n"
                f"[bold]Metadata:[/bold] {pattern.get('metadata', {})}",
                title=f"Result {i}/{len(results)}",
                border_style="blue",
            )
            console.print(panel)
            console.print()

    except ImportError:
        console.print(
            "[red]Error:[/red] UnifiedMemory not available. "
            "Ensure memory module is installed."
        )
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1)


# =============================================================================
# Session Context Commands
# =============================================================================


@meta_workflow_app.command("session-stats")
def show_session_stats(
    session_id: str | None = typer.Option(
        None,
        "--session-id",
        "-s",
        help="Session ID (optional, creates new if not specified)",
    ),
    user_id: str = typer.Option(
        "cli_user",
        "--user-id",
        "-u",
        help="User ID for session",
    ),
):
    """Show session context statistics.

    Displays information about user's session including:
    - Recent form choices
    - Templates used
    - Choice counts

    Examples:
        empathy meta-workflow session-stats
        empathy meta-workflow session-stats --session-id sess_123
    """
    try:
        from empathy_os.memory.unified import UnifiedMemory
        from empathy_os.meta_workflows.session_context import SessionContext

        # Initialize memory and session
        memory = UnifiedMemory(user_id=user_id)
        session = SessionContext(
            memory=memory,
            session_id=session_id,
        )

        console.print("\n[bold]Session Statistics[/bold]")
        console.print(f"[dim]Session ID: {session.session_id}[/dim]")
        console.print(f"[dim]User ID: {session.user_id}[/dim]\n")

        # Get stats
        stats = session.get_session_stats()

        # Display
        table = Table(show_header=True)
        table.add_column("Metric", style="cyan")
        table.add_column("Value")

        table.add_row("Total Choices", str(stats.get("choice_count", 0)))
        table.add_row("Templates Used", str(len(stats.get("templates_used", []))))
        table.add_row(
            "Most Recent Choice",
            stats.get("most_recent_choice_timestamp", "N/A")
        )

        console.print(table)
        console.print()

        # Show templates used
        templates = stats.get("templates_used", [])
        if templates:
            console.print("[bold]Templates Used:[/bold]")
            for template_id in templates:
                console.print(f"  • {template_id}")
            console.print()

    except ImportError:
        console.print(
            "[red]Error:[/red] Session context not available. "
            "Ensure memory and session modules are installed."
        )
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1)


@meta_workflow_app.command("suggest-defaults")
def suggest_defaults_cmd(
    template_id: str = typer.Argument(..., help="Template ID to get defaults for"),
    session_id: str | None = typer.Option(
        None,
        "--session-id",
        "-s",
        help="Session ID (optional)",
    ),
    user_id: str = typer.Option(
        "cli_user",
        "--user-id",
        "-u",
        help="User ID for session",
    ),
):
    """Get suggested default values based on session history.

    Analyzes recent choices for the specified template and suggests
    intelligent defaults for the next run.

    Examples:
        empathy meta-workflow suggest-defaults test_creation_management_workflow
        empathy meta-workflow suggest-defaults python_package_publish --session-id sess_123
    """
    try:
        from empathy_os.memory.unified import UnifiedMemory
        from empathy_os.meta_workflows.session_context import SessionContext

        # Initialize
        memory = UnifiedMemory(user_id=user_id)
        session = SessionContext(memory=memory, session_id=session_id)

        # Load template
        registry = TemplateRegistry()
        template = registry.load_template(template_id)
        if not template:
            console.print(f"[red]Error:[/red] Template not found: {template_id}")
            raise typer.Exit(code=1)

        console.print(f"\n[bold]Suggested Defaults for:[/bold] {template.name}")
        console.print(f"[dim]Template ID: {template_id}[/dim]\n")

        # Get suggestions
        defaults = session.suggest_defaults(
            template_id=template_id,
            form_schema=template.form_schema,
        )

        if not defaults:
            console.print("[yellow]No suggestions available (no recent history).[/yellow]\n")
            return

        # Display
        console.print(f"[green]Found {len(defaults)} suggested default(s):[/green]\n")

        table = Table(show_header=True)
        table.add_column("Question ID", style="cyan")
        table.add_column("Suggested Value")

        for question_id, value in defaults.items():
            # Find the question to get the display text
            question = next(
                (q for q in template.form_schema.questions if q.id == question_id),
                None
            )
            question_text = question.text if question else question_id

            value_str = str(value)
            if isinstance(value, list):
                value_str = ", ".join(str(v) for v in value)

            table.add_row(question_text, value_str)

        console.print(table)
        console.print(
            f"\n[dim]Use these defaults by running:[/dim]\n"
            f"  empathy meta-workflow run {template_id} --use-defaults\n"
        )

    except ImportError:
        console.print(
            "[red]Error:[/red] Session context not available. "
            "Ensure memory and session modules are installed."
        )
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1)


# =============================================================================
# Migration Commands
# =============================================================================


@meta_workflow_app.command("migrate")
def show_migration_guide(
    crew_name: str | None = typer.Argument(
        None,
        help="Specific Crew workflow name (optional)",
    ),
):
    """Show migration guide from deprecated Crew workflows.

    Displays information about migrating from the deprecated Crew-based
    workflows to the new meta-workflow system.

    Examples:
        empathy meta-workflow migrate
        empathy meta-workflow migrate ReleasePreparationCrew
    """
    # Migration mapping
    CREW_MIGRATION_MAP = {
        "ReleasePreparationCrew": {
            "template_id": "release-prep",
            "old_import": "from empathy_os.workflows.release_prep_crew import ReleasePreparationCrew",
            "old_usage": "crew = ReleasePreparationCrew(project_root='.')\nresult = await crew.execute()",
            "new_usage": "empathy meta-workflow run release-prep",
        },
        "TestCoverageBoostCrew": {
            "template_id": "test-coverage-boost",
            "old_import": "from empathy_os.workflows.test_coverage_boost_crew import TestCoverageBoostCrew",
            "old_usage": "crew = TestCoverageBoostCrew(target_coverage=85.0)\nresult = await crew.execute()",
            "new_usage": "empathy meta-workflow run test-coverage-boost",
        },
        "TestMaintenanceCrew": {
            "template_id": "test-maintenance",
            "old_import": "from empathy_os.workflows.test_maintenance_crew import TestMaintenanceCrew",
            "old_usage": "crew = TestMaintenanceCrew('.')\nresult = await crew.run(mode='full')",
            "new_usage": "empathy meta-workflow run test-maintenance",
        },
        "ManageDocumentationCrew": {
            "template_id": "manage-docs",
            "old_import": "from empathy_os.workflows.manage_documentation import ManageDocumentationCrew",
            "old_usage": "crew = ManageDocumentationCrew()\nresult = await crew.execute(path='./src')",
            "new_usage": "empathy meta-workflow run manage-docs",
        },
    }

    console.print("\n[bold cyan]🔄 Crew → Meta-Workflow Migration Guide[/bold cyan]\n")

    if crew_name:
        # Show specific migration
        if crew_name not in CREW_MIGRATION_MAP:
            console.print(f"[red]Unknown Crew workflow:[/red] {crew_name}")
            console.print("\n[bold]Available Crew workflows:[/bold]")
            for name in CREW_MIGRATION_MAP:
                console.print(f"  • {name}")
            raise typer.Exit(code=1)

        info = CREW_MIGRATION_MAP[crew_name]
        console.print(f"[bold]Migrating:[/bold] {crew_name}\n")

        console.print("[bold red]DEPRECATED (Before):[/bold red]")
        console.print(f"[dim]{info['old_import']}[/dim]")
        console.print(f"\n[yellow]{info['old_usage']}[/yellow]\n")

        console.print("[bold green]RECOMMENDED (After):[/bold green]")
        console.print(f"[green]{info['new_usage']}[/green]\n")

        console.print("[bold]Benefits:[/bold]")
        console.print("  ✓ No CrewAI/LangChain dependency required")
        console.print("  ✓ Interactive configuration via Socratic questions")
        console.print("  ✓ Automatic cost optimization with tier escalation")
        console.print("  ✓ Session context for learning preferences")
        console.print("  ✓ Built-in analytics and pattern learning\n")

        console.print(f"[dim]Try it now: empathy meta-workflow run {info['template_id']}[/dim]\n")

    else:
        # Show overview
        console.print("[bold]Why Migrate?[/bold]")
        console.print("  The Crew-based workflows are deprecated since v4.3.0.")
        console.print("  The meta-workflow system provides the same functionality")
        console.print("  with better cost optimization and no extra dependencies.\n")

        # Show migration table
        table = Table(title="Migration Map", show_header=True)
        table.add_column("Deprecated Crew", style="yellow")
        table.add_column("Meta-Workflow Command", style="green")
        table.add_column("Template ID", style="cyan")

        for crew_name, info in CREW_MIGRATION_MAP.items():
            table.add_row(
                crew_name,
                info["new_usage"],
                info["template_id"],
            )

        console.print(table)

        console.print("\n[bold]Quick Start:[/bold]")
        console.print("  1. List available templates: [cyan]empathy meta-workflow list-templates[/cyan]")
        console.print("  2. Run a workflow: [cyan]empathy meta-workflow run release-prep[/cyan]")
        console.print("  3. View results: [cyan]empathy meta-workflow list-runs[/cyan]\n")

        console.print("[bold]More Details:[/bold]")
        console.print("  • Migration guide: [dim]empathy meta-workflow migrate <CrewName>[/dim]")
        console.print("  • Full documentation: [dim]docs/CREWAI_MIGRATION.md[/dim]\n")


# =============================================================================
# Dynamic Agent/Team Creation Commands (v4.4)
# =============================================================================


@meta_workflow_app.command("create-agent")
def create_agent(
    interactive: bool = typer.Option(
        True,
        "--interactive/--quick",
        "-i/-q",
        help="Use interactive Socratic-guided creation",
    ),
    name: str = typer.Option(
        None,
        "--name",
        "-n",
        help="Agent name (for quick mode)",
    ),
    role: str = typer.Option(
        None,
        "--role",
        "-r",
        help="Agent role description (for quick mode)",
    ),
    tier: str = typer.Option(
        "capable",
        "--tier",
        "-t",
        help="Model tier: cheap, capable, or premium",
    ),
    output_file: str = typer.Option(
        None,
        "--output",
        "-o",
        help="Save agent spec to file",
    ),
):
    """Create a custom AI agent with Socratic-guided questions.

    Interactive mode asks clarifying questions to help you define:
    - Agent capabilities and responsibilities
    - Model tier selection (cost vs quality tradeoff)
    - Tools and success criteria

    Quick mode creates an agent directly from provided options.

    Examples:
        empathy meta-workflow create-agent --interactive
        empathy meta-workflow create-agent -q --name "SecurityBot" --role "Scan for vulnerabilities"
    """
    import json

    if interactive:
        console.print("\n[bold cyan]🤖 Create Custom Agent - Socratic Guide[/bold cyan]\n")
        console.print("[dim]I'll ask you a few questions to help define your agent.[/dim]\n")

        # Question 1: Purpose
        console.print("[bold]1. What should this agent do?[/bold]")
        purpose = typer.prompt("   Describe the agent's main purpose")

        # Question 2: Specific tasks
        console.print("\n[bold]2. What specific tasks will it perform?[/bold]")
        console.print("   [dim]Examples: analyze code, generate tests, review PRs, write docs[/dim]")
        tasks = typer.prompt("   List main tasks (comma-separated)")

        # Question 3: Tier selection
        console.print("\n[bold]3. What quality/cost balance do you need?[/bold]")
        console.print("   [dim]cheap[/dim]    - Fast & low-cost, good for simple analysis")
        console.print("   [dim]capable[/dim]  - Balanced, good for most development tasks")
        console.print("   [dim]premium[/dim]  - Highest quality, for complex reasoning")
        tier = typer.prompt("   Select tier", default="capable")

        # Question 4: Tools
        console.print("\n[bold]4. What tools should it have access to?[/bold]")
        console.print("   [dim]Examples: file_read, file_write, web_search, code_exec[/dim]")
        tools_input = typer.prompt("   List tools (comma-separated, or 'none')", default="none")
        tools = [t.strip() for t in tools_input.split(",")] if tools_input != "none" else []

        # Question 5: Success criteria
        console.print("\n[bold]5. How will you measure success?[/bold]")
        success = typer.prompt("   Describe success criteria")

        # Generate name from purpose
        name = purpose.split()[0].title() + "Agent" if not name else name

        # Build agent spec
        agent_spec = {
            "name": name,
            "role": purpose,
            "tasks": [t.strip() for t in tasks.split(",")],
            "tier": tier,
            "tools": tools,
            "success_criteria": success,
            "base_template": "generic",
        }

    else:
        # Quick mode
        if not name or not role:
            console.print("[red]Error:[/red] --name and --role required in quick mode")
            console.print("[dim]Use --interactive for guided creation[/dim]")
            raise typer.Exit(code=1)

        agent_spec = {
            "name": name,
            "role": role,
            "tier": tier,
            "tools": [],
            "success_criteria": "Task completed successfully",
            "base_template": "generic",
        }

    # Display result
    console.print("\n[bold green]✓ Agent Specification Created[/bold green]\n")

    spec_json = json.dumps(agent_spec, indent=2)
    console.print(Panel(spec_json, title=f"Agent: {agent_spec['name']}", border_style="green"))

    # Save if requested
    if output_file:
        validated_output = _validate_file_path(output_file)
        validated_output.write_text(spec_json)
        console.print(f"\n[green]Saved to:[/green] {validated_output}")

    # Show usage
    console.print("\n[bold]Next Steps:[/bold]")
    console.print("  1. Use this agent in a custom team: [cyan]empathy meta-workflow create-team[/cyan]")
    console.print("  2. Or add to an existing template manually")
    console.print(f"\n[dim]Agent tier '{tier}' will cost approximately:")
    costs = {"cheap": "$0.001-0.01", "capable": "$0.01-0.05", "premium": "$0.05-0.20"}
    console.print(f"   {costs.get(tier, costs['capable'])} per execution[/dim]\n")


@meta_workflow_app.command("create-team")
def create_team(
    interactive: bool = typer.Option(
        True,
        "--interactive/--quick",
        "-i/-q",
        help="Use interactive Socratic-guided creation",
    ),
    name: str = typer.Option(
        None,
        "--name",
        "-n",
        help="Team name (for quick mode)",
    ),
    goal: str = typer.Option(
        None,
        "--goal",
        "-g",
        help="Team goal description (for quick mode)",
    ),
    output_file: str = typer.Option(
        None,
        "--output",
        "-o",
        help="Save team template to file",
    ),
):
    """Create a custom AI agent team with Socratic-guided workflow.

    Interactive mode asks clarifying questions to help you define:
    - Team composition and agent roles
    - Collaboration pattern (sequential, parallel, mixed)
    - Success criteria and cost estimates

    Examples:
        empathy meta-workflow create-team --interactive
        empathy meta-workflow create-team -q --name "ReviewTeam" --goal "Code review pipeline"
    """
    import json

    if interactive:
        console.print("\n[bold cyan]👥 Create Custom Agent Team - Socratic Guide[/bold cyan]\n")
        console.print("[dim]I'll help you design a team of agents that work together.[/dim]\n")

        # Question 1: Goal
        console.print("[bold]1. What is the team's overall goal?[/bold]")
        console.print("   [dim]Example: prepare code for production release[/dim]")
        goal = typer.prompt("   Describe the team's mission")

        # Question 2: Agent count
        console.print("\n[bold]2. How many agents should be on this team?[/bold]")
        console.print("   [dim]Typical teams have 2-5 agents with specialized roles[/dim]")
        agent_count = typer.prompt("   Number of agents", default="3")
        agent_count = int(agent_count)

        # Question 3: Agent roles
        console.print(f"\n[bold]3. Define {agent_count} agent roles:[/bold]")
        console.print("   [dim]Common roles: analyst, reviewer, generator, validator, reporter[/dim]")

        agents = []
        for i in range(agent_count):
            console.print(f"\n   [bold]Agent {i+1}:[/bold]")
            role = typer.prompt("     Role name")
            purpose = typer.prompt("     What does this agent do?")
            tier = typer.prompt("     Tier (cheap/capable/premium)", default="capable")

            agents.append({
                "role": role,
                "purpose": purpose,
                "tier": tier,
                "base_template": "generic",
            })

        # Question 4: Collaboration pattern
        console.print("\n[bold]4. How should agents collaborate?[/bold]")
        console.print("   [dim]sequential[/dim] - Each agent waits for the previous one")
        console.print("   [dim]parallel[/dim]   - All agents run simultaneously")
        console.print("   [dim]mixed[/dim]      - Some parallel, then sequential synthesis")
        pattern = typer.prompt("   Collaboration pattern", default="sequential")

        # Question 5: Team name
        console.print("\n[bold]5. What should we call this team?[/bold]")
        name = typer.prompt("   Team name", default=goal.split()[0].title() + "Team")

        # Build team template
        team_template = {
            "id": name.lower().replace(" ", "-"),
            "name": name,
            "description": goal,
            "collaboration_pattern": pattern,
            "agents": agents,
            "estimated_cost_range": {
                "min": len(agents) * 0.01,
                "max": len(agents) * 0.15,
            },
        }

    else:
        # Quick mode
        if not name or not goal:
            console.print("[red]Error:[/red] --name and --goal required in quick mode")
            console.print("[dim]Use --interactive for guided creation[/dim]")
            raise typer.Exit(code=1)

        # Create a default 3-agent team
        team_template = {
            "id": name.lower().replace(" ", "-"),
            "name": name,
            "description": goal,
            "collaboration_pattern": "sequential",
            "agents": [
                {"role": "Analyst", "purpose": "Analyze requirements", "tier": "cheap", "base_template": "generic"},
                {"role": "Executor", "purpose": "Perform main task", "tier": "capable", "base_template": "generic"},
                {"role": "Validator", "purpose": "Verify results", "tier": "capable", "base_template": "generic"},
            ],
            "estimated_cost_range": {"min": 0.03, "max": 0.45},
        }

    # Display result
    console.print("\n[bold green]✓ Agent Team Template Created[/bold green]\n")

    spec_json = json.dumps(team_template, indent=2)
    console.print(Panel(spec_json, title=f"Team: {team_template['name']}", border_style="green"))

    # Save if requested
    if output_file:
        validated_output = _validate_file_path(output_file)
        validated_output.write_text(spec_json)
        console.print(f"\n[green]Saved to:[/green] {validated_output}")

    # Show usage
    console.print("\n[bold]Next Steps:[/bold]")
    console.print(f"  1. Save as template: [cyan]--output .empathy/meta_workflows/templates/{team_template['id']}.json[/cyan]")
    console.print(f"  2. Run the team: [cyan]empathy meta-workflow run {team_template['id']}[/cyan]")

    cost_min = team_template['estimated_cost_range']['min']
    cost_max = team_template['estimated_cost_range']['max']
    console.print(f"\n[dim]Estimated cost: ${cost_min:.2f} - ${cost_max:.2f} per execution[/dim]\n")


if __name__ == "__main__":
    meta_workflow_app()
