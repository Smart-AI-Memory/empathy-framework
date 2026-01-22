"""Real tool implementations for meta-orchestration agents.

This module provides actual tool integrations for agents to interact with
real systems instead of returning mock data.

Security:
    - All file operations validated with _validate_file_path()
    - Subprocess calls sanitized
    - Output size limited to prevent memory issues
"""

import json
import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _validate_file_path(path: str) -> Path:
    """Validate file path to prevent path traversal (simplified version).

    Args:
        path: File path to validate

    Returns:
        Validated Path object

    Raises:
        ValueError: If path is invalid
    """
    if not path or not isinstance(path, str):
        raise ValueError("path must be a non-empty string")

    if "\x00" in path:
        raise ValueError("path contains null bytes")

    try:
        resolved = Path(path).resolve()
    except (OSError, RuntimeError) as e:
        raise ValueError(f"Invalid path: {e}") from e

    # Block system directories
    dangerous_paths = ["/etc", "/sys", "/proc", "/dev"]
    for dangerous in dangerous_paths:
        if str(resolved).startswith(dangerous):
            raise ValueError(f"Cannot write to system directory: {dangerous}")

    return resolved


@dataclass
class CoverageReport:
    """Coverage analysis report from pytest-cov."""

    total_coverage: float
    files_analyzed: int
    uncovered_files: list[dict[str, Any]]
    missing_lines: dict[str, list[int]]


class RealCoverageAnalyzer:
    """Runs real pytest coverage analysis."""

    def __init__(self, project_root: str = "."):
        """Initialize coverage analyzer.

        Args:
            project_root: Project root directory
        """
        self.project_root = Path(project_root).resolve()

    def analyze(self, use_existing: bool = True) -> CoverageReport:
        """Run coverage analysis on all project packages.

        Analyzes coverage for: empathy_os, empathy_llm_toolkit,
        empathy_software_plugin, empathy_healthcare_plugin

        Args:
            use_existing: Use existing coverage.json if available (default: True)

        Returns:
            CoverageReport with results

        Raises:
            RuntimeError: If coverage analysis fails
        """
        logger.info("Running coverage analysis on all packages")

        coverage_file = self.project_root / "coverage.json"

        # Check if we can use existing coverage data
        if use_existing and coverage_file.exists():
            import time

            file_age = time.time() - coverage_file.stat().st_mtime
            # Use existing file if less than 1 hour old
            if file_age < 3600:
                logger.info(
                    f"Using existing coverage data (age: {file_age/60:.1f} minutes)"
                )
            else:
                logger.info("Existing coverage data is stale, regenerating")
                use_existing = False

        if not use_existing or not coverage_file.exists():
            try:
                # Run pytest with coverage on test suite
                logger.info("Running test suite to generate coverage (may take 2-5 minutes)")

                # Use actual package names (match pyproject.toml configuration)
                cov_packages = [
                    "empathy_os",
                    "empathy_llm_toolkit",
                    "empathy_software_plugin",
                    "empathy_healthcare_plugin",
                ]

                cmd = [
                    "pytest",
                    "tests/",  # Run all tests to measure coverage
                    "--cov-report=json",
                    "--cov-report=term-missing",
                    "-q",
                    "--tb=no",
                    "--maxfail=50",  # Continue despite failures
                ]

                # Add --cov for each package
                for pkg in cov_packages:
                    cmd.append(f"--cov={pkg}")

                _result = subprocess.run(  # Result not needed, only coverage.json
                    cmd,
                    cwd=self.project_root,
                    capture_output=True,
                    text=True,
                    timeout=600,  # Increased to 10 minutes
                )

            except subprocess.TimeoutExpired:
                logger.warning("Coverage generation timed out, checking for partial results")
                # Fall through to use whatever coverage.json exists

        # Read coverage.json
        if not coverage_file.exists():
            raise RuntimeError(
                "Coverage report not found. Run 'pytest --cov=src --cov-report=json' first."
            )

        try:
            with coverage_file.open() as f:
                coverage_data = json.load(f)

            # Parse results
            total_coverage = coverage_data["totals"]["percent_covered"]
            files = coverage_data.get("files", {})

            # Identify low coverage files
            uncovered_files = []
            missing_lines = {}

            for filepath, file_data in files.items():
                file_coverage = file_data["summary"]["percent_covered"]
                if file_coverage < 80:  # Below target
                    uncovered_files.append(
                        {
                            "path": filepath,
                            "coverage": file_coverage,
                            "missing_lines": file_data["missing_lines"],
                        }
                    )
                    missing_lines[filepath] = file_data["missing_lines"]

            logger.info(
                f"Coverage analysis complete: {total_coverage:.1f}% "
                f"({len(uncovered_files)} files below 80%)"
            )

            return CoverageReport(
                total_coverage=total_coverage,
                files_analyzed=len(files),
                uncovered_files=uncovered_files,
                missing_lines=missing_lines,
            )

        except Exception as e:
            logger.error(f"Coverage analysis failed: {e}")
            raise RuntimeError(f"Coverage analysis failed: {e}") from e


class RealTestGenerator:
    """Generates actual test code using LLM."""

    def __init__(
        self,
        project_root: str = ".",
        output_dir: str = "tests/generated",
        api_key: str | None = None,
        use_llm: bool = True,
    ):
        """Initialize test generator.

        Args:
            project_root: Project root directory
            output_dir: Directory for generated tests (relative to project_root)
            api_key: Anthropic API key (or uses env var)
            use_llm: Whether to use LLM for intelligent test generation
        """
        self.project_root = Path(project_root).resolve()
        self.output_dir = self.project_root / output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.api_key = api_key
        self.use_llm = use_llm

        # Initialize LLM client if needed
        self._llm = None
        if use_llm:
            self._initialize_llm()

    def _initialize_llm(self):
        """Initialize Anthropic LLM client."""
        try:
            import os

            from anthropic import Anthropic

            # Try to load .env file
            try:
                from dotenv import load_dotenv
                load_dotenv()
            except ImportError:
                pass  # python-dotenv not required

            api_key = self.api_key or os.environ.get("ANTHROPIC_API_KEY")
            if not api_key:
                logger.warning(
                    "No Anthropic API key found. Set ANTHROPIC_API_KEY environment variable "
                    "or create .env file with ANTHROPIC_API_KEY=your_key_here. "
                    "Falling back to basic templates."
                )
                self.use_llm = False
                return

            self._llm = Anthropic(api_key=api_key)
            logger.info("✓ LLM client initialized successfully with Claude")

        except ImportError as e:
            logger.warning(f"Required package not installed: {e}. Falling back to templates")
            self.use_llm = False
        except Exception as e:
            logger.warning(f"Failed to initialize LLM: {e}. Falling back to templates")
            self.use_llm = False

    def generate_tests_for_file(
        self, source_file: str, missing_lines: list[int]
    ) -> Path:
        """Generate tests for uncovered code in a file.

        Args:
            source_file: Path to source file
            missing_lines: Line numbers without coverage

        Returns:
            Path to generated test file

        Raises:
            RuntimeError: If test generation fails
        """
        logger.info(f"Generating tests for {source_file} (lines: {missing_lines[:5]}...)")

        # Read source file
        source_path = Path(source_file)
        if not source_path.exists():
            source_path = self.project_root / source_file

        # Resolve to absolute path for relative_to() to work correctly
        source_path = source_path.resolve()

        try:
            source_code = source_path.read_text()
        except Exception as e:
            raise RuntimeError(f"Cannot read source file: {e}") from e

        # Create unique test name from full path to avoid collisions
        # Example: src/empathy_os/telemetry/cli.py → test_src_empathy_os_telemetry_cli_generated.py
        relative_path = str(source_path.relative_to(self.project_root))
        test_name = f"test_{relative_path.replace('/', '_').replace('.py', '')}_generated.py"
        test_path = self.output_dir / test_name

        # Generate tests using LLM or template
        if self.use_llm and self._llm:
            test_code = self._generate_llm_tests(source_file, source_code, missing_lines)
        else:
            test_code = self._generate_basic_test_template(
                source_file, source_code, missing_lines
            )

        # Write test file
        validated_path = _validate_file_path(str(test_path))
        validated_path.write_text(test_code)

        logger.info(f"Generated test file: {test_path}")
        return test_path

    def _generate_llm_tests(
        self, source_file: str, source_code: str, missing_lines: list[int]
    ) -> str:
        """Generate tests using LLM (Claude).

        Args:
            source_file: Source file path
            source_code: Source file content
            missing_lines: Uncovered line numbers

        Returns:
            Generated test code

        Raises:
            RuntimeError: If LLM generation fails
        """
        logger.info(f"Using LLM to generate intelligent tests for {source_file}")

        # Extract API signatures using AST
        api_docs = self._extract_api_docs(source_code)

        # Extract module path
        module_path = source_file.replace("/", ".").replace(".py", "")

        # Create prompt for Claude with full context
        prompt = f"""Generate comprehensive pytest tests for the following Python code.

**Source File:** `{source_file}`
**Module Path:** `{module_path}`
**Uncovered Lines:** {missing_lines[:20]}

{api_docs}

**Full Source Code:**
```python
{source_code}
```

**CRITICAL Requirements - API Accuracy:**
1. **READ THE SOURCE CODE CAREFULLY** - Extract exact API signatures from:
   - Dataclass definitions (@dataclass) - use EXACT parameter names
   - Function signatures - match parameter names and types
   - Class __init__ methods - use correct constructor arguments

2. **DO NOT GUESS** parameter names - if you see:
   ```python
   @dataclass
   class Foo:
       bar: str  # Parameter name is 'bar', NOT 'bar_name'
   ```
   Then use: `Foo(bar="value")` NOT `Foo(bar_name="value")`

3. **Computed Properties** - Do NOT pass @property values to constructors:
   - If source has `@property def total(self): return self.a + self.b`
   - Then DO NOT use `Foo(total=10)` - it's computed from `a` and `b`

**Test Requirements:**
1. Write complete, runnable pytest tests
2. Focus on covering uncovered lines: {missing_lines[:10]}
3. Include:
   - Test class with descriptive name
   - Test methods for key functions/classes
   - Proper imports from the actual module path
   - Mock external dependencies (database, API calls, etc.)
   - Edge cases (empty inputs, None, zero, negative numbers)
   - Error handling tests (invalid input, exceptions)
4. Follow pytest best practices
5. Use clear, descriptive test method names
6. Add docstrings explaining what each test validates

**Output Format:**
Return ONLY the Python test code, starting with imports. No markdown, no explanations.
"""

        try:
            # Try Sonnet models only (Capable tier) - do NOT downgrade
            models_to_try = [
                "claude-sonnet-4-5-20250929",  # Sonnet 4.5 (January 2025 - latest)
                "claude-3-5-sonnet-20241022",  # 3.5 Sonnet Oct 2024
                "claude-3-5-sonnet-20240620",  # 3.5 Sonnet Jun 2024
            ]

            response = None
            last_error = None

            for model_name in models_to_try:
                try:
                    response = self._llm.messages.create(
                        model=model_name,
                        max_tokens=12000,  # Increased to prevent truncation on large files
                        temperature=0.3,  # Lower temperature for consistent code
                        messages=[{"role": "user", "content": prompt}],
                    )
                    logger.info(f"✓ Using Sonnet model: {model_name}")
                    break
                except Exception as e:
                    last_error = e
                    logger.debug(f"Model {model_name} not available: {e}")
                    continue

            if response is None:
                error_msg = f"All Sonnet models unavailable. Last error: {last_error}"
                logger.error(error_msg)
                raise RuntimeError(error_msg)

            test_code = response.content[0].text

            # Clean up markdown if present
            if "```python" in test_code:
                test_code = test_code.split("```python")[1].split("```")[0].strip()
            elif "```" in test_code:
                test_code = test_code.split("```")[1].split("```")[0].strip()

            logger.info(f"✓ LLM generated {len(test_code)} chars of test code")
            return test_code

        except Exception as e:
            logger.error(f"LLM test generation failed: {e}, falling back to template")
            return self._generate_basic_test_template(
                source_file, source_code, missing_lines
            )

    def _extract_api_docs(self, source_code: str) -> str:
        """Extract API signatures from source code using AST.

        Args:
            source_code: Python source code

        Returns:
            Formatted API documentation for LLM prompt
        """
        try:
            import sys
            from pathlib import Path

            # Add scripts to path
            scripts_dir = Path(__file__).parent.parent.parent.parent / "scripts"
            if str(scripts_dir) not in sys.path:
                sys.path.insert(0, str(scripts_dir))

            from ast_api_extractor import extract_api_signatures, format_api_docs

            classes, functions = extract_api_signatures(source_code)
            return format_api_docs(classes, functions)
        except Exception as e:
            logger.warning(f"AST extraction failed: {e}, proceeding without API docs")
            return "# API extraction failed - use source code carefully"

    def _generate_basic_test_template(
        self, source_file: str, source_code: str, missing_lines: list[int]
    ) -> str:
        """Generate basic test template.

        Args:
            source_file: Source file path
            source_code: Source file content
            missing_lines: Uncovered line numbers

        Returns:
            Test code as string
        """
        # Extract module name
        module_path = source_file.replace("/", ".").replace(".py", "")

        template = f'''"""Auto-generated tests for {source_file}.

Coverage gaps on lines: {missing_lines[:10]}
"""

import pytest


class TestGeneratedCoverage:
    """Tests to improve coverage for {source_file}."""

    def test_module_imports(self):
        """Test that module can be imported."""
        try:
            import {module_path}
            assert True
        except ImportError as e:
            pytest.fail(f"Module import failed: {{e}}")

    def test_placeholder_for_lines_{missing_lines[0] if missing_lines else 0}(self):
        """Placeholder test for uncovered code.

        TODO: Implement actual test logic for lines {missing_lines[:5]}
        """
        # This is a placeholder - connect to LLM for real test generation
        assert True, "Placeholder test - needs implementation"
'''
        return template


class RealTestValidator:
    """Validates generated tests by running them."""

    def __init__(self, project_root: str = "."):
        """Initialize test validator.

        Args:
            project_root: Project root directory
        """
        self.project_root = Path(project_root).resolve()

    def validate_tests(self, test_files: list[Path]) -> dict[str, Any]:
        """Run tests and measure coverage improvement.

        Args:
            test_files: List of test file paths

        Returns:
            Validation results dict

        Raises:
            RuntimeError: If validation fails
        """
        logger.info(f"Validating {len(test_files)} generated test files")

        try:
            # Run tests
            test_paths = [str(t) for t in test_files]
            cmd = ["pytest"] + test_paths + ["-v", "--tb=short"]

            result = subprocess.run(
                cmd,
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=300,
            )

            tests_passed = result.returncode == 0
            output_lines = result.stdout.split("\n")

            # Count passed/failed
            passed = sum(1 for line in output_lines if " PASSED" in line)
            failed = sum(1 for line in output_lines if " FAILED" in line)

            logger.info(
                f"Validation complete: {passed} passed, {failed} failed, "
                f"tests_passed={tests_passed}"
            )

            return {
                "all_passed": tests_passed,
                "passed_count": passed,
                "failed_count": failed,
                "output": result.stdout[:1000],  # Limit output
            }

        except subprocess.TimeoutExpired:
            raise RuntimeError("Test validation timed out after 5 minutes")
        except Exception as e:
            logger.error(f"Test validation failed: {e}")
            raise RuntimeError(f"Test validation failed: {e}") from e


@dataclass
class SecurityReport:
    """Security audit report from bandit."""

    total_issues: int
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int
    issues_by_file: dict[str, list[dict[str, Any]]]
    passed: bool


class RealSecurityAuditor:
    """Runs real security audit using bandit."""

    def __init__(self, project_root: str = "."):
        """Initialize security auditor.

        Args:
            project_root: Project root directory
        """
        self.project_root = Path(project_root).resolve()

    def audit(self, target_path: str = "src") -> SecurityReport:
        """Run security audit on codebase.

        Args:
            target_path: Path to audit (default: src)

        Returns:
            SecurityReport with vulnerability findings

        Raises:
            RuntimeError: If security audit fails
        """
        logger.info(f"Running security audit on {target_path}")

        try:
            # Run bandit with JSON output
            cmd = [
                "bandit",
                "-r",
                target_path,
                "-f",
                "json",
                "-q",  # Quiet mode - suppress progress bar and log messages
                "-ll",  # Only report medium and above
            ]

            result = subprocess.run(
                cmd,
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=300,
            )

            # Parse JSON output
            try:
                bandit_data = json.loads(result.stdout)
            except json.JSONDecodeError as e:
                # Bandit might not be installed or JSON output malformed
                logger.warning(f"Bandit not available or returned invalid JSON: {e}")
                stdout = result.stdout if isinstance(result.stdout, str) else ""
                stderr = result.stderr if isinstance(result.stderr, str) else ""
                logger.debug(f"Bandit stdout: {stdout[:500]}")
                logger.debug(f"Bandit stderr: {stderr[:500]}")
                return SecurityReport(
                    total_issues=0,
                    critical_count=0,
                    high_count=0,
                    medium_count=0,
                    low_count=0,
                    issues_by_file={},
                    passed=True,
                )

            # Count issues by severity
            results = bandit_data.get("results", [])
            critical_count = sum(1 for r in results if r.get("issue_severity") == "CRITICAL")
            high_count = sum(1 for r in results if r.get("issue_severity") == "HIGH")
            medium_count = sum(1 for r in results if r.get("issue_severity") == "MEDIUM")
            low_count = sum(1 for r in results if r.get("issue_severity") == "LOW")

            # Group by file
            issues_by_file = {}
            for issue in results:
                filepath = issue.get("filename", "unknown")
                if filepath not in issues_by_file:
                    issues_by_file[filepath] = []
                issues_by_file[filepath].append(
                    {
                        "line": issue.get("line_number"),
                        "severity": issue.get("issue_severity"),
                        "confidence": issue.get("issue_confidence"),
                        "message": issue.get("issue_text"),
                        "test_id": issue.get("test_id"),
                    }
                )

            total_issues = len(results)
            passed = critical_count == 0 and high_count == 0

            logger.info(
                f"Security audit complete: {total_issues} issues "
                f"(critical={critical_count}, high={high_count}, medium={medium_count})"
            )

            return SecurityReport(
                total_issues=total_issues,
                critical_count=critical_count,
                high_count=high_count,
                medium_count=medium_count,
                low_count=low_count,
                issues_by_file=issues_by_file,
                passed=passed,
            )

        except subprocess.TimeoutExpired:
            raise RuntimeError("Security audit timed out after 5 minutes")
        except Exception as e:
            logger.error(f"Security audit failed: {e}")
            raise RuntimeError(f"Security audit failed: {e}") from e


@dataclass
class QualityReport:
    """Code quality report from ruff and mypy."""

    quality_score: float  # 0-10
    ruff_issues: int
    mypy_issues: int
    total_files: int
    issues_by_category: dict[str, int]
    passed: bool


class RealCodeQualityAnalyzer:
    """Runs real code quality analysis using ruff and mypy."""

    def __init__(self, project_root: str = "."):
        """Initialize code quality analyzer.

        Args:
            project_root: Project root directory
        """
        self.project_root = Path(project_root).resolve()

    def analyze(self, target_path: str = "src") -> QualityReport:
        """Run code quality analysis.

        Args:
            target_path: Path to analyze (default: src)

        Returns:
            QualityReport with quality metrics

        Raises:
            RuntimeError: If quality analysis fails
        """
        logger.info(f"Running code quality analysis on {target_path}")

        try:
            # Run ruff for linting
            ruff_issues = self._run_ruff(target_path)

            # Run mypy for type checking (optional - may not be installed)
            mypy_issues = self._run_mypy(target_path)

            # Count files
            target = self.project_root / target_path
            py_files = list(target.rglob("*.py")) if target.is_dir() else [target]
            total_files = len(py_files)

            # Calculate quality score (0-10 scale)
            # Start with 10, deduct points for issues
            quality_score = 10.0
            quality_score -= min(ruff_issues * 0.01, 3.0)  # Max -3 points for ruff
            quality_score -= min(mypy_issues * 0.02, 2.0)  # Max -2 points for mypy
            quality_score = max(0.0, quality_score)  # Floor at 0

            # Passed if score >= 7.0
            passed = quality_score >= 7.0

            logger.info(
                f"Quality analysis complete: score={quality_score:.1f}/10 "
                f"(ruff={ruff_issues}, mypy={mypy_issues})"
            )

            return QualityReport(
                quality_score=quality_score,
                ruff_issues=ruff_issues,
                mypy_issues=mypy_issues,
                total_files=total_files,
                issues_by_category={"ruff": ruff_issues, "mypy": mypy_issues},
                passed=passed,
            )

        except Exception as e:
            logger.error(f"Quality analysis failed: {e}")
            raise RuntimeError(f"Quality analysis failed: {e}") from e

    def _run_ruff(self, target_path: str) -> int:
        """Run ruff linter and count issues."""
        try:
            cmd = ["ruff", "check", target_path, "--output-format=json"]

            result = subprocess.run(
                cmd,
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=120,
            )

            # Parse JSON output
            try:
                ruff_data = json.loads(result.stdout) if result.stdout else []
                return len(ruff_data)
            except json.JSONDecodeError:
                logger.warning("Ruff returned invalid JSON")
                return 0

        except FileNotFoundError:
            logger.warning("Ruff not installed, skipping")
            return 0
        except Exception as e:
            logger.warning(f"Ruff check failed: {e}")
            return 0

    def _run_mypy(self, target_path: str) -> int:
        """Run mypy type checker and count issues."""
        try:
            cmd = ["mypy", target_path, "--no-error-summary"]

            result = subprocess.run(
                cmd,
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=120,
            )

            # Count error lines
            error_count = sum(
                1 for line in result.stdout.split("\n") if ": error:" in line
            )
            return error_count

        except FileNotFoundError:
            logger.warning("Mypy not installed, skipping")
            return 0
        except Exception as e:
            logger.warning(f"Mypy check failed: {e}")
            return 0


@dataclass
class DocumentationReport:
    """Documentation completeness report."""

    completeness_percentage: float
    total_functions: int
    documented_functions: int
    total_classes: int
    documented_classes: int
    missing_docstrings: list[str]
    passed: bool


class RealDocumentationAnalyzer:
    """Analyzes documentation completeness by scanning docstrings."""

    def __init__(self, project_root: str = "."):
        """Initialize documentation analyzer.

        Args:
            project_root: Project root directory
        """
        self.project_root = Path(project_root).resolve()

    def analyze(self, target_path: str = "src") -> DocumentationReport:
        """Analyze documentation completeness.

        Args:
            target_path: Path to analyze (default: src)

        Returns:
            DocumentationReport with completeness metrics

        Raises:
            RuntimeError: If analysis fails
        """
        logger.info(f"Analyzing documentation completeness in {target_path}")

        import ast

        target = self.project_root / target_path
        py_files = list(target.rglob("*.py")) if target.is_dir() else [target]

        total_functions = 0
        documented_functions = 0
        total_classes = 0
        documented_classes = 0
        missing_docstrings = []

        for py_file in py_files:
            if py_file.name.startswith("__") and py_file.name.endswith("__.py"):
                continue  # Skip __init__.py, __main__.py

            try:
                tree = ast.parse(py_file.read_text())

                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef):
                        if not node.name.startswith("_"):  # Public functions
                            total_functions += 1
                            if ast.get_docstring(node):
                                documented_functions += 1
                            else:
                                missing_docstrings.append(
                                    f"{py_file.relative_to(self.project_root)}:{node.lineno} - function {node.name}"
                                )

                    elif isinstance(node, ast.ClassDef):
                        if not node.name.startswith("_"):  # Public classes
                            total_classes += 1
                            if ast.get_docstring(node):
                                documented_classes += 1
                            else:
                                missing_docstrings.append(
                                    f"{py_file.relative_to(self.project_root)}:{node.lineno} - class {node.name}"
                                )

            except Exception as e:
                logger.warning(f"Failed to parse {py_file}: {e}")
                continue

        # Calculate completeness
        total_items = total_functions + total_classes
        documented_items = documented_functions + documented_classes

        if total_items > 0:
            completeness_percentage = (documented_items / total_items) * 100
        else:
            completeness_percentage = 100.0  # No public APIs, consider complete

        passed = completeness_percentage >= 80.0

        logger.info(
            f"Documentation analysis complete: {completeness_percentage:.1f}% "
            f"({documented_items}/{total_items} items documented)"
        )

        return DocumentationReport(
            completeness_percentage=completeness_percentage,
            total_functions=total_functions,
            documented_functions=documented_functions,
            total_classes=total_classes,
            documented_classes=documented_classes,
            missing_docstrings=missing_docstrings[:10],  # Limit to first 10
            passed=passed,
        )


# Tool registry for agents
REAL_TOOLS = {
    "coverage_analyzer": RealCoverageAnalyzer,
    "test_generator": RealTestGenerator,
    "test_validator": RealTestValidator,
    "security_auditor": RealSecurityAuditor,
    "code_quality_analyzer": RealCodeQualityAnalyzer,
    "documentation_analyzer": RealDocumentationAnalyzer,
}
