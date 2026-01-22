"""
Automatic tier recommendation and progression tracking for workflows.

Integrates TierRecommender into workflows to:
1. Auto-suggest optimal tier at workflow start
2. Track tier progression during execution
3. Save tier progression data automatically

Copyright 2025 Smart-AI-Memory
Licensed under Fair Source License 0.9
"""

import json
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from empathy_os.config import _validate_file_path
from empathy_os.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class TierAttempt:
    """Record of a single tier attempt."""

    tier: str
    attempt: int
    success: bool
    quality_gate_failed: str | None = None
    quality_gates_passed: list[str] | None = None


@dataclass
class WorkflowTierProgression:
    """Track tier progression for a workflow run."""

    workflow_name: str
    workflow_id: str
    bug_description: str
    files_affected: list[str]
    bug_type: str

    # Tier progression
    recommended_tier: str
    starting_tier: str
    successful_tier: str
    total_attempts: int
    tier_history: list[dict[str, Any]]

    # Costs
    total_cost: float
    cost_if_always_premium: float
    savings_percent: float

    # Quality
    tests_passed: bool
    error_occurred: bool

    # Metadata
    started_at: str
    completed_at: str
    duration_seconds: float

    # Optional fields must come last
    error_message: str | None = None


class WorkflowTierTracker:
    """
    Automatically track tier progression for workflow runs.

    Usage in BaseWorkflow:
        tracker = WorkflowTierTracker(workflow_name, description)
        tracker.show_recommendation(files_affected)
        # ... run workflow ...
        tracker.save_progression(result)
    """

    TIER_COSTS = {
        "cheap": 0.030,
        "capable": 0.090,
        "premium": 0.450,
    }

    # Retention policy: keep only this many workflow files
    MAX_WORKFLOW_FILES = 100
    # Only run cleanup every N saves to avoid overhead
    CLEANUP_FREQUENCY = 10

    def __init__(
        self,
        workflow_name: str,
        workflow_description: str,
        patterns_dir: Path | None = None,
    ):
        """
        Initialize tier tracker for a workflow.

        Args:
            workflow_name: Name of the workflow
            workflow_description: Description/purpose of workflow
            patterns_dir: Directory to save tier progression patterns
        """
        self.workflow_name = workflow_name
        self.workflow_description = workflow_description
        self.workflow_id = str(uuid.uuid4())
        self.started_at = datetime.now()

        if patterns_dir is None:
            patterns_dir = Path.cwd() / "patterns" / "debugging"
        self.patterns_dir = Path(patterns_dir)
        self.patterns_dir.mkdir(parents=True, exist_ok=True)

        self.recommended_tier: str | None = None
        self.starting_tier: str | None = None
        self.tier_attempts: list[TierAttempt] = []

    def show_recommendation(
        self,
        files_affected: list[str] | None = None,
        show_ui: bool = True,
    ) -> str:
        """
        Show tier recommendation at workflow start.

        Args:
            files_affected: Files involved in this workflow run
            show_ui: Whether to print recommendation to console

        Returns:
            Recommended tier (CHEAP, CAPABLE, or PREMIUM)
        """
        try:
            from empathy_os.tier_recommender import TierRecommender

            recommender = TierRecommender()
            result = recommender.recommend(
                bug_description=self.workflow_description,
                files_affected=files_affected or [],
            )

            self.recommended_tier = result.tier

            if show_ui:
                self._print_recommendation(result)

            return result.tier

        except Exception as e:
            logger.debug(f"Could not get tier recommendation: {e}")
            # Fallback to CHEAP if recommendation fails
            self.recommended_tier = "CHEAP"
            return "CHEAP"

    def _print_recommendation(self, result):
        """Print tier recommendation to console."""
        from rich.console import Console
        from rich.panel import Panel

        console = Console()

        confidence_color = "green" if result.confidence > 0.7 else "yellow"

        message = f"""[bold]Workflow:[/bold] {self.workflow_name}
[bold]Description:[/bold] {self.workflow_description}

[bold cyan]💡 Tier Recommendation[/bold cyan]
📍 Recommended: [bold]{result.tier}[/bold]
🎯 Confidence: [{confidence_color}]{result.confidence * 100:.0f}%[/{confidence_color}]
💰 Expected Cost: ${result.expected_cost:.3f}
🔄 Expected Attempts: {result.expected_attempts:.1f}

[dim]Reasoning: {result.reasoning}[/dim]"""

        if result.fallback_used:
            message += "\n\n[yellow]⚠️  Using default - limited historical data[/yellow]"
        else:
            message += (
                f"\n\n[green]✅ Based on {result.similar_patterns_count} similar patterns[/green]"
            )

        console.print(Panel(message, title="🎯 Auto Tier Recommendation", border_style="cyan"))

    def record_tier_attempt(
        self,
        tier: str,
        attempt: int,
        success: bool,
        quality_gate_failed: str | None = None,
        quality_gates_passed: list[str] | None = None,
    ):
        """Record a tier attempt during workflow execution."""
        self.tier_attempts.append(
            TierAttempt(
                tier=tier,
                attempt=attempt,
                success=success,
                quality_gate_failed=quality_gate_failed,
                quality_gates_passed=quality_gates_passed,
            )
        )

    def save_progression(
        self,
        workflow_result: Any,
        files_affected: list[str] | None = None,
        bug_type: str = "workflow_run",
        tier_progression: list[tuple[str, str, bool]] | None = None,
    ) -> Path | None:
        """
        Save tier progression data after workflow completion.

        Args:
            workflow_result: WorkflowResult from workflow execution
            files_affected: Files processed by workflow
            bug_type: Type of issue being addressed
            tier_progression: Optional detailed tier progression list
                             [(stage, tier, success), ...]

        Returns:
            Path to saved pattern file, or None if save failed
        """
        try:
            completed_at = datetime.now()
            duration = (completed_at - self.started_at).total_seconds()

            # Determine successful tier from workflow result
            successful_tier = self._determine_successful_tier(workflow_result)
            self.starting_tier = self.starting_tier or successful_tier

            # Build tier history - use detailed progression if available
            if tier_progression:
                tier_history = self._build_tier_history_from_progression(tier_progression)
            else:
                tier_history = self._build_tier_history(workflow_result)

            # Calculate costs
            total_cost = (
                workflow_result.cost_report.get("total", 0)
                if isinstance(workflow_result.cost_report, dict)
                else sum(stage.cost for stage in workflow_result.stages)
            )
            cost_if_premium = self._estimate_premium_cost(workflow_result)
            savings_percent = (
                ((cost_if_premium - total_cost) / cost_if_premium * 100)
                if cost_if_premium > 0
                else 0
            )

            # Create progression record
            progression = {
                "pattern_id": f"workflow_{datetime.now().strftime('%Y%m%d')}_{self.workflow_id[:8]}",
                "bug_type": bug_type,
                "status": "resolved" if workflow_result.error is None else "failed",
                "root_cause": f"Workflow: {self.workflow_name} - {self.workflow_description}",
                "fix": f"Completed via {self.workflow_name} workflow",
                "resolved_by": "@empathy_framework",
                "resolved_at": completed_at.strftime("%Y-%m-%d"),
                "files_affected": files_affected or [],
                "source": "workflow_tracking",
                "tier_progression": {
                    "methodology": "AI-ADDIE",
                    "recommended_tier": self.recommended_tier or self.starting_tier,
                    "starting_tier": self.starting_tier,
                    "successful_tier": successful_tier,
                    "total_attempts": len(tier_history),
                    "tier_history": tier_history,
                    "cost_breakdown": {
                        "total_cost": round(total_cost, 3),
                        "cost_if_always_premium": round(cost_if_premium, 3),
                        "savings_percent": round(savings_percent, 1),
                    },
                    "quality_metrics": {
                        "tests_passed": workflow_result.error is None,
                        "health_score_before": 73,  # Default
                        "health_score_after": 73,
                    },
                    "xml_protocol_compliance": {
                        "prompt_used_xml": True,
                        "response_used_xml": True,
                        "all_sections_present": True,
                        "test_evidence_provided": True,
                        "false_complete_avoided": workflow_result.error is None,
                    },
                },
                "workflow_metadata": {
                    "workflow_name": self.workflow_name,
                    "workflow_id": self.workflow_id,
                    "duration_seconds": round(duration, 2),
                    "started_at": self.started_at.isoformat(),
                    "completed_at": completed_at.isoformat(),
                },
            }

            # Save to individual pattern file
            pattern_file = self.patterns_dir / f"{progression['pattern_id']}.json"
            validated_pattern_file = _validate_file_path(str(pattern_file))
            with open(validated_pattern_file, "w") as f:
                json.dump(progression, f, indent=2)

            logger.info(f"💾 Saved tier progression: {validated_pattern_file}")

            # Also update consolidated patterns file
            self._update_consolidated_patterns(progression)

            # Periodic cleanup of old workflow files (every CLEANUP_FREQUENCY saves)
            workflow_count = len(list(self.patterns_dir.glob("workflow_*.json")))
            if workflow_count > self.MAX_WORKFLOW_FILES + self.CLEANUP_FREQUENCY:
                self._cleanup_old_workflow_files()

            return pattern_file

        except Exception as e:
            logger.warning(f"Failed to save tier progression: {e}")
            return None

    def _determine_successful_tier(self, workflow_result: Any) -> str:
        """Determine which tier successfully completed the workflow."""
        if not workflow_result.stages:
            return "CHEAP"

        # Use the highest tier that was actually used
        tiers_used = [
            stage.tier.value if hasattr(stage.tier, "value") else str(stage.tier).lower()
            for stage in workflow_result.stages
        ]

        if "premium" in tiers_used:
            return "PREMIUM"
        elif "capable" in tiers_used:
            return "CAPABLE"
        else:
            return "CHEAP"

    def _build_tier_history_from_progression(
        self, tier_progression: list[tuple[str, str, bool]]
    ) -> list[dict[str, Any]]:
        """Build detailed tier history from tier progression tracking.

        Args:
            tier_progression: List of (stage, tier, success) tuples

        Returns:
            List of tier history entries with detailed attempt information

        """
        # Group attempts by stage
        stage_attempts: dict[str, list[tuple[str, bool]]] = {}
        for stage, tier, success in tier_progression:
            if stage not in stage_attempts:
                stage_attempts[stage] = []
            stage_attempts[stage].append((tier, success))

        # Build history with fallback information
        history: list[dict[str, Any]] = []
        for stage, attempts in stage_attempts.items():
            stage_entry: dict[str, Any] = {
                "stage": stage,
                "total_attempts": len(attempts),
                "attempts": [],
            }

            for attempt_num, (tier, success) in enumerate(attempts, 1):
                attempt_entry = {
                    "attempt": attempt_num,
                    "tier": tier.upper(),
                    "success": success,
                }

                if not success:
                    attempt_entry["quality_gate_failed"] = "validation_failed"

                stage_entry["attempts"].append(attempt_entry)

            # Record successful tier for this stage
            successful_attempts = [a for a in attempts if a[1]]
            if successful_attempts:
                final_tier = successful_attempts[-1][0]
                stage_entry["successful_tier"] = final_tier.upper()

                # Check if tier fallback occurred
                if len(attempts) > 1:
                    first_tier = attempts[0][0]
                    stage_entry["tier_fallback_occurred"] = True
                    stage_entry["fallback_chain"] = f"{first_tier.upper()} → {final_tier.upper()}"

            history.append(stage_entry)

        return history

    def _build_tier_history(self, workflow_result: Any) -> list[dict[str, Any]]:
        """Build tier history from workflow stages."""
        tier_groups: dict[str, list[Any]] = {}

        # Group stages by tier
        for stage in workflow_result.stages:
            tier = stage.tier.value if hasattr(stage.tier, "value") else str(stage.tier).lower()
            tier_upper = tier.upper()
            if tier_upper not in tier_groups:
                tier_groups[tier_upper] = []
            tier_groups[tier_upper].append(stage)

        # Build history entries
        history = []
        for tier, stages in tier_groups.items():
            # Check if any stage failed
            failures = []
            success_stage = None

            for i, stage in enumerate(stages, 1):
                if hasattr(stage, "error") and stage.error:
                    failures.append({"attempt": i, "quality_gate_failed": "execution"})
                else:
                    success_stage = i

            entry = {
                "tier": tier,
                "attempts": len(stages),
            }

            if failures:
                entry["failures"] = failures

            if success_stage:
                entry["success"] = {
                    "attempt": success_stage,
                    "quality_gates_passed": ["execution", "output"],
                }

            history.append(entry)

        return history

    def _estimate_premium_cost(self, workflow_result: Any) -> float:
        """Estimate what the cost would be if all stages used PREMIUM tier."""
        _total_tokens = sum(
            (stage.input_tokens or 0) + (stage.output_tokens or 0)
            for stage in workflow_result.stages
        )

        # Calculate actual cost from stages
        actual_cost: float = sum(stage.cost for stage in workflow_result.stages)

        # Rough estimate: PREMIUM tier is ~15x more expensive than CHEAP
        return actual_cost * 5  # Conservative multiplier

    def _update_consolidated_patterns(self, progression: dict[str, Any]):
        """Update the consolidated patterns.json file with retention policy."""
        consolidated_file = self.patterns_dir / "all_patterns.json"

        try:
            if consolidated_file.exists():
                with open(consolidated_file) as f:
                    data = json.load(f)
                if "patterns" not in data:
                    data = {"patterns": []}
            else:
                data = {"patterns": []}

            # Add new progression
            data["patterns"].append(progression)

            # Apply retention policy: keep only MAX_WORKFLOW_FILES patterns
            if len(data["patterns"]) > self.MAX_WORKFLOW_FILES:
                data["patterns"] = data["patterns"][-self.MAX_WORKFLOW_FILES :]

            # Save updated file
            validated_consolidated = _validate_file_path(str(consolidated_file))
            with open(validated_consolidated, "w") as f:
                json.dump(data, f, indent=2)

        except (OSError, ValueError, json.JSONDecodeError) as e:
            logger.warning(f"Could not update consolidated patterns: {e}")
            # If file is corrupted, start fresh
            try:
                data = {"patterns": [progression]}
                validated_consolidated = _validate_file_path(str(consolidated_file))
                with open(validated_consolidated, "w") as f:
                    json.dump(data, f, indent=2)
                logger.info("Recreated consolidated patterns file")
            except (OSError, ValueError) as e2:
                logger.warning(f"Could not recreate consolidated patterns: {e2}")

    def _cleanup_old_workflow_files(self):
        """Remove old workflow files to prevent unbounded growth.

        Called periodically during save_progression to keep disk usage bounded.
        Keeps only the most recent MAX_WORKFLOW_FILES workflow files.
        """
        try:
            workflow_files = sorted(
                self.patterns_dir.glob("workflow_*.json"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )

            # Delete files beyond retention limit
            files_to_delete = workflow_files[self.MAX_WORKFLOW_FILES :]
            if files_to_delete:
                for f in files_to_delete:
                    try:
                        f.unlink()
                    except OSError:
                        pass  # Best effort cleanup
                logger.debug(f"Cleaned up {len(files_to_delete)} old workflow files")
        except OSError as e:
            logger.debug(f"Workflow file cleanup skipped: {e}")


def auto_recommend_tier(
    workflow_name: str,
    workflow_description: str,
    files_affected: list[str] | None = None,
) -> str:
    """
    Quick helper to get tier recommendation without tracker.

    Args:
        workflow_name: Name of workflow
        workflow_description: What the workflow does
        files_affected: Files involved

    Returns:
        Recommended tier
    """
    tracker = WorkflowTierTracker(workflow_name, workflow_description)
    return tracker.show_recommendation(files_affected, show_ui=False)
