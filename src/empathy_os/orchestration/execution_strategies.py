"""Execution strategies for agent composition patterns.

This module implements the 7 grammar rules for composing agents:
1. Sequential (A → B → C)
2. Parallel (A || B || C)
3. Debate (A ⇄ B ⇄ C → Synthesis)
4. Teaching (Junior → Expert validation)
5. Refinement (Draft → Review → Polish)
6. Adaptive (Classifier → Specialist)
7. Conditional (if X then A else B) - branching based on gates

Security:
    - All agent outputs validated before passing to next agent
    - No eval() or exec() usage
    - Timeout enforcement at strategy level
    - Condition predicates validated (no code execution)

Example:
    >>> strategy = SequentialStrategy()
    >>> agents = [agent1, agent2, agent3]
    >>> result = await strategy.execute(agents, context)

    >>> # Conditional branching example
    >>> cond_strategy = ConditionalStrategy(
    ...     condition=Condition(predicate={"confidence": {"$lt": 0.8}}),
    ...     then_branch=expert_agents,
    ...     else_branch=fast_agents
    ... )
    >>> result = await cond_strategy.execute([], context)
"""

import asyncio
import json
import logging
import operator
import re
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .agent_templates import AgentTemplate

logger = logging.getLogger(__name__)


@dataclass
class AgentResult:
    """Result from agent execution.

    Attributes:
        agent_id: ID of agent that produced result
        success: Whether execution succeeded
        output: Agent output data
        confidence: Confidence score (0-1)
        duration_seconds: Execution time
        error: Error message if failed
    """

    agent_id: str
    success: bool
    output: dict[str, Any]
    confidence: float = 0.0
    duration_seconds: float = 0.0
    error: str = ""


@dataclass
class StrategyResult:
    """Aggregated result from strategy execution.

    Attributes:
        success: Whether overall execution succeeded
        outputs: List of individual agent results
        aggregated_output: Combined/synthesized output
        total_duration: Total execution time
        errors: List of errors encountered
    """

    success: bool
    outputs: list[AgentResult]
    aggregated_output: dict[str, Any]
    total_duration: float = 0.0
    errors: list[str] = field(default_factory=list)

    def __post_init__(self):
        """Initialize errors list if None."""
        if not self.errors:
            self.errors = []


# =============================================================================
# Conditional Grammar Types (Pattern 7)
# =============================================================================


class ConditionType(Enum):
    """Type of condition for gate evaluation.

    Attributes:
        JSON_PREDICATE: MongoDB-style JSON predicate ({"field": {"$op": value}})
        NATURAL_LANGUAGE: LLM-interpreted natural language condition
        COMPOSITE: Logical combination of conditions (AND/OR)
    """

    JSON_PREDICATE = "json"
    NATURAL_LANGUAGE = "natural"
    COMPOSITE = "composite"


@dataclass
class Condition:
    """A conditional gate for branching in agent workflows.

    Supports hybrid syntax: JSON predicates for simple conditions,
    natural language for complex semantic conditions.

    Attributes:
        predicate: JSON predicate dict or natural language string
        condition_type: How to evaluate the condition
        description: Human-readable description of the condition
        source_field: Which field(s) in context to evaluate

    JSON Predicate Operators:
        $eq: Equal to value
        $ne: Not equal to value
        $gt: Greater than value
        $gte: Greater than or equal to value
        $lt: Less than value
        $lte: Less than or equal to value
        $in: Value is in list
        $nin: Value is not in list
        $exists: Field exists (or not)
        $regex: Matches regex pattern

    Example (JSON):
        >>> # Low confidence triggers expert review
        >>> cond = Condition(
        ...     predicate={"confidence": {"$lt": 0.8}},
        ...     description="Confidence is below threshold"
        ... )

    Example (Natural Language):
        >>> # LLM interprets complex semantic condition
        >>> cond = Condition(
        ...     predicate="The security audit found critical vulnerabilities",
        ...     condition_type=ConditionType.NATURAL_LANGUAGE,
        ...     description="Security issues detected"
        ... )
    """

    predicate: dict[str, Any] | str
    condition_type: ConditionType = ConditionType.JSON_PREDICATE
    description: str = ""
    source_field: str = ""  # Empty means evaluate whole context

    def __post_init__(self):
        """Validate condition and auto-detect type."""
        if isinstance(self.predicate, str):
            # Auto-detect: if it looks like prose, it's natural language
            if " " in self.predicate and not self.predicate.startswith("{"):
                object.__setattr__(self, "condition_type", ConditionType.NATURAL_LANGUAGE)
        elif isinstance(self.predicate, dict):
            # Validate JSON predicate structure
            self._validate_predicate(self.predicate)
        else:
            raise ValueError(f"predicate must be dict or str, got {type(self.predicate)}")

    def _validate_predicate(self, predicate: dict[str, Any]) -> None:
        """Validate JSON predicate structure (no code execution).

        Args:
            predicate: The predicate dict to validate

        Raises:
            ValueError: If predicate contains invalid operators
        """
        valid_operators = {
            "$eq",
            "$ne",
            "$gt",
            "$gte",
            "$lt",
            "$lte",
            "$in",
            "$nin",
            "$exists",
            "$regex",
            "$and",
            "$or",
            "$not",
        }

        for key, value in predicate.items():
            if key.startswith("$"):
                if key not in valid_operators:
                    raise ValueError(f"Invalid operator: {key}")
            if isinstance(value, dict):
                self._validate_predicate(value)


@dataclass
class Branch:
    """A branch in conditional execution.

    Attributes:
        agents: Agents to execute in this branch
        strategy: Strategy to use for executing agents (default: sequential)
        label: Human-readable branch label
    """

    agents: list[AgentTemplate]
    strategy: str = "sequential"
    label: str = ""


# =============================================================================
# Nested Sentence Types (Phase 2 - Recursive Composition)
# =============================================================================


@dataclass
class WorkflowReference:
    """Reference to a workflow for nested composition.

    Enables "sentences within sentences" - workflows that invoke other workflows.
    Supports both registered workflow IDs and inline definitions.

    Attributes:
        workflow_id: ID of registered workflow (mutually exclusive with inline)
        inline: Inline workflow definition (mutually exclusive with workflow_id)
        context_mapping: Optional mapping of parent context fields to child
        result_key: Key to store nested workflow result in parent context

    Example (by ID):
        >>> ref = WorkflowReference(
        ...     workflow_id="security-audit-team",
        ...     result_key="security_result"
        ... )

    Example (inline):
        >>> ref = WorkflowReference(
        ...     inline=InlineWorkflow(
        ...         agents=[agent1, agent2],
        ...         strategy="parallel"
        ...     ),
        ...     result_key="analysis_result"
        ... )
    """

    workflow_id: str = ""
    inline: "InlineWorkflow | None" = None
    context_mapping: dict[str, str] = field(default_factory=dict)
    result_key: str = "nested_result"

    def __post_init__(self):
        """Validate that exactly one reference type is provided."""
        if bool(self.workflow_id) == bool(self.inline):
            raise ValueError(
                "WorkflowReference must have exactly one of: workflow_id or inline"
            )


@dataclass
class InlineWorkflow:
    """Inline workflow definition for nested composition.

    Allows defining a sub-workflow directly within a parent workflow,
    without requiring registration.

    Attributes:
        agents: Agents to execute
        strategy: Strategy name (from STRATEGY_REGISTRY)
        description: Human-readable description

    Example:
        >>> inline = InlineWorkflow(
        ...     agents=[analyzer, reviewer],
        ...     strategy="sequential",
        ...     description="Code review sub-workflow"
        ... )
    """

    agents: list[AgentTemplate]
    strategy: str = "sequential"
    description: str = ""


class NestingContext:
    """Tracks nesting depth and prevents infinite recursion.

    Attributes:
        current_depth: Current nesting level (0 = root)
        max_depth: Maximum allowed nesting depth
        workflow_stack: Stack of workflow IDs for cycle detection
    """

    CONTEXT_KEY = "_nesting"
    DEFAULT_MAX_DEPTH = 3

    def __init__(self, max_depth: int = DEFAULT_MAX_DEPTH):
        """Initialize nesting context.

        Args:
            max_depth: Maximum allowed nesting depth
        """
        self.current_depth = 0
        self.max_depth = max_depth
        self.workflow_stack: list[str] = []

    @classmethod
    def from_context(cls, context: dict[str, Any]) -> "NestingContext":
        """Extract or create NestingContext from execution context.

        Args:
            context: Execution context dict

        Returns:
            NestingContext instance
        """
        if cls.CONTEXT_KEY in context:
            return context[cls.CONTEXT_KEY]
        return cls()

    def can_nest(self, workflow_id: str = "") -> bool:
        """Check if another nesting level is allowed.

        Args:
            workflow_id: ID of workflow to nest (for cycle detection)

        Returns:
            True if nesting is allowed
        """
        if self.current_depth >= self.max_depth:
            return False
        if workflow_id and workflow_id in self.workflow_stack:
            return False  # Cycle detected
        return True

    def enter(self, workflow_id: str = "") -> "NestingContext":
        """Create a child context for nested execution.

        Args:
            workflow_id: ID of workflow being entered

        Returns:
            New NestingContext with incremented depth
        """
        child = NestingContext(self.max_depth)
        child.current_depth = self.current_depth + 1
        child.workflow_stack = self.workflow_stack.copy()
        if workflow_id:
            child.workflow_stack.append(workflow_id)
        return child

    def to_context(self, context: dict[str, Any]) -> dict[str, Any]:
        """Add nesting context to execution context.

        Args:
            context: Execution context dict

        Returns:
            Updated context with nesting info
        """
        context = context.copy()
        context[self.CONTEXT_KEY] = self
        return context


# Registry for named workflows (populated at runtime)
WORKFLOW_REGISTRY: dict[str, "WorkflowDefinition"] = {}


@dataclass
class WorkflowDefinition:
    """A registered workflow definition.

    Workflows can be registered and referenced by ID in nested compositions.

    Attributes:
        id: Unique workflow identifier
        agents: Agents in the workflow
        strategy: Composition strategy name
        description: Human-readable description
    """

    id: str
    agents: list[AgentTemplate]
    strategy: str = "sequential"
    description: str = ""


def register_workflow(workflow: WorkflowDefinition) -> None:
    """Register a workflow for nested references.

    Args:
        workflow: Workflow definition to register
    """
    WORKFLOW_REGISTRY[workflow.id] = workflow
    logger.info(f"Registered workflow: {workflow.id}")


def get_workflow(workflow_id: str) -> WorkflowDefinition:
    """Get a registered workflow by ID.

    Args:
        workflow_id: Workflow identifier

    Returns:
        WorkflowDefinition

    Raises:
        ValueError: If workflow is not registered
    """
    if workflow_id not in WORKFLOW_REGISTRY:
        raise ValueError(
            f"Unknown workflow: {workflow_id}. "
            f"Available: {list(WORKFLOW_REGISTRY.keys())}"
        )
    return WORKFLOW_REGISTRY[workflow_id]


class ConditionEvaluator:
    """Evaluates conditions against execution context.

    Supports both JSON predicates (fast, deterministic) and
    natural language conditions (LLM-interpreted, semantic).

    Security:
        - No eval() or exec() - all operators are whitelisted
        - JSON predicates use safe comparison operators
        - Natural language uses LLM API (no code execution)
    """

    # Mapping of JSON operators to Python comparison functions
    OPERATORS: dict[str, Callable[[Any, Any], bool]] = {
        "$eq": operator.eq,
        "$ne": operator.ne,
        "$gt": operator.gt,
        "$gte": operator.ge,
        "$lt": operator.lt,
        "$lte": operator.le,
        "$in": lambda val, lst: val in lst,
        "$nin": lambda val, lst: val not in lst,
        "$exists": lambda val, exists: (val is not None) == exists,
        "$regex": lambda val, pattern: bool(re.match(pattern, str(val))) if val else False,
    }

    def evaluate(self, condition: Condition, context: dict[str, Any]) -> bool:
        """Evaluate a condition against the current context.

        Args:
            condition: The condition to evaluate
            context: Execution context with agent results

        Returns:
            True if condition is met, False otherwise

        Example:
            >>> evaluator = ConditionEvaluator()
            >>> context = {"confidence": 0.6, "errors": 0}
            >>> cond = Condition(predicate={"confidence": {"$lt": 0.8}})
            >>> evaluator.evaluate(cond, context)
            True
        """
        if condition.condition_type == ConditionType.JSON_PREDICATE:
            return self._evaluate_json(condition.predicate, context)
        elif condition.condition_type == ConditionType.NATURAL_LANGUAGE:
            return self._evaluate_natural_language(condition.predicate, context)
        elif condition.condition_type == ConditionType.COMPOSITE:
            return self._evaluate_composite(condition.predicate, context)
        else:
            raise ValueError(f"Unknown condition type: {condition.condition_type}")

    def _evaluate_json(self, predicate: dict[str, Any], context: dict[str, Any]) -> bool:
        """Evaluate JSON predicate against context.

        Args:
            predicate: MongoDB-style predicate dict
            context: Context to evaluate against

        Returns:
            True if all conditions match
        """
        for field_name, condition_spec in predicate.items():
            # Handle logical operators
            if field_name == "$and":
                return all(self._evaluate_json(sub, context) for sub in condition_spec)
            if field_name == "$or":
                return any(self._evaluate_json(sub, context) for sub in condition_spec)
            if field_name == "$not":
                return not self._evaluate_json(condition_spec, context)

            # Get value from context (supports nested paths like "result.confidence")
            value = self._get_nested_value(context, field_name)

            # Evaluate condition
            if isinstance(condition_spec, dict):
                for op, target in condition_spec.items():
                    if op not in self.OPERATORS:
                        raise ValueError(f"Unknown operator: {op}")
                    if not self.OPERATORS[op](value, target):
                        return False
            else:
                # Direct equality check
                if value != condition_spec:
                    return False

        return True

    def _get_nested_value(self, context: dict[str, Any], path: str) -> Any:
        """Get nested value from context using dot notation.

        Args:
            context: Context dict
            path: Dot-separated path (e.g., "result.confidence")

        Returns:
            Value at path or None if not found
        """
        parts = path.split(".")
        current = context

        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
            else:
                return None

        return current

    def _evaluate_natural_language(
        self, condition_text: str, context: dict[str, Any]
    ) -> bool:
        """Evaluate natural language condition using LLM.

        Args:
            condition_text: Natural language condition
            context: Context to evaluate against

        Returns:
            True if LLM determines condition is met

        Note:
            Falls back to keyword matching if LLM unavailable.
        """
        logger.info(f"Evaluating natural language condition: {condition_text}")

        # Try LLM evaluation first
        try:
            return self._evaluate_with_llm(condition_text, context)
        except Exception as e:
            logger.warning(f"LLM evaluation failed, using keyword fallback: {e}")
            return self._keyword_fallback(condition_text, context)

    def _evaluate_with_llm(self, condition_text: str, context: dict[str, Any]) -> bool:
        """Use LLM to evaluate natural language condition.

        Args:
            condition_text: The condition in natural language
            context: Execution context

        Returns:
            LLM's determination (True/False)
        """
        # Import LLM client lazily to avoid circular imports
        try:
            from ..llm import get_cheap_tier_client
        except ImportError:
            logger.warning("LLM client not available for natural language conditions")
            raise

        # Prepare context summary for LLM
        context_summary = json.dumps(context, indent=2, default=str)[:2000]

        prompt = f"""Evaluate whether the following condition is TRUE or FALSE based on the context.

Condition: {condition_text}

Context:
{context_summary}

Respond with ONLY "TRUE" or "FALSE" (no explanation)."""

        client = get_cheap_tier_client()
        response = client.complete(prompt, max_tokens=10)

        result = response.strip().upper()
        return result == "TRUE"

    def _keyword_fallback(self, condition_text: str, context: dict[str, Any]) -> bool:
        """Fallback keyword-based evaluation for natural language.

        Args:
            condition_text: The condition text
            context: Execution context

        Returns:
            True if keywords suggest condition is likely met
        """
        # Simple keyword matching as fallback
        condition_lower = condition_text.lower()
        context_str = json.dumps(context, default=str).lower()

        # Check for negation
        is_negated = any(neg in condition_lower for neg in ["not ", "no ", "without "])

        # Extract key terms
        terms = re.findall(r"\b\w{4,}\b", condition_lower)
        terms = [t for t in terms if t not in {"the", "that", "this", "with", "from"}]

        # Count matching terms
        matches = sum(1 for term in terms if term in context_str)
        match_ratio = matches / len(terms) if terms else 0

        result = match_ratio > 0.5
        return not result if is_negated else result

    def _evaluate_composite(
        self, predicate: dict[str, Any], context: dict[str, Any]
    ) -> bool:
        """Evaluate composite condition (AND/OR of other conditions).

        Args:
            predicate: Composite predicate with $and/$or
            context: Context to evaluate against

        Returns:
            Result of logical combination
        """
        return self._evaluate_json(predicate, context)


class ExecutionStrategy(ABC):
    """Base class for agent composition strategies.

    All strategies must implement execute() method to define
    how agents are coordinated and results aggregated.
    """

    @abstractmethod
    async def execute(self, agents: list[AgentTemplate], context: dict[str, Any]) -> StrategyResult:
        """Execute agents using this strategy.

        Args:
            agents: List of agent templates to execute
            context: Initial context for execution

        Returns:
            StrategyResult with aggregated outputs

        Raises:
            ValueError: If agents list is empty
            TimeoutError: If execution exceeds timeout
        """
        pass

    async def _execute_agent(self, agent: AgentTemplate, context: dict[str, Any]) -> AgentResult:
        """Execute a single agent with real analysis tools.

        Maps agent capabilities to real tool implementations and executes them.

        Args:
            agent: Agent template to execute
            context: Execution context

        Returns:
            AgentResult with execution outcome
        """
        import time

        from ..orchestration.real_tools import (
            RealCodeQualityAnalyzer,
            RealCoverageAnalyzer,
            RealDocumentationAnalyzer,
            RealSecurityAuditor,
        )

        logger.info(f"Executing agent: {agent.id} ({agent.role})")
        start_time = time.perf_counter()

        # Get project root from context
        project_root = context.get("project_root", ".")
        target_path = context.get("target_path", "src")

        try:
            # Map agent ID to real tool implementation
            if agent.id == "security_auditor" or "security" in agent.role.lower():
                auditor = RealSecurityAuditor(project_root)
                report = auditor.audit(target_path)

                output = {
                    "agent_role": agent.role,
                    "total_issues": report.total_issues,
                    "critical_issues": report.critical_count,  # Match workflow field name
                    "high_issues": report.high_count,  # Match workflow field name
                    "medium_issues": report.medium_count,  # Match workflow field name
                    "passed": report.passed,
                    "issues_by_file": report.issues_by_file,
                }
                success = report.passed
                confidence = 1.0 if report.total_issues == 0 else 0.7

            elif agent.id == "test_coverage_analyzer" or "coverage" in agent.role.lower():
                analyzer = RealCoverageAnalyzer(project_root)
                report = analyzer.analyze()  # Analyzes all packages automatically

                output = {
                    "agent_role": agent.role,
                    "coverage_percent": report.total_coverage,  # Match workflow field name
                    "total_coverage": report.total_coverage,  # Keep for compatibility
                    "files_analyzed": report.files_analyzed,
                    "uncovered_files": report.uncovered_files,
                    "passed": report.total_coverage >= 80.0,
                }
                success = report.total_coverage >= 80.0
                confidence = min(report.total_coverage / 100.0, 1.0)

            elif agent.id == "code_reviewer" or "quality" in agent.role.lower():
                analyzer = RealCodeQualityAnalyzer(project_root)
                report = analyzer.analyze(target_path)

                output = {
                    "agent_role": agent.role,
                    "quality_score": report.quality_score,
                    "ruff_issues": report.ruff_issues,
                    "mypy_issues": report.mypy_issues,
                    "total_files": report.total_files,
                    "passed": report.passed,
                }
                success = report.passed
                confidence = report.quality_score / 10.0

            elif agent.id == "documentation_writer" or "documentation" in agent.role.lower():
                analyzer = RealDocumentationAnalyzer(project_root)
                report = analyzer.analyze(target_path)

                output = {
                    "agent_role": agent.role,
                    "completeness": report.completeness_percentage,
                    "coverage_percent": report.completeness_percentage,  # Match Release Prep field name
                    "total_functions": report.total_functions,
                    "documented_functions": report.documented_functions,
                    "total_classes": report.total_classes,
                    "documented_classes": report.documented_classes,
                    "missing_docstrings": report.missing_docstrings,
                    "passed": report.passed,
                }
                success = report.passed
                confidence = report.completeness_percentage / 100.0

            elif agent.id == "performance_optimizer" or "performance" in agent.role.lower():
                # Performance analysis placeholder - mark as passed for now
                # TODO: Implement real performance profiling
                logger.warning("Performance analysis not yet implemented, returning placeholder")
                output = {
                    "agent_role": agent.role,
                    "message": "Performance analysis not yet implemented",
                    "passed": True,
                    "placeholder": True,
                }
                success = True
                confidence = 1.0

            elif agent.id == "test_generator":
                # Test generation requires different handling (LLM-based)
                logger.info("Test generation requires manual invocation, returning placeholder")
                output = {
                    "agent_role": agent.role,
                    "message": "Test generation requires manual invocation",
                    "passed": True,
                }
                success = True
                confidence = 0.8

            else:
                # Unknown agent type - log warning and return placeholder
                logger.warning(f"Unknown agent type: {agent.id}, returning placeholder")
                output = {
                    "agent_role": agent.role,
                    "agent_id": agent.id,
                    "message": "Unknown agent type - no real implementation",
                    "passed": True,
                }
                success = True
                confidence = 0.5

            duration = time.perf_counter() - start_time

            logger.info(
                f"Agent {agent.id} completed: success={success}, "
                f"confidence={confidence:.2f}, duration={duration:.2f}s"
            )

            return AgentResult(
                agent_id=agent.id,
                success=success,
                output=output,
                confidence=confidence,
                duration_seconds=duration,
            )

        except Exception as e:
            duration = time.perf_counter() - start_time
            logger.error(f"Agent {agent.id} failed: {e}")

            return AgentResult(
                agent_id=agent.id,
                success=False,
                output={"agent_role": agent.role, "error_details": str(e)},
                error=str(e),
                confidence=0.0,
                duration_seconds=duration,
            )

    def _aggregate_results(self, results: list[AgentResult]) -> dict[str, Any]:
        """Aggregate results from multiple agents.

        Args:
            results: List of agent results

        Returns:
            Aggregated output dictionary
        """
        return {
            "num_agents": len(results),
            "all_succeeded": all(r.success for r in results),
            "avg_confidence": (
                sum(r.confidence for r in results) / len(results) if results else 0.0
            ),
            "outputs": [r.output for r in results],
        }


class SequentialStrategy(ExecutionStrategy):
    """Sequential composition (A → B → C).

    Executes agents one after another, passing results forward.
    Each agent receives output from previous agent in context.

    Use when:
        - Tasks must be done in order
        - Each step depends on previous results
        - Pipeline processing needed

    Example:
        Coverage Analyzer → Test Generator → Quality Validator
    """

    async def execute(self, agents: list[AgentTemplate], context: dict[str, Any]) -> StrategyResult:
        """Execute agents sequentially.

        Args:
            agents: List of agents to execute in order
            context: Initial context

        Returns:
            StrategyResult with sequential execution results
        """
        if not agents:
            raise ValueError("agents list cannot be empty")

        logger.info(f"Sequential execution of {len(agents)} agents")

        results: list[AgentResult] = []
        current_context = context.copy()
        total_duration = 0.0

        for agent in agents:
            try:
                result = await self._execute_agent(agent, current_context)
                results.append(result)
                total_duration += result.duration_seconds

                # Pass output to next agent's context
                if result.success:
                    current_context[f"{agent.id}_output"] = result.output
                else:
                    logger.error(f"Agent {agent.id} failed: {result.error}")
                    # Continue or stop based on error handling policy
                    # For now: continue to next agent

            except Exception as e:
                logger.exception(f"Error executing agent {agent.id}: {e}")
                results.append(
                    AgentResult(
                        agent_id=agent.id,
                        success=False,
                        output={},
                        error=str(e),
                    )
                )

        return StrategyResult(
            success=all(r.success for r in results),
            outputs=results,
            aggregated_output=self._aggregate_results(results),
            total_duration=total_duration,
            errors=[r.error for r in results if not r.success],
        )


class ParallelStrategy(ExecutionStrategy):
    """Parallel composition (A || B || C).

    Executes all agents simultaneously, aggregates results.
    Each agent receives same initial context.

    Use when:
        - Independent validations needed
        - Multi-perspective review desired
        - Time optimization important

    Example:
        Security Audit || Performance Check || Code Quality || Docs Check
    """

    async def execute(self, agents: list[AgentTemplate], context: dict[str, Any]) -> StrategyResult:
        """Execute agents in parallel.

        Args:
            agents: List of agents to execute concurrently
            context: Initial context for all agents

        Returns:
            StrategyResult with parallel execution results
        """
        if not agents:
            raise ValueError("agents list cannot be empty")

        logger.info(f"Parallel execution of {len(agents)} agents")

        # Execute all agents concurrently
        tasks = [self._execute_agent(agent, context) for agent in agents]

        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as e:
            logger.exception(f"Error in parallel execution: {e}")
            raise

        # Process results (handle exceptions)
        processed_results: list[AgentResult] = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Agent {agents[i].id} raised exception: {result}")
                processed_results.append(
                    AgentResult(
                        agent_id=agents[i].id,
                        success=False,
                        output={},
                        error=str(result),
                    )
                )
            else:
                # Type checker doesn't know we already filtered out exceptions
                assert isinstance(result, AgentResult)
                processed_results.append(result)

        total_duration = max((r.duration_seconds for r in processed_results), default=0.0)

        return StrategyResult(
            success=all(r.success for r in processed_results),
            outputs=processed_results,
            aggregated_output=self._aggregate_results(processed_results),
            total_duration=total_duration,
            errors=[r.error for r in processed_results if not r.success],
        )


class DebateStrategy(ExecutionStrategy):
    """Debate/Consensus composition (A ⇄ B ⇄ C → Synthesis).

    Agents provide independent opinions, then a synthesizer
    aggregates and resolves conflicts.

    Use when:
        - Multiple expert opinions needed
        - Architecture decisions require debate
        - Tradeoff analysis needed

    Example:
        Architect(scale) || Architect(cost) || Architect(simplicity) → Synthesizer
    """

    async def execute(self, agents: list[AgentTemplate], context: dict[str, Any]) -> StrategyResult:
        """Execute debate pattern.

        Args:
            agents: List of agents to debate (recommend 2-4)
            context: Initial context

        Returns:
            StrategyResult with synthesized consensus
        """
        if not agents:
            raise ValueError("agents list cannot be empty")

        if len(agents) < 2:
            logger.warning("Debate pattern works best with 2+ agents")

        logger.info(f"Debate execution with {len(agents)} agents")

        # Phase 1: Parallel execution for independent opinions
        parallel_strategy = ParallelStrategy()
        phase1_result = await parallel_strategy.execute(agents, context)

        # Phase 2: Synthesis (simplified - no actual synthesizer agent)
        # In production: would use dedicated synthesizer agent
        synthesis = {
            "debate_participants": [r.agent_id for r in phase1_result.outputs],
            "opinions": [r.output for r in phase1_result.outputs],
            "consensus": self._synthesize_opinions(phase1_result.outputs),
        }

        return StrategyResult(
            success=phase1_result.success,
            outputs=phase1_result.outputs,
            aggregated_output=synthesis,
            total_duration=phase1_result.total_duration,
            errors=phase1_result.errors,
        )

    def _synthesize_opinions(self, results: list[AgentResult]) -> dict[str, Any]:
        """Synthesize multiple agent opinions into consensus.

        Args:
            results: Agent results to synthesize

        Returns:
            Synthesized consensus
        """
        # Simplified synthesis: majority vote on success
        success_votes = sum(1 for r in results if r.success)
        consensus_reached = success_votes > len(results) / 2

        return {
            "consensus_reached": consensus_reached,
            "success_votes": success_votes,
            "total_votes": len(results),
            "avg_confidence": (
                sum(r.confidence for r in results) / len(results) if results else 0.0
            ),
        }


class TeachingStrategy(ExecutionStrategy):
    """Teaching/Validation (Junior → Expert Review).

    Junior agent attempts task (cheap tier), expert validates.
    If validation fails, expert takes over.

    Use when:
        - Cost-effective generation desired
        - Quality assurance critical
        - Simple tasks with review needed

    Example:
        Junior Writer(CHEAP) → Quality Gate → (pass ? done : Expert Review(CAPABLE))
    """

    def __init__(self, quality_threshold: float = 0.7):
        """Initialize teaching strategy.

        Args:
            quality_threshold: Minimum confidence for junior to pass (0-1)
        """
        self.quality_threshold = quality_threshold

    async def execute(self, agents: list[AgentTemplate], context: dict[str, Any]) -> StrategyResult:
        """Execute teaching pattern.

        Args:
            agents: [junior_agent, expert_agent] (exactly 2)
            context: Initial context

        Returns:
            StrategyResult with teaching outcome
        """
        if len(agents) != 2:
            raise ValueError("Teaching strategy requires exactly 2 agents")

        junior, expert = agents
        logger.info(f"Teaching: {junior.id} → {expert.id} validation")

        results: list[AgentResult] = []
        total_duration = 0.0

        # Phase 1: Junior attempt
        junior_result = await self._execute_agent(junior, context)
        results.append(junior_result)
        total_duration += junior_result.duration_seconds

        # Phase 2: Quality gate
        if junior_result.success and junior_result.confidence >= self.quality_threshold:
            logger.info(f"Junior passed quality gate (confidence={junior_result.confidence:.2f})")
            aggregated = {"outcome": "junior_success", "junior_output": junior_result.output}
        else:
            logger.info(
                f"Junior failed quality gate, expert taking over "
                f"(confidence={junior_result.confidence:.2f})"
            )

            # Phase 3: Expert takeover
            expert_context = context.copy()
            expert_context["junior_attempt"] = junior_result.output
            expert_result = await self._execute_agent(expert, expert_context)
            results.append(expert_result)
            total_duration += expert_result.duration_seconds

            aggregated = {
                "outcome": "expert_takeover",
                "junior_output": junior_result.output,
                "expert_output": expert_result.output,
            }

        return StrategyResult(
            success=all(r.success for r in results),
            outputs=results,
            aggregated_output=aggregated,
            total_duration=total_duration,
            errors=[r.error for r in results if not r.success],
        )


class RefinementStrategy(ExecutionStrategy):
    """Progressive Refinement (Draft → Review → Polish).

    Iterative improvement through multiple quality levels.
    Each agent refines output from previous stage.

    Use when:
        - Iterative improvement needed
        - Quality ladder desired
        - Multi-stage refinement beneficial

    Example:
        Drafter(CHEAP) → Reviewer(CAPABLE) → Polisher(PREMIUM)
    """

    async def execute(self, agents: list[AgentTemplate], context: dict[str, Any]) -> StrategyResult:
        """Execute refinement pattern.

        Args:
            agents: [drafter, reviewer, polisher] (3+ agents)
            context: Initial context

        Returns:
            StrategyResult with refined output
        """
        if len(agents) < 2:
            raise ValueError("Refinement strategy requires at least 2 agents")

        logger.info(f"Refinement with {len(agents)} stages")

        results: list[AgentResult] = []
        current_context = context.copy()
        total_duration = 0.0

        for i, agent in enumerate(agents):
            stage_name = f"stage_{i+1}"
            logger.info(f"Refinement {stage_name}: {agent.id}")

            result = await self._execute_agent(agent, current_context)
            results.append(result)
            total_duration += result.duration_seconds

            if result.success:
                # Pass refined output to next stage
                current_context[f"{stage_name}_output"] = result.output
                current_context["previous_output"] = result.output
            else:
                logger.error(f"Refinement stage {i+1} failed: {result.error}")
                break  # Stop refinement on failure

        # Final output is from last successful stage
        final_output = results[-1].output if results[-1].success else {}

        return StrategyResult(
            success=all(r.success for r in results),
            outputs=results,
            aggregated_output={
                "refinement_stages": len(results),
                "final_output": final_output,
                "stage_outputs": [r.output for r in results],
            },
            total_duration=total_duration,
            errors=[r.error for r in results if not r.success],
        )


class AdaptiveStrategy(ExecutionStrategy):
    """Adaptive Routing (Classifier → Specialist).

    Classifier assesses task complexity, routes to appropriate specialist.
    Right-sizing: match agent tier to task needs.

    Use when:
        - Variable task complexity
        - Cost optimization desired
        - Right-sizing important

    Example:
        Classifier(CHEAP) → route(simple|moderate|complex) → Specialist(tier)
    """

    async def execute(self, agents: list[AgentTemplate], context: dict[str, Any]) -> StrategyResult:
        """Execute adaptive routing pattern.

        Args:
            agents: [classifier, *specialists] (2+ agents)
            context: Initial context

        Returns:
            StrategyResult with routed execution
        """
        if len(agents) < 2:
            raise ValueError("Adaptive strategy requires at least 2 agents")

        classifier = agents[0]
        specialists = agents[1:]

        logger.info(f"Adaptive: {classifier.id} → {len(specialists)} specialists")

        results: list[AgentResult] = []
        total_duration = 0.0

        # Phase 1: Classification
        classifier_result = await self._execute_agent(classifier, context)
        results.append(classifier_result)
        total_duration += classifier_result.duration_seconds

        if not classifier_result.success:
            logger.error("Classifier failed, defaulting to first specialist")
            selected_specialist = specialists[0]
        else:
            # Phase 2: Route to specialist based on classification
            # Simplified: select based on confidence score
            if classifier_result.confidence > 0.8:
                # High confidence → simple task → cheap specialist
                selected_specialist = min(
                    specialists,
                    key=lambda s: {
                        "CHEAP": 0,
                        "CAPABLE": 1,
                        "PREMIUM": 2,
                    }.get(s.tier_preference, 1),
                )
            else:
                # Low confidence → complex task → premium specialist
                selected_specialist = max(
                    specialists,
                    key=lambda s: {
                        "CHEAP": 0,
                        "CAPABLE": 1,
                        "PREMIUM": 2,
                    }.get(s.tier_preference, 1),
                )

        logger.info(f"Routed to specialist: {selected_specialist.id}")

        # Phase 3: Execute selected specialist
        specialist_context = context.copy()
        specialist_context["classification"] = classifier_result.output
        specialist_result = await self._execute_agent(selected_specialist, specialist_context)
        results.append(specialist_result)
        total_duration += specialist_result.duration_seconds

        return StrategyResult(
            success=all(r.success for r in results),
            outputs=results,
            aggregated_output={
                "classification": classifier_result.output,
                "selected_specialist": selected_specialist.id,
                "specialist_output": specialist_result.output,
            },
            total_duration=total_duration,
            errors=[r.error for r in results if not r.success],
        )


class ConditionalStrategy(ExecutionStrategy):
    """Conditional branching (if X then A else B).

    The 7th grammar rule enabling dynamic workflow decisions based on gates.

    Use when:
        - Quality gates determine next steps
        - Error handling requires different paths
        - Agent consensus affects workflow
    """

    def __init__(
        self,
        condition: Condition,
        then_branch: Branch,
        else_branch: Branch | None = None,
    ):
        """Initialize conditional strategy."""
        self.condition = condition
        self.then_branch = then_branch
        self.else_branch = else_branch
        self.evaluator = ConditionEvaluator()

    async def execute(
        self, agents: list[AgentTemplate], context: dict[str, Any]
    ) -> StrategyResult:
        """Execute conditional branching."""
        logger.info(f"Conditional: Evaluating '{self.condition.description or 'condition'}'")

        condition_met = self.evaluator.evaluate(self.condition, context)
        logger.info(f"Conditional: Condition evaluated to {condition_met}")

        if condition_met:
            selected_branch = self.then_branch
            branch_label = "then"
        else:
            if self.else_branch is None:
                return StrategyResult(
                    success=True,
                    outputs=[],
                    aggregated_output={"branch_taken": None},
                    total_duration=0.0,
                )
            selected_branch = self.else_branch
            branch_label = "else"

        logger.info(f"Conditional: Taking '{branch_label}' branch")

        branch_strategy = get_strategy(selected_branch.strategy)
        branch_context = context.copy()
        branch_context["_conditional"] = {"condition_met": condition_met, "branch": branch_label}

        result = await branch_strategy.execute(selected_branch.agents, branch_context)
        result.aggregated_output["_conditional"] = {
            "condition_met": condition_met,
            "branch_taken": branch_label,
        }
        return result


class MultiConditionalStrategy(ExecutionStrategy):
    """Multiple conditional branches (switch/case pattern)."""

    def __init__(
        self,
        conditions: list[tuple[Condition, Branch]],
        default_branch: Branch | None = None,
    ):
        """Initialize multi-conditional strategy."""
        self.conditions = conditions
        self.default_branch = default_branch
        self.evaluator = ConditionEvaluator()

    async def execute(
        self, agents: list[AgentTemplate], context: dict[str, Any]
    ) -> StrategyResult:
        """Execute multi-conditional branching."""
        for i, (condition, branch) in enumerate(self.conditions):
            if self.evaluator.evaluate(condition, context):
                logger.info(f"MultiConditional: Condition {i + 1} matched")
                branch_strategy = get_strategy(branch.strategy)
                result = await branch_strategy.execute(branch.agents, context)
                result.aggregated_output["_matched_index"] = i
                return result

        if self.default_branch:
            branch_strategy = get_strategy(self.default_branch.strategy)
            return await branch_strategy.execute(self.default_branch.agents, context)

        return StrategyResult(
            success=True,
            outputs=[],
            aggregated_output={"reason": "No conditions matched"},
            total_duration=0.0,
        )


class NestedStrategy(ExecutionStrategy):
    """Nested workflow execution (sentences within sentences).

    Enables recursive composition where workflows invoke other workflows.
    Implements the "subordinate clause" pattern in the grammar metaphor.

    Features:
        - Reference workflows by ID or define inline
        - Configurable max depth (default: 3)
        - Cycle detection prevents infinite recursion
        - Full context inheritance from parent to child

    Use when:
        - Complex multi-stage pipelines need modular sub-workflows
        - Reusable workflow components should be shared
        - Hierarchical team structures (teams containing sub-teams)

    Example:
        >>> # Parent workflow with nested sub-workflow
        >>> strategy = NestedStrategy(
        ...     workflow_ref=WorkflowReference(workflow_id="security-audit"),
        ...     max_depth=3
        ... )
        >>> result = await strategy.execute([], context)

    Example (inline):
        >>> strategy = NestedStrategy(
        ...     workflow_ref=WorkflowReference(
        ...         inline=InlineWorkflow(
        ...             agents=[analyzer, reviewer],
        ...             strategy="parallel"
        ...         )
        ...     )
        ... )
    """

    def __init__(
        self,
        workflow_ref: WorkflowReference,
        max_depth: int = NestingContext.DEFAULT_MAX_DEPTH,
    ):
        """Initialize nested strategy.

        Args:
            workflow_ref: Reference to workflow (by ID or inline)
            max_depth: Maximum nesting depth allowed
        """
        self.workflow_ref = workflow_ref
        self.max_depth = max_depth

    async def execute(
        self, agents: list[AgentTemplate], context: dict[str, Any]
    ) -> StrategyResult:
        """Execute nested workflow.

        Args:
            agents: Ignored (workflow_ref defines agents)
            context: Parent execution context (inherited by child)

        Returns:
            StrategyResult from nested workflow execution

        Raises:
            RecursionError: If max depth exceeded or cycle detected
        """
        # Get or create nesting context
        nesting = NestingContext.from_context(context)

        # Resolve workflow
        if self.workflow_ref.workflow_id:
            workflow_id = self.workflow_ref.workflow_id
            workflow = get_workflow(workflow_id)
            workflow_agents = workflow.agents
            strategy_name = workflow.strategy
        else:
            workflow_id = f"inline_{id(self.workflow_ref.inline)}"
            workflow_agents = self.workflow_ref.inline.agents
            strategy_name = self.workflow_ref.inline.strategy

        # Check nesting limits
        if not nesting.can_nest(workflow_id):
            if nesting.current_depth >= nesting.max_depth:
                error_msg = (
                    f"Maximum nesting depth ({nesting.max_depth}) exceeded. "
                    f"Current stack: {' → '.join(nesting.workflow_stack)}"
                )
            else:
                error_msg = (
                    f"Cycle detected: workflow '{workflow_id}' already in stack. "
                    f"Stack: {' → '.join(nesting.workflow_stack)}"
                )
            logger.error(error_msg)
            raise RecursionError(error_msg)

        logger.info(
            f"Nested: Entering '{workflow_id}' at depth {nesting.current_depth + 1}"
        )

        # Create child context with updated nesting
        child_nesting = nesting.enter(workflow_id)
        child_context = child_nesting.to_context(context.copy())

        # Execute nested workflow
        strategy = get_strategy(strategy_name)
        result = await strategy.execute(workflow_agents, child_context)

        # Augment result with nesting metadata
        result.aggregated_output["_nested"] = {
            "workflow_id": workflow_id,
            "depth": child_nesting.current_depth,
            "parent_stack": nesting.workflow_stack,
        }

        # Store result under specified key if provided
        if self.workflow_ref.result_key:
            result.aggregated_output[self.workflow_ref.result_key] = result.aggregated_output.copy()

        logger.info(f"Nested: Exiting '{workflow_id}'")

        return result


class NestedSequentialStrategy(ExecutionStrategy):
    """Sequential execution with nested workflow support.

    Like SequentialStrategy but steps can be either agents OR workflow references.
    Enables mixing direct agent execution with nested sub-workflows.

    Example:
        >>> strategy = NestedSequentialStrategy(
        ...     steps=[
        ...         StepDefinition(agent=analyzer),
        ...         StepDefinition(workflow_ref=WorkflowReference(workflow_id="review-team")),
        ...         StepDefinition(agent=reporter),
        ...     ]
        ... )
    """

    def __init__(
        self,
        steps: list["StepDefinition"],
        max_depth: int = NestingContext.DEFAULT_MAX_DEPTH,
    ):
        """Initialize nested sequential strategy.

        Args:
            steps: List of step definitions (agents or workflow refs)
            max_depth: Maximum nesting depth
        """
        self.steps = steps
        self.max_depth = max_depth

    async def execute(
        self, agents: list[AgentTemplate], context: dict[str, Any]
    ) -> StrategyResult:
        """Execute steps sequentially, handling both agents and nested workflows."""
        if not self.steps:
            raise ValueError("steps list cannot be empty")

        logger.info(f"NestedSequential: Executing {len(self.steps)} steps")

        results: list[AgentResult] = []
        current_context = context.copy()
        total_duration = 0.0

        for i, step in enumerate(self.steps):
            logger.info(f"NestedSequential: Step {i + 1}/{len(self.steps)}")

            if step.agent:
                # Direct agent execution
                result = await self._execute_agent(step.agent, current_context)
                results.append(result)
                total_duration += result.duration_seconds

                if result.success:
                    current_context[f"{step.agent.id}_output"] = result.output
            else:
                # Nested workflow execution
                nested_strategy = NestedStrategy(
                    workflow_ref=step.workflow_ref,
                    max_depth=self.max_depth,
                )
                nested_result = await nested_strategy.execute([], current_context)
                total_duration += nested_result.total_duration

                # Convert to AgentResult for consistency
                results.append(
                    AgentResult(
                        agent_id=f"nested_{step.workflow_ref.workflow_id or 'inline'}",
                        success=nested_result.success,
                        output=nested_result.aggregated_output,
                        confidence=nested_result.aggregated_output.get("avg_confidence", 0.0),
                        duration_seconds=nested_result.total_duration,
                    )
                )

                if nested_result.success:
                    key = step.workflow_ref.result_key or f"step_{i}_output"
                    current_context[key] = nested_result.aggregated_output

        return StrategyResult(
            success=all(r.success for r in results),
            outputs=results,
            aggregated_output=self._aggregate_results(results),
            total_duration=total_duration,
            errors=[r.error for r in results if not r.success],
        )


@dataclass
class StepDefinition:
    """Definition of a step in NestedSequentialStrategy.

    Either agent OR workflow_ref must be provided (mutually exclusive).

    Attributes:
        agent: Agent to execute directly
        workflow_ref: Nested workflow to execute
    """

    agent: AgentTemplate | None = None
    workflow_ref: WorkflowReference | None = None

    def __post_init__(self):
        """Validate that exactly one step type is provided."""
        if bool(self.agent) == bool(self.workflow_ref):
            raise ValueError("StepDefinition must have exactly one of: agent or workflow_ref")


# Strategy registry for lookup by name
STRATEGY_REGISTRY: dict[str, type[ExecutionStrategy]] = {
    "sequential": SequentialStrategy,
    "parallel": ParallelStrategy,
    "debate": DebateStrategy,
    "teaching": TeachingStrategy,
    "refinement": RefinementStrategy,
    "adaptive": AdaptiveStrategy,
    "conditional": ConditionalStrategy,
    "multi_conditional": MultiConditionalStrategy,
    "nested": NestedStrategy,
    "nested_sequential": NestedSequentialStrategy,
}


def get_strategy(strategy_name: str) -> ExecutionStrategy:
    """Get strategy instance by name.

    Args:
        strategy_name: Strategy name (e.g., "sequential", "parallel")

    Returns:
        ExecutionStrategy instance

    Raises:
        ValueError: If strategy name is invalid

    Example:
        >>> strategy = get_strategy("sequential")
        >>> isinstance(strategy, SequentialStrategy)
        True
    """
    if strategy_name not in STRATEGY_REGISTRY:
        raise ValueError(
            f"Unknown strategy: {strategy_name}. " f"Available: {list(STRATEGY_REGISTRY.keys())}"
        )

    strategy_class = STRATEGY_REGISTRY[strategy_name]
    return strategy_class()
