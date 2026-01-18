"""CLI for Socratic Workflow Builder

Provides command-line interface for:
- Starting interactive Socratic sessions
- Listing and resuming sessions
- Generating workflows from sessions
- Managing blueprints

Commands:
    empathy socratic start [--goal "..."]
    empathy socratic resume <session_id>
    empathy socratic list [--state completed|in_progress]
    empathy socratic generate <session_id>
    empathy socratic blueprints [--domain security]
    empathy socratic run <blueprint_id> [--input file.json]

Copyright 2026 Smart-AI-Memory
Licensed under Fair Source License 0.9
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from .engine import SocraticWorkflowBuilder
from .session import SessionState, SocraticSession
from .forms import Form, FormField, FieldType
from .storage import get_default_storage, JSONFileStorage, SQLiteStorage, StorageBackend


# =============================================================================
# CONSOLE FORMATTING
# =============================================================================


class Console:
    """Simple console output formatting."""

    COLORS = {
        "reset": "\033[0m",
        "bold": "\033[1m",
        "dim": "\033[2m",
        "red": "\033[91m",
        "green": "\033[92m",
        "yellow": "\033[93m",
        "blue": "\033[94m",
        "magenta": "\033[95m",
        "cyan": "\033[96m",
    }

    def __init__(self, use_color: bool = True):
        self.use_color = use_color and sys.stdout.isatty()

    def _c(self, color: str, text: str) -> str:
        """Apply color to text."""
        if not self.use_color:
            return text
        return f"{self.COLORS.get(color, '')}{text}{self.COLORS['reset']}"

    def header(self, text: str) -> None:
        """Print a header."""
        print()
        print(self._c("bold", "=" * 60))
        print(self._c("bold", f"  {text}"))
        print(self._c("bold", "=" * 60))
        print()

    def subheader(self, text: str) -> None:
        """Print a subheader."""
        print()
        print(self._c("cyan", f"── {text} ──"))
        print()

    def success(self, text: str) -> None:
        """Print success message."""
        print(self._c("green", f"✓ {text}"))

    def error(self, text: str) -> None:
        """Print error message."""
        print(self._c("red", f"✗ {text}"))

    def warning(self, text: str) -> None:
        """Print warning message."""
        print(self._c("yellow", f"⚠ {text}"))

    def info(self, text: str) -> None:
        """Print info message."""
        print(self._c("blue", f"ℹ {text}"))

    def dim(self, text: str) -> None:
        """Print dimmed text."""
        print(self._c("dim", text))

    def progress(self, value: float, width: int = 30) -> str:
        """Generate progress bar."""
        filled = int(value * width)
        bar = "▓" * filled + "░" * (width - filled)
        return f"[{bar}] {value:.0%}"

    def table(self, headers: list[str], rows: list[list[str]]) -> None:
        """Print a simple table."""
        # Calculate column widths
        widths = [len(h) for h in headers]
        for row in rows:
            for i, cell in enumerate(row):
                if i < len(widths):
                    widths[i] = max(widths[i], len(str(cell)))

        # Print header
        header_line = " | ".join(
            self._c("bold", h.ljust(widths[i])) for i, h in enumerate(headers)
        )
        print(header_line)
        print("-" * (sum(widths) + len(widths) * 3 - 1))

        # Print rows
        for row in rows:
            row_line = " | ".join(
                str(cell).ljust(widths[i]) for i, cell in enumerate(row)
            )
            print(row_line)


console = Console()


# =============================================================================
# INTERACTIVE FORM RENDERER
# =============================================================================


def render_form_interactive(form: Form, console: Console) -> dict[str, Any]:
    """Render a form and collect user input.

    Args:
        form: Form to render
        console: Console for output

    Returns:
        Dictionary of answers
    """
    console.subheader(form.title)

    if form.description:
        print(form.description)
        print()

    print(console.progress(form.progress))
    print()

    answers: dict[str, Any] = {}

    for field in form.fields:
        # Check visibility
        if not field.should_show(answers):
            continue

        # Render field
        required = " *" if field.validation.required else ""
        print(f"{console._c('bold', field.label)}{required}")

        if field.help_text:
            console.dim(f"  {field.help_text}")

        # Handle by field type
        if field.field_type == FieldType.SINGLE_SELECT:
            answers[field.id] = _input_single_select(field, console)

        elif field.field_type == FieldType.MULTI_SELECT:
            answers[field.id] = _input_multi_select(field, console)

        elif field.field_type == FieldType.BOOLEAN:
            answers[field.id] = _input_boolean(field, console)

        elif field.field_type == FieldType.TEXT_AREA:
            answers[field.id] = _input_text_area(field, console)

        else:  # TEXT, NUMBER, etc.
            answers[field.id] = _input_text(field, console)

        print()

    return answers


def _input_single_select(field: FormField, console: Console) -> str | None:
    """Input for single select field."""
    for i, opt in enumerate(field.options, 1):
        rec = console._c("green", " (Recommended)") if opt.recommended else ""
        print(f"  {i}. {opt.label}{rec}")
        if opt.description:
            console.dim(f"     {opt.description}")

    while True:
        response = input("\n  Enter number: ").strip()

        if not response:
            if not field.validation.required:
                return None
            console.error("This field is required")
            continue

        try:
            idx = int(response) - 1
            if 0 <= idx < len(field.options):
                return field.options[idx].value
            console.error(f"Enter a number between 1 and {len(field.options)}")
        except ValueError:
            console.error("Enter a valid number")


def _input_multi_select(field: FormField, console: Console) -> list[str]:
    """Input for multi select field."""
    for i, opt in enumerate(field.options, 1):
        rec = console._c("green", " (Recommended)") if opt.recommended else ""
        print(f"  {i}. {opt.label}{rec}")
        if opt.description:
            console.dim(f"     {opt.description}")

    while True:
        response = input("\n  Enter numbers (comma-separated): ").strip()

        if not response:
            if not field.validation.required:
                return []
            console.error("Select at least one option")
            continue

        try:
            indices = [int(x.strip()) - 1 for x in response.split(",")]
            selected = []
            for idx in indices:
                if 0 <= idx < len(field.options):
                    selected.append(field.options[idx].value)

            if selected:
                return selected
            console.error("No valid options selected")
        except ValueError:
            console.error("Enter valid numbers separated by commas")


def _input_boolean(field: FormField, console: Console) -> bool:
    """Input for boolean field."""
    while True:
        response = input("  (y/n): ").strip().lower()

        if response in ("y", "yes", "true", "1"):
            return True
        elif response in ("n", "no", "false", "0"):
            return False
        elif not response and not field.validation.required:
            return False
        else:
            console.error("Enter 'y' or 'n'")


def _input_text(field: FormField, console: Console) -> str:
    """Input for text field."""
    prompt = f"  {field.placeholder or 'Enter value'}: " if field.placeholder else "  > "

    while True:
        response = input(prompt).strip()

        if not response:
            if not field.validation.required:
                return ""
            console.error("This field is required")
            continue

        # Validate
        is_valid, error = field.validate(response)
        if is_valid:
            return response
        console.error(error)


def _input_text_area(field: FormField, console: Console) -> str:
    """Input for text area field."""
    print("  (Enter text, then press Enter twice to finish)")

    lines = []
    empty_count = 0

    while True:
        line = input("  > " if not lines else "    ")

        if not line:
            empty_count += 1
            if empty_count >= 2:
                break
            lines.append("")
        else:
            empty_count = 0
            lines.append(line)

    response = "\n".join(lines).strip()

    if not response and field.validation.required:
        console.error("This field is required")
        return _input_text_area(field, console)

    return response


# =============================================================================
# CLI COMMANDS
# =============================================================================


def cmd_start(args: argparse.Namespace) -> int:
    """Start a new Socratic session."""
    storage = get_default_storage()
    builder = SocraticWorkflowBuilder()

    console.header("SOCRATIC WORKFLOW BUILDER")

    # Start session
    session = builder.start_session()
    console.info(f"Session ID: {session.session_id[:8]}...")

    # Get initial goal
    if args.goal:
        goal = args.goal
        console.info(f"Goal: {goal}")
    else:
        initial_form = builder.get_initial_form()
        answers = render_form_interactive(initial_form, console)
        goal = answers.get("goal", "")

    if not goal:
        console.error("No goal provided")
        return 1

    # Set goal and analyze
    session = builder.set_goal(session, goal)
    storage.save_session(session)

    # Show analysis
    if session.goal_analysis:
        console.subheader("Goal Analysis")
        print(f"  Domain: {session.goal_analysis.domain}")
        print(f"  Confidence: {session.goal_analysis.confidence:.0%}")

        if session.goal_analysis.ambiguities:
            print()
            console.warning("Ambiguities detected:")
            for amb in session.goal_analysis.ambiguities:
                print(f"    • {amb}")

    # Interactive questioning loop
    while not builder.is_ready_to_generate(session):
        form = builder.get_next_questions(session)
        if not form:
            break

        answers = render_form_interactive(form, console)
        session = builder.submit_answers(session, answers)
        storage.save_session(session)

        # Show progress
        summary = builder.get_session_summary(session)
        console.info(f"Requirements completeness: {summary['requirements_completeness']:.0%}")

    # Generate workflow
    if builder.is_ready_to_generate(session):
        console.subheader("Generating Workflow")

        workflow = builder.generate_workflow(session)
        storage.save_session(session)

        if session.blueprint:
            storage.save_blueprint(session.blueprint)

        console.success("Workflow generated!")
        print()
        print(workflow.describe())

        if session.blueprint:
            console.info(f"Blueprint ID: {session.blueprint.id[:8]}...")

    return 0


def cmd_resume(args: argparse.Namespace) -> int:
    """Resume an existing session."""
    storage = get_default_storage()
    builder = SocraticWorkflowBuilder()

    # Find session
    session = storage.load_session(args.session_id)

    # Try partial match
    if not session:
        sessions = storage.list_sessions()
        matches = [s for s in sessions if s["session_id"].startswith(args.session_id)]
        if len(matches) == 1:
            session = storage.load_session(matches[0]["session_id"])
        elif len(matches) > 1:
            console.error(f"Multiple sessions match '{args.session_id}':")
            for m in matches:
                print(f"  - {m['session_id'][:8]}... ({m['state']})")
            return 1

    if not session:
        console.error(f"Session not found: {args.session_id}")
        return 1

    console.header(f"RESUMING SESSION {session.session_id[:8]}...")
    console.info(f"Goal: {session.goal[:80]}...")
    console.info(f"State: {session.state.value}")

    # Rebuild builder state
    if session.goal:
        builder._sessions[session.session_id] = session

    # Continue questioning or generate
    if session.state == SessionState.COMPLETED:
        console.success("Session already completed")
        return 0

    while not builder.is_ready_to_generate(session):
        form = builder.get_next_questions(session)
        if not form:
            break

        answers = render_form_interactive(form, console)
        session = builder.submit_answers(session, answers)
        storage.save_session(session)

    if builder.is_ready_to_generate(session):
        console.subheader("Generating Workflow")

        workflow = builder.generate_workflow(session)
        storage.save_session(session)

        if session.blueprint:
            storage.save_blueprint(session.blueprint)

        console.success("Workflow generated!")
        print()
        print(workflow.describe())

    return 0


def cmd_list(args: argparse.Namespace) -> int:
    """List sessions."""
    storage = get_default_storage()

    state = None
    if args.state:
        try:
            state = SessionState(args.state)
        except ValueError:
            console.error(f"Invalid state: {args.state}")
            return 1

    sessions = storage.list_sessions(state=state, limit=args.limit)

    if not sessions:
        console.info("No sessions found")
        return 0

    console.header("SOCRATIC SESSIONS")

    headers = ["ID", "State", "Goal", "Updated"]
    rows = []
    for s in sessions:
        rows.append([
            s["session_id"][:8],
            s["state"],
            (s.get("goal") or "")[:40] + "..." if len(s.get("goal") or "") > 40 else s.get("goal") or "",
            s.get("updated_at", "")[:16],
        ])

    console.table(headers, rows)
    return 0


def cmd_blueprints(args: argparse.Namespace) -> int:
    """List blueprints."""
    storage = get_default_storage()

    blueprints = storage.list_blueprints(domain=args.domain, limit=args.limit)

    if not blueprints:
        console.info("No blueprints found")
        return 0

    console.header("WORKFLOW BLUEPRINTS")

    headers = ["ID", "Name", "Domain", "Agents", "Generated"]
    rows = []
    for b in blueprints:
        rows.append([
            b["id"][:8] if b.get("id") else "?",
            b.get("name", "")[:30],
            b.get("domain", ""),
            str(b.get("agents_count", 0)),
            (b.get("generated_at") or "")[:16],
        ])

    console.table(headers, rows)
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    """Show details of a session or blueprint."""
    storage = get_default_storage()

    # Try as session first
    session = storage.load_session(args.id)
    if session:
        console.header(f"SESSION: {session.session_id[:8]}...")

        print(f"State: {session.state.value}")
        print(f"Goal: {session.goal}")
        print(f"Created: {session.created_at}")
        print(f"Updated: {session.updated_at}")

        if session.goal_analysis:
            console.subheader("Analysis")
            print(f"Domain: {session.goal_analysis.domain}")
            print(f"Confidence: {session.goal_analysis.confidence:.0%}")
            print(f"Intent: {session.goal_analysis.intent}")

        if session.requirements.must_have:
            console.subheader("Requirements")
            for req in session.requirements.must_have:
                print(f"  • {req}")

        return 0

    # Try as blueprint
    blueprint = storage.load_blueprint(args.id)
    if blueprint:
        console.header(f"BLUEPRINT: {blueprint.name}")

        print(f"ID: {blueprint.id}")
        print(f"Domain: {blueprint.domain}")
        print(f"Languages: {', '.join(blueprint.supported_languages)}")
        print(f"Quality Focus: {', '.join(blueprint.quality_focus)}")

        console.subheader("Agents")
        for agent in blueprint.agents:
            print(f"  • {agent.spec.name} ({agent.spec.role.value})")
            print(f"    Goal: {agent.spec.goal[:60]}...")

        console.subheader("Stages")
        for stage in blueprint.stages:
            parallel = "(parallel)" if stage.parallel else "(sequential)"
            print(f"  • {stage.name} {parallel}")
            print(f"    Agents: {', '.join(stage.agent_ids)}")

        return 0

    console.error(f"Not found: {args.id}")
    return 1


def cmd_delete(args: argparse.Namespace) -> int:
    """Delete a session."""
    storage = get_default_storage()

    if not args.force:
        response = input(f"Delete session {args.session_id}? (y/N): ").strip().lower()
        if response != "y":
            console.info("Cancelled")
            return 0

    if storage.delete_session(args.session_id):
        console.success(f"Deleted session {args.session_id}")
        return 0
    else:
        console.error(f"Session not found: {args.session_id}")
        return 1


def cmd_export(args: argparse.Namespace) -> int:
    """Export a blueprint to JSON."""
    storage = get_default_storage()

    blueprint = storage.load_blueprint(args.blueprint_id)
    if not blueprint:
        console.error(f"Blueprint not found: {args.blueprint_id}")
        return 1

    data = blueprint.to_dict()

    if args.output:
        with open(args.output, "w") as f:
            json.dump(data, f, indent=2, default=str)
        console.success(f"Exported to {args.output}")
    else:
        print(json.dumps(data, indent=2, default=str))

    return 0


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser."""
    parser = argparse.ArgumentParser(
        prog="empathy socratic",
        description="Socratic Workflow Builder - Generate agent workflows through guided questioning",
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # start
    start_parser = subparsers.add_parser("start", help="Start a new Socratic session")
    start_parser.add_argument("--goal", "-g", help="Initial goal (skip first question)")
    start_parser.add_argument("--non-interactive", action="store_true", help="Non-interactive mode")

    # resume
    resume_parser = subparsers.add_parser("resume", help="Resume an existing session")
    resume_parser.add_argument("session_id", help="Session ID (can be partial)")

    # list
    list_parser = subparsers.add_parser("list", help="List sessions")
    list_parser.add_argument("--state", "-s", choices=["awaiting_goal", "awaiting_answers", "ready_to_generate", "completed", "cancelled"])
    list_parser.add_argument("--limit", "-n", type=int, default=20)

    # blueprints
    bp_parser = subparsers.add_parser("blueprints", help="List workflow blueprints")
    bp_parser.add_argument("--domain", "-d", help="Filter by domain")
    bp_parser.add_argument("--limit", "-n", type=int, default=20)

    # show
    show_parser = subparsers.add_parser("show", help="Show session or blueprint details")
    show_parser.add_argument("id", help="Session or blueprint ID")

    # delete
    delete_parser = subparsers.add_parser("delete", help="Delete a session")
    delete_parser.add_argument("session_id", help="Session ID")
    delete_parser.add_argument("--force", "-f", action="store_true", help="Skip confirmation")

    # export
    export_parser = subparsers.add_parser("export", help="Export blueprint to JSON")
    export_parser.add_argument("blueprint_id", help="Blueprint ID")
    export_parser.add_argument("--output", "-o", help="Output file (default: stdout)")

    return parser


def main(argv: list[str] | None = None) -> int:
    """Main entry point."""
    parser = create_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 0

    commands = {
        "start": cmd_start,
        "resume": cmd_resume,
        "list": cmd_list,
        "blueprints": cmd_blueprints,
        "show": cmd_show,
        "delete": cmd_delete,
        "export": cmd_export,
    }

    cmd_func = commands.get(args.command)
    if cmd_func:
        try:
            return cmd_func(args)
        except KeyboardInterrupt:
            print()
            console.info("Interrupted")
            return 130
        except Exception as e:
            console.error(f"Error: {e}")
            return 1

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
