"""Feedback Loop for Continuous Improvement

Analyzes success metrics from workflow executions to improve
future agent generation. This creates a learning system that:

1. Tracks which agent configurations succeed
2. Identifies patterns in successful workflows
3. Adjusts agent recommendations based on historical data
4. Provides insights for manual tuning

Copyright 2026 Smart-AI-Memory
Licensed under Fair Source License 0.9
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from .blueprint import AgentBlueprint, WorkflowBlueprint
from .success import SuccessEvaluation

logger = logging.getLogger(__name__)


# =============================================================================
# FEEDBACK DATA STRUCTURES
# =============================================================================


@dataclass
class AgentPerformance:
    """Performance statistics for an agent template."""

    template_id: str
    total_uses: int = 0
    successful_uses: int = 0
    average_score: float = 0.0
    scores: list[float] = field(default_factory=list)

    # Context-specific performance
    by_domain: dict[str, dict[str, float]] = field(default_factory=dict)
    by_language: dict[str, dict[str, float]] = field(default_factory=dict)
    by_quality_focus: dict[str, dict[str, float]] = field(default_factory=dict)

    # Trend data
    recent_scores: list[tuple[str, float]] = field(default_factory=list)  # (timestamp, score)

    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        if self.total_uses == 0:
            return 0.0
        return self.successful_uses / self.total_uses

    @property
    def trend(self) -> str:
        """Determine performance trend."""
        if len(self.recent_scores) < 5:
            return "insufficient_data"

        recent_5 = [s for _, s in self.recent_scores[-5:]]
        older_5 = [s for _, s in self.recent_scores[-10:-5]] if len(self.recent_scores) >= 10 else []

        if not older_5:
            return "stable"

        recent_avg = sum(recent_5) / len(recent_5)
        older_avg = sum(older_5) / len(older_5)

        if recent_avg > older_avg * 1.1:
            return "improving"
        elif recent_avg < older_avg * 0.9:
            return "declining"
        else:
            return "stable"

    def record_use(
        self,
        success: bool,
        score: float,
        domain: str | None = None,
        languages: list[str] | None = None,
        quality_focus: list[str] | None = None,
    ) -> None:
        """Record a use of this agent."""
        self.total_uses += 1
        if success:
            self.successful_uses += 1

        self.scores.append(score)
        self.average_score = sum(self.scores) / len(self.scores)

        # Record with timestamp for trend analysis
        self.recent_scores.append((datetime.now().isoformat(), score))
        # Keep last 100 scores
        if len(self.recent_scores) > 100:
            self.recent_scores = self.recent_scores[-100:]

        # Record by context
        if domain:
            if domain not in self.by_domain:
                self.by_domain[domain] = {"uses": 0, "successes": 0, "total_score": 0}
            self.by_domain[domain]["uses"] += 1
            self.by_domain[domain]["successes"] += 1 if success else 0
            self.by_domain[domain]["total_score"] += score

        if languages:
            for lang in languages:
                if lang not in self.by_language:
                    self.by_language[lang] = {"uses": 0, "successes": 0, "total_score": 0}
                self.by_language[lang]["uses"] += 1
                self.by_language[lang]["successes"] += 1 if success else 0
                self.by_language[lang]["total_score"] += score

        if quality_focus:
            for qf in quality_focus:
                if qf not in self.by_quality_focus:
                    self.by_quality_focus[qf] = {"uses": 0, "successes": 0, "total_score": 0}
                self.by_quality_focus[qf]["uses"] += 1
                self.by_quality_focus[qf]["successes"] += 1 if success else 0
                self.by_quality_focus[qf]["total_score"] += score

    def get_score_for_context(
        self,
        domain: str | None = None,
        languages: list[str] | None = None,
        quality_focus: list[str] | None = None,
    ) -> float:
        """Get a weighted score for a specific context."""
        scores = []
        weights = []

        # Base score
        if self.total_uses > 0:
            scores.append(self.average_score)
            weights.append(1.0)

        # Domain-specific score
        if domain and domain in self.by_domain:
            d = self.by_domain[domain]
            if d["uses"] > 0:
                scores.append(d["total_score"] / d["uses"])
                weights.append(2.0)  # Higher weight for domain match

        # Language-specific score
        if languages:
            for lang in languages:
                if lang in self.by_language:
                    lang_stats = self.by_language[lang]
                    if lang_stats["uses"] > 0:
                        scores.append(lang_stats["total_score"] / lang_stats["uses"])
                        weights.append(1.5)

        # Quality focus score
        if quality_focus:
            for qf in quality_focus:
                if qf in self.by_quality_focus:
                    q = self.by_quality_focus[qf]
                    if q["uses"] > 0:
                        scores.append(q["total_score"] / q["uses"])
                        weights.append(1.5)

        if not scores:
            return 0.5  # Default neutral score

        # Weighted average
        return sum(s * w for s, w in zip(scores, weights, strict=False)) / sum(weights)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "template_id": self.template_id,
            "total_uses": self.total_uses,
            "successful_uses": self.successful_uses,
            "average_score": self.average_score,
            "success_rate": self.success_rate,
            "trend": self.trend,
            "by_domain": self.by_domain,
            "by_language": self.by_language,
            "by_quality_focus": self.by_quality_focus,
            "recent_scores": self.recent_scores[-20:],  # Last 20 for display
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentPerformance:
        """Deserialize from dictionary."""
        perf = cls(template_id=data.get("template_id", ""))
        perf.total_uses = data.get("total_uses", 0)
        perf.successful_uses = data.get("successful_uses", 0)
        perf.average_score = data.get("average_score", 0.0)
        perf.by_domain = data.get("by_domain", {})
        perf.by_language = data.get("by_language", {})
        perf.by_quality_focus = data.get("by_quality_focus", {})
        perf.recent_scores = data.get("recent_scores", [])
        return perf


@dataclass
class WorkflowPattern:
    """Pattern of successful workflow configurations."""

    pattern_id: str
    domain: str
    agent_combination: list[str]  # List of template IDs
    stage_configuration: list[dict[str, Any]]
    uses: int = 0
    successes: int = 0
    average_score: float = 0.0

    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        if self.uses == 0:
            return 0.0
        return self.successes / self.uses

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "pattern_id": self.pattern_id,
            "domain": self.domain,
            "agent_combination": self.agent_combination,
            "stage_configuration": self.stage_configuration,
            "uses": self.uses,
            "successes": self.successes,
            "average_score": self.average_score,
            "success_rate": self.success_rate,
        }


# =============================================================================
# FEEDBACK COLLECTOR
# =============================================================================


class FeedbackCollector:
    """Collects and stores feedback from workflow executions.

    Example:
        >>> collector = FeedbackCollector()
        >>> collector.record_execution(blueprint, evaluation)
        >>> performance = collector.get_agent_performance("security_reviewer")
    """

    def __init__(self, storage_path: str = ".empathy/socratic/feedback"):
        """Initialize the collector.

        Args:
            storage_path: Path for feedback data storage
        """
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)

        self._agent_performance: dict[str, AgentPerformance] = {}
        self._workflow_patterns: dict[str, WorkflowPattern] = {}

        self._load_data()

    def _load_data(self) -> None:
        """Load existing feedback data."""
        # Load agent performance
        perf_file = self.storage_path / "agent_performance.json"
        if perf_file.exists():
            try:
                with perf_file.open() as f:
                    data = json.load(f)
                for template_id, perf_data in data.items():
                    self._agent_performance[template_id] = AgentPerformance.from_dict(perf_data)
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(f"Failed to load agent performance: {e}")

        # Load workflow patterns
        patterns_file = self.storage_path / "workflow_patterns.json"
        if patterns_file.exists():
            try:
                with patterns_file.open() as f:
                    data = json.load(f)
                for pattern_id, pattern_data in data.items():
                    self._workflow_patterns[pattern_id] = WorkflowPattern(**pattern_data)
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(f"Failed to load workflow patterns: {e}")

    def _save_data(self) -> None:
        """Save feedback data to disk."""
        # Save agent performance
        perf_file = self.storage_path / "agent_performance.json"
        perf_data = {k: v.to_dict() for k, v in self._agent_performance.items()}
        with perf_file.open("w") as f:
            json.dump(perf_data, f, indent=2)

        # Save workflow patterns
        patterns_file = self.storage_path / "workflow_patterns.json"
        patterns_data = {k: v.to_dict() for k, v in self._workflow_patterns.items()}
        with patterns_file.open("w") as f:
            json.dump(patterns_data, f, indent=2)

    def record_execution(
        self,
        blueprint: WorkflowBlueprint,
        evaluation: SuccessEvaluation,
    ) -> None:
        """Record feedback from a workflow execution.

        Args:
            blueprint: The executed workflow blueprint
            evaluation: The success evaluation results
        """
        success = evaluation.overall_success
        score = evaluation.overall_score

        # Record for each agent
        for agent in blueprint.agents:
            template_id = agent.template_id or agent.spec.id

            if template_id not in self._agent_performance:
                self._agent_performance[template_id] = AgentPerformance(template_id=template_id)

            self._agent_performance[template_id].record_use(
                success=success,
                score=score,
                domain=blueprint.domain,
                languages=blueprint.supported_languages,
                quality_focus=blueprint.quality_focus,
            )

        # Record workflow pattern
        pattern_id = self._generate_pattern_id(blueprint)
        if pattern_id not in self._workflow_patterns:
            self._workflow_patterns[pattern_id] = WorkflowPattern(
                pattern_id=pattern_id,
                domain=blueprint.domain,
                agent_combination=[a.template_id or a.spec.id for a in blueprint.agents],
                stage_configuration=[s.to_dict() for s in blueprint.stages],
            )

        pattern = self._workflow_patterns[pattern_id]
        pattern.uses += 1
        if success:
            pattern.successes += 1
        # Rolling average
        pattern.average_score = (
            (pattern.average_score * (pattern.uses - 1) + score) / pattern.uses
        )

        self._save_data()
        logger.info(f"Recorded feedback for blueprint {blueprint.id[:8]}: success={success}, score={score:.2f}")

    def _generate_pattern_id(self, blueprint: WorkflowBlueprint) -> str:
        """Generate a unique ID for a workflow pattern."""
        agents = sorted(a.template_id or a.spec.id for a in blueprint.agents)
        return f"{blueprint.domain}:{':'.join(agents)}"

    def get_agent_performance(self, template_id: str) -> AgentPerformance | None:
        """Get performance data for an agent template."""
        return self._agent_performance.get(template_id)

    def get_all_performance(self) -> dict[str, AgentPerformance]:
        """Get all agent performance data."""
        return self._agent_performance.copy()

    def get_best_agents_for_context(
        self,
        domain: str,
        languages: list[str] | None = None,
        quality_focus: list[str] | None = None,
        limit: int = 5,
    ) -> list[tuple[str, float]]:
        """Get the best performing agents for a context.

        Args:
            domain: Target domain
            languages: Target languages
            quality_focus: Quality attributes
            limit: Maximum number of results

        Returns:
            List of (template_id, score) tuples sorted by score
        """
        scored_agents = []

        for template_id, perf in self._agent_performance.items():
            score = perf.get_score_for_context(domain, languages, quality_focus)
            # Apply confidence penalty for low sample sizes
            confidence = min(perf.total_uses / 10, 1.0)  # Full confidence at 10+ uses
            adjusted_score = score * confidence + 0.5 * (1 - confidence)  # Blend with neutral
            scored_agents.append((template_id, adjusted_score))

        # Sort by score descending
        scored_agents.sort(key=lambda x: x[1], reverse=True)

        return scored_agents[:limit]

    def get_successful_patterns(
        self,
        domain: str | None = None,
        min_success_rate: float = 0.7,
        min_uses: int = 3,
    ) -> list[WorkflowPattern]:
        """Get successful workflow patterns.

        Args:
            domain: Filter by domain
            min_success_rate: Minimum success rate threshold
            min_uses: Minimum number of uses to be considered

        Returns:
            List of successful patterns
        """
        patterns = []

        for pattern in self._workflow_patterns.values():
            if domain and pattern.domain != domain:
                continue
            if pattern.uses < min_uses:
                continue
            if pattern.success_rate < min_success_rate:
                continue
            patterns.append(pattern)

        # Sort by success rate then by uses
        patterns.sort(key=lambda p: (p.success_rate, p.uses), reverse=True)

        return patterns

    def get_insights(self) -> dict[str, Any]:
        """Get aggregated insights from feedback data.

        Returns:
            Dictionary with various insights
        """
        insights: dict[str, Any] = {
            "total_agents_tracked": len(self._agent_performance),
            "total_patterns_tracked": len(self._workflow_patterns),
            "top_performing_agents": [],
            "declining_agents": [],
            "domain_insights": {},
            "recommendations": [],
        }

        # Top performing agents
        all_agents = [
            (tid, perf) for tid, perf in self._agent_performance.items()
            if perf.total_uses >= 5
        ]
        all_agents.sort(key=lambda x: x[1].average_score, reverse=True)
        insights["top_performing_agents"] = [
            {"template_id": tid, "score": perf.average_score, "uses": perf.total_uses}
            for tid, perf in all_agents[:5]
        ]

        # Declining agents
        for tid, perf in self._agent_performance.items():
            if perf.trend == "declining" and perf.total_uses >= 5:
                insights["declining_agents"].append({
                    "template_id": tid,
                    "current_score": perf.average_score,
                    "uses": perf.total_uses,
                })

        # Domain insights
        domains: dict[str, dict[str, Any]] = {}
        for perf in self._agent_performance.values():
            for domain, stats in perf.by_domain.items():
                if domain not in domains:
                    domains[domain] = {"total_uses": 0, "total_score": 0, "agents": set()}
                domains[domain]["total_uses"] += stats["uses"]
                domains[domain]["total_score"] += stats["total_score"]
                domains[domain]["agents"].add(perf.template_id)

        for domain, stats in domains.items():
            if stats["total_uses"] > 0:
                insights["domain_insights"][domain] = {
                    "average_score": stats["total_score"] / stats["total_uses"],
                    "total_uses": stats["total_uses"],
                    "agents_used": len(stats["agents"]),
                }

        # Generate recommendations
        insights["recommendations"] = self._generate_recommendations()

        return insights

    def _generate_recommendations(self) -> list[str]:
        """Generate improvement recommendations based on feedback."""
        recommendations = []

        # Check for underperforming agents
        for tid, perf in self._agent_performance.items():
            if perf.total_uses >= 10 and perf.success_rate < 0.5:
                recommendations.append(
                    f"Consider reviewing '{tid}' configuration - success rate is {perf.success_rate:.0%}"
                )

        # Check for agents that work well together
        successful_patterns = self.get_successful_patterns(min_success_rate=0.8, min_uses=5)
        for pattern in successful_patterns[:3]:
            agents = ", ".join(pattern.agent_combination)
            recommendations.append(
                f"Successful pattern for '{pattern.domain}': [{agents}] - {pattern.success_rate:.0%} success rate"
            )

        # Check for domains needing more data
        for domain, stats in self.get_insights().get("domain_insights", {}).items():
            if stats["total_uses"] < 5:
                recommendations.append(
                    f"More data needed for '{domain}' domain - only {stats['total_uses']} executions recorded"
                )

        return recommendations


# =============================================================================
# ADAPTIVE AGENT GENERATOR
# =============================================================================


class AdaptiveAgentGenerator:
    """Agent generator that uses feedback to improve recommendations.

    Wraps the standard AgentGenerator and adjusts recommendations
    based on historical performance data.

    Example:
        >>> generator = AdaptiveAgentGenerator()
        >>> agents = generator.generate_agents_for_requirements(requirements)
        >>> # Returns agents weighted by historical success
    """

    def __init__(self, feedback_collector: FeedbackCollector | None = None):
        """Initialize the adaptive generator.

        Args:
            feedback_collector: Feedback collector instance
        """
        from .generator import AgentGenerator

        self.base_generator = AgentGenerator()
        self.feedback = feedback_collector or FeedbackCollector()

    def generate_agents_for_requirements(
        self,
        requirements: dict[str, Any],
        use_feedback: bool = True,
    ) -> list[AgentBlueprint]:
        """Generate agents using feedback-informed recommendations.

        Args:
            requirements: Requirements from Socratic session
            use_feedback: Whether to use feedback data

        Returns:
            List of AgentBlueprints optimized based on feedback
        """
        # Get base recommendations
        base_agents = self.base_generator.generate_agents_for_requirements(requirements)

        if not use_feedback:
            return base_agents

        # Get context
        domain = requirements.get("domain", "general")
        languages = requirements.get("languages", [])
        quality_focus = requirements.get("quality_focus", [])

        # Get best agents for this context
        best_agents = self.feedback.get_best_agents_for_context(
            domain=domain,
            languages=languages,
            quality_focus=quality_focus,
            limit=10,
        )

        if not best_agents:
            return base_agents

        # Reorder and potentially add agents based on feedback
        agent_scores = dict(best_agents)

        # Score base agents
        scored_base = []
        for agent in base_agents:
            tid = agent.template_id or agent.spec.id
            feedback_score = agent_scores.get(tid, 0.5)
            scored_base.append((agent, feedback_score))

        # Sort by feedback score
        scored_base.sort(key=lambda x: x[1], reverse=True)

        # Check if any high-performing agents are missing
        base_ids = {a.template_id or a.spec.id for a in base_agents}
        for tid, score in best_agents:
            if tid not in base_ids and score > 0.7:
                # Add this high-performing agent
                try:
                    new_agent = self.base_generator.generate_agent_from_template(
                        tid,
                        customizations={
                            "languages": languages,
                            "quality_focus": quality_focus,
                        }
                    )
                    scored_base.append((new_agent, score))
                    logger.info(f"Added high-performing agent '{tid}' based on feedback")
                except ValueError:
                    pass  # Template not found

        # Return sorted agents
        return [agent for agent, _ in scored_base]

    def get_recommendation_explanation(
        self,
        requirements: dict[str, Any],
    ) -> dict[str, Any]:
        """Get explanation for agent recommendations.

        Args:
            requirements: Requirements dict

        Returns:
            Explanation of why agents were recommended
        """
        domain = requirements.get("domain", "general")
        languages = requirements.get("languages", [])
        quality_focus = requirements.get("quality_focus", [])

        best_agents = self.feedback.get_best_agents_for_context(
            domain=domain,
            languages=languages,
            quality_focus=quality_focus,
        )

        successful_patterns = self.feedback.get_successful_patterns(
            domain=domain,
            min_success_rate=0.7,
        )

        return {
            "context": {
                "domain": domain,
                "languages": languages,
                "quality_focus": quality_focus,
            },
            "recommended_agents": [
                {
                    "template_id": tid,
                    "score": score,
                    "performance": self.feedback.get_agent_performance(tid).to_dict()
                    if self.feedback.get_agent_performance(tid) else None,
                }
                for tid, score in best_agents
            ],
            "successful_patterns": [p.to_dict() for p in successful_patterns[:3]],
            "data_quality": {
                "total_executions": sum(
                    p.total_uses for p in self.feedback.get_all_performance().values()
                ),
                "agents_with_data": len([
                    p for p in self.feedback.get_all_performance().values()
                    if p.total_uses >= 5
                ]),
            },
        }


# =============================================================================
# FEEDBACK LOOP INTEGRATION
# =============================================================================


class FeedbackLoop:
    """High-level integration for the feedback loop.

    Provides a simple interface to:
    1. Record execution results
    2. Get improved recommendations
    3. View insights

    Example:
        >>> loop = FeedbackLoop()
        >>>
        >>> # After workflow execution
        >>> loop.record(blueprint, evaluation)
        >>>
        >>> # For next generation
        >>> agents = loop.get_recommended_agents(requirements)
        >>>
        >>> # View insights
        >>> insights = loop.get_insights()
    """

    def __init__(
        self,
        storage_path: str = ".empathy/socratic/feedback",
    ):
        """Initialize the feedback loop.

        Args:
            storage_path: Path for feedback storage
        """
        self.collector = FeedbackCollector(storage_path)
        self.adaptive_generator = AdaptiveAgentGenerator(self.collector)

    def record(
        self,
        blueprint: WorkflowBlueprint,
        evaluation: SuccessEvaluation,
    ) -> None:
        """Record execution results for learning.

        Args:
            blueprint: The executed blueprint
            evaluation: The success evaluation
        """
        self.collector.record_execution(blueprint, evaluation)

    def get_recommended_agents(
        self,
        requirements: dict[str, Any],
    ) -> list[AgentBlueprint]:
        """Get recommended agents using feedback data.

        Args:
            requirements: Requirements from Socratic session

        Returns:
            List of recommended agents
        """
        return self.adaptive_generator.generate_agents_for_requirements(requirements)

    def get_insights(self) -> dict[str, Any]:
        """Get aggregated insights.

        Returns:
            Dictionary with insights and recommendations
        """
        return self.collector.get_insights()

    def get_agent_stats(self, template_id: str) -> dict[str, Any] | None:
        """Get performance stats for a specific agent.

        Args:
            template_id: Agent template ID

        Returns:
            Performance statistics or None
        """
        perf = self.collector.get_agent_performance(template_id)
        return perf.to_dict() if perf else None

    def explain_recommendations(
        self,
        requirements: dict[str, Any],
    ) -> dict[str, Any]:
        """Explain why certain agents are recommended.

        Args:
            requirements: Requirements dict

        Returns:
            Explanation dictionary
        """
        return self.adaptive_generator.get_recommendation_explanation(requirements)
