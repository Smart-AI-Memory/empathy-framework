"""A/B Testing for Workflow Optimization

Enables controlled experiments to compare different workflow configurations
and determine which performs better for specific goals or domains.

Key Features:
- Experiment definition with control and variant groups
- Statistical significance testing
- Automatic traffic allocation
- Multi-armed bandit for adaptive optimization
- Integration with feedback loop

Copyright 2026 Smart-AI-Memory
Licensed under Fair Source License 0.9
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import random
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)


# =============================================================================
# DATA STRUCTURES
# =============================================================================


class ExperimentStatus(Enum):
    """Status of an A/B experiment."""

    DRAFT = "draft"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    STOPPED = "stopped"


class AllocationStrategy(Enum):
    """Strategy for allocating traffic to variants."""

    FIXED = "fixed"  # Fixed percentage split
    EPSILON_GREEDY = "epsilon_greedy"  # Explore vs exploit
    THOMPSON_SAMPLING = "thompson_sampling"  # Bayesian bandits
    UCB = "ucb"  # Upper confidence bound


@dataclass
class Variant:
    """A variant in an A/B experiment."""

    variant_id: str
    name: str
    description: str
    config: dict[str, Any]
    is_control: bool = False
    traffic_percentage: float = 50.0

    # Statistics
    impressions: int = 0
    conversions: int = 0
    total_success_score: float = 0.0

    @property
    def conversion_rate(self) -> float:
        """Calculate conversion rate."""
        if self.impressions == 0:
            return 0.0
        return self.conversions / self.impressions

    @property
    def avg_success_score(self) -> float:
        """Calculate average success score."""
        if self.impressions == 0:
            return 0.0
        return self.total_success_score / self.impressions

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "variant_id": self.variant_id,
            "name": self.name,
            "description": self.description,
            "config": self.config,
            "is_control": self.is_control,
            "traffic_percentage": self.traffic_percentage,
            "impressions": self.impressions,
            "conversions": self.conversions,
            "total_success_score": self.total_success_score,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Variant:
        """Create from dictionary."""
        return cls(
            variant_id=data["variant_id"],
            name=data["name"],
            description=data["description"],
            config=data["config"],
            is_control=data.get("is_control", False),
            traffic_percentage=data.get("traffic_percentage", 50.0),
            impressions=data.get("impressions", 0),
            conversions=data.get("conversions", 0),
            total_success_score=data.get("total_success_score", 0.0),
        )


@dataclass
class Experiment:
    """An A/B experiment definition."""

    experiment_id: str
    name: str
    description: str
    hypothesis: str
    variants: list[Variant]
    domain_filter: str | None = None
    goal_filter: str | None = None
    allocation_strategy: AllocationStrategy = AllocationStrategy.FIXED
    min_sample_size: int = 100
    max_duration_days: int = 30
    confidence_level: float = 0.95
    status: ExperimentStatus = ExperimentStatus.DRAFT
    created_at: datetime = field(default_factory=datetime.now)
    started_at: datetime | None = None
    ended_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "experiment_id": self.experiment_id,
            "name": self.name,
            "description": self.description,
            "hypothesis": self.hypothesis,
            "variants": [v.to_dict() for v in self.variants],
            "domain_filter": self.domain_filter,
            "goal_filter": self.goal_filter,
            "allocation_strategy": self.allocation_strategy.value,
            "min_sample_size": self.min_sample_size,
            "max_duration_days": self.max_duration_days,
            "confidence_level": self.confidence_level,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Experiment:
        """Create from dictionary."""
        return cls(
            experiment_id=data["experiment_id"],
            name=data["name"],
            description=data["description"],
            hypothesis=data["hypothesis"],
            variants=[Variant.from_dict(v) for v in data["variants"]],
            domain_filter=data.get("domain_filter"),
            goal_filter=data.get("goal_filter"),
            allocation_strategy=AllocationStrategy(
                data.get("allocation_strategy", "fixed")
            ),
            min_sample_size=data.get("min_sample_size", 100),
            max_duration_days=data.get("max_duration_days", 30),
            confidence_level=data.get("confidence_level", 0.95),
            status=ExperimentStatus(data.get("status", "draft")),
            created_at=datetime.fromisoformat(data["created_at"]),
            started_at=(
                datetime.fromisoformat(data["started_at"])
                if data.get("started_at")
                else None
            ),
            ended_at=(
                datetime.fromisoformat(data["ended_at"])
                if data.get("ended_at")
                else None
            ),
        )

    @property
    def total_impressions(self) -> int:
        """Total impressions across all variants."""
        return sum(v.impressions for v in self.variants)

    @property
    def control(self) -> Variant | None:
        """Get control variant."""
        for v in self.variants:
            if v.is_control:
                return v
        return None

    @property
    def treatments(self) -> list[Variant]:
        """Get treatment variants (non-control)."""
        return [v for v in self.variants if not v.is_control]


@dataclass
class ExperimentResult:
    """Results and analysis of an experiment."""

    experiment: Experiment
    winner: Variant | None
    is_significant: bool
    p_value: float
    confidence_interval: tuple[float, float]
    lift: float  # Percentage improvement over control
    recommendation: str


# =============================================================================
# STATISTICAL ANALYSIS
# =============================================================================


class StatisticalAnalyzer:
    """Statistical analysis for A/B tests."""

    @staticmethod
    def z_test_proportions(
        n1: int,
        c1: int,
        n2: int,
        c2: int,
    ) -> tuple[float, float]:
        """Two-proportion z-test.

        Args:
            n1: Sample size for group 1
            c1: Conversions for group 1
            n2: Sample size for group 2
            c2: Conversions for group 2

        Returns:
            (z_score, p_value)
        """
        if n1 == 0 or n2 == 0:
            return 0.0, 1.0

        p1 = c1 / n1
        p2 = c2 / n2
        p_pooled = (c1 + c2) / (n1 + n2)

        if p_pooled == 0 or p_pooled == 1:
            return 0.0, 1.0

        se = math.sqrt(p_pooled * (1 - p_pooled) * (1 / n1 + 1 / n2))
        if se == 0:
            return 0.0, 1.0

        z = (p1 - p2) / se

        # Approximate p-value using normal CDF
        p_value = 2 * (1 - StatisticalAnalyzer._normal_cdf(abs(z)))

        return z, p_value

    @staticmethod
    def t_test_means(
        n1: int,
        mean1: float,
        var1: float,
        n2: int,
        mean2: float,
        var2: float,
    ) -> tuple[float, float]:
        """Welch's t-test for means.

        Args:
            n1, mean1, var1: Stats for group 1
            n2, mean2, var2: Stats for group 2

        Returns:
            (t_score, p_value)
        """
        if n1 < 2 or n2 < 2:
            return 0.0, 1.0

        se = math.sqrt(var1 / n1 + var2 / n2)
        if se == 0:
            return 0.0, 1.0

        t = (mean1 - mean2) / se

        # Welch-Satterthwaite degrees of freedom
        num = (var1 / n1 + var2 / n2) ** 2
        denom = (var1 / n1) ** 2 / (n1 - 1) + (var2 / n2) ** 2 / (n2 - 1)
        df = num / denom if denom > 0 else 1

        # Approximate p-value using t-distribution
        p_value = 2 * StatisticalAnalyzer._t_cdf(-abs(t), df)

        return t, p_value

    @staticmethod
    def confidence_interval(
        n: int,
        successes: int,
        confidence: float = 0.95,
    ) -> tuple[float, float]:
        """Wilson score interval for proportions.

        Args:
            n: Sample size
            successes: Number of successes
            confidence: Confidence level

        Returns:
            (lower, upper) bounds
        """
        if n == 0:
            return 0.0, 1.0

        z = StatisticalAnalyzer._z_score(confidence)
        p = successes / n

        denominator = 1 + z * z / n
        centre = p + z * z / (2 * n)
        adjustment = z * math.sqrt((p * (1 - p) + z * z / (4 * n)) / n)

        lower = max(0, (centre - adjustment) / denominator)
        upper = min(1, (centre + adjustment) / denominator)

        return lower, upper

    @staticmethod
    def _normal_cdf(x: float) -> float:
        """Approximate standard normal CDF."""
        return 0.5 * (1 + math.erf(x / math.sqrt(2)))

    @staticmethod
    def _t_cdf(t: float, df: float) -> float:
        """Approximate t-distribution CDF."""
        # Use normal approximation for large df
        if df > 30:
            return StatisticalAnalyzer._normal_cdf(t)

        # Beta function approximation
        x = df / (df + t * t)
        return 0.5 * StatisticalAnalyzer._incomplete_beta(df / 2, 0.5, x)

    @staticmethod
    def _incomplete_beta(a: float, b: float, x: float) -> float:
        """Approximate incomplete beta function."""
        if x == 0:
            return 0
        if x == 1:
            return 1

        # Continued fraction approximation (simplified)
        result = 0.0
        for k in range(100):
            term = (x ** k) * math.gamma(a + k) / (math.gamma(k + 1) * math.gamma(a))
            result += term * ((1 - x) ** b) / (a + k)
            if abs(term) < 1e-10:
                break

        return result * math.gamma(a + b) / (math.gamma(a) * math.gamma(b))

    @staticmethod
    def _z_score(confidence: float) -> float:
        """Get z-score for confidence level."""
        # Common values
        z_scores = {
            0.90: 1.645,
            0.95: 1.96,
            0.99: 2.576,
        }
        return z_scores.get(confidence, 1.96)


# =============================================================================
# TRAFFIC ALLOCATOR
# =============================================================================


class TrafficAllocator:
    """Allocates traffic to experiment variants."""

    def __init__(self, experiment: Experiment):
        """Initialize allocator.

        Args:
            experiment: The experiment to allocate for
        """
        self.experiment = experiment
        self._random = random.Random()

    def allocate(self, user_id: str) -> Variant:
        """Allocate a user to a variant.

        Args:
            user_id: Unique user/session identifier

        Returns:
            Allocated variant
        """
        strategy = self.experiment.allocation_strategy

        if strategy == AllocationStrategy.FIXED:
            return self._fixed_allocation(user_id)
        elif strategy == AllocationStrategy.EPSILON_GREEDY:
            return self._epsilon_greedy(epsilon=0.1)
        elif strategy == AllocationStrategy.THOMPSON_SAMPLING:
            return self._thompson_sampling()
        elif strategy == AllocationStrategy.UCB:
            return self._ucb_allocation()
        else:
            return self._fixed_allocation(user_id)

    def _fixed_allocation(self, user_id: str) -> Variant:
        """Deterministic allocation based on user ID hash."""
        # Hash user ID for consistent assignment
        hash_val = int(hashlib.md5(
            f"{self.experiment.experiment_id}:{user_id}".encode()
        ).hexdigest(), 16)
        bucket = hash_val % 100

        cumulative = 0.0
        for variant in self.experiment.variants:
            cumulative += variant.traffic_percentage
            if bucket < cumulative:
                return variant

        return self.experiment.variants[-1]

    def _epsilon_greedy(self, epsilon: float = 0.1) -> Variant:
        """Epsilon-greedy: explore with probability epsilon."""
        if self._random.random() < epsilon:
            # Explore: random variant
            return self._random.choice(self.experiment.variants)
        else:
            # Exploit: best performing variant
            return max(
                self.experiment.variants,
                key=lambda v: v.avg_success_score,
            )

    def _thompson_sampling(self) -> Variant:
        """Thompson sampling: Bayesian multi-armed bandit."""
        samples = []

        for variant in self.experiment.variants:
            # Beta distribution parameters
            alpha = variant.conversions + 1
            beta = (variant.impressions - variant.conversions) + 1

            # Sample from beta distribution
            sample = self._random.betavariate(alpha, beta)
            samples.append((sample, variant))

        # Select variant with highest sample
        return max(samples, key=lambda x: x[0])[1]

    def _ucb_allocation(self) -> Variant:
        """Upper Confidence Bound selection."""
        total_impressions = self.experiment.total_impressions or 1

        ucb_scores = []
        for variant in self.experiment.variants:
            if variant.impressions == 0:
                # Give unvisited variants high priority
                ucb_scores.append((float('inf'), variant))
            else:
                mean = variant.avg_success_score
                exploration = math.sqrt(
                    2 * math.log(total_impressions) / variant.impressions
                )
                ucb = mean + exploration
                ucb_scores.append((ucb, variant))

        return max(ucb_scores, key=lambda x: x[0])[1]


# =============================================================================
# EXPERIMENT MANAGER
# =============================================================================


class ExperimentManager:
    """Manages A/B experiments lifecycle."""

    def __init__(self, storage_path: Path | str | None = None):
        """Initialize experiment manager.

        Args:
            storage_path: Path to persist experiments
        """
        if storage_path is None:
            storage_path = Path.home() / ".empathy" / "socratic" / "experiments.json"
        self.storage_path = Path(storage_path)
        self._experiments: dict[str, Experiment] = {}
        self._allocators: dict[str, TrafficAllocator] = {}

        # Load existing experiments
        self._load()

    def create_experiment(
        self,
        name: str,
        description: str,
        hypothesis: str,
        control_config: dict[str, Any],
        treatment_configs: list[dict[str, Any]],
        domain_filter: str | None = None,
        allocation_strategy: AllocationStrategy = AllocationStrategy.FIXED,
        min_sample_size: int = 100,
    ) -> Experiment:
        """Create a new experiment.

        Args:
            name: Experiment name
            description: Description
            hypothesis: What we're testing
            control_config: Configuration for control group
            treatment_configs: Configurations for treatment groups
            domain_filter: Optional domain to filter
            allocation_strategy: How to allocate traffic
            min_sample_size: Minimum samples before analysis

        Returns:
            Created experiment
        """
        experiment_id = hashlib.sha256(
            f"{name}:{time.time()}".encode()
        ).hexdigest()[:12]

        # Create variants
        num_variants = 1 + len(treatment_configs)
        traffic_each = 100.0 / num_variants

        variants = [
            Variant(
                variant_id=f"{experiment_id}_control",
                name="Control",
                description="Control group with existing configuration",
                config=control_config,
                is_control=True,
                traffic_percentage=traffic_each,
            )
        ]

        for i, config in enumerate(treatment_configs):
            variants.append(Variant(
                variant_id=f"{experiment_id}_treatment_{i}",
                name=config.get("name", f"Treatment {i + 1}"),
                description=config.get("description", ""),
                config=config.get("config", config),
                is_control=False,
                traffic_percentage=traffic_each,
            ))

        experiment = Experiment(
            experiment_id=experiment_id,
            name=name,
            description=description,
            hypothesis=hypothesis,
            variants=variants,
            domain_filter=domain_filter,
            allocation_strategy=allocation_strategy,
            min_sample_size=min_sample_size,
        )

        self._experiments[experiment_id] = experiment
        self._save()

        return experiment

    def start_experiment(self, experiment_id: str) -> bool:
        """Start an experiment.

        Args:
            experiment_id: ID of experiment to start

        Returns:
            True if started successfully
        """
        experiment = self._experiments.get(experiment_id)
        if not experiment:
            return False

        if experiment.status != ExperimentStatus.DRAFT:
            return False

        experiment.status = ExperimentStatus.RUNNING
        experiment.started_at = datetime.now()
        self._allocators[experiment_id] = TrafficAllocator(experiment)
        self._save()

        return True

    def stop_experiment(self, experiment_id: str) -> ExperimentResult | None:
        """Stop an experiment and analyze results.

        Args:
            experiment_id: ID of experiment to stop

        Returns:
            Experiment results with analysis
        """
        experiment = self._experiments.get(experiment_id)
        if not experiment:
            return None

        experiment.status = ExperimentStatus.COMPLETED
        experiment.ended_at = datetime.now()
        self._save()

        return self.analyze_experiment(experiment_id)

    def allocate_variant(
        self,
        experiment_id: str,
        user_id: str,
    ) -> Variant | None:
        """Allocate a user to a variant.

        Args:
            experiment_id: Experiment ID
            user_id: User/session ID

        Returns:
            Allocated variant or None
        """
        experiment = self._experiments.get(experiment_id)
        if not experiment or experiment.status != ExperimentStatus.RUNNING:
            return None

        allocator = self._allocators.get(experiment_id)
        if not allocator:
            allocator = TrafficAllocator(experiment)
            self._allocators[experiment_id] = allocator

        return allocator.allocate(user_id)

    def record_impression(self, experiment_id: str, variant_id: str):
        """Record an impression for a variant.

        Args:
            experiment_id: Experiment ID
            variant_id: Variant ID
        """
        experiment = self._experiments.get(experiment_id)
        if not experiment:
            return

        for variant in experiment.variants:
            if variant.variant_id == variant_id:
                variant.impressions += 1
                break

        self._save()

    def record_conversion(
        self,
        experiment_id: str,
        variant_id: str,
        success_score: float = 1.0,
    ):
        """Record a conversion for a variant.

        Args:
            experiment_id: Experiment ID
            variant_id: Variant ID
            success_score: Score from 0-1
        """
        experiment = self._experiments.get(experiment_id)
        if not experiment:
            return

        for variant in experiment.variants:
            if variant.variant_id == variant_id:
                variant.conversions += 1
                variant.total_success_score += success_score
                break

        self._save()

    def analyze_experiment(self, experiment_id: str) -> ExperimentResult | None:
        """Analyze experiment results.

        Args:
            experiment_id: Experiment ID

        Returns:
            Analysis results
        """
        experiment = self._experiments.get(experiment_id)
        if not experiment:
            return None

        control = experiment.control
        if not control:
            return None

        treatments = experiment.treatments
        if not treatments:
            return None

        # Find best treatment
        best_treatment = max(treatments, key=lambda v: v.conversion_rate)

        # Statistical test
        z_score, p_value = StatisticalAnalyzer.z_test_proportions(
            control.impressions,
            control.conversions,
            best_treatment.impressions,
            best_treatment.conversions,
        )

        is_significant = p_value < (1 - experiment.confidence_level)

        # Calculate lift
        if control.conversion_rate > 0:
            lift = (
                (best_treatment.conversion_rate - control.conversion_rate)
                / control.conversion_rate
            ) * 100
        else:
            lift = 0.0

        # Confidence interval for treatment
        ci = StatisticalAnalyzer.confidence_interval(
            best_treatment.impressions,
            best_treatment.conversions,
            experiment.confidence_level,
        )

        # Determine winner
        winner = None
        recommendation = ""

        if is_significant:
            if best_treatment.conversion_rate > control.conversion_rate:
                winner = best_treatment
                recommendation = (
                    f"Adopt {best_treatment.name}. It shows {lift:.1f}% improvement "
                    f"over control with p-value {p_value:.4f}."
                )
            else:
                winner = control
                recommendation = (
                    "Keep control. Treatment did not show improvement."
                )
        else:
            recommendation = (
                f"No significant difference detected (p={p_value:.4f}). "
                f"Consider running longer or increasing sample size."
            )

        return ExperimentResult(
            experiment=experiment,
            winner=winner,
            is_significant=is_significant,
            p_value=p_value,
            confidence_interval=ci,
            lift=lift,
            recommendation=recommendation,
        )

    def get_running_experiments(
        self,
        domain: str | None = None,
    ) -> list[Experiment]:
        """Get all running experiments.

        Args:
            domain: Optional domain filter

        Returns:
            List of running experiments
        """
        running = []
        for exp in self._experiments.values():
            if exp.status != ExperimentStatus.RUNNING:
                continue
            if domain and exp.domain_filter and exp.domain_filter != domain:
                continue
            running.append(exp)
        return running

    def get_experiment(self, experiment_id: str) -> Experiment | None:
        """Get experiment by ID."""
        return self._experiments.get(experiment_id)

    def list_experiments(self) -> list[Experiment]:
        """List all experiments."""
        return list(self._experiments.values())

    def _save(self):
        """Save experiments to storage."""
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "version": 1,
            "experiments": [e.to_dict() for e in self._experiments.values()],
        }

        with self.storage_path.open("w") as f:
            json.dump(data, f, indent=2)

    def _load(self):
        """Load experiments from storage."""
        if not self.storage_path.exists():
            return

        try:
            with self.storage_path.open("r") as f:
                data = json.load(f)

            for exp_data in data.get("experiments", []):
                exp = Experiment.from_dict(exp_data)
                self._experiments[exp.experiment_id] = exp

                # Restore allocators for running experiments
                if exp.status == ExperimentStatus.RUNNING:
                    self._allocators[exp.experiment_id] = TrafficAllocator(exp)

        except Exception as e:
            logger.warning(f"Failed to load experiments: {e}")


# =============================================================================
# WORKFLOW A/B TESTING INTEGRATION
# =============================================================================


class WorkflowABTester:
    """High-level API for A/B testing workflow configurations.

    Integrates with the Socratic workflow builder to test different
    configurations and optimize over time.
    """

    def __init__(self, storage_path: Path | str | None = None):
        """Initialize the tester.

        Args:
            storage_path: Path to persist data
        """
        self.manager = ExperimentManager(storage_path)

    def create_workflow_experiment(
        self,
        name: str,
        hypothesis: str,
        control_agents: list[str],
        treatment_agents_list: list[list[str]],
        domain: str | None = None,
    ) -> str:
        """Create an experiment comparing workflow agent configurations.

        Args:
            name: Experiment name
            hypothesis: What we're testing
            control_agents: Agent list for control
            treatment_agents_list: Agent lists for treatments
            domain: Domain filter

        Returns:
            Experiment ID
        """
        control_config = {"agents": control_agents}
        treatment_configs = [
            {
                "name": f"Treatment {i + 1}",
                "config": {"agents": agents},
            }
            for i, agents in enumerate(treatment_agents_list)
        ]

        experiment = self.manager.create_experiment(
            name=name,
            description=f"Testing different agent configurations for {domain or 'general'} workflows",
            hypothesis=hypothesis,
            control_config=control_config,
            treatment_configs=treatment_configs,
            domain_filter=domain,
            allocation_strategy=AllocationStrategy.THOMPSON_SAMPLING,
        )

        return experiment.experiment_id

    def get_workflow_config(
        self,
        session_id: str,
        domain: str | None = None,
    ) -> tuple[dict[str, Any], str | None, str | None]:
        """Get workflow configuration for a session.

        Returns control config or allocates to an experiment.

        Args:
            session_id: Session ID for allocation
            domain: Optional domain filter

        Returns:
            (config, experiment_id, variant_id) or (default_config, None, None)
        """
        # Check for running experiments
        experiments = self.manager.get_running_experiments(domain)

        for exp in experiments:
            variant = self.manager.allocate_variant(exp.experiment_id, session_id)
            if variant:
                self.manager.record_impression(exp.experiment_id, variant.variant_id)
                return (variant.config, exp.experiment_id, variant.variant_id)

        # No experiment, return default
        return ({}, None, None)

    def record_workflow_result(
        self,
        experiment_id: str,
        variant_id: str,
        success: bool,
        success_score: float = 0.0,
    ):
        """Record the result of a workflow execution.

        Args:
            experiment_id: Experiment ID
            variant_id: Variant ID
            success: Whether workflow succeeded
            success_score: Success score (0-1)
        """
        if success:
            self.manager.record_conversion(
                experiment_id,
                variant_id,
                success_score,
            )

    def get_best_config(self, domain: str | None = None) -> dict[str, Any]:
        """Get the best known configuration for a domain.

        Args:
            domain: Domain filter

        Returns:
            Best configuration based on completed experiments
        """
        best_config: dict[str, Any] = {}
        best_score = 0.0

        for exp in self.manager.list_experiments():
            if exp.status != ExperimentStatus.COMPLETED:
                continue
            if domain and exp.domain_filter != domain:
                continue

            result = self.manager.analyze_experiment(exp.experiment_id)
            if result and result.winner:
                if result.winner.avg_success_score > best_score:
                    best_score = result.winner.avg_success_score
                    best_config = result.winner.config

        return best_config
