"""Progressive Feature Discovery for Empathy Framework

Surface tips and suggestions at the right time based on usage patterns.
Helps users discover power-user features without overwhelming them upfront.

Copyright 2025 Smart-AI-Memory
Licensed under Fair Source License 0.9
"""

import json
from datetime import datetime
from pathlib import Path

from empathy_os.config import _validate_file_path

# Discovery tips with conditions
DISCOVERY_TIPS = {
    # After first commands
    "after_first_inspect": {
        "tip": "Try 'empathy ship' before commits for automated pre-flight checks",
        "trigger": "inspect",
        "min_uses": 1,
        "priority": 2,
        "shown": False,
    },
    "after_first_health": {
        "tip": "Use 'empathy fix-all' to auto-fix lint and format issues",
        "trigger": "health",
        "min_uses": 1,
        "priority": 2,
        "shown": False,
    },
    # After accumulating usage
    "after_10_inspects": {
        "tip": "You've got patterns! Run 'empathy sync-claude' to share them with Claude Code",
        "trigger": "inspect",
        "min_uses": 10,
        "priority": 1,
        "shown": False,
    },
    "after_5_ships": {
        "tip": "Start your day with 'empathy morning' for a productivity briefing",
        "trigger": "ship",
        "min_uses": 5,
        "priority": 1,
        "shown": False,
    },
    # Context-based tips
    "high_tech_debt": {
        "tip": "Tech debt is trending up. Try 'empathy status' for priority focus areas",
        "condition": lambda stats: stats.get("tech_debt_trend") == "increasing",
        "priority": 1,
        "shown": False,
    },
    "no_patterns": {
        "tip": "Run 'empathy learn' to extract patterns from your git history",
        "condition": lambda stats: stats.get("patterns_learned", 0) == 0
        and stats.get("total_commands", 0) > 5,
        "priority": 1,
        "shown": False,
    },
    "cost_savings": {
        "tip": "Check your API savings with 'empathy costs' - model routing can save 80%!",
        "condition": lambda stats: stats.get("api_requests", 0) > 10,
        "priority": 2,
        "shown": False,
    },
    # Weekly reminders
    "weekly_sync": {
        "tip": "Weekly reminder: Run 'empathy sync-claude' to keep Claude Code patterns current",
        "condition": lambda stats: _days_since_sync(stats) >= 7,
        "priority": 2,
        "shown": False,
    },
}


def _days_since_sync(stats: dict) -> int:
    """Calculate days since last Claude sync."""
    last_sync = stats.get("last_claude_sync")
    if not last_sync:
        return 999
    try:
        sync_date = datetime.fromisoformat(last_sync)
        return (datetime.now() - sync_date).days
    except (ValueError, TypeError):
        return 999


class DiscoveryEngine:
    """Tracks usage and surfaces contextual tips.

    Usage:
        engine = DiscoveryEngine()
        engine.record_command("inspect")
        tips = engine.get_pending_tips()
        engine.mark_shown("after_first_inspect")
    """

    def __init__(self, storage_dir: str = ".empathy"):
        """Initialize discovery engine."""
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.stats_file = self.storage_dir / "discovery_stats.json"
        self._load()

    def _load(self) -> None:
        """Load discovery state from storage."""
        if self.stats_file.exists():
            try:
                with open(self.stats_file) as f:
                    self.state = json.load(f)
            except (OSError, json.JSONDecodeError):
                self.state = self._default_state()
        else:
            self.state = self._default_state()

    def _default_state(self) -> dict:
        """Return default state structure."""
        return {
            "command_counts": {},
            "tips_shown": [],
            "total_commands": 0,
            "patterns_learned": 0,
            "api_requests": 0,
            "tech_debt_trend": "unknown",
            "last_claude_sync": None,
            "first_run": datetime.now().isoformat(),
            "last_updated": datetime.now().isoformat(),
        }

    def _save(self) -> None:
        """Save state to storage."""
        self.state["last_updated"] = datetime.now().isoformat()
        validated_path = _validate_file_path(str(self.stats_file))
        with open(validated_path, "w") as f:
            json.dump(self.state, f, indent=2)

    def record_command(self, command: str) -> list:
        """Record a command execution and return any triggered tips.

        Args:
            command: The command that was executed

        Returns:
            List of tip messages to show

        """
        # Update counts
        counts = self.state.get("command_counts", {})
        counts[command] = counts.get(command, 0) + 1
        self.state["command_counts"] = counts
        self.state["total_commands"] = self.state.get("total_commands", 0) + 1

        self._save()

        # Check for triggered tips
        return self.get_pending_tips(trigger=command)

    def record_patterns_learned(self, count: int) -> None:
        """Record patterns learned."""
        self.state["patterns_learned"] = self.state.get("patterns_learned", 0) + count
        self._save()

    def record_api_request(self) -> None:
        """Record an API request."""
        self.state["api_requests"] = self.state.get("api_requests", 0) + 1
        self._save()

    def record_claude_sync(self) -> None:
        """Record a Claude sync."""
        self.state["last_claude_sync"] = datetime.now().isoformat()
        self._save()

    def set_tech_debt_trend(self, trend: str) -> None:
        """Set tech debt trend (increasing/decreasing/stable)."""
        self.state["tech_debt_trend"] = trend
        self._save()

    def get_pending_tips(self, trigger: str | None = None, max_tips: int = 2) -> list:
        """Get pending tips based on current state.

        Args:
            trigger: Command that triggered this check (optional)
            max_tips: Maximum number of tips to return

        Returns:
            List of tip messages

        """
        tips_to_show = []
        shown_tips = set(self.state.get("tips_shown", []))

        for tip_id, tip_config in DISCOVERY_TIPS.items():
            # Skip if already shown
            if tip_id in shown_tips:
                continue

            should_show = False

            # Check trigger-based tips
            if "trigger" in tip_config:
                if trigger == tip_config["trigger"]:
                    count = self.state.get("command_counts", {}).get(trigger, 0)
                    if count >= tip_config.get("min_uses", 1):
                        should_show = True

            # Check condition-based tips
            elif "condition" in tip_config:
                try:
                    condition = tip_config["condition"]
                    if callable(condition) and condition(self.state):
                        should_show = True
                except Exception:
                    pass

            if should_show:
                tips_to_show.append(
                    {
                        "id": tip_id,
                        "tip": tip_config["tip"],
                        "priority": tip_config.get("priority", 3),
                    },
                )

        # Sort by priority and limit - ensure we get an int for sorting
        def get_priority(x: dict) -> int:
            p = x.get("priority", 3)
            return int(p) if isinstance(p, int | float | str) else 3

        tips_to_show.sort(key=get_priority)
        return tips_to_show[:max_tips]

    def mark_shown(self, tip_id: str) -> None:
        """Mark a tip as shown so it won't be repeated."""
        shown = self.state.get("tips_shown", [])
        if tip_id not in shown:
            shown.append(tip_id)
            self.state["tips_shown"] = shown
            self._save()

    def get_stats(self) -> dict:
        """Get current discovery statistics."""
        return {
            "total_commands": self.state.get("total_commands", 0),
            "command_counts": self.state.get("command_counts", {}),
            "patterns_learned": self.state.get("patterns_learned", 0),
            "tips_shown": len(self.state.get("tips_shown", [])),
            "tips_remaining": len(DISCOVERY_TIPS) - len(self.state.get("tips_shown", [])),
            "days_active": self._days_active(),
        }

    def _days_active(self) -> int:
        """Calculate days since first run."""
        first_run = self.state.get("first_run")
        if not first_run:
            return 0
        try:
            first = datetime.fromisoformat(first_run)
            return (datetime.now() - first).days
        except (ValueError, TypeError):
            return 0


# Singleton instance
_engine: DiscoveryEngine | None = None


def get_engine(storage_dir: str = ".empathy") -> DiscoveryEngine:
    """Get or create the global discovery engine."""
    global _engine
    if _engine is None:
        _engine = DiscoveryEngine(storage_dir)
    return _engine


def show_tip_if_available(command: str, quiet: bool = False) -> None:
    """Check for tips after a command and display them.

    Args:
        command: The command that was just executed
        quiet: If True, don't print anything

    """
    engine = get_engine()
    tips = engine.record_command(command)

    if tips and not quiet:
        print()
        for tip_data in tips:
            print(f"  TIP: {tip_data['tip']}")
            engine.mark_shown(tip_data["id"])
        print()


def format_tips_for_cli(tips: list) -> str:
    """Format tips for CLI output."""
    if not tips:
        return ""

    lines = ["\n  TIPS", "  " + "-" * 38]
    for tip_data in tips:
        lines.append(f"  {tip_data['tip']}")
    lines.append("")

    return "\n".join(lines)
