"""Command-Line Interface for Empathy Framework

Provides CLI commands for:
- Running interactive REPL (empathy run)
- Inspecting patterns, metrics, state (empathy inspect)
- Exporting/importing patterns (empathy export/import)
- Interactive setup wizard (empathy wizard)
- Configuration management
- Power user workflows: morning, ship, fix-all, learn (v2.4+)

Copyright 2025 Smart-AI-Memory
Licensed under Fair Source License 0.9
"""

import argparse
import heapq
import sys
import time
from importlib.metadata import version as get_version
from pathlib import Path

from empathy_os import EmpathyConfig, EmpathyOS, load_config
from empathy_os.config import _validate_file_path
from empathy_os.cost_tracker import cmd_costs
from empathy_os.dashboard import cmd_dashboard
from empathy_os.discovery import show_tip_if_available
from empathy_os.logging_config import get_logger
from empathy_os.pattern_library import PatternLibrary
from empathy_os.persistence import MetricsCollector, PatternPersistence, StateManager
from empathy_os.platform_utils import setup_asyncio_policy
from empathy_os.templates import cmd_new
from empathy_os.wizard_factory_cli import add_wizard_factory_commands
from empathy_os.workflows import (
    cmd_fix_all,
    cmd_learn,
    cmd_morning,
    cmd_ship,
    create_example_config,
    get_workflow,
)
from empathy_os.workflows import list_workflows as get_workflow_list

# Import telemetry CLI commands
try:
    from empathy_os.telemetry.cli import (
        cmd_agent_performance,
        cmd_task_routing_report,
        cmd_telemetry_compare,
        cmd_telemetry_export,
        cmd_telemetry_reset,
        cmd_telemetry_savings,
        cmd_telemetry_show,
        cmd_test_status,
        cmd_tier1_status,
    )

    TELEMETRY_CLI_AVAILABLE = True
except ImportError:
    TELEMETRY_CLI_AVAILABLE = False

# Import progressive workflow CLI commands
try:
    from empathy_os.workflows.progressive.cli import (
        cmd_analytics,
        cmd_cleanup,
        cmd_list_results,
        cmd_show_report,
    )

    PROGRESSIVE_CLI_AVAILABLE = True
except ImportError:
    PROGRESSIVE_CLI_AVAILABLE = False

logger = get_logger(__name__)


# =============================================================================
# =============================================================================
# CHEATSHEET DATA - Quick reference for all commands
# =============================================================================

CHEATSHEET = {
    "Getting Started": [
        ("empathy init", "Create a new config file"),
        ("empathy wizard", "Interactive setup wizard"),
        ("empathy run", "Interactive REPL mode"),
    ],
    "Daily Workflow": [
        ("empathy morning", "Start-of-day briefing"),
        ("empathy status", "What needs attention now"),
        ("empathy ship", "Pre-commit validation"),
    ],
    "Code Quality": [
        ("empathy health", "Quick health check"),
        ("empathy health --deep", "Comprehensive check"),
        ("empathy health --fix", "Auto-fix issues"),
        ("empathy fix-all", "Fix all lint/format issues"),
    ],
    "Pattern Learning": [
        ("empathy learn --analyze 20", "Learn from last 20 commits"),
        ("empathy sync-claude", "Sync patterns to Claude Code"),
        ("empathy inspect patterns", "View learned patterns"),
    ],
    "Code Review": [
        ("empathy review", "Review recent changes"),
        ("empathy review --staged", "Review staged changes only"),
    ],
    "Memory & State": [
        ("empathy inspect state", "View saved states"),
        ("empathy inspect metrics --user-id X", "View user metrics"),
        ("empathy export patterns.json", "Export patterns"),
    ],
    "Advanced": [
        ("empathy costs", "View API cost tracking"),
        ("empathy dashboard", "Launch visual dashboard"),
        ("empathy frameworks", "List agent frameworks"),
        ("empathy workflow list", "List multi-model workflows"),
        ("empathy new <template>", "Create project from template"),
    ],
}

EXPLAIN_CONTENT = {
    "morning": """
HOW 'empathy morning' WORKS:
━━━━━━━━━━━━━━━━━━━━━━━━━━━
This command aggregates multiple data sources to give you a prioritized
start-of-day briefing:

1. PATTERNS ANALYSIS
   Reads ./patterns/*.json to find:
   - Unresolved bugs (status: investigating)
   - Recent security decisions
   - Tech debt trends

2. GIT CONTEXT
   Checks your recent git activity:
   - Commits from yesterday
   - Uncommitted changes
   - Branch status

3. HEALTH SNAPSHOT
   Runs quick health checks:
   - Lint issues count
   - Type errors
   - Test status

4. PRIORITY SCORING
   Items are scored and sorted by:
   - Age (older = higher priority)
   - Severity (critical > high > medium)
   - Your recent activity patterns

TIPS:
• Run this first thing each day
• Use 'empathy morning --verbose' for details
• Pair with 'empathy status --select N' to dive deeper
""",
    "ship": """
HOW 'empathy ship' WORKS:
━━━━━━━━━━━━━━━━━━━━━━━━━
Pre-commit validation pipeline that ensures code quality before shipping:

1. HEALTH CHECKS
   - Runs lint checks (ruff/flake8)
   - Validates types (mypy/pyright)
   - Checks formatting (black/prettier)

2. PATTERN REVIEW
   - Compares changes against known bug patterns
   - Flags code that matches historical issues
   - Suggests fixes based on past resolutions

3. SECURITY SCAN
   - Checks for hardcoded secrets
   - Validates against security patterns
   - Reports potential vulnerabilities

4. PATTERN SYNC (optional)
   - Updates Claude Code rules
   - Syncs new patterns discovered
   - Skip with --skip-sync

EXIT CODES:
• 0 = All checks passed, safe to commit
• 1 = Issues found, review before committing

TIPS:
• Add to pre-commit hook: empathy ship --skip-sync
• Use 'empathy ship --verbose' to see all checks
""",
    "learn": """
HOW 'empathy learn' WORKS:
━━━━━━━━━━━━━━━━━━━━━━━━━
Extracts patterns from your git history to teach Claude about your codebase:

1. COMMIT ANALYSIS
   Parses commit messages looking for:
   - fix: Bug fixes → debugging.json
   - security: decisions → security.json
   - TODO/FIXME in code → tech_debt.json

2. DIFF INSPECTION
   Analyzes code changes to:
   - Identify affected files
   - Extract error types
   - Record fix patterns

3. PATTERN STORAGE
   Saves to ./patterns/:
   - debugging.json: Bug patterns
   - security.json: Security decisions
   - tech_debt.json: Technical debt
   - inspection.json: Code review findings

4. SUMMARY GENERATION
   Creates .claude/patterns_summary.md:
   - Human-readable pattern overview
   - Loaded by Claude Code automatically

USAGE EXAMPLES:
• empathy learn --analyze 10    # Last 10 commits
• empathy learn --analyze 100   # Deeper history
• empathy sync-claude           # Apply patterns to Claude

TIPS:
• Run weekly to keep patterns current
• Use good commit messages (fix:, feat:, etc.)
• Check ./patterns/ to see what was learned
""",
    "health": """
HOW 'empathy health' WORKS:
━━━━━━━━━━━━━━━━━━━━━━━━━
Code health dashboard that runs multiple quality checks:

1. QUICK MODE (default)
   Fast checks that run in seconds:
   - Lint: ruff check or flake8
   - Format: black --check or prettier
   - Basic type checking

2. DEEP MODE (--deep)
   Comprehensive checks (slower):
   - Full type analysis (mypy --strict)
   - Test suite execution
   - Security scanning
   - Dependency audit

3. SCORING
   Health score 0-100 based on:
   - Lint issues (×2 penalty each)
   - Type errors (×5 penalty each)
   - Test failures (×10 penalty each)
   - Security issues (×20 penalty each)

4. AUTO-FIX (--fix)
   Can automatically fix:
   - Formatting issues
   - Import sorting
   - Simple lint errors

USAGE:
• empathy health              # Quick check
• empathy health --deep       # Full check
• empathy health --fix        # Auto-fix issues
• empathy health --trends 30  # 30-day trend

TIPS:
• Run quick checks before commits
• Run deep checks in CI/CD
• Track trends to catch regressions
""",
    "sync-claude": """
HOW 'empathy sync-claude' WORKS:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Converts learned patterns into Claude Code rules:

1. READS PATTERNS
   Loads from ./patterns/:
   - debugging.json → Bug fix patterns
   - security.json → Security decisions
   - tech_debt.json → Known debt items

2. GENERATES RULES
   Creates .claude/rules/empathy/:
   - debugging.md
   - security.md
   - tech_debt.md

3. CLAUDE CODE INTEGRATION
   Rules are automatically loaded when:
   - Claude Code starts in this directory
   - Combined with CLAUDE.md instructions

HOW CLAUDE USES THESE:
• Sees historical bugs before suggesting code
• Knows about accepted security patterns
• Understands existing tech debt

FILE STRUCTURE:
./patterns/             # Your pattern storage
  debugging.json
  security.json
.claude/
  CLAUDE.md             # Project instructions
  rules/
    empathy/            # Generated rules
      debugging.md
      security.md

TIPS:
• Run after 'empathy learn'
• Commit .claude/rules/ to share with team
• Weekly sync keeps Claude current
""",
}


def cmd_version(args):
    """Display version information for Empathy Framework.

    Args:
        args: Namespace object from argparse (no additional attributes used).

    Returns:
        None: Prints version, copyright, and license information to stdout.
    """
    logger.info("Displaying version information")
    try:
        version = get_version("empathy")
    except Exception as e:
        # Package metadata not available or invalid (development install)
        logger.debug(f"Version not available: {e}")
        version = "unknown"
    logger.info(f"Empathy v{version}")
    logger.info("Copyright 2025 Smart-AI-Memory")
    logger.info("Licensed under Fair Source License 0.9")
    logger.info("\n✨ Built with Claude Code + MemDocs + VS Code transformative stack")


def cmd_cheatsheet(args):
    """Display quick reference cheatsheet for all commands.

    Args:
        args: Namespace object from argparse with attributes:
            - category (str | None): Specific category to show (e.g., 'daily-workflow').
            - compact (bool): If True, show commands only without descriptions.

    Returns:
        None: Prints formatted cheatsheet to stdout.
    """
    category = getattr(args, "category", None)
    compact = getattr(args, "compact", False)

    print()
    print("=" * 60)
    print("  EMPATHY FRAMEWORK - QUICK REFERENCE")
    print("=" * 60)

    if category:
        # Show specific category
        category_title = category.replace("-", " ").title()
        if category_title in CHEATSHEET:
            print(f"\n  {category_title}")
            print("  " + "-" * 40)
            for cmd, desc in CHEATSHEET[category_title]:
                if compact:
                    print(f"  {cmd}")
                else:
                    print(f"  {cmd:35} {desc}")
        else:
            print(f"\n  Unknown category: {category}")
            print("  Available: " + ", ".join(k.lower().replace(" ", "-") for k in CHEATSHEET))
    else:
        # Show all categories
        for cat_name, commands in CHEATSHEET.items():
            print(f"\n  {cat_name}")
            print("  " + "-" * 40)
            for cmd, desc in commands:
                if compact:
                    print(f"  {cmd}")
                else:
                    print(f"  {cmd:35} {desc}")

    print()
    print("-" * 60)
    print("  Use: empathy <command> --explain  for detailed explanation")
    print("  Use: empathy onboard              for interactive tutorial")
    print("=" * 60)
    print()


def cmd_onboard(args):
    """Interactive onboarding tutorial for new users.

    Guides users through setup steps: init, learn, sync-claude, health check.

    Args:
        args: Namespace object from argparse with attributes:
            - step (int | None): Jump to specific tutorial step (1-5).
            - reset (bool): If True, reset onboarding progress.

    Returns:
        None: Prints tutorial content and tracks progress.
    """
    from empathy_os.discovery import get_engine

    step = getattr(args, "step", None)
    reset = getattr(args, "reset", False)

    engine = get_engine()
    stats = engine.get_stats()

    if reset:
        # Reset onboarding progress
        engine.state["onboarding_step"] = 0
        engine.state["onboarding_completed"] = []
        engine._save()
        print("Onboarding progress reset.")
        return

    # Define onboarding steps
    steps = [
        {
            "title": "Welcome to Empathy Framework",
            "content": """
Welcome! Empathy Framework helps you build AI systems with 5 levels
of sophistication, from reactive responses to anticipatory assistance.

This tutorial will walk you through the key features.

Let's check your current setup first...
""",
            "check": lambda: True,
            "action": None,
        },
        {
            "title": "Step 1: Initialize Your Project",
            "content": """
First, let's create a configuration file for your project.

Run: empathy init

This creates empathy.config.yaml with sensible defaults.
Alternatively, use 'empathy wizard' for an interactive setup.
""",
            "check": lambda: _file_exists("empathy.config.yaml")
            or _file_exists("empathy.config.yml"),
            "action": "empathy init",
        },
        {
            "title": "Step 2: Learn From Your History",
            "content": """
Empathy can learn patterns from your git commit history.
This teaches Claude about your codebase's patterns and past bugs.

Run: empathy learn --analyze 10

This analyzes the last 10 commits and extracts:
- Bug fix patterns
- Security decisions
- Technical debt markers
""",
            "check": lambda: _file_exists("patterns/debugging.json"),
            "action": "empathy learn --analyze 10",
        },
        {
            "title": "Step 3: Sync Patterns to Claude",
            "content": """
Now let's share what we learned with Claude Code.

Run: empathy sync-claude

This creates .claude/rules/empathy/ with markdown rules
that Claude Code automatically loads when you work in this directory.
""",
            "check": lambda: _file_exists(".claude/rules/empathy/debugging.md"),
            "action": "empathy sync-claude",
        },
        {
            "title": "Step 4: Check Code Health",
            "content": """
Let's run a quick health check on your codebase.

Run: empathy health

This checks:
- Linting issues
- Type errors
- Formatting problems

Try 'empathy health --fix' to auto-fix what's possible.
""",
            "check": lambda: stats.get("command_counts", {}).get("health", 0) > 0,
            "action": "empathy health",
        },
        {
            "title": "Step 5: Daily Workflow",
            "content": """
You're almost there! Here's your recommended daily workflow:

MORNING:
  empathy morning     - Get your priority briefing

BEFORE COMMITS:
  empathy ship        - Validate before committing

WEEKLY:
  empathy learn       - Update patterns from new commits
  empathy sync-claude - Keep Claude current

You've completed the basics! Run 'empathy cheatsheet' anytime
for a quick reference of all commands.
""",
            "check": lambda: True,
            "action": None,
        },
    ]

    # Determine current step
    current_step = engine.state.get("onboarding_step", 0)
    if step is not None:
        current_step = max(0, min(step - 1, len(steps) - 1))

    step_data = steps[current_step]

    # Display header
    print()
    print("=" * 60)
    print(f"  ONBOARDING ({current_step + 1}/{len(steps)})")
    print("=" * 60)
    print()
    print(f"  {step_data['title']}")
    print("  " + "-" * 50)
    print(step_data["content"])

    # Check if step is completed
    if step_data["check"]():
        if current_step < len(steps) - 1:
            print("  [DONE] This step is complete!")
            print()
            print(f"  Continue with: empathy onboard --step {current_step + 2}")
            # Auto-advance
            engine.state["onboarding_step"] = current_step + 1
            engine._save()
        else:
            print("  Congratulations! You've completed the onboarding!")
            print()
            _show_achievements(engine)
    elif step_data["action"]:
        print(f"  NEXT: Run '{step_data['action']}'")
        print("        Then run 'empathy onboard' to continue")

    print()
    print("-" * 60)
    print(f"  Progress: {'*' * (current_step + 1)}{'.' * (len(steps) - current_step - 1)}")
    print("=" * 60)
    print()


def _file_exists(path: str) -> bool:
    """Check if a file exists."""

    return Path(path).exists()


def _show_achievements(engine) -> None:
    """Show user achievements based on usage."""
    stats = engine.get_stats()

    achievements = []
    total_cmds = stats.get("total_commands", 0)
    cmd_counts = stats.get("command_counts", {})

    # Check achievements
    if total_cmds >= 1:
        achievements.append(("First Steps", "Ran your first command"))
    if total_cmds >= 10:
        achievements.append(("Getting Started", "Ran 10+ commands"))
    if total_cmds >= 50:
        achievements.append(("Power User", "Ran 50+ commands"))
    if total_cmds >= 100:
        achievements.append(("Expert", "Ran 100+ commands"))

    if cmd_counts.get("learn", 0) >= 1:
        achievements.append(("Pattern Learner", "Learned from git history"))
    if cmd_counts.get("sync-claude", 0) >= 1:
        achievements.append(("Claude Whisperer", "Synced patterns to Claude"))
    if cmd_counts.get("morning", 0) >= 5:
        achievements.append(("Early Bird", "Used morning briefing 5+ times"))
    if cmd_counts.get("ship", 0) >= 10:
        achievements.append(("Quality Shipper", "Used pre-commit checks 10+ times"))
    if cmd_counts.get("health", 0) >= 1 and cmd_counts.get("fix-all", 0) >= 1:
        achievements.append(("Code Doctor", "Used health checks and fixes"))

    if stats.get("patterns_learned", 0) >= 10:
        achievements.append(("Pattern Master", "Learned 10+ patterns"))

    if stats.get("days_active", 0) >= 7:
        achievements.append(("Week Warrior", "Active for 7+ days"))
    if stats.get("days_active", 0) >= 30:
        achievements.append(("Monthly Maven", "Active for 30+ days"))

    if achievements:
        print("  ACHIEVEMENTS UNLOCKED")
        print("  " + "-" * 30)
        for name, desc in achievements:
            print(f"  * {name}: {desc}")
        print()


def cmd_explain(args):
    """Show detailed explanation for a command.

    Provides in-depth documentation about how specific commands work.

    Args:
        args: Namespace object from argparse with attributes:
            - command (str): Command name to explain (e.g., 'morning', 'ship').

    Returns:
        None: Prints detailed explanation to stdout.
    """
    command = args.command

    if command in EXPLAIN_CONTENT:
        print(EXPLAIN_CONTENT[command])
    else:
        available = ", ".join(EXPLAIN_CONTENT.keys())
        print(f"\nNo detailed explanation available for '{command}'")
        print(f"Available: {available}")
        print("\nTry: empathy cheatsheet  for a quick reference")
        print()


def cmd_achievements(args):
    """Show user achievements and progress.

    Displays gamification stats including unlocked achievements and usage streaks.

    Args:
        args: Namespace object from argparse (no additional attributes used).

    Returns:
        None: Prints achievements and progress to stdout.
    """
    from empathy_os.discovery import get_engine

    engine = get_engine()
    stats = engine.get_stats()

    print()
    print("=" * 60)
    print("  YOUR EMPATHY FRAMEWORK JOURNEY")
    print("=" * 60)
    print()

    # Stats summary
    print("  STATISTICS")
    print("  " + "-" * 40)
    print(f"  Total commands run:    {stats.get('total_commands', 0)}")
    print(f"  Days active:           {stats.get('days_active', 0)}")
    print(f"  Patterns learned:      {stats.get('patterns_learned', 0)}")
    shown = stats.get("tips_shown", 0)
    total = shown + stats.get("tips_remaining", 0)
    print(f"  Tips discovered:       {shown}/{total}")
    print()

    # Command breakdown
    cmd_counts = stats.get("command_counts", {})
    if cmd_counts:
        print("  COMMAND USAGE")
        print("  " + "-" * 40)
        sorted_cmds = sorted(cmd_counts.items(), key=lambda x: x[1], reverse=True)
        for cmd, count in sorted_cmds[:10]:
            bar = "*" * min(count, 20)
            print(f"  {cmd:15} {count:4} {bar}")
        print()

    # Achievements
    _show_achievements(engine)

    print("=" * 60)
    print()


def cmd_tier_recommend(args):
    """Get intelligent tier recommendation for a bug/task.

    Analyzes bug description and historical patterns to recommend
    the most cost-effective tier (HAIKU/SONNET/OPUS).

    Args:
        args: Namespace object from argparse with attributes:
            - description (str): Bug or task description to analyze.
            - files (str | None): Comma-separated list of affected files.
            - complexity (str | None): Complexity hint (low/medium/high).

    Returns:
        None: Prints tier recommendation with confidence and expected cost.
    """
    from empathy_os.tier_recommender import TierRecommender

    recommender = TierRecommender()

    # Get recommendation
    result = recommender.recommend(
        bug_description=args.description,
        files_affected=args.files.split(",") if args.files else None,
        complexity_hint=args.complexity,
    )

    # Display results
    print()
    print("=" * 60)
    print("  TIER RECOMMENDATION")
    print("=" * 60)
    print()
    print(f"  Bug/Task: {args.description}")
    print()
    print(f"  📍 Recommended Tier: {result.tier}")
    print(f"  🎯 Confidence: {result.confidence * 100:.1f}%")
    print(f"  💰 Expected Cost: ${result.expected_cost:.3f}")
    print(f"  🔄 Expected Attempts: {result.expected_attempts:.1f}")
    print()
    print("  📊 Reasoning:")
    print(f"     {result.reasoning}")
    print()

    if result.similar_patterns_count > 0:
        print(f"  ✅ Based on {result.similar_patterns_count} similar patterns")
    else:
        print("  ⚠️  No historical data - using conservative default")

    if result.fallback_used:
        print()
        print("  💡 Tip: As more patterns are collected, recommendations")
        print("     will become more accurate and personalized.")

    print()
    print("=" * 60)
    print()


def cmd_tier_stats(args):
    """Show tier pattern learning statistics.

    Displays statistics about collected patterns and tier distribution.

    Args:
        args: Namespace object from argparse (no additional attributes used).

    Returns:
        None: Prints tier statistics, savings percentages, and bug type distribution.
    """
    from empathy_os.tier_recommender import TierRecommender

    recommender = TierRecommender()
    stats = recommender.get_stats()

    print()
    print("=" * 60)
    print("  TIER PATTERN LEARNING STATS")
    print("=" * 60)
    print()

    if stats.get("total_patterns", 0) == 0:
        print("  No patterns collected yet.")
        print()
        print("  💡 Patterns are automatically collected as you use")
        print("     cascading workflows with enhanced tracking enabled.")
        print()
        print("=" * 60)
        print()
        return

    print(f"  Total Patterns: {stats['total_patterns']}")
    print(f"  Avg Savings: {stats['avg_savings_percent']}%")
    print()

    print("  TIER DISTRIBUTION")
    print("  " + "-" * 40)
    for tier, count in stats["patterns_by_tier"].items():
        percent = (count / stats["total_patterns"]) * 100
        bar = "█" * int(percent / 5)
        print(f"  {tier:10} {count:3} ({percent:5.1f}%) {bar}")
    print()

    print("  BUG TYPE DISTRIBUTION")
    print("  " + "-" * 40)
    sorted_types = sorted(stats["bug_type_distribution"].items(), key=lambda x: x[1], reverse=True)
    for bug_type, count in sorted_types[:10]:
        percent = (count / stats["total_patterns"]) * 100
        print(f"  {bug_type:20} {count:3} ({percent:5.1f}%)")

    print()
    print("=" * 60)
    print()


def cmd_orchestrate(args):
    """Run meta-orchestration workflows.

    Orchestrates teams of agents to accomplish complex tasks through
    intelligent composition patterns.

    Args:
        args: Namespace object from argparse with attributes:
            - workflow (str): Orchestration workflow name.
            - path (str): Target path for orchestration.
            - mode (str | None): Execution mode (e.g., 'daily', 'weekly', 'release').
            - json (bool): If True, output as JSON format.
            - dry_run (bool): If True, show plan without executing.
            - verbose (bool): If True, show detailed output.

    Returns:
        int: 0 on success, 1 on failure.
    """
    import asyncio
    import json

    from empathy_os.workflows.orchestrated_health_check import OrchestratedHealthCheckWorkflow
    from empathy_os.workflows.orchestrated_release_prep import OrchestratedReleasePrepWorkflow
    # test_coverage_boost removed - feature disabled in v4.0.0 (being redesigned)

    # Get workflow type
    workflow_type = args.workflow

    # Only print header in non-JSON mode
    if not (hasattr(args, "json") and args.json):
        print()
        print("=" * 60)
        print(f"  META-ORCHESTRATION: {workflow_type.upper()}")
        print("=" * 60)
        print()

    if workflow_type == "release-prep":
        # Release Preparation workflow
        path = args.path or "."
        quality_gates = {}

        # Collect custom quality gates
        if hasattr(args, "min_coverage") and args.min_coverage is not None:
            quality_gates["min_coverage"] = args.min_coverage
        if hasattr(args, "min_quality") and args.min_quality is not None:
            quality_gates["min_quality_score"] = args.min_quality
        if hasattr(args, "max_critical") and args.max_critical is not None:
            quality_gates["max_critical_issues"] = args.max_critical

        # Only print details in non-JSON mode
        if not (hasattr(args, "json") and args.json):
            print(f"  Project Path: {path}")
            if quality_gates:
                print(f"  Quality Gates: {quality_gates}")
            print()
            print("  🔍 Parallel Validation Agents:")
            print("    • Security Auditor (vulnerability scan)")
            print("    • Test Coverage Analyzer (gap analysis)")
            print("    • Code Quality Reviewer (best practices)")
            print("    • Documentation Writer (completeness)")
            print()

        # Create workflow
        workflow = OrchestratedReleasePrepWorkflow(
            quality_gates=quality_gates if quality_gates else None
        )

        try:
            # Execute workflow
            report = asyncio.run(workflow.execute(path=path))

            # Display results
            if hasattr(args, "json") and args.json:
                print(json.dumps(report.to_dict(), indent=2))
            else:
                print(report.format_console_output())

            # Return appropriate exit code
            return 0 if report.approved else 1

        except Exception as e:
            print(f"  ❌ Error executing release prep workflow: {e}")
            print()
            logger.exception("Release prep workflow failed")
            return 1

    elif workflow_type == "test-coverage":
        # Test Coverage Boost workflow - DISABLED in v4.0.0
        print("  ⚠️  FEATURE DISABLED")
        print("  " + "-" * 56)
        print()
        print("  The test-coverage workflow has been disabled in v4.0.0")
        print("  due to poor quality (0% test pass rate).")
        print()
        print("  This feature is being redesigned and will return in a")
        print("  future release with improved test generation quality.")
        print()
        print("  Available v4.0 workflows:")
        print("    • health-check - Real-time codebase health analysis")
        print("    • release-prep - Quality gate validation")
        print()
        return 1

    elif workflow_type == "health-check":
        # Health Check workflow
        mode = args.mode or "daily"
        project_root = args.project_root or "."
        focus_area = getattr(args, "focus", None)

        # Only print details in non-JSON mode
        if not (hasattr(args, "json") and args.json):
            print(f"  Mode: {mode.upper()}")
            print(f"  Project Root: {project_root}")
            if focus_area:
                print(f"  Focus Area: {focus_area}")
            print()

            # Show agents for mode
            mode_agents = {
                "daily": ["Security", "Coverage", "Quality"],
                "weekly": ["Security", "Coverage", "Quality", "Performance", "Documentation"],
                "release": [
                    "Security",
                    "Coverage",
                    "Quality",
                    "Performance",
                    "Documentation",
                    "Architecture",
                ],
            }

            print(f"  🔍 {mode.capitalize()} Check Agents:")
            for agent in mode_agents.get(mode, []):
                print(f"    • {agent}")
            print()

        # Create workflow
        workflow = OrchestratedHealthCheckWorkflow(mode=mode, project_root=project_root)

        try:
            # Execute workflow
            report = asyncio.run(workflow.execute())

            # Display results
            if hasattr(args, "json") and args.json:
                print(json.dumps(report.to_dict(), indent=2))
            else:
                print(report.format_console_output())

            # Return appropriate exit code (70+ is passing)
            return 0 if report.overall_health_score >= 70 else 1

        except Exception as e:
            print(f"  ❌ Error executing health check workflow: {e}")
            print()
            logger.exception("Health check workflow failed")
            return 1

    else:
        print(f"  ❌ Unknown workflow type: {workflow_type}")
        print()
        print("  Available workflows:")
        print("    - release-prep: Release readiness validation (parallel agents)")
        print("    - health-check: Project health assessment (daily/weekly/release modes)")
        print()
        print("  Note: test-coverage workflow disabled in v4.0.0 (being redesigned)")
        print()
        return 1

    print()
    print("=" * 60)
    print()

    return 0


def cmd_init(args):
    """Initialize a new Empathy Framework project.

    Creates a configuration file with sensible defaults.

    Args:
        args: Namespace object from argparse with attributes:
            - format (str): Output format ('yaml' or 'json').
            - output (str | None): Output file path.

    Returns:
        None: Creates configuration file at specified path.

    Raises:
        ValueError: If output path is invalid or unsafe.
    """
    config_format = args.format
    output_path = args.output or f"empathy.config.{config_format}"

    # Validate output path to prevent path traversal attacks
    validated_path = _validate_file_path(output_path)

    logger.info(f"Initializing new Empathy Framework project with format: {config_format}")

    # Create default config
    config = EmpathyConfig()

    # Save to file
    if config_format == "yaml":
        config.to_yaml(str(validated_path))
        logger.info(f"Created YAML configuration file: {output_path}")
        logger.info(f"✓ Created YAML configuration: {output_path}")
    elif config_format == "json":
        config.to_json(str(validated_path))
        logger.info(f"Created JSON configuration file: {validated_path}")
        logger.info(f"✓ Created JSON configuration: {validated_path}")

    logger.info("\nNext steps:")
    logger.info(f"  1. Edit {output_path} to customize settings")
    logger.info("  2. Use 'empathy run' to start using the framework")


def cmd_validate(args):
    """Validate a configuration file.

    Loads and validates the specified configuration file.

    Args:
        args: Namespace object from argparse with attributes:
            - config (str): Path to configuration file to validate.

    Returns:
        None: Prints validation result. Exits with code 1 on failure.
    """
    filepath = args.config
    logger.info(f"Validating configuration file: {filepath}")

    try:
        config = load_config(filepath=filepath, use_env=False)
        config.validate()
        logger.info(f"Configuration validation successful: {filepath}")
        logger.info(f"✓ Configuration valid: {filepath}")
        logger.info(f"\n  User ID: {config.user_id}")
        logger.info(f"  Target Level: {config.target_level}")
        logger.info(f"  Confidence Threshold: {config.confidence_threshold}")
        logger.info(f"  Persistence Backend: {config.persistence_backend}")
        logger.info(f"  Metrics Enabled: {config.metrics_enabled}")
    except (OSError, FileNotFoundError) as e:
        # Config file not found or cannot be read
        logger.error(f"Configuration file error: {e}")
        logger.error(f"✗ Cannot read configuration file: {e}")
        sys.exit(1)
    except ValueError as e:
        # Invalid configuration values
        logger.error(f"Configuration validation failed: {e}")
        logger.error(f"✗ Configuration invalid: {e}")
        sys.exit(1)
    except Exception as e:
        # Unexpected errors during config validation
        logger.exception(f"Unexpected error validating configuration: {e}")
        logger.error(f"✗ Configuration invalid: {e}")
        sys.exit(1)


def cmd_info(args):
    """Display information about the framework.

    Shows configuration, persistence, and feature status.

    Args:
        args: Namespace object from argparse with attributes:
            - config (str | None): Optional path to configuration file.

    Returns:
        None: Prints framework information to stdout.
    """
    config_file = args.config
    logger.info("Displaying framework information")

    if config_file:
        logger.debug(f"Loading config from file: {config_file}")
        config = load_config(filepath=config_file)
    else:
        logger.debug("Loading default configuration")
        config = load_config()

    logger.info("=== Empathy Framework Info ===\n")
    logger.info("Configuration:")
    logger.info(f"  User ID: {config.user_id}")
    logger.info(f"  Target Level: {config.target_level}")
    logger.info(f"  Confidence Threshold: {config.confidence_threshold}")
    logger.info("\nPersistence:")
    logger.info(f"  Backend: {config.persistence_backend}")
    logger.info(f"  Path: {config.persistence_path}")
    logger.info(f"  Enabled: {config.persistence_enabled}")
    logger.info("\nMetrics:")
    logger.info(f"  Enabled: {config.metrics_enabled}")
    logger.info(f"  Path: {config.metrics_path}")
    logger.info("\nPattern Library:")
    logger.info(f"  Enabled: {config.pattern_library_enabled}")
    logger.info(f"  Pattern Sharing: {config.pattern_sharing}")
    logger.info(f"  Confidence Threshold: {config.pattern_confidence_threshold}")


def cmd_patterns_list(args):
    """List patterns in a pattern library.

    Args:
        args: Namespace object from argparse with attributes:
            - library (str): Path to pattern library file.
            - format (str): Library format ('json' or 'sqlite').

    Returns:
        None: Prints pattern list to stdout. Exits with code 1 on failure.
    """
    filepath = args.library
    format_type = args.format
    logger.info(f"Listing patterns from library: {filepath} (format: {format_type})")

    try:
        if format_type == "json":
            library = PatternPersistence.load_from_json(filepath)
        elif format_type == "sqlite":
            library = PatternPersistence.load_from_sqlite(filepath)
        else:
            logger.error(f"Unknown pattern library format: {format_type}")
            logger.error(f"✗ Unknown format: {format_type}")
            sys.exit(1)

        logger.info(f"Loaded {len(library.patterns)} patterns from {filepath}")
        logger.info(f"=== Pattern Library: {filepath} ===\n")
        logger.info(f"Total patterns: {len(library.patterns)}")
        logger.info(f"Total agents: {len(library.agent_contributions)}")

        if library.patterns:
            logger.info("\nPatterns:")
            for pattern_id, pattern in library.patterns.items():
                logger.info(f"\n  [{pattern_id}] {pattern.name}")
                logger.info(f"    Agent: {pattern.agent_id}")
                logger.info(f"    Type: {pattern.pattern_type}")
                logger.info(f"    Confidence: {pattern.confidence:.2f}")
                logger.info(f"    Usage: {pattern.usage_count}")
                logger.info(f"    Success Rate: {pattern.success_rate:.2f}")
    except FileNotFoundError:
        logger.error(f"Pattern library not found: {filepath}")
        logger.error(f"✗ Pattern library not found: {filepath}")
        sys.exit(1)


def cmd_patterns_export(args):
    """Export patterns from one format to another.

    Args:
        args: Namespace object from argparse with attributes:
            - input (str): Input file path.
            - output (str): Output file path.
            - input_format (str): Input format ('json' or 'sqlite').
            - output_format (str): Output format ('json' or 'sqlite').

    Returns:
        None: Exports patterns to output file. Exits with code 1 on failure.

    Raises:
        ValueError: If output path is invalid or unsafe.
    """
    input_file = args.input
    input_format = args.input_format
    output_file = args.output
    output_format = args.output_format

    logger.info(f"Exporting patterns from {input_format} to {output_format}")

    # Load from input format
    try:
        if input_format == "json":
            library = PatternPersistence.load_from_json(input_file)
        elif input_format == "sqlite":
            library = PatternPersistence.load_from_sqlite(input_file)
        else:
            logger.error(f"Unknown input format: {input_format}")
            logger.error(f"✗ Unknown input format: {input_format}")
            sys.exit(1)

        logger.info(f"Loaded {len(library.patterns)} patterns from {input_file}")
        logger.info(f"✓ Loaded {len(library.patterns)} patterns from {input_file}")
    except (OSError, FileNotFoundError) as e:
        # Input file not found or cannot be read
        logger.error(f"Pattern file error: {e}")
        logger.error(f"✗ Cannot read pattern file: {e}")
        sys.exit(1)
    except (ValueError, KeyError) as e:
        # Invalid pattern data format
        logger.error(f"Pattern data error: {e}")
        logger.error(f"✗ Invalid pattern data: {e}")
        sys.exit(1)
    except Exception as e:
        # Unexpected errors loading patterns
        logger.exception(f"Unexpected error loading patterns: {e}")
        logger.error(f"✗ Failed to load patterns: {e}")
        sys.exit(1)

    # Validate output path
    validated_output = _validate_file_path(output_file)

    # Save to output format
    try:
        if output_format == "json":
            PatternPersistence.save_to_json(library, str(validated_output))
        elif output_format == "sqlite":
            PatternPersistence.save_to_sqlite(library, str(validated_output))

        logger.info(f"Saved {len(library.patterns)} patterns to {output_file}")
        logger.info(f"✓ Saved {len(library.patterns)} patterns to {output_file}")
    except (OSError, FileNotFoundError, PermissionError) as e:
        # Cannot write output file
        logger.error(f"Pattern file write error: {e}")
        logger.error(f"✗ Cannot write pattern file: {e}")
        sys.exit(1)
    except Exception as e:
        # Unexpected errors saving patterns
        logger.exception(f"Unexpected error saving patterns: {e}")
        logger.error(f"✗ Failed to save patterns: {e}")
        sys.exit(1)


def cmd_patterns_resolve(args):
    """Resolve investigating bug patterns with root cause and fix.

    Updates pattern status and adds resolution information.

    Args:
        args: Namespace object from argparse with attributes:
            - pattern_id (str | None): Pattern ID to resolve.
            - root_cause (str | None): Root cause description.
            - fix (str | None): Fix description.
            - fix_code (str | None): Code snippet of the fix.
            - time (int | None): Resolution time in minutes.
            - status (str): New status ('resolved', 'wont_fix', etc.).
            - patterns_dir (str): Patterns directory path.
            - commit (str | None): Related commit hash.

    Returns:
        None: Updates pattern and prints result. Exits with code 1 on failure.
    """
    from empathy_llm_toolkit.pattern_resolver import PatternResolver

    resolver = PatternResolver(args.patterns_dir)

    # If no bug_id, list investigating bugs
    if not args.bug_id:
        investigating = resolver.list_investigating()
        if not investigating:
            print("No bugs with 'investigating' status found.")
            return

        print(f"\nBugs needing resolution ({len(investigating)}):\n")
        for bug in investigating:
            print(f"  {bug.get('bug_id', 'unknown')}")
            print(f"    Type: {bug.get('error_type', 'unknown')}")
            print(f"    File: {bug.get('file_path', 'unknown')}")
            msg = bug.get("error_message", "N/A")
            print(f"    Message: {msg[:60]}..." if len(msg) > 60 else f"    Message: {msg}")
            print()
        return

    # Validate required args
    if not args.root_cause or not args.fix:
        print("✗ --root-cause and --fix are required when resolving a bug")
        print(
            "  Example: empathy patterns resolve bug_123 --root-cause 'Null check' --fix 'Added ?.'",
        )
        sys.exit(1)

    # Resolve the specified bug
    success = resolver.resolve_bug(
        bug_id=args.bug_id,
        root_cause=args.root_cause,
        fix_applied=args.fix,
        fix_code=args.fix_code,
        resolution_time_minutes=args.time or 0,
        resolved_by=args.resolved_by or "@developer",
    )

    if success:
        print(f"✓ Resolved: {args.bug_id}")

        # Regenerate summary if requested
        if not args.no_regenerate:
            if resolver.regenerate_summary():
                print("✓ Regenerated patterns_summary.md")
            else:
                print("⚠ Failed to regenerate summary")
    else:
        print(f"✗ Failed to resolve: {args.bug_id}")
        print("  Use 'empathy patterns resolve' (no args) to list investigating bugs")
        sys.exit(1)


def cmd_status(args):
    """Session status assistant - prioritized project status report.

    Collects and displays project status including patterns, git context,
    and health metrics with priority scoring.

    Args:
        args: Namespace object from argparse with attributes:
            - patterns_dir (str): Path to patterns directory (default: ./patterns).
            - project_root (str): Project root directory (default: .).
            - inactivity (int): Minutes of inactivity before showing status.
            - full (bool): If True, show all items without limit.
            - json (bool): If True, output as JSON format.
            - select (int | None): Select specific item for action prompt.
            - force (bool): If True, show status even with recent activity.

    Returns:
        None: Prints prioritized status report or JSON output.
    """
    from empathy_llm_toolkit.session_status import SessionStatusCollector

    config = {"inactivity_minutes": args.inactivity}
    collector = SessionStatusCollector(
        patterns_dir=args.patterns_dir,
        project_root=args.project_root,
        config=config,
    )

    # Check if should show (unless forced)
    if not args.force and not collector.should_show():
        print("No status update needed (recent activity detected).")
        print("Use --force to show status anyway.")
        return

    # Collect status
    status = collector.collect()

    # Handle selection
    if args.select:
        prompt = collector.get_action_prompt(status, args.select)
        if prompt:
            print(f"\nAction prompt for selection {args.select}:\n")
            print(prompt)
        else:
            print(f"Invalid selection: {args.select}")
        return

    # Output
    if args.json:
        print(collector.format_json(status))
    else:
        max_items = None if args.full else 5
        print()
        print(collector.format_output(status, max_items=max_items))
        print()

    # Record interaction
    collector.record_interaction()


def cmd_review(args):
    """Pattern-based code review against historical bugs.

    Analyzes code changes against learned patterns to identify potential issues.

    Args:
        args: Namespace object from argparse with attributes:
            - files (list[str]): Files to review (default: recent changes).
            - staged (bool): If True, review staged changes only.
            - severity (str): Minimum severity threshold for findings.
            - patterns_dir (str): Path to patterns directory.
            - json (bool): If True, output as JSON format.

    Returns:
        None: Prints review findings and recommendations.
    """
    import asyncio

    from empathy_software_plugin.wizards.code_review_wizard import CodeReviewWizard

    wizard = CodeReviewWizard(patterns_dir=args.patterns_dir)

    # Run the async analysis
    result = asyncio.run(
        wizard.analyze(
            {
                "files": args.files,
                "staged_only": args.staged,
                "severity_threshold": args.severity,
            },
        ),
    )

    # Output results
    if args.json:
        import json

        print(json.dumps(result, indent=2, default=str))
    else:
        print(wizard.format_terminal_output(result))

        # Show recommendations
        recommendations = result.get("recommendations", [])
        if recommendations and result.get("findings"):
            print("\nRecommendations:")
            for rec in recommendations:
                print(f"  • {rec}")


def cmd_health(args):
    """Code health assistant - run health checks and auto-fix issues.

    Runs comprehensive health checks including linting, type checking,
    and formatting with optional auto-fix capability.

    Args:
        args: Namespace object from argparse with attributes:
            - check (str | None): Specific check to run (lint/type/format/test).
            - deep (bool): If True, run comprehensive checks.
            - fix (bool): If True, auto-fix issues where possible.
            - threshold (str): Severity threshold for issues.
            - project_root (str): Project root directory.
            - patterns_dir (str): Path to patterns directory.
            - details (bool): If True, show detailed issue list.
            - compare (str | None): Compare against historical baseline.
            - export (str | None): Export results to file.
            - json (bool): If True, output as JSON format.

    Returns:
        None: Prints health check results and optionally fixes issues.
    """
    import asyncio

    from empathy_llm_toolkit.code_health import (
        AutoFixer,
        CheckCategory,
        HealthCheckRunner,
        HealthTrendTracker,
        format_health_output,
    )

    runner = HealthCheckRunner(
        project_root=args.project_root,
    )

    # Determine what checks to run
    if args.check:
        # Run specific check
        try:
            category = CheckCategory(args.check)
            report_future = runner.run_check(category)
            result = asyncio.run(report_future)
            # Create a minimal report with just this result
            from empathy_llm_toolkit.code_health import HealthReport

            report = HealthReport(project_root=args.project_root)
            report.add_result(result)
        except ValueError:
            print(f"Unknown check category: {args.check}")
            print(f"Available: {', '.join(c.value for c in CheckCategory)}")
            return
    elif args.deep:
        # Run all checks
        print("Running comprehensive health check...\n")
        report = asyncio.run(runner.run_all())
    else:
        # Run quick checks (default)
        report = asyncio.run(runner.run_quick())

    # Handle fix mode
    if args.fix:
        fixer = AutoFixer()

        if args.dry_run:
            # Preview only
            fixes = fixer.preview_fixes(report)
            if fixes:
                print("Would fix the following issues:\n")
                for fix in fixes:
                    safe_indicator = " (safe)" if fix["safe"] else " (needs confirmation)"
                    print(f"  [{fix['category']}] {fix['file']}")
                    print(f"    {fix['issue']}")
                    print(f"    Command: {fix['fix_command']}{safe_indicator}")
                    print()
            else:
                print("No auto-fixable issues found.")
            return

        # Apply fixes
        if args.check:
            try:
                category = CheckCategory(args.check)
                result = asyncio.run(fixer.fix_category(report, category))
            except ValueError:
                result = {"fixed": [], "skipped": [], "failed": []}
        else:
            result = asyncio.run(fixer.fix_all(report, interactive=args.interactive))

        # Report fix results
        if result["fixed"]:
            print(f"✓ Fixed {len(result['fixed'])} issue(s)")
            for fix in result["fixed"][:5]:
                print(f"  - {fix['file_path']}: {fix['message']}")
            if len(result["fixed"]) > 5:
                print(f"  ... and {len(result['fixed']) - 5} more")

        if result["skipped"]:
            if args.interactive:
                print(f"\n⚠ Skipped {len(result['skipped'])} issue(s) (could not auto-fix)")
            else:
                print(
                    f"\n⚠ Skipped {len(result['skipped'])} issue(s) (use --interactive to review)",
                )

        if result["failed"]:
            print(f"\n✗ Failed to fix {len(result['failed'])} issue(s)")

        return

    # Handle trends
    if args.trends:
        tracker = HealthTrendTracker(project_root=args.project_root)
        trends = tracker.get_trends(days=args.trends)

        print(f"📈 Health Trends ({trends['period_days']} days)\n")
        print(f"Average Score: {trends['average_score']}/100")
        print(f"Trend: {trends['trend_direction']} ({trends['score_change']:+d})")

        if trends["data_points"]:
            print("\nRecent scores:")
            for point in trends["data_points"][:7]:
                print(f"  {point['date']}: {point['score']}/100")

        hotspots = tracker.identify_hotspots()
        if hotspots:
            print("\n🔥 Hotspots (files with recurring issues):")
            for spot in hotspots[:5]:
                print(f"  {spot['file']}: {spot['issue_count']} issues")

        return

    # Output report
    if args.json:
        import json

        print(json.dumps(report.to_dict(), indent=2, default=str))
    else:
        level = 3 if args.full else (2 if args.details else 1)
        print(format_health_output(report, level=level))

    # Record to trend history
    if not args.check:  # Only record full runs
        tracker = HealthTrendTracker(project_root=args.project_root)
        tracker.record_check(report)


def cmd_metrics_show(args):
    """Display metrics for a user.

    Args:
        args: Namespace object from argparse with attributes:
            - user (str): User ID to retrieve metrics for.
            - db (str): Path to metrics database (default: ./metrics.db).

    Returns:
        None: Prints user metrics to stdout. Exits with code 1 on failure.
    """
    db_path = args.db
    user_id = args.user

    logger.info(f"Retrieving metrics for user: {user_id} from {db_path}")

    collector = MetricsCollector(db_path)

    try:
        stats = collector.get_user_stats(user_id)

        logger.info(f"Successfully retrieved metrics for user: {user_id}")
        logger.info(f"=== Metrics for User: {user_id} ===\n")
        logger.info(f"Total Operations: {stats['total_operations']}")
        logger.info(f"Success Rate: {stats['success_rate']:.1%}")
        logger.info(f"Average Response Time: {stats.get('avg_response_time_ms', 0):.0f} ms")
        logger.info(f"\nFirst Use: {stats['first_use']}")
        logger.info(f"Last Use: {stats['last_use']}")

        logger.info("\nEmpathy Level Usage:")
        logger.info(f"  Level 1: {stats.get('level_1_count', 0)} uses")
        logger.info(f"  Level 2: {stats.get('level_2_count', 0)} uses")
        logger.info(f"  Level 3: {stats.get('level_3_count', 0)} uses")
        logger.info(f"  Level 4: {stats.get('level_4_count', 0)} uses")
        logger.info(f"  Level 5: {stats.get('level_5_count', 0)} uses")
    except (OSError, FileNotFoundError) as e:
        # Database file not found
        logger.error(f"Metrics database error: {e}")
        logger.error(f"✗ Cannot read metrics database: {e}")
        sys.exit(1)
    except KeyError as e:
        # User not found in database
        logger.error(f"User not found in metrics: {e}")
        logger.error(f"✗ User {user_id} not found: {e}")
        sys.exit(1)
    except Exception as e:
        # Unexpected errors retrieving metrics
        logger.exception(f"Unexpected error retrieving metrics for user {user_id}: {e}")
        logger.error(f"✗ Failed to retrieve metrics: {e}")
        sys.exit(1)


def cmd_state_list(args):
    """List saved user states.

    Args:
        args: Namespace object from argparse with attributes:
            - state_dir (str): Directory containing state files.

    Returns:
        None: Prints list of users with saved states.
    """
    state_dir = args.state_dir

    logger.info(f"Listing saved user states from: {state_dir}")

    manager = StateManager(state_dir)
    users = manager.list_users()

    logger.info(f"Found {len(users)} saved user states")
    logger.info(f"=== Saved User States: {state_dir} ===\n")
    logger.info(f"Total users: {len(users)}")

    if users:
        logger.info("\nUsers:")
        for user_id in users:
            logger.info(f"  - {user_id}")


def cmd_run(args):
    """Interactive REPL for testing empathy interactions.

    Starts an interactive session for testing empathy levels and features.

    Args:
        args: Namespace object from argparse with attributes:
            - config (str | None): Path to configuration file.
            - user_id (str | None): User ID (default: cli_user).
            - level (int): Target empathy level (1-5).

    Returns:
        None: Runs interactive REPL until user exits.
    """
    config_file = args.config
    user_id = args.user_id or "cli_user"
    level = args.level

    print("🧠 Empathy Framework - Interactive Mode")
    print("=" * 50)

    # Load configuration
    if config_file:
        config = load_config(filepath=config_file)
        print(f"✓ Loaded config from: {config_file}")
    else:
        config = EmpathyConfig(user_id=user_id, target_level=level)
        print("✓ Using default configuration")

    print(f"\nUser ID: {config.user_id}")
    print(f"Target Level: {config.target_level}")
    print(f"Confidence Threshold: {config.confidence_threshold:.0%}")

    # Create EmpathyOS instance
    try:
        empathy = EmpathyOS(
            user_id=config.user_id,
            target_level=config.target_level,
            confidence_threshold=config.confidence_threshold,
            persistence_enabled=config.persistence_enabled,
        )
        print("✓ Empathy OS initialized")
    except ValueError as e:
        # Invalid configuration parameters
        print(f"✗ Configuration error: {e}")
        sys.exit(1)
    except (OSError, FileNotFoundError, PermissionError) as e:
        # Cannot access required files/directories
        print(f"✗ File system error: {e}")
        sys.exit(1)
    except Exception as e:
        # Unexpected initialization failure
        logger.exception(f"Unexpected error initializing Empathy OS: {e}")
        print(f"✗ Failed to initialize Empathy OS: {e}")
        sys.exit(1)

    print("\n" + "=" * 50)
    print("Type your input (or 'exit'/'quit' to stop)")
    print("Type 'help' for available commands")
    print("=" * 50 + "\n")

    # Interactive loop
    while True:
        try:
            user_input = input("You: ").strip()

            if not user_input:
                continue

            if user_input.lower() in ["exit", "quit", "q"]:
                print("\n👋 Goodbye!")
                break

            if user_input.lower() == "help":
                print("\nAvailable commands:")
                print("  exit, quit, q - Exit the program")
                print("  help - Show this help message")
                print("  trust - Show current trust level")
                print("  stats - Show session statistics")
                print("  level - Show current empathy level")
                print()
                continue

            if user_input.lower() == "trust":
                trust = empathy.collaboration_state.trust_level
                print(f"\n  Current trust level: {trust:.0%}\n")
                continue

            if user_input.lower() == "level":
                current_level = empathy.collaboration_state.current_level
                print(f"\n  Current empathy level: {current_level}\n")
                continue

            if user_input.lower() == "stats":
                print("\n  Session Statistics:")
                print(f"    Trust: {empathy.collaboration_state.trust_level:.0%}")
                print(f"    Current Level: {empathy.collaboration_state.current_level}")
                print(f"    Target Level: {config.target_level}")
                print()
                continue

            # Process interaction
            start_time = time.time()
            response = empathy.interact(user_id=config.user_id, user_input=user_input, context={})
            duration = (time.time() - start_time) * 1000

            # Display response with level indicator
            level_indicators = ["❌", "🔵", "🟢", "🟡", "🔮"]
            level_indicator = level_indicators[response.level]

            print(f"\nBot {level_indicator} [L{response.level}]: {response.response}")

            # Show predictions if Level 4
            if response.predictions:
                print("\n🔮 Predictions:")
                for pred in response.predictions:
                    print(f"   • {pred}")

            conf = f"{response.confidence:.0%}"
            print(f"\n  Level: {response.level} | Confidence: {conf} | Time: {duration:.0f}ms")
            print()

            # Ask for feedback
            feedback = input("Was this helpful? (y/n/skip): ").strip().lower()
            if feedback == "y":
                empathy.record_success(success=True)
                trust = empathy.collaboration_state.trust_level
                print(f"  ✓ Trust increased to {trust:.0%}\n")
            elif feedback == "n":
                empathy.record_success(success=False)
                trust = empathy.collaboration_state.trust_level
                print(f"  ✗ Trust decreased to {trust:.0%}\n")

        except KeyboardInterrupt:
            print("\n\n👋 Goodbye!")
            break
        except (ValueError, KeyError) as e:
            # Invalid input or response structure
            print(f"\n✗ Input error: {e}\n")
        except Exception as e:
            # Unexpected errors in interactive loop - log and continue
            logger.exception(f"Unexpected error in interactive loop: {e}")
            print(f"\n✗ Error: {e}\n")


def cmd_inspect(args):
    """Unified inspection command for patterns, metrics, and state.

    Inspect various framework data including patterns, user metrics, and states.

    Args:
        args: Namespace object from argparse with attributes:
            - type (str): What to inspect ('patterns', 'metrics', or 'state').
            - user_id (str | None): Filter by user ID.
            - db (str | None): Database path (default: .empathy/patterns.db).
            - state_dir (str | None): State directory for state inspection.

    Returns:
        None: Prints inspection results. Exits with code 1 on failure.
    """
    inspect_type = args.type
    user_id = args.user_id
    db_path = args.db or ".empathy/patterns.db"

    print(f"🔍 Inspecting: {inspect_type}")
    print("=" * 50)

    if inspect_type == "patterns":
        try:
            # Determine file format from extension
            if db_path.endswith(".json"):
                library = PatternPersistence.load_from_json(db_path)
            else:
                library = PatternPersistence.load_from_sqlite(db_path)

            patterns = list(library.patterns.values())

            # Filter by user_id if specified
            if user_id:
                patterns = [p for p in patterns if p.agent_id == user_id]

            print(f"\nPatterns for {'user ' + user_id if user_id else 'all users'}:")
            print(f"  Total patterns: {len(patterns)}")

            if patterns:
                print("\n  Top patterns:")
                # Sort by confidence
                top_patterns = heapq.nlargest(10, patterns, key=lambda p: p.confidence)
                for i, pattern in enumerate(top_patterns, 1):
                    print(f"\n  {i}. {pattern.name}")
                    print(f"     Confidence: {pattern.confidence:.0%}")
                    print(f"     Used: {pattern.usage_count} times")
                    print(f"     Success rate: {pattern.success_rate:.0%}")
        except FileNotFoundError:
            print(f"✗ Pattern library not found: {db_path}")
            print("  Tip: Use 'empathy-framework wizard' to set up your first project")
            sys.exit(1)
        except (ValueError, KeyError) as e:
            # Invalid pattern data format
            print(f"✗ Invalid pattern data: {e}")
            sys.exit(1)
        except Exception as e:
            # Unexpected errors loading patterns
            logger.exception(f"Unexpected error loading patterns: {e}")
            print(f"✗ Failed to load patterns: {e}")
            sys.exit(1)

    elif inspect_type == "metrics":
        if not user_id:
            print("✗ User ID required for metrics inspection")
            print("  Usage: empathy-framework inspect metrics --user-id USER_ID")
            sys.exit(1)

        try:
            collector = MetricsCollector(db_path=db_path)
            stats = collector.get_user_stats(user_id)

            print(f"\nMetrics for user: {user_id}")
            print(f"  Total operations: {stats.get('total_operations', 0)}")
            print(f"  Success rate: {stats.get('success_rate', 0):.0%}")
            print(f"  Average response time: {stats.get('avg_response_time_ms', 0):.0f}ms")
            print("\n  Empathy level usage:")
            for level in range(1, 6):
                count = stats.get(f"level_{level}_count", 0)
                print(f"    Level {level}: {count} times")
        except (OSError, FileNotFoundError) as e:
            # Database file not found
            print(f"✗ Metrics database not found: {e}")
            sys.exit(1)
        except KeyError as e:
            # User not found
            print(f"✗ User {user_id} not found: {e}")
            sys.exit(1)
        except Exception as e:
            # Unexpected errors loading metrics
            logger.exception(f"Unexpected error loading metrics: {e}")
            print(f"✗ Failed to load metrics: {e}")
            sys.exit(1)

    elif inspect_type == "state":
        state_dir = args.state_dir or ".empathy/state"
        try:
            manager = StateManager(state_dir)
            users = manager.list_users()

            print("\nSaved states:")
            print(f"  Total users: {len(users)}")

            if users:
                print("\n  Users:")
                for uid in users:
                    print(f"    • {uid}")
        except (OSError, FileNotFoundError) as e:
            # State directory not found
            print(f"✗ State directory not found: {e}")
            sys.exit(1)
        except Exception as e:
            # Unexpected errors loading state
            logger.exception(f"Unexpected error loading state: {e}")
            print(f"✗ Failed to load state: {e}")
            sys.exit(1)

    print()


def cmd_export(args):
    """Export patterns to file for sharing/backup.

    Args:
        args: Namespace object from argparse with attributes:
            - output (str): Output file path.
            - user_id (str | None): Filter patterns by user ID.
            - db (str | None): Source database path.
            - format (str): Output format ('json').

    Returns:
        None: Exports patterns to file. Exits with code 1 on failure.

    Raises:
        ValueError: If output path is invalid or unsafe.
    """
    output_file = args.output
    user_id = args.user_id
    db_path = args.db or ".empathy/patterns.db"
    format_type = args.format

    print(f"📦 Exporting patterns to: {output_file}")
    print("=" * 50)

    try:
        # Load pattern library from source file
        if db_path.endswith(".json"):
            library = PatternPersistence.load_from_json(db_path)
        else:
            library = PatternPersistence.load_from_sqlite(db_path)

        patterns = list(library.patterns.values())

        # Filter by user_id if specified
        if user_id:
            patterns = [p for p in patterns if p.agent_id == user_id]

        print(f"  Found {len(patterns)} patterns")

        # Validate output path
        validated_output = _validate_file_path(output_file)

        if format_type == "json":
            # Create filtered library if user_id specified
            if user_id:
                filtered_library = PatternLibrary()
                for pattern in patterns:
                    filtered_library.contribute_pattern(pattern.agent_id, pattern)
            else:
                filtered_library = library

            # Export as JSON
            PatternPersistence.save_to_json(filtered_library, str(validated_output))
            print(f"  ✓ Exported {len(patterns)} patterns to {output_file}")
        else:
            print(f"✗ Unsupported format: {format_type}")
            sys.exit(1)

    except FileNotFoundError:
        print(f"✗ Source file not found: {db_path}")
        print("  Tip: Patterns are saved automatically when using the framework")
        sys.exit(1)
    except (OSError, PermissionError) as e:
        # Cannot write output file
        print(f"✗ Cannot write to file: {e}")
        sys.exit(1)
    except (ValueError, KeyError) as e:
        # Invalid pattern data
        print(f"✗ Invalid pattern data: {e}")
        sys.exit(1)
    except Exception as e:
        # Unexpected errors during export
        logger.exception(f"Unexpected error exporting patterns: {e}")
        print(f"✗ Export failed: {e}")
        sys.exit(1)

    print()


def cmd_import(args):
    """Import patterns from file (local dev only - SQLite/JSON).

    Merges imported patterns into existing pattern library.

    Args:
        args: Namespace object from argparse with attributes:
            - input (str): Input file path.
            - db (str | None): Target database path (default: .empathy/patterns.db).

    Returns:
        None: Imports and merges patterns. Exits with code 1 on failure.
    """
    input_file = args.input
    db_path = args.db or ".empathy/patterns.db"

    print(f"📥 Importing patterns from: {input_file}")
    print("=" * 50)

    try:
        # Load patterns from input file
        if input_file.endswith(".json"):
            imported_library = PatternPersistence.load_from_json(input_file)
        else:
            imported_library = PatternPersistence.load_from_sqlite(input_file)

        pattern_count = len(imported_library.patterns)
        print(f"  Found {pattern_count} patterns in file")

        # Load existing library if it exists, otherwise create new one
        try:
            if db_path.endswith(".json"):
                existing_library = PatternPersistence.load_from_json(db_path)
            else:
                existing_library = PatternPersistence.load_from_sqlite(db_path)

            print(f"  Existing library has {len(existing_library.patterns)} patterns")
        except FileNotFoundError:
            existing_library = PatternLibrary()
            print("  Creating new pattern library")

        # Merge imported patterns into existing library
        for pattern in imported_library.patterns.values():
            existing_library.contribute_pattern(pattern.agent_id, pattern)

        # Save merged library (SQLite for local dev)
        if db_path.endswith(".json"):
            PatternPersistence.save_to_json(existing_library, db_path)
        else:
            PatternPersistence.save_to_sqlite(existing_library, db_path)

        print(f"  ✓ Imported {pattern_count} patterns")
        print(f"  ✓ Total patterns in library: {len(existing_library.patterns)}")

    except FileNotFoundError:
        print(f"✗ Input file not found: {input_file}")
        sys.exit(1)
    except (ValueError, KeyError) as e:
        # Invalid pattern data format
        print(f"✗ Invalid pattern data: {e}")
        sys.exit(1)
    except (OSError, PermissionError) as e:
        # Cannot read input or write to database
        print(f"✗ File access error: {e}")
        sys.exit(1)
    except Exception as e:
        # Unexpected errors during import
        logger.exception(f"Unexpected error importing patterns: {e}")
        print(f"✗ Import failed: {e}")
        sys.exit(1)

    print()


def cmd_wizard(args):
    """Interactive setup wizard.

    Guides user through initial framework configuration step by step.

    Args:
        args: Namespace object from argparse (no additional attributes used).

    Returns:
        None: Creates empathy.config.yml with user's choices.
    """
    print("🧙 Empathy Framework Setup Wizard")
    print("=" * 50)
    print("\nI'll help you set up your Empathy Framework configuration.\n")

    # Step 1: Use case
    print("1. What's your primary use case?")
    print("   [1] Software development")
    print("   [2] Healthcare applications")
    print("   [3] Customer support")
    print("   [4] Other")

    use_case_choice = input("\nYour choice (1-4): ").strip()
    use_case_map = {
        "1": "software_development",
        "2": "healthcare",
        "3": "customer_support",
        "4": "general",
    }
    use_case = use_case_map.get(use_case_choice, "general")

    # Step 2: Empathy level
    print("\n2. What empathy level do you want to target?")
    print("   [1] Level 1 - Reactive (basic Q&A)")
    print("   [2] Level 2 - Guided (asks clarifying questions)")
    print("   [3] Level 3 - Proactive (offers improvements)")
    print("   [4] Level 4 - Anticipatory (predicts problems) ⭐ Recommended")
    print("   [5] Level 5 - Transformative (reshapes workflows)")

    level_choice = input("\nYour choice (1-5) [4]: ").strip() or "4"
    target_level = int(level_choice) if level_choice in ["1", "2", "3", "4", "5"] else 4

    # Step 3: LLM provider
    print("\n3. Which LLM provider will you use?")
    print("   [1] Anthropic Claude ⭐ Recommended")
    print("   [2] OpenAI GPT-4")
    print("   [3] Google Gemini (2M context)")
    print("   [4] Local (Ollama)")
    print("   [5] Hybrid (mix best models from each provider)")
    print("   [6] Skip (configure later)")

    llm_choice = input("\nYour choice (1-6) [1]: ").strip() or "1"
    llm_map = {
        "1": "anthropic",
        "2": "openai",
        "3": "google",
        "4": "ollama",
        "5": "hybrid",
        "6": None,
    }
    llm_provider = llm_map.get(llm_choice, "anthropic")

    # If hybrid selected, launch interactive tier selection
    if llm_provider == "hybrid":
        from empathy_os.models.provider_config import configure_hybrid_interactive

        configure_hybrid_interactive()
        llm_provider = None  # Already saved by hybrid config

    # Step 4: User ID
    print("\n4. What user ID should we use?")
    user_id = input("User ID [default_user]: ").strip() or "default_user"

    # Generate configuration
    config = {
        "user_id": user_id,
        "target_level": target_level,
        "confidence_threshold": 0.75,
        "persistence_enabled": True,
        "persistence_backend": "sqlite",
        "persistence_path": ".empathy",
        "metrics_enabled": True,
        "use_case": use_case,
    }

    if llm_provider:
        config["llm_provider"] = llm_provider

    # Save configuration
    output_file = "empathy.config.yml"
    print(f"\n5. Creating configuration file: {output_file}")

    # Write YAML config
    yaml_content = f"""# Empathy Framework Configuration
# Generated by setup wizard

# Core settings
user_id: "{config["user_id"]}"
target_level: {config["target_level"]}
confidence_threshold: {config["confidence_threshold"]}

# Use case
use_case: "{config["use_case"]}"

# Persistence
persistence_enabled: {str(config["persistence_enabled"]).lower()}
persistence_backend: "{config["persistence_backend"]}"
persistence_path: "{config["persistence_path"]}"

# Metrics
metrics_enabled: {str(config["metrics_enabled"]).lower()}
"""

    if llm_provider:
        yaml_content += f"""
# LLM Provider
llm_provider: "{llm_provider}"
"""

    validated_output = _validate_file_path(output_file)
    with open(validated_output, "w") as f:
        f.write(yaml_content)

    print(f"  ✓ Created {validated_output}")

    print("\n" + "=" * 50)
    print("✅ Setup complete!")
    print("\nNext steps:")
    print(f"  1. Edit {output_file} to customize settings")

    if llm_provider in ["anthropic", "openai", "google"]:
        env_var_map = {
            "anthropic": "ANTHROPIC_API_KEY",
            "openai": "OPENAI_API_KEY",
            "google": "GOOGLE_API_KEY",
        }
        env_var = env_var_map.get(llm_provider, "API_KEY")
        print(f"  2. Set {env_var} environment variable")

    print("  3. Run: empathy-framework run --config empathy.config.yml")
    print("\nHappy empathizing! 🧠✨\n")


def cmd_provider_hybrid(args):
    """Configure hybrid mode - pick best models for each tier.

    Args:
        args: Namespace object from argparse (no additional attributes used).

    Returns:
        None: Launches interactive tier configuration.
    """
    from empathy_os.models.provider_config import configure_hybrid_interactive

    configure_hybrid_interactive()


def cmd_provider_show(args):
    """Show current provider configuration.

    Args:
        args: Namespace object from argparse (no additional attributes used).

    Returns:
        None: Prints provider configuration and model mappings.
    """
    from empathy_os.models.provider_config import ProviderConfig
    from empathy_os.workflows.config import WorkflowConfig

    print("\n" + "=" * 60)
    print("Provider Configuration")
    print("=" * 60)

    # Detect available providers
    config = ProviderConfig.auto_detect()
    print(
        f"\nDetected API keys for: {', '.join(config.available_providers) if config.available_providers else 'None'}",
    )

    # Load workflow config
    wf_config = WorkflowConfig.load()
    print(f"\nDefault provider: {wf_config.default_provider}")

    # Show effective models
    print("\nEffective model mapping:")
    if wf_config.custom_models and "hybrid" in wf_config.custom_models:
        hybrid = wf_config.custom_models["hybrid"]
        for tier in ["cheap", "capable", "premium"]:
            model = hybrid.get(tier, "not configured")
            print(f"  {tier:8} → {model}")
    else:
        from empathy_os.models import MODEL_REGISTRY

        provider = wf_config.default_provider
        if provider in MODEL_REGISTRY:
            for tier in ["cheap", "capable", "premium"]:
                model_info = MODEL_REGISTRY[provider].get(tier)
                if model_info:
                    print(f"  {tier:8} → {model_info.id} ({provider})")

    print()


def cmd_provider_set(args):
    """Set default provider.

    Args:
        args: Namespace object from argparse with attributes:
            - name (str): Provider name to set as default.

    Returns:
        None: Saves provider to .empathy/workflows.yaml.
    """
    import yaml

    provider = args.name
    workflows_path = Path(".empathy/workflows.yaml")

    # Load existing config or create new
    if workflows_path.exists():
        with open(workflows_path) as f:
            config = yaml.safe_load(f) or {}
    else:
        config = {}
        workflows_path.parent.mkdir(parents=True, exist_ok=True)

    config["default_provider"] = provider

    validated_workflows_path = _validate_file_path(str(workflows_path))
    with open(validated_workflows_path, "w") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)

    print(f"✓ Default provider set to: {provider}")
    print(f"  Saved to: {validated_workflows_path}")

    if provider == "hybrid":
        print("\n  Tip: Run 'empathy provider hybrid' to customize tier models")


def cmd_sync_claude(args):
    """Sync patterns to Claude Code rules directory.

    Converts learned patterns into Claude Code markdown rules.

    Args:
        args: Namespace object from argparse with attributes:
            - patterns_dir (str): Source patterns directory.
            - output_dir (str): Target Claude Code rules directory.

    Returns:
        int: 0 on success, 1 on failure.

    Raises:
        ValueError: If output path is invalid or unsafe.
    """
    import json as json_mod

    patterns_dir = Path(args.patterns_dir)
    # Validate output directory path
    validated_output_dir = _validate_file_path(args.output_dir)
    output_dir = validated_output_dir

    print("=" * 60)
    print("  SYNC PATTERNS TO CLAUDE CODE")
    print("=" * 60 + "\n")

    if not patterns_dir.exists():
        print(f"✗ Patterns directory not found: {patterns_dir}")
        print("  Run 'empathy learn --analyze 20' first to learn patterns")
        return 1

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    synced_count = 0
    pattern_files = ["debugging.json", "security.json", "tech_debt.json", "inspection.json"]

    for pattern_file in pattern_files:
        source_path = patterns_dir / pattern_file
        if not source_path.exists():
            continue

        try:
            with open(source_path) as f:
                data = json_mod.load(f)

            patterns = data.get("patterns", data.get("items", []))
            if not patterns:
                continue

            # Generate markdown rule file
            category = pattern_file.replace(".json", "")
            rule_content = _generate_claude_rule(category, patterns)

            # Write rule file
            rule_file = output_dir / f"{category}.md"
            # Validate rule file path before writing
            validated_rule_file = _validate_file_path(str(rule_file), allowed_dir=str(output_dir))
            with open(validated_rule_file, "w") as f:
                f.write(rule_content)

            print(f"  ✓ {category}: {len(patterns)} patterns → {rule_file}")
            synced_count += len(patterns)

        except (json_mod.JSONDecodeError, OSError) as e:
            print(f"  ✗ Failed to process {pattern_file}: {e}")

    print(f"\n{'─' * 60}")
    print(f"  Total: {synced_count} patterns synced to {output_dir}")
    print("=" * 60 + "\n")

    if synced_count == 0:
        print("No patterns to sync. Run 'empathy learn' first.")
        return 1

    return 0


def _generate_claude_rule(category: str, patterns: list) -> str:
    """Generate a Claude Code rule file from patterns."""
    lines = [
        f"# {category.replace('_', ' ').title()} Patterns",
        "",
        "Auto-generated from Empathy Framework learned patterns.",
        f"Total patterns: {len(patterns)}",
        "",
        "---",
        "",
    ]

    if category == "debugging":
        lines.extend(
            [
                "## Bug Fix Patterns",
                "",
                "When debugging similar issues, consider these historical fixes:",
                "",
            ],
        )
        for p in patterns[:20]:  # Limit to 20 most recent
            bug_type = p.get("bug_type", "unknown")
            root_cause = p.get("root_cause", "Unknown")
            fix = p.get("fix", "See commit history")
            files = p.get("files_affected", [])

            lines.append(f"### {bug_type}")
            lines.append(f"- **Root cause**: {root_cause}")
            lines.append(f"- **Fix**: {fix}")
            if files:
                lines.append(f"- **Files**: {', '.join(files[:3])}")
            lines.append("")

    elif category == "security":
        lines.extend(
            [
                "## Security Decisions",
                "",
                "Previously reviewed security items:",
                "",
            ],
        )
        for p in patterns[:20]:
            decision = p.get("decision", "unknown")
            reason = p.get("reason", "")
            lines.append(f"- **{p.get('type', 'unknown')}**: {decision}")
            if reason:
                lines.append(f"  - Reason: {reason}")
            lines.append("")

    elif category == "tech_debt":
        lines.extend(
            [
                "## Tech Debt Tracking",
                "",
                "Known technical debt items:",
                "",
            ],
        )
        for p in patterns[:20]:
            lines.append(f"- {p.get('description', str(p))}")

    else:
        lines.extend(
            [
                f"## {category.title()} Items",
                "",
            ],
        )
        for p in patterns[:20]:
            lines.append(f"- {p.get('description', str(p)[:100])}")

    return "\n".join(lines)


def _extract_workflow_content(final_output):
    """Extract readable content from workflow final_output.

    Workflows return their results in various formats - this extracts
    the actual content users want to see.
    """
    if final_output is None:
        return None

    # If it's already a string, return it
    if isinstance(final_output, str):
        return final_output

    # If it's a dict, try to extract meaningful content
    if isinstance(final_output, dict):
        # Common keys that contain the main output
        # formatted_report is first - preferred for security-audit and other formatted outputs
        content_keys = [
            "formatted_report",  # Human-readable formatted output (security-audit, etc.)
            "answer",
            "synthesis",
            "result",
            "output",
            "content",
            "report",
            "summary",
            "analysis",
            "review",
            "documentation",
            "response",
            "recommendations",
            "findings",
            "tests",
            "plan",
        ]
        for key in content_keys:
            if final_output.get(key):
                val = final_output[key]
                if isinstance(val, str):
                    return val
                if isinstance(val, dict):
                    # Recursively extract
                    return _extract_workflow_content(val)

        # If no common key found, try to format the dict nicely
        # Look for any string value that's substantial
        for _key, val in final_output.items():
            if isinstance(val, str) and len(val) > 100:
                return val

        # Last resort: return a formatted version
        import json

        return json.dumps(final_output, indent=2)

    # For lists or other types, convert to string
    return str(final_output)


def cmd_workflow(args):
    """Multi-model workflow management and execution.

    Supports listing, describing, and running workflows with tier-based models.

    Args:
        args: Namespace object from argparse with attributes:
            - action (str): Action to perform ('list', 'describe', 'run').
            - name (str | None): Workflow name (for describe/run).
            - input (str | None): JSON input for workflow execution.
            - provider (str | None): LLM provider override.
            - json (bool): If True, output as JSON format.
            - use_recommended_tier (bool): Enable tier fallback.
            - write_tests (bool): For test-gen, write tests to files.
            - output_dir (str | None): For test-gen, output directory.

    Returns:
        int | None: 0 on success, 1 on failure, None for list action.
    """
    import asyncio
    import json as json_mod

    action = args.action

    if action == "list":
        # List available workflows
        workflows = get_workflow_list()

        if args.json:
            print(json_mod.dumps(workflows, indent=2))
        else:
            print("\n" + "=" * 60)
            print("  MULTI-MODEL WORKFLOWS")
            print("=" * 60 + "\n")

            for wf in workflows:
                print(f"  {wf['name']:15} {wf['description']}")
                stages = " → ".join(f"{s}({wf['tier_map'][s]})" for s in wf["stages"])
                print(f"    Stages: {stages}")
                print()

            print("-" * 60)
            print("  Use: empathy workflow describe <name>")
            print("  Use: empathy workflow run <name> [--input JSON]")
            print("=" * 60 + "\n")

    elif action == "describe":
        # Describe a specific workflow
        name = args.name
        if not name:
            print("Error: workflow name required")
            print("Usage: empathy workflow describe <name>")
            return 1

        try:
            workflow_cls = get_workflow(name)
            provider = getattr(args, "provider", None)
            workflow = workflow_cls(provider=provider)

            # Get actual provider from workflow (may come from config)
            actual_provider = getattr(workflow, "_provider_str", provider or "anthropic")

            if args.json:
                info = {
                    "name": workflow.name,
                    "description": workflow.description,
                    "provider": actual_provider,
                    "stages": workflow.stages,
                    "tier_map": {k: v.value for k, v in workflow.tier_map.items()},
                    "models": {
                        stage: workflow.get_model_for_tier(workflow.tier_map[stage])
                        for stage in workflow.stages
                    },
                }
                print(json_mod.dumps(info, indent=2))
            else:
                print(f"Provider: {actual_provider}")
                print(workflow.describe())

        except KeyError as e:
            print(f"Error: {e}")
            return 1

    elif action == "run":
        # Run a workflow
        name = args.name
        if not name:
            print("Error: workflow name required")
            print('Usage: empathy workflow run <name> --input \'{"key": "value"}\'')
            return 1

        try:
            workflow_cls = get_workflow(name)

            # Get provider from CLI arg, or fall back to config's default_provider
            if args.provider:
                provider = args.provider
            else:
                from empathy_os.workflows.config import WorkflowConfig

                wf_config = WorkflowConfig.load()
                provider = wf_config.default_provider

            # Initialize workflow with provider and optional tier fallback
            # Note: Not all workflows support enable_tier_fallback, so we check first
            import inspect
            use_tier_fallback = getattr(args, "use_recommended_tier", False)

            # Get the workflow's __init__ signature to know what params it accepts
            init_sig = inspect.signature(workflow_cls.__init__)
            init_params = set(init_sig.parameters.keys())

            workflow_kwargs = {}

            # Add provider if supported
            if "provider" in init_params:
                workflow_kwargs["provider"] = provider

            # Add enable_tier_fallback only if the workflow supports it
            if "enable_tier_fallback" in init_params and use_tier_fallback:
                workflow_kwargs["enable_tier_fallback"] = use_tier_fallback

            # Add health-check specific parameters
            if name == "health-check" and "health_score_threshold" in init_params:
                health_score_threshold = getattr(args, "health_score_threshold", 100)
                workflow_kwargs["health_score_threshold"] = health_score_threshold

            workflow = workflow_cls(**workflow_kwargs)

            # Parse input
            input_data = {}
            if args.input:
                input_data = json_mod.loads(args.input)

            # Add test-gen specific flags to input_data (only for test-gen workflow)
            if name == "test-gen":
                if getattr(args, "write_tests", False):
                    input_data["write_tests"] = True
                if getattr(args, "output_dir", None):
                    input_data["output_dir"] = args.output_dir

            # Only print header when not in JSON mode
            if not args.json:
                print(f"\n Running workflow: {name} (provider: {provider})")
                print("=" * 50)

            # Execute workflow
            result = asyncio.run(workflow.execute(**input_data))

            # Extract the actual content - handle different result types
            if hasattr(result, "final_output"):
                output_content = _extract_workflow_content(result.final_output)
            elif hasattr(result, "metadata") and isinstance(result.metadata, dict):
                # Check for formatted_report in metadata (e.g., HealthCheckResult)
                output_content = result.metadata.get("formatted_report")
                if not output_content and hasattr(result, "summary"):
                    output_content = result.summary
            elif hasattr(result, "summary"):
                output_content = result.summary
            else:
                output_content = str(result)

            # Get timing - handle different attribute names
            duration_ms = getattr(result, "total_duration_ms", None)
            if duration_ms is None and hasattr(result, "duration_seconds"):
                duration_ms = int(result.duration_seconds * 1000)

            # Get cost info if available (check cost_report first, then direct cost attribute)
            cost_report = getattr(result, "cost_report", None)
            if cost_report and hasattr(cost_report, "total_cost"):
                total_cost = cost_report.total_cost
                savings = getattr(cost_report, "savings", 0.0)
            else:
                # Fall back to direct cost attribute (e.g., CodeReviewPipelineResult)
                total_cost = getattr(result, "cost", 0.0)
                savings = 0.0

            if args.json:
                # Extract error from various result types
                error = getattr(result, "error", None)
                is_successful = getattr(result, "success", getattr(result, "approved", True))
                if not error and not is_successful:
                    blockers = getattr(result, "blockers", [])
                    if blockers:
                        error = "; ".join(blockers)
                    else:
                        metadata = getattr(result, "metadata", {})
                        error = metadata.get("error") if isinstance(metadata, dict) else None

                # JSON output includes both content and metadata
                # Include final_output for programmatic access (VSCode panels, etc.)
                raw_final_output = getattr(result, "final_output", None)
                if raw_final_output and isinstance(raw_final_output, dict):
                    # Make a copy to avoid modifying the original
                    final_output_serializable = {}
                    for k, v in raw_final_output.items():
                        # Skip non-serializable items
                        if isinstance(v, set):
                            final_output_serializable[k] = list(v)
                        elif v is None or isinstance(v, str | int | float | bool | list | dict):
                            final_output_serializable[k] = v
                        else:
                            try:
                                final_output_serializable[k] = str(v)
                            except Exception as e:  # noqa: BLE001
                                # INTENTIONAL: Silently skip any non-serializable objects
                                # This is a best-effort serialization for JSON output
                                # We cannot predict all possible object types users might return
                                logger.debug(f"Cannot serialize field {k}: {e}")
                                pass
                else:
                    final_output_serializable = None

                output = {
                    "success": is_successful,
                    "output": output_content,
                    "final_output": final_output_serializable,
                    "cost": total_cost,
                    "savings": savings,
                    "duration_ms": duration_ms or 0,
                    "error": error,
                }
                print(json_mod.dumps(output, indent=2))
            # Display the actual results - this is what users want to see
            else:
                # Show tier progression if tier fallback was used
                if use_tier_fallback and hasattr(workflow, "_tier_progression"):
                    tier_progression = workflow._tier_progression
                    if tier_progression:
                        print("\n" + "=" * 60)
                        print("  TIER PROGRESSION (Intelligent Fallback)")
                        print("=" * 60)

                        # Group by stage
                        stage_tiers: dict[str, list[tuple[str, bool]]] = {}
                        for stage, tier, success in tier_progression:
                            if stage not in stage_tiers:
                                stage_tiers[stage] = []
                            stage_tiers[stage].append((tier, success))

                        # Display progression for each stage
                        for stage, attempts in stage_tiers.items():
                            status = "✓" if any(success for _, success in attempts) else "✗"
                            print(f"\n{status} Stage: {stage}")

                            for idx, (tier, success) in enumerate(attempts, 1):
                                attempt_status = "✓ SUCCESS" if success else "✗ FAILED"
                                if idx == 1:
                                    print(f"  Attempt {idx}: {tier.upper():8} → {attempt_status}")
                                else:
                                    prev_tier = attempts[idx - 2][0]
                                    print(
                                        f"  Attempt {idx}: {tier.upper():8} → {attempt_status} "
                                        f"(upgraded from {prev_tier.upper()})"
                                    )

                        # Calculate cost savings (only if result has stages attribute)
                        if hasattr(result, "stages") and result.stages:
                            actual_cost = sum(stage.cost for stage in result.stages if stage.cost)
                            # Estimate what cost would be if all stages used PREMIUM
                            premium_cost = actual_cost * 3  # Conservative estimate

                            savings = premium_cost - actual_cost
                            savings_pct = (savings / premium_cost * 100) if premium_cost > 0 else 0

                            print("\n" + "-" * 60)
                            print("💰 Cost Savings:")
                            print(f"  Actual cost:   ${actual_cost:.4f}")
                            print(f"  Premium cost:  ${premium_cost:.4f} (if all PREMIUM)")
                            print(f"  Savings:       ${savings:.4f} ({savings_pct:.1f}%)")
                        print("=" * 60 + "\n")

                # Display workflow result
                # Handle different result types (success, approved, etc.)
                is_successful = getattr(result, "success", getattr(result, "approved", True))
                if is_successful:
                    if output_content:
                        print(f"\n{output_content}\n")
                    else:
                        print("\n✓ Workflow completed successfully.\n")
                else:
                    # Extract error from various result types
                    error_msg = getattr(result, "error", None)
                    if not error_msg:
                        # Check for blockers (CodeReviewPipelineResult)
                        blockers = getattr(result, "blockers", [])
                        if blockers:
                            error_msg = "; ".join(blockers)
                        else:
                            # Check metadata for error
                            metadata = getattr(result, "metadata", {})
                            error_msg = (
                                metadata.get("error") if isinstance(metadata, dict) else None
                            )
                    error_msg = error_msg or "Unknown error"
                    print(f"\n✗ Workflow failed: {error_msg}\n")

        except KeyError as e:
            print(f"Error: {e}")
            return 1
        except json_mod.JSONDecodeError as e:
            print(f"Error parsing input JSON: {e}")
            return 1

    elif action == "config":
        # Generate or show workflow configuration
        from pathlib import Path

        config_path = Path(".empathy/workflows.yaml")

        if config_path.exists() and not getattr(args, "force", False):
            print(f"Config already exists: {config_path}")
            print("Use --force to overwrite")
            print("\nCurrent configuration:")
            print("-" * 40)
            config = WorkflowConfig.load()
            print(f"  Default provider: {config.default_provider}")
            if config.workflow_providers:
                print("  Workflow providers:")
                for wf, prov in config.workflow_providers.items():
                    print(f"    {wf}: {prov}")
            if config.custom_models:
                print("  Custom models configured")
            return 0

        # Create config directory and file
        config_path.parent.mkdir(parents=True, exist_ok=True)
        validated_config_path = _validate_file_path(str(config_path))
        validated_config_path.write_text(create_example_config())
        print(f"✓ Created workflow config: {validated_config_path}")
        print("\nEdit this file to customize:")
        print("  - Default provider (anthropic, openai, ollama)")
        print("  - Per-workflow provider overrides")
        print("  - Custom model mappings")
        print("  - Model pricing")
        print("\nOr use environment variables:")
        print("  EMPATHY_WORKFLOW_PROVIDER=openai")
        print("  EMPATHY_MODEL_PREMIUM=gpt-5.2")

    else:
        print(f"Unknown action: {action}")
        print("Available: list, describe, run, config")
        return 1

    return 0


def cmd_frameworks(args):
    """List and manage agent frameworks.

    Displays available agent frameworks with their capabilities and recommendations.

    Args:
        args: Namespace object from argparse with attributes:
            - all (bool): If True, show all frameworks including experimental.
            - recommend (str | None): Use case for framework recommendation.
            - json (bool): If True, output as JSON format.

    Returns:
        int: 0 on success, 1 on failure.
    """
    import json as json_mod

    try:
        from empathy_llm_toolkit.agent_factory import AgentFactory
        from empathy_llm_toolkit.agent_factory.framework import (
            get_framework_info,
            get_recommended_framework,
        )
    except ImportError:
        print("Agent Factory not available. Install empathy-framework with all dependencies.")
        return 1

    show_all = getattr(args, "all", False)
    recommend_use_case = getattr(args, "recommend", None)
    output_json = getattr(args, "json", False)

    if recommend_use_case:
        # Recommend a framework
        recommended = get_recommended_framework(recommend_use_case)
        info = get_framework_info(recommended)

        if output_json:
            print(
                json_mod.dumps(
                    {"use_case": recommend_use_case, "recommended": recommended.value, **info},
                    indent=2,
                ),
            )
        else:
            print(f"\nRecommended framework for '{recommend_use_case}': {info['name']}")
            print(f"  Best for: {', '.join(info['best_for'])}")
            if info.get("install_command"):
                print(f"  Install: {info['install_command']}")
            print()
        return 0

    # List frameworks
    frameworks = AgentFactory.list_frameworks(installed_only=not show_all)

    if output_json:
        print(
            json_mod.dumps(
                [
                    {
                        "id": f["framework"].value,
                        "name": f["name"],
                        "installed": f["installed"],
                        "best_for": f["best_for"],
                        "install_command": f.get("install_command"),
                    }
                    for f in frameworks
                ],
                indent=2,
            ),
        )
    else:
        print("\n" + "=" * 60)
        print("  AGENT FRAMEWORKS")
        print("=" * 60 + "\n")

        for f in frameworks:
            status = "INSTALLED" if f["installed"] else "not installed"
            print(f"  {f['name']:20} [{status}]")
            print(f"    Best for: {', '.join(f['best_for'][:3])}")
            if not f["installed"] and f.get("install_command"):
                print(f"    Install:  {f['install_command']}")
            print()

        print("-" * 60)
        print("  Use: empathy frameworks --recommend <use_case>")
        print("  Use cases: general, rag, multi_agent, code_analysis")
        print("=" * 60 + "\n")

    return 0


# =============================================================================
# Telemetry CLI Command Wrappers
# =============================================================================


def _cmd_telemetry_show(args):
    """Wrapper for telemetry show command."""
    if not TELEMETRY_CLI_AVAILABLE:
        print("Telemetry commands not available. Install telemetry dependencies.")
        return 1
    return cmd_telemetry_show(args)


def _cmd_telemetry_savings(args):
    """Wrapper for telemetry savings command."""
    if not TELEMETRY_CLI_AVAILABLE:
        print("Telemetry commands not available. Install telemetry dependencies.")
        return 1
    return cmd_telemetry_savings(args)


def _cmd_telemetry_compare(args):
    """Wrapper for telemetry compare command."""
    if not TELEMETRY_CLI_AVAILABLE:
        print("Telemetry commands not available. Install telemetry dependencies.")
        return 1
    return cmd_telemetry_compare(args)


def _cmd_telemetry_reset(args):
    """Wrapper for telemetry reset command."""
    if not TELEMETRY_CLI_AVAILABLE:
        print("Telemetry commands not available. Install telemetry dependencies.")
        return 1
    return cmd_telemetry_reset(args)


def _cmd_telemetry_export(args):
    """Wrapper for telemetry export command."""
    if not TELEMETRY_CLI_AVAILABLE:
        print("Telemetry commands not available. Install telemetry dependencies.")
        return 1
    return cmd_telemetry_export(args)


def _cmd_tier1_status(args):
    """Wrapper for tier1 status command."""
    if not TELEMETRY_CLI_AVAILABLE:
        print("Tier 1 monitoring commands not available. Install telemetry dependencies.")
        return 1
    return cmd_tier1_status(args)


def _cmd_task_routing_report(args):
    """Wrapper for task routing report command."""
    if not TELEMETRY_CLI_AVAILABLE:
        print("Tier 1 monitoring commands not available. Install telemetry dependencies.")
        return 1
    return cmd_task_routing_report(args)


def _cmd_test_status(args):
    """Wrapper for test status command."""
    if not TELEMETRY_CLI_AVAILABLE:
        print("Tier 1 monitoring commands not available. Install telemetry dependencies.")
        return 1
    return cmd_test_status(args)


def _cmd_agent_performance(args):
    """Wrapper for agent performance command."""
    if not TELEMETRY_CLI_AVAILABLE:
        print("Tier 1 monitoring commands not available. Install telemetry dependencies.")
        return 1
    return cmd_agent_performance(args)


def main():
    """Main CLI entry point"""
    # Configure Windows-compatible asyncio event loop policy
    setup_asyncio_policy()

    parser = argparse.ArgumentParser(
        prog="empathy",
        description="Empathy - Build AI systems with 5 levels of empathy",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Version command
    parser_version = subparsers.add_parser("version", help="Display version information")
    parser_version.set_defaults(func=cmd_version)

    # Init command
    parser_init = subparsers.add_parser("init", help="Initialize a new project")
    parser_init.add_argument(
        "--format",
        choices=["yaml", "json"],
        default="yaml",
        help="Configuration format (default: yaml)",
    )
    parser_init.add_argument("--output", "-o", help="Output file path")
    parser_init.set_defaults(func=cmd_init)

    # Validate command
    parser_validate = subparsers.add_parser("validate", help="Validate configuration file")
    parser_validate.add_argument("config", help="Path to configuration file")
    parser_validate.set_defaults(func=cmd_validate)

    # Info command
    parser_info = subparsers.add_parser("info", help="Display framework information")
    parser_info.add_argument("--config", "-c", help="Configuration file")
    parser_info.set_defaults(func=cmd_info)

    # Patterns commands
    parser_patterns = subparsers.add_parser("patterns", help="Pattern library commands")
    patterns_subparsers = parser_patterns.add_subparsers(dest="patterns_command")

    # Patterns list
    parser_patterns_list = patterns_subparsers.add_parser("list", help="List patterns in library")
    parser_patterns_list.add_argument("library", help="Path to pattern library file")
    parser_patterns_list.add_argument(
        "--format",
        choices=["json", "sqlite"],
        default="json",
        help="Library format (default: json)",
    )
    parser_patterns_list.set_defaults(func=cmd_patterns_list)

    # Patterns export
    parser_patterns_export = patterns_subparsers.add_parser("export", help="Export patterns")
    parser_patterns_export.add_argument("input", help="Input file path")
    parser_patterns_export.add_argument("output", help="Output file path")
    parser_patterns_export.add_argument(
        "--input-format",
        choices=["json", "sqlite"],
        default="json",
    )
    parser_patterns_export.add_argument(
        "--output-format",
        choices=["json", "sqlite"],
        default="json",
    )
    parser_patterns_export.set_defaults(func=cmd_patterns_export)

    # Patterns resolve - mark investigating bugs as resolved
    parser_patterns_resolve = patterns_subparsers.add_parser(
        "resolve",
        help="Resolve investigating bug patterns",
    )
    parser_patterns_resolve.add_argument(
        "bug_id",
        nargs="?",
        help="Bug ID to resolve (omit to list investigating)",
    )
    parser_patterns_resolve.add_argument("--root-cause", help="Description of the root cause")
    parser_patterns_resolve.add_argument("--fix", help="Description of the fix applied")
    parser_patterns_resolve.add_argument("--fix-code", help="Code snippet of the fix")
    parser_patterns_resolve.add_argument("--time", type=int, help="Resolution time in minutes")
    parser_patterns_resolve.add_argument(
        "--resolved-by",
        default="@developer",
        help="Who resolved it",
    )
    parser_patterns_resolve.add_argument(
        "--patterns-dir",
        default="./patterns",
        help="Path to patterns directory",
    )
    parser_patterns_resolve.add_argument(
        "--no-regenerate",
        action="store_true",
        help="Skip regenerating summary",
    )
    parser_patterns_resolve.set_defaults(func=cmd_patterns_resolve)

    # Metrics commands
    parser_metrics = subparsers.add_parser("metrics", help="Metrics commands")
    metrics_subparsers = parser_metrics.add_subparsers(dest="metrics_command")

    # Metrics show
    parser_metrics_show = metrics_subparsers.add_parser("show", help="Show user metrics")
    parser_metrics_show.add_argument("user", help="User ID")
    parser_metrics_show.add_argument("--db", default="./metrics.db", help="Metrics database path")
    parser_metrics_show.set_defaults(func=cmd_metrics_show)

    # State commands
    parser_state = subparsers.add_parser("state", help="State management commands")
    state_subparsers = parser_state.add_subparsers(dest="state_command")

    # State list
    parser_state_list = state_subparsers.add_parser("list", help="List saved states")
    parser_state_list.add_argument(
        "--state-dir",
        default="./empathy_state",
        help="State directory path",
    )
    parser_state_list.set_defaults(func=cmd_state_list)

    # Run command (Interactive REPL)
    parser_run = subparsers.add_parser("run", help="Interactive REPL mode")
    parser_run.add_argument("--config", "-c", help="Configuration file path")
    parser_run.add_argument("--user-id", help="User ID (default: cli_user)")
    parser_run.add_argument(
        "--level",
        type=int,
        default=4,
        help="Target empathy level (1-5, default: 4)",
    )
    parser_run.set_defaults(func=cmd_run)

    # Inspect command (Unified inspection)
    parser_inspect = subparsers.add_parser("inspect", help="Inspect patterns, metrics, or state")
    parser_inspect.add_argument(
        "type",
        choices=["patterns", "metrics", "state"],
        help="Type of inspection (patterns, metrics, or state)",
    )
    parser_inspect.add_argument("--user-id", help="User ID to filter by (optional)")
    parser_inspect.add_argument("--db", help="Database path (default: .empathy/patterns.db)")
    parser_inspect.add_argument(
        "--state-dir",
        help="State directory path (default: .empathy/state)",
    )
    parser_inspect.set_defaults(func=cmd_inspect)

    # Export command
    parser_export = subparsers.add_parser(
        "export",
        help="Export patterns to file for sharing/backup",
    )
    parser_export.add_argument("output", help="Output file path")
    parser_export.add_argument(
        "--user-id",
        help="User ID to export (optional, exports all if not specified)",
    )
    parser_export.add_argument("--db", help="Database path (default: .empathy/patterns.db)")
    parser_export.add_argument(
        "--format",
        default="json",
        choices=["json"],
        help="Export format (default: json)",
    )
    parser_export.set_defaults(func=cmd_export)

    # Import command
    parser_import = subparsers.add_parser("import", help="Import patterns from file")
    parser_import.add_argument("input", help="Input file path")
    parser_import.add_argument("--db", help="Database path (default: .empathy/patterns.db)")
    parser_import.set_defaults(func=cmd_import)

    # Wizard command (Interactive setup)
    parser_wizard = subparsers.add_parser(
        "wizard",
        help="Interactive setup wizard for creating configuration",
    )
    parser_wizard.set_defaults(func=cmd_wizard)

    # Provider command (Model provider configuration)
    parser_provider = subparsers.add_parser(
        "provider",
        help="Configure model providers and hybrid mode",
    )
    provider_subparsers = parser_provider.add_subparsers(dest="provider_cmd")

    # provider hybrid - Interactive hybrid configuration
    parser_provider_hybrid = provider_subparsers.add_parser(
        "hybrid",
        help="Configure hybrid mode - pick best models for each tier",
    )
    parser_provider_hybrid.set_defaults(func=cmd_provider_hybrid)

    # provider show - Show current configuration
    parser_provider_show = provider_subparsers.add_parser(
        "show",
        help="Show current provider configuration",
    )
    parser_provider_show.set_defaults(func=cmd_provider_show)

    # provider set - Quick set single provider
    parser_provider_set = provider_subparsers.add_parser(
        "set",
        help="Set default provider (anthropic, openai, google, ollama)",
    )
    parser_provider_set.add_argument(
        "name",
        choices=["anthropic", "openai", "google", "ollama", "hybrid"],
        help="Provider name",
    )
    parser_provider_set.set_defaults(func=cmd_provider_set)

    # Status command (Session status assistant)
    parser_status = subparsers.add_parser(
        "status",
        help="Session status - prioritized project status report",
    )
    parser_status.add_argument(
        "--patterns-dir",
        default="./patterns",
        help="Path to patterns directory",
    )
    parser_status.add_argument("--project-root", default=".", help="Project root directory")
    parser_status.add_argument(
        "--force",
        action="store_true",
        help="Force show status regardless of inactivity",
    )
    parser_status.add_argument("--full", action="store_true", help="Show all items (no limit)")
    parser_status.add_argument("--json", action="store_true", help="Output as JSON")
    parser_status.add_argument("--select", type=int, help="Select an item to get its action prompt")
    parser_status.add_argument(
        "--inactivity",
        type=int,
        default=60,
        help="Inactivity threshold in minutes (default: 60)",
    )
    parser_status.set_defaults(func=cmd_status)

    # Review command (Pattern-based code review)
    parser_review = subparsers.add_parser(
        "review",
        help="Pattern-based code review against historical bugs",
    )
    parser_review.add_argument("files", nargs="*", help="Files to review (default: recent changes)")
    parser_review.add_argument("--staged", action="store_true", help="Review staged changes only")
    parser_review.add_argument(
        "--severity",
        choices=["info", "warning", "error"],
        default="info",
        help="Minimum severity to report (default: info)",
    )
    parser_review.add_argument("--patterns-dir", default="./patterns", help="Patterns directory")
    parser_review.add_argument("--json", action="store_true", help="Output as JSON")
    parser_review.set_defaults(func=cmd_review)

    # Health command (Code Health Assistant)
    parser_health = subparsers.add_parser(
        "health",
        help="Code health assistant - run checks and auto-fix issues",
    )
    parser_health.add_argument(
        "--deep",
        action="store_true",
        help="Run comprehensive checks (slower)",
    )
    parser_health.add_argument(
        "--check",
        choices=["lint", "format", "types", "tests", "security", "deps"],
        help="Run specific check only",
    )
    parser_health.add_argument("--fix", action="store_true", help="Auto-fix issues where possible")
    parser_health.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be fixed without applying",
    )
    parser_health.add_argument(
        "--interactive",
        action="store_true",
        help="Prompt before applying non-safe fixes",
    )
    parser_health.add_argument("--details", action="store_true", help="Show detailed issue list")
    parser_health.add_argument(
        "--full",
        action="store_true",
        help="Show full report with all details",
    )
    parser_health.add_argument(
        "--trends",
        type=int,
        metavar="DAYS",
        help="Show health trends over N days",
    )
    parser_health.add_argument(
        "--project-root",
        default=".",
        help="Project root directory (default: current)",
    )
    parser_health.add_argument("--json", action="store_true", help="Output as JSON")
    parser_health.set_defaults(func=cmd_health)

    # =========================================================================
    # POWER USER WORKFLOWS (v2.4+)
    # =========================================================================

    # Morning command (start-of-day briefing)
    parser_morning = subparsers.add_parser(
        "morning",
        help="Start-of-day briefing with patterns, debt, and focus areas",
    )
    parser_morning.add_argument(
        "--patterns-dir",
        default="./patterns",
        help="Path to patterns directory",
    )
    parser_morning.add_argument("--project-root", default=".", help="Project root directory")
    parser_morning.add_argument("--verbose", "-v", action="store_true", help="Show detailed output")
    parser_morning.set_defaults(func=cmd_morning)

    # Ship command (pre-commit validation)
    parser_ship = subparsers.add_parser("ship", help="Pre-commit validation pipeline")
    parser_ship.add_argument(
        "--patterns-dir",
        default="./patterns",
        help="Path to patterns directory",
    )
    parser_ship.add_argument("--project-root", default=".", help="Project root directory")
    parser_ship.add_argument(
        "--skip-sync",
        action="store_true",
        help="Skip syncing patterns to Claude",
    )
    parser_ship.add_argument(
        "--tests-only",
        action="store_true",
        help="Run tests only (skip lint/format checks)",
    )
    parser_ship.add_argument(
        "--security-only",
        action="store_true",
        help="Run security checks only",
    )
    parser_ship.add_argument("--verbose", "-v", action="store_true", help="Show detailed output")
    parser_ship.set_defaults(func=cmd_ship)

    # Fix-all command (auto-fix everything)
    parser_fix_all = subparsers.add_parser(
        "fix-all",
        help="Auto-fix all fixable lint and format issues",
    )
    parser_fix_all.add_argument("--project-root", default=".", help="Project root directory")
    parser_fix_all.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be fixed without applying",
    )
    parser_fix_all.add_argument("--verbose", "-v", action="store_true", help="Show detailed output")
    parser_fix_all.set_defaults(func=cmd_fix_all)

    # Learn command (pattern learning from git history)
    parser_learn = subparsers.add_parser(
        "learn",
        help="Learn patterns from git history and bug fixes",
    )
    parser_learn.add_argument(
        "--patterns-dir",
        default="./patterns",
        help="Path to patterns directory",
    )
    parser_learn.add_argument(
        "--analyze",
        type=int,
        metavar="N",
        help="Analyze last N commits (default: 10)",
    )
    parser_learn.add_argument(
        "--watch",
        action="store_true",
        help="Watch for new commits (not yet implemented)",
    )
    parser_learn.add_argument("--verbose", "-v", action="store_true", help="Show detailed output")
    parser_learn.set_defaults(func=cmd_learn)

    # Costs command (cost tracking dashboard)
    parser_costs = subparsers.add_parser(
        "costs",
        help="View API cost tracking and savings from model routing",
    )
    parser_costs.add_argument(
        "--days",
        type=int,
        default=7,
        help="Number of days to include (default: 7)",
    )
    parser_costs.add_argument("--empathy-dir", default=".empathy", help="Empathy data directory")
    parser_costs.add_argument("--json", action="store_true", help="Output as JSON")
    parser_costs.set_defaults(func=cmd_costs)

    # Telemetry commands (usage tracking)
    parser_telemetry = subparsers.add_parser(
        "telemetry",
        help="View and manage local usage telemetry",
    )
    telemetry_subparsers = parser_telemetry.add_subparsers(dest="telemetry_command")

    # Telemetry show command
    parser_telemetry_show = telemetry_subparsers.add_parser(
        "show",
        help="Show recent LLM calls",
    )
    parser_telemetry_show.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Number of entries to show (default: 20)",
    )
    parser_telemetry_show.add_argument(
        "--days",
        type=int,
        help="Only show entries from last N days",
    )
    parser_telemetry_show.set_defaults(func=lambda args: _cmd_telemetry_show(args))

    # Telemetry savings command
    parser_telemetry_savings = telemetry_subparsers.add_parser(
        "savings",
        help="Calculate cost savings vs baseline",
    )
    parser_telemetry_savings.add_argument(
        "--days",
        type=int,
        default=30,
        help="Number of days to analyze (default: 30)",
    )
    parser_telemetry_savings.set_defaults(func=lambda args: _cmd_telemetry_savings(args))

    # Telemetry compare command
    parser_telemetry_compare = telemetry_subparsers.add_parser(
        "compare",
        help="Compare two time periods",
    )
    parser_telemetry_compare.add_argument(
        "--period1",
        type=int,
        default=7,
        help="First period in days (default: 7)",
    )
    parser_telemetry_compare.add_argument(
        "--period2",
        type=int,
        default=30,
        help="Second period in days (default: 30)",
    )
    parser_telemetry_compare.set_defaults(func=lambda args: _cmd_telemetry_compare(args))

    # Telemetry reset command
    parser_telemetry_reset = telemetry_subparsers.add_parser(
        "reset",
        help="Clear all telemetry data",
    )
    parser_telemetry_reset.add_argument(
        "--confirm",
        action="store_true",
        help="Confirm deletion",
    )
    parser_telemetry_reset.set_defaults(func=lambda args: _cmd_telemetry_reset(args))

    # Telemetry export command
    parser_telemetry_export = telemetry_subparsers.add_parser(
        "export",
        help="Export telemetry data",
    )
    parser_telemetry_export.add_argument(
        "--format",
        choices=["json", "csv"],
        default="json",
        help="Export format (default: json)",
    )
    parser_telemetry_export.add_argument(
        "--output",
        "-o",
        help="Output file (default: stdout)",
    )
    parser_telemetry_export.add_argument(
        "--days",
        type=int,
        help="Only export last N days",
    )
    parser_telemetry_export.set_defaults(func=lambda args: _cmd_telemetry_export(args))

    # Progressive workflow commands (tier escalation)
    parser_progressive = subparsers.add_parser(
        "progressive",
        help="Manage progressive tier escalation workflows",
    )
    progressive_subparsers = parser_progressive.add_subparsers(dest="progressive_command")

    # Progressive list command
    parser_progressive_list = progressive_subparsers.add_parser(
        "list",
        help="List all saved progressive workflow results",
    )
    parser_progressive_list.add_argument(
        "--storage-path",
        help="Path to progressive workflow storage (default: .empathy/progressive_runs)",
    )
    parser_progressive_list.set_defaults(func=lambda args: cmd_list_results(args))

    # Progressive show command
    parser_progressive_show = progressive_subparsers.add_parser(
        "show",
        help="Show detailed report for a specific task",
    )
    parser_progressive_show.add_argument(
        "task_id",
        type=str,
        help="Task ID to display",
    )
    parser_progressive_show.add_argument(
        "--storage-path",
        help="Path to progressive workflow storage (default: .empathy/progressive_runs)",
    )
    parser_progressive_show.add_argument(
        "--json",
        action="store_true",
        help="Output in JSON format",
    )
    parser_progressive_show.set_defaults(func=lambda args: cmd_show_report(args))

    # Progressive analytics command
    parser_progressive_analytics = progressive_subparsers.add_parser(
        "analytics",
        help="Show cost optimization analytics",
    )
    parser_progressive_analytics.add_argument(
        "--storage-path",
        help="Path to progressive workflow storage (default: .empathy/progressive_runs)",
    )
    parser_progressive_analytics.add_argument(
        "--json",
        action="store_true",
        help="Output in JSON format",
    )
    parser_progressive_analytics.set_defaults(func=lambda args: cmd_analytics(args))

    # Progressive cleanup command
    parser_progressive_cleanup = progressive_subparsers.add_parser(
        "cleanup",
        help="Clean up old progressive workflow results",
    )
    parser_progressive_cleanup.add_argument(
        "--storage-path",
        help="Path to progressive workflow storage (default: .empathy/progressive_runs)",
    )
    parser_progressive_cleanup.add_argument(
        "--retention-days",
        type=int,
        default=30,
        help="Number of days to retain results (default: 30)",
    )
    parser_progressive_cleanup.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be deleted without actually deleting",
    )
    parser_progressive_cleanup.set_defaults(func=lambda args: cmd_cleanup(args))

    # Tier 1 automation monitoring commands

    # tier1 command - comprehensive status
    parser_tier1 = subparsers.add_parser(
        "tier1",
        help="Show Tier 1 automation status (tasks, tests, coverage, agents)",
    )
    parser_tier1.add_argument(
        "--hours",
        type=int,
        default=24,
        help="Hours to analyze (default: 24)",
    )
    parser_tier1.set_defaults(func=lambda args: _cmd_tier1_status(args))

    # tasks command - task routing report
    parser_tasks = subparsers.add_parser(
        "tasks",
        help="Show task routing report",
    )
    parser_tasks.add_argument(
        "--hours",
        type=int,
        default=24,
        help="Hours to analyze (default: 24)",
    )
    parser_tasks.set_defaults(func=lambda args: _cmd_task_routing_report(args))

    # tests command - test execution status
    parser_tests = subparsers.add_parser(
        "tests",
        help="Show test execution status",
    )
    parser_tests.add_argument(
        "--hours",
        type=int,
        default=24,
        help="Hours to analyze (default: 24)",
    )
    parser_tests.set_defaults(func=lambda args: _cmd_test_status(args))

    # agents command - agent performance
    parser_agents = subparsers.add_parser(
        "agents",
        help="Show agent performance metrics",
    )
    parser_agents.add_argument(
        "--hours",
        type=int,
        default=168,
        help="Hours to analyze (default: 168 / 7 days)",
    )
    parser_agents.set_defaults(func=lambda args: _cmd_agent_performance(args))

    # New command (project scaffolding)
    parser_new = subparsers.add_parser("new", help="Create a new project from a template")
    parser_new.add_argument(
        "template",
        nargs="?",
        help="Template name (minimal, python-cli, python-fastapi, python-agent)",
    )
    parser_new.add_argument("name", nargs="?", help="Project name")
    parser_new.add_argument("--output", "-o", help="Output directory (default: ./<project-name>)")
    parser_new.add_argument("--force", "-f", action="store_true", help="Overwrite existing files")
    parser_new.add_argument("--list", "-l", action="store_true", help="List available templates")
    parser_new.set_defaults(func=cmd_new)

    # Dashboard command (visual web interface)
    parser_dashboard = subparsers.add_parser("dashboard", help="Launch visual dashboard in browser")
    parser_dashboard.add_argument(
        "--port",
        type=int,
        default=8765,
        help="Port to run on (default: 8765)",
    )
    parser_dashboard.add_argument(
        "--patterns-dir",
        default="./patterns",
        help="Path to patterns directory",
    )
    parser_dashboard.add_argument(
        "--empathy-dir",
        default=".empathy",
        help="Empathy data directory",
    )
    parser_dashboard.add_argument(
        "--no-browser",
        action="store_true",
        help="Don't open browser automatically",
    )
    parser_dashboard.set_defaults(func=cmd_dashboard)

    # Frameworks command (agent framework management)
    parser_frameworks = subparsers.add_parser(
        "frameworks",
        help="List and manage agent frameworks (LangChain, LangGraph, AutoGen, Haystack)",
    )
    parser_frameworks.add_argument(
        "--all",
        action="store_true",
        help="Show all frameworks including uninstalled",
    )
    parser_frameworks.add_argument(
        "--recommend",
        metavar="USE_CASE",
        help="Recommend framework for use case (general, rag, multi_agent, code_analysis)",
    )
    parser_frameworks.add_argument("--json", action="store_true", help="Output as JSON")
    parser_frameworks.set_defaults(func=cmd_frameworks)

    # Workflow command (multi-model workflow management)
    parser_workflow = subparsers.add_parser(
        "workflow",
        help="Multi-model workflows for cost-optimized task pipelines",
    )
    parser_workflow.add_argument(
        "action",
        choices=["list", "describe", "run", "config"],
        help="Action: list, describe, run, or config",
    )
    parser_workflow.add_argument(
        "name",
        nargs="?",
        help="Workflow name (for describe/run)",
    )
    parser_workflow.add_argument(
        "--input",
        "-i",
        help="JSON input data for workflow execution",
    )
    parser_workflow.add_argument(
        "--provider",
        "-p",
        choices=["anthropic", "openai", "google", "ollama", "hybrid"],
        default=None,  # None means use config
        help="Model provider: anthropic, openai, google, ollama, or hybrid (mix of best models)",
    )
    parser_workflow.add_argument(
        "--force",
        action="store_true",
        help="Force overwrite existing config file",
    )
    parser_workflow.add_argument("--json", action="store_true", help="Output as JSON")
    parser_workflow.add_argument(
        "--use-recommended-tier",
        action="store_true",
        help="Enable intelligent tier fallback: start with CHEAP tier and automatically upgrade if quality gates fail",
    )
    parser_workflow.add_argument(
        "--write-tests",
        action="store_true",
        help="(test-gen workflow) Write generated tests to disk",
    )
    parser_workflow.add_argument(
        "--output-dir",
        default="tests/generated",
        help="(test-gen workflow) Output directory for generated tests",
    )
    parser_workflow.add_argument(
        "--health-score-threshold",
        type=int,
        default=95,
        help="(health-check workflow) Minimum health score required (0-100, default: 95 for very strict quality)",
    )
    parser_workflow.set_defaults(func=cmd_workflow)

    # Sync-claude command (sync patterns to Claude Code)
    parser_sync_claude = subparsers.add_parser(
        "sync-claude",
        help="Sync learned patterns to Claude Code rules",
    )
    parser_sync_claude.add_argument(
        "--patterns-dir",
        default="./patterns",
        help="Path to patterns directory",
    )
    parser_sync_claude.add_argument(
        "--output-dir",
        default=".claude/rules/empathy",
        help="Output directory for Claude rules (default: .claude/rules/empathy)",
    )
    parser_sync_claude.set_defaults(func=cmd_sync_claude)

    # =========================================================================
    # USER EXPERIENCE COMMANDS (v2.5+)
    # =========================================================================

    # Cheatsheet command (quick reference)
    parser_cheatsheet = subparsers.add_parser("cheatsheet", help="Quick reference of all commands")
    parser_cheatsheet.add_argument(
        "category",
        nargs="?",
        help="Category to show (getting-started, daily-workflow, code-quality, etc.)",
    )
    parser_cheatsheet.add_argument(
        "--compact",
        action="store_true",
        help="Show commands only without descriptions",
    )
    parser_cheatsheet.set_defaults(func=cmd_cheatsheet)

    # Onboard command (interactive tutorial)
    parser_onboard = subparsers.add_parser(
        "onboard",
        help="Interactive onboarding tutorial for new users",
    )
    parser_onboard.add_argument("--step", type=int, help="Jump to a specific step (1-5)")
    parser_onboard.add_argument("--reset", action="store_true", help="Reset onboarding progress")
    parser_onboard.set_defaults(func=cmd_onboard)

    # Explain command (detailed command explanations)
    parser_explain = subparsers.add_parser(
        "explain",
        help="Get detailed explanation of how a command works",
    )
    parser_explain.add_argument(
        "command",
        choices=["morning", "ship", "learn", "health", "sync-claude"],
        help="Command to explain",
    )
    parser_explain.set_defaults(func=cmd_explain)

    # Achievements command (progress tracking)
    parser_achievements = subparsers.add_parser(
        "achievements",
        help="View your usage statistics and achievements",
    )
    parser_achievements.set_defaults(func=cmd_achievements)

    # Tier recommendation commands (cascading tier optimization)
    parser_tier = subparsers.add_parser(
        "tier",
        help="Intelligent tier recommendations for cascading workflows",
    )
    tier_subparsers = parser_tier.add_subparsers(dest="tier_command")

    # tier recommend
    parser_tier_recommend = tier_subparsers.add_parser(
        "recommend",
        help="Get tier recommendation for a bug/task",
    )
    parser_tier_recommend.add_argument(
        "description",
        help="Description of the bug or task",
    )
    parser_tier_recommend.add_argument(
        "--files",
        help="Comma-separated list of affected files (optional)",
    )
    parser_tier_recommend.add_argument(
        "--complexity",
        type=int,
        help="Manual complexity hint 1-10 (optional)",
    )
    parser_tier_recommend.set_defaults(func=cmd_tier_recommend)

    # tier stats
    parser_tier_stats = tier_subparsers.add_parser(
        "stats",
        help="Show tier pattern learning statistics",
    )
    parser_tier_stats.set_defaults(func=cmd_tier_stats)

    # Orchestrate command (meta-orchestration workflows)
    parser_orchestrate = subparsers.add_parser(
        "orchestrate",
        help="Run meta-orchestration workflows (release-prep, health-check)",
    )
    parser_orchestrate.add_argument(
        "workflow",
        choices=["release-prep", "health-check"],
        help="Workflow to execute (test-coverage disabled in v4.0.0)",
    )
    parser_orchestrate.add_argument(
        "--project-root",
        default=".",
        help="Project root directory (default: current directory)",
    )
    # Release-prep workflow arguments
    parser_orchestrate.add_argument(
        "--path",
        default=".",
        help="Path to codebase to analyze (for release-prep, default: current directory)",
    )
    parser_orchestrate.add_argument(
        "--min-coverage",
        type=float,
        help="Minimum test coverage threshold (for release-prep, default: 80.0)",
    )
    parser_orchestrate.add_argument(
        "--min-quality",
        type=float,
        help="Minimum code quality score (for release-prep, default: 7.0)",
    )
    parser_orchestrate.add_argument(
        "--max-critical",
        type=float,
        help="Maximum critical security issues (for release-prep, default: 0)",
    )
    # Health-check workflow arguments
    parser_orchestrate.add_argument(
        "--mode",
        choices=["daily", "weekly", "release"],
        help="Health check mode (for health-check, default: daily)",
    )
    parser_orchestrate.add_argument(
        "--focus",
        help="Focus area for health check (for health-check, optional)",
    )
    parser_orchestrate.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON",
    )
    parser_orchestrate.set_defaults(func=cmd_orchestrate)

    # Wizard Factory commands (create wizards 12x faster)
    add_wizard_factory_commands(subparsers)

    # Parse arguments
    args = parser.parse_args()

    # Execute command
    if hasattr(args, "func"):
        result = args.func(args)

        # Show progressive discovery tips after command execution
        if args.command and args.command not in ("dashboard", "run"):
            try:
                show_tip_if_available(args.command)
            except Exception as e:  # noqa: BLE001
                # INTENTIONAL: Discovery tips are optional UX enhancements
                # They should never cause command execution to fail
                # Cannot predict all possible errors from discovery system
                logger.debug(f"Discovery tip not available for {args.command}: {e}")
                pass

        return result if result is not None else 0
    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
