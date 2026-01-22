"""Bug Prediction Workflow

Analyzes code against learned bug patterns to predict likely issues
before they manifest in production.

Stages:
1. scan (CHEAP) - Scan codebase for code patterns and structures
2. correlate (CAPABLE) - Match against historical bug patterns
3. predict (CAPABLE) - Identify high-risk areas based on correlation
4. recommend (PREMIUM) - Generate actionable fix recommendations

Copyright 2025 Smart-AI-Memory
Licensed under Fair Source License 0.9
"""

import fnmatch
import json
import logging
import re
from pathlib import Path
from typing import Any

import yaml

from .base import BaseWorkflow, ModelTier
from .step_config import WorkflowStepConfig

logger = logging.getLogger(__name__)


def _load_bug_predict_config() -> dict:
    """Load bug_predict configuration from empathy.config.yml.

    Returns:
        Dict with bug_predict settings, or defaults if not found.

    """
    defaults = {
        "risk_threshold": 0.7,
        "exclude_files": [],
        "acceptable_exception_contexts": ["version", "config", "cleanup", "optional"],
    }

    config_paths = [
        Path("empathy.config.yml"),
        Path("empathy.config.yaml"),
        Path(".empathy.yml"),
        Path(".empathy.yaml"),
    ]

    for config_path in config_paths:
        if config_path.exists():
            try:
                with open(config_path) as f:
                    config = yaml.safe_load(f)
                    if config and "bug_predict" in config:
                        bug_config = config["bug_predict"]
                        return {
                            "risk_threshold": bug_config.get(
                                "risk_threshold",
                                defaults["risk_threshold"],
                            ),
                            "exclude_files": bug_config.get(
                                "exclude_files",
                                defaults["exclude_files"],
                            ),
                            "acceptable_exception_contexts": bug_config.get(
                                "acceptable_exception_contexts",
                                defaults["acceptable_exception_contexts"],
                            ),
                        }
            except (yaml.YAMLError, OSError):
                pass

    return defaults


def _should_exclude_file(file_path: str, exclude_patterns: list[str]) -> bool:
    """Check if a file should be excluded based on glob patterns.

    Args:
        file_path: Path to the file
        exclude_patterns: List of glob patterns (e.g., "**/test_*.py")

    Returns:
        True if the file matches any exclusion pattern.

    """
    for pattern in exclude_patterns:
        # Handle ** patterns for recursive matching
        if "**" in pattern:
            # Convert ** glob to fnmatch-compatible pattern
            parts = pattern.split("**")
            if len(parts) == 2:
                prefix, suffix = parts
                # Check if file path contains the pattern structure
                if prefix and not file_path.startswith(prefix.rstrip("/")):
                    continue
                if suffix and fnmatch.fnmatch(file_path, f"*{suffix}"):
                    return True
                if not suffix and fnmatch.fnmatch(file_path, f"*{prefix}*"):
                    return True
        elif fnmatch.fnmatch(file_path, pattern) or fnmatch.fnmatch(
            Path(file_path).name,
            pattern,
        ):
            return True

    return False


def _is_acceptable_broad_exception(
    line: str,
    context_before: list[str],
    context_after: list[str],
    acceptable_contexts: list[str] | None = None,
) -> bool:
    """Check if a broad exception handler is acceptable based on context.

    Acceptable patterns (configurable via acceptable_contexts):
    - version: Version/metadata detection with fallback
    - config: Config loading with default fallback
    - optional: Optional feature detection (imports, hasattr)
    - cleanup: Cleanup/teardown code
    - logging: Logging-only handlers that re-raise

    Args:
        line: The line containing the except clause
        context_before: Lines before the except
        context_after: Lines after the except (the handler body)
        acceptable_contexts: List of context types to accept (from config)

    Returns:
        True if the exception handler is acceptable, False if problematic.

    """
    # Default acceptable contexts if not provided
    if acceptable_contexts is None:
        acceptable_contexts = ["version", "config", "cleanup", "optional"]

    # Join context for pattern matching
    before_text = "\n".join(context_before[-5:]).lower()
    after_text = "\n".join(context_after[:5]).lower()

    # Acceptable: Version/metadata detection
    if "version" in acceptable_contexts:
        if any(kw in before_text for kw in ["get_version", "version", "metadata", "__version__"]):
            if any(kw in after_text for kw in ["return", "dev", "unknown", "0.0.0"]):
                return True

    # Acceptable: Config loading with fallback to defaults
    if "config" in acceptable_contexts:
        if any(kw in before_text for kw in ["config", "settings", "yaml", "json", "load"]):
            if "pass" in after_text or "default" in after_text or "fallback" in after_text:
                return True

    # Acceptable: Optional import/feature detection
    if "optional" in acceptable_contexts:
        if "import" in before_text or "hasattr" in before_text:
            if "pass" in after_text or "none" in after_text or "false" in after_text:
                return True

    # Acceptable: Cleanup with pass (often in __del__ or context managers)
    if "cleanup" in acceptable_contexts:
        if any(kw in before_text for kw in ["__del__", "__exit__", "cleanup", "close", "teardown"]):
            return True

    # Acceptable: Explicit logging then re-raise or return error
    if "logging" in acceptable_contexts:
        if "log" in after_text and ("raise" in after_text or "return" in after_text):
            return True

    # Always accept: Comment explains the broad catch is intentional
    if "# " in after_text and any(
        kw in after_text
        for kw in ["fallback", "ignore", "optional", "best effort", "graceful", "intentional"]
    ):
        return True

    return False


def _has_problematic_exception_handlers(
    content: str,
    file_path: str,
    acceptable_contexts: list[str] | None = None,
) -> bool:
    """Check if file has problematic broad exception handlers.

    Filters out acceptable uses like version detection, config fallbacks,
    and optional feature detection.

    Args:
        content: File content to check
        file_path: Path to the file
        acceptable_contexts: List of acceptable context types from config

    Returns:
        True if problematic exception handlers found, False otherwise.

    """
    if "except:" not in content and "except Exception:" not in content:
        return False

    lines = content.splitlines()
    problematic_count = 0

    for i, line in enumerate(lines):
        stripped = line.strip()

        # Check for broad exception patterns
        if stripped.startswith("except:") or stripped.startswith("except Exception"):
            context_before = lines[max(0, i - 5) : i]
            context_after = lines[i + 1 : min(len(lines), i + 6)]

            if not _is_acceptable_broad_exception(
                stripped,
                context_before,
                context_after,
                acceptable_contexts,
            ):
                problematic_count += 1

    # Only flag if there are problematic handlers
    return problematic_count > 0


def _is_dangerous_eval_usage(content: str, file_path: str) -> bool:
    """Check if file contains dangerous eval/exec usage, filtering false positives.

    Excludes:
    - String literals used for detection (e.g., 'if "eval(" in content')
    - Comments mentioning eval/exec (e.g., '# SECURITY FIX: Use json.loads() instead of eval()')
    - JavaScript's safe regex.exec() method
    - Pattern definitions for security scanners
    - Test fixtures: code written via write_text() or similar for testing
    - Scanner test files that deliberately contain example bad patterns
    - Docstrings documenting security policies (e.g., "No eval() or exec() usage")
    - Security policy documentation in comments

    Returns:
        True if dangerous eval/exec usage is found, False otherwise.

    """
    # Check if file even contains eval or exec
    if "eval(" not in content and "exec(" not in content:
        return False

    # Exclude scanner test files (they deliberately contain example bad patterns)
    scanner_test_patterns = [
        "test_bug_predict",
        "test_scanner",
        "test_security_scan",
    ]
    file_name = file_path.lower()
    if any(pattern in file_name for pattern in scanner_test_patterns):
        return False

    # Check for test fixture patterns - eval/exec inside write_text() or heredoc strings
    # These are test data being written to temp files, not actual dangerous code
    fixture_patterns = [
        r'write_text\s*\(\s*["\'][\s\S]*?(?:eval|exec)\s*\(',  # write_text("...eval(...")
        r'write_text\s*\(\s*"""[\s\S]*?(?:eval|exec)\s*\(',  # write_text("""...eval(...""")
        r"write_text\s*\(\s*'''[\s\S]*?(?:eval|exec)\s*\(",  # write_text('''...eval(...''')
    ]
    for pattern in fixture_patterns:
        if re.search(pattern, content, re.MULTILINE):
            # All eval/exec occurrences might be in fixtures - do deeper check
            # Remove fixture content and see if any eval/exec remains
            content_without_fixtures = re.sub(
                r"write_text\s*\([^)]*\)",
                "",
                content,
                flags=re.DOTALL,
            )
            content_without_fixtures = re.sub(
                r'write_text\s*\("""[\s\S]*?"""\)',
                "",
                content_without_fixtures,
            )
            content_without_fixtures = re.sub(
                r"write_text\s*\('''[\s\S]*?'''\)",
                "",
                content_without_fixtures,
            )
            if "eval(" not in content_without_fixtures and "exec(" not in content_without_fixtures:
                return False

    # For JavaScript/TypeScript files, check for regex.exec() which is safe
    if file_path.endswith((".js", ".ts", ".tsx", ".jsx")):
        # Remove all regex.exec() calls (these are safe)
        content_without_regex_exec = re.sub(r"\.\s*exec\s*\(", ".SAFE_EXEC(", content)
        # If no eval/exec remains, it was all regex.exec()
        if "eval(" not in content_without_regex_exec and "exec(" not in content_without_regex_exec:
            return False

    # Remove docstrings before line-by-line analysis
    # This prevents false positives from documentation that mentions eval/exec
    content_without_docstrings = _remove_docstrings(content)

    # Check each line for real dangerous usage
    lines = content_without_docstrings.splitlines()
    for line in lines:
        # Skip comment lines
        stripped = line.strip()
        if stripped.startswith("#") or stripped.startswith("//") or stripped.startswith("*"):
            continue

        # Skip security policy documentation (e.g., "- No eval() or exec()")
        if _is_security_policy_line(stripped):
            continue

        # Check for eval( or exec( in this line
        if "eval(" not in line and "exec(" not in line:
            continue

        # Skip if it's inside a string literal for detection purposes
        # e.g., 'if "eval(" in content' or "pattern = r'eval\('"
        detection_patterns = [
            r'["\'].*eval\(.*["\']',  # "eval(" or 'eval(' in a string
            r'["\'].*exec\(.*["\']',  # "exec(" or 'exec(' in a string
            r"in\s+\w+",  # Pattern like 'in content'
            r'r["\'].*eval',  # Raw string regex pattern
            r'r["\'].*exec',  # Raw string regex pattern
        ]

        is_detection_code = False
        for pattern in detection_patterns:
            if re.search(pattern, line):
                # Check if it's really detection code
                if " in " in line and (
                    "content" in line or "text" in line or "code" in line or "source" in line
                ):
                    is_detection_code = True
                    break
                # Check if it's a string literal being defined (eval or exec)
                if re.search(r'["\'][^"\']*eval\([^"\']*["\']', line):
                    is_detection_code = True
                    break
                if re.search(r'["\'][^"\']*exec\([^"\']*["\']', line):
                    is_detection_code = True
                    break
                # Check for raw string regex patterns containing eval/exec
                if re.search(r"r['\"][^'\"]*(?:eval|exec)[^'\"]*['\"]", line):
                    is_detection_code = True
                    break

        if is_detection_code:
            continue

        # Skip JavaScript regex.exec() - pattern.exec(text)
        if re.search(r"\w+\.exec\s*\(", line):
            continue

        # This looks like real dangerous usage
        return True

    return False


def _remove_docstrings(content: str) -> str:
    """Remove docstrings from Python content to avoid false positives.

    Docstrings often document security policies (e.g., "No eval() usage")
    which should not trigger the scanner.

    Args:
        content: Python source code

    Returns:
        Content with docstrings replaced by placeholder comments.
    """
    # Remove triple-quoted strings (docstrings)
    # Match """ ... """ and ''' ... ''' including multiline
    content = re.sub(r'"""[\s\S]*?"""', '# [docstring removed]', content)
    content = re.sub(r"'''[\s\S]*?'''", "# [docstring removed]", content)
    return content


def _is_security_policy_line(line: str) -> bool:
    """Check if a line is documenting security policy rather than using eval/exec.

    Args:
        line: Stripped line of code

    Returns:
        True if this appears to be security documentation.
    """
    line_lower = line.lower()

    # Patterns indicating security policy documentation
    policy_patterns = [
        r"no\s+eval",  # "No eval" or "no eval()"
        r"no\s+exec",  # "No exec" or "no exec()"
        r"never\s+use\s+eval",
        r"never\s+use\s+exec",
        r"avoid\s+eval",
        r"avoid\s+exec",
        r"don'?t\s+use\s+eval",
        r"don'?t\s+use\s+exec",
        r"prohibited.*eval",
        r"prohibited.*exec",
        r"security.*eval",
        r"security.*exec",
    ]

    for pattern in policy_patterns:
        if re.search(pattern, line_lower):
            return True

    # Check for list item documentation (e.g., "- No eval() or exec() usage")
    if line.startswith("-") and ("eval" in line_lower or "exec" in line_lower):
        # If it contains "no", "never", "avoid", it's policy documentation
        if any(word in line_lower for word in ["no ", "never", "avoid", "don't", "prohibited"]):
            return True

    return False


# Define step configurations for executor-based execution
BUG_PREDICT_STEPS = {
    "recommend": WorkflowStepConfig(
        name="recommend",
        task_type="final_review",  # Premium tier task
        tier_hint="premium",
        description="Generate bug prevention recommendations",
        max_tokens=2000,
    ),
}


class BugPredictionWorkflow(BaseWorkflow):
    """Predict bugs by correlating current code with learned patterns.

    Uses pattern library integration to identify code that matches
    historical bug patterns and generates preventive recommendations.
    """

    name = "bug-predict"
    description = "Predict bugs by analyzing code against learned patterns"
    stages = ["scan", "correlate", "predict", "recommend"]
    tier_map = {
        "scan": ModelTier.CHEAP,
        "correlate": ModelTier.CAPABLE,
        "predict": ModelTier.CAPABLE,
        "recommend": ModelTier.PREMIUM,
    }

    def __init__(
        self,
        risk_threshold: float | None = None,
        patterns_dir: str = "./patterns",
        **kwargs: Any,
    ):
        """Initialize bug prediction workflow.

        Args:
            risk_threshold: Minimum risk score to trigger premium recommendations
                           (defaults to config value or 0.7)
            patterns_dir: Directory containing learned patterns
            **kwargs: Additional arguments passed to BaseWorkflow

        """
        super().__init__(**kwargs)

        # Load bug_predict config from empathy.config.yml
        self._bug_predict_config = _load_bug_predict_config()

        # Use provided risk_threshold or fall back to config
        self.risk_threshold = (
            risk_threshold
            if risk_threshold is not None
            else self._bug_predict_config["risk_threshold"]
        )
        self.patterns_dir = patterns_dir
        self._risk_score: float = 0.0
        self._bug_patterns: list[dict] = []
        self._load_patterns()

    def _load_patterns(self) -> None:
        """Load bug patterns from the pattern library."""
        debugging_file = Path(self.patterns_dir) / "debugging.json"
        if debugging_file.exists():
            try:
                with open(debugging_file) as f:
                    data = json.load(f)
                    self._bug_patterns = data.get("patterns", [])
            except (json.JSONDecodeError, OSError):
                self._bug_patterns = []

    def should_skip_stage(self, stage_name: str, input_data: Any) -> tuple[bool, str | None]:
        """Conditionally downgrade recommend stage based on risk score.

        Args:
            stage_name: Name of the stage to check
            input_data: Current workflow data

        Returns:
            Tuple of (should_skip, reason)

        """
        if stage_name == "recommend":
            if self._risk_score < self.risk_threshold:
                # Downgrade to CAPABLE instead of skipping
                self.tier_map["recommend"] = ModelTier.CAPABLE
                return False, None
        return False, None

    async def run_stage(
        self,
        stage_name: str,
        tier: ModelTier,
        input_data: Any,
    ) -> tuple[Any, int, int]:
        """Route to specific stage implementation.

        Args:
            stage_name: Name of the stage to run
            tier: Model tier to use
            input_data: Input data for the stage

        Returns:
            Tuple of (output_data, input_tokens, output_tokens)

        """
        if stage_name == "scan":
            return await self._scan(input_data, tier)
        if stage_name == "correlate":
            return await self._correlate(input_data, tier)
        if stage_name == "predict":
            return await self._predict(input_data, tier)
        if stage_name == "recommend":
            return await self._recommend(input_data, tier)
        raise ValueError(f"Unknown stage: {stage_name}")

    async def _scan(self, input_data: dict, tier: ModelTier) -> tuple[dict, int, int]:
        """Scan codebase for code patterns and structures.

        In production, this would analyze source files for patterns
        that historically correlate with bugs.
        """
        target_path = input_data.get("path", ".")
        file_types = input_data.get("file_types", [".py", ".ts", ".tsx", ".js"])

        # Simulate scanning for code patterns
        scanned_files: list[dict] = []
        patterns_found: list[dict] = []

        # Directories to exclude from scanning (dependencies, build artifacts, etc.)
        exclude_dirs = [
            ".git",
            "node_modules",
            ".venv",
            "venv",
            "env",
            "__pycache__",
            "site-packages",
            "dist",
            "build",
            ".tox",
            ".nox",
            ".eggs",
            "*.egg-info",
        ]

        # Get config options
        config_exclude_patterns = self._bug_predict_config.get("exclude_files", [])
        acceptable_contexts = self._bug_predict_config.get("acceptable_exception_contexts", None)

        # Walk directory and collect file info
        target = Path(target_path)
        if target.exists():
            for ext in file_types:
                for file_path in target.rglob(f"*{ext}"):
                    # Skip excluded directories
                    path_str = str(file_path)
                    if any(excl in path_str for excl in exclude_dirs):
                        continue

                    # Skip files matching config exclude patterns
                    if _should_exclude_file(path_str, config_exclude_patterns):
                        continue

                    try:
                        content = file_path.read_text(errors="ignore")
                        scanned_files.append(
                            {
                                "path": str(file_path),
                                "lines": len(content.splitlines()),
                                "size": len(content),
                            },
                        )

                        # Look for common bug-prone patterns
                        # Use smart detection with configurable acceptable contexts
                        if _has_problematic_exception_handlers(
                            content,
                            str(file_path),
                            acceptable_contexts,
                        ):
                            patterns_found.append(
                                {
                                    "file": str(file_path),
                                    "pattern": "broad_exception",
                                    "severity": "medium",
                                },
                            )
                        if "# TODO" in content or "# FIXME" in content:
                            patterns_found.append(
                                {
                                    "file": str(file_path),
                                    "pattern": "incomplete_code",
                                    "severity": "low",
                                },
                            )
                        # Use smart detection to filter false positives
                        if _is_dangerous_eval_usage(content, str(file_path)):
                            patterns_found.append(
                                {
                                    "file": str(file_path),
                                    "pattern": "dangerous_eval",
                                    "severity": "high",
                                },
                            )
                    except OSError:
                        continue

        input_tokens = len(str(input_data)) // 4
        output_tokens = len(str(scanned_files)) // 4 + len(str(patterns_found)) // 4

        return (
            {
                "scanned_files": scanned_files[:100],  # Limit for efficiency
                "patterns_found": patterns_found,
                "file_count": len(scanned_files),
                "pattern_count": len(patterns_found),
                **input_data,
            },
            input_tokens,
            output_tokens,
        )

    async def _correlate(self, input_data: dict, tier: ModelTier) -> tuple[dict, int, int]:
        """Match current code patterns against historical bug patterns.

        Correlates findings from scan stage with patterns stored in
        the debugging.json pattern library.
        """
        patterns_found = input_data.get("patterns_found", [])
        correlations: list[dict] = []

        # Match against known bug patterns
        for pattern in patterns_found:
            pattern_type = pattern.get("pattern", "")

            # Check against historical patterns
            for bug_pattern in self._bug_patterns:
                bug_type = bug_pattern.get("bug_type", "")
                if self._patterns_correlate(pattern_type, bug_type):
                    correlations.append(
                        {
                            "current_pattern": pattern,
                            "historical_bug": {
                                "type": bug_type,
                                "root_cause": bug_pattern.get("root_cause", ""),
                                "fix": bug_pattern.get("fix", ""),
                            },
                            "confidence": 0.75,
                        },
                    )

        # Add correlations for patterns without direct matches
        for pattern in patterns_found:
            if not any(c["current_pattern"] == pattern for c in correlations):
                correlations.append(
                    {
                        "current_pattern": pattern,
                        "historical_bug": None,
                        "confidence": 0.3,
                    },
                )

        input_tokens = len(str(input_data)) // 4
        output_tokens = len(str(correlations)) // 4

        return (
            {
                "correlations": correlations,
                "correlation_count": len(correlations),
                "high_confidence_count": len([c for c in correlations if c["confidence"] > 0.6]),
                **input_data,
            },
            input_tokens,
            output_tokens,
        )

    def _patterns_correlate(self, current: str, historical: str) -> bool:
        """Check if current pattern correlates with historical bug type."""
        correlation_map = {
            "broad_exception": ["null_reference", "type_mismatch", "unknown"],
            "incomplete_code": ["async_timing", "null_reference"],
            "dangerous_eval": ["import_error", "type_mismatch"],
        }
        return historical in correlation_map.get(current, [])

    async def _predict(self, input_data: dict, tier: ModelTier) -> tuple[dict, int, int]:
        """Identify high-risk areas based on correlation scores.

        Calculates risk scores for each file and identifies
        the most likely locations for bugs to occur.
        """
        correlations = input_data.get("correlations", [])
        patterns_found = input_data.get("patterns_found", [])

        # Calculate file risk scores
        file_risks: dict[str, float] = {}
        for corr in correlations:
            file_path = corr["current_pattern"].get("file", "")
            confidence = corr.get("confidence", 0.3)
            severity_weight = {
                "high": 1.0,
                "medium": 0.6,
                "low": 0.3,
            }.get(corr["current_pattern"].get("severity", "low"), 0.3)

            risk = confidence * severity_weight
            file_risks[file_path] = file_risks.get(file_path, 0) + risk

        # Normalize and sort
        max_risk = max(file_risks.values()) if file_risks else 1.0
        predictions: list[dict] = [
            {
                "file": f,
                "risk_score": round(r / max_risk, 2),
                "patterns": [p for p in patterns_found if p.get("file") == f],
            }
            for f, r in sorted(file_risks.items(), key=lambda x: -x[1])
        ]

        # Calculate overall risk score
        self._risk_score = (
            sum(float(p["risk_score"]) for p in predictions[:5]) / 5
            if len(predictions) >= 5
            else sum(float(p["risk_score"]) for p in predictions) / max(len(predictions), 1)
        )

        input_tokens = len(str(input_data)) // 4
        output_tokens = len(str(predictions)) // 4

        return (
            {
                "predictions": predictions[:20],  # Top 20 risky files
                "overall_risk_score": round(self._risk_score, 2),
                "high_risk_files": len([p for p in predictions if float(p["risk_score"]) > 0.7]),
                **input_data,
            },
            input_tokens,
            output_tokens,
        )

    async def _recommend(self, input_data: dict, tier: ModelTier) -> tuple[dict, int, int]:
        """Generate actionable fix recommendations using LLM.

        Uses premium tier (or capable if downgraded) to generate
        specific recommendations for addressing predicted bugs.

        Supports XML-enhanced prompts when enabled in workflow config.
        """
        predictions = input_data.get("predictions", [])
        target = input_data.get("target", "")

        # Build context for LLM
        top_risks = predictions[:10]
        issues_summary = []
        for pred in top_risks:
            file_path = pred.get("file", "")
            patterns = pred.get("patterns", [])
            for p in patterns:
                issues_summary.append(
                    f"- {file_path}: {p.get('pattern')} (severity: {p.get('severity')})",
                )

        # Build input payload
        input_payload = f"""Target: {target or "codebase"}

Issues Found:
{chr(10).join(issues_summary) if issues_summary else "No specific issues identified"}

Historical Bug Patterns:
{json.dumps(self._bug_patterns[:5], indent=2) if self._bug_patterns else "None"}

Risk Score: {input_data.get("overall_risk_score", 0):.2f}"""

        # Check if XML prompts are enabled
        if self._is_xml_enabled():
            # Use XML-enhanced prompt
            user_message = self._render_xml_prompt(
                role="senior software engineer specializing in bug prevention",
                goal="Analyze bug-prone patterns and generate actionable recommendations",
                instructions=[
                    "Explain why each pattern is risky",
                    "Provide specific fixes with code examples",
                    "Suggest preventive measures",
                    "Reference historical patterns when relevant",
                    "Prioritize by severity and risk score",
                ],
                constraints=[
                    "Be specific and actionable",
                    "Include code examples where helpful",
                    "Group recommendations by priority",
                ],
                input_type="bug_patterns",
                input_payload=input_payload,
                extra={
                    "risk_score": input_data.get("overall_risk_score", 0),
                    "pattern_count": len(issues_summary),
                },
            )
            system = None  # XML prompt includes all context
        else:
            # Use legacy plain text prompts
            system = """You are a senior software engineer specializing in bug prevention.
Analyze the identified code patterns and generate actionable recommendations.

For each issue:
1. Explain why this pattern is risky
2. Provide a specific fix with code example if applicable
3. Suggest preventive measures

Be specific and actionable. Prioritize by severity."""

            user_message = f"""Analyze these bug-prone patterns and provide recommendations:

{input_payload}

Provide detailed recommendations for preventing bugs."""

        # Try executor-based execution first (Phase 3 pattern)
        if self._executor is not None or self._api_key:
            try:
                step = BUG_PREDICT_STEPS["recommend"]
                response, input_tokens, output_tokens, cost = await self.run_step_with_executor(
                    step=step,
                    prompt=user_message,
                    system=system,
                )
            except Exception as e:
                # Graceful fallback to legacy _call_llm if executor fails
                logger.warning(f"Executor failed, falling back to legacy LLM call: {e}")
                response, input_tokens, output_tokens = await self._call_llm(
                    tier,
                    system or "",
                    user_message,
                    max_tokens=2000,
                )
        else:
            # Legacy path for backward compatibility
            response, input_tokens, output_tokens = await self._call_llm(
                tier,
                system or "",
                user_message,
                max_tokens=2000,
            )

        # Parse XML response if enforcement is enabled
        parsed_data = self._parse_xml_response(response)

        result = {
            "recommendations": response,
            "recommendation_count": len(top_risks),
            "model_tier_used": tier.value,
            "overall_risk_score": input_data.get("overall_risk_score", 0),
        }

        # Merge parsed XML data if available
        if parsed_data.get("xml_parsed"):
            result.update(
                {
                    "xml_parsed": True,
                    "summary": parsed_data.get("summary"),
                    "findings": parsed_data.get("findings", []),
                    "checklist": parsed_data.get("checklist", []),
                },
            )

        # Add formatted report for human readability
        result["formatted_report"] = format_bug_predict_report(result, input_data)

        return (result, input_tokens, output_tokens)


def format_bug_predict_report(result: dict, input_data: dict) -> str:
    """Format bug prediction output as a human-readable report.

    Args:
        result: The recommend stage result
        input_data: Input data from previous stages

    Returns:
        Formatted report string

    """
    lines = []

    # Header with risk assessment
    risk_score = result.get("overall_risk_score", 0)
    if risk_score >= 0.8:
        risk_icon = "🔴"
        risk_text = "HIGH RISK"
    elif risk_score >= 0.5:
        risk_icon = "🟠"
        risk_text = "MODERATE RISK"
    elif risk_score >= 0.3:
        risk_icon = "🟡"
        risk_text = "LOW RISK"
    else:
        risk_icon = "🟢"
        risk_text = "MINIMAL RISK"

    lines.append("=" * 60)
    lines.append("BUG PREDICTION REPORT")
    lines.append("=" * 60)
    lines.append("")
    lines.append(f"Overall Risk: {risk_icon} {risk_text} ({risk_score:.0%})")
    lines.append("")

    # Scan summary
    file_count = input_data.get("file_count", 0)
    pattern_count = input_data.get("pattern_count", 0)
    lines.append("-" * 60)
    lines.append("SCAN SUMMARY")
    lines.append("-" * 60)
    lines.append(f"Files Scanned: {file_count}")
    lines.append(f"Patterns Found: {pattern_count}")
    lines.append("")

    # Patterns found by severity
    patterns = input_data.get("patterns_found", [])
    if patterns:
        high = [p for p in patterns if p.get("severity") == "high"]
        medium = [p for p in patterns if p.get("severity") == "medium"]
        low = [p for p in patterns if p.get("severity") == "low"]

        lines.append("Pattern Breakdown:")
        lines.append(f"  🔴 High: {len(high)}")
        lines.append(f"  🟡 Medium: {len(medium)}")
        lines.append(f"  🟢 Low: {len(low)}")
        lines.append("")

    # High risk predictions
    predictions = input_data.get("predictions", [])
    high_risk = [p for p in predictions if float(p.get("risk_score", 0)) > 0.7]
    if high_risk:
        lines.append("-" * 60)
        lines.append("HIGH RISK FILES")
        lines.append("-" * 60)
        for pred in high_risk[:10]:
            file_path = pred.get("file", "unknown")
            score = pred.get("risk_score", 0)
            file_patterns = pred.get("patterns", [])
            lines.append(f"  🔴 {file_path} (risk: {score:.0%})")
            for p in file_patterns[:3]:
                lines.append(
                    f"      - {p.get('pattern', 'unknown')}: {p.get('severity', 'unknown')}",
                )
        lines.append("")

    # Correlations with historical bugs
    correlations = input_data.get("correlations", [])
    high_conf = [
        c for c in correlations if c.get("confidence", 0) > 0.6 and c.get("historical_bug")
    ]
    if high_conf:
        lines.append("-" * 60)
        lines.append("HISTORICAL BUG CORRELATIONS")
        lines.append("-" * 60)
        for corr in high_conf[:5]:
            current = corr.get("current_pattern", {})
            historical = corr.get("historical_bug", {})
            confidence = corr.get("confidence", 0)
            lines.append(
                f"  ⚠️ {current.get('pattern', 'unknown')} correlates with {historical.get('type', 'unknown')}",
            )
            lines.append(f"      Confidence: {confidence:.0%}")
            if historical.get("root_cause"):
                lines.append(f"      Root cause: {historical.get('root_cause')[:80]}")
        lines.append("")

    # Recommendations
    recommendations = result.get("recommendations", "")
    if recommendations:
        lines.append("-" * 60)
        lines.append("RECOMMENDATIONS")
        lines.append("-" * 60)
        lines.append(recommendations)
        lines.append("")

    # Footer
    lines.append("=" * 60)
    model_tier = result.get("model_tier_used", "unknown")
    lines.append(f"Analysis completed using {model_tier} tier model")
    lines.append("=" * 60)

    return "\n".join(lines)


def main():
    """CLI entry point for bug prediction workflow."""
    import asyncio

    async def run():
        workflow = BugPredictionWorkflow()
        result = await workflow.execute(path=".", file_types=[".py"])

        print("\nBug Prediction Results")
        print("=" * 50)
        print(f"Provider: {result.provider}")
        print(f"Success: {result.success}")
        print(f"Risk Score: {result.final_output.get('overall_risk_score', 0)}")
        print(f"Recommendations: {result.final_output.get('recommendation_count', 0)}")
        print("\nCost Report:")
        print(f"  Total Cost: ${result.cost_report.total_cost:.4f}")
        savings = result.cost_report.savings
        pct = result.cost_report.savings_percent
        print(f"  Savings: ${savings:.4f} ({pct:.1f}%)")

    asyncio.run(run())


if __name__ == "__main__":
    main()
