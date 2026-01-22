"""Report generation and result storage for progressive workflows.

This module provides utilities for:
1. Generating human-readable progression reports
2. Saving detailed results to disk
3. Formatting cost analysis
4. Creating progression visualizations
"""

import json
import logging
from pathlib import Path
from typing import Any

from empathy_os.config import _validate_file_path
from empathy_os.workflows.progressive.core import (
    ProgressiveWorkflowResult,
    Tier,
)

logger = logging.getLogger(__name__)


def generate_progression_report(result: ProgressiveWorkflowResult) -> str:
    """Generate human-readable progression report.

    Creates a detailed ASCII report showing:
    - Tier-by-tier breakdown
    - Quality scores and success rates
    - Cost analysis and savings
    - Escalation decisions
    - Final results summary

    Args:
        result: Progressive workflow result

    Returns:
        Formatted report string

    Example:
        >>> print(generate_progression_report(result))
        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        🎯 PROGRESSIVE ESCALATION REPORT
        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        ...
    """
    report = []

    # Header
    report.append("━" * 60)
    report.append("🎯 PROGRESSIVE ESCALATION REPORT")
    report.append("━" * 60)
    report.append("")

    # Summary
    report.append(f"Workflow: {result.workflow_name}")
    report.append(f"Task ID: {result.task_id}")
    report.append(f"Duration: {_format_duration(result.total_duration)}")
    report.append(f"Total Cost: ${result.total_cost:.2f}")
    report.append("")

    # Cost savings
    if result.cost_savings > 0:
        report.append(f"Cost Savings: ${result.cost_savings:.2f} ({result.cost_savings_percent:.0f}% vs all-Premium)")
        report.append("")

    report.append("TIER BREAKDOWN:")
    report.append("")

    # Tier-by-tier breakdown
    for tier_result in result.tier_results:
        tier_emoji = {
            Tier.CHEAP: "💰",
            Tier.CAPABLE: "📊",
            Tier.PREMIUM: "💎"
        }[tier_result.tier]

        report.append(f"{tier_emoji} {tier_result.tier.value.upper()} Tier ({tier_result.model})")
        report.append(f"   • Items: {len(tier_result.generated_items)}")
        report.append(f"   • Attempts: {tier_result.attempt}")

        success_count = tier_result.success_count
        total_items = len(tier_result.generated_items)
        success_rate = tier_result.success_rate * 100

        report.append(f"   • Success: {success_count}/{total_items} ({success_rate:.0f}%)")
        report.append(f"   • Quality: CQS={tier_result.quality_score:.1f}")
        report.append(f"   • Cost: ${tier_result.cost:.2f}")
        report.append(f"   • Duration: {_format_duration(tier_result.duration)}")

        if tier_result.escalated:
            report.append(f"   • Escalated: {tier_result.escalation_reason}")

        report.append("")

    report.append("━" * 60)
    report.append("")
    report.append("FINAL RESULTS:")

    total_items = sum(len(r.generated_items) for r in result.tier_results)
    total_successful = sum(r.success_count for r in result.tier_results)

    status_icon = "✅" if result.success else "❌"
    status_text = "Success" if result.success else "Incomplete"

    report.append(f"{status_icon} {total_successful}/{total_items} items completed")
    report.append(f"{status_icon} Overall CQS: {result.final_result.quality_score:.0f}")
    report.append(f"{status_icon} Status: {status_text}")
    report.append("")

    report.append("━" * 60)
    report.append("")
    report.append("Detailed results saved to:")
    report.append(f".empathy/progressive_runs/{result.task_id}/")
    report.append("")

    return "\n".join(report)


def save_results_to_disk(result: ProgressiveWorkflowResult, storage_path: str) -> None:
    """Save detailed results to disk.

    Creates a directory structure:
        <storage_path>/<task_id>/
        ├── summary.json
        ├── tier_0_cheap.json
        ├── tier_1_capable.json
        ├── tier_2_premium.json (if used)
        └── report.txt

    Args:
        result: Progressive workflow result
        storage_path: Base directory for storage

    Example:
        >>> save_results_to_disk(result, ".empathy/progressive_runs")
        # Creates .empathy/progressive_runs/test-gen-20260117-143022/...
    """
    task_dir = Path(storage_path) / result.task_id
    task_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Validate task directory path for security
        validated_dir = _validate_file_path(str(task_dir))

        # Save summary
        summary = {
            "workflow": result.workflow_name,
            "task_id": result.task_id,
            "timestamp": result.tier_results[0].timestamp.isoformat() if result.tier_results else None,
            "total_cost": result.total_cost,
            "total_duration": result.total_duration,
            "cost_savings": result.cost_savings,
            "cost_savings_percent": result.cost_savings_percent,
            "success": result.success,
            "tier_count": len(result.tier_results),
            "final_cqs": result.final_result.quality_score if result.final_result else 0
        }

        summary_file = validated_dir / "summary.json"
        summary_file.write_text(json.dumps(summary, indent=2))

        # Save each tier result
        for i, tier_result in enumerate(result.tier_results):
            tier_data = {
                "tier": tier_result.tier.value,
                "model": tier_result.model,
                "attempt": tier_result.attempt,
                "timestamp": tier_result.timestamp.isoformat(),
                "quality_score": tier_result.quality_score,
                "success_count": tier_result.success_count,
                "success_rate": tier_result.success_rate,
                "cost": tier_result.cost,
                "duration": tier_result.duration,
                "escalated": tier_result.escalated,
                "escalation_reason": tier_result.escalation_reason,
                "failure_analysis": {
                    "syntax_errors": len(tier_result.failure_analysis.syntax_errors),
                    "test_pass_rate": tier_result.failure_analysis.test_pass_rate,
                    "coverage": tier_result.failure_analysis.coverage_percent,
                    "assertion_depth": tier_result.failure_analysis.assertion_depth,
                    "confidence": tier_result.failure_analysis.confidence_score
                },
                "item_count": len(tier_result.generated_items)
            }

            tier_file = validated_dir / f"tier_{i}_{tier_result.tier.value}.json"
            tier_file.write_text(json.dumps(tier_data, indent=2))

        # Save human-readable report
        report_file = validated_dir / "report.txt"
        report_file.write_text(generate_progression_report(result))

        logger.info(f"Saved progressive results to {validated_dir}")

    except ValueError as e:
        logger.error(f"Failed to save results: {e}")
        raise


def _format_duration(seconds: float) -> str:
    """Format duration in human-readable form.

    Args:
        seconds: Duration in seconds

    Returns:
        Formatted string (e.g., "1m 23s", "45s")

    Example:
        >>> _format_duration(83.5)
        '1m 24s'
        >>> _format_duration(12.3)
        '12s'
    """
    if seconds < 60:
        return f"{int(seconds)}s"

    minutes = int(seconds // 60)
    remaining_seconds = int(seconds % 60)

    return f"{minutes}m {remaining_seconds}s"


def load_result_from_disk(task_id: str, storage_path: str = ".empathy/progressive_runs") -> dict[str, Any]:
    """Load saved result from disk.

    Args:
        task_id: Task ID to load
        storage_path: Base storage directory

    Returns:
        Dictionary with summary and tier results

    Raises:
        FileNotFoundError: If task_id not found

    Example:
        >>> result = load_result_from_disk("test-gen-20260117-143022")
        >>> print(result["summary"]["total_cost"])
        0.95
    """
    task_dir = Path(storage_path) / task_id

    if not task_dir.exists():
        raise FileNotFoundError(f"Task {task_id} not found in {storage_path}")

    # Load summary
    summary_file = task_dir / "summary.json"
    if not summary_file.exists():
        raise FileNotFoundError(f"Summary file not found for task {task_id}")

    summary = json.loads(summary_file.read_text())

    # Load tier results
    tier_results = []
    for tier_file in sorted(task_dir.glob("tier_*.json")):
        tier_data = json.loads(tier_file.read_text())
        tier_results.append(tier_data)

    # Load report
    report_file = task_dir / "report.txt"
    report = report_file.read_text() if report_file.exists() else ""

    return {
        "summary": summary,
        "tier_results": tier_results,
        "report": report
    }


def list_saved_results(storage_path: str = ".empathy/progressive_runs") -> list[dict[str, Any]]:
    """List all saved progressive results.

    Args:
        storage_path: Base storage directory

    Returns:
        List of result summaries sorted by timestamp (newest first)

    Example:
        >>> results = list_saved_results()
        >>> for r in results:
        ...     print(f"{r['task_id']}: ${r['total_cost']:.2f}")
    """
    storage_dir = Path(storage_path)

    if not storage_dir.exists():
        return []

    summaries = []

    for task_dir in storage_dir.iterdir():
        if not task_dir.is_dir():
            continue

        summary_file = task_dir / "summary.json"
        if not summary_file.exists():
            continue

        try:
            summary = json.loads(summary_file.read_text())
            summaries.append(summary)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Failed to load summary from {task_dir}: {e}")

    # Sort by timestamp (newest first)
    summaries.sort(key=lambda s: s.get("timestamp", ""), reverse=True)

    return summaries


def cleanup_old_results(
    storage_path: str = ".empathy/progressive_runs",
    retention_days: int = 30,
    dry_run: bool = False
) -> tuple[int, int]:
    """Clean up old progressive workflow results.

    Args:
        storage_path: Base storage directory
        retention_days: Number of days to retain results (default: 30)
        dry_run: If True, only report what would be deleted without deleting

    Returns:
        Tuple of (deleted_count, retained_count)

    Example:
        >>> deleted, retained = cleanup_old_results(retention_days=7)
        >>> print(f"Deleted {deleted} old results, kept {retained}")
    """
    from datetime import datetime, timedelta

    storage_dir = Path(storage_path)

    if not storage_dir.exists():
        return (0, 0)

    cutoff_date = datetime.now() - timedelta(days=retention_days)
    deleted_count = 0
    retained_count = 0

    for task_dir in storage_dir.iterdir():
        if not task_dir.is_dir():
            continue

        summary_file = task_dir / "summary.json"
        if not summary_file.exists():
            continue

        try:
            summary = json.loads(summary_file.read_text())
            timestamp_str = summary.get("timestamp")

            if not timestamp_str:
                logger.warning(f"No timestamp in {task_dir}, skipping")
                retained_count += 1
                continue

            timestamp = datetime.fromisoformat(timestamp_str)

            if timestamp < cutoff_date:
                # Old result, delete it
                if not dry_run:
                    import shutil
                    shutil.rmtree(task_dir)
                    logger.info(f"Deleted old result: {task_dir.name}")
                else:
                    logger.info(f"Would delete: {task_dir.name}")
                deleted_count += 1
            else:
                retained_count += 1

        except (json.JSONDecodeError, ValueError, OSError) as e:
            logger.warning(f"Error processing {task_dir}: {e}")
            retained_count += 1

    return (deleted_count, retained_count)


def generate_cost_analytics(
    storage_path: str = ".empathy/progressive_runs"
) -> dict[str, Any]:
    """Generate cost optimization analytics from saved results.

    Analyzes historical progressive workflow runs to provide insights:
    - Total cost savings
    - Average escalation rate
    - Most cost-effective workflow types
    - Tier usage distribution
    - Success rates by tier

    Args:
        storage_path: Base storage directory

    Returns:
        Dictionary with analytics data

    Example:
        >>> analytics = generate_cost_analytics()
        >>> print(f"Total savings: ${analytics['total_savings']:.2f}")
        >>> print(f"Avg escalation rate: {analytics['avg_escalation_rate']:.1%}")
    """
    results = list_saved_results(storage_path)

    if not results:
        return {
            "total_runs": 0,
            "total_cost": 0.0,
            "total_savings": 0.0,
            "avg_savings_percent": 0.0
        }

    total_runs = len(results)
    total_cost = sum(r.get("total_cost", 0) for r in results)
    total_savings = sum(r.get("cost_savings", 0) for r in results)

    # Calculate average savings percent (weighted by cost)
    weighted_savings = sum(
        r.get("cost_savings_percent", 0) * r.get("total_cost", 0)
        for r in results
    )
    avg_savings_percent = weighted_savings / total_cost if total_cost > 0 else 0

    # Tier usage statistics
    tier_usage = {"cheap": 0, "capable": 0, "premium": 0}
    tier_costs = {"cheap": 0.0, "capable": 0.0, "premium": 0.0}
    escalation_count = 0

    for result in results:
        tier_count = result.get("tier_count", 0)
        if tier_count > 1:
            escalation_count += 1

    escalation_rate = escalation_count / total_runs if total_runs > 0 else 0

    # Success rate
    successful_runs = sum(1 for r in results if r.get("success", False))
    success_rate = successful_runs / total_runs if total_runs > 0 else 0

    # Average final CQS
    avg_cqs = sum(r.get("final_cqs", 0) for r in results) / total_runs if total_runs > 0 else 0

    # Per-workflow analytics
    workflow_stats: dict[str, dict[str, Any]] = {}
    for result in results:
        workflow = result.get("workflow", "unknown")
        if workflow not in workflow_stats:
            workflow_stats[workflow] = {
                "runs": 0,
                "total_cost": 0.0,
                "total_savings": 0.0,
                "successes": 0
            }

        stats = workflow_stats[workflow]
        stats["runs"] += 1
        stats["total_cost"] += result.get("total_cost", 0)
        stats["total_savings"] += result.get("cost_savings", 0)
        if result.get("success", False):
            stats["successes"] += 1

    # Calculate per-workflow averages
    for stats in workflow_stats.values():
        stats["avg_cost"] = stats["total_cost"] / stats["runs"]
        stats["avg_savings"] = stats["total_savings"] / stats["runs"]
        stats["success_rate"] = stats["successes"] / stats["runs"]

    return {
        "total_runs": total_runs,
        "total_cost": round(total_cost, 2),
        "total_savings": round(total_savings, 2),
        "avg_savings_percent": round(avg_savings_percent, 1),
        "escalation_rate": round(escalation_rate, 2),
        "success_rate": round(success_rate, 2),
        "avg_final_cqs": round(avg_cqs, 1),
        "tier_usage": tier_usage,
        "tier_costs": tier_costs,
        "workflow_stats": workflow_stats
    }


def format_cost_analytics_report(analytics: dict[str, Any]) -> str:
    """Format cost analytics as human-readable report.

    Args:
        analytics: Analytics data from generate_cost_analytics()

    Returns:
        Formatted report string

    Example:
        >>> analytics = generate_cost_analytics()
        >>> print(format_cost_analytics_report(analytics))
    """
    report = []

    report.append("━" * 60)
    report.append("📊 PROGRESSIVE ESCALATION ANALYTICS")
    report.append("━" * 60)
    report.append("")

    # Overall statistics
    report.append("OVERALL STATISTICS:")
    report.append(f"  Total Runs: {analytics['total_runs']}")
    report.append(f"  Total Cost: ${analytics['total_cost']:.2f}")
    report.append(f"  Total Savings: ${analytics['total_savings']:.2f}")
    report.append(f"  Avg Savings: {analytics['avg_savings_percent']:.1f}%")
    report.append(f"  Escalation Rate: {analytics['escalation_rate']:.1%}")
    report.append(f"  Success Rate: {analytics['success_rate']:.1%}")
    report.append(f"  Avg Final CQS: {analytics['avg_final_cqs']:.1f}")
    report.append("")

    # Per-workflow breakdown
    if analytics.get("workflow_stats"):
        report.append("PER-WORKFLOW BREAKDOWN:")
        report.append("")

        for workflow, stats in sorted(analytics["workflow_stats"].items()):
            report.append(f"  {workflow}:")
            report.append(f"    Runs: {stats['runs']}")
            report.append(f"    Avg Cost: ${stats['avg_cost']:.2f}")
            report.append(f"    Avg Savings: ${stats['avg_savings']:.2f}")
            report.append(f"    Success Rate: {stats['success_rate']:.1%}")
            report.append("")

    report.append("━" * 60)

    return "\n".join(report)
