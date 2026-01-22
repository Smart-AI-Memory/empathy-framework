"""Tests for execution strategies.

This module tests all 6 execution strategies:
1. SequentialStrategy
2. ParallelStrategy
3. DebateStrategy
4. TeachingStrategy
5. RefinementStrategy
6. AdaptiveStrategy

Unit tests use mock agents with predictable outputs.
Integration tests (marked with @pytest.mark.integration) use real agents.
"""

from unittest.mock import AsyncMock, patch

import pytest

from empathy_os.orchestration.agent_templates import (
    AgentTemplate,
    ResourceRequirements,
    get_template,
)
from empathy_os.orchestration.execution_strategies import (
    AdaptiveStrategy,
    AgentResult,
    DebateStrategy,
    ExecutionStrategy,
    ParallelStrategy,
    RefinementStrategy,
    SequentialStrategy,
    StrategyResult,
    TeachingStrategy,
    get_strategy,
)

# =============================================================================
# Mock Agent Fixtures (Predictable Outputs)
# =============================================================================


def create_mock_agent(agent_id: str, role: str, tier: str = "CAPABLE") -> AgentTemplate:
    """Create a mock AgentTemplate for testing."""
    return AgentTemplate(
        id=agent_id,
        role=role,
        capabilities=["analyze", "report"],
        tier_preference=tier,
        tools=["mock_tool"],
        default_instructions=f"Mock instructions for {role}",
        quality_gates={"min_score": 0.8},
        resource_requirements=ResourceRequirements(timeout_seconds=30),
    )


@pytest.fixture
def mock_agents():
    """Create mock agents with predictable behavior."""
    return [
        create_mock_agent("mock_analyzer_1", "Mock Analyzer 1"),
        create_mock_agent("mock_analyzer_2", "Mock Analyzer 2"),
        create_mock_agent("mock_analyzer_3", "Mock Analyzer 3"),
    ]


@pytest.fixture
def mock_junior_agent():
    """Create a mock junior/cheap agent."""
    return create_mock_agent("mock_junior", "Junior Writer", tier="CHEAP")


@pytest.fixture
def mock_expert_agent():
    """Create a mock expert/capable agent."""
    return create_mock_agent("mock_expert", "Expert Reviewer", tier="CAPABLE")


@pytest.fixture
def test_context():
    """Get test context dictionary."""
    return {"project": "test-project", "version": "1.0.0"}


def create_success_result(agent_id: str, output: dict | None = None) -> AgentResult:
    """Create a successful AgentResult."""
    return AgentResult(
        agent_id=agent_id,
        success=True,
        output=output or {"status": "passed", "passed": True, "score": 0.9},
        confidence=0.9,
        duration_seconds=0.5,
    )


def create_failure_result(agent_id: str, error: str = "Test failure") -> AgentResult:
    """Create a failed AgentResult."""
    return AgentResult(
        agent_id=agent_id,
        success=False,
        output={"status": "failed", "passed": False},
        confidence=0.3,
        duration_seconds=0.5,
        error=error,
    )


# =============================================================================
# Real Agent Fixtures (For Integration Tests)
# =============================================================================


@pytest.fixture
def real_agents():
    """Get real agent templates for integration tests."""
    return [
        get_template("test_coverage_analyzer"),
        get_template("code_reviewer"),
        get_template("documentation_writer"),
    ]


# =============================================================================
# Unit Tests - Sequential Strategy
# =============================================================================


class TestSequentialStrategy:
    """Test sequential execution strategy with mocks."""

    @pytest.mark.asyncio
    async def test_sequential_execution(self, mock_agents, test_context):
        """Test sequential execution of agents."""
        strategy = SequentialStrategy()

        # Mock _execute_agent to return predictable results
        async def mock_execute(agent, context):
            return create_success_result(agent.id)

        with patch.object(strategy, "_execute_agent", side_effect=mock_execute):
            result = await strategy.execute(mock_agents, test_context)

        assert result.success
        assert len(result.outputs) == len(mock_agents)
        assert result.total_duration > 0
        assert "num_agents" in result.aggregated_output
        assert result.aggregated_output["num_agents"] == len(mock_agents)

    @pytest.mark.asyncio
    async def test_sequential_passes_context_forward(self, mock_agents, test_context):
        """Test that sequential passes output to next agent."""
        strategy = SequentialStrategy()

        captured_contexts = []

        async def mock_execute(agent, context):
            captured_contexts.append(context.copy())
            return create_success_result(agent.id, {"data": f"from_{agent.id}"})

        with patch.object(strategy, "_execute_agent", side_effect=mock_execute):
            result = await strategy.execute(mock_agents[:2], test_context)

        assert result.success
        assert len(result.outputs) == 2
        # Second agent should have received first agent's output in context
        assert len(captured_contexts) == 2

    @pytest.mark.asyncio
    async def test_sequential_empty_agents_raises_error(self, test_context):
        """Test that empty agents list raises error."""
        strategy = SequentialStrategy()

        with pytest.raises(ValueError, match="agents list cannot be empty"):
            await strategy.execute([], test_context)

    @pytest.mark.asyncio
    async def test_sequential_single_agent(self, mock_agents, test_context):
        """Test sequential with single agent."""
        strategy = SequentialStrategy()

        async def mock_execute(agent, context):
            return create_success_result(agent.id)

        with patch.object(strategy, "_execute_agent", side_effect=mock_execute):
            result = await strategy.execute(mock_agents[:1], test_context)

        assert result.success
        assert len(result.outputs) == 1

    @pytest.mark.asyncio
    async def test_sequential_handles_agent_failure(self, mock_agents, test_context):
        """Test sequential handles an agent failure gracefully."""
        strategy = SequentialStrategy()

        call_count = 0

        async def mock_execute(agent, context):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                return create_failure_result(agent.id, "Agent 2 failed")
            return create_success_result(agent.id)

        with patch.object(strategy, "_execute_agent", side_effect=mock_execute):
            result = await strategy.execute(mock_agents, test_context)

        # Strategy should still complete but report the failure
        assert len(result.outputs) == 3
        assert result.outputs[1].success is False


# =============================================================================
# Unit Tests - Parallel Strategy
# =============================================================================


class TestParallelStrategy:
    """Test parallel execution strategy with mocks."""

    @pytest.mark.asyncio
    async def test_parallel_execution(self, mock_agents, test_context):
        """Test parallel execution of agents."""
        strategy = ParallelStrategy()

        async def mock_execute(agent, context):
            return create_success_result(agent.id)

        with patch.object(strategy, "_execute_agent", side_effect=mock_execute):
            result = await strategy.execute(mock_agents, test_context)

        assert result.success
        assert len(result.outputs) == len(mock_agents)

    @pytest.mark.asyncio
    async def test_parallel_all_agents_receive_same_context(self, mock_agents, test_context):
        """Test that all agents receive same initial context."""
        strategy = ParallelStrategy()

        captured_contexts = []

        async def mock_execute(agent, context):
            captured_contexts.append(context.copy())
            return create_success_result(agent.id)

        with patch.object(strategy, "_execute_agent", side_effect=mock_execute):
            result = await strategy.execute(mock_agents, test_context)

        assert result.success
        # All contexts should be identical (parallel doesn't chain context)
        for ctx in captured_contexts:
            assert ctx["project"] == test_context["project"]

    @pytest.mark.asyncio
    async def test_parallel_empty_agents_raises_error(self, test_context):
        """Test that empty agents list raises error."""
        strategy = ParallelStrategy()

        with pytest.raises(ValueError, match="agents list cannot be empty"):
            await strategy.execute([], test_context)

    @pytest.mark.asyncio
    async def test_parallel_handles_partial_failure(self, mock_agents, test_context):
        """Test parallel continues even if one agent fails."""
        strategy = ParallelStrategy()

        async def mock_execute(agent, context):
            if agent.id == "mock_analyzer_2":
                return create_failure_result(agent.id)
            return create_success_result(agent.id)

        with patch.object(strategy, "_execute_agent", side_effect=mock_execute):
            result = await strategy.execute(mock_agents, test_context)

        # All agents should have run
        assert len(result.outputs) == 3
        # One should have failed
        failures = [o for o in result.outputs if not o.success]
        assert len(failures) == 1


# =============================================================================
# Unit Tests - Debate Strategy
# =============================================================================


class TestDebateStrategy:
    """Test debate/consensus strategy with mocks."""

    @pytest.mark.asyncio
    async def test_debate_execution(self, mock_agents, test_context):
        """Test debate pattern execution."""
        strategy = DebateStrategy()

        async def mock_execute(agent, context):
            return create_success_result(agent.id, {"opinion": f"{agent.id}_opinion", "passed": True})

        with patch.object(strategy, "_execute_agent", side_effect=mock_execute):
            result = await strategy.execute(mock_agents[:2], test_context)

        assert result.success
        assert len(result.outputs) == 2
        assert "debate_participants" in result.aggregated_output
        assert "opinions" in result.aggregated_output
        assert "consensus" in result.aggregated_output

    @pytest.mark.asyncio
    async def test_debate_consensus_reached(self, mock_agents, test_context):
        """Test that consensus is synthesized when all pass."""
        strategy = DebateStrategy()

        async def mock_execute(agent, context):
            return create_success_result(agent.id, {"passed": True, "score": 0.9})

        with patch.object(strategy, "_execute_agent", side_effect=mock_execute):
            result = await strategy.execute(mock_agents[:2], test_context)

        consensus = result.aggregated_output["consensus"]
        assert "consensus_reached" in consensus
        assert "success_votes" in consensus
        assert "total_votes" in consensus
        assert consensus["consensus_reached"] is True
        assert consensus["success_votes"] == 2

    @pytest.mark.asyncio
    async def test_debate_no_consensus_when_disagreement(self, mock_agents, test_context):
        """Test that consensus is False when agents disagree."""
        strategy = DebateStrategy()

        call_count = 0

        async def mock_execute(self_arg, agent, context):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return create_success_result(agent.id, {"passed": True})
            return create_failure_result(agent.id)

        with patch.object(ExecutionStrategy, "_execute_agent", mock_execute):
            result = await strategy.execute(mock_agents[:2], test_context)

        consensus = result.aggregated_output["consensus"]
        assert consensus["consensus_reached"] is False
        assert consensus["success_votes"] == 1
        assert consensus["total_votes"] == 2

    @pytest.mark.asyncio
    async def test_debate_with_single_agent(self, mock_agents, test_context):
        """Test debate with single agent (edge case)."""
        strategy = DebateStrategy()

        async def mock_execute(agent, context):
            return create_success_result(agent.id)

        with patch.object(strategy, "_execute_agent", side_effect=mock_execute):
            result = await strategy.execute(mock_agents[:1], test_context)

        # Should still work
        assert result.success
        assert len(result.outputs) == 1


# =============================================================================
# Unit Tests - Teaching Strategy
# =============================================================================


class TestTeachingStrategy:
    """Test teaching/validation strategy with mocks."""

    @pytest.mark.asyncio
    async def test_teaching_junior_passes(self, mock_junior_agent, mock_expert_agent, test_context):
        """Test teaching pattern when junior passes quality gate."""
        strategy = TeachingStrategy(quality_threshold=0.7)

        async def mock_execute(agent, context):
            # Junior produces good output
            return create_success_result(agent.id, {"quality": 0.85, "passed": True})

        with patch.object(strategy, "_execute_agent", side_effect=mock_execute):
            result = await strategy.execute([mock_junior_agent, mock_expert_agent], test_context)

        assert result.success
        assert "junior_output" in result.aggregated_output

    @pytest.mark.asyncio
    async def test_teaching_expert_takeover(self, mock_junior_agent, mock_expert_agent, test_context):
        """Test teaching pattern when expert takes over."""
        strategy = TeachingStrategy(quality_threshold=0.95)

        call_count = 0

        async def mock_execute(agent, context):
            nonlocal call_count
            call_count += 1
            if call_count == 1:  # Junior
                return create_success_result(agent.id, {"quality": 0.7, "passed": True})
            return create_success_result(agent.id, {"quality": 0.98, "passed": True})

        with patch.object(strategy, "_execute_agent", side_effect=mock_execute):
            result = await strategy.execute([mock_junior_agent, mock_expert_agent], test_context)

        assert result.success
        assert "junior_output" in result.aggregated_output

    @pytest.mark.asyncio
    async def test_teaching_requires_two_agents(self, mock_agents, test_context):
        """Test that teaching requires exactly 2 agents."""
        strategy = TeachingStrategy()

        with pytest.raises(ValueError, match="Teaching strategy requires exactly 2 agents"):
            await strategy.execute(mock_agents, test_context)

    @pytest.mark.asyncio
    async def test_teaching_custom_threshold(self, mock_junior_agent, mock_expert_agent, test_context):
        """Test teaching with custom quality threshold."""
        strategy = TeachingStrategy(quality_threshold=0.5)

        async def mock_execute(agent, context):
            return create_success_result(agent.id, {"quality": 0.6, "passed": True})

        with patch.object(strategy, "_execute_agent", side_effect=mock_execute):
            result = await strategy.execute([mock_junior_agent, mock_expert_agent], test_context)

        assert result.success


# =============================================================================
# Unit Tests - Refinement Strategy
# =============================================================================


class TestRefinementStrategy:
    """Test progressive refinement strategy with mocks."""

    @pytest.mark.asyncio
    async def test_refinement_execution(self, mock_agents, test_context):
        """Test refinement pattern execution."""
        strategy = RefinementStrategy()

        async def mock_execute(agent, context):
            return create_success_result(agent.id, {"refined": True, "passed": True})

        with patch.object(strategy, "_execute_agent", side_effect=mock_execute):
            result = await strategy.execute(mock_agents, test_context)

        assert result.success
        assert len(result.outputs) == len(mock_agents)
        assert "refinement_stages" in result.aggregated_output
        assert "final_output" in result.aggregated_output
        assert "stage_outputs" in result.aggregated_output

    @pytest.mark.asyncio
    async def test_refinement_progressive_improvement(self, mock_agents, test_context):
        """Test that each stage refines previous output."""
        strategy = RefinementStrategy()

        stage = 0

        async def mock_execute(agent, context):
            nonlocal stage
            stage += 1
            return create_success_result(agent.id, {"stage": stage, "quality": 0.5 + stage * 0.1, "passed": True})

        with patch.object(strategy, "_execute_agent", side_effect=mock_execute):
            result = await strategy.execute(mock_agents, test_context)

        assert result.success
        stage_outputs = result.aggregated_output["stage_outputs"]
        assert len(stage_outputs) == len(mock_agents)

    @pytest.mark.asyncio
    async def test_refinement_requires_multiple_agents(self, mock_agents, test_context):
        """Test that refinement requires at least 2 agents."""
        strategy = RefinementStrategy()

        with pytest.raises(ValueError, match="Refinement strategy requires at least 2 agents"):
            await strategy.execute(mock_agents[:1], test_context)

    @pytest.mark.asyncio
    async def test_refinement_two_agents(self, mock_agents, test_context):
        """Test refinement with minimum 2 agents."""
        strategy = RefinementStrategy()

        async def mock_execute(agent, context):
            return create_success_result(agent.id, {"passed": True})

        with patch.object(strategy, "_execute_agent", side_effect=mock_execute):
            result = await strategy.execute(mock_agents[:2], test_context)

        assert result.success
        assert len(result.outputs) == 2


# =============================================================================
# Unit Tests - Adaptive Strategy
# =============================================================================


class TestAdaptiveStrategy:
    """Test adaptive routing strategy with mocks."""

    @pytest.mark.asyncio
    async def test_adaptive_execution(self, mock_agents, test_context):
        """Test adaptive routing execution."""
        strategy = AdaptiveStrategy()

        async def mock_execute(agent, context):
            return create_success_result(agent.id, {"passed": True})

        with patch.object(strategy, "_execute_agent", side_effect=mock_execute):
            result = await strategy.execute(mock_agents, test_context)

        assert result.success
        assert len(result.outputs) == 2  # Classifier + specialist
        assert "classification" in result.aggregated_output
        assert "selected_specialist" in result.aggregated_output
        assert "specialist_output" in result.aggregated_output

    @pytest.mark.asyncio
    async def test_adaptive_routes_to_specialist(self, mock_agents, test_context):
        """Test that adaptive routes to appropriate specialist."""
        strategy = AdaptiveStrategy()

        async def mock_execute(agent, context):
            return create_success_result(agent.id, {"passed": True})

        with patch.object(strategy, "_execute_agent", side_effect=mock_execute):
            result = await strategy.execute(mock_agents, test_context)

        selected = result.aggregated_output["selected_specialist"]
        # Should have selected one of the specialist agents
        assert selected in [a.id for a in mock_agents[1:]]

    @pytest.mark.asyncio
    async def test_adaptive_requires_multiple_agents(self, mock_agents, test_context):
        """Test that adaptive requires at least 2 agents."""
        strategy = AdaptiveStrategy()

        with pytest.raises(ValueError, match="Adaptive strategy requires at least 2 agents"):
            await strategy.execute(mock_agents[:1], test_context)


# =============================================================================
# Unit Tests - Strategy Registry
# =============================================================================


class TestStrategyRegistry:
    """Test strategy registry and lookup."""

    def test_get_strategy_sequential(self):
        """Test getting sequential strategy."""
        strategy = get_strategy("sequential")
        assert isinstance(strategy, SequentialStrategy)

    def test_get_strategy_parallel(self):
        """Test getting parallel strategy."""
        strategy = get_strategy("parallel")
        assert isinstance(strategy, ParallelStrategy)

    def test_get_strategy_debate(self):
        """Test getting debate strategy."""
        strategy = get_strategy("debate")
        assert isinstance(strategy, DebateStrategy)

    def test_get_strategy_teaching(self):
        """Test getting teaching strategy."""
        strategy = get_strategy("teaching")
        assert isinstance(strategy, TeachingStrategy)

    def test_get_strategy_refinement(self):
        """Test getting refinement strategy."""
        strategy = get_strategy("refinement")
        assert isinstance(strategy, RefinementStrategy)

    def test_get_strategy_adaptive(self):
        """Test getting adaptive strategy."""
        strategy = get_strategy("adaptive")
        assert isinstance(strategy, AdaptiveStrategy)

    def test_get_strategy_invalid_raises_error(self):
        """Test that invalid strategy name raises error."""
        with pytest.raises(ValueError, match="Unknown strategy"):
            get_strategy("invalid_strategy")


# =============================================================================
# Unit Tests - Data Classes
# =============================================================================


class TestAgentResult:
    """Test AgentResult dataclass."""

    def test_agent_result_creation(self):
        """Test creating AgentResult."""
        result = AgentResult(
            agent_id="test_agent",
            success=True,
            output={"key": "value"},
            confidence=0.9,
            duration_seconds=1.5,
        )

        assert result.agent_id == "test_agent"
        assert result.success is True
        assert result.output["key"] == "value"
        assert result.confidence == 0.9
        assert result.duration_seconds == 1.5
        assert result.error == ""

    def test_agent_result_with_error(self):
        """Test creating AgentResult with error."""
        result = AgentResult(
            agent_id="test_agent",
            success=False,
            output={},
            error="Something went wrong",
        )

        assert result.success is False
        assert result.error == "Something went wrong"


class TestStrategyResult:
    """Test StrategyResult dataclass."""

    def test_strategy_result_creation(self):
        """Test creating StrategyResult."""
        outputs = [
            AgentResult("agent1", True, {"data": 1}, 0.9, 1.0),
            AgentResult("agent2", True, {"data": 2}, 0.8, 1.5),
        ]

        result = StrategyResult(
            success=True,
            outputs=outputs,
            aggregated_output={"combined": "data"},
            total_duration=2.5,
        )

        assert result.success is True
        assert len(result.outputs) == 2
        assert result.aggregated_output["combined"] == "data"
        assert result.total_duration == 2.5
        assert result.errors == []

    def test_strategy_result_with_errors(self):
        """Test creating StrategyResult with errors."""
        outputs = [
            AgentResult("agent1", False, {}, 0.0, 0.0, "Error 1"),
        ]

        result = StrategyResult(
            success=False,
            outputs=outputs,
            aggregated_output={},
            errors=["Error 1"],
        )

        assert result.success is False
        assert len(result.errors) == 1
        assert result.errors[0] == "Error 1"


# =============================================================================
# Integration Tests (Real Agents - Slow)
# =============================================================================


@pytest.mark.integration
@pytest.mark.slow
class TestIntegrationWithRealAgents:
    """Integration tests using real agent templates.

    These tests analyze the actual codebase and may fail if the codebase
    has issues (low coverage, quality problems, etc.). They are marked as
    'integration' and 'slow' to allow selective running.

    Run with: pytest -m integration
    Skip with: pytest -m "not integration"
    """

    @pytest.mark.asyncio
    async def test_sequential_with_real_agents(self, real_agents, test_context):
        """Integration test: sequential execution with real agents."""
        strategy = SequentialStrategy()
        result = await strategy.execute(real_agents, test_context)

        # Just verify it completes - success depends on codebase state
        assert result is not None
        assert len(result.outputs) == len(real_agents)

    @pytest.mark.asyncio
    async def test_parallel_with_real_agents(self, real_agents, test_context):
        """Integration test: parallel execution with real agents."""
        strategy = ParallelStrategy()
        result = await strategy.execute(real_agents, test_context)

        assert result is not None
        assert len(result.outputs) == len(real_agents)

    @pytest.mark.asyncio
    async def test_debate_with_real_agents(self, real_agents, test_context):
        """Integration test: debate execution with real agents."""
        strategy = DebateStrategy()
        result = await strategy.execute(real_agents[:2], test_context)

        assert result is not None
        assert "consensus" in result.aggregated_output

    @pytest.mark.asyncio
    async def test_refinement_with_real_agents(self, real_agents, test_context):
        """Integration test: refinement execution with real agents."""
        strategy = RefinementStrategy()
        result = await strategy.execute(real_agents, test_context)

        assert result is not None
        assert "refinement_stages" in result.aggregated_output


# =============================================================================
# NestingContext Tests
# =============================================================================


@pytest.mark.unit
class TestNestingContext:
    """Test NestingContext for nested workflow execution."""

    def test_create_with_default_max_depth(self):
        """Test NestingContext creation with default max depth."""
        from empathy_os.orchestration.execution_strategies import NestingContext

        ctx = NestingContext()

        assert ctx.current_depth == 0
        assert ctx.max_depth == NestingContext.DEFAULT_MAX_DEPTH
        assert ctx.workflow_stack == []

    def test_create_with_custom_max_depth(self):
        """Test NestingContext creation with custom max depth."""
        from empathy_os.orchestration.execution_strategies import NestingContext

        ctx = NestingContext(max_depth=5)

        assert ctx.max_depth == 5

    def test_can_nest_within_limits(self):
        """Test can_nest returns True when within depth limits."""
        from empathy_os.orchestration.execution_strategies import NestingContext

        ctx = NestingContext(max_depth=3)

        assert ctx.can_nest("workflow_a") is True

    def test_can_nest_at_max_depth_returns_false(self):
        """Test can_nest returns False when at max depth."""
        from empathy_os.orchestration.execution_strategies import NestingContext

        ctx = NestingContext(max_depth=2)
        ctx.current_depth = 2

        assert ctx.can_nest("workflow_a") is False

    def test_can_nest_detects_cycles(self):
        """Test can_nest detects cycles in workflow stack."""
        from empathy_os.orchestration.execution_strategies import NestingContext

        ctx = NestingContext(max_depth=5)
        ctx.workflow_stack = ["workflow_a", "workflow_b"]

        # workflow_a is already in stack - cycle!
        assert ctx.can_nest("workflow_a") is False
        # workflow_c is not in stack - ok
        assert ctx.can_nest("workflow_c") is True

    def test_enter_increments_depth(self):
        """Test enter creates child context with incremented depth."""
        from empathy_os.orchestration.execution_strategies import NestingContext

        parent = NestingContext(max_depth=3)
        child = parent.enter("workflow_a")

        assert child.current_depth == 1
        assert parent.current_depth == 0  # Parent unchanged
        assert child.max_depth == parent.max_depth

    def test_enter_adds_to_workflow_stack(self):
        """Test enter adds workflow_id to stack."""
        from empathy_os.orchestration.execution_strategies import NestingContext

        parent = NestingContext()
        child = parent.enter("workflow_a")

        assert child.workflow_stack == ["workflow_a"]
        assert parent.workflow_stack == []  # Parent unchanged

    def test_enter_preserves_existing_stack(self):
        """Test enter preserves existing workflow stack."""
        from empathy_os.orchestration.execution_strategies import NestingContext

        parent = NestingContext()
        parent.workflow_stack = ["root_workflow"]

        child = parent.enter("child_workflow")

        assert child.workflow_stack == ["root_workflow", "child_workflow"]

    def test_from_context_creates_new_if_missing(self):
        """Test from_context creates new NestingContext if not in context."""
        from empathy_os.orchestration.execution_strategies import NestingContext

        context = {"task": "test"}

        result = NestingContext.from_context(context)

        assert isinstance(result, NestingContext)
        assert result.current_depth == 0

    def test_from_context_extracts_existing(self):
        """Test from_context extracts existing NestingContext."""
        from empathy_os.orchestration.execution_strategies import NestingContext

        existing = NestingContext(max_depth=5)
        existing.current_depth = 2
        context = {NestingContext.CONTEXT_KEY: existing}

        result = NestingContext.from_context(context)

        assert result is existing
        assert result.current_depth == 2

    def test_to_context_adds_nesting_info(self):
        """Test to_context adds nesting context to dict."""
        from empathy_os.orchestration.execution_strategies import NestingContext

        ctx = NestingContext()
        original = {"task": "test"}

        result = ctx.to_context(original)

        assert NestingContext.CONTEXT_KEY in result
        assert result[NestingContext.CONTEXT_KEY] is ctx
        assert "task" in original  # Original unchanged


# =============================================================================
# WorkflowReference and InlineWorkflow Tests
# =============================================================================


@pytest.mark.unit
class TestWorkflowReference:
    """Test WorkflowReference for nested workflow composition."""

    def test_create_with_workflow_id(self):
        """Test creating WorkflowReference with workflow_id."""
        from empathy_os.orchestration.execution_strategies import WorkflowReference

        ref = WorkflowReference(workflow_id="security-audit")

        assert ref.workflow_id == "security-audit"
        assert ref.inline is None

    def test_create_with_inline_workflow(self):
        """Test creating WorkflowReference with inline workflow."""
        from empathy_os.orchestration.execution_strategies import (
            InlineWorkflow,
            WorkflowReference,
        )

        agent = create_mock_agent("agent_1", "analyzer")
        inline = InlineWorkflow(agents=[agent], strategy="sequential")

        ref = WorkflowReference(inline=inline)

        assert ref.workflow_id == ""
        assert ref.inline is inline

    def test_validation_requires_exactly_one(self):
        """Test validation requires exactly one of workflow_id or inline."""
        from empathy_os.orchestration.execution_strategies import (
            InlineWorkflow,
            WorkflowReference,
        )

        # Neither provided - should raise
        with pytest.raises(ValueError, match="exactly one of"):
            WorkflowReference()

        # Both provided - should raise
        agent = create_mock_agent("agent_1", "analyzer")
        inline = InlineWorkflow(agents=[agent])
        with pytest.raises(ValueError, match="exactly one of"):
            WorkflowReference(workflow_id="test", inline=inline)

    def test_context_mapping_defaults_empty(self):
        """Test context_mapping defaults to empty dict."""
        from empathy_os.orchestration.execution_strategies import WorkflowReference

        ref = WorkflowReference(workflow_id="test")

        assert ref.context_mapping == {}

    def test_result_key_defaults(self):
        """Test result_key has default value."""
        from empathy_os.orchestration.execution_strategies import WorkflowReference

        ref = WorkflowReference(workflow_id="test")

        assert ref.result_key == "nested_result"


@pytest.mark.unit
class TestInlineWorkflow:
    """Test InlineWorkflow for inline workflow definitions."""

    def test_create_with_agents_and_strategy(self):
        """Test creating InlineWorkflow with agents and strategy."""
        from empathy_os.orchestration.execution_strategies import InlineWorkflow

        agent1 = create_mock_agent("agent_1", "analyzer")
        agent2 = create_mock_agent("agent_2", "reviewer")

        inline = InlineWorkflow(agents=[agent1, agent2], strategy="parallel")

        assert len(inline.agents) == 2
        assert inline.strategy == "parallel"

    def test_strategy_defaults_to_sequential(self):
        """Test strategy defaults to sequential."""
        from empathy_os.orchestration.execution_strategies import InlineWorkflow

        agent = create_mock_agent("agent_1", "analyzer")
        inline = InlineWorkflow(agents=[agent])

        assert inline.strategy == "sequential"

    def test_description_defaults_empty(self):
        """Test description defaults to empty string."""
        from empathy_os.orchestration.execution_strategies import InlineWorkflow

        agent = create_mock_agent("agent_1", "analyzer")
        inline = InlineWorkflow(agents=[agent])

        assert inline.description == ""


# =============================================================================
# StepDefinition Tests
# =============================================================================


@pytest.mark.unit
class TestStepDefinition:
    """Test StepDefinition for NestedSequentialStrategy steps."""

    def test_create_with_agent(self):
        """Test creating StepDefinition with agent."""
        from empathy_os.orchestration.execution_strategies import StepDefinition

        agent = create_mock_agent("agent_1", "analyzer")
        step = StepDefinition(agent=agent)

        assert step.agent is agent
        assert step.workflow_ref is None

    def test_create_with_workflow_ref(self):
        """Test creating StepDefinition with workflow reference."""
        from empathy_os.orchestration.execution_strategies import (
            StepDefinition,
            WorkflowReference,
        )

        ref = WorkflowReference(workflow_id="sub-workflow")
        step = StepDefinition(workflow_ref=ref)

        assert step.agent is None
        assert step.workflow_ref is ref

    def test_validation_requires_exactly_one(self):
        """Test validation requires exactly one of agent or workflow_ref."""
        from empathy_os.orchestration.execution_strategies import (
            StepDefinition,
            WorkflowReference,
        )

        # Neither provided - should raise
        with pytest.raises(ValueError, match="exactly one of"):
            StepDefinition()

        # Both provided - should raise
        agent = create_mock_agent("agent_1", "analyzer")
        ref = WorkflowReference(workflow_id="test")
        with pytest.raises(ValueError, match="exactly one of"):
            StepDefinition(agent=agent, workflow_ref=ref)


# =============================================================================
# NestedStrategy Tests
# =============================================================================


@pytest.mark.unit
class TestNestedStrategy:
    """Test NestedStrategy for nested workflow execution."""

    @pytest.mark.asyncio
    async def test_execute_inline_workflow(self):
        """Test executing inline nested workflow."""
        from empathy_os.orchestration.execution_strategies import (
            InlineWorkflow,
            NestedStrategy,
            WorkflowReference,
        )

        agent = create_mock_agent("agent_1", "analyzer")
        inline = InlineWorkflow(agents=[agent], strategy="sequential")
        ref = WorkflowReference(inline=inline)

        strategy = NestedStrategy(workflow_ref=ref)

        with patch.object(
            strategy, "_execute_agent", new_callable=AsyncMock
        ) as mock_execute:
            mock_execute.return_value = create_success_result("agent_1")
            result = await strategy.execute([], {"task": "test"})

        assert result.success is True
        assert "_nested" in result.aggregated_output
        assert result.aggregated_output["_nested"]["depth"] == 1

    @pytest.mark.asyncio
    async def test_execute_registered_workflow(self):
        """Test executing registered workflow by ID."""
        from empathy_os.orchestration.execution_strategies import (
            WORKFLOW_REGISTRY,
            NestedStrategy,
            WorkflowDefinition,
            WorkflowReference,
            register_workflow,
        )

        # Register a test workflow
        agent = create_mock_agent("agent_1", "analyzer")
        workflow = WorkflowDefinition(
            id="test-workflow",
            agents=[agent],
            strategy="sequential",
        )
        register_workflow(workflow)

        try:
            ref = WorkflowReference(workflow_id="test-workflow")
            strategy = NestedStrategy(workflow_ref=ref)

            with patch(
                "empathy_os.orchestration.execution_strategies.SequentialStrategy._execute_agent",
                new_callable=AsyncMock,
            ) as mock_execute:
                mock_execute.return_value = create_success_result("agent_1")
                result = await strategy.execute([], {"task": "test"})

            assert result.success is True
            assert result.aggregated_output["_nested"]["workflow_id"] == "test-workflow"
        finally:
            # Clean up registry
            WORKFLOW_REGISTRY.pop("test-workflow", None)

    @pytest.mark.asyncio
    async def test_execute_exceeds_max_depth_raises(self):
        """Test execute raises RecursionError when max depth exceeded."""
        from empathy_os.orchestration.execution_strategies import (
            InlineWorkflow,
            NestedStrategy,
            NestingContext,
            WorkflowReference,
        )

        agent = create_mock_agent("agent_1", "analyzer")
        inline = InlineWorkflow(agents=[agent])
        ref = WorkflowReference(inline=inline)

        strategy = NestedStrategy(workflow_ref=ref, max_depth=2)

        # Create context at max depth
        nesting = NestingContext(max_depth=2)
        nesting.current_depth = 2
        context = {NestingContext.CONTEXT_KEY: nesting, "task": "test"}

        with pytest.raises(RecursionError, match="Maximum nesting depth"):
            await strategy.execute([], context)

    @pytest.mark.asyncio
    async def test_execute_detects_cycle_raises(self):
        """Test execute raises RecursionError when cycle detected."""
        from empathy_os.orchestration.execution_strategies import (
            WORKFLOW_REGISTRY,
            NestedStrategy,
            NestingContext,
            WorkflowDefinition,
            WorkflowReference,
            register_workflow,
        )

        # Register workflow
        agent = create_mock_agent("agent_1", "analyzer")
        workflow = WorkflowDefinition(
            id="cyclic-workflow",
            agents=[agent],
            strategy="sequential",
        )
        register_workflow(workflow)

        try:
            ref = WorkflowReference(workflow_id="cyclic-workflow")
            strategy = NestedStrategy(workflow_ref=ref)

            # Create context with workflow already in stack
            nesting = NestingContext(max_depth=5)
            nesting.workflow_stack = ["parent", "cyclic-workflow"]
            context = {NestingContext.CONTEXT_KEY: nesting, "task": "test"}

            with pytest.raises(RecursionError, match="Cycle detected"):
                await strategy.execute([], context)
        finally:
            WORKFLOW_REGISTRY.pop("cyclic-workflow", None)

    @pytest.mark.asyncio
    async def test_execute_stores_result_with_key(self):
        """Test execute stores result under specified result_key."""
        from empathy_os.orchestration.execution_strategies import (
            InlineWorkflow,
            NestedStrategy,
            WorkflowReference,
        )

        agent = create_mock_agent("agent_1", "analyzer")
        inline = InlineWorkflow(agents=[agent])
        ref = WorkflowReference(inline=inline, result_key="custom_result")

        strategy = NestedStrategy(workflow_ref=ref)

        with patch.object(
            strategy, "_execute_agent", new_callable=AsyncMock
        ) as mock_execute:
            mock_execute.return_value = create_success_result("agent_1")
            result = await strategy.execute([], {"task": "test"})

        assert "custom_result" in result.aggregated_output


# =============================================================================
# NestedSequentialStrategy Tests
# =============================================================================


@pytest.mark.unit
class TestNestedSequentialStrategy:
    """Test NestedSequentialStrategy for mixed agent/workflow sequences."""

    @pytest.mark.asyncio
    async def test_execute_agent_steps(self):
        """Test executing steps with agents only."""
        from empathy_os.orchestration.execution_strategies import (
            NestedSequentialStrategy,
            StepDefinition,
        )

        agent1 = create_mock_agent("agent_1", "analyzer")
        agent2 = create_mock_agent("agent_2", "reviewer")

        steps = [
            StepDefinition(agent=agent1),
            StepDefinition(agent=agent2),
        ]

        strategy = NestedSequentialStrategy(steps=steps)

        with patch.object(
            strategy, "_execute_agent", new_callable=AsyncMock
        ) as mock_execute:
            mock_execute.return_value = create_success_result("agent_1")
            result = await strategy.execute([], {"task": "test"})

        assert result.success is True
        assert len(result.outputs) == 2

    @pytest.mark.asyncio
    async def test_execute_empty_steps_raises(self):
        """Test execute raises ValueError with empty steps."""
        from empathy_os.orchestration.execution_strategies import NestedSequentialStrategy

        strategy = NestedSequentialStrategy(steps=[])

        with pytest.raises(ValueError, match="steps list cannot be empty"):
            await strategy.execute([], {"task": "test"})

    @pytest.mark.asyncio
    async def test_execute_mixed_agent_and_workflow_steps(self):
        """Test executing mixed agent and nested workflow steps."""
        from empathy_os.orchestration.execution_strategies import (
            InlineWorkflow,
            NestedSequentialStrategy,
            StepDefinition,
            WorkflowReference,
        )

        agent1 = create_mock_agent("agent_1", "analyzer")
        nested_agent = create_mock_agent("nested_agent", "nested")
        inline = InlineWorkflow(agents=[nested_agent], strategy="sequential")
        ref = WorkflowReference(inline=inline)

        steps = [
            StepDefinition(agent=agent1),
            StepDefinition(workflow_ref=ref),
        ]

        strategy = NestedSequentialStrategy(steps=steps)

        with patch.object(
            strategy, "_execute_agent", new_callable=AsyncMock
        ) as mock_execute:
            mock_execute.return_value = create_success_result("agent_1")
            result = await strategy.execute([], {"task": "test"})

        assert result.success is True
        assert len(result.outputs) == 2
        # Second result should be from nested workflow
        assert result.outputs[1].agent_id.startswith("nested_")

    @pytest.mark.asyncio
    async def test_execute_passes_context_between_steps(self):
        """Test context is passed between sequential steps."""
        from empathy_os.orchestration.execution_strategies import (
            NestedSequentialStrategy,
            StepDefinition,
        )

        agent1 = create_mock_agent("agent_1", "analyzer")
        agent2 = create_mock_agent("agent_2", "reviewer")

        steps = [
            StepDefinition(agent=agent1),
            StepDefinition(agent=agent2),
        ]

        strategy = NestedSequentialStrategy(steps=steps)
        call_contexts = []

        async def capture_context(agent, context):
            call_contexts.append(context.copy())
            return create_success_result(agent.id, {"step_data": agent.id})

        with patch.object(
            strategy, "_execute_agent", side_effect=capture_context
        ):
            await strategy.execute([], {"task": "test"})

        # Second call should have first agent's output in context
        assert len(call_contexts) == 2
        assert "agent_1_output" in call_contexts[1]

    @pytest.mark.asyncio
    async def test_execute_calculates_total_duration(self):
        """Test total duration is sum of all step durations."""
        from empathy_os.orchestration.execution_strategies import (
            NestedSequentialStrategy,
            StepDefinition,
        )

        agent1 = create_mock_agent("agent_1", "analyzer")
        agent2 = create_mock_agent("agent_2", "reviewer")

        steps = [
            StepDefinition(agent=agent1),
            StepDefinition(agent=agent2),
        ]

        strategy = NestedSequentialStrategy(steps=steps)

        results = [
            AgentResult(
                agent_id="agent_1",
                success=True,
                output={},
                confidence=0.9,
                duration_seconds=1.5,
            ),
            AgentResult(
                agent_id="agent_2",
                success=True,
                output={},
                confidence=0.9,
                duration_seconds=2.0,
            ),
        ]

        with patch.object(
            strategy, "_execute_agent", new_callable=AsyncMock, side_effect=results
        ):
            result = await strategy.execute([], {"task": "test"})

        assert result.total_duration == 3.5


# =============================================================================
# ConditionalStrategy Async Execute Tests
# =============================================================================


@pytest.mark.unit
class TestConditionalStrategyExecute:
    """Test ConditionalStrategy async execute method."""

    @pytest.mark.asyncio
    async def test_execute_then_branch_when_condition_true(self):
        """Test execute takes then_branch when condition is true."""
        from empathy_os.orchestration.execution_strategies import (
            Branch,
            Condition,
            ConditionalStrategy,
        )

        agent = create_mock_agent("then_agent", "executor")
        then_branch = Branch(agents=[agent], strategy="sequential")
        condition = Condition(predicate={"confidence": {"$gt": 0.5}})

        strategy = ConditionalStrategy(
            condition=condition, then_branch=then_branch, else_branch=None
        )

        context = {"confidence": 0.9}

        with patch(
            "empathy_os.orchestration.execution_strategies.SequentialStrategy._execute_agent",
            new_callable=AsyncMock,
        ) as mock_execute:
            mock_execute.return_value = create_success_result("then_agent")
            result = await strategy.execute([], context)

        assert result.success is True
        assert result.aggregated_output["_conditional"]["branch_taken"] == "then"

    @pytest.mark.asyncio
    async def test_execute_else_branch_when_condition_false(self):
        """Test execute takes else_branch when condition is false."""
        from empathy_os.orchestration.execution_strategies import (
            Branch,
            Condition,
            ConditionalStrategy,
        )

        then_agent = create_mock_agent("then_agent", "executor")
        else_agent = create_mock_agent("else_agent", "fallback")
        then_branch = Branch(agents=[then_agent], strategy="sequential")
        else_branch = Branch(agents=[else_agent], strategy="sequential")
        condition = Condition(predicate={"confidence": {"$gt": 0.8}})

        strategy = ConditionalStrategy(
            condition=condition, then_branch=then_branch, else_branch=else_branch
        )

        context = {"confidence": 0.5}  # Below threshold

        with patch(
            "empathy_os.orchestration.execution_strategies.SequentialStrategy._execute_agent",
            new_callable=AsyncMock,
        ) as mock_execute:
            mock_execute.return_value = create_success_result("else_agent")
            result = await strategy.execute([], context)

        assert result.success is True
        assert result.aggregated_output["_conditional"]["branch_taken"] == "else"

    @pytest.mark.asyncio
    async def test_execute_no_branch_when_condition_false_and_no_else(self):
        """Test execute returns empty result when condition false and no else_branch."""
        from empathy_os.orchestration.execution_strategies import (
            Branch,
            Condition,
            ConditionalStrategy,
        )

        agent = create_mock_agent("then_agent", "executor")
        then_branch = Branch(agents=[agent], strategy="sequential")
        condition = Condition(predicate={"confidence": {"$gt": 0.8}})

        strategy = ConditionalStrategy(
            condition=condition, then_branch=then_branch, else_branch=None
        )

        context = {"confidence": 0.5}  # Below threshold

        result = await strategy.execute([], context)

        assert result.success is True
        assert result.outputs == []
        assert result.aggregated_output["branch_taken"] is None

    @pytest.mark.asyncio
    async def test_execute_passes_conditional_context(self):
        """Test execute adds conditional info to branch context."""
        from empathy_os.orchestration.execution_strategies import (
            Branch,
            Condition,
            ConditionalStrategy,
        )

        agent = create_mock_agent("then_agent", "executor")
        then_branch = Branch(agents=[agent], strategy="sequential")
        condition = Condition(
            predicate={"status": {"$eq": "ready"}},
            description="Status check",
        )

        strategy = ConditionalStrategy(
            condition=condition, then_branch=then_branch
        )

        context = {"status": "ready"}

        with patch(
            "empathy_os.orchestration.execution_strategies.SequentialStrategy.execute",
            new_callable=AsyncMock,
        ) as mock_execute:
            from empathy_os.orchestration.execution_strategies import StrategyResult
            mock_execute.return_value = StrategyResult(
                success=True,
                outputs=[],
                aggregated_output={},
                total_duration=0.5,
            )
            await strategy.execute([], context)

        # Check that context was passed to branch
        call_args = mock_execute.call_args
        branch_context = call_args[0][1]
        assert "_conditional" in branch_context
        assert branch_context["_conditional"]["condition_met"] is True


# =============================================================================
# MultiConditionalStrategy Async Execute Tests
# =============================================================================


@pytest.mark.unit
class TestMultiConditionalStrategyExecute:
    """Test MultiConditionalStrategy async execute method."""

    @pytest.mark.asyncio
    async def test_execute_first_matching_condition(self):
        """Test execute takes first branch where condition matches."""
        from empathy_os.orchestration.execution_strategies import (
            Branch,
            Condition,
            MultiConditionalStrategy,
        )

        agent1 = create_mock_agent("agent_1", "handler_1")
        agent2 = create_mock_agent("agent_2", "handler_2")

        conditions = [
            (Condition(predicate={"type": {"$eq": "error"}}), Branch(agents=[agent1])),
            (Condition(predicate={"type": {"$eq": "warning"}}), Branch(agents=[agent2])),
        ]

        strategy = MultiConditionalStrategy(conditions=conditions)

        context = {"type": "warning"}

        with patch(
            "empathy_os.orchestration.execution_strategies.SequentialStrategy._execute_agent",
            new_callable=AsyncMock,
        ) as mock_execute:
            mock_execute.return_value = create_success_result("agent_2")
            result = await strategy.execute([], context)

        assert result.success is True
        assert result.aggregated_output["_matched_index"] == 1

    @pytest.mark.asyncio
    async def test_execute_default_branch_when_no_match(self):
        """Test execute takes default_branch when no conditions match."""
        from empathy_os.orchestration.execution_strategies import (
            Branch,
            Condition,
            MultiConditionalStrategy,
        )

        agent1 = create_mock_agent("agent_1", "handler_1")
        default_agent = create_mock_agent("default_agent", "fallback")

        conditions = [
            (Condition(predicate={"type": {"$eq": "error"}}), Branch(agents=[agent1])),
        ]
        default_branch = Branch(agents=[default_agent])

        strategy = MultiConditionalStrategy(
            conditions=conditions, default_branch=default_branch
        )

        context = {"type": "info"}  # No match

        with patch(
            "empathy_os.orchestration.execution_strategies.SequentialStrategy._execute_agent",
            new_callable=AsyncMock,
        ) as mock_execute:
            mock_execute.return_value = create_success_result("default_agent")
            result = await strategy.execute([], context)

        assert result.success is True

    @pytest.mark.asyncio
    async def test_execute_returns_empty_when_no_match_and_no_default(self):
        """Test execute returns empty result when no match and no default."""
        from empathy_os.orchestration.execution_strategies import (
            Branch,
            Condition,
            MultiConditionalStrategy,
        )

        agent1 = create_mock_agent("agent_1", "handler_1")

        conditions = [
            (Condition(predicate={"type": {"$eq": "error"}}), Branch(agents=[agent1])),
        ]

        strategy = MultiConditionalStrategy(conditions=conditions, default_branch=None)

        context = {"type": "info"}  # No match

        result = await strategy.execute([], context)

        assert result.success is True
        assert result.outputs == []
        assert result.aggregated_output["reason"] == "No conditions matched"

    @pytest.mark.asyncio
    async def test_execute_stops_at_first_match(self):
        """Test execute only evaluates until first match (short-circuit)."""
        from empathy_os.orchestration.execution_strategies import (
            Branch,
            Condition,
            MultiConditionalStrategy,
        )

        agent1 = create_mock_agent("agent_1", "handler_1")
        agent2 = create_mock_agent("agent_2", "handler_2")

        # Both conditions would match, but first should win
        conditions = [
            (Condition(predicate={"value": {"$gt": 5}}), Branch(agents=[agent1])),
            (Condition(predicate={"value": {"$gt": 3}}), Branch(agents=[agent2])),
        ]

        strategy = MultiConditionalStrategy(conditions=conditions)

        context = {"value": 10}  # Both conditions true

        with patch(
            "empathy_os.orchestration.execution_strategies.SequentialStrategy._execute_agent",
            new_callable=AsyncMock,
        ) as mock_execute:
            mock_execute.return_value = create_success_result("agent_1")
            result = await strategy.execute([], context)

        assert result.aggregated_output["_matched_index"] == 0  # First match


# =============================================================================
# WorkflowDefinition and Registry Tests
# =============================================================================


@pytest.mark.unit
class TestWorkflowRegistry:
    """Test workflow registration and retrieval."""

    def test_register_workflow(self):
        """Test registering a workflow."""
        from empathy_os.orchestration.execution_strategies import (
            WORKFLOW_REGISTRY,
            WorkflowDefinition,
            get_workflow,
            register_workflow,
        )

        agent = create_mock_agent("agent_1", "analyzer")
        workflow = WorkflowDefinition(
            id="test-registry-workflow",
            agents=[agent],
            strategy="parallel",
            description="Test workflow",
        )

        try:
            register_workflow(workflow)

            retrieved = get_workflow("test-registry-workflow")
            assert retrieved.id == "test-registry-workflow"
            assert retrieved.strategy == "parallel"
        finally:
            WORKFLOW_REGISTRY.pop("test-registry-workflow", None)

    def test_get_unknown_workflow_raises(self):
        """Test get_workflow raises ValueError for unknown workflow."""
        from empathy_os.orchestration.execution_strategies import get_workflow

        with pytest.raises(ValueError, match="Unknown workflow"):
            get_workflow("nonexistent-workflow-12345")

    def test_workflow_definition_defaults(self):
        """Test WorkflowDefinition default values."""
        from empathy_os.orchestration.execution_strategies import WorkflowDefinition

        agent = create_mock_agent("agent_1", "analyzer")
        workflow = WorkflowDefinition(id="test", agents=[agent])

        assert workflow.strategy == "sequential"
        assert workflow.description == ""


# =============================================================================
# get_strategy Tests
# =============================================================================


@pytest.mark.unit
class TestGetStrategy:
    """Test get_strategy factory function."""

    def test_get_sequential_strategy(self):
        """Test getting sequential strategy by name."""
        from empathy_os.orchestration.execution_strategies import (
            SequentialStrategy,
            get_strategy,
        )

        strategy = get_strategy("sequential")
        assert isinstance(strategy, SequentialStrategy)

    def test_get_parallel_strategy(self):
        """Test getting parallel strategy by name."""
        from empathy_os.orchestration.execution_strategies import (
            ParallelStrategy,
            get_strategy,
        )

        strategy = get_strategy("parallel")
        assert isinstance(strategy, ParallelStrategy)

    def test_get_unknown_strategy_raises(self):
        """Test get_strategy raises ValueError for unknown strategy."""
        from empathy_os.orchestration.execution_strategies import get_strategy

        with pytest.raises(ValueError, match="Unknown strategy"):
            get_strategy("nonexistent_strategy")

    def test_all_registered_strategies_are_retrievable(self):
        """Test all strategies in registry can be retrieved."""
        from empathy_os.orchestration.execution_strategies import (
            STRATEGY_REGISTRY,
            get_strategy,
        )

        for strategy_name in STRATEGY_REGISTRY:
            # ConditionalStrategy and others need args, skip those
            if strategy_name in ("conditional", "multi_conditional", "nested", "nested_sequential"):
                continue
            strategy = get_strategy(strategy_name)
            assert strategy is not None
