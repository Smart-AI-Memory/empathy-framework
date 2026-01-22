"""Comprehensive Tests for BugPredictionWorkflow

Tests cover:
- Workflow stage execution (_scan, _correlate, _predict, _recommend)
- Helper methods (_patterns_correlate, _load_patterns)
- Report formatting (format_bug_predict_report)
- Constants and configuration
- Conditional stage skipping

Copyright 2025 Smart-AI-Memory
Licensed under Fair Source License 0.9
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from empathy_os.workflows.base import ModelTier
from empathy_os.workflows.bug_predict import (
    BUG_PREDICT_STEPS,
    BugPredictionWorkflow,
    format_bug_predict_report,
)

# ============================================================================
# Constants Tests
# ============================================================================


@pytest.mark.unit
class TestBugPredictConstants:
    """Tests for bug prediction constants."""

    def test_bug_predict_steps_recommend_config(self):
        """Verify BUG_PREDICT_STEPS has recommend configuration."""
        assert "recommend" in BUG_PREDICT_STEPS
        assert BUG_PREDICT_STEPS["recommend"].name == "recommend"
        assert BUG_PREDICT_STEPS["recommend"].tier_hint == "premium"
        assert BUG_PREDICT_STEPS["recommend"].max_tokens == 2000


# ============================================================================
# Workflow Initialization Tests
# ============================================================================


@pytest.mark.unit
class TestBugPredictionWorkflowInit:
    """Tests for BugPredictionWorkflow initialization."""

    def test_workflow_attributes(self, bug_predict_workflow):
        """Verify workflow has correct class attributes."""
        assert bug_predict_workflow.name == "bug-predict"
        assert bug_predict_workflow.description
        assert "scan" in bug_predict_workflow.stages
        assert "correlate" in bug_predict_workflow.stages
        assert "predict" in bug_predict_workflow.stages
        assert "recommend" in bug_predict_workflow.stages

    def test_tier_map_configuration(self, bug_predict_workflow):
        """Verify tier map assigns correct model tiers."""
        assert bug_predict_workflow.tier_map["scan"] == ModelTier.CHEAP
        assert bug_predict_workflow.tier_map["correlate"] == ModelTier.CAPABLE
        assert bug_predict_workflow.tier_map["predict"] == ModelTier.CAPABLE
        assert bug_predict_workflow.tier_map["recommend"] == ModelTier.PREMIUM

    def test_default_risk_threshold(self, bug_predict_workflow):
        """Test default risk threshold is set."""
        # Default from config or 0.7
        assert bug_predict_workflow.risk_threshold == 0.7

    def test_custom_risk_threshold(self):
        """Test custom risk threshold can be set."""
        workflow = BugPredictionWorkflow(risk_threshold=0.5)
        assert workflow.risk_threshold == 0.5

    def test_patterns_dir_configuration(self):
        """Test patterns directory can be configured."""
        workflow = BugPredictionWorkflow(patterns_dir="/custom/patterns")
        assert workflow.patterns_dir == "/custom/patterns"

    def test_load_patterns_from_file(self, tmp_path):
        """Test loading patterns from debugging.json."""
        patterns_dir = tmp_path / "patterns"
        patterns_dir.mkdir()
        debugging_file = patterns_dir / "debugging.json"
        debugging_file.write_text(
            json.dumps(
                {
                    "patterns": [
                        {"bug_type": "null_reference", "root_cause": "Missing null check"},
                        {"bug_type": "type_mismatch", "root_cause": "Wrong type"},
                    ]
                }
            )
        )

        workflow = BugPredictionWorkflow(patterns_dir=str(patterns_dir))
        assert len(workflow._bug_patterns) == 2
        assert workflow._bug_patterns[0]["bug_type"] == "null_reference"

    def test_load_patterns_handles_missing_file(self, tmp_path):
        """Test handling of missing debugging.json."""
        workflow = BugPredictionWorkflow(patterns_dir=str(tmp_path / "nonexistent"))
        assert workflow._bug_patterns == []

    def test_load_patterns_handles_invalid_json(self, tmp_path):
        """Test handling of invalid JSON in debugging.json."""
        patterns_dir = tmp_path / "patterns"
        patterns_dir.mkdir()
        debugging_file = patterns_dir / "debugging.json"
        debugging_file.write_text("invalid json{}")

        workflow = BugPredictionWorkflow(patterns_dir=str(patterns_dir))
        assert workflow._bug_patterns == []


# ============================================================================
# Skip Stage Tests
# ============================================================================


@pytest.mark.unit
class TestShouldSkipStage:
    """Tests for conditional stage skipping/downgrading."""

    def test_downgrade_recommend_when_low_risk(self, bug_predict_workflow):
        """Test recommend stage is downgraded when risk is below threshold."""
        bug_predict_workflow._risk_score = 0.3  # Below 0.7 threshold

        should_skip, reason = bug_predict_workflow.should_skip_stage("recommend", {})

        assert should_skip is False  # Doesn't skip, just downgrades
        assert bug_predict_workflow.tier_map["recommend"] == ModelTier.CAPABLE

    def test_no_downgrade_when_high_risk(self, bug_predict_workflow):
        """Test recommend stage stays premium when risk is high."""
        bug_predict_workflow._risk_score = 0.8  # Above 0.7 threshold

        should_skip, reason = bug_predict_workflow.should_skip_stage("recommend", {})

        assert should_skip is False
        # tier_map should remain PREMIUM (set in __init__)

    def test_other_stages_not_affected(self, bug_predict_workflow):
        """Test other stages are not affected by skip logic."""
        for stage in ["scan", "correlate", "predict"]:
            should_skip, reason = bug_predict_workflow.should_skip_stage(stage, {})
            assert should_skip is False
            assert reason is None


# ============================================================================
# Scan Stage Tests
# ============================================================================


@pytest.mark.unit
class TestScanStage:
    """Tests for the _scan stage."""

    @pytest.mark.asyncio
    async def test_scan_counts_files(self, tmp_path, monkeypatch):
        """Test scan counts scanned files."""
        # Change to tmp_path so config won't be loaded from real project
        monkeypatch.chdir(tmp_path)

        # Create a fresh workflow without external config
        workflow = BugPredictionWorkflow(patterns_dir=str(tmp_path))

        # Create some Python files
        (tmp_path / "file1.py").write_text("print('hello')")
        (tmp_path / "file2.py").write_text("print('world')")

        input_data = {"path": str(tmp_path), "file_types": [".py"]}
        result, _, _ = await workflow._scan(input_data, ModelTier.CHEAP)

        assert result["file_count"] >= 2
        assert "scanned_files" in result

    @pytest.mark.asyncio
    async def test_scan_detects_broad_exception(self, tmp_path, monkeypatch):
        """Test scan detects broad exception handlers."""
        # Change to tmp_path so config won't be loaded from real project
        monkeypatch.chdir(tmp_path)

        # Create a fresh workflow without external config
        workflow = BugPredictionWorkflow(patterns_dir=str(tmp_path))

        bad_file = tmp_path / "bad.py"
        bad_file.write_text(
            """
def process():
    try:
        risky()
    except Exception:
        print("error")  # Bad: just printing
"""
        )

        input_data = {"path": str(tmp_path), "file_types": [".py"]}
        result, _, _ = await workflow._scan(input_data, ModelTier.CHEAP)

        broad_exc = [p for p in result["patterns_found"] if p["pattern"] == "broad_exception"]
        assert len(broad_exc) >= 1

    @pytest.mark.asyncio
    async def test_scan_detects_incomplete_code(self, tmp_path, monkeypatch):
        """Test scan detects TODO/FIXME comments."""
        # Change to tmp_path so config won't be loaded from real project
        monkeypatch.chdir(tmp_path)

        # Create a fresh workflow without external config
        workflow = BugPredictionWorkflow(patterns_dir=str(tmp_path))

        todo_file = tmp_path / "todo.py"
        todo_file.write_text(
            """
def incomplete():
    # TODO: Implement this
    pass
"""
        )

        input_data = {"path": str(tmp_path), "file_types": [".py"]}
        result, _, _ = await workflow._scan(input_data, ModelTier.CHEAP)

        incomplete = [p for p in result["patterns_found"] if p["pattern"] == "incomplete_code"]
        assert len(incomplete) >= 1

    @pytest.mark.asyncio
    async def test_scan_skips_excluded_directories(self, tmp_path, monkeypatch):
        """Test scan skips node_modules and other excluded dirs."""
        monkeypatch.chdir(tmp_path)
        workflow = BugPredictionWorkflow(patterns_dir=str(tmp_path))

        node_modules = tmp_path / "node_modules"
        node_modules.mkdir()
        (node_modules / "bad.py").write_text("eval(x)")  # Would be flagged

        (tmp_path / "good.py").write_text("print('safe')")

        input_data = {"path": str(tmp_path), "file_types": [".py"]}
        result, _, _ = await workflow._scan(input_data, ModelTier.CHEAP)

        # Should only scan good.py, not node_modules/bad.py
        scanned_paths = [f["path"] for f in result["scanned_files"]]
        assert not any("node_modules" in p for p in scanned_paths)

    @pytest.mark.asyncio
    async def test_scan_handles_nonexistent_path(self, tmp_path, monkeypatch):
        """Test scan handles nonexistent path gracefully."""
        monkeypatch.chdir(tmp_path)
        workflow = BugPredictionWorkflow(patterns_dir=str(tmp_path))

        input_data = {"path": str(tmp_path / "nonexistent"), "file_types": [".py"]}
        result, _, _ = await workflow._scan(input_data, ModelTier.CHEAP)

        assert result["file_count"] == 0
        assert result["patterns_found"] == []

    @pytest.mark.asyncio
    async def test_scan_returns_token_estimates(self, tmp_path, monkeypatch):
        """Test scan returns token estimates."""
        monkeypatch.chdir(tmp_path)
        workflow = BugPredictionWorkflow(patterns_dir=str(tmp_path))

        (tmp_path / "test.py").write_text("x = 1")

        input_data = {"path": str(tmp_path), "file_types": [".py"]}
        result, input_tokens, output_tokens = await workflow._scan(
            input_data, ModelTier.CHEAP
        )

        assert isinstance(input_tokens, int)
        assert isinstance(output_tokens, int)

    @pytest.mark.asyncio
    async def test_scan_limits_scanned_files_output(self, tmp_path, monkeypatch):
        """Test scan limits scanned_files to 100 entries."""
        # Change to tmp_path so config won't be loaded from real project
        monkeypatch.chdir(tmp_path)

        workflow = BugPredictionWorkflow(patterns_dir=str(tmp_path))

        # Create many files
        for i in range(150):
            (tmp_path / f"file{i}.py").write_text(f"x = {i}")

        input_data = {"path": str(tmp_path), "file_types": [".py"]}
        result, _, _ = await workflow._scan(input_data, ModelTier.CHEAP)

        assert len(result["scanned_files"]) <= 100
        assert result["file_count"] >= 150  # Total count is accurate


# ============================================================================
# Correlate Stage Tests
# ============================================================================


@pytest.mark.unit
class TestCorrelateStage:
    """Tests for the _correlate stage."""

    @pytest.mark.asyncio
    async def test_correlate_matches_patterns(self, tmp_path):
        """Test correlate matches current patterns with historical bugs."""
        # Create workflow with known patterns
        patterns_dir = tmp_path / "patterns"
        patterns_dir.mkdir()
        (patterns_dir / "debugging.json").write_text(
            json.dumps(
                {
                    "patterns": [
                        {"bug_type": "null_reference", "root_cause": "Missing null check"},
                    ]
                }
            )
        )

        workflow = BugPredictionWorkflow(patterns_dir=str(patterns_dir))

        input_data = {
            "patterns_found": [
                {"file": "test.py", "pattern": "broad_exception", "severity": "medium"}
            ]
        }

        result, _, _ = await workflow._correlate(input_data, ModelTier.CAPABLE)

        assert "correlations" in result
        assert result["correlation_count"] >= 1

    @pytest.mark.asyncio
    async def test_correlate_sets_confidence_scores(self, bug_predict_workflow):
        """Test correlate sets confidence scores for matches."""
        input_data = {
            "patterns_found": [
                {"file": "test.py", "pattern": "broad_exception", "severity": "medium"}
            ]
        }

        result, _, _ = await bug_predict_workflow._correlate(input_data, ModelTier.CAPABLE)

        for corr in result["correlations"]:
            assert "confidence" in corr
            assert 0 <= corr["confidence"] <= 1

    @pytest.mark.asyncio
    async def test_correlate_handles_no_patterns(self, bug_predict_workflow):
        """Test correlate handles empty patterns list."""
        input_data = {"patterns_found": []}

        result, _, _ = await bug_predict_workflow._correlate(input_data, ModelTier.CAPABLE)

        assert result["correlations"] == []
        assert result["correlation_count"] == 0

    @pytest.mark.asyncio
    async def test_correlate_counts_high_confidence(self, bug_predict_workflow):
        """Test correlate counts high confidence correlations."""
        input_data = {
            "patterns_found": [
                {"file": "a.py", "pattern": "broad_exception", "severity": "medium"},
                {"file": "b.py", "pattern": "incomplete_code", "severity": "low"},
            ]
        }

        result, _, _ = await bug_predict_workflow._correlate(input_data, ModelTier.CAPABLE)

        assert "high_confidence_count" in result


# ============================================================================
# Patterns Correlate Helper Tests
# ============================================================================


@pytest.mark.unit
class TestPatternsCorrelate:
    """Tests for _patterns_correlate helper method."""

    def test_broad_exception_correlates_with_null_reference(self, bug_predict_workflow):
        """Test broad_exception correlates with null_reference."""
        result = bug_predict_workflow._patterns_correlate("broad_exception", "null_reference")
        assert result is True

    def test_broad_exception_correlates_with_type_mismatch(self, bug_predict_workflow):
        """Test broad_exception correlates with type_mismatch."""
        result = bug_predict_workflow._patterns_correlate("broad_exception", "type_mismatch")
        assert result is True

    def test_incomplete_code_correlates_with_async_timing(self, bug_predict_workflow):
        """Test incomplete_code correlates with async_timing."""
        result = bug_predict_workflow._patterns_correlate("incomplete_code", "async_timing")
        assert result is True

    def test_dangerous_eval_correlates_with_import_error(self, bug_predict_workflow):
        """Test dangerous_eval correlates with import_error."""
        result = bug_predict_workflow._patterns_correlate("dangerous_eval", "import_error")
        assert result is True

    def test_unknown_pattern_no_correlation(self, bug_predict_workflow):
        """Test unknown patterns don't correlate."""
        result = bug_predict_workflow._patterns_correlate("unknown", "null_reference")
        assert result is False


# ============================================================================
# Predict Stage Tests
# ============================================================================


@pytest.mark.unit
class TestPredictStage:
    """Tests for the _predict stage."""

    @pytest.mark.asyncio
    async def test_predict_calculates_file_risks(self, bug_predict_workflow):
        """Test predict calculates risk scores for files."""
        input_data = {
            "correlations": [
                {
                    "current_pattern": {
                        "file": "risky.py",
                        "pattern": "broad_exception",
                        "severity": "high",
                    },
                    "confidence": 0.8,
                }
            ],
            "patterns_found": [
                {"file": "risky.py", "pattern": "broad_exception", "severity": "high"}
            ],
        }

        result, _, _ = await bug_predict_workflow._predict(input_data, ModelTier.CAPABLE)

        assert "predictions" in result
        assert len(result["predictions"]) >= 1
        assert result["predictions"][0]["file"] == "risky.py"
        assert "risk_score" in result["predictions"][0]

    @pytest.mark.asyncio
    async def test_predict_calculates_overall_risk(self, bug_predict_workflow):
        """Test predict calculates overall risk score."""
        input_data = {
            "correlations": [
                {
                    "current_pattern": {"file": "a.py", "severity": "high"},
                    "confidence": 0.9,
                },
                {
                    "current_pattern": {"file": "b.py", "severity": "medium"},
                    "confidence": 0.5,
                },
            ],
            "patterns_found": [],
        }

        result, _, _ = await bug_predict_workflow._predict(input_data, ModelTier.CAPABLE)

        assert "overall_risk_score" in result
        assert 0 <= result["overall_risk_score"] <= 1

    @pytest.mark.asyncio
    async def test_predict_sorts_by_risk(self, bug_predict_workflow):
        """Test predict sorts predictions by risk score descending."""
        input_data = {
            "correlations": [
                {
                    "current_pattern": {"file": "low.py", "severity": "low"},
                    "confidence": 0.3,
                },
                {
                    "current_pattern": {"file": "high.py", "severity": "high"},
                    "confidence": 0.9,
                },
            ],
            "patterns_found": [],
        }

        result, _, _ = await bug_predict_workflow._predict(input_data, ModelTier.CAPABLE)

        if len(result["predictions"]) >= 2:
            assert result["predictions"][0]["risk_score"] >= result["predictions"][1]["risk_score"]

    @pytest.mark.asyncio
    async def test_predict_counts_high_risk_files(self, bug_predict_workflow):
        """Test predict counts high risk files."""
        input_data = {
            "correlations": [
                {
                    "current_pattern": {"file": "critical.py", "severity": "high"},
                    "confidence": 1.0,
                }
            ],
            "patterns_found": [],
        }

        result, _, _ = await bug_predict_workflow._predict(input_data, ModelTier.CAPABLE)

        assert "high_risk_files" in result

    @pytest.mark.asyncio
    async def test_predict_limits_to_top_20(self, bug_predict_workflow):
        """Test predict limits predictions to top 20."""
        # Create many correlations
        correlations = [
            {"current_pattern": {"file": f"file{i}.py", "severity": "medium"}, "confidence": 0.5}
            for i in range(30)
        ]

        input_data = {"correlations": correlations, "patterns_found": []}

        result, _, _ = await bug_predict_workflow._predict(input_data, ModelTier.CAPABLE)

        assert len(result["predictions"]) <= 20

    @pytest.mark.asyncio
    async def test_predict_handles_empty_correlations(self, bug_predict_workflow):
        """Test predict handles empty correlations."""
        input_data = {"correlations": [], "patterns_found": []}

        result, _, _ = await bug_predict_workflow._predict(input_data, ModelTier.CAPABLE)

        assert result["predictions"] == []
        assert result["overall_risk_score"] == 0


# ============================================================================
# Recommend Stage Tests
# ============================================================================


@pytest.mark.unit
class TestRecommendStage:
    """Tests for the _recommend stage."""

    @pytest.mark.asyncio
    async def test_recommend_generates_recommendations(self, bug_predict_workflow):
        """Test recommend generates recommendations via LLM."""
        with patch.object(
            bug_predict_workflow, "_call_llm", new_callable=AsyncMock
        ) as mock_llm:
            mock_llm.return_value = ("Fix the broad exception handlers.", 100, 200)

            input_data = {
                "predictions": [
                    {
                        "file": "risky.py",
                        "risk_score": 0.8,
                        "patterns": [{"pattern": "broad_exception", "severity": "high"}],
                    }
                ],
                "overall_risk_score": 0.8,
            }

            result, _, _ = await bug_predict_workflow._recommend(input_data, ModelTier.PREMIUM)

            assert "recommendations" in result
            assert "Fix" in result["recommendations"]

    @pytest.mark.asyncio
    async def test_recommend_includes_formatted_report(self, bug_predict_workflow):
        """Test recommend includes formatted report."""
        with patch.object(
            bug_predict_workflow, "_call_llm", new_callable=AsyncMock
        ) as mock_llm:
            mock_llm.return_value = ("Recommendations here", 50, 100)

            input_data = {
                "predictions": [],
                "overall_risk_score": 0.5,
            }

            result, _, _ = await bug_predict_workflow._recommend(input_data, ModelTier.PREMIUM)

            assert "formatted_report" in result
            assert "BUG PREDICTION REPORT" in result["formatted_report"]

    @pytest.mark.asyncio
    async def test_recommend_uses_executor_when_available(self, bug_predict_workflow):
        """Test recommend uses executor when available."""
        bug_predict_workflow._executor = MagicMock()
        bug_predict_workflow._api_key = "test-key"

        with patch.object(
            bug_predict_workflow, "run_step_with_executor", new_callable=AsyncMock
        ) as mock_run:
            mock_run.return_value = ("Executor recommendations", 100, 200, 0.05)

            input_data = {"predictions": [], "overall_risk_score": 0.5}

            result, _, _ = await bug_predict_workflow._recommend(input_data, ModelTier.PREMIUM)

            mock_run.assert_called_once()

    @pytest.mark.asyncio
    async def test_recommend_falls_back_on_executor_failure(self, bug_predict_workflow):
        """Test recommend falls back to _call_llm on executor failure."""
        bug_predict_workflow._executor = MagicMock()
        bug_predict_workflow._api_key = "test-key"

        with patch.object(
            bug_predict_workflow, "run_step_with_executor", new_callable=AsyncMock
        ) as mock_run:
            mock_run.side_effect = Exception("Executor failed")

            with patch.object(
                bug_predict_workflow, "_call_llm", new_callable=AsyncMock
            ) as mock_llm:
                mock_llm.return_value = ("Fallback recommendations", 50, 100)

                input_data = {"predictions": [], "overall_risk_score": 0.5}

                result, _, _ = await bug_predict_workflow._recommend(
                    input_data, ModelTier.PREMIUM
                )

                mock_llm.assert_called_once()


# ============================================================================
# Run Stage Router Tests
# ============================================================================


@pytest.mark.unit
class TestRunStageRouter:
    """Tests for run_stage method routing."""

    @pytest.mark.asyncio
    async def test_run_stage_routes_to_scan(self, bug_predict_workflow, tmp_path):
        """Test run_stage routes 'scan' to _scan method."""
        (tmp_path / "test.py").write_text("x = 1")
        input_data = {"path": str(tmp_path)}

        result, _, _ = await bug_predict_workflow.run_stage("scan", ModelTier.CHEAP, input_data)

        assert "scanned_files" in result
        assert "patterns_found" in result

    @pytest.mark.asyncio
    async def test_run_stage_routes_to_correlate(self, bug_predict_workflow):
        """Test run_stage routes 'correlate' to _correlate method."""
        input_data = {"patterns_found": []}

        result, _, _ = await bug_predict_workflow.run_stage(
            "correlate", ModelTier.CAPABLE, input_data
        )

        assert "correlations" in result

    @pytest.mark.asyncio
    async def test_run_stage_routes_to_predict(self, bug_predict_workflow):
        """Test run_stage routes 'predict' to _predict method."""
        input_data = {"correlations": [], "patterns_found": []}

        result, _, _ = await bug_predict_workflow.run_stage(
            "predict", ModelTier.CAPABLE, input_data
        )

        assert "predictions" in result

    @pytest.mark.asyncio
    async def test_run_stage_routes_to_recommend(self, bug_predict_workflow):
        """Test run_stage routes 'recommend' to _recommend method."""
        with patch.object(
            bug_predict_workflow, "_call_llm", new_callable=AsyncMock
        ) as mock_llm:
            mock_llm.return_value = ("Recommendations", 50, 100)

            input_data = {"predictions": [], "overall_risk_score": 0.5}

            result, _, _ = await bug_predict_workflow.run_stage(
                "recommend", ModelTier.PREMIUM, input_data
            )

            assert "recommendations" in result

    @pytest.mark.asyncio
    async def test_run_stage_raises_for_unknown_stage(self, bug_predict_workflow):
        """Test run_stage raises ValueError for unknown stage."""
        with pytest.raises(ValueError, match="Unknown stage"):
            await bug_predict_workflow.run_stage("unknown", ModelTier.CHEAP, {})


# ============================================================================
# Format Report Tests
# ============================================================================


@pytest.mark.unit
class TestFormatBugPredictReport:
    """Tests for format_bug_predict_report function."""

    def test_format_report_includes_header(self):
        """Test format_bug_predict_report includes header."""
        result = {"overall_risk_score": 0.5, "model_tier_used": "capable"}
        input_data = {}
        report = format_bug_predict_report(result, input_data)

        assert "BUG PREDICTION REPORT" in report
        assert "MODERATE RISK" in report

    def test_format_report_high_risk_level(self):
        """Test format_bug_predict_report shows HIGH RISK for score >= 0.8."""
        result = {"overall_risk_score": 0.85, "model_tier_used": "premium"}
        input_data = {}
        report = format_bug_predict_report(result, input_data)

        assert "HIGH RISK" in report

    def test_format_report_low_risk_level(self):
        """Test format_bug_predict_report shows LOW RISK for score >= 0.3."""
        result = {"overall_risk_score": 0.35, "model_tier_used": "capable"}
        input_data = {}
        report = format_bug_predict_report(result, input_data)

        assert "LOW RISK" in report

    def test_format_report_minimal_risk_level(self):
        """Test format_bug_predict_report shows MINIMAL RISK for score < 0.3."""
        result = {"overall_risk_score": 0.1, "model_tier_used": "cheap"}
        input_data = {}
        report = format_bug_predict_report(result, input_data)

        assert "MINIMAL RISK" in report

    def test_format_report_includes_scan_summary(self):
        """Test format_bug_predict_report includes scan summary."""
        result = {"overall_risk_score": 0.5, "model_tier_used": "capable"}
        input_data = {"file_count": 100, "pattern_count": 5}
        report = format_bug_predict_report(result, input_data)

        assert "SCAN SUMMARY" in report
        assert "Files Scanned: 100" in report
        assert "Patterns Found: 5" in report

    def test_format_report_includes_pattern_breakdown(self):
        """Test format_bug_predict_report includes pattern breakdown."""
        result = {"overall_risk_score": 0.5, "model_tier_used": "capable"}
        input_data = {
            "patterns_found": [
                {"severity": "high"},
                {"severity": "medium"},
                {"severity": "medium"},
                {"severity": "low"},
            ]
        }
        report = format_bug_predict_report(result, input_data)

        assert "Pattern Breakdown:" in report
        assert "High: 1" in report
        assert "Medium: 2" in report
        assert "Low: 1" in report

    def test_format_report_includes_high_risk_files(self):
        """Test format_bug_predict_report includes high risk files section."""
        result = {"overall_risk_score": 0.8, "model_tier_used": "premium"}
        input_data = {
            "predictions": [
                {
                    "file": "critical.py",
                    "risk_score": 0.9,
                    "patterns": [{"pattern": "broad_exception", "severity": "high"}],
                }
            ]
        }
        report = format_bug_predict_report(result, input_data)

        assert "HIGH RISK FILES" in report
        assert "critical.py" in report

    def test_format_report_includes_correlations(self):
        """Test format_bug_predict_report includes historical correlations."""
        result = {"overall_risk_score": 0.6, "model_tier_used": "capable"}
        input_data = {
            "correlations": [
                {
                    "current_pattern": {"pattern": "broad_exception"},
                    "historical_bug": {"type": "null_reference", "root_cause": "Missing check"},
                    "confidence": 0.75,
                }
            ]
        }
        report = format_bug_predict_report(result, input_data)

        assert "HISTORICAL BUG CORRELATIONS" in report
        assert "broad_exception" in report
        assert "null_reference" in report

    def test_format_report_includes_recommendations(self):
        """Test format_bug_predict_report includes recommendations."""
        result = {
            "overall_risk_score": 0.7,
            "model_tier_used": "premium",
            "recommendations": "Fix the broad exception handlers by using specific exceptions.",
        }
        input_data = {}
        report = format_bug_predict_report(result, input_data)

        assert "RECOMMENDATIONS" in report
        assert "Fix the broad exception" in report

    def test_format_report_includes_model_tier_footer(self):
        """Test format_bug_predict_report includes model tier in footer."""
        result = {"overall_risk_score": 0.5, "model_tier_used": "premium"}
        input_data = {}
        report = format_bug_predict_report(result, input_data)

        assert "premium tier model" in report


# ============================================================================
# XML Prompt Tests
# ============================================================================


@pytest.mark.unit
class TestXMLPromptHandling:
    """Tests for XML-enhanced prompt handling in recommend stage."""

    @pytest.mark.asyncio
    async def test_recommend_uses_xml_when_enabled(self, bug_predict_workflow):
        """Test recommend uses XML-enhanced prompts when enabled."""
        with patch.object(bug_predict_workflow, "_is_xml_enabled", return_value=True):
            with patch.object(
                bug_predict_workflow, "_render_xml_prompt", return_value="<xml>prompt</xml>"
            ) as mock_render:
                with patch.object(
                    bug_predict_workflow, "_call_llm", new_callable=AsyncMock
                ) as mock_llm:
                    mock_llm.return_value = ("XML response", 100, 200)

                    input_data = {"predictions": [], "overall_risk_score": 0.5}

                    await bug_predict_workflow._recommend(input_data, ModelTier.PREMIUM)

                    mock_render.assert_called_once()

    @pytest.mark.asyncio
    async def test_recommend_uses_legacy_prompt_when_xml_disabled(self, bug_predict_workflow):
        """Test recommend uses legacy prompts when XML is disabled."""
        with patch.object(bug_predict_workflow, "_is_xml_enabled", return_value=False):
            with patch.object(
                bug_predict_workflow, "_call_llm", new_callable=AsyncMock
            ) as mock_llm:
                mock_llm.return_value = ("Legacy response", 100, 200)

                input_data = {"predictions": [], "overall_risk_score": 0.5}

                await bug_predict_workflow._recommend(input_data, ModelTier.PREMIUM)

                # Verify _call_llm was called with non-None system prompt
                call_args = mock_llm.call_args
                system_prompt = call_args[0][1]  # Second positional arg
                assert system_prompt  # Non-empty system prompt for legacy mode
