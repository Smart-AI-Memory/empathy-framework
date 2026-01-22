"""PR Review Workflow

A comprehensive PR review workflow that combines CodeReviewCrew and
SecurityAuditCrew for thorough code and security analysis.

Features:
- Runs both crews in parallel for speed
- Merges findings from code quality and security perspectives
- Provides unified verdict and risk assessment
- Graceful fallback if crews are unavailable

Copyright 2025 Smart-AI-Memory
Licensed under Fair Source License 0.9
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class PRReviewResult:
    """Result from PRReviewWorkflow execution."""

    success: bool
    verdict: str  # "approve", "approve_with_suggestions", "request_changes", "reject"
    code_quality_score: float
    security_risk_score: float
    combined_score: float
    code_review: dict | None
    security_audit: dict | None
    all_findings: list[dict]
    code_findings: list[dict]
    security_findings: list[dict]
    critical_count: int
    high_count: int
    blockers: list[str]
    warnings: list[str]
    recommendations: list[str]
    summary: str
    agents_used: list[str]
    duration_seconds: float
    cost: float = 0.0  # Total cost from code review and security audit crews
    metadata: dict = field(default_factory=dict)


class PRReviewWorkflow:
    """Combined code review + security audit for comprehensive PR analysis.

    Runs CodeReviewCrew and SecurityAuditCrew in parallel for maximum
    speed while providing thorough analysis from both perspectives.

    Usage:
        workflow = PRReviewWorkflow()
        result = await workflow.execute(
            diff="...",
            files_changed=["src/main.py"],
            target_path="./src",
        )
    """

    def __init__(
        self,
        provider: str = "anthropic",
        use_code_crew: bool = True,
        use_security_crew: bool = True,
        parallel: bool = True,
        code_crew_config: dict | None = None,
        security_crew_config: dict | None = None,
    ):
        """Initialize the workflow.

        Args:
            provider: LLM provider to use (anthropic, openai, etc.)
            use_code_crew: Enable CodeReviewCrew
            use_security_crew: Enable SecurityAuditCrew
            parallel: Run crews in parallel (recommended)
            code_crew_config: Configuration for CodeReviewCrew
            security_crew_config: Configuration for SecurityAuditCrew

        """
        self.provider = provider
        self.use_code_crew = use_code_crew
        self.use_security_crew = use_security_crew
        self.parallel = parallel

        # Map "hybrid" to a real provider for crews (they don't understand "hybrid")
        crew_provider = "anthropic" if provider == "hybrid" else provider

        # Inject provider into crew configs
        self.code_crew_config = {"provider": crew_provider, **(code_crew_config or {})}
        self.security_crew_config = {"provider": crew_provider, **(security_crew_config or {})}

    @classmethod
    def for_comprehensive_review(cls) -> "PRReviewWorkflow":
        """Factory for comprehensive PR review with all crews."""
        return cls(
            use_code_crew=True,
            use_security_crew=True,
            parallel=True,
        )

    @classmethod
    def for_security_focused(cls) -> "PRReviewWorkflow":
        """Factory for security-focused review."""
        return cls(
            use_code_crew=False,
            use_security_crew=True,
            parallel=False,
        )

    @classmethod
    def for_code_quality_focused(cls) -> "PRReviewWorkflow":
        """Factory for code quality-focused review."""
        return cls(
            use_code_crew=True,
            use_security_crew=False,
            parallel=False,
        )

    async def execute(
        self,
        diff: str | None = None,
        files_changed: list[str] | None = None,
        target_path: str = ".",
        target: str | None = None,  # Alias for target_path (compatibility)
        context: dict | None = None,
    ) -> PRReviewResult:
        """Execute comprehensive PR review with both crews.

        Args:
            diff: PR diff content (auto-generated from git if not provided)
            files_changed: List of changed files
            target_path: Path to codebase for security audit
            target: Alias for target_path (for CLI compatibility)
            context: Additional context

        Returns:
            PRReviewResult with combined analysis

        """
        start_time = time.time()
        files_changed = files_changed or []
        context = context or {}

        # Support 'target' as alias for 'target_path'
        if target and target_path == ".":
            target_path = target

        # Auto-generate diff from git if not provided
        if not diff:
            import subprocess

            try:
                # Get diff of staged and unstaged changes
                git_result = subprocess.run(
                    ["git", "diff", "HEAD"],
                    check=False,
                    cwd=target_path,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                diff = git_result.stdout or ""
                if not diff:
                    # Try getting diff against main/master
                    for branch in ["main", "master"]:
                        git_result = subprocess.run(
                            ["git", "diff", branch],
                            check=False,
                            cwd=target_path,
                            capture_output=True,
                            text=True,
                            timeout=30,
                        )
                        if git_result.stdout:
                            diff = git_result.stdout
                            break
                if not diff:
                    diff = "(No diff available - no changes detected)"
            except Exception:
                diff = "(Could not generate diff from git)"

        # Initialize result collectors
        code_review: dict | None = None
        security_audit: dict | None = None
        code_findings: list[dict] = []
        security_findings: list[dict] = []
        blockers: list[str] = []
        warnings: list[str] = []
        recommendations: list[str] = []
        agents_used: list[str] = []

        try:
            if self.parallel and self.use_code_crew and self.use_security_crew:
                # Run both crews in parallel
                code_review, security_audit = await self._run_parallel(
                    diff,
                    files_changed,
                    target_path,
                )
            else:
                # Run sequentially
                if self.use_code_crew:
                    code_review = await self._run_code_review(diff, files_changed)
                if self.use_security_crew:
                    security_audit = await self._run_security_audit(target_path)

            # Collect findings and costs from code review
            total_cost = 0.0
            if code_review:
                code_findings = code_review.get("findings", [])
                agents_used.extend(code_review.get("agents_used", []))
                for f in code_findings:
                    if f.get("suggestion"):
                        recommendations.append(f["suggestion"])
                # Accumulate cost from code review (if tracked by crew)
                total_cost += code_review.get("cost", 0.0)

            # Collect findings and costs from security audit
            if security_audit:
                security_findings = security_audit.get("findings", [])
                agents_used.extend(security_audit.get("agents_used", []))
                for f in security_findings:
                    if f.get("remediation"):
                        recommendations.append(f["remediation"])
                # Accumulate cost from security audit (if tracked by crew)
                total_cost += security_audit.get("cost", 0.0)

            # Combine all findings
            all_findings = self._merge_findings(code_findings, security_findings)

            # Count by severity
            critical_count = len([f for f in all_findings if f.get("severity") == "critical"])
            high_count = len([f for f in all_findings if f.get("severity") == "high"])

            # Determine blockers
            if critical_count > 0:
                blockers.append(f"{critical_count} critical issue(s) must be fixed")
            if high_count > 3:
                blockers.append(f"{high_count} high severity issues exceed threshold")

            # Calculate scores
            code_quality_score = self._get_code_quality_score(code_review)
            security_risk_score = self._get_security_risk_score(security_audit)
            combined_score = self._calculate_combined_score(code_quality_score, security_risk_score)

            # Determine verdict
            verdict = self._determine_verdict(code_review, security_audit, combined_score, blockers)

            # Generate summary
            summary = self._generate_summary(
                verdict,
                code_quality_score,
                security_risk_score,
                len(all_findings),
                critical_count,
                high_count,
            )

            # Check for warnings
            if not code_review and self.use_code_crew:
                warnings.append("CodeReviewCrew unavailable - code review limited")
            if not security_audit and self.use_security_crew:
                warnings.append("SecurityAuditCrew unavailable - security audit limited")

            duration = time.time() - start_time

            result = PRReviewResult(
                success=True,
                verdict=verdict,
                code_quality_score=code_quality_score,
                security_risk_score=security_risk_score,
                combined_score=combined_score,
                code_review=code_review,
                security_audit=security_audit,
                all_findings=all_findings,
                code_findings=code_findings,
                security_findings=security_findings,
                critical_count=critical_count,
                high_count=high_count,
                blockers=blockers,
                warnings=warnings,
                recommendations=recommendations[:15],  # Top 15
                summary=summary,
                agents_used=list(dict.fromkeys(agents_used)),  # Deduplicate (preserves order)
                duration_seconds=duration,
                cost=total_cost,
                metadata={
                    "files_changed": len(files_changed),
                    "total_findings": len(all_findings),
                    "code_crew_enabled": self.use_code_crew,
                    "security_crew_enabled": self.use_security_crew,
                    "parallel_execution": self.parallel,
                },
            )

            # Add formatted report for human readability
            result.metadata["formatted_report"] = format_pr_review_report(result)
            return result

        except Exception as e:
            logger.error(f"PRReviewWorkflow failed: {e}")
            duration = time.time() - start_time
            return PRReviewResult(
                success=False,
                verdict="reject",
                code_quality_score=0.0,
                security_risk_score=100.0,
                combined_score=0.0,
                code_review=code_review,
                security_audit=security_audit,
                all_findings=[],
                code_findings=[],
                security_findings=[],
                critical_count=0,
                high_count=0,
                blockers=[f"Review failed: {e!s}"],
                warnings=[],
                recommendations=[],
                summary=f"PR review failed with error: {e!s}",
                agents_used=[],
                duration_seconds=duration,
                cost=0.0,
                metadata={"error": str(e)},
            )

    async def _run_parallel(
        self,
        diff: str,
        files_changed: list[str],
        target_path: str,
    ) -> tuple[dict | None, dict | None]:
        """Run both crews in parallel."""
        code_task = asyncio.create_task(self._run_code_review(diff, files_changed))
        security_task = asyncio.create_task(self._run_security_audit(target_path))

        results = await asyncio.gather(code_task, security_task, return_exceptions=True)

        code_review: dict | None = results[0] if isinstance(results[0], dict) else None
        security_audit: dict | None = results[1] if isinstance(results[1], dict) else None

        if isinstance(results[0], Exception):
            logger.warning(f"Code review failed: {results[0]}")
        if isinstance(results[1], Exception):
            logger.warning(f"Security audit failed: {results[1]}")

        return code_review, security_audit

    async def _run_code_review(
        self,
        diff: str,
        files_changed: list[str],
    ) -> dict | None:
        """Run CodeReviewCrew."""
        from .code_review_adapters import (
            _check_crew_available,
            _get_crew_review,
            crew_report_to_workflow_format,
        )

        if not _check_crew_available():
            logger.info("CodeReviewCrew not available")
            return None

        report = await _get_crew_review(
            diff=diff,
            files_changed=files_changed,
            config=self.code_crew_config,
        )

        if report:
            return crew_report_to_workflow_format(report)
        return None

    async def _run_security_audit(
        self,
        target_path: str,
    ) -> dict | None:
        """Run SecurityAuditCrew."""
        from .security_adapters import (
            _check_crew_available,
            _get_crew_audit,
            crew_report_to_workflow_format,
        )

        if not _check_crew_available():
            logger.info("SecurityAuditCrew not available")
            return None

        report = await _get_crew_audit(
            target=target_path,
            config=self.security_crew_config,
        )

        if report:
            return crew_report_to_workflow_format(report)
        return None

    def _merge_findings(
        self,
        code_findings: list[dict],
        security_findings: list[dict],
    ) -> list[dict]:
        """Merge and deduplicate findings from both sources."""
        # Tag findings with source
        for f in code_findings:
            f["source"] = "code_review"
        for f in security_findings:
            f["source"] = "security_audit"

        # Combine and deduplicate by (file, line, type)
        all_findings = code_findings + security_findings
        seen = set()
        unique = []

        for f in all_findings:
            key = (f.get("file"), f.get("line"), f.get("type") or f.get("title"))
            if key not in seen:
                seen.add(key)
                unique.append(f)

        # Sort by severity (critical first)
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
        unique.sort(key=lambda f: severity_order.get(f.get("severity", "medium"), 2))

        return unique

    def _get_code_quality_score(self, code_review: dict | None) -> float:
        """Extract code quality score from review."""
        if code_review:
            return float(code_review.get("quality_score", 85.0))
        return 85.0  # Default if no review

    def _get_security_risk_score(self, security_audit: dict | None) -> float:
        """Extract security risk score from audit."""
        if security_audit:
            return float(security_audit.get("risk_score", 20.0))
        return 20.0  # Default if no audit

    def _calculate_combined_score(
        self,
        code_quality: float,
        security_risk: float,
    ) -> float:
        """Calculate combined score.

        Higher is better. Combines code quality (0-100, higher=better)
        with security risk (0-100, lower=better).
        """
        # Convert security risk to "safety score" (invert)
        security_safety = 100.0 - security_risk

        # Weighted average: security is slightly more important
        combined = (code_quality * 0.45) + (security_safety * 0.55)
        return max(0.0, min(100.0, combined))

    def _determine_verdict(
        self,
        code_review: dict | None,
        security_audit: dict | None,
        combined_score: float,
        blockers: list[str],
    ) -> str:
        """Determine final PR verdict."""
        verdicts = []

        # Code review verdict
        if code_review:
            code_verdict = code_review.get("verdict", "approve")
            verdicts.append(code_verdict)

        # Security risk-based verdict
        if security_audit:
            risk = security_audit.get("risk_score", 0)
            if risk >= 70:
                verdicts.append("reject")
            elif risk >= 50:
                verdicts.append("request_changes")
            elif risk >= 30:
                verdicts.append("approve_with_suggestions")

        # Score-based verdict
        if combined_score < 50:
            verdicts.append("reject")
        elif combined_score < 70:
            verdicts.append("request_changes")
        elif combined_score < 85:
            verdicts.append("approve_with_suggestions")
        else:
            verdicts.append("approve")

        # Blockers force request_changes at minimum
        if blockers:
            verdicts.append("request_changes")

        # Return most severe verdict
        priority = ["reject", "request_changes", "approve_with_suggestions", "approve"]
        for v in priority:
            if v in verdicts:
                return v

        return "approve"

    def _generate_summary(
        self,
        verdict: str,
        code_quality: float,
        security_risk: float,
        total_findings: int,
        critical_count: int,
        high_count: int,
    ) -> str:
        """Generate human-readable summary."""
        verdict_text = {
            "approve": "PR is ready to merge",
            "approve_with_suggestions": "PR can be merged with minor improvements",
            "request_changes": "PR requires changes before merging",
            "reject": "PR has critical issues and should not be merged",
        }.get(verdict, "Unknown status")

        summary_parts = [verdict_text]

        if total_findings > 0:
            findings_text = f"{total_findings} finding(s)"
            if critical_count > 0:
                findings_text += f" ({critical_count} critical)"
            elif high_count > 0:
                findings_text += f" ({high_count} high)"
            summary_parts.append(findings_text)

        summary_parts.append(f"Code quality: {code_quality:.0f}/100")
        summary_parts.append(f"Security risk: {security_risk:.0f}/100")

        return ". ".join(summary_parts) + "."


# CLI entry point
def main():
    """Run PRReviewWorkflow from command line."""
    import argparse

    parser = argparse.ArgumentParser(description="PR Review Workflow")
    parser.add_argument("--diff", "-d", help="PR diff content")
    parser.add_argument("--target", "-t", default=".", help="Target path for security audit")
    parser.add_argument("--files", "-f", nargs="*", default=[], help="Changed files")
    parser.add_argument("--parallel/--sequential", dest="parallel", default=True)
    parser.add_argument("--code-only", action="store_true", help="Only run code review")
    parser.add_argument("--security-only", action="store_true", help="Only run security audit")

    args = parser.parse_args()

    async def run():
        if args.code_only:
            workflow = PRReviewWorkflow.for_code_quality_focused()
        elif args.security_only:
            workflow = PRReviewWorkflow.for_security_focused()
        else:
            workflow = PRReviewWorkflow(parallel=args.parallel)

        result = await workflow.execute(
            diff=args.diff or "",
            files_changed=args.files,
            target_path=args.target,
        )

        print("\n" + "=" * 60)
        print("PR REVIEW RESULTS")
        print("=" * 60)
        print(f"\nVerdict: {result.verdict.upper()}")
        print(f"\n{result.summary}")
        print(f"\nDuration: {result.duration_seconds * 1000:.0f}ms")

        if result.agents_used:
            print(f"\nAgents Used: {', '.join(result.agents_used)}")

        print(f"\nFindings: {len(result.all_findings)} total")
        print(f"  Code: {len(result.code_findings)}")
        print(f"  Security: {len(result.security_findings)}")
        print(f"  Critical: {result.critical_count}")
        print(f"  High: {result.high_count}")

        if result.blockers:
            print("\nBlockers:")
            for b in result.blockers:
                print(f"  - {b}")

        if result.warnings:
            print("\nWarnings:")
            for w in result.warnings:
                print(f"  - {w}")

        if result.recommendations[:5]:
            print("\nTop Recommendations:")
            for r in result.recommendations[:5]:
                print(f"  - {r[:80]}...")

    asyncio.run(run())


def format_pr_review_report(result: PRReviewResult) -> str:
    """Format PR review result as a human-readable report.

    Args:
        result: The PRReviewResult dataclass

    Returns:
        Formatted report string

    """
    lines = []

    # Header with verdict
    verdict_emoji = {
        "approve": "✅",
        "approve_with_suggestions": "🟡",
        "request_changes": "🟠",
        "reject": "🔴",
    }
    emoji = verdict_emoji.get(result.verdict, "⚪")

    lines.append("=" * 60)
    lines.append("PR REVIEW REPORT")
    lines.append("=" * 60)
    lines.append("")

    # Verdict banner
    lines.append("-" * 60)
    lines.append(f"{emoji} VERDICT: {result.verdict.upper().replace('_', ' ')}")
    lines.append("-" * 60)
    lines.append("")

    # Scores
    lines.append("-" * 60)
    lines.append("SCORES")
    lines.append("-" * 60)

    # Code quality score with visual bar
    cq_score = result.code_quality_score
    cq_bar = "█" * int(cq_score / 10) + "░" * (10 - int(cq_score / 10))
    lines.append(f"Code Quality:    [{cq_bar}] {cq_score:.0f}/100")

    # Security risk (inverted - lower is better)
    sr_score = result.security_risk_score
    sr_bar = "█" * int(sr_score / 10) + "░" * (10 - int(sr_score / 10))
    risk_label = "LOW" if sr_score < 30 else "MEDIUM" if sr_score < 60 else "HIGH"
    lines.append(f"Security Risk:   [{sr_bar}] {sr_score:.0f}/100 ({risk_label})")

    # Combined score
    combined = result.combined_score
    combined_bar = "█" * int(combined / 10) + "░" * (10 - int(combined / 10))
    lines.append(f"Combined Score:  [{combined_bar}] {combined:.0f}/100")
    lines.append("")

    # Summary
    if result.summary:
        lines.append("-" * 60)
        lines.append("SUMMARY")
        lines.append("-" * 60)
        # Word wrap summary
        words = result.summary.split()
        current_line = ""
        for word in words:
            if len(current_line) + len(word) + 1 <= 58:
                current_line += (" " if current_line else "") + word
            else:
                lines.append(current_line)
                current_line = word
        if current_line:
            lines.append(current_line)
        lines.append("")

    # Blockers
    if result.blockers:
        lines.append("-" * 60)
        lines.append("🚫 BLOCKERS (must fix before merge)")
        lines.append("-" * 60)
        for blocker in result.blockers:
            lines.append(f"  • {blocker}")
        lines.append("")

    # Findings summary
    if result.all_findings:
        lines.append("-" * 60)
        lines.append("FINDINGS")
        lines.append("-" * 60)
        lines.append(f"Total: {len(result.all_findings)}")
        lines.append(f"  🔴 Critical: {result.critical_count}")
        lines.append(f"  🟠 High: {result.high_count}")
        lines.append(f"  Code Issues: {len(result.code_findings)}")
        lines.append(f"  Security Issues: {len(result.security_findings)}")
        lines.append("")

        # Show top critical/high findings
        critical_high = [
            f for f in result.all_findings if f.get("severity") in ("critical", "high")
        ]
        if critical_high:
            lines.append("Top Issues:")
            for i, finding in enumerate(critical_high[:5], 1):
                severity = finding.get("severity", "unknown")
                title = finding.get("title", finding.get("message", "Unknown issue"))
                emoji = "🔴" if severity == "critical" else "🟠"
                if len(title) > 50:
                    title = title[:47] + "..."
                lines.append(f"  {emoji} {i}. {title}")
            if len(critical_high) > 5:
                lines.append(f"  ... and {len(critical_high) - 5} more critical/high issues")
            lines.append("")

    # Warnings
    if result.warnings:
        lines.append("-" * 60)
        lines.append("⚠️  WARNINGS")
        lines.append("-" * 60)
        for warning in result.warnings:
            lines.append(f"  • {warning}")
        lines.append("")

    # Recommendations
    if result.recommendations:
        lines.append("-" * 60)
        lines.append("RECOMMENDATIONS")
        lines.append("-" * 60)
        for i, rec in enumerate(result.recommendations[:5], 1):
            if len(rec) > 55:
                rec = rec[:52] + "..."
            lines.append(f"  {i}. {rec}")
        if len(result.recommendations) > 5:
            lines.append(f"  ... and {len(result.recommendations) - 5} more")
        lines.append("")

    # Agents used
    if result.agents_used:
        lines.append("-" * 60)
        lines.append("AGENTS USED")
        lines.append("-" * 60)
        lines.append(f"  {', '.join(result.agents_used)}")
        lines.append("")

    # Footer
    lines.append("=" * 60)
    duration_ms = result.duration_seconds * 1000
    lines.append(f"Review completed in {duration_ms:.0f}ms | Cost: ${result.cost:.4f}")
    lines.append("=" * 60)

    return "\n".join(lines)


if __name__ == "__main__":
    main()
