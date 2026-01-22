"""Comprehensive Tests for SecurityAuditWorkflow

Tests cover:
- Workflow stage execution (_triage, _analyze, _assess, _remediate)
- Helper methods (_analyze_finding, _get_remediation_action)
- Report formatting (format_security_report)
- Constants and patterns validation
- Team decision loading and filtering

Copyright 2025 Smart-AI-Memory
Licensed under Fair Source License 0.9
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from empathy_os.workflows.base import ModelTier
from empathy_os.workflows.security_audit import (
    DETECTION_PATTERNS,
    FAKE_CREDENTIAL_PATTERNS,
    SECURITY_PATTERNS,
    SECURITY_STEPS,
    SKIP_DIRECTORIES,
    TEST_FILE_PATTERNS,
    SecurityAuditWorkflow,
    format_security_report,
)

# ============================================================================
# Constants and Patterns Tests
# ============================================================================


@pytest.mark.unit
class TestSecurityAuditConstants:
    """Tests for security audit constants and patterns."""

    def test_skip_directories_contains_common_excludes(self):
        """Verify SKIP_DIRECTORIES includes common build/vendor directories."""
        expected_dirs = [".git", "node_modules", "__pycache__", "venv", "dist", "build"]
        for dir_name in expected_dirs:
            assert dir_name in SKIP_DIRECTORIES, f"Expected {dir_name} in SKIP_DIRECTORIES"

    def test_detection_patterns_are_valid_regex(self):
        """Verify all DETECTION_PATTERNS are valid regex patterns."""
        import re

        for pattern in DETECTION_PATTERNS:
            try:
                re.compile(pattern)
            except re.error as e:
                pytest.fail(f"Invalid regex pattern '{pattern}': {e}")

    def test_fake_credential_patterns_are_valid_regex(self):
        """Verify all FAKE_CREDENTIAL_PATTERNS are valid regex patterns."""
        import re

        for pattern in FAKE_CREDENTIAL_PATTERNS:
            try:
                re.compile(pattern)
            except re.error as e:
                pytest.fail(f"Invalid regex pattern '{pattern}': {e}")

    def test_security_patterns_have_required_keys(self):
        """Verify SECURITY_PATTERNS entries have required structure."""
        required_keys = ["patterns", "severity", "owasp"]
        for vuln_type, info in SECURITY_PATTERNS.items():
            for key in required_keys:
                assert key in info, f"Missing '{key}' in SECURITY_PATTERNS['{vuln_type}']"
            assert info["severity"] in [
                "critical",
                "high",
                "medium",
                "low",
            ], f"Invalid severity in {vuln_type}"
            assert isinstance(info["patterns"], list), f"patterns should be list in {vuln_type}"

    def test_security_steps_remediate_config(self):
        """Verify SECURITY_STEPS has remediate configuration."""
        assert "remediate" in SECURITY_STEPS
        assert SECURITY_STEPS["remediate"].name == "remediate"
        assert SECURITY_STEPS["remediate"].tier_hint == "premium"

    def test_test_file_patterns_are_valid_regex(self):
        """Verify all TEST_FILE_PATTERNS are valid regex patterns."""
        import re

        for pattern in TEST_FILE_PATTERNS:
            try:
                re.compile(pattern)
            except re.error as e:
                pytest.fail(f"Invalid regex pattern '{pattern}': {e}")


# ============================================================================
# Workflow Initialization Tests
# ============================================================================


@pytest.mark.unit
class TestSecurityAuditWorkflowInit:
    """Tests for SecurityAuditWorkflow initialization."""

    def test_workflow_attributes(self, security_audit_workflow):
        """Verify workflow has correct class attributes."""
        assert security_audit_workflow.name == "security-audit"
        assert security_audit_workflow.description
        assert "triage" in security_audit_workflow.stages
        assert "analyze" in security_audit_workflow.stages
        assert "assess" in security_audit_workflow.stages
        assert "remediate" in security_audit_workflow.stages

    def test_tier_map_configuration(self, security_audit_workflow):
        """Verify tier map assigns correct model tiers."""
        assert security_audit_workflow.tier_map["triage"] == ModelTier.CHEAP
        assert security_audit_workflow.tier_map["analyze"] == ModelTier.CAPABLE
        assert security_audit_workflow.tier_map["assess"] == ModelTier.CAPABLE
        assert security_audit_workflow.tier_map["remediate"] == ModelTier.PREMIUM

    def test_crew_configuration(self):
        """Verify crew configuration options."""
        workflow = SecurityAuditWorkflow(
            use_crew_for_assessment=True,
            use_crew_for_remediation=True,
            crew_config={"scan_depth": "deep"},
        )
        assert workflow.use_crew_for_assessment is True
        assert workflow.use_crew_for_remediation is True
        assert workflow.crew_config == {"scan_depth": "deep"}

    def test_team_decisions_loading_from_file(self, tmp_path):
        """Test loading team decisions from JSON file."""
        # Create patterns/security/team_decisions.json
        security_dir = tmp_path / "patterns" / "security"
        security_dir.mkdir(parents=True)
        decisions_file = security_dir / "team_decisions.json"
        decisions_file.write_text(
            json.dumps(
                {
                    "decisions": [
                        {
                            "finding_hash": "test_hash",
                            "decision": "false_positive",
                            "reason": "Test pattern",
                            "decided_by": "test_user",
                        }
                    ]
                }
            )
        )

        workflow = SecurityAuditWorkflow(patterns_dir=str(tmp_path / "patterns"))
        assert "test_hash" in workflow._team_decisions
        assert workflow._team_decisions["test_hash"]["decision"] == "false_positive"

    def test_team_decisions_handles_missing_file(self, tmp_path):
        """Test handling of missing team_decisions.json."""
        workflow = SecurityAuditWorkflow(patterns_dir=str(tmp_path / "nonexistent"))
        assert workflow._team_decisions == {}

    def test_team_decisions_handles_invalid_json(self, tmp_path):
        """Test handling of invalid JSON in team_decisions.json."""
        security_dir = tmp_path / "patterns" / "security"
        security_dir.mkdir(parents=True)
        decisions_file = security_dir / "team_decisions.json"
        decisions_file.write_text("invalid json{}")

        workflow = SecurityAuditWorkflow(patterns_dir=str(tmp_path / "patterns"))
        assert workflow._team_decisions == {}


# ============================================================================
# Triage Stage Tests
# ============================================================================


@pytest.mark.unit
class TestTriageStage:
    """Tests for the _triage stage."""

    @pytest.mark.asyncio
    async def test_triage_scans_python_files(self, security_audit_workflow, tmp_path):
        """Test triage scans Python files for vulnerabilities."""
        # Create a vulnerable Python file
        vuln_file = tmp_path / "vulnerable.py"
        vuln_file.write_text('result = eval(user_input)\npassword = "secret123"')

        input_data = {"path": str(tmp_path), "file_types": [".py"]}
        result, input_tokens, output_tokens = await security_audit_workflow._triage(
            input_data, ModelTier.CHEAP
        )

        assert result["files_scanned"] >= 1
        assert "findings" in result

    @pytest.mark.asyncio
    async def test_triage_skips_excluded_directories(self, security_audit_workflow, tmp_path):
        """Test triage skips directories in SKIP_DIRECTORIES."""
        # Create node_modules with a "vulnerable" file
        node_modules = tmp_path / "node_modules"
        node_modules.mkdir()
        (node_modules / "vulnerable.py").write_text("eval(user_input)")

        # Create a safe file in main directory
        (tmp_path / "safe.py").write_text("print('hello')")

        input_data = {"path": str(tmp_path), "file_types": [".py"]}
        result, _, _ = await security_audit_workflow._triage(input_data, ModelTier.CHEAP)

        # Should scan safe.py but not node_modules/vulnerable.py
        assert result["files_scanned"] >= 1
        # Findings should not include node_modules paths
        for finding in result.get("findings", []):
            assert "node_modules" not in finding.get("file", "")

    @pytest.mark.asyncio
    async def test_triage_handles_nonexistent_path(self, security_audit_workflow, tmp_path):
        """Test triage handles nonexistent path gracefully."""
        input_data = {"path": str(tmp_path / "nonexistent"), "file_types": [".py"]}
        result, _, _ = await security_audit_workflow._triage(input_data, ModelTier.CHEAP)

        assert result["files_scanned"] == 0
        assert result["findings"] == []

    @pytest.mark.asyncio
    async def test_triage_detects_sql_injection(self, security_audit_workflow, tmp_path):
        """Test triage detects SQL injection patterns."""
        vuln_file = tmp_path / "db.py"
        vuln_file.write_text('cursor.execute(f"SELECT * FROM users WHERE id={user_id}")')

        input_data = {"path": str(tmp_path), "file_types": [".py"]}
        result, _, _ = await security_audit_workflow._triage(input_data, ModelTier.CHEAP)

        sql_findings = [f for f in result["findings"] if f["type"] == "sql_injection"]
        assert len(sql_findings) >= 1

    @pytest.mark.asyncio
    async def test_triage_detects_command_injection(self, security_audit_workflow, tmp_path):
        """Test triage detects command injection patterns."""
        vuln_file = tmp_path / "shell.py"
        vuln_file.write_text("subprocess.call(cmd, shell=True)")

        input_data = {"path": str(tmp_path), "file_types": [".py"]}
        result, _, _ = await security_audit_workflow._triage(input_data, ModelTier.CHEAP)

        cmd_findings = [f for f in result["findings"] if f["type"] == "command_injection"]
        assert len(cmd_findings) >= 1

    @pytest.mark.asyncio
    async def test_triage_marks_test_files_as_low_severity(
        self, security_audit_workflow, tmp_path
    ):
        """Test triage marks findings in test files as low severity."""
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        test_file = tests_dir / "test_example.py"
        test_file.write_text("eval(user_input)  # Testing eval behavior")

        input_data = {"path": str(tmp_path), "file_types": [".py"]}
        result, _, _ = await security_audit_workflow._triage(input_data, ModelTier.CHEAP)

        test_findings = [f for f in result["findings"] if "tests" in f.get("file", "")]
        for finding in test_findings:
            assert finding.get("is_test") is True or finding.get("severity") == "low"

    @pytest.mark.asyncio
    async def test_triage_returns_token_estimates(self, security_audit_workflow, tmp_path):
        """Test triage returns token estimates for cost tracking."""
        (tmp_path / "example.py").write_text("print('hello')")

        input_data = {"path": str(tmp_path), "file_types": [".py"]}
        result, input_tokens, output_tokens = await security_audit_workflow._triage(
            input_data, ModelTier.CHEAP
        )

        assert isinstance(input_tokens, int)
        assert isinstance(output_tokens, int)
        assert input_tokens >= 0
        assert output_tokens >= 0


# ============================================================================
# Analyze Stage Tests
# ============================================================================


@pytest.mark.unit
class TestAnalyzeStage:
    """Tests for the _analyze stage."""

    @pytest.mark.asyncio
    async def test_analyze_categorizes_findings(self, security_audit_workflow):
        """Test analyze categorizes findings by status."""
        input_data = {
            "findings": [
                {"type": "sql_injection", "file": "db.py", "line": 10, "severity": "critical"},
                {"type": "xss", "file": "web.py", "line": 20, "severity": "high"},
            ]
        }

        result, _, _ = await security_audit_workflow._analyze(input_data, ModelTier.CAPABLE)

        assert "needs_review" in result
        assert "false_positives" in result
        assert "accepted_risks" in result
        assert result["review_count"] == 2

    @pytest.mark.asyncio
    async def test_analyze_applies_team_decisions(self, tmp_path):
        """Test analyze applies team decisions to filter findings."""
        # Create team decisions file
        security_dir = tmp_path / "patterns" / "security"
        security_dir.mkdir(parents=True)
        (security_dir / "team_decisions.json").write_text(
            json.dumps(
                {
                    "decisions": [
                        {
                            "finding_hash": "sql_injection",
                            "decision": "false_positive",
                            "reason": "Parameter is validated",
                            "decided_by": "security_team",
                        }
                    ]
                }
            )
        )

        workflow = SecurityAuditWorkflow(patterns_dir=str(tmp_path / "patterns"))

        input_data = {
            "findings": [
                {"type": "sql_injection", "file": "db.py", "line": 10, "severity": "critical"},
            ]
        }

        result, _, _ = await workflow._analyze(input_data, ModelTier.CAPABLE)

        # SQL injection should be marked as false positive
        assert len(result["false_positives"]) == 1
        assert result["false_positives"][0]["status"] == "false_positive"

    @pytest.mark.asyncio
    async def test_analyze_adds_analysis_to_needs_review(self, security_audit_workflow):
        """Test analyze adds analysis text to findings needing review."""
        input_data = {
            "findings": [
                {"type": "sql_injection", "file": "db.py", "line": 10, "severity": "critical"},
            ]
        }

        result, _, _ = await security_audit_workflow._analyze(input_data, ModelTier.CAPABLE)

        needs_review = result["needs_review"]
        assert len(needs_review) == 1
        assert "analysis" in needs_review[0]
        assert needs_review[0]["analysis"]  # Non-empty analysis

    @pytest.mark.asyncio
    async def test_analyze_handles_accepted_risk_decision(self, tmp_path):
        """Test analyze handles accepted risk decisions."""
        security_dir = tmp_path / "patterns" / "security"
        security_dir.mkdir(parents=True)
        (security_dir / "team_decisions.json").write_text(
            json.dumps(
                {
                    "decisions": [
                        {
                            "finding_hash": "insecure_random",
                            "decision": "accepted",
                            "reason": "Used only for non-security purposes",
                        }
                    ]
                }
            )
        )

        workflow = SecurityAuditWorkflow(patterns_dir=str(tmp_path / "patterns"))

        input_data = {
            "findings": [
                {"type": "insecure_random", "file": "utils.py", "line": 5, "severity": "medium"},
            ]
        }

        result, _, _ = await workflow._analyze(input_data, ModelTier.CAPABLE)

        assert len(result["accepted_risks"]) == 1
        assert result["accepted_risks"][0]["status"] == "accepted_risk"

    @pytest.mark.asyncio
    async def test_analyze_handles_deferred_decision(self, tmp_path):
        """Test analyze handles deferred decisions."""
        security_dir = tmp_path / "patterns" / "security"
        security_dir.mkdir(parents=True)
        (security_dir / "team_decisions.json").write_text(
            json.dumps(
                {
                    "decisions": [
                        {
                            "finding_hash": "path_traversal",
                            "decision": "deferred",
                            "reason": "Will fix in Q2",
                        }
                    ]
                }
            )
        )

        workflow = SecurityAuditWorkflow(patterns_dir=str(tmp_path / "patterns"))

        input_data = {
            "findings": [
                {"type": "path_traversal", "file": "files.py", "line": 15, "severity": "high"},
            ]
        }

        result, _, _ = await workflow._analyze(input_data, ModelTier.CAPABLE)

        analyzed = result["analyzed_findings"]
        assert any(f["status"] == "deferred" for f in analyzed)


# ============================================================================
# Assess Stage Tests
# ============================================================================


@pytest.mark.unit
class TestAssessStage:
    """Tests for the _assess stage."""

    @pytest.mark.asyncio
    async def test_assess_calculates_risk_score(self, security_audit_workflow):
        """Test assess calculates risk score correctly."""
        input_data = {
            "needs_review": [
                {"type": "sql_injection", "severity": "critical", "owasp": "A03:2021"},
                {"type": "xss", "severity": "high", "owasp": "A03:2021"},
                {"type": "insecure_random", "severity": "medium", "owasp": "A02:2021"},
            ]
        }

        result, _, _ = await security_audit_workflow._assess(input_data, ModelTier.CAPABLE)

        assessment = result["assessment"]
        # 1 critical (25) + 1 high (10) + 1 medium (3) = 38
        assert assessment["risk_score"] == 38
        assert assessment["risk_level"] == "medium"

    @pytest.mark.asyncio
    async def test_assess_severity_breakdown(self, security_audit_workflow):
        """Test assess provides severity breakdown."""
        input_data = {
            "needs_review": [
                {"type": "sql_injection", "severity": "critical", "owasp": "A03:2021"},
                {"type": "xss", "severity": "high", "owasp": "A03:2021"},
                {"type": "xss2", "severity": "high", "owasp": "A03:2021"},
                {"type": "insecure_random", "severity": "medium", "owasp": "A02:2021"},
                {"type": "info", "severity": "low", "owasp": "Other"},
            ]
        }

        result, _, _ = await security_audit_workflow._assess(input_data, ModelTier.CAPABLE)

        breakdown = result["assessment"]["severity_breakdown"]
        assert breakdown["critical"] == 1
        assert breakdown["high"] == 2
        assert breakdown["medium"] == 1
        assert breakdown["low"] == 1

    @pytest.mark.asyncio
    async def test_assess_sets_has_critical_flag(self, security_audit_workflow):
        """Test assess sets _has_critical flag for skip logic."""
        input_data = {
            "needs_review": [
                {"type": "sql_injection", "severity": "critical", "owasp": "A03:2021"},
            ]
        }

        await security_audit_workflow._assess(input_data, ModelTier.CAPABLE)

        assert security_audit_workflow._has_critical is True

    @pytest.mark.asyncio
    async def test_assess_no_critical_flag_when_clean(self, security_audit_workflow):
        """Test assess does not set _has_critical when no critical/high findings."""
        input_data = {
            "needs_review": [
                {"type": "insecure_random", "severity": "medium", "owasp": "A02:2021"},
                {"type": "info", "severity": "low", "owasp": "Other"},
            ]
        }

        await security_audit_workflow._assess(input_data, ModelTier.CAPABLE)

        assert security_audit_workflow._has_critical is False

    @pytest.mark.asyncio
    async def test_assess_groups_by_owasp_category(self, security_audit_workflow):
        """Test assess groups findings by OWASP category."""
        input_data = {
            "needs_review": [
                {"type": "sql_injection", "severity": "critical", "owasp": "A03:2021 Injection"},
                {"type": "xss", "severity": "high", "owasp": "A03:2021 Injection"},
                {
                    "type": "hardcoded_secret",
                    "severity": "critical",
                    "owasp": "A02:2021 Crypto",
                },
            ]
        }

        result, _, _ = await security_audit_workflow._assess(input_data, ModelTier.CAPABLE)

        by_owasp = result["assessment"]["by_owasp_category"]
        assert by_owasp.get("A03:2021 Injection") == 2
        assert by_owasp.get("A02:2021 Crypto") == 1

    @pytest.mark.asyncio
    async def test_assess_risk_level_thresholds(self, security_audit_workflow):
        """Test assess assigns correct risk levels based on score."""
        # Critical: score >= 75
        critical_input = {
            "needs_review": [
                {"type": "a", "severity": "critical", "owasp": "A"},
                {"type": "b", "severity": "critical", "owasp": "A"},
                {"type": "c", "severity": "critical", "owasp": "A"},
            ]
        }  # 75 points
        result, _, _ = await security_audit_workflow._assess(critical_input, ModelTier.CAPABLE)
        assert result["assessment"]["risk_level"] == "critical"

        # High: score >= 50
        high_input = {
            "needs_review": [
                {"type": "a", "severity": "critical", "owasp": "A"},
                {"type": "b", "severity": "critical", "owasp": "A"},
            ]
        }  # 50 points
        result, _, _ = await security_audit_workflow._assess(high_input, ModelTier.CAPABLE)
        assert result["assessment"]["risk_level"] == "high"

        # Low: score < 25
        low_input = {
            "needs_review": [
                {"type": "a", "severity": "low", "owasp": "A"},
            ]
        }  # 1 point
        result, _, _ = await security_audit_workflow._assess(low_input, ModelTier.CAPABLE)
        assert result["assessment"]["risk_level"] == "low"

    @pytest.mark.asyncio
    async def test_assess_includes_formatted_report(self, security_audit_workflow):
        """Test assess includes formatted report in output."""
        input_data = {
            "needs_review": [
                {"type": "sql_injection", "severity": "critical", "owasp": "A03:2021"},
            ]
        }

        result, _, _ = await security_audit_workflow._assess(input_data, ModelTier.CAPABLE)

        assert "formatted_report" in result
        assert "SECURITY AUDIT REPORT" in result["formatted_report"]


# ============================================================================
# Helper Method Tests
# ============================================================================


@pytest.mark.unit
class TestHelperMethods:
    """Tests for helper methods."""

    def test_analyze_finding_returns_analysis_for_known_types(self, security_audit_workflow):
        """Test _analyze_finding returns appropriate analysis."""
        vuln_types = [
            "sql_injection",
            "xss",
            "hardcoded_secret",
            "insecure_random",
            "path_traversal",
            "command_injection",
        ]

        for vuln_type in vuln_types:
            finding = {"type": vuln_type}
            analysis = security_audit_workflow._analyze_finding(finding)
            assert analysis  # Non-empty string
            assert isinstance(analysis, str)

    def test_analyze_finding_returns_default_for_unknown_type(self, security_audit_workflow):
        """Test _analyze_finding returns default for unknown vulnerability type."""
        finding = {"type": "unknown_vulnerability"}
        analysis = security_audit_workflow._analyze_finding(finding)
        assert "Review for security implications" in analysis

    def test_get_remediation_action_for_known_types(self, security_audit_workflow):
        """Test _get_remediation_action returns remediation for known types."""
        vuln_types = [
            "sql_injection",
            "xss",
            "hardcoded_secret",
            "insecure_random",
            "path_traversal",
            "command_injection",
        ]

        for vuln_type in vuln_types:
            finding = {"type": vuln_type}
            action = security_audit_workflow._get_remediation_action(finding)
            assert action  # Non-empty string
            assert isinstance(action, str)

    def test_get_remediation_action_for_unknown_type(self, security_audit_workflow):
        """Test _get_remediation_action returns default for unknown type."""
        finding = {"type": "unknown"}
        action = security_audit_workflow._get_remediation_action(finding)
        assert "security best practices" in action


# ============================================================================
# Run Stage Router Tests
# ============================================================================


@pytest.mark.unit
class TestRunStageRouter:
    """Tests for run_stage method routing."""

    @pytest.mark.asyncio
    async def test_run_stage_routes_to_triage(self, security_audit_workflow, tmp_path):
        """Test run_stage routes 'triage' to _triage method."""
        (tmp_path / "test.py").write_text("print('hello')")
        input_data = {"path": str(tmp_path)}

        result, _, _ = await security_audit_workflow.run_stage(
            "triage", ModelTier.CHEAP, input_data
        )

        assert "findings" in result
        assert "files_scanned" in result

    @pytest.mark.asyncio
    async def test_run_stage_routes_to_analyze(self, security_audit_workflow):
        """Test run_stage routes 'analyze' to _analyze method."""
        input_data = {"findings": []}

        result, _, _ = await security_audit_workflow.run_stage(
            "analyze", ModelTier.CAPABLE, input_data
        )

        assert "needs_review" in result
        assert "analyzed_findings" in result

    @pytest.mark.asyncio
    async def test_run_stage_routes_to_assess(self, security_audit_workflow):
        """Test run_stage routes 'assess' to _assess method."""
        input_data = {"needs_review": []}

        result, _, _ = await security_audit_workflow.run_stage(
            "assess", ModelTier.CAPABLE, input_data
        )

        assert "assessment" in result

    @pytest.mark.asyncio
    async def test_run_stage_raises_for_unknown_stage(self, security_audit_workflow):
        """Test run_stage raises ValueError for unknown stage."""
        with pytest.raises(ValueError, match="Unknown stage"):
            await security_audit_workflow.run_stage("unknown", ModelTier.CHEAP, {})


# ============================================================================
# Format Report Tests
# ============================================================================


@pytest.mark.unit
class TestFormatSecurityReport:
    """Tests for format_security_report function."""

    def test_format_report_includes_header(self):
        """Test format_security_report includes header."""
        output = {"assessment": {"risk_level": "high", "risk_score": 50}}
        report = format_security_report(output)

        assert "SECURITY AUDIT REPORT" in report
        assert "Risk Level: HIGH" in report
        assert "Risk Score: 50/100" in report

    def test_format_report_includes_severity_summary(self):
        """Test format_security_report includes severity summary."""
        output = {
            "assessment": {
                "risk_level": "medium",
                "risk_score": 30,
                "severity_breakdown": {"critical": 1, "high": 2, "medium": 3, "low": 4},
            }
        }
        report = format_security_report(output)

        assert "Severity Summary:" in report
        assert "Critical: 1" in report
        assert "High: 2" in report
        assert "Medium: 3" in report
        assert "Low: 4" in report

    def test_format_report_includes_findings(self):
        """Test format_security_report includes findings."""
        output = {
            "assessment": {"risk_level": "high", "risk_score": 50, "severity_breakdown": {}},
            "needs_review": [
                {
                    "type": "sql_injection",
                    "file": "/path/to/Empathy-framework/db.py",
                    "line": 10,
                    "match": "cursor.execute(f'SELECT...')",
                    "severity": "critical",
                    "owasp": "A03:2021 Injection",
                    "analysis": "SQL injection risk",
                }
            ],
        }
        report = format_security_report(output)

        assert "FINDINGS REQUIRING REVIEW" in report
        assert "sql_injection" in report
        assert "db.py:10" in report

    def test_format_report_includes_accepted_risks(self):
        """Test format_security_report includes accepted risks."""
        output = {
            "assessment": {"risk_level": "low", "risk_score": 5, "severity_breakdown": {}},
            "accepted_risks": [
                {
                    "type": "insecure_random",
                    "file": "/path/utils.py",
                    "line": 5,
                    "decision_reason": "Non-security use",
                }
            ],
        }
        report = format_security_report(output)

        assert "ACCEPTED RISKS" in report
        assert "insecure_random" in report

    def test_format_report_includes_remediation_plan(self):
        """Test format_security_report includes remediation plan."""
        output = {
            "assessment": {"risk_level": "high", "risk_score": 50, "severity_breakdown": {}},
            "remediation_plan": "Fix the SQL injection by using parameterized queries.",
        }
        report = format_security_report(output)

        assert "REMEDIATION PLAN" in report
        assert "parameterized queries" in report

    def test_format_report_action_required_when_findings(self):
        """Test format_security_report shows action required when findings exist."""
        output = {
            "assessment": {"risk_level": "high", "risk_score": 50, "severity_breakdown": {}},
            "needs_review": [{"type": "xss"}],
        }
        report = format_security_report(output)

        assert "ACTION REQUIRED" in report

    def test_format_report_all_clear_when_no_findings(self):
        """Test format_security_report shows all clear when no findings."""
        output = {
            "assessment": {"risk_level": "low", "risk_score": 0, "severity_breakdown": {}},
            "needs_review": [],
        }
        report = format_security_report(output)

        assert "All clear" in report or "STATUS:" in report

    def test_format_report_handles_missing_fields(self):
        """Test format_security_report handles missing optional fields."""
        output = {"assessment": {"risk_level": "unknown", "risk_score": 0}}
        report = format_security_report(output)

        # Should not raise an error
        assert "SECURITY AUDIT REPORT" in report


# ============================================================================
# Crew Integration Tests
# ============================================================================


@pytest.mark.unit
class TestCrewIntegration:
    """Tests for SecurityAuditCrew integration."""

    @pytest.mark.asyncio
    async def test_crew_not_available_state(self):
        """Test workflow works when crew is not available."""
        # Create a fresh workflow and simulate crew being unavailable
        workflow = SecurityAuditWorkflow()
        workflow._crew = None
        workflow._crew_available = False

        # Verify the workflow can still function
        assert workflow._crew_available is False
        assert workflow._crew is None

        # The workflow should still work for non-crew operations
        input_data = {
            "needs_review": [{"type": "xss", "severity": "high", "owasp": "A03:2021"}]
        }
        result, _, _ = await workflow._assess(input_data, ModelTier.CAPABLE)
        assert result["assessment"]["crew_enhanced"] is False

    @pytest.mark.asyncio
    async def test_assess_without_crew(self, security_audit_workflow):
        """Test assess works without crew available."""
        security_audit_workflow.use_crew_for_assessment = False

        input_data = {
            "needs_review": [{"type": "xss", "severity": "high", "owasp": "A03:2021"}]
        }

        result, _, _ = await security_audit_workflow._assess(input_data, ModelTier.CAPABLE)

        assert result["assessment"]["crew_enhanced"] is False

    def test_merge_crew_remediation_adds_section(self, security_audit_workflow):
        """Test _merge_crew_remediation adds crew section to response."""
        llm_response = "Original LLM remediation plan."
        crew_remediation = {
            "findings": [
                {
                    "title": "SQL Injection",
                    "severity": "critical",
                    "remediation": "Use prepared statements",
                    "cwe_id": "CWE-89",
                    "cvss_score": 9.8,
                }
            ],
            "agents_used": ["Scanner", "Analyzer", "Remediator"],
        }

        result = security_audit_workflow._merge_crew_remediation(llm_response, crew_remediation)

        assert "Original LLM remediation plan" in result
        assert "Enhanced Remediation (SecurityAuditCrew)" in result
        assert "SQL Injection" in result
        assert "CWE-89" in result
        assert "Scanner, Analyzer, Remediator" in result

    def test_merge_crew_remediation_empty_findings(self, security_audit_workflow):
        """Test _merge_crew_remediation handles empty findings."""
        llm_response = "Original plan."
        crew_remediation = {"findings": [], "agents_used": []}

        result = security_audit_workflow._merge_crew_remediation(llm_response, crew_remediation)

        # Should return original unchanged
        assert result == "Original plan."


# ============================================================================
# Remediate Stage Tests
# ============================================================================


@pytest.mark.unit
class TestRemediateStage:
    """Tests for the _remediate stage."""

    @pytest.mark.asyncio
    async def test_remediate_builds_findings_summary(self, security_audit_workflow):
        """Test remediate builds findings summary for LLM."""
        # Mock _call_llm to capture the prompt
        with patch.object(
            security_audit_workflow, "_call_llm", new_callable=AsyncMock
        ) as mock_llm:
            mock_llm.return_value = ("Remediation plan here", 100, 200)

            input_data = {
                "assessment": {
                    "risk_score": 50,
                    "risk_level": "high",
                    "severity_breakdown": {"critical": 1, "high": 1},
                    "critical_findings": [
                        {
                            "type": "sql_injection",
                            "file": "db.py",
                            "line": 10,
                            "owasp": "A03:2021",
                        }
                    ],
                    "high_findings": [
                        {"type": "xss", "file": "web.py", "line": 20, "owasp": "A03:2021"}
                    ],
                },
                "target": "./src",
            }

            result, input_tokens, output_tokens = await security_audit_workflow._remediate(
                input_data, ModelTier.PREMIUM
            )

            assert "remediation_plan" in result
            assert result["remediation_count"] == 2
            assert result["risk_score"] == 50
            assert result["risk_level"] == "high"

    @pytest.mark.asyncio
    async def test_remediate_returns_token_counts(self, security_audit_workflow):
        """Test remediate returns token counts for cost tracking."""
        with patch.object(
            security_audit_workflow, "_call_llm", new_callable=AsyncMock
        ) as mock_llm:
            mock_llm.return_value = ("Plan", 150, 300)

            input_data = {
                "assessment": {
                    "risk_score": 25,
                    "risk_level": "medium",
                    "severity_breakdown": {},
                    "critical_findings": [],
                    "high_findings": [],
                }
            }

            result, input_tokens, output_tokens = await security_audit_workflow._remediate(
                input_data, ModelTier.PREMIUM
            )

            assert input_tokens == 150
            assert output_tokens == 300

    @pytest.mark.asyncio
    async def test_remediate_uses_executor_when_available(self, security_audit_workflow):
        """Test remediate uses executor when available."""
        # Create mock executor
        mock_executor = MagicMock()
        security_audit_workflow._executor = mock_executor
        security_audit_workflow._api_key = "test-key"

        with patch.object(
            security_audit_workflow, "run_step_with_executor", new_callable=AsyncMock
        ) as mock_run:
            mock_run.return_value = ("Executor plan", 100, 200, 0.05)

            input_data = {
                "assessment": {
                    "risk_score": 50,
                    "risk_level": "high",
                    "severity_breakdown": {},
                    "critical_findings": [],
                    "high_findings": [],
                }
            }

            result, _, _ = await security_audit_workflow._remediate(
                input_data, ModelTier.PREMIUM
            )

            mock_run.assert_called_once()
            assert "Executor plan" in result["remediation_plan"]

    @pytest.mark.asyncio
    async def test_remediate_falls_back_to_call_llm_on_executor_failure(
        self, security_audit_workflow
    ):
        """Test remediate falls back to _call_llm when executor fails."""
        security_audit_workflow._executor = MagicMock()
        security_audit_workflow._api_key = "test-key"

        with patch.object(
            security_audit_workflow, "run_step_with_executor", new_callable=AsyncMock
        ) as mock_run:
            mock_run.side_effect = Exception("Executor failed")

            with patch.object(
                security_audit_workflow, "_call_llm", new_callable=AsyncMock
            ) as mock_llm:
                mock_llm.return_value = ("Fallback plan", 50, 100)

                input_data = {
                    "assessment": {
                        "risk_score": 30,
                        "risk_level": "medium",
                        "severity_breakdown": {},
                        "critical_findings": [],
                        "high_findings": [],
                    }
                }

                result, _, _ = await security_audit_workflow._remediate(
                    input_data, ModelTier.PREMIUM
                )

                mock_llm.assert_called_once()
                assert "Fallback plan" in result["remediation_plan"]

    @pytest.mark.asyncio
    async def test_remediate_with_no_findings(self, security_audit_workflow):
        """Test remediate handles case with no critical/high findings."""
        with patch.object(
            security_audit_workflow, "_call_llm", new_callable=AsyncMock
        ) as mock_llm:
            mock_llm.return_value = ("No issues to remediate", 50, 100)

            input_data = {
                "assessment": {
                    "risk_score": 5,
                    "risk_level": "low",
                    "severity_breakdown": {"low": 2},
                    "critical_findings": [],
                    "high_findings": [],
                }
            }

            result, _, _ = await security_audit_workflow._remediate(
                input_data, ModelTier.PREMIUM
            )

            assert result["remediation_count"] == 0

    @pytest.mark.asyncio
    async def test_run_stage_routes_to_remediate(self, security_audit_workflow):
        """Test run_stage routes 'remediate' to _remediate method."""
        with patch.object(
            security_audit_workflow, "_call_llm", new_callable=AsyncMock
        ) as mock_llm:
            mock_llm.return_value = ("Plan", 50, 100)

            input_data = {
                "assessment": {
                    "risk_score": 50,
                    "risk_level": "high",
                    "severity_breakdown": {},
                    "critical_findings": [],
                    "high_findings": [],
                }
            }

            result, _, _ = await security_audit_workflow.run_stage(
                "remediate", ModelTier.PREMIUM, input_data
            )

            assert "remediation_plan" in result


# ============================================================================
# XML Prompt Tests
# ============================================================================


@pytest.mark.unit
class TestXMLPromptHandling:
    """Tests for XML-enhanced prompt handling."""

    @pytest.mark.asyncio
    async def test_remediate_uses_xml_when_enabled(self, security_audit_workflow):
        """Test remediate uses XML-enhanced prompts when enabled."""
        with patch.object(
            security_audit_workflow, "_is_xml_enabled", return_value=True
        ):
            with patch.object(
                security_audit_workflow, "_render_xml_prompt", return_value="<xml>prompt</xml>"
            ) as mock_render:
                with patch.object(
                    security_audit_workflow, "_call_llm", new_callable=AsyncMock
                ) as mock_llm:
                    mock_llm.return_value = ("XML response", 100, 200)

                    input_data = {
                        "assessment": {
                            "risk_score": 50,
                            "risk_level": "high",
                            "severity_breakdown": {},
                            "critical_findings": [],
                            "high_findings": [],
                        }
                    }

                    await security_audit_workflow._remediate(input_data, ModelTier.PREMIUM)

                    mock_render.assert_called_once()

    @pytest.mark.asyncio
    async def test_remediate_uses_legacy_prompt_when_xml_disabled(
        self, security_audit_workflow
    ):
        """Test remediate uses legacy prompts when XML is disabled."""
        with patch.object(
            security_audit_workflow, "_is_xml_enabled", return_value=False
        ):
            with patch.object(
                security_audit_workflow, "_call_llm", new_callable=AsyncMock
            ) as mock_llm:
                mock_llm.return_value = ("Legacy response", 100, 200)

                input_data = {
                    "assessment": {
                        "risk_score": 50,
                        "risk_level": "high",
                        "severity_breakdown": {},
                        "critical_findings": [],
                        "high_findings": [],
                    }
                }

                await security_audit_workflow._remediate(input_data, ModelTier.PREMIUM)

                # Verify _call_llm was called with non-None system prompt
                call_args = mock_llm.call_args
                system_prompt = call_args[0][1]  # Second positional arg
                assert system_prompt  # Non-empty system prompt for legacy mode
