"""Success Criteria and Measurement System

Define and measure success for generated workflows.

Success criteria allow users to:
1. Define what "done" looks like for their workflow
2. Track progress toward goals
3. Measure effectiveness over time
4. Iterate and improve workflows

Copyright 2026 Smart-AI-Memory
Licensed under Fair Source License 0.9
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable


class MetricType(Enum):
    """Types of success metrics."""

    # Numeric metrics
    COUNT = "count"  # Integer count (e.g., issues found)
    PERCENTAGE = "percentage"  # 0-100 percentage
    RATIO = "ratio"  # 0-1 ratio
    DURATION = "duration"  # Time in seconds

    # Boolean metrics
    BOOLEAN = "boolean"  # True/False

    # Comparison metrics
    IMPROVEMENT = "improvement"  # Before/after comparison
    THRESHOLD = "threshold"  # Above/below threshold

    # Quality metrics
    SCORE = "score"  # 0-10 quality score
    RATING = "rating"  # Categorical (good, moderate, poor)


class MetricDirection(Enum):
    """Which direction indicates success."""

    HIGHER_IS_BETTER = "higher"  # More issues found = better
    LOWER_IS_BETTER = "lower"  # Less time = better
    TARGET_VALUE = "target"  # Specific value is best
    RANGE = "range"  # Within a range is success


@dataclass
class SuccessMetric:
    """A single success metric definition.

    Example:
        >>> metric = SuccessMetric(
        ...     id="security_issues_found",
        ...     name="Security Issues Detected",
        ...     description="Number of security vulnerabilities identified",
        ...     metric_type=MetricType.COUNT,
        ...     direction=MetricDirection.HIGHER_IS_BETTER,
        ...     target_value=None,  # No specific target
        ...     minimum_value=0,
        ...     unit="issues"
        ... )
    """

    # Unique metric identifier
    id: str

    # Display name
    name: str

    # Description of what this measures
    description: str

    # Type of metric
    metric_type: MetricType

    # Which direction indicates success
    direction: MetricDirection = MetricDirection.HIGHER_IS_BETTER

    # Target value (for TARGET_VALUE direction)
    target_value: float | None = None

    # Minimum acceptable value
    minimum_value: float | None = None

    # Maximum acceptable value
    maximum_value: float | None = None

    # Unit of measurement
    unit: str = ""

    # Weight for composite scoring (0-1)
    weight: float = 1.0

    # Whether this is a primary success indicator
    is_primary: bool = False

    # How to extract this metric from workflow output
    extraction_path: str = ""  # JSONPath-like expression

    # Custom extraction function
    extractor: Callable[[dict], float | bool] | None = None

    def evaluate(
        self,
        value: float | bool,
        baseline: float | bool | None = None,
    ) -> tuple[bool, float, str]:
        """Evaluate if a value meets this metric's success criteria.

        Args:
            value: The measured value
            baseline: Optional baseline for comparison

        Returns:
            Tuple of (met_criteria, score 0-1, explanation)
        """
        # Boolean metrics
        if self.metric_type == MetricType.BOOLEAN:
            if isinstance(value, bool):
                met = value
                score = 1.0 if value else 0.0
                explanation = "Criteria met" if met else "Criteria not met"
                return met, score, explanation

        # Ensure numeric value for other types
        if not isinstance(value, (int, float)):
            return False, 0.0, f"Expected numeric value, got {type(value)}"

        # Calculate score based on direction
        if self.direction == MetricDirection.HIGHER_IS_BETTER:
            if self.minimum_value is not None:
                met = value >= self.minimum_value
                # Score is ratio of value to minimum (capped at 1.0)
                score = min(value / self.minimum_value, 1.0) if self.minimum_value > 0 else 1.0
            else:
                met = True  # No minimum, always met
                score = 1.0

        elif self.direction == MetricDirection.LOWER_IS_BETTER:
            if self.maximum_value is not None:
                met = value <= self.maximum_value
                # Score is inverse ratio (lower is better)
                score = max(1.0 - (value / self.maximum_value), 0.0) if self.maximum_value > 0 else 1.0
            else:
                met = True
                score = 1.0

        elif self.direction == MetricDirection.TARGET_VALUE:
            if self.target_value is not None:
                deviation = abs(value - self.target_value)
                # Allow 10% tolerance by default
                tolerance = self.target_value * 0.1 if self.target_value > 0 else 1.0
                met = deviation <= tolerance
                score = max(1.0 - (deviation / max(tolerance, 0.001)), 0.0)
            else:
                met = True
                score = 1.0

        elif self.direction == MetricDirection.RANGE:
            min_val = self.minimum_value or float("-inf")
            max_val = self.maximum_value or float("inf")
            met = min_val <= value <= max_val
            if met:
                # Score based on position in range (center = best)
                range_size = max_val - min_val
                if range_size > 0 and range_size != float("inf"):
                    center = (min_val + max_val) / 2
                    distance_from_center = abs(value - center)
                    score = 1.0 - (distance_from_center / (range_size / 2))
                else:
                    score = 1.0
            else:
                score = 0.0
        else:
            met = True
            score = 1.0

        # Generate explanation
        explanation = self._generate_explanation(value, met, score, baseline)

        return met, score, explanation

    def _generate_explanation(
        self,
        value: float | bool,
        met: bool,
        score: float,
        baseline: float | bool | None,
    ) -> str:
        """Generate human-readable explanation of the evaluation."""
        parts = []

        # Value statement
        if self.unit:
            parts.append(f"Measured: {value} {self.unit}")
        else:
            parts.append(f"Measured: {value}")

        # Comparison to baseline
        if baseline is not None and isinstance(value, (int, float)) and isinstance(baseline, (int, float)):
            diff = value - baseline
            pct_change = (diff / baseline * 100) if baseline != 0 else 0
            direction = "↑" if diff > 0 else "↓" if diff < 0 else "→"
            parts.append(f"vs baseline: {direction} {abs(pct_change):.1f}%")

        # Target comparison
        if self.direction == MetricDirection.TARGET_VALUE and self.target_value is not None:
            parts.append(f"Target: {self.target_value} {self.unit}".strip())

        # Result
        result = "✓ Met" if met else "✗ Not met"
        parts.append(f"{result} (score: {score:.1%})")

        return " | ".join(parts)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "metric_type": self.metric_type.value,
            "direction": self.direction.value,
            "target_value": self.target_value,
            "minimum_value": self.minimum_value,
            "maximum_value": self.maximum_value,
            "unit": self.unit,
            "weight": self.weight,
            "is_primary": self.is_primary,
            "extraction_path": self.extraction_path,
        }


@dataclass
class MetricResult:
    """Result of evaluating a single metric."""

    metric_id: str
    value: float | bool
    met_criteria: bool
    score: float
    explanation: str
    baseline: float | bool | None = None
    timestamp: str = ""


@dataclass
class SuccessCriteria:
    """Complete success criteria for a workflow.

    Example:
        >>> criteria = SuccessCriteria(
        ...     id="code_review_success",
        ...     name="Code Review Success Criteria",
        ...     description="Measures effectiveness of automated code review",
        ...     metrics=[
        ...         SuccessMetric(
        ...             id="issues_found",
        ...             name="Issues Found",
        ...             metric_type=MetricType.COUNT,
        ...             is_primary=True
        ...         ),
        ...         SuccessMetric(
        ...             id="review_time",
        ...             name="Review Time",
        ...             metric_type=MetricType.DURATION,
        ...             direction=MetricDirection.LOWER_IS_BETTER,
        ...             maximum_value=60,  # seconds
        ...         ),
        ...     ],
        ...     success_threshold=0.7  # 70% overall score = success
        ... )
    """

    # Unique identifier
    id: str = ""

    # Display name
    name: str = ""

    # Description
    description: str = ""

    # List of metrics
    metrics: list[SuccessMetric] = field(default_factory=list)

    # Threshold for overall success (0-1)
    success_threshold: float = 0.7

    # Whether ALL metrics must be met (vs weighted average)
    require_all: bool = False

    # Minimum primary metrics that must pass
    min_primary_metrics: int = 1

    # Custom success evaluator
    custom_evaluator: Callable[[dict[str, MetricResult]], bool] | None = None

    def add_metric(self, metric: SuccessMetric) -> None:
        """Add a metric to the criteria."""
        self.metrics.append(metric)

    def get_primary_metrics(self) -> list[SuccessMetric]:
        """Get all primary success indicators."""
        return [m for m in self.metrics if m.is_primary]

    def evaluate(
        self,
        workflow_output: dict[str, Any],
        baselines: dict[str, float | bool] | None = None,
    ) -> SuccessEvaluation:
        """Evaluate workflow output against success criteria.

        Args:
            workflow_output: The workflow's output to evaluate
            baselines: Optional baseline values for comparison

        Returns:
            SuccessEvaluation with detailed results
        """
        baselines = baselines or {}
        results: list[MetricResult] = []
        timestamp = datetime.now().isoformat()

        # Evaluate each metric
        for metric in self.metrics:
            # Extract value from output
            value = self._extract_metric_value(metric, workflow_output)

            if value is None:
                # Metric not found in output
                results.append(MetricResult(
                    metric_id=metric.id,
                    value=0,
                    met_criteria=False,
                    score=0.0,
                    explanation=f"Metric '{metric.name}' not found in output",
                    timestamp=timestamp,
                ))
                continue

            # Get baseline if available
            baseline = baselines.get(metric.id)

            # Evaluate
            met, score, explanation = metric.evaluate(value, baseline)

            results.append(MetricResult(
                metric_id=metric.id,
                value=value,
                met_criteria=met,
                score=score,
                explanation=explanation,
                baseline=baseline,
                timestamp=timestamp,
            ))

        # Calculate overall success
        return self._calculate_overall_success(results)

    def _extract_metric_value(
        self,
        metric: SuccessMetric,
        output: dict[str, Any],
    ) -> float | bool | None:
        """Extract metric value from workflow output."""
        # Use custom extractor if provided
        if metric.extractor:
            try:
                return metric.extractor(output)
            except (KeyError, TypeError, ValueError):
                return None

        # Use extraction path
        if metric.extraction_path:
            try:
                value = output
                for key in metric.extraction_path.split("."):
                    if isinstance(value, dict):
                        value = value[key]
                    elif isinstance(value, list) and key.isdigit():
                        value = value[int(key)]
                    else:
                        return None
                return value
            except (KeyError, IndexError, TypeError):
                return None

        # Try direct key match
        if metric.id in output:
            return output[metric.id]

        # Try nested in 'metrics' key
        if "metrics" in output and isinstance(output["metrics"], dict):
            if metric.id in output["metrics"]:
                return output["metrics"][metric.id]

        return None

    def _calculate_overall_success(
        self,
        results: list[MetricResult],
    ) -> SuccessEvaluation:
        """Calculate overall success from metric results."""
        if not results:
            return SuccessEvaluation(
                overall_success=False,
                overall_score=0.0,
                metric_results=results,
                summary="No metrics to evaluate",
            )

        # Check primary metrics
        primary_results = [
            r for r in results
            if any(m.id == r.metric_id and m.is_primary for m in self.metrics)
        ]
        primary_passed = sum(1 for r in primary_results if r.met_criteria)

        # Check if minimum primary metrics are met
        primary_check = primary_passed >= self.min_primary_metrics

        # Check if all required
        if self.require_all:
            all_met = all(r.met_criteria for r in results)
            overall_success = all_met and primary_check
            overall_score = 1.0 if overall_success else sum(r.score for r in results) / len(results)
        else:
            # Weighted average score
            total_weight = sum(
                m.weight for m in self.metrics
                if any(r.metric_id == m.id for r in results)
            )

            if total_weight > 0:
                weighted_score = sum(
                    r.score * next((m.weight for m in self.metrics if m.id == r.metric_id), 1.0)
                    for r in results
                ) / total_weight
            else:
                weighted_score = sum(r.score for r in results) / len(results)

            overall_score = weighted_score
            overall_success = overall_score >= self.success_threshold and primary_check

        # Custom evaluator override
        if self.custom_evaluator:
            results_dict = {r.metric_id: r for r in results}
            overall_success = self.custom_evaluator(results_dict)

        # Generate summary
        summary = self._generate_summary(results, overall_success, overall_score)

        return SuccessEvaluation(
            overall_success=overall_success,
            overall_score=overall_score,
            metric_results=results,
            summary=summary,
            primary_metrics_passed=primary_passed,
            total_primary_metrics=len(primary_results),
        )

    def _generate_summary(
        self,
        results: list[MetricResult],
        success: bool,
        score: float,
    ) -> str:
        """Generate human-readable summary."""
        status = "✓ SUCCESS" if success else "✗ NOT MET"
        met_count = sum(1 for r in results if r.met_criteria)

        lines = [
            f"{status} - Overall score: {score:.1%}",
            f"Metrics: {met_count}/{len(results)} met criteria",
            "",
            "Details:",
        ]

        for result in results:
            metric = next((m for m in self.metrics if m.id == result.metric_id), None)
            name = metric.name if metric else result.metric_id
            indicator = "✓" if result.met_criteria else "✗"
            lines.append(f"  {indicator} {name}: {result.explanation}")

        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "metrics": [m.to_dict() for m in self.metrics],
            "success_threshold": self.success_threshold,
            "require_all": self.require_all,
            "min_primary_metrics": self.min_primary_metrics,
        }


@dataclass
class SuccessEvaluation:
    """Result of evaluating success criteria."""

    # Whether overall success criteria were met
    overall_success: bool

    # Overall score (0-1)
    overall_score: float

    # Individual metric results
    metric_results: list[MetricResult]

    # Human-readable summary
    summary: str

    # Primary metrics that passed
    primary_metrics_passed: int = 0

    # Total primary metrics
    total_primary_metrics: int = 0

    # Timestamp of evaluation
    evaluated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "overall_success": self.overall_success,
            "overall_score": self.overall_score,
            "metric_results": [
                {
                    "metric_id": r.metric_id,
                    "value": r.value,
                    "met_criteria": r.met_criteria,
                    "score": r.score,
                    "explanation": r.explanation,
                    "baseline": r.baseline,
                }
                for r in self.metric_results
            ],
            "summary": self.summary,
            "primary_metrics_passed": self.primary_metrics_passed,
            "total_primary_metrics": self.total_primary_metrics,
            "evaluated_at": self.evaluated_at,
        }


# =============================================================================
# PREDEFINED SUCCESS CRITERIA TEMPLATES
# =============================================================================


def code_review_criteria() -> SuccessCriteria:
    """Create standard success criteria for code review workflows."""
    return SuccessCriteria(
        id="code_review_success",
        name="Code Review Success",
        description="Standard metrics for code review effectiveness",
        metrics=[
            SuccessMetric(
                id="issues_found",
                name="Issues Found",
                description="Number of issues identified",
                metric_type=MetricType.COUNT,
                direction=MetricDirection.HIGHER_IS_BETTER,
                is_primary=True,
                weight=1.0,
                extraction_path="findings_count",
            ),
            SuccessMetric(
                id="severity_coverage",
                name="Severity Coverage",
                description="Percentage of severity levels covered",
                metric_type=MetricType.PERCENTAGE,
                direction=MetricDirection.HIGHER_IS_BETTER,
                minimum_value=50,
                weight=0.8,
                extraction_path="severity_coverage",
            ),
            SuccessMetric(
                id="review_time",
                name="Review Duration",
                description="Time to complete review",
                metric_type=MetricType.DURATION,
                direction=MetricDirection.LOWER_IS_BETTER,
                maximum_value=120,  # 2 minutes
                unit="seconds",
                weight=0.6,
                extraction_path="duration_seconds",
            ),
            SuccessMetric(
                id="actionable_recommendations",
                name="Actionable Recommendations",
                description="Whether recommendations are actionable",
                metric_type=MetricType.BOOLEAN,
                is_primary=True,
                weight=1.0,
                extraction_path="has_recommendations",
            ),
        ],
        success_threshold=0.7,
        min_primary_metrics=1,
    )


def security_audit_criteria() -> SuccessCriteria:
    """Create success criteria for security audit workflows."""
    return SuccessCriteria(
        id="security_audit_success",
        name="Security Audit Success",
        description="Metrics for security audit effectiveness",
        metrics=[
            SuccessMetric(
                id="vulnerabilities_found",
                name="Vulnerabilities Found",
                description="Security vulnerabilities identified",
                metric_type=MetricType.COUNT,
                direction=MetricDirection.HIGHER_IS_BETTER,
                is_primary=True,
                weight=1.0,
                extraction_path="vulnerabilities.count",
            ),
            SuccessMetric(
                id="critical_issues",
                name="Critical Issues",
                description="High/critical severity issues found",
                metric_type=MetricType.COUNT,
                direction=MetricDirection.HIGHER_IS_BETTER,
                is_primary=True,
                weight=1.2,  # Extra weight for critical issues
                extraction_path="vulnerabilities.critical_count",
            ),
            SuccessMetric(
                id="owasp_coverage",
                name="OWASP Coverage",
                description="OWASP Top 10 categories checked",
                metric_type=MetricType.PERCENTAGE,
                direction=MetricDirection.HIGHER_IS_BETTER,
                minimum_value=80,
                weight=0.9,
                extraction_path="owasp_coverage_percent",
            ),
            SuccessMetric(
                id="false_positive_rate",
                name="False Positive Rate",
                description="Estimated false positive rate",
                metric_type=MetricType.PERCENTAGE,
                direction=MetricDirection.LOWER_IS_BETTER,
                maximum_value=20,
                weight=0.7,
                extraction_path="estimated_fp_rate",
            ),
        ],
        success_threshold=0.75,
        min_primary_metrics=1,
    )


def test_generation_criteria() -> SuccessCriteria:
    """Create success criteria for test generation workflows."""
    return SuccessCriteria(
        id="test_generation_success",
        name="Test Generation Success",
        description="Metrics for test generation effectiveness",
        metrics=[
            SuccessMetric(
                id="tests_generated",
                name="Tests Generated",
                description="Number of test cases generated",
                metric_type=MetricType.COUNT,
                direction=MetricDirection.HIGHER_IS_BETTER,
                minimum_value=1,
                is_primary=True,
                weight=1.0,
                extraction_path="tests.count",
            ),
            SuccessMetric(
                id="coverage_increase",
                name="Coverage Increase",
                description="Increase in code coverage",
                metric_type=MetricType.IMPROVEMENT,
                direction=MetricDirection.HIGHER_IS_BETTER,
                minimum_value=5,  # At least 5% increase
                unit="%",
                weight=1.0,
                extraction_path="coverage.increase_percent",
            ),
            SuccessMetric(
                id="tests_passing",
                name="Tests Passing",
                description="Percentage of generated tests that pass",
                metric_type=MetricType.PERCENTAGE,
                direction=MetricDirection.HIGHER_IS_BETTER,
                minimum_value=80,
                is_primary=True,
                weight=1.2,
                extraction_path="tests.pass_rate",
            ),
            SuccessMetric(
                id="edge_cases_covered",
                name="Edge Cases Covered",
                description="Number of edge cases with tests",
                metric_type=MetricType.COUNT,
                direction=MetricDirection.HIGHER_IS_BETTER,
                weight=0.8,
                extraction_path="edge_cases.count",
            ),
        ],
        success_threshold=0.7,
        min_primary_metrics=2,
    )
