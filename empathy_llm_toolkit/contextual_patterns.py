"""Contextual Pattern Injection

Filters and injects only relevant patterns based on current context.
Instead of loading all patterns, this module selects patterns that
are most likely to be useful for the current task.

Usage:
    from empathy_llm_toolkit.contextual_patterns import ContextualPatternInjector

    injector = ContextualPatternInjector("./patterns")

    # Get relevant patterns for a Python file with an async error
    relevant = injector.get_relevant_patterns(
        file_path="src/api.py",
        error_type="async_timing",
        max_patterns=5
    )

Author: Empathy Framework Team
Version: 2.1.3
License: Fair Source 0.9
"""

import json
import logging
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class ContextualPatternInjector:
    """Injects only relevant patterns based on context.

    Reduces cognitive load by filtering patterns to those
    most likely to help with the current task.
    """

    def __init__(self, patterns_dir: str = "./patterns"):
        self.patterns_dir = Path(patterns_dir)
        self._debugging_dirs = ["debugging", "debugging_demo", "repo_test/debugging"]
        self._security_dirs = ["security", "security_demo", "repo_test/security"]
        self._cache: dict[str, list[dict]] = {}

    def get_relevant_patterns(
        self,
        file_path: str | None = None,
        error_type: str | None = None,
        error_message: str | None = None,
        max_patterns: int = 5,
        include_security: bool = True,
    ) -> str:
        """Get relevant patterns formatted as markdown.

        Args:
            file_path: Current file being worked on
            error_type: Type of error (null_reference, async_timing, etc.)
            error_message: Error message text
            max_patterns: Maximum patterns to include
            include_security: Whether to include security decisions

        Returns:
            Markdown string with relevant patterns

        """
        all_bugs = self._load_all_bugs()
        all_security = self._load_all_security() if include_security else []

        # Score and filter patterns
        scored_bugs = self._score_bugs(all_bugs, file_path, error_type, error_message)
        top_bugs = scored_bugs[:max_patterns]

        # Filter security decisions by file extension
        relevant_security = self._filter_security(all_security, file_path)

        return self._format_markdown(top_bugs, relevant_security[:3])

    def get_patterns_for_review(
        self,
        files: list[str],
        max_per_file: int = 3,
    ) -> dict[str, list[dict]]:
        """Get relevant patterns for code review of multiple files.

        Args:
            files: List of file paths being reviewed
            max_per_file: Maximum patterns per file

        Returns:
            Dict mapping file paths to relevant patterns

        """
        all_bugs = self._load_all_bugs()
        result = {}

        for file_path in files:
            file_ext = Path(file_path).suffix
            relevant = [
                bug
                for bug in all_bugs
                if self._file_type_matches(bug.get("file_path", ""), file_ext)
                and bug.get("status") == "resolved"
            ]
            result[file_path] = relevant[:max_per_file]

        return result

    def get_patterns_from_git_changes(self, max_patterns: int = 5) -> str:
        """Get relevant patterns based on recently changed files.

        Returns:
            Markdown with patterns relevant to git changes

        """
        changed_files = self._get_git_changed_files()
        if not changed_files:
            return "No recent git changes detected.\n"

        # Collect file types
        extensions = set()
        for f in changed_files:
            ext = Path(f).suffix
            if ext:
                extensions.add(ext)

        all_bugs = self._load_all_bugs()

        # Filter by file types in changes
        relevant = []
        for bug in all_bugs:
            bug_ext = Path(bug.get("file_path", "")).suffix
            if bug_ext in extensions and bug.get("status") == "resolved":
                relevant.append(bug)

        return self._format_markdown(relevant[:max_patterns], [])

    def _load_all_bugs(self) -> list[dict[str, Any]]:
        """Load all bug patterns from storage."""
        if "bugs" in self._cache:
            return self._cache["bugs"]

        bugs = []
        for debug_dir in self._debugging_dirs:
            dir_path = self.patterns_dir / debug_dir
            if not dir_path.exists():
                continue

            for json_file in dir_path.glob("bug_*.json"):
                try:
                    with open(json_file, encoding="utf-8") as f:
                        bug = json.load(f)
                        bug["_source"] = str(json_file)
                        bugs.append(bug)
                except (json.JSONDecodeError, OSError):
                    continue

        self._cache["bugs"] = bugs
        return bugs

    def _load_all_security(self) -> list[dict[str, Any]]:
        """Load all security decisions from storage."""
        if "security" in self._cache:
            return self._cache["security"]

        decisions = []
        for sec_dir in self._security_dirs:
            decisions_file = self.patterns_dir / sec_dir / "team_decisions.json"
            if not decisions_file.exists():
                continue

            try:
                with open(decisions_file, encoding="utf-8") as f:
                    data = json.load(f)
                    decisions.extend(data.get("decisions", []))
            except (json.JSONDecodeError, OSError):
                continue

        self._cache["security"] = decisions
        return decisions

    def _score_bugs(
        self,
        bugs: list[dict],
        file_path: str | None,
        error_type: str | None,
        error_message: str | None,
    ) -> list[dict]:
        """Score bugs by relevance to current context."""
        scored = []

        for bug in bugs:
            score = 0.0

            # Resolved bugs are more valuable
            if bug.get("status") == "resolved":
                score += 0.3

            # Error type match is strongest signal
            if error_type and bug.get("error_type") == error_type:
                score += 0.5

            # File extension match
            if file_path:
                current_ext = Path(file_path).suffix
                bug_ext = Path(bug.get("file_path", "")).suffix
                if current_ext == bug_ext:
                    score += 0.2

            # Error message similarity (simple keyword match)
            if error_message:
                bug_msg = bug.get("error_message", "").lower()
                error_lower = error_message.lower()
                common_words = set(bug_msg.split()) & set(error_lower.split())
                if common_words:
                    score += min(len(common_words) * 0.05, 0.2)

            # Recent bugs slightly preferred
            try:
                bug_date = datetime.fromisoformat(bug.get("date", "").replace("Z", "+00:00"))
                days_old = (datetime.now(bug_date.tzinfo) - bug_date).days
                if days_old < 30:
                    score += 0.1
            except (ValueError, TypeError):
                pass

            bug["_relevance_score"] = score
            scored.append(bug)

        # Sort by relevance
        return sorted(scored, key=lambda b: b.get("_relevance_score", 0), reverse=True)

    def _filter_security(
        self,
        decisions: list[dict],
        file_path: str | None,
    ) -> list[dict]:
        """Filter security decisions relevant to current file."""
        if not file_path:
            return decisions[:3]  # Return top 3 general

        # Map file extensions to security concern areas
        ext_security_map = {
            ".py": ["sql_injection", "command_injection", "path_traversal"],
            ".js": ["xss", "insecure_random"],
            ".ts": ["xss", "insecure_random"],
            ".tsx": ["xss"],
            ".sql": ["sql_injection"],
        }

        current_ext = Path(file_path).suffix
        relevant_types = ext_security_map.get(current_ext, [])

        filtered = [d for d in decisions if d.get("finding_hash", "") in relevant_types]

        return filtered or decisions[:2]  # Fallback to top 2

    def _file_type_matches(self, bug_path: str, target_ext: str) -> bool:
        """Check if bug's file type matches target extension."""
        return Path(bug_path).suffix == target_ext

    def _get_git_changed_files(self) -> list[str]:
        """Get list of recently changed files from git."""
        try:
            result = subprocess.run(
                ["git", "diff", "--name-only", "HEAD~5", "HEAD"],
                check=False,
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                return [f.strip() for f in result.stdout.strip().split("\n") if f.strip()]
        except subprocess.SubprocessError as e:
            logger.debug(f"Git command failed: {e}")
        except Exception:  # noqa: BLE001
            # INTENTIONAL: Git availability detection - don't crash on git errors
            logger.debug("Could not get git changed files (expected in non-git directories)")
        return []

    def _format_markdown(
        self,
        bugs: list[dict],
        security: list[dict],
    ) -> str:
        """Format patterns as concise markdown."""
        lines = [
            "# Relevant Patterns",
            "",
        ]

        if bugs:
            lines.append("## Bug Patterns")
            lines.append("")
            for bug in bugs:
                status = bug.get("status", "unknown")
                icon = "✓" if status == "resolved" else "?"
                lines.append(f"- **{bug.get('bug_id', 'unknown')}** [{icon}]")
                lines.append(f"  - Type: {bug.get('error_type', 'unknown')}")
                if bug.get("root_cause"):
                    lines.append(f"  - Cause: {bug.get('root_cause')}")
                if bug.get("fix_applied"):
                    lines.append(f"  - Fix: {bug.get('fix_applied')}")
                if bug.get("fix_code"):
                    lines.append(f"  - Code: `{bug.get('fix_code')}`")
                lines.append("")
        else:
            lines.append("*No matching bug patterns.*")
            lines.append("")

        if security:
            lines.append("## Security Decisions")
            lines.append("")
            for decision in security:
                lines.append(
                    f"- **{decision.get('finding_hash', '?')}**: {decision.get('decision', '?')}",
                )
                lines.append(f"  - Reason: {decision.get('reason', 'N/A')}")
                lines.append("")

        return "\n".join(lines)

    def clear_cache(self) -> None:
        """Clear the pattern cache."""
        self._cache.clear()


def main():
    """CLI entry point for contextual patterns."""
    import argparse

    parser = argparse.ArgumentParser(description="Get contextually relevant patterns")
    parser.add_argument("--file", help="Current file path")
    parser.add_argument("--error-type", help="Error type (null_reference, async_timing, etc.)")
    parser.add_argument("--error-message", help="Error message text")
    parser.add_argument("--max", type=int, default=5, help="Max patterns to show")
    parser.add_argument("--git", action="store_true", help="Use git changes for context")
    parser.add_argument("--patterns-dir", default="./patterns", help="Patterns directory")

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    injector = ContextualPatternInjector(args.patterns_dir)

    if args.git:
        print(injector.get_patterns_from_git_changes(args.max))
    else:
        print(
            injector.get_relevant_patterns(
                file_path=args.file,
                error_type=args.error_type,
                error_message=args.error_message,
                max_patterns=args.max,
            ),
        )


if __name__ == "__main__":
    main()
