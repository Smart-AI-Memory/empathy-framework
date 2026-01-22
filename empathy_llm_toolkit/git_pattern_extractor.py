"""Git Pattern Extractor

Automatically detects bug fixes from git commits and creates
draft pattern entries for review.

This module integrates with git hooks (post-commit) to capture
fix patterns as they happen.

Usage:
    # As a post-commit hook
    python -m empathy_llm_toolkit.git_pattern_extractor

    # Manual extraction for recent commits
    python -m empathy_llm_toolkit.git_pattern_extractor --commits 5

Author: Empathy Framework Team
Version: 2.1.3
License: Fair Source 0.9
"""

import hashlib
import json
import logging
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class GitPatternExtractor:
    """Extracts bug fix patterns from git commits.

    Analyzes commit messages and diffs to detect common
    fix patterns, then creates draft pattern files.
    """

    def __init__(self, patterns_dir: str = "./patterns"):
        self.patterns_dir = Path(patterns_dir)
        self.debugging_dir = self.patterns_dir / "debugging"

        # Commit message patterns that indicate fixes
        self._fix_message_patterns = [
            (r"\bfix(?:es|ed)?\b", 1.0),  # "fix", "fixes", "fixed"
            (r"\bbug\b", 0.8),  # "bug"
            (r"\bresolve[sd]?\b", 0.9),  # "resolve", "resolved"
            (r"\brepair[sed]?\b", 0.8),  # "repair"
            (r"\bpatch(?:es|ed)?\b", 0.7),  # "patch"
            (r"\bcorrect[sed]?\b", 0.7),  # "correct"
            (r"\bhotfix\b", 1.0),  # "hotfix"
            (r"#\d+", 0.6),  # Issue references
            (r"\bclose[sd]?\s+#\d+", 0.9),  # "closes #123"
        ]

        # Code patterns that indicate specific fix types
        self._code_fix_patterns = {
            "null_reference": {
                "patterns": [
                    r"\?\.",  # Optional chaining added
                    r"\?\?\s*\[",  # Nullish coalescing with array
                    r"\.get\s*\([^,]+,\s*",  # Python .get() with default
                    r"if\s*\(\s*\w+\s*(!=|!==)\s*(null|undefined)",  # Null check
                    r"or\s*\[\]",  # Python or [] fallback
                ],
                "description": "Null/undefined reference fix",
            },
            "async_timing": {
                "patterns": [
                    r"\bawait\s+\w+",  # Added await
                    r"async\s+def\s+",  # Made async
                    r"\.then\s*\([^)]*\)\s*\.\s*catch",  # Added error handling
                ],
                "description": "Async/timing fix",
            },
            "error_handling": {
                "patterns": [
                    r"\btry\s*[:\{]",  # Try block
                    r"\bexcept\s+\w+",  # Python except
                    r"\.catch\s*\(",  # Promise catch
                    r"\bcatch\s*\(",  # Try-catch
                ],
                "description": "Error handling improvement",
            },
            "type_mismatch": {
                "patterns": [
                    r":\s*(str|int|float|bool)",  # Python type hints
                    r"isinstance\s*\(",  # Type check
                    r"typeof\s+\w+\s*===",  # JS typeof
                ],
                "description": "Type mismatch fix",
            },
            "import_error": {
                "patterns": [
                    r"from\s+\w+\s+import",  # Python import
                    r"import\s+\{[^}]+\}\s+from",  # ES6 import
                    r"require\s*\(['\"]",  # CommonJS require
                ],
                "description": "Import/dependency fix",
            },
        }

    def extract_from_recent_commits(self, num_commits: int = 1) -> list[dict[str, Any]]:
        """Extract patterns from recent git commits.

        Args:
            num_commits: Number of recent commits to analyze

        Returns:
            List of detected pattern dicts

        """
        patterns = []

        for i in range(num_commits):
            commit_info = self._get_commit_info(f"HEAD~{i}")
            if not commit_info:
                continue

            # Check if this looks like a fix commit
            fix_score = self._score_fix_commit(commit_info["message"])
            if fix_score < 0.5:
                continue

            # Analyze the diff for this commit
            diff = self._get_commit_diff(f"HEAD~{i + 1}", f"HEAD~{i}")
            detected = self._analyze_diff(diff, commit_info)

            for pattern in detected:
                pattern["fix_score"] = fix_score
                pattern["commit_hash"] = commit_info["hash"]
                pattern["commit_message"] = commit_info["message"]
                patterns.append(pattern)

        return patterns

    def extract_from_staged(self) -> list[dict[str, Any]]:
        """Extract patterns from currently staged changes.

        Returns:
            List of detected pattern dicts

        """
        diff = self._get_staged_diff()
        if not diff:
            return []

        commit_info = {
            "hash": "staged",
            "message": "staged changes",
            "author": self._get_git_config("user.name") or "developer",
            "date": datetime.now().isoformat(),
        }

        return self._analyze_diff(diff, commit_info)

    def save_pattern(self, pattern: dict[str, Any]) -> Path | None:
        """Save a detected pattern as a draft for review.

        Args:
            pattern: Pattern dict from extraction

        Returns:
            Path to saved file, or None if failed

        """
        self.debugging_dir.mkdir(parents=True, exist_ok=True)

        # Generate pattern file
        pattern_data = {
            "bug_id": pattern["pattern_id"],
            "date": datetime.now().isoformat(),
            "file_path": pattern.get("file", "unknown"),
            "error_type": pattern.get("type", "unknown"),
            "error_message": f"From commit: {pattern.get('commit_message', '')[:80]}",
            "root_cause": "",  # To be filled by user
            "fix_applied": pattern.get("description", ""),
            "fix_code": pattern.get("code_sample", ""),
            "status": "investigating",  # Draft status
            "resolved_by": pattern.get("author", "@developer"),
            "auto_detected": True,
            "commit_hash": pattern.get("commit_hash", ""),
            "fix_score": pattern.get("fix_score", 0.0),
        }

        output_file = self.debugging_dir / f"{pattern['pattern_id']}.json"

        try:
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(pattern_data, f, indent=2, default=str)
            return output_file
        except OSError as e:
            logger.error("Failed to save pattern: %s", e)
            return None

    def _get_commit_info(self, ref: str) -> dict[str, str] | None:
        """Get info about a specific commit."""
        try:
            result = subprocess.run(
                ["git", "log", "-1", "--format=%H%n%s%n%an%n%aI", ref],
                check=False,
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode != 0:
                return None

            lines = result.stdout.strip().split("\n")
            if len(lines) < 4:
                return None

            return {
                "hash": lines[0][:8],
                "message": lines[1],
                "author": lines[2],
                "date": lines[3],
            }
        except Exception:  # noqa: BLE001
            # INTENTIONAL: Git commands may fail for various reasons (not a repo, detached HEAD, etc.)
            return None

    def _get_commit_diff(self, ref1: str, ref2: str) -> str:
        """Get diff between two commits."""
        try:
            result = subprocess.run(
                ["git", "diff", ref1, ref2],
                check=False,
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.stdout if result.returncode == 0 else ""
        except Exception:  # noqa: BLE001
            # INTENTIONAL: Git commands may fail for various reasons (not a repo, no commits, etc.)
            return ""

    def _get_staged_diff(self) -> str:
        """Get diff of staged changes."""
        try:
            result = subprocess.run(
                ["git", "diff", "--cached"],
                check=False,
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.stdout if result.returncode == 0 else ""
        except Exception:  # noqa: BLE001
            # INTENTIONAL: Git commands may fail for various reasons (not a repo, nothing staged, etc.)
            return ""

    def _get_git_config(self, key: str) -> str | None:
        """Get a git config value."""
        try:
            result = subprocess.run(
                ["git", "config", key],
                check=False,
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.stdout.strip() if result.returncode == 0 else None
        except Exception:  # noqa: BLE001
            # INTENTIONAL: Git config may fail (not a repo, key not set, etc.)
            return None

    def _score_fix_commit(self, message: str) -> float:
        """Score how likely a commit message indicates a fix."""
        message_lower = message.lower()
        max_score = 0.0

        for pattern, score in self._fix_message_patterns:
            if re.search(pattern, message_lower, re.IGNORECASE):
                max_score = max(max_score, score)

        return max_score

    def _analyze_diff(
        self,
        diff: str,
        commit_info: dict[str, str],
    ) -> list[dict[str, Any]]:
        """Analyze a diff for fix patterns."""
        patterns = []
        current_file = ""
        added_lines: list[str] = []

        for line in diff.split("\n"):
            if line.startswith("diff --git"):
                # Process previous file
                if current_file and added_lines:
                    file_patterns = self._detect_fix_patterns(
                        current_file,
                        added_lines,
                        commit_info,
                    )
                    patterns.extend(file_patterns)

                # Start new file
                match = re.search(r"b/(.+)$", line)
                current_file = match.group(1) if match else ""
                added_lines = []

            elif line.startswith("+") and not line.startswith("+++"):
                added_lines.append(line[1:])

        # Process last file
        if current_file and added_lines:
            file_patterns = self._detect_fix_patterns(current_file, added_lines, commit_info)
            patterns.extend(file_patterns)

        return patterns

    def _detect_fix_patterns(
        self,
        file_path: str,
        added_lines: list[str],
        commit_info: dict[str, str],
    ) -> list[dict[str, Any]]:
        """Detect fix patterns in added lines."""
        detected = []
        added_content = "\n".join(added_lines)

        for fix_type, config in self._code_fix_patterns.items():
            matches = []
            for pattern in config["patterns"]:
                found = re.findall(pattern, added_content)
                if found:
                    matches.extend(found)

            if matches:
                pattern_id = self._generate_pattern_id(file_path, fix_type)
                detected.append(
                    {
                        "pattern_id": pattern_id,
                        "type": fix_type,
                        "file": file_path,
                        "description": config["description"],
                        "code_sample": matches[0] if matches else "",
                        "matches_count": len(matches),
                        "author": commit_info.get("author", "unknown"),
                        "date": commit_info.get("date", datetime.now().isoformat()),
                    },
                )

        return detected

    def _generate_pattern_id(self, file_path: str, pattern_type: str) -> str:
        """Generate unique pattern ID."""
        date_str = datetime.now().strftime("%Y%m%d")
        content = f"{file_path}:{pattern_type}:{datetime.now().isoformat()}"
        hash_suffix = hashlib.md5(content.encode(), usedforsecurity=False).hexdigest()[:8]
        return f"bug_{date_str}_{hash_suffix}"


def main():
    """CLI entry point for git pattern extraction."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Extract bug fix patterns from git commits",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Extract from last commit (post-commit hook)
  python -m empathy_llm_toolkit.git_pattern_extractor

  # Extract from last 5 commits
  python -m empathy_llm_toolkit.git_pattern_extractor --commits 5

  # Extract from staged changes
  python -m empathy_llm_toolkit.git_pattern_extractor --staged

  # Save detected patterns
  python -m empathy_llm_toolkit.git_pattern_extractor --save
        """,
    )

    parser.add_argument("--commits", type=int, default=1, help="Number of commits to analyze")
    parser.add_argument("--staged", action="store_true", help="Analyze staged changes instead")
    parser.add_argument("--save", action="store_true", help="Save detected patterns to files")
    parser.add_argument("--patterns-dir", default="./patterns", help="Patterns directory")
    parser.add_argument("--quiet", action="store_true", help="Suppress output (for hooks)")

    args = parser.parse_args()

    # Configure logging
    log_level = logging.WARNING if args.quiet else logging.INFO
    logging.basicConfig(level=log_level, format="%(levelname)s: %(message)s")

    extractor = GitPatternExtractor(args.patterns_dir)

    # Extract patterns
    if args.staged:
        patterns = extractor.extract_from_staged()
    else:
        patterns = extractor.extract_from_recent_commits(args.commits)

    if not patterns:
        if not args.quiet:
            print("No fix patterns detected.")
        return

    # Display or save patterns
    if not args.quiet:
        print(f"\n{'=' * 50}")
        print(f"Detected {len(patterns)} fix pattern(s)")
        print(f"{'=' * 50}\n")

    for pattern in patterns:
        if not args.quiet:
            print(f"  Pattern: {pattern['pattern_id']}")
            print(f"    Type: {pattern['type']}")
            print(f"    File: {pattern['file']}")
            print(f"    Description: {pattern['description']}")
            if "commit_message" in pattern:
                print(f"    Commit: {pattern['commit_message'][:60]}...")
            print(f"    Confidence: {pattern.get('fix_score', 0):.0%}")
            print()

        if args.save:
            saved_path = extractor.save_pattern(pattern)
            if saved_path and not args.quiet:
                print(f"    ✓ Saved to: {saved_path}")
                print()

    if args.save and not args.quiet:
        print("\nPatterns saved with 'investigating' status.")
        print("Use 'empathy patterns resolve <id>' to complete them.")


if __name__ == "__main__":
    main()
