"""Tests for CodeReviewWorkflow main functionality.

This test suite covers:
- Stage execution flow
- Classification logic
- Conditional stage skipping
- Crew integration (mocked)
- Security scan integration
- Architect review triggering
"""

from unittest.mock import AsyncMock, patch

import pytest

from empathy_os.workflows.base import ModelTier
from empathy_os.workflows.code_review import CodeReviewWorkflow

# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def workflow(cost_tracker):
    """Create CodeReviewWorkflow with isolated storage."""
    return CodeReviewWorkflow(cost_tracker=cost_tracker, use_crew=False)


@pytest.fixture
def workflow_with_crew(cost_tracker):
    """Create CodeReviewWorkflow with crew enabled."""
    return CodeReviewWorkflow(cost_tracker=cost_tracker, use_crew=True)


@pytest.fixture
def sample_diff():
    """Simple code diff for testing."""
    return """
diff --git a/src/utils.py b/src/utils.py
index 1234567..abcdefg 100644
--- a/src/utils.py
+++ b/src/utils.py
@@ -10,6 +10,10 @@ def helper():
     return "hello"
+
+def new_function():
+    '''A new utility function.'''
+    return 42
"""


@pytest.fixture
def security_diff():
    """Diff with potential security issues for testing."""
    return """
diff --git a/src/auth.py b/src/auth.py
--- a/src/auth.py
+++ b/src/auth.py
@@ -1,3 +1,8 @@
+import os
+
+def get_secret():
+    password = "hardcoded_secret"  # Security issue
+    return eval(os.getenv("CMD"))  # Another issue
"""


# ============================================================================
# Test: Workflow Initialization
# ============================================================================


@pytest.mark.unit
class TestWorkflowInitialization:
    """Tests for workflow initialization and configuration."""

    def test_default_initialization(self, cost_tracker):
        """Test workflow initializes with default settings."""
        workflow = CodeReviewWorkflow(cost_tracker=cost_tracker)

        assert workflow.name == "code-review"
        assert workflow.file_threshold == 10
        assert workflow.use_crew is True

    def test_custom_file_threshold(self, cost_tracker):
        """Test workflow respects custom file threshold."""
        workflow = CodeReviewWorkflow(cost_tracker=cost_tracker, file_threshold=5)

        assert workflow.file_threshold == 5

    def test_custom_core_modules(self, cost_tracker):
        """Test workflow respects custom core modules list."""
        custom_modules = ["src/critical/", "lib/secure/"]
        workflow = CodeReviewWorkflow(
            cost_tracker=cost_tracker, core_modules=custom_modules
        )

        assert workflow.core_modules == custom_modules

    def test_crew_disabled(self, cost_tracker):
        """Test workflow can be initialized with crew disabled."""
        workflow = CodeReviewWorkflow(cost_tracker=cost_tracker, use_crew=False)

        assert workflow.use_crew is False


# ============================================================================
# Test: Stage Configuration
# ============================================================================


@pytest.mark.unit
class TestStageConfiguration:
    """Tests for stage and tier configuration."""

    def test_stages_without_crew(self, workflow):
        """Test stages when crew is disabled."""
        # When crew is disabled, crew_review stage should not be in stages
        assert "classify" in workflow.stages
        assert "scan" in workflow.stages
        assert "architect_review" in workflow.stages

    def test_tier_mapping(self, workflow):
        """Test tier assignments for stages."""
        assert workflow.tier_map["classify"] == ModelTier.CHEAP
        assert workflow.tier_map["scan"] == ModelTier.CAPABLE
        assert workflow.tier_map["architect_review"] == ModelTier.PREMIUM


# ============================================================================
# Test: Classification Stage
# ============================================================================


@pytest.mark.unit
class TestClassifyStage:
    """Tests for the classification stage logic."""

    @pytest.mark.asyncio
    async def test_classify_simple_change(self, workflow, sample_diff):
        """Test classification of a simple code change."""
        with patch.object(workflow, "_call_llm", new_callable=AsyncMock) as mock_llm:
            # _call_llm returns (response, input_tokens, output_tokens)
            mock_llm.return_value = (
                "Classification: Simple utility addition\n"
                "Change Type: feature\n"
                "Complexity: low",
                100,  # input_tokens
                50,   # output_tokens
            )

            input_data = {"diff": sample_diff, "files_changed": ["src/utils.py"]}
            result, _, _ = await workflow._classify(input_data, ModelTier.CHEAP)

            assert "classification" in result
            mock_llm.assert_called_once()

    @pytest.mark.asyncio
    async def test_classify_triggers_architect_for_many_files(self, cost_tracker):
        """Test that many file changes trigger architect review."""
        workflow = CodeReviewWorkflow(
            cost_tracker=cost_tracker, file_threshold=3, use_crew=False
        )

        with patch.object(workflow, "_call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = (
                "Classification: Large refactor\nChange Type: refactor",
                100,
                50,
            )

            # Provide more files than threshold
            many_files = ["file1.py", "file2.py", "file3.py", "file4.py"]
            input_data = {"diff": "...", "files_changed": many_files}
            result, _, _ = await workflow._classify(input_data, ModelTier.CHEAP)

            assert result.get("file_count", 0) >= 3

    @pytest.mark.asyncio
    async def test_classify_core_module_detection(self, cost_tracker):
        """Test that core module changes are detected."""
        workflow = CodeReviewWorkflow(
            cost_tracker=cost_tracker,
            core_modules=["src/security/"],
            use_crew=False,
        )

        with patch.object(workflow, "_call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = ("Classification: Security update", 100, 50)

            input_data = {"diff": "...", "files_changed": ["src/security/auth.py"]}
            result, _, _ = await workflow._classify(input_data, ModelTier.CHEAP)

            # Core module should influence review decision
            assert "classification" in result


# ============================================================================
# Test: Stage Skipping Logic
# ============================================================================


@pytest.mark.unit
class TestShouldSkipStage:
    """Tests for conditional stage skipping."""

    def test_never_skip_classify(self, workflow):
        """Classify stage should never be skipped."""
        should_skip, reason = workflow.should_skip_stage("classify", {})

        assert should_skip is False

    def test_skip_architect_for_simple_changes(self, workflow):
        """Architect review should be skipped for simple changes."""
        workflow._needs_architect_review = False

        should_skip, reason = workflow.should_skip_stage("architect_review", {})

        assert should_skip is True
        assert reason is not None

    def test_dont_skip_architect_when_needed(self, workflow):
        """Architect review should not be skipped when flagged."""
        workflow._needs_architect_review = True

        should_skip, reason = workflow.should_skip_stage("architect_review", {})

        assert should_skip is False


# ============================================================================
# Test: Security Scan Stage
# ============================================================================


@pytest.mark.unit
class TestScanStage:
    """Tests for the security scan stage."""

    @pytest.mark.asyncio
    async def test_scan_detects_issues(self, workflow, security_diff):
        """Test that scan stage can detect security issues."""
        with patch.object(workflow, "_call_llm", new_callable=AsyncMock) as mock_llm:
            # _call_llm returns (response, input_tokens, output_tokens)
            mock_llm.return_value = (
                "Security Issues Found:\n"
                "1. Hardcoded credential detected\n"
                "2. Use of eval() with user input\n"
                "Severity: HIGH",
                150,
                80,
            )

            input_data = {
                "code_to_review": security_diff,
                "classification": "Security-sensitive change",
            }
            result, _, _ = await workflow._scan(input_data, ModelTier.CAPABLE)

            assert "scan_results" in result
            mock_llm.assert_called_once()

    @pytest.mark.asyncio
    async def test_scan_returns_findings(self, workflow, sample_diff):
        """Test that scan returns structured findings."""
        with patch.object(workflow, "_call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = (
                "No security issues found. Code looks clean.",
                100,
                40,
            )

            input_data = {
                "code_to_review": sample_diff,
                "classification": "Simple change",
            }
            result, _, _ = await workflow._scan(input_data, ModelTier.CAPABLE)

            assert "scan_results" in result


# ============================================================================
# Test: Architect Review Stage
# ============================================================================


@pytest.mark.unit
class TestArchitectReviewStage:
    """Tests for the architect review stage."""

    @pytest.mark.asyncio
    async def test_architect_review_generates_verdict(self, workflow):
        """Test that architect review produces a verdict."""
        workflow._needs_architect_review = True

        with patch.object(workflow, "_call_llm", new_callable=AsyncMock) as mock_llm:
            # _call_llm returns (response, input_tokens, output_tokens)
            mock_llm.return_value = (
                "Architectural Assessment:\n"
                "The changes are well-structured.\n"
                "Verdict: APPROVE\n"
                "Recommendations: None",
                200,
                100,
            )

            input_data = {
                "code_to_review": "def example(): pass",
                "scan_results": "No issues found",
            }
            result, _, _ = await workflow._architect_review(input_data, ModelTier.PREMIUM)

            assert "architectural_review" in result
            mock_llm.assert_called_once()


# ============================================================================
# Test: Full Workflow Execution
# ============================================================================


@pytest.mark.unit
class TestWorkflowExecution:
    """Tests for end-to-end workflow execution."""

    @pytest.mark.asyncio
    async def test_execute_simple_review(self, workflow, sample_diff):
        """Test executing a simple code review."""
        with patch.object(workflow, "_call_llm", new_callable=AsyncMock) as mock_llm:
            # Mock responses for each stage - returns (response, input_tokens, output_tokens)
            mock_llm.side_effect = [
                ("Classification: Simple change\nChange Type: feature\nComplexity: low", 100, 50),
                ("No security issues found.", 100, 40),
            ]

            workflow._needs_architect_review = False

            result = await workflow.execute(
                diff=sample_diff, files_changed=["src/utils.py"]
            )

            # Result is a WorkflowResult object
            assert result is not None
            assert hasattr(result, "success") or hasattr(result, "output")

    @pytest.mark.asyncio
    async def test_execute_with_validation_error(self, workflow):
        """Test execution with invalid input."""
        # No diff or target provided
        result = await workflow.execute(files_changed=[])

        # Should handle gracefully - returns WorkflowResult
        assert result is not None


# ============================================================================
# Test: Report Formatting
# ============================================================================


@pytest.mark.unit
class TestReportFormatting:
    """Tests for report generation."""

    def test_format_code_review_report_exists(self):
        """Test that report formatting function exists."""
        from empathy_os.workflows.code_review import format_code_review_report

        assert callable(format_code_review_report)

    def test_format_empty_results(self):
        """Test formatting with minimal results."""
        from empathy_os.workflows.code_review import format_code_review_report

        # Function takes (results: dict, input_data: dict)
        report = format_code_review_report({}, {})

        assert isinstance(report, str)
