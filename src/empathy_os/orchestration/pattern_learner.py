"""Pattern Learning System - Grammar that evolves from experience.

This module implements the learning grammar that tracks pattern success
and recommends optimal compositions based on historical data.

Features:
    - Track success metrics for each pattern execution
    - Memory + file storage for fast access and persistence
    - Hybrid recommendation: similarity matching → statistical fallback

Security:
    - No eval() or exec() usage
    - File paths validated before writing
    - JSON serialization only (no pickle)
"""

import json
import logging
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from empathy_os.config import _validate_file_path

logger = logging.getLogger(__name__)


# =============================================================================
# Data Models
# =============================================================================


@dataclass
class ExecutionRecord:
    """Record of a single pattern execution.

    Captures the essential metrics for learning.

    Attributes:
        pattern: Pattern/strategy name used
        success: Whether execution succeeded
        duration_seconds: Execution time
        cost: Estimated cost (tokens * rate)
        confidence: Aggregate confidence score
        context_features: Key features of the execution context
        timestamp: When the execution occurred
    """

    pattern: str
    success: bool
    duration_seconds: float
    cost: float = 0.0
    confidence: float = 0.0
    context_features: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ExecutionRecord":
        """Create from dictionary."""
        return cls(**data)


@dataclass
class PatternStats:
    """Aggregated statistics for a pattern.

    Attributes:
        pattern: Pattern/strategy name
        total_executions: Number of times executed
        success_count: Number of successful executions
        total_duration: Sum of all execution durations
        total_cost: Sum of all execution costs
        avg_confidence: Average confidence across executions
    """

    pattern: str
    total_executions: int = 0
    success_count: int = 0
    total_duration: float = 0.0
    total_cost: float = 0.0
    avg_confidence: float = 0.0

    @property
    def success_rate(self) -> float:
        """Calculate success rate (0.0 - 1.0)."""
        if self.total_executions == 0:
            return 0.0
        return self.success_count / self.total_executions

    @property
    def avg_duration(self) -> float:
        """Calculate average execution duration."""
        if self.total_executions == 0:
            return 0.0
        return self.total_duration / self.total_executions

    @property
    def avg_cost(self) -> float:
        """Calculate average execution cost."""
        if self.total_executions == 0:
            return 0.0
        return self.total_cost / self.total_executions

    def update(self, record: ExecutionRecord) -> None:
        """Update stats with a new execution record.

        Args:
            record: Execution record to incorporate
        """
        self.total_executions += 1
        if record.success:
            self.success_count += 1
        self.total_duration += record.duration_seconds
        self.total_cost += record.cost

        # Running average for confidence
        n = self.total_executions
        self.avg_confidence = (
            (self.avg_confidence * (n - 1) + record.confidence) / n
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "pattern": self.pattern,
            "total_executions": self.total_executions,
            "success_count": self.success_count,
            "total_duration": self.total_duration,
            "total_cost": self.total_cost,
            "avg_confidence": self.avg_confidence,
            # Computed properties
            "success_rate": self.success_rate,
            "avg_duration": self.avg_duration,
            "avg_cost": self.avg_cost,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PatternStats":
        """Create from dictionary."""
        return cls(
            pattern=data["pattern"],
            total_executions=data.get("total_executions", 0),
            success_count=data.get("success_count", 0),
            total_duration=data.get("total_duration", 0.0),
            total_cost=data.get("total_cost", 0.0),
            avg_confidence=data.get("avg_confidence", 0.0),
        )


@dataclass
class ContextSignature:
    """Signature of a context for similarity matching.

    Extracts key features from execution context for comparison.

    Attributes:
        task_type: Type of task (e.g., "code_review", "test_gen")
        agent_count: Number of agents involved
        has_conditions: Whether conditionals were used
        has_nesting: Whether nested workflows were used
        priority: Task priority level
    """

    task_type: str = ""
    agent_count: int = 0
    has_conditions: bool = False
    has_nesting: bool = False
    priority: str = "normal"

    @classmethod
    def from_context(cls, context: dict[str, Any]) -> "ContextSignature":
        """Extract signature from execution context.

        Args:
            context: Execution context dictionary

        Returns:
            ContextSignature with extracted features
        """
        return cls(
            task_type=context.get("task_type", context.get("_task_type", "")),
            agent_count=len(context.get("agents", [])),
            has_conditions="_conditional" in context,
            has_nesting="_nesting" in context,
            priority=context.get("priority", "normal"),
        )

    def similarity(self, other: "ContextSignature") -> float:
        """Calculate similarity score with another signature.

        Args:
            other: Signature to compare with

        Returns:
            Similarity score (0.0 - 1.0)
        """
        score = 0.0
        max_score = 0.0

        # Task type match (highest weight)
        max_score += 3.0
        if self.task_type and other.task_type:
            if self.task_type == other.task_type:
                score += 3.0
            elif self.task_type.split("_")[0] == other.task_type.split("_")[0]:
                score += 1.5  # Partial match

        # Agent count similarity
        max_score += 1.0
        if self.agent_count > 0 and other.agent_count > 0:
            ratio = min(self.agent_count, other.agent_count) / max(
                self.agent_count, other.agent_count
            )
            score += ratio

        # Boolean features
        max_score += 2.0
        if self.has_conditions == other.has_conditions:
            score += 1.0
        if self.has_nesting == other.has_nesting:
            score += 1.0

        # Priority match
        max_score += 1.0
        if self.priority == other.priority:
            score += 1.0

        return score / max_score if max_score > 0 else 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ContextSignature":
        """Create from dictionary."""
        return cls(**data)


# =============================================================================
# Storage Layer
# =============================================================================


class LearningStore:
    """Memory + file storage for learning data.

    Maintains an in-memory cache for fast access with
    periodic persistence to a JSON file.

    Attributes:
        file_path: Path to persistence file
        _records: In-memory execution records
        _stats: In-memory pattern statistics
        _dirty: Whether in-memory data needs saving
    """

    DEFAULT_FILE = "patterns/learning_memory.json"

    def __init__(self, file_path: str | None = None):
        """Initialize learning store.

        Args:
            file_path: Path to persistence file (default: patterns/learning_memory.json)
        """
        self.file_path = Path(file_path or self.DEFAULT_FILE)
        self._records: list[ExecutionRecord] = []
        self._stats: dict[str, PatternStats] = {}
        self._context_index: dict[str, list[int]] = defaultdict(list)
        self._dirty = False

        # Load existing data if available
        self._load()

    def _load(self) -> None:
        """Load data from file if it exists."""
        if not self.file_path.exists():
            logger.info(f"No existing learning data at {self.file_path}")
            return

        try:
            with self.file_path.open("r") as f:
                data = json.load(f)

            # Load records
            self._records = [
                ExecutionRecord.from_dict(r) for r in data.get("records", [])
            ]

            # Load stats
            self._stats = {
                s["pattern"]: PatternStats.from_dict(s)
                for s in data.get("stats", [])
            }

            # Rebuild context index
            for i, record in enumerate(self._records):
                sig = ContextSignature(
                    task_type=record.context_features.get("task_type", "")
                )
                self._context_index[sig.task_type].append(i)

            logger.info(
                f"Loaded {len(self._records)} records, "
                f"{len(self._stats)} pattern stats from {self.file_path}"
            )
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse learning data: {e}")
        except Exception as e:
            logger.exception(f"Failed to load learning data: {e}")

    def save(self) -> None:
        """Save data to file."""
        if not self._dirty:
            return

        # Ensure directory exists
        self.file_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "records": [r.to_dict() for r in self._records],
            "stats": [s.to_dict() for s in self._stats.values()],
            "metadata": {
                "saved_at": datetime.now().isoformat(),
                "total_records": len(self._records),
                "patterns_tracked": len(self._stats),
            },
        }

        try:
            validated_path = _validate_file_path(str(self.file_path))
            with validated_path.open("w") as f:
                json.dump(data, f, indent=2)
            self._dirty = False
            logger.info(f"Saved learning data to {validated_path}")
        except (OSError, ValueError) as e:
            logger.exception(f"Failed to save learning data: {e}")

    def add_record(self, record: ExecutionRecord) -> None:
        """Add an execution record.

        Args:
            record: Record to add
        """
        self._records.append(record)

        # Update stats
        if record.pattern not in self._stats:
            self._stats[record.pattern] = PatternStats(pattern=record.pattern)
        self._stats[record.pattern].update(record)

        # Update context index
        task_type = record.context_features.get("task_type", "")
        self._context_index[task_type].append(len(self._records) - 1)

        self._dirty = True

        # Auto-save periodically
        if len(self._records) % 10 == 0:
            self.save()

    def get_stats(self, pattern: str) -> PatternStats | None:
        """Get statistics for a pattern.

        Args:
            pattern: Pattern name

        Returns:
            PatternStats or None if not tracked
        """
        return self._stats.get(pattern)

    def get_all_stats(self) -> list[PatternStats]:
        """Get all pattern statistics.

        Returns:
            List of PatternStats sorted by success rate
        """
        return sorted(
            self._stats.values(),
            key=lambda s: s.success_rate,
            reverse=True,
        )

    def find_similar_records(
        self, signature: ContextSignature, limit: int = 10
    ) -> list[tuple[ExecutionRecord, float]]:
        """Find records with similar context.

        Args:
            signature: Context signature to match
            limit: Maximum records to return

        Returns:
            List of (record, similarity_score) tuples
        """
        scored: list[tuple[ExecutionRecord, float]] = []

        for record in self._records:
            record_sig = ContextSignature(
                task_type=record.context_features.get("task_type", ""),
                agent_count=record.context_features.get("agent_count", 0),
                has_conditions=record.context_features.get("has_conditions", False),
                has_nesting=record.context_features.get("has_nesting", False),
                priority=record.context_features.get("priority", "normal"),
            )
            score = signature.similarity(record_sig)
            if score > 0.3:  # Minimum threshold
                scored.append((record, score))

        # Sort by similarity and return top results
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:limit]


# =============================================================================
# Recommendation Engine
# =============================================================================


@dataclass
class PatternRecommendation:
    """A pattern recommendation.

    Attributes:
        pattern: Recommended pattern name
        confidence: Confidence in recommendation (0.0 - 1.0)
        reason: Why this pattern was recommended
        expected_success_rate: Predicted success rate
        expected_duration: Predicted duration
    """

    pattern: str
    confidence: float
    reason: str
    expected_success_rate: float = 0.0
    expected_duration: float = 0.0


class PatternRecommender:
    """Hybrid recommendation engine for patterns.

    Uses similarity matching first, falls back to statistical ranking.
    """

    def __init__(self, store: LearningStore):
        """Initialize recommender.

        Args:
            store: Learning store with historical data
        """
        self.store = store

    def recommend(
        self, context: dict[str, Any], top_k: int = 3
    ) -> list[PatternRecommendation]:
        """Recommend patterns for a context.

        Uses hybrid approach:
        1. Find similar past contexts
        2. Recommend patterns that worked for them
        3. Fall back to overall statistics if no matches

        Args:
            context: Current execution context
            top_k: Number of recommendations to return

        Returns:
            List of PatternRecommendation
        """
        signature = ContextSignature.from_context(context)
        recommendations: list[PatternRecommendation] = []

        # Phase 1: Similarity matching
        similar = self.store.find_similar_records(signature, limit=20)
        if similar:
            recommendations = self._recommend_from_similar(similar, top_k)

        # Phase 2: Statistical fallback
        if len(recommendations) < top_k:
            statistical = self._recommend_statistical(top_k - len(recommendations))
            recommendations.extend(statistical)

        return recommendations[:top_k]

    def _recommend_from_similar(
        self, similar: list[tuple[ExecutionRecord, float]], top_k: int
    ) -> list[PatternRecommendation]:
        """Generate recommendations from similar records.

        Args:
            similar: List of (record, similarity) tuples
            top_k: Number of recommendations

        Returns:
            List of recommendations
        """
        # Aggregate by pattern
        pattern_scores: dict[str, dict[str, Any]] = defaultdict(
            lambda: {"total_similarity": 0, "success_similarity": 0, "count": 0}
        )

        for record, similarity in similar:
            pattern_scores[record.pattern]["count"] += 1
            pattern_scores[record.pattern]["total_similarity"] += similarity
            if record.success:
                pattern_scores[record.pattern]["success_similarity"] += similarity

        # Calculate weighted success rate
        recommendations = []
        for pattern, scores in pattern_scores.items():
            if scores["total_similarity"] > 0:
                weighted_success = (
                    scores["success_similarity"] / scores["total_similarity"]
                )
                stats = self.store.get_stats(pattern)

                recommendations.append(
                    PatternRecommendation(
                        pattern=pattern,
                        confidence=min(weighted_success, 0.95),
                        reason=f"Worked in {scores['count']} similar contexts",
                        expected_success_rate=stats.success_rate if stats else 0,
                        expected_duration=stats.avg_duration if stats else 0,
                    )
                )

        # Sort by confidence
        recommendations.sort(key=lambda r: r.confidence, reverse=True)
        return recommendations[:top_k]

    def _recommend_statistical(self, top_k: int) -> list[PatternRecommendation]:
        """Generate recommendations from overall statistics.

        Args:
            top_k: Number of recommendations

        Returns:
            List of recommendations based on global stats
        """
        all_stats = self.store.get_all_stats()
        recommendations = []

        for stats in all_stats[:top_k]:
            if stats.total_executions >= 3:  # Minimum sample size
                recommendations.append(
                    PatternRecommendation(
                        pattern=stats.pattern,
                        confidence=stats.success_rate * 0.8,  # Slight penalty
                        reason=f"High overall success rate ({stats.success_rate:.0%})",
                        expected_success_rate=stats.success_rate,
                        expected_duration=stats.avg_duration,
                    )
                )

        return recommendations


# =============================================================================
# Main Interface
# =============================================================================


class PatternLearner:
    """Main interface for the learning grammar system.

    Provides a simple API for recording executions and getting recommendations.

    Example:
        >>> learner = PatternLearner()
        >>> # Record an execution
        >>> learner.record(
        ...     pattern="sequential",
        ...     success=True,
        ...     duration=2.5,
        ...     cost=0.05,
        ...     context={"task_type": "code_review"}
        ... )
        >>> # Get recommendations
        >>> recs = learner.recommend({"task_type": "code_review"})
        >>> print(recs[0].pattern, recs[0].confidence)
    """

    def __init__(self, storage_path: str | None = None):
        """Initialize pattern learner.

        Args:
            storage_path: Path for persistence (default: patterns/learning_memory.json)
        """
        self.store = LearningStore(storage_path)
        self.recommender = PatternRecommender(self.store)

    def record(
        self,
        pattern: str,
        success: bool,
        duration: float,
        cost: float = 0.0,
        confidence: float = 0.0,
        context: dict[str, Any] | None = None,
    ) -> None:
        """Record a pattern execution.

        Args:
            pattern: Pattern/strategy name
            success: Whether execution succeeded
            duration: Execution duration in seconds
            cost: Estimated cost
            confidence: Aggregate confidence score
            context: Execution context (for similarity matching)
        """
        record = ExecutionRecord(
            pattern=pattern,
            success=success,
            duration_seconds=duration,
            cost=cost,
            confidence=confidence,
            context_features=context or {},
        )
        self.store.add_record(record)
        logger.debug(f"Recorded {pattern} execution: success={success}")

    def recommend(
        self, context: dict[str, Any], top_k: int = 3
    ) -> list[PatternRecommendation]:
        """Get pattern recommendations for a context.

        Args:
            context: Execution context
            top_k: Number of recommendations

        Returns:
            List of PatternRecommendation
        """
        return self.recommender.recommend(context, top_k)

    def get_stats(self, pattern: str) -> PatternStats | None:
        """Get statistics for a specific pattern.

        Args:
            pattern: Pattern name

        Returns:
            PatternStats or None
        """
        return self.store.get_stats(pattern)

    def get_all_stats(self) -> list[PatternStats]:
        """Get statistics for all patterns.

        Returns:
            List of PatternStats sorted by success rate
        """
        return self.store.get_all_stats()

    def save(self) -> None:
        """Force save to disk."""
        self.store.save()

    def report(self) -> str:
        """Generate a human-readable report of learning data.

        Returns:
            Formatted report string
        """
        stats = self.get_all_stats()
        if not stats:
            return "No learning data recorded yet."

        lines = ["Pattern Learning Report", "=" * 50, ""]

        for s in stats:
            lines.append(f"Pattern: {s.pattern}")
            lines.append(f"  Executions: {s.total_executions}")
            lines.append(f"  Success Rate: {s.success_rate:.1%}")
            lines.append(f"  Avg Duration: {s.avg_duration:.2f}s")
            lines.append(f"  Avg Cost: ${s.avg_cost:.4f}")
            lines.append("")

        return "\n".join(lines)


# Module-level singleton for convenience
_default_learner: PatternLearner | None = None


def get_learner() -> PatternLearner:
    """Get the default pattern learner instance.

    Returns:
        PatternLearner singleton
    """
    global _default_learner
    if _default_learner is None:
        _default_learner = PatternLearner()
    return _default_learner
