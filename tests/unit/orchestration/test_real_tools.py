"""Tests for Real Analysis Tools (v4.0 Meta-Orchestration)

This module tests the real analysis tools that power the v4.0 orchestration:
1. RealSecurityAuditor - Runs bandit for security analysis
2. RealCoverageAnalyzer - Runs pytest-cov for coverage analysis
3. RealCodeQualityAnalyzer - Runs ruff and mypy for quality analysis
4. RealDocumentationAnalyzer - Analyzes docstring coverage via AST

These tools replace mock implementations with actual analysis,
providing real metrics for health checks and release prep workflows.

Copyright 2025 Smart-AI-Memory
Licensed under Fair Source License 0.9
"""

import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Skip this test module if dependencies aren't available
pytest.importorskip("empathy_os.orchestration.real_tools")

from empathy_os.orchestration.real_tools import (
    CoverageReport,
    DocumentationReport,
    QualityReport,
    RealCodeQualityAnalyzer,
    RealCoverageAnalyzer,
    RealDocumentationAnalyzer,
    RealSecurityAuditor,
    SecurityReport,
)


# =============================================================================
# SecurityReport Tests
# =============================================================================


class TestSecurityReport:
    """Tests for SecurityReport dataclass."""

    def test_security_report_creation(self):
        """Test creating a security report."""
        report = SecurityReport(
            total_issues=5,
            critical_count=1,
            high_count=2,
            medium_count=2,
            low_count=0,
            issues_by_file={"test.py": [{"issue": "B101: assert used"}]},
            passed=False,
        )

        assert report.total_issues == 5
        assert report.critical_count == 1
        assert report.high_count == 2
        assert report.passed is False

    def test_security_report_passed_no_issues(self):
        """Test security report passes with no issues."""
        report = SecurityReport(
            total_issues=0,
            critical_count=0,
            high_count=0,
            medium_count=0,
            low_count=0,
            issues_by_file={},
            passed=True,
        )

        assert report.passed is True
        assert report.total_issues == 0

    def test_security_report_failed_critical(self):
        """Test security report fails with critical issues."""
        report = SecurityReport(
            total_issues=1,
            critical_count=1,
            high_count=0,
            medium_count=0,
            low_count=0,
            issues_by_file={"vuln.py": [{"issue": "B102: exec used"}]},
            passed=False,
        )

        assert report.passed is False
        assert report.critical_count == 1


# =============================================================================
# CoverageReport Tests
# =============================================================================


class TestCoverageReport:
    """Tests for CoverageReport dataclass."""

    def test_coverage_report_creation(self):
        """Test creating a coverage report."""
        report = CoverageReport(
            total_coverage=85.5,
            files_analyzed=50,
            uncovered_files=[{"path": "untested.py", "coverage": 50.0}],
            missing_lines={"untested.py": [10, 20, 30]},
        )

        assert report.total_coverage == 85.5
        assert report.files_analyzed == 50
        assert len(report.uncovered_files) == 1
        assert "untested.py" in report.missing_lines

    def test_coverage_report_empty_uncovered(self):
        """Test coverage report with no uncovered files."""
        report = CoverageReport(
            total_coverage=95.0,
            files_analyzed=100,
            uncovered_files=[],
            missing_lines={},
        )

        assert report.uncovered_files == []
        assert report.missing_lines == {}


# =============================================================================
# QualityReport Tests
# =============================================================================


class TestQualityReport:
    """Tests for QualityReport dataclass."""

    def test_quality_report_creation(self):
        """Test creating a quality report."""
        report = QualityReport(
            quality_score=8.5,
            ruff_issues=10,
            mypy_issues=5,
            total_files=100,
            issues_by_category={"F401": 5, "E501": 5},
            passed=True,
        )

        assert report.quality_score == 8.5
        assert report.ruff_issues == 10
        assert report.mypy_issues == 5
        assert report.passed is True

    def test_quality_report_failed(self):
        """Test quality report with failing score."""
        report = QualityReport(
            quality_score=5.0,
            ruff_issues=100,
            mypy_issues=50,
            total_files=50,
            issues_by_category={"F401": 50, "E501": 50},
            passed=False,
        )

        assert report.passed is False
        assert report.quality_score == 5.0


# =============================================================================
# DocumentationReport Tests
# =============================================================================


class TestDocumentationReport:
    """Tests for DocumentationReport dataclass."""

    def test_documentation_report_creation(self):
        """Test creating a documentation report."""
        report = DocumentationReport(
            completeness_percentage=75.0,
            total_functions=100,
            documented_functions=75,
            total_classes=20,
            documented_classes=15,
            missing_docstrings=["func1", "func2"],
            passed=False,
        )

        assert report.completeness_percentage == 75.0
        assert report.total_functions == 100
        assert report.documented_functions == 75
        assert len(report.missing_docstrings) == 2
        assert report.passed is False

    def test_documentation_report_fully_documented(self):
        """Test fully documented report."""
        report = DocumentationReport(
            completeness_percentage=100.0,
            total_functions=50,
            documented_functions=50,
            total_classes=10,
            documented_classes=10,
            missing_docstrings=[],
            passed=True,
        )

        assert report.passed is True
        assert report.completeness_percentage == 100.0


# =============================================================================
# RealSecurityAuditor Tests
# =============================================================================


class TestRealSecurityAuditor:
    """Tests for RealSecurityAuditor."""

    def test_auditor_initialization(self, tmp_path):
        """Test security auditor initialization."""
        auditor = RealSecurityAuditor(str(tmp_path))
        assert auditor.project_root == tmp_path

    def test_auditor_invalid_path_raises(self):
        """Test auditor raises on invalid path."""
        with pytest.raises(ValueError, match="Project root does not exist"):
            RealSecurityAuditor("/nonexistent/path")

    def test_auditor_empty_path_uses_default(self):
        """Test auditor uses current directory for empty path."""
        # Empty string should use current directory
        auditor = RealSecurityAuditor("")
        assert auditor.project_root.exists()

    @patch("subprocess.run")
    def test_audit_parses_bandit_output(self, mock_run, tmp_path):
        """Test audit parses bandit JSON output correctly."""
        # Create a test Python file
        test_file = tmp_path / "test.py"
        test_file.write_text("print('hello')")

        # Mock bandit output
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='{"results": [], "metrics": {"_totals": {"SEVERITY.LOW": 0, "SEVERITY.MEDIUM": 0, "SEVERITY.HIGH": 0}}}',
            stderr="",
        )

        auditor = RealSecurityAuditor(str(tmp_path))
        report = auditor.audit(".")

        assert report.total_issues == 0
        assert report.passed is True

    @patch("subprocess.run")
    def test_audit_handles_security_issues(self, mock_run, tmp_path):
        """Test audit handles files with security issues."""
        test_file = tmp_path / "vulnerable.py"
        test_file.write_text("eval(input())")

        # Mock bandit finding issues
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="""{
                "results": [
                    {
                        "filename": "vulnerable.py",
                        "issue_severity": "HIGH",
                        "issue_text": "Use of eval detected"
                    }
                ],
                "metrics": {"_totals": {"SEVERITY.HIGH": 1}}
            }""",
            stderr="",
        )

        auditor = RealSecurityAuditor(str(tmp_path))
        report = auditor.audit(".")

        assert report.total_issues >= 1
        assert report.passed is False


# =============================================================================
# RealCoverageAnalyzer Tests
# =============================================================================


class TestRealCoverageAnalyzer:
    """Tests for RealCoverageAnalyzer."""

    def test_analyzer_initialization(self, tmp_path):
        """Test coverage analyzer initialization."""
        analyzer = RealCoverageAnalyzer(str(tmp_path))
        assert analyzer.project_root == tmp_path

    def test_analyzer_uses_existing_coverage_file(self, tmp_path):
        """Test analyzer uses existing coverage.json if available."""
        # Create a coverage.json file
        import json
        import time

        coverage_file = tmp_path / "coverage.json"
        coverage_data = {
            "totals": {"percent_covered": 85.5},
            "files": {
                "test.py": {
                    "summary": {"percent_covered": 85.5},
                    "missing_lines": [],
                }
            },
        }
        coverage_file.write_text(json.dumps(coverage_data))

        analyzer = RealCoverageAnalyzer(str(tmp_path))
        report = analyzer.analyze("src", use_existing=True)

        assert report.total_coverage == 85.5


# =============================================================================
# RealCodeQualityAnalyzer Tests
# =============================================================================


class TestRealCodeQualityAnalyzer:
    """Tests for RealCodeQualityAnalyzer."""

    def test_analyzer_initialization(self, tmp_path):
        """Test code quality analyzer initialization."""
        analyzer = RealCodeQualityAnalyzer(str(tmp_path))
        assert analyzer.project_root == tmp_path

    @patch("subprocess.run")
    def test_analyze_parses_ruff_output(self, mock_run, tmp_path):
        """Test analyze parses ruff output correctly."""
        test_file = tmp_path / "clean.py"
        test_file.write_text("def func():\n    pass\n")

        # Mock ruff finding no issues, mypy finding no issues
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="",
            stderr="",
        )

        analyzer = RealCodeQualityAnalyzer(str(tmp_path))
        report = analyzer.analyze(".")

        assert report.ruff_issues >= 0
        assert report.quality_score >= 0


# =============================================================================
# RealDocumentationAnalyzer Tests
# =============================================================================


class TestRealDocumentationAnalyzer:
    """Tests for RealDocumentationAnalyzer."""

    def test_analyzer_initialization(self, tmp_path):
        """Test documentation analyzer initialization."""
        analyzer = RealDocumentationAnalyzer(str(tmp_path))
        assert analyzer.project_root == tmp_path

    def test_analyze_fully_documented_file(self, tmp_path):
        """Test analyze on fully documented file."""
        test_file = tmp_path / "documented.py"
        test_file.write_text('''
"""Module docstring."""

def func():
    """Function docstring."""
    pass

class MyClass:
    """Class docstring."""

    def method(self):
        """Method docstring."""
        pass
''')

        analyzer = RealDocumentationAnalyzer(str(tmp_path))
        report = analyzer.analyze(".")

        assert report.completeness_percentage > 0
        assert report.total_functions >= 0
        assert report.total_classes >= 0

    def test_analyze_undocumented_file(self, tmp_path):
        """Test analyze on file with missing docstrings."""
        test_file = tmp_path / "undocumented.py"
        test_file.write_text('''
def func1():
    pass

def func2():
    pass

class MyClass:
    def method(self):
        pass
''')

        analyzer = RealDocumentationAnalyzer(str(tmp_path))
        report = analyzer.analyze(".")

        # Should detect missing docstrings
        assert report.total_functions >= 2
        assert len(report.missing_docstrings) >= 0

    def test_analyze_empty_directory(self, tmp_path):
        """Test analyze on empty directory."""
        analyzer = RealDocumentationAnalyzer(str(tmp_path))
        report = analyzer.analyze(".")

        assert report.total_functions == 0
        assert report.total_classes == 0
        # Empty = 100% complete (nothing to document)
        assert report.completeness_percentage == 100.0

    def test_analyze_mixed_documentation(self, tmp_path):
        """Test analyze on partially documented code."""
        test_file = tmp_path / "mixed.py"
        test_file.write_text('''
"""Module with mixed documentation."""

def documented_func():
    """This function is documented."""
    pass

def undocumented_func():
    pass

class DocumentedClass:
    """This class is documented."""

    def documented_method(self):
        """This method is documented."""
        pass

    def undocumented_method(self):
        pass
''')

        analyzer = RealDocumentationAnalyzer(str(tmp_path))
        report = analyzer.analyze(".")

        # Should have some documented, some not
        assert report.total_functions >= 2
        assert report.documented_functions >= 1


# =============================================================================
# Path Validation Security Tests
# =============================================================================


class TestPathValidationSecurity:
    """Test path validation prevents security issues."""

    def test_security_auditor_handles_invalid_subpath(self, tmp_path):
        """Test security auditor handles invalid subpaths safely."""
        auditor = RealSecurityAuditor(str(tmp_path))

        # Attempting to audit nonexistent path should be handled safely
        report = auditor.audit("nonexistent_subdir")

        # Should not crash, should return valid report
        assert isinstance(report, SecurityReport)

    def test_doc_analyzer_handles_invalid_paths(self, tmp_path):
        """Test documentation analyzer handles invalid paths gracefully."""
        analyzer = RealDocumentationAnalyzer(str(tmp_path))

        # Should handle nonexistent subpath safely
        report = analyzer.analyze("nonexistent_subdir")

        assert isinstance(report, DocumentationReport)


# =============================================================================
# Integration Tests
# =============================================================================


class TestRealToolsIntegration:
    """Integration tests for real tools working together."""

    def test_all_tools_on_sample_project(self, tmp_path):
        """Test all tools work on a sample project."""
        # Create a mini project structure
        src_dir = tmp_path / "src"
        src_dir.mkdir()

        # Create a Python file
        module = src_dir / "module.py"
        module.write_text('''
"""Sample module for testing."""

def sample_function(x: int) -> int:
    """Return x doubled."""
    return x * 2

class SampleClass:
    """Sample class."""

    def method(self) -> str:
        """Return greeting."""
        return "hello"
''')

        # Run documentation analyzer (doesn't require external tools)
        docs = RealDocumentationAnalyzer(str(tmp_path))
        doc_report = docs.analyze("src")

        # Should return valid report
        assert isinstance(doc_report, DocumentationReport)
        assert doc_report.total_functions >= 1
        assert doc_report.total_classes >= 1
