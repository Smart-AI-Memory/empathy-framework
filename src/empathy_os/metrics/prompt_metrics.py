"""Prompt performance metrics tracking

Tracks token usage, latency, success rates, and other metrics for
XML-enhanced prompts to enable optimization and A/B testing.

Copyright 2026 Smart-AI-Memory
Licensed under Fair Source License 0.9
"""

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from empathy_os.config import _validate_file_path

logger = logging.getLogger(__name__)


@dataclass
class PromptMetrics:
    """Metrics for a single prompt execution.

    Tracks comprehensive performance data for prompt optimization
    and A/B testing.

    Attributes:
        timestamp: ISO format timestamp of execution
        workflow: Workflow name (e.g., "code_review", "bug_predict")
        agent_role: Role of the agent (e.g., "Code Reviewer")
        task_description: Brief description of task (truncated to 100 chars)
        model: Model name (e.g., "gpt-4", "claude-sonnet")
        prompt_tokens: Number of input tokens
        completion_tokens: Number of output tokens
        total_tokens: Total tokens (input + output)
        latency_ms: Execution time in milliseconds
        retry_count: Number of retry attempts
        parsing_success: Whether XML parsing succeeded
        validation_success: Whether XML validation succeeded (None if not validated)
        error_message: Error message if execution failed (None if successful)
        xml_structure_used: Whether XML-enhanced prompts were used
    """

    timestamp: str
    workflow: str
    agent_role: str
    task_description: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    latency_ms: float
    retry_count: int
    parsing_success: bool
    validation_success: bool | None
    error_message: str | None
    xml_structure_used: bool

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "PromptMetrics":
        """Create from dictionary (deserialization)."""
        return cls(**data)


class MetricsTracker:
    """Tracks and persists prompt metrics to disk.

    Uses JSON Lines format for append-only writes and efficient reading.
    Metrics are stored in .empathy/prompt_metrics.json by default.

    Usage:
        tracker = MetricsTracker()
        metric = PromptMetrics(...)
        tracker.log_metric(metric)

        summary = tracker.get_summary(workflow="code_review")
        print(f"Avg tokens: {summary['avg_tokens']}")
    """

    def __init__(self, metrics_file: str = ".empathy/prompt_metrics.json"):
        """Initialize metrics tracker.

        Args:
            metrics_file: Path to metrics file (JSON Lines format)
        """
        self.metrics_file = Path(metrics_file)
        self.metrics_file.parent.mkdir(parents=True, exist_ok=True)

        # Create file if it doesn't exist
        if not self.metrics_file.exists():
            validated_path = _validate_file_path(str(self.metrics_file))
            validated_path.write_text("")

    def log_metric(self, metric: PromptMetrics) -> None:
        """Log a single metric to file (JSON Lines format).

        Args:
            metric: PromptMetrics instance to log
        """
        try:
            validated_path = _validate_file_path(str(self.metrics_file))
            with open(validated_path, "a") as f:
                f.write(json.dumps(metric.to_dict()) + "\n")
        except (OSError, ValueError) as e:
            logger.error(f"Failed to log metric: {e}")

    def get_metrics(
        self,
        workflow: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[PromptMetrics]:
        """Retrieve metrics with optional filtering.

        Args:
            workflow: Filter by workflow name (None = all workflows)
            start_date: Filter by start date (None = no lower bound)
            end_date: Filter by end date (None = no upper bound)

        Returns:
            List of PromptMetrics matching filters
        """
        metrics: list[PromptMetrics] = []

        try:
            if not self.metrics_file.exists():
                return metrics

            with open(self.metrics_file) as f:
                for line in f:
                    if line.strip():
                        data = json.loads(line)
                        metric = PromptMetrics.from_dict(data)

                        # Apply filters
                        if workflow and metric.workflow != workflow:
                            continue

                        metric_time = datetime.fromisoformat(metric.timestamp)
                        if start_date and metric_time < start_date:
                            continue
                        if end_date and metric_time > end_date:
                            continue

                        metrics.append(metric)
        except Exception as e:
            logger.error(f"Failed to read metrics: {e}")

        return metrics

    def get_summary(self, workflow: str | None = None) -> dict[str, Any]:
        """Get aggregated metrics summary.

        Args:
            workflow: Filter by workflow name (None = all workflows)

        Returns:
            Dictionary with aggregated metrics:
            - total_prompts: Total number of prompts
            - avg_tokens: Average total tokens
            - avg_latency_ms: Average latency in milliseconds
            - success_rate: Ratio of successful parses
            - retry_rate: Average retry count per prompt
        """
        metrics = self.get_metrics(workflow=workflow)

        if not metrics:
            return {
                "total_prompts": 0,
                "avg_tokens": 0,
                "avg_latency_ms": 0,
                "success_rate": 0,
                "retry_rate": 0,
            }

        total_prompts = len(metrics)
        total_tokens = sum(m.total_tokens for m in metrics)
        total_latency = sum(m.latency_ms for m in metrics)
        successful = sum(1 for m in metrics if m.parsing_success)
        retries = sum(m.retry_count for m in metrics)

        return {
            "total_prompts": total_prompts,
            "avg_tokens": total_tokens / total_prompts,
            "avg_latency_ms": total_latency / total_prompts,
            "success_rate": successful / total_prompts,
            "retry_rate": retries / total_prompts,
        }
