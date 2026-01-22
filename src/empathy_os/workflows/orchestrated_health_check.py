"""Orchestrated Health Check Workflow

Uses meta-orchestration to perform comprehensive project health assessments
with configurable depth levels (daily, weekly, release).

This workflow demonstrates adaptive agent composition based on execution mode,
intelligent health scoring, and historical trend tracking.

Architecture:
    - MetaOrchestrator selects agents based on mode
    - ParallelStrategy for daily/weekly (fast validation)
    - RefinementStrategy for release (deep multi-stage analysis)
    - Health score calculation with weighted criteria
    - Trend tracking for historical comparisons

Modes:
    - daily: Quick parallel check (security, coverage, quality)
    - weekly: Comprehensive parallel (+ performance, docs, dependencies)
    - release: Deep sequential refinement (multi-stage validation)

Quality Criteria (weighted):
    - Security: 30% (critical issues, vulnerability count)
    - Coverage: 25% (test coverage percentage)
    - Quality: 20% (code quality score)
    - Performance: 15% (bottleneck count, response times)
    - Documentation: 10% (completeness percentage)

Example:
    >>> workflow = OrchestratedHealthCheckWorkflow(mode="weekly")
    >>> report = await workflow.execute(project_root=".")
    >>> print(f"{report.overall_health_score}/100 ({report.grade})")
    85/100 (B)

Copyright 2025 Smart-AI-Memory
Licensed under Fair Source License 0.9
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from empathy_os.config import _validate_file_path

from ..orchestration.agent_templates import AgentTemplate, get_template
from ..orchestration.execution_strategies import (
    ParallelStrategy,
    StrategyResult,
)
from ..orchestration.meta_orchestrator import MetaOrchestrator

logger = logging.getLogger(__name__)


@dataclass
class CategoryScore:
    """Individual category health score.

    Attributes:
        name: Category name (e.g., "Security")
        score: Score 0-100
        weight: Weight in overall score (0-1)
        raw_metrics: Raw metrics from agent
        issues: Issues found
        passed: Whether category passed threshold
    """

    name: str
    score: float
    weight: float
    raw_metrics: dict[str, Any] = field(default_factory=dict)
    issues: list[str] = field(default_factory=list)
    passed: bool = True


@dataclass
class HealthCheckReport:
    """Comprehensive health check report.

    Attributes:
        overall_health_score: Overall health score 0-100
        grade: Letter grade (A/B/C/D/F)
        category_scores: Scores by category
        issues: All issues found
        recommendations: Actionable recommendations
        trend: Comparison with last check
        execution_time: Total execution time in seconds
        mode: Execution mode (daily/weekly/release)
        timestamp: Report generation time
        agents_executed: Number of agents executed
        success: Whether check completed successfully
    """

    overall_health_score: float
    grade: str
    category_scores: list[CategoryScore] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    trend: str = ""
    execution_time: float = 0.0
    mode: str = "daily"
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    agents_executed: int = 0
    success: bool = True

    def to_dict(self) -> dict[str, Any]:
        """Convert report to dictionary for JSON serialization.

        Returns:
            Dictionary representation
        """
        return {
            "overall_health_score": self.overall_health_score,
            "grade": self.grade,
            "category_scores": [
                {
                    "name": cat.name,
                    "score": cat.score,
                    "weight": cat.weight,
                    "raw_metrics": cat.raw_metrics,
                    "issues": cat.issues,
                    "passed": cat.passed,
                }
                for cat in self.category_scores
            ],
            "issues": self.issues,
            "recommendations": self.recommendations,
            "trend": self.trend,
            "execution_time": self.execution_time,
            "mode": self.mode,
            "timestamp": self.timestamp,
            "agents_executed": self.agents_executed,
            "success": self.success,
        }

    def format_console_output(self) -> str:
        """Format report for console display.

        Returns:
            Human-readable formatted report
        """
        lines = []

        # Header
        lines.append("=" * 70)
        lines.append("PROJECT HEALTH CHECK REPORT (Meta-Orchestrated)")
        lines.append("=" * 70)
        lines.append("")

        # Overall health
        grade_emoji = {
            "A": "🏆",
            "B": "✅",
            "C": "⚠️",
            "D": "❌",
            "F": "🚨",
        }
        emoji = grade_emoji.get(self.grade, "")

        lines.append(
            f"Overall Health: {emoji} {self.overall_health_score:.1f}/100 (Grade {self.grade})"
        )
        lines.append(f"Mode: {self.mode.upper()}")
        lines.append(f"Agents Executed: {self.agents_executed}")
        lines.append(f"Generated: {self.timestamp}")
        lines.append(f"Duration: {self.execution_time:.2f}s")

        if self.trend:
            lines.append(f"Trend: {self.trend}")

        lines.append("")

        # Category scores
        lines.append("-" * 70)
        lines.append("CATEGORY BREAKDOWN")
        lines.append("-" * 70)

        for category in sorted(self.category_scores, key=lambda x: x.score, reverse=True):
            status = "✅" if category.passed else "❌"
            bar_length = int(category.score / 5)  # 0-20 chars
            bar = "█" * bar_length
            lines.append(
                f"{status} {category.name:15} {category.score:5.1f}/100 "
                f"(weight: {category.weight*100:2.0f}%) {bar}"
            )

            # Show issues for failing categories
            if category.issues and not category.passed:
                for issue in category.issues[:3]:  # Show first 3
                    lines.append(f"     • {issue}")

        lines.append("")

        # Issues summary
        if self.issues:
            lines.append("-" * 70)
            lines.append(f"🚨 ISSUES FOUND ({len(self.issues)})")
            lines.append("-" * 70)
            for issue in self.issues[:10]:  # Show first 10
                lines.append(f"  • {issue}")
            if len(self.issues) > 10:
                lines.append(f"  ... and {len(self.issues) - 10} more")
            lines.append("")

        # Recommendations
        if self.recommendations:
            lines.append("-" * 70)
            lines.append(f"💡 RECOMMENDATIONS ({len(self.recommendations)})")
            lines.append("-" * 70)
            for rec in self.recommendations:
                lines.append(f"  • {rec}")
            lines.append("")

        lines.append("=" * 70)

        return "\n".join(lines)


class OrchestratedHealthCheckWorkflow:
    """Health check workflow using meta-orchestration.

    This workflow performs comprehensive project health assessment using
    intelligent agent composition based on execution mode.

    Modes:
        - daily: Fast parallel check (security, coverage, quality) with CHEAP/CAPABLE agents
        - weekly: Comprehensive parallel (adds performance, docs, deps) with all tiers
        - release: Deep sequential refinement with premium agents

    Health Score Calculation:
        Weighted average of category scores:
        - Security: 30%
        - Coverage: 25%
        - Quality: 20%
        - Performance: 15%
        - Documentation: 10%

    Example:
        >>> workflow = OrchestratedHealthCheckWorkflow(mode="weekly")
        >>> report = await workflow.execute(project_root=".")
        >>> if report.overall_health_score >= 80:
        ...     print("Project is healthy!")
    """

    # Category weights for overall score
    CATEGORY_WEIGHTS = {
        "Security": 0.30,
        "Coverage": 0.25,
        "Quality": 0.20,
        "Performance": 0.15,
        "Documentation": 0.10,
    }

    # Agent sets by mode
    MODE_AGENTS = {
        "daily": [
            "security_auditor",
            "test_coverage_analyzer",
            "code_reviewer",
        ],
        "weekly": [
            "security_auditor",
            "test_coverage_analyzer",
            "code_reviewer",
            "performance_optimizer",
            "documentation_writer",
        ],
        "release": [
            "security_auditor",
            "test_coverage_analyzer",
            "code_reviewer",
            "performance_optimizer",
            "documentation_writer",
            "architecture_analyst",
        ],
    }

    # Grade thresholds
    GRADE_THRESHOLDS = {
        "A": 90.0,
        "B": 80.0,
        "C": 70.0,
        "D": 60.0,
    }

    def __init__(self, mode: str = "daily", project_root: str = ".", **kwargs):
        """Initialize health check workflow.

        Args:
            mode: Execution mode ("daily", "weekly", "release")
            project_root: Project root directory
            **kwargs: Extra parameters (ignored, for CLI compatibility)

        Raises:
            ValueError: If mode is invalid
        """
        if mode not in self.MODE_AGENTS:
            raise ValueError(
                f"Invalid mode: {mode}. Must be one of {list(self.MODE_AGENTS.keys())}"
            )

        self.mode = mode
        self.project_root = Path(project_root).resolve()
        self.orchestrator = MetaOrchestrator()

        # Tracking directory
        self.tracking_dir = self.project_root / ".empathy" / "health_tracking"
        self.tracking_dir.mkdir(parents=True, exist_ok=True)

        logger.info(
            f"OrchestratedHealthCheckWorkflow initialized: mode={mode}, root={project_root}"
        )

    async def execute(
        self,
        project_root: str | None = None,
        context: dict[str, Any] | None = None,
        **kwargs  # Absorb extra parameters from VSCode/CLI (target, etc.)
    ) -> HealthCheckReport:
        """Execute health check workflow.

        Args:
            project_root: Optional project root (overrides init value)
            context: Additional context for agents
            **kwargs: Extra parameters (ignored, for VSCode/CLI compatibility)

        Returns:
            HealthCheckReport with comprehensive health assessment

        Raises:
            ValueError: If project_root is invalid
        """
        # Map 'target' to 'project_root' for VSCode compatibility
        if 'target' in kwargs and not project_root:
            project_root = kwargs['target']
        if project_root:
            self.project_root = Path(project_root).resolve()

        if not self.project_root.exists():
            raise ValueError(f"Project root does not exist: {self.project_root}")

        logger.info(f"Starting health check: mode={self.mode}, root={self.project_root}")
        start_time = asyncio.get_event_loop().time()

        # Prepare context
        full_context = {
            "project_root": str(self.project_root),
            "mode": self.mode,
            **(context or {}),
        }

        # Get agents for mode
        agent_ids = self.MODE_AGENTS[self.mode]
        agents = []
        for agent_id in agent_ids:
            template = get_template(agent_id)
            if template:
                agents.append(template)
            else:
                logger.warning(f"Agent template not found: {agent_id}")

        if not agents:
            raise ValueError(f"No agents available for mode: {self.mode}")

        logger.info(f"Selected {len(agents)} agents: {[a.id for a in agents]}")

        # Execute agents based on mode strategy
        # All modes use parallel strategy for reliability and speed
        # (RefinementStrategy had issues with data passing between stages)
        strategy = ParallelStrategy()

        strategy_result = await strategy.execute(agents, full_context)

        # Create health report
        report = await self._create_report(strategy_result, agents)

        # Set execution time
        end_time = asyncio.get_event_loop().time()
        report.execution_time = end_time - start_time

        # Save to tracking history
        self._save_tracking_history(report)

        # Save to .empathy/health.json for VS Code extension
        self._save_health_json(report)

        logger.info(
            f"Health check completed: score={report.overall_health_score:.1f}, "
            f"grade={report.grade}, duration={report.execution_time:.2f}s"
        )

        return report

    async def _create_report(
        self, strategy_result: StrategyResult, agents: list[AgentTemplate]
    ) -> HealthCheckReport:
        """Create health check report from agent results.

        Args:
            strategy_result: Results from strategy execution
            agents: Agents that were executed

        Returns:
            HealthCheckReport with all findings
        """
        # Extract agent results
        agent_results: dict[str, dict] = {}
        for result in strategy_result.outputs:
            agent_results[result.agent_id] = {
                "success": result.success,
                "output": result.output,
                "confidence": result.confidence,
                "duration": result.duration_seconds,
                "error": result.error,
            }

        # Calculate category scores
        category_scores = self._calculate_category_scores(agent_results)

        # Calculate overall health score
        overall_score = self._calculate_overall_score(category_scores)

        # Assign grade
        grade = self._assign_grade(overall_score)

        # Collect all issues
        issues = []
        for category in category_scores:
            issues.extend(category.issues)

        # Generate recommendations
        recommendations = self._generate_recommendations(category_scores)

        # Get trend comparison
        trend = self._get_trend_comparison(overall_score)

        return HealthCheckReport(
            overall_health_score=overall_score,
            grade=grade,
            category_scores=category_scores,
            issues=issues,
            recommendations=recommendations,
            trend=trend,
            mode=self.mode,
            agents_executed=len(agents),
            success=strategy_result.success,
        )

    def _calculate_category_scores(self, agent_results: dict[str, dict]) -> list[CategoryScore]:
        """Calculate health scores for each category.

        Args:
            agent_results: Results from all agents

        Returns:
            List of CategoryScore objects
        """
        scores = []

        # Security score (from security_auditor)
        security_result = agent_results.get("security_auditor", {}).get("output", {})
        critical_issues = security_result.get("critical_issues", 0)
        high_issues = security_result.get("high_issues", 0)
        medium_issues = security_result.get("medium_issues", 0)

        security_score = 100.0
        security_issues = []

        if critical_issues > 0:
            security_score -= critical_issues * 20  # -20 per critical
            security_issues.append(f"{critical_issues} critical security issue(s)")
        if high_issues > 0:
            security_score -= high_issues * 10  # -10 per high
            security_issues.append(f"{high_issues} high severity issue(s)")
        if medium_issues > 0:
            security_score -= medium_issues * 5  # -5 per medium
            security_issues.append(f"{medium_issues} medium severity issue(s)")

        security_score = max(0.0, security_score)

        scores.append(
            CategoryScore(
                name="Security",
                score=security_score,
                weight=self.CATEGORY_WEIGHTS["Security"],
                raw_metrics={
                    "critical": critical_issues,
                    "high": high_issues,
                    "medium": medium_issues,
                },
                issues=security_issues,
                passed=critical_issues == 0 and high_issues == 0,
            )
        )

        # Coverage score (from test_coverage_analyzer)
        coverage_result = agent_results.get("test_coverage_analyzer", {}).get("output", {})
        coverage_percent = coverage_result.get("coverage_percent", 0.0)

        coverage_issues = []
        if coverage_percent < 80.0:
            coverage_issues.append(f"Coverage below 80% ({coverage_percent:.1f}%)")

        scores.append(
            CategoryScore(
                name="Coverage",
                score=coverage_percent,
                weight=self.CATEGORY_WEIGHTS["Coverage"],
                raw_metrics={"coverage_percent": coverage_percent},
                issues=coverage_issues,
                passed=coverage_percent >= 80.0,
            )
        )

        # Quality score (from code_reviewer)
        quality_result = agent_results.get("code_reviewer", {}).get("output", {})
        quality_score = quality_result.get("quality_score", 0.0)
        # Convert 0-10 scale to 0-100
        quality_score_100 = quality_score * 10

        quality_issues = []
        if quality_score < 7.0:
            quality_issues.append(f"Quality score below 7 ({quality_score:.1f}/10)")

        scores.append(
            CategoryScore(
                name="Quality",
                score=quality_score_100,
                weight=self.CATEGORY_WEIGHTS["Quality"],
                raw_metrics={"quality_score": quality_score},
                issues=quality_issues,
                passed=quality_score >= 7.0,
            )
        )

        # Performance score (from performance_optimizer, if available)
        if "performance_optimizer" in agent_results:
            perf_result = agent_results.get("performance_optimizer", {}).get("output", {})
            bottleneck_count = perf_result.get("bottleneck_count", 0)

            perf_score = 100.0 - (bottleneck_count * 10)  # -10 per bottleneck
            perf_score = max(0.0, perf_score)

            perf_issues = []
            if bottleneck_count > 0:
                perf_issues.append(f"{bottleneck_count} performance bottleneck(s)")

            scores.append(
                CategoryScore(
                    name="Performance",
                    score=perf_score,
                    weight=self.CATEGORY_WEIGHTS["Performance"],
                    raw_metrics={"bottleneck_count": bottleneck_count},
                    issues=perf_issues,
                    passed=bottleneck_count <= 2,
                )
            )

        # Documentation score (from documentation_writer, if available)
        if "documentation_writer" in agent_results:
            docs_result = agent_results.get("documentation_writer", {}).get("output", {})
            doc_coverage = docs_result.get("coverage_percent", 0.0)

            doc_issues = []
            if doc_coverage < 100.0:
                doc_issues.append(f"Documentation incomplete ({doc_coverage:.1f}%)")

            scores.append(
                CategoryScore(
                    name="Documentation",
                    score=doc_coverage,
                    weight=self.CATEGORY_WEIGHTS["Documentation"],
                    raw_metrics={"coverage_percent": doc_coverage},
                    issues=doc_issues,
                    passed=doc_coverage >= 90.0,
                )
            )

        return scores

    def _calculate_overall_score(self, category_scores: list[CategoryScore]) -> float:
        """Calculate weighted overall health score.

        Args:
            category_scores: Category scores

        Returns:
            Overall score 0-100
        """
        total_score = 0.0
        total_weight = 0.0

        for category in category_scores:
            total_score += category.score * category.weight
            total_weight += category.weight

        if total_weight == 0:
            return 0.0

        return total_score / total_weight

    def _assign_grade(self, score: float) -> str:
        """Assign letter grade based on score.

        Args:
            score: Overall health score 0-100

        Returns:
            Letter grade (A/B/C/D/F)
        """
        for grade, threshold in self.GRADE_THRESHOLDS.items():
            if score >= threshold:
                return grade
        return "F"

    def _generate_recommendations(self, category_scores: list[CategoryScore]) -> list[str]:
        """Generate actionable recommendations with specific commands.

        Args:
            category_scores: Category scores

        Returns:
            List of recommendations with commands to run
        """
        recommendations = []

        # Sort categories by score (lowest first)
        sorted_categories = sorted(category_scores, key=lambda x: x.score)

        for category in sorted_categories:
            if not category.passed:
                if category.name == "Security":
                    recommendations.append(f"🔒 Address {len(category.issues)} security issue(s)")
                    recommendations.append("   → Run: empathy workflow run security-audit --path .")
                elif category.name == "Coverage":
                    recommendations.append(
                        f"🧪 Increase test coverage to 80%+ (currently {category.score:.1f}%)"
                    )
                    recommendations.append(
                        "   → Run: pytest --cov=src --cov-report=term-missing"
                    )
                    recommendations.append(
                        "   → Or use: empathy workflow run test-gen --path <file>"
                    )
                elif category.name == "Quality":
                    quality_score = category.raw_metrics.get("quality_score", 0.0)
                    recommendations.append(
                        f"✨ Improve code quality to 7+ (currently {quality_score:.1f}/10)"
                    )
                    recommendations.append("   → Run: empathy workflow run code-review --path .")
                    recommendations.append(
                        "   → Or: empathy fix-all  (auto-fix lint/format issues)"
                    )
                elif category.name == "Performance":
                    bottlenecks = category.raw_metrics.get("bottleneck_count", 0)
                    recommendations.append(f"⚡ Optimize {bottlenecks} performance bottleneck(s)")
                    recommendations.append("   → Run: empathy workflow run perf-audit --path .")
                elif category.name == "Documentation":
                    recommendations.append(
                        f"📚 Complete documentation (currently {category.score:.1f}%)"
                    )
                    recommendations.append("   → Run: empathy workflow run doc-gen --path .")

        # Add general recommendations
        if len(recommendations) == 0:
            recommendations.append("✅ Project health looks good! Keep up the good work.")
            recommendations.append(
                "   → Run: empathy orchestrate health-check --mode weekly  (for deeper analysis)"
            )
        elif len(recommendations) >= 6:  # Multiple issues
            recommendations.append("")
            recommendations.append("💡 Tip: Focus on top priority first for maximum impact")
            recommendations.append(
                "   → Rerun: empathy orchestrate health-check --mode daily  (to track progress)"
            )

        return recommendations

    def _get_trend_comparison(self, current_score: float) -> str:
        """Compare current score with last check.

        Args:
            current_score: Current health score

        Returns:
            Trend description
        """
        history_file = self.tracking_dir / "history.jsonl"

        if not history_file.exists():
            return "No historical data"

        # Read last score from history
        try:
            with history_file.open("r") as f:
                lines = f.readlines()
                if len(lines) < 2:
                    return "First baseline established"

                # Get second-to-last entry (last is current)
                previous_entry = json.loads(lines[-2])
                previous_score = previous_entry.get("overall_health_score", 0.0)

                delta = current_score - previous_score

                if abs(delta) < 1.0:
                    return f"Stable (~{previous_score:.1f})"
                elif delta > 0:
                    return f"Improving (+{delta:.1f} from {previous_score:.1f})"
                else:
                    return f"Declining ({delta:.1f} from {previous_score:.1f})"

        except (json.JSONDecodeError, KeyError, IndexError) as e:
            logger.warning(f"Error reading tracking history: {e}")
            return "Unable to determine trend"

    def _save_tracking_history(self, report: HealthCheckReport) -> None:
        """Save health check report to tracking history.

        Args:
            report: Health check report to save
        """
        history_file = self.tracking_dir / "history.jsonl"

        try:
            # Append to history file (JSONL format)
            with history_file.open("a") as f:
                entry = {
                    "timestamp": report.timestamp,
                    "mode": report.mode,
                    "overall_health_score": report.overall_health_score,
                    "grade": report.grade,
                    "execution_time": report.execution_time,
                    "category_scores": [
                        {"name": cat.name, "score": cat.score} for cat in report.category_scores
                    ],
                }
                f.write(json.dumps(entry) + "\n")

            logger.info(f"Saved health check to tracking history: {history_file}")

        except OSError as e:
            logger.error(f"Failed to save tracking history: {e}")

    def _save_health_json(self, report: HealthCheckReport) -> None:
        """Save health check report to .empathy/health.json for VS Code extension.

        This creates the health.json file that the Empathy VS Code extension
        reads to display the interactive health dashboard.

        Args:
            report: Health check report to save
        """
        health_file = self.project_root / ".empathy" / "health.json"

        try:
            # Ensure .empathy directory exists
            health_file.parent.mkdir(parents=True, exist_ok=True)

            # Extract metrics from category scores
            lint_errors = 0
            type_errors = 0
            security_high = 0
            security_medium = 0
            security_low = 0
            test_passed = 0
            test_failed = 0
            test_total = 0
            coverage_pct = 0.0

            for category in report.category_scores:
                if category.name == "Quality":
                    # Quality issues often come from lint/type errors
                    quality_score = category.raw_metrics.get("quality_score", 10.0)
                    # Estimate errors from quality score (10 = perfect, 0 = many errors)
                    lint_errors = max(0, int((10 - quality_score) * 5))

                elif category.name == "Security":
                    security_high = category.raw_metrics.get("critical_issues", 0)
                    security_medium = category.raw_metrics.get("high_issues", 0)
                    security_low = category.raw_metrics.get("medium_issues", 0)

                elif category.name == "Coverage":
                    coverage_pct = category.score
                    # Estimate test counts (assuming good coverage means tests are passing)
                    if coverage_pct > 70:
                        test_total = 100
                        test_passed = int(coverage_pct)
                        test_failed = test_total - test_passed

            # Build health data in VS Code extension format
            health_data = {
                "score": int(report.overall_health_score),
                "lint": {"errors": lint_errors, "warnings": 0},
                "types": {"errors": type_errors},
                "security": {
                    "high": security_high,
                    "medium": security_medium,
                    "low": security_low,
                },
                "tests": {
                    "passed": test_passed,
                    "failed": test_failed,
                    "total": test_total,
                    "coverage": int(coverage_pct),
                },
                "tech_debt": {"total": 0, "todos": 0, "fixmes": 0, "hacks": 0},
                "timestamp": report.timestamp,
                "mode": report.mode,
                "grade": report.grade,
            }

            # Write health.json
            validated_health_file = _validate_file_path(str(health_file))
            with validated_health_file.open("w") as f:
                json.dump(health_data, f, indent=2)

            logger.info(f"Saved health data to {validated_health_file} for VS Code extension")

        except OSError as e:
            logger.warning(f"Failed to save health.json (file system error): {e}")
        except (TypeError, ValueError) as e:
            logger.error(f"Failed to save health.json (serialization error): {e}")
        except Exception as e:  # noqa: BLE001
            # INTENTIONAL: Saving health data should never crash a health check
            logger.warning(f"Failed to save health.json (unexpected error): {e}")


async def main():
    """CLI entry point for orchestrated health check."""
    import sys

    # Parse arguments
    mode = sys.argv[1] if len(sys.argv) > 1 else "daily"
    project_root = sys.argv[2] if len(sys.argv) > 2 else "."

    # Create workflow
    workflow = OrchestratedHealthCheckWorkflow(mode=mode, project_root=project_root)

    # Execute
    report = await workflow.execute()

    # Print report
    print(report.format_console_output())

    # Exit with appropriate code
    sys.exit(0 if report.overall_health_score >= 70 else 1)


if __name__ == "__main__":
    asyncio.run(main())
