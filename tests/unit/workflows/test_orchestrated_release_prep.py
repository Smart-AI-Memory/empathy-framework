"""Tests for Orchestrated Release Preparation Workflow.

Tests the first production use case of the meta-orchestration system:
parallel agent execution for release readiness validation.

Test Coverage:
    - Workflow initialization
    - Parallel execution of validation agents
    - Quality gate enforcement
    - Report generation
    - Integration with configuration store
    - Error handling and edge cases

Copyright 2025 Smart-AI-Memory
Licensed under Fair Source License 0.9
"""

import pytest

from empathy_os.orchestration.agent_templates import get_template
from empathy_os.orchestration.execution_strategies import AgentResult
from empathy_os.workflows.orchestrated_release_prep import (
    OrchestratedReleasePrepWorkflow,
    QualityGate,
    ReleaseReadinessReport,
)


class TestQualityGate:
    """Test QualityGate data class."""

    def test_quality_gate_pass(self):
        """Test quality gate that passes threshold."""
        gate = QualityGate(
            name="Coverage",
            threshold=80.0,
            actual=85.0,
            passed=True,  # Must be set explicitly
        )

        assert gate.passed is True
        assert gate.name == "Coverage"
        assert gate.threshold == 80.0
        assert gate.actual == 85.0
        assert "PASS" in gate.message

    def test_quality_gate_fail(self):
        """Test quality gate that fails threshold."""
        gate = QualityGate(
            name="Coverage",
            threshold=80.0,
            actual=75.0,
            passed=False,  # Must be set explicitly
        )

        assert gate.passed is False
        assert "FAIL" in gate.message

    def test_quality_gate_critical(self):
        """Test critical quality gate."""
        gate = QualityGate(
            name="Security",
            threshold=0.0,
            actual=1.0,
            passed=False,  # Explicitly set - higher is worse for security
            critical=True,
        )

        assert gate.critical is True
        assert gate.passed is False

    def test_quality_gate_non_critical(self):
        """Test non-critical quality gate."""
        gate = QualityGate(
            name="Documentation",
            threshold=100.0,
            actual=95.0,
            passed=False,  # Explicitly set - below threshold
            critical=False,
        )

        assert gate.critical is False
        assert gate.passed is False

    def test_quality_gate_validation(self):
        """Test quality gate field validation."""
        # Empty name
        with pytest.raises(ValueError, match="name must be non-empty"):
            QualityGate(name="", threshold=80.0)

        # Negative threshold
        with pytest.raises(ValueError, match="threshold must be non-negative"):
            QualityGate(name="Test", threshold=-1.0)

    def test_quality_gate_custom_message(self):
        """Test quality gate with custom message."""
        custom_msg = "Custom status message"
        gate = QualityGate(
            name="Test",
            threshold=80.0,
            actual=85.0,
            message=custom_msg,
        )

        assert gate.message == custom_msg


class TestReleaseReadinessReport:
    """Test ReleaseReadinessReport data class."""

    def test_report_creation(self):
        """Test basic report creation."""
        report = ReleaseReadinessReport(
            approved=True,
            confidence="high",
            summary="All checks passed",
        )

        assert report.approved is True
        assert report.confidence == "high"
        assert report.summary == "All checks passed"
        assert isinstance(report.quality_gates, list)
        assert isinstance(report.agent_results, dict)
        assert isinstance(report.blockers, list)
        assert isinstance(report.warnings, list)

    def test_report_to_dict(self):
        """Test report serialization to dict."""
        gate = QualityGate(name="Coverage", threshold=80.0, actual=85.0)

        report = ReleaseReadinessReport(
            approved=True,
            confidence="high",
            quality_gates=[gate],
            agent_results={"test_agent": {"success": True}},
            blockers=[],
            warnings=["Minor issue"],
            summary="Good to go",
        )

        result = report.to_dict()

        assert isinstance(result, dict)
        assert result["approved"] is True
        assert result["confidence"] == "high"
        assert len(result["quality_gates"]) == 1
        assert result["quality_gates"][0]["name"] == "Coverage"
        assert result["agent_results"]["test_agent"]["success"] is True
        assert len(result["warnings"]) == 1

    def test_report_format_console_approved(self):
        """Test console formatting for approved release."""
        gate = QualityGate(name="Coverage", threshold=80.0, actual=85.0)

        report = ReleaseReadinessReport(
            approved=True,
            confidence="high",
            quality_gates=[gate],
            summary="Ready for release",
            total_duration=5.5,
        )

        output = report.format_console_output()

        assert "READY FOR RELEASE" in output
        assert "✅" in output
        assert "Coverage" in output
        assert "5.5" in output
        assert "HIGH" in output

    def test_report_format_console_rejected(self):
        """Test console formatting for rejected release."""
        gate = QualityGate(name="Security", threshold=0.0, actual=2.0, critical=True)

        report = ReleaseReadinessReport(
            approved=False,
            confidence="low",
            quality_gates=[gate],
            blockers=["Critical security issues"],
            warnings=["Minor warnings"],
            summary="Not ready",
        )

        output = report.format_console_output()

        assert "NOT READY" in output
        assert "❌" in output
        assert "BLOCKERS" in output
        assert "Critical security issues" in output
        assert "WARNINGS" in output

    def test_report_with_agent_results(self):
        """Test report with agent execution results."""
        report = ReleaseReadinessReport(
            approved=True,
            confidence="high",
            agent_results={
                "security_auditor": {"success": True, "duration": 1.2},
                "code_reviewer": {"success": True, "duration": 2.3},
            },
        )

        output = report.format_console_output()

        assert "security_auditor" in output
        assert "code_reviewer" in output
        assert "1.2" in output
        assert "2.3" in output


class TestOrchestratedReleasePrepWorkflow:
    """Test OrchestratedReleasePrepWorkflow class."""

    def test_workflow_initialization_default(self):
        """Test workflow initialization with defaults."""
        workflow = OrchestratedReleasePrepWorkflow()

        assert workflow.quality_gates["min_coverage"] == 80.0
        assert workflow.quality_gates["min_quality_score"] == 7.0
        assert workflow.quality_gates["max_critical_issues"] == 0.0
        assert workflow.quality_gates["min_doc_coverage"] == 100.0
        assert workflow.orchestrator is not None
        # Default agent_ids are set
        assert workflow.agent_ids is not None
        assert len(workflow.agent_ids) > 0

    def test_workflow_initialization_custom_gates(self):
        """Test workflow initialization with custom quality gates."""
        custom_gates = {
            "min_coverage": 90.0,
            "min_quality_score": 8.0,
        }

        workflow = OrchestratedReleasePrepWorkflow(quality_gates=custom_gates)

        assert workflow.quality_gates["min_coverage"] == 90.0
        assert workflow.quality_gates["min_quality_score"] == 8.0
        # Defaults still present
        assert workflow.quality_gates["max_critical_issues"] == 0.0

    def test_workflow_initialization_custom_agents(self):
        """Test workflow initialization with specific agent IDs."""
        agent_ids = ["security_auditor", "test_coverage_analyzer"]

        workflow = OrchestratedReleasePrepWorkflow(agent_ids=agent_ids)

        assert workflow.agent_ids == agent_ids

    def test_workflow_initialization_invalid_gates(self):
        """Test workflow initialization with invalid quality gates."""
        # Non-numeric threshold
        with pytest.raises(ValueError, match="must be numeric"):
            OrchestratedReleasePrepWorkflow(quality_gates={"min_coverage": "80"})

        # Negative threshold
        with pytest.raises(ValueError, match="must be non-negative"):
            OrchestratedReleasePrepWorkflow(quality_gates={"min_coverage": -10.0})

    @pytest.mark.asyncio
    async def test_execute_basic(self):
        """Test basic workflow execution."""
        workflow = OrchestratedReleasePrepWorkflow()

        # Execute with default path
        report = await workflow.execute(path=".")

        # Verify report structure
        assert isinstance(report, ReleaseReadinessReport)
        assert isinstance(report.approved, bool)
        assert report.confidence in ["high", "medium", "low"]
        assert isinstance(report.quality_gates, list)
        assert isinstance(report.agent_results, dict)
        assert report.total_duration >= 0.0

    @pytest.mark.asyncio
    async def test_execute_with_context(self):
        """Test workflow execution with additional context."""
        workflow = OrchestratedReleasePrepWorkflow()

        context = {
            "version": "3.12.0",
            "release_type": "major",
        }

        report = await workflow.execute(path=".", context=context)

        assert isinstance(report, ReleaseReadinessReport)
        # Context should be passed to agents
        assert report.agent_results  # Agents should have executed

    @pytest.mark.asyncio
    async def test_execute_invalid_path(self):
        """Test workflow execution with invalid path."""
        workflow = OrchestratedReleasePrepWorkflow()

        # Empty path
        with pytest.raises(ValueError, match="path must be a non-empty string"):
            await workflow.execute(path="")

        # Non-string path
        with pytest.raises(ValueError, match="path must be a non-empty string"):
            await workflow.execute(path=None)

    @pytest.mark.asyncio
    async def test_execute_with_specific_agents(self):
        """Test workflow execution with specific agent IDs."""
        agent_ids = ["security_auditor", "code_reviewer"]
        workflow = OrchestratedReleasePrepWorkflow(agent_ids=agent_ids)

        report = await workflow.execute(path=".")

        # Verify agents were used
        assert len(report.agent_results) >= len(agent_ids)

    @pytest.mark.asyncio
    async def test_execute_invalid_agent_ids(self):
        """Test workflow execution with invalid agent IDs."""
        workflow = OrchestratedReleasePrepWorkflow(agent_ids=["nonexistent_agent"])

        with pytest.raises(ValueError, match="No valid agents found"):
            await workflow.execute(path=".")

    def test_evaluate_quality_gates_all_pass(self):
        """Test quality gate evaluation when all gates pass."""
        workflow = OrchestratedReleasePrepWorkflow()

        agent_results = {
            "security_auditor": {
                "output": {"critical_issues": 0},
                "success": True,
            },
            "test_coverage_analyzer": {
                "output": {"coverage_percent": 85.0},
                "success": True,
            },
            "code_reviewer": {
                "output": {"quality_score": 8.0},
                "success": True,
            },
            "documentation_writer": {
                "output": {"coverage_percent": 100.0},
                "success": True,
            },
        }

        gates = workflow._evaluate_quality_gates(agent_results)

        assert len(gates) == 4
        assert all(gate.passed for gate in gates)

    def test_evaluate_quality_gates_some_fail(self):
        """Test quality gate evaluation when some gates fail."""
        workflow = OrchestratedReleasePrepWorkflow()

        agent_results = {
            "security_auditor": {
                "output": {"critical_issues": 0},  # PASS - no issues
                "success": True,
            },
            "test_coverage_analyzer": {
                "output": {"coverage_percent": 75.0},  # FAIL (< 80)
                "success": True,
            },
            "code_reviewer": {
                "output": {"quality_score": 8.0},  # PASS
                "success": True,
            },
            "documentation_writer": {
                "output": {"coverage_percent": 95.0},  # FAIL (< 100, but non-critical)
                "success": True,
            },
        }

        gates = workflow._evaluate_quality_gates(agent_results)

        assert len(gates) == 4
        failed_gates = [g for g in gates if not g.passed]
        assert len(failed_gates) == 2  # Coverage and docs fail

        # Check specific gates
        security_gate = next(g for g in gates if g.name == "Security")
        assert security_gate.passed  # No critical issues
        assert security_gate.critical

        coverage_gate = next(g for g in gates if g.name == "Test Coverage")
        assert not coverage_gate.passed
        assert coverage_gate.critical

        docs_gate = next(g for g in gates if g.name == "Documentation")
        assert not docs_gate.passed
        assert not docs_gate.critical  # Non-critical

    def test_evaluate_quality_gates_missing_results(self):
        """Test quality gate evaluation with missing agent results."""
        workflow = OrchestratedReleasePrepWorkflow()

        # Empty results
        agent_results = {}

        gates = workflow._evaluate_quality_gates(agent_results)

        # Should still create gates with default values
        assert len(gates) == 4

        # Security passes (0 issues is good)
        security_gate = next(g for g in gates if g.name == "Security")
        assert security_gate.passed  # 0 <= 0

        # Other gates fail (0 doesn't meet minimums)
        coverage_gate = next(g for g in gates if g.name == "Test Coverage")
        assert not coverage_gate.passed  # 0 < 80

        quality_gate = next(g for g in gates if g.name == "Code Quality")
        assert not quality_gate.passed  # 0 < 7

        docs_gate = next(g for g in gates if g.name == "Documentation")
        assert not docs_gate.passed  # 0 < 100

    def test_identify_issues_no_issues(self):
        """Test issue identification when all gates pass."""
        workflow = OrchestratedReleasePrepWorkflow()

        quality_gates = [
            QualityGate(
                name="Security",
                threshold=0.0,
                actual=0.0,
                passed=True,  # Explicitly pass
                critical=True,
            ),
            QualityGate(
                name="Coverage",
                threshold=80.0,
                actual=85.0,
                passed=True,  # Explicitly pass
                critical=True,
            ),
        ]

        agent_results = {
            "security_auditor": {"success": True},
            "test_coverage_analyzer": {"success": True},
        }

        blockers, warnings = workflow._identify_issues(quality_gates, agent_results)

        assert len(blockers) == 0
        assert len(warnings) == 0

    def test_identify_issues_critical_failures(self):
        """Test issue identification with critical gate failures."""
        workflow = OrchestratedReleasePrepWorkflow()

        quality_gates = [
            QualityGate(
                name="Coverage",
                threshold=80.0,
                actual=75.0,
                critical=True,
                passed=False,
            ),
        ]

        agent_results = {
            "test_coverage_analyzer": {"success": True},
        }

        blockers, warnings = workflow._identify_issues(quality_gates, agent_results)

        assert len(blockers) == 1
        assert any("Coverage failed" in b for b in blockers)
        assert len(warnings) == 0

    def test_identify_issues_warnings_only(self):
        """Test issue identification with non-critical failures."""
        workflow = OrchestratedReleasePrepWorkflow()

        quality_gates = [
            QualityGate(
                name="Documentation",
                threshold=100.0,
                actual=95.0,
                critical=False,
                passed=False,
            ),
        ]

        agent_results = {
            "documentation_writer": {"success": True},
        }

        blockers, warnings = workflow._identify_issues(quality_gates, agent_results)

        assert len(blockers) == 0
        assert len(warnings) == 1
        assert "Documentation" in warnings[0]

    def test_identify_issues_agent_failures(self):
        """Test issue identification with agent execution failures."""
        workflow = OrchestratedReleasePrepWorkflow()

        quality_gates = []  # All gates pass

        agent_results = {
            "security_auditor": {
                "success": False,
                "error": "Scan failed",
            },
            "test_coverage_analyzer": {"success": True},
        }

        blockers, warnings = workflow._identify_issues(quality_gates, agent_results)

        assert len(blockers) == 1
        assert "security_auditor" in blockers[0]
        assert "Scan failed" in blockers[0]

    def test_generate_summary_approved(self):
        """Test summary generation for approved release."""
        workflow = OrchestratedReleasePrepWorkflow()

        quality_gates = [
            QualityGate(name="Security", threshold=0.0, actual=0.0, passed=True),
            QualityGate(name="Coverage", threshold=80.0, actual=85.0, passed=True),
        ]

        agent_results = {
            "security_auditor": {"success": True},
            "test_coverage_analyzer": {"success": True},
        }

        summary = workflow._generate_summary(True, quality_gates, agent_results)

        assert "RELEASE APPROVED" in summary
        assert "ready for release" in summary.lower()
        assert "Passed: 2/2" in summary

    def test_generate_summary_rejected(self):
        """Test summary generation for rejected release."""
        workflow = OrchestratedReleasePrepWorkflow()

        quality_gates = [
            QualityGate(
                name="Security",
                threshold=0.0,
                actual=0.0,
                passed=True,  # Security passes
            ),
            QualityGate(name="Coverage", threshold=80.0, actual=75.0, passed=False),
        ]

        agent_results = {
            "security_auditor": {"success": True},
            "test_coverage_analyzer": {"success": True},
        }

        summary = workflow._generate_summary(False, quality_gates, agent_results)

        assert "NOT APPROVED" in summary
        assert "Address blockers" in summary
        assert "Passed: 1/2" in summary  # Security passes, Coverage fails
        assert "Failed:" in summary

    @pytest.mark.asyncio
    async def test_create_report_all_success(self):
        """Test report creation with all agents successful."""
        workflow = OrchestratedReleasePrepWorkflow()

        # Mock strategy result
        from empathy_os.orchestration.execution_strategies import (
            StrategyResult,
        )

        agent_results = [
            AgentResult(
                agent_id="security_auditor",
                success=True,
                output={"critical_issues": 0},
                confidence=0.9,
                duration_seconds=1.5,
            ),
            AgentResult(
                agent_id="test_coverage_analyzer",
                success=True,
                output={"coverage_percent": 85.0},
                confidence=0.85,
                duration_seconds=2.0,
            ),
            AgentResult(
                agent_id="code_reviewer",
                success=True,
                output={"quality_score": 8.0},
                confidence=0.88,
                duration_seconds=1.8,
            ),
            AgentResult(
                agent_id="documentation_writer",
                success=True,
                output={"coverage_percent": 100.0},
                confidence=0.92,
                duration_seconds=1.2,
            ),
        ]

        strategy_result = StrategyResult(
            success=True,
            outputs=agent_results,
            aggregated_output={},
            total_duration=2.0,
        )

        # Mock agents
        agents = [
            get_template("security_auditor"),
            get_template("test_coverage_analyzer"),
            get_template("code_reviewer"),
            get_template("documentation_writer"),
        ]

        context = {"path": "."}

        report = await workflow._create_report(strategy_result, agents, context)

        assert report.approved is True
        assert report.confidence == "high"
        assert len(report.quality_gates) == 4
        assert all(gate.passed for gate in report.quality_gates)
        assert len(report.blockers) == 0
        assert len(report.warnings) == 0

    @pytest.mark.asyncio
    async def test_create_report_with_failures(self):
        """Test report creation with some failures."""
        workflow = OrchestratedReleasePrepWorkflow()

        from empathy_os.orchestration.execution_strategies import (
            StrategyResult,
        )

        agent_results = [
            AgentResult(
                agent_id="security_auditor",
                success=True,
                output={"critical_issues": 0},  # PASS - no security issues
                confidence=0.7,
                duration_seconds=1.5,
            ),
            AgentResult(
                agent_id="test_coverage_analyzer",
                success=True,
                output={"coverage_percent": 75.0},  # FAIL - below threshold
                confidence=0.6,
                duration_seconds=2.0,
            ),
            AgentResult(
                agent_id="code_reviewer",
                success=False,  # Agent failed
                output={},
                error="Analysis failed",
                duration_seconds=0.5,
            ),
        ]

        strategy_result = StrategyResult(
            success=False,
            outputs=agent_results,
            aggregated_output={},
            total_duration=2.0,
        )

        agents = [
            get_template("security_auditor"),
            get_template("test_coverage_analyzer"),
            get_template("code_reviewer"),
        ]

        context = {"path": "."}

        report = await workflow._create_report(strategy_result, agents, context)

        assert report.approved is False
        assert report.confidence == "low"
        assert len(report.blockers) > 0
        # Should have blocker for failed coverage and failed agent
        assert any("code_reviewer" in b for b in report.blockers)
        assert any("Coverage" in b or "Test Coverage" in b for b in report.blockers)

    @pytest.mark.asyncio
    async def test_create_report_medium_confidence(self):
        """Test report creation with warnings but approval."""
        workflow = OrchestratedReleasePrepWorkflow()

        from empathy_os.orchestration.execution_strategies import (
            StrategyResult,
        )

        agent_results = [
            AgentResult(
                agent_id="security_auditor",
                success=True,
                output={"critical_issues": 0},  # PASS
                confidence=0.9,
                duration_seconds=1.5,
            ),
            AgentResult(
                agent_id="test_coverage_analyzer",
                success=True,
                output={"coverage_percent": 85.0},  # PASS
                confidence=0.85,
                duration_seconds=2.0,
            ),
            AgentResult(
                agent_id="code_reviewer",
                success=True,
                output={"quality_score": 8.0},  # PASS
                confidence=0.88,
                duration_seconds=1.8,
            ),
            AgentResult(
                agent_id="documentation_writer",
                success=True,
                output={"coverage_percent": 95.0},  # FAIL (non-critical)
                confidence=0.92,
                duration_seconds=1.2,
            ),
        ]

        strategy_result = StrategyResult(
            success=True,
            outputs=agent_results,
            aggregated_output={},
            total_duration=2.0,
        )

        agents = [
            get_template("security_auditor"),
            get_template("test_coverage_analyzer"),
            get_template("code_reviewer"),
            get_template("documentation_writer"),
        ]

        context = {"path": "."}

        report = await workflow._create_report(strategy_result, agents, context)

        assert report.approved is True  # No critical failures
        assert report.confidence == "medium"  # Has warnings
        assert len(report.blockers) == 0
        assert len(report.warnings) > 0


class TestIntegration:
    """Integration tests for orchestrated release prep workflow."""

    @pytest.mark.asyncio
    async def test_end_to_end_workflow(self):
        """Test complete end-to-end workflow execution."""
        # Create workflow with lenient quality gates for testing
        workflow = OrchestratedReleasePrepWorkflow(
            quality_gates={
                "min_coverage": 0.0,  # Accept any coverage
                "min_quality_score": 0.0,  # Accept any quality
                "max_critical_issues": 100.0,  # Accept issues
                "min_doc_coverage": 0.0,  # Accept any docs
            }
        )

        # Execute workflow
        report = await workflow.execute(path=".")

        # Verify report structure
        assert isinstance(report, ReleaseReadinessReport)
        assert isinstance(report.approved, bool)
        assert report.confidence in ["high", "medium", "low"]
        assert len(report.quality_gates) == 4
        assert isinstance(report.agent_results, dict)
        assert report.total_duration > 0.0

        # Verify console output
        console_output = report.format_console_output()
        assert isinstance(console_output, str)
        assert len(console_output) > 0
        assert "RELEASE READINESS REPORT" in console_output

        # Verify dict serialization
        report_dict = report.to_dict()
        assert isinstance(report_dict, dict)
        assert "approved" in report_dict
        assert "quality_gates" in report_dict
        assert "agent_results" in report_dict

    @pytest.mark.asyncio
    async def test_workflow_with_custom_agents(self):
        """Test workflow execution with specific agents."""
        # Use only security and coverage agents
        workflow = OrchestratedReleasePrepWorkflow(
            agent_ids=["security_auditor", "test_coverage_analyzer"],
            quality_gates={
                "min_coverage": 0.0,
                "max_critical_issues": 100.0,
                "min_quality_score": 0.0,
                "min_doc_coverage": 0.0,
            },
        )

        report = await workflow.execute(path=".")

        # Should have results from specified agents
        assert "security_auditor" in report.agent_results
        assert "test_coverage_analyzer" in report.agent_results

    @pytest.mark.asyncio
    async def test_workflow_report_persistence(self):
        """Test that workflow results can be saved to configuration store."""
        workflow = OrchestratedReleasePrepWorkflow(
            quality_gates={"min_coverage": 0.0, "max_critical_issues": 100.0}
        )

        report = await workflow.execute(path=".")

        # Convert to dict for storage
        report_dict = report.to_dict()

        # Verify serializable
        import json

        json_str = json.dumps(report_dict)
        assert isinstance(json_str, str)

        # Verify deserializable
        restored = json.loads(json_str)
        assert restored["approved"] == report.approved
        assert restored["confidence"] == report.confidence
