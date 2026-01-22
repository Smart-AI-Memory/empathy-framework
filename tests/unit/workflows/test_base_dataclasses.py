"""Tests for workflow base dataclasses.

These tests cover:
- WorkflowStage dataclass
- CostReport dataclass
- StageQualityMetrics dataclass
- WorkflowResult dataclass
- ModelTier and ModelProvider enums
"""

from datetime import datetime

import pytest

from empathy_os.workflows.base import (
    CostReport,
    ModelProvider,
    ModelTier,
    StageQualityMetrics,
    WorkflowResult,
    WorkflowStage,
)


@pytest.mark.unit
class TestWorkflowStage:
    """Test WorkflowStage dataclass."""

    def test_create_stage_with_required_fields(self):
        """Test creating stage with required fields."""
        stage = WorkflowStage(
            name="analysis",
            tier=ModelTier.CHEAP,
            description="Analyze code",
        )

        assert stage.name == "analysis"
        assert stage.tier == ModelTier.CHEAP
        assert stage.description == "Analyze code"

    def test_stage_default_values(self):
        """Test stage default field values."""
        stage = WorkflowStage(
            name="test",
            tier=ModelTier.CAPABLE,
            description="Test stage",
        )

        assert stage.input_tokens == 0
        assert stage.output_tokens == 0
        assert stage.cost == 0.0
        assert stage.duration_ms == 0
        assert stage.skipped is False
        assert stage.skip_reason is None

    def test_stage_with_all_fields(self):
        """Test stage with all fields set."""
        stage = WorkflowStage(
            name="premium_analysis",
            tier=ModelTier.PREMIUM,
            description="Premium analysis",
            input_tokens=500,
            output_tokens=1000,
            cost=0.05,
            result={"findings": []},
            duration_ms=2500,
            skipped=False,
        )

        assert stage.input_tokens == 500
        assert stage.output_tokens == 1000
        assert stage.cost == 0.05
        assert stage.result == {"findings": []}
        assert stage.duration_ms == 2500

    def test_stage_with_skipped_true(self):
        """Test stage with skipped=True."""
        stage = WorkflowStage(
            name="optional",
            tier=ModelTier.PREMIUM,
            description="Optional stage",
            skipped=True,
            skip_reason="User requested skip",
        )

        assert stage.skipped is True
        assert stage.skip_reason == "User requested skip"


@pytest.mark.unit
class TestCostReport:
    """Test CostReport dataclass."""

    def test_create_cost_report(self):
        """Test creating cost report."""
        report = CostReport(
            total_cost=0.006,
            baseline_cost=0.02,
            savings=0.014,
            savings_percent=70.0,
        )

        assert report.total_cost == 0.006
        assert report.baseline_cost == 0.02
        assert report.savings == 0.014
        assert report.savings_percent == 70.0

    def test_cost_report_with_breakdowns(self):
        """Test cost report with stage and tier breakdowns."""
        report = CostReport(
            total_cost=0.01,
            baseline_cost=0.05,
            savings=0.04,
            savings_percent=80.0,
            by_stage={"analysis": 0.003, "review": 0.007},
            by_tier={"cheap": 0.003, "capable": 0.007},
        )

        assert report.by_stage["analysis"] == 0.003
        assert report.by_tier["cheap"] == 0.003

    def test_cost_report_with_cache_stats(self):
        """Test cost report with cache statistics."""
        report = CostReport(
            total_cost=0.005,
            baseline_cost=0.02,
            savings=0.015,
            savings_percent=75.0,
            cache_hits=5,
            cache_misses=2,
            cache_hit_rate=0.714,
            estimated_cost_without_cache=0.01,
            savings_from_cache=0.005,
        )

        assert report.cache_hits == 5
        assert report.cache_misses == 2
        assert report.cache_hit_rate == 0.714
        assert report.savings_from_cache == 0.005

    def test_cost_report_default_cache_stats(self):
        """Test cost report defaults cache stats to 0."""
        report = CostReport(
            total_cost=0.0,
            baseline_cost=0.0,
            savings=0.0,
            savings_percent=0.0,
        )

        assert report.cache_hits == 0
        assert report.cache_misses == 0
        assert report.cache_hit_rate == 0.0
        assert report.savings_from_cache == 0.0


@pytest.mark.unit
class TestStageQualityMetrics:
    """Test StageQualityMetrics dataclass."""

    def test_create_quality_metrics_success(self):
        """Test creating quality metrics for successful execution."""
        metrics = StageQualityMetrics(
            execution_succeeded=True,
            output_valid=True,
            quality_improved=True,
            error_type=None,
            validation_error=None,
        )

        assert metrics.execution_succeeded is True
        assert metrics.output_valid is True
        assert metrics.quality_improved is True
        assert metrics.error_type is None

    def test_quality_metrics_failure(self):
        """Test quality metrics with failed execution."""
        metrics = StageQualityMetrics(
            execution_succeeded=False,
            output_valid=False,
            quality_improved=False,
            error_type="timeout",
            validation_error="Output too short",
        )

        assert metrics.execution_succeeded is False
        assert metrics.output_valid is False
        assert metrics.error_type == "timeout"
        assert metrics.validation_error == "Output too short"


@pytest.mark.unit
class TestWorkflowResult:
    """Test WorkflowResult dataclass."""

    def test_create_successful_result(self):
        """Test creating successful workflow result."""
        now = datetime.now()
        stages = [
            WorkflowStage("s1", ModelTier.CHEAP, "Stage 1", input_tokens=100, cost=0.001),
        ]
        cost_report = CostReport(
            total_cost=0.001,
            baseline_cost=0.005,
            savings=0.004,
            savings_percent=80.0,
        )

        result = WorkflowResult(
            success=True,
            stages=stages,
            final_output="Analysis complete",
            cost_report=cost_report,
            started_at=now,
            completed_at=now,
            total_duration_ms=1500,
        )

        assert result.success is True
        assert result.final_output == "Analysis complete"
        assert result.total_duration_ms == 1500
        assert result.error is None

    def test_create_failed_result_with_error(self):
        """Test creating failed workflow result."""
        now = datetime.now()
        cost_report = CostReport(
            total_cost=0.0,
            baseline_cost=0.0,
            savings=0.0,
            savings_percent=0.0,
        )

        result = WorkflowResult(
            success=False,
            stages=[],
            final_output="",
            cost_report=cost_report,
            started_at=now,
            completed_at=now,
            total_duration_ms=500,
            error="Provider timeout",
            error_type="timeout",
            transient=True,
        )

        assert result.success is False
        assert result.error == "Provider timeout"
        assert result.error_type == "timeout"
        assert result.transient is True

    def test_result_default_error_fields(self):
        """Test result defaults error fields."""
        now = datetime.now()
        cost_report = CostReport(
            total_cost=0.0,
            baseline_cost=0.0,
            savings=0.0,
            savings_percent=0.0,
        )

        result = WorkflowResult(
            success=True,
            stages=[],
            final_output="",
            cost_report=cost_report,
            started_at=now,
            completed_at=now,
            total_duration_ms=100,
        )

        assert result.error is None
        assert result.error_type is None
        assert result.transient is False


@pytest.mark.unit
class TestModelTier:
    """Test ModelTier enum."""

    def test_tier_values(self):
        """Test tier enum values exist."""
        assert ModelTier.CHEAP is not None
        assert ModelTier.CAPABLE is not None
        assert ModelTier.PREMIUM is not None

    def test_tier_string_values(self):
        """Test tier enum string values."""
        assert ModelTier.CHEAP.value == "cheap"
        assert ModelTier.CAPABLE.value == "capable"
        assert ModelTier.PREMIUM.value == "premium"

    def test_tier_to_unified(self):
        """Test tier converts to unified ModelTier."""
        from empathy_os.models import ModelTier as UnifiedModelTier

        unified = ModelTier.CHEAP.to_unified()
        assert unified == UnifiedModelTier.CHEAP

        unified = ModelTier.CAPABLE.to_unified()
        assert unified == UnifiedModelTier.CAPABLE

        unified = ModelTier.PREMIUM.to_unified()
        assert unified == UnifiedModelTier.PREMIUM


@pytest.mark.unit
class TestModelProvider:
    """Test ModelProvider enum."""

    def test_provider_values_exist(self):
        """Test provider enum values exist."""
        assert ModelProvider.ANTHROPIC is not None
        assert ModelProvider.OPENAI is not None
        assert ModelProvider.GOOGLE is not None
        assert ModelProvider.OLLAMA is not None
        assert ModelProvider.HYBRID is not None
        assert ModelProvider.CUSTOM is not None

    def test_provider_string_values(self):
        """Test provider enum string values."""
        assert ModelProvider.ANTHROPIC.value == "anthropic"
        assert ModelProvider.OPENAI.value == "openai"
        assert ModelProvider.GOOGLE.value == "google"
        assert ModelProvider.OLLAMA.value == "ollama"

    def test_provider_to_unified(self):
        """Test provider converts to unified ModelProvider."""
        from empathy_os.models import ModelProvider as UnifiedModelProvider

        unified = ModelProvider.ANTHROPIC.to_unified()
        assert unified == UnifiedModelProvider.ANTHROPIC

        unified = ModelProvider.OPENAI.to_unified()
        assert unified == UnifiedModelProvider.OPENAI
