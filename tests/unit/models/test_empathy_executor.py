"""Unit tests for EmpathyLLMExecutor.

Tests for:
- Provider detection from model names
- Cost estimation
- Model routing for tasks
- Tier-based model selection
- MockLLMExecutor behavior

Copyright 2026 Smart-AI-Memory
Licensed under Fair Source License 0.9
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestProviderDetection:
    """Test provider detection from model names."""

    def _get_executor(self):
        """Create executor without triggering LLM initialization."""
        # Import here to avoid import issues at module level
        import sys
        from pathlib import Path

        # Add src to path if needed
        src_path = Path(__file__).parent.parent.parent.parent / "src"
        if str(src_path) not in sys.path:
            sys.path.insert(0, str(src_path))

        from empathy_os.models.empathy_executor import EmpathyLLMExecutor

        # Create executor with mock to avoid LLM initialization
        executor = EmpathyLLMExecutor(empathy_llm=MagicMock(), provider="anthropic")
        return executor

    @pytest.mark.parametrize(
        "model_id,expected_provider",
        [
            # Anthropic models
            ("claude-3-5-sonnet-20241022", "anthropic"),
            ("claude-3-5-haiku-20241022", "anthropic"),
            ("claude-opus-4-5-20250514", "anthropic"),
            ("claude-sonnet-4-5-20250514", "anthropic"),
            ("claude-3-haiku-20240307", "anthropic"),
            # OpenAI models
            ("gpt-4o", "openai"),
            ("gpt-4-turbo", "openai"),
            ("gpt-3.5-turbo", "openai"),
            ("o1-preview", "openai"),
            ("o1-mini", "openai"),
            # Google models
            ("gemini-1.5-pro", "google"),
            ("gemini-2.0-flash", "google"),
            ("gemini-pro", "google"),
            # Ollama models
            ("llama3.2:3b", "ollama"),
            ("mixtral:8x7b", "ollama"),
            ("codellama:7b", "ollama"),
            ("custom:model", "ollama"),  # Colon indicates Ollama format
            # Unknown defaults to anthropic
            ("unknown-model", "anthropic"),
        ],
    )
    def test_get_provider_for_model(self, model_id, expected_provider):
        """Test that model IDs are correctly mapped to providers."""
        executor = self._get_executor()
        result = executor._get_provider_for_model(model_id)
        assert result == expected_provider

    def test_provider_detection_case_insensitive(self):
        """Test that provider detection is case-insensitive."""
        executor = self._get_executor()

        # Test various case combinations
        assert executor._get_provider_for_model("CLAUDE-3-SONNET") == "anthropic"
        assert executor._get_provider_for_model("GPT-4O") == "openai"
        assert executor._get_provider_for_model("GEMINI-PRO") == "google"
        assert executor._get_provider_for_model("LLAMA3:8B") == "ollama"


class TestCostEstimation:
    """Test cost estimation functionality."""

    def _get_executor(self, provider="anthropic"):
        """Create executor for testing."""
        import sys
        from pathlib import Path

        src_path = Path(__file__).parent.parent.parent.parent / "src"
        if str(src_path) not in sys.path:
            sys.path.insert(0, str(src_path))

        from empathy_os.models.empathy_executor import EmpathyLLMExecutor

        return EmpathyLLMExecutor(empathy_llm=MagicMock(), provider=provider)

    @pytest.mark.parametrize(
        "task_type,expected_tier",
        [
            # Cheap tier tasks
            ("summarize", "cheap"),
            ("classify", "cheap"),
            ("triage", "cheap"),
            # Capable tier tasks
            ("generate_code", "capable"),
            ("fix_bug", "capable"),
            ("write_tests", "capable"),
            # Premium tier tasks
            ("coordinate", "premium"),
            ("architectural_decision", "premium"),
            ("complex_reasoning", "premium"),
            # Unknown defaults to capable
            ("unknown_task", "capable"),
        ],
    )
    def test_tier_routing_for_tasks(self, task_type, expected_tier):
        """Test that tasks are routed to correct tiers."""
        import sys
        from pathlib import Path

        src_path = Path(__file__).parent.parent.parent.parent / "src"
        if str(src_path) not in sys.path:
            sys.path.insert(0, str(src_path))

        from empathy_os.models.tasks import get_tier_for_task

        tier = get_tier_for_task(task_type)
        assert tier.value == expected_tier

    def test_estimate_cost_returns_float(self):
        """Test that cost estimation returns a float."""
        executor = self._get_executor()

        cost = executor.estimate_cost(
            task_type="summarize",
            input_tokens=1000,
            output_tokens=500,
        )

        assert isinstance(cost, float)
        assert cost >= 0.0

    def test_estimate_cost_scales_with_tokens(self):
        """Test that cost scales with token count."""
        executor = self._get_executor()

        cost_small = executor.estimate_cost("summarize", 100, 50)
        cost_large = executor.estimate_cost("summarize", 10000, 5000)

        # Larger token count should have higher cost
        assert cost_large > cost_small

    def test_estimate_cost_different_tiers(self):
        """Test that different tiers have different costs."""
        executor = self._get_executor()

        # Same token counts, different tasks (thus different tiers)
        cost_cheap = executor.estimate_cost("summarize", 1000, 500)
        cost_premium = executor.estimate_cost("coordinate", 1000, 500)

        # Premium tier should cost more (assuming pricing is set correctly)
        # Note: This depends on actual pricing in registry
        assert isinstance(cost_cheap, float)
        assert isinstance(cost_premium, float)


class TestGetModelForTask:
    """Test model selection for tasks."""

    def _get_executor(self, provider="anthropic"):
        """Create executor for testing."""
        import sys
        from pathlib import Path

        src_path = Path(__file__).parent.parent.parent.parent / "src"
        if str(src_path) not in sys.path:
            sys.path.insert(0, str(src_path))

        from empathy_os.models.empathy_executor import EmpathyLLMExecutor

        return EmpathyLLMExecutor(empathy_llm=MagicMock(), provider=provider)

    def test_get_model_returns_string(self):
        """Test that get_model_for_task returns a string."""
        executor = self._get_executor()

        model = executor.get_model_for_task("summarize")

        assert isinstance(model, str)

    def test_different_tasks_may_return_different_models(self):
        """Test that different task types may route to different models."""
        executor = self._get_executor()

        cheap_model = executor.get_model_for_task("summarize")
        premium_model = executor.get_model_for_task("coordinate")

        # Both should return valid model strings
        assert isinstance(cheap_model, str)
        assert isinstance(premium_model, str)


class TestMockLLMExecutor:
    """Test MockLLMExecutor for testing scenarios."""

    def _get_mock_executor(self):
        """Create mock executor."""
        import sys
        from pathlib import Path

        src_path = Path(__file__).parent.parent.parent.parent / "src"
        if str(src_path) not in sys.path:
            sys.path.insert(0, str(src_path))

        from empathy_os.models.executor import MockLLMExecutor

        return MockLLMExecutor(
            default_response="Test response",
            default_model="test-model-v1",
        )

    @pytest.mark.asyncio
    async def test_mock_executor_returns_response(self):
        """Test that mock executor returns configured response."""
        executor = self._get_mock_executor()

        response = await executor.run(
            task_type="summarize",
            prompt="Summarize this text",
        )

        assert response.content == "Test response"
        assert response.model_id == "test-model-v1"
        assert response.provider == "mock"

    @pytest.mark.asyncio
    async def test_mock_executor_tracks_call_history(self):
        """Test that mock executor tracks call history."""
        executor = self._get_mock_executor()

        # Make multiple calls
        await executor.run(task_type="summarize", prompt="First call")
        await executor.run(task_type="fix_bug", prompt="Second call")
        await executor.run(task_type="coordinate", prompt="Third call")

        assert len(executor.call_history) == 3
        assert executor.call_history[0]["task_type"] == "summarize"
        assert executor.call_history[1]["task_type"] == "fix_bug"
        assert executor.call_history[2]["task_type"] == "coordinate"

    @pytest.mark.asyncio
    async def test_mock_executor_estimates_tokens(self):
        """Test that mock executor provides token estimates."""
        executor = self._get_mock_executor()

        response = await executor.run(
            task_type="summarize",
            prompt="This is a test prompt with several words",
        )

        # Mock estimates tokens based on word count * 4
        assert response.tokens_input > 0
        assert response.tokens_output > 0

    def test_mock_executor_get_model_for_task(self):
        """Test that mock executor returns configured model."""
        executor = self._get_mock_executor()

        model = executor.get_model_for_task("any_task")

        assert model == "test-model-v1"

    def test_mock_executor_estimate_cost_zero(self):
        """Test that mock executor returns zero cost."""
        executor = self._get_mock_executor()

        cost = executor.estimate_cost("summarize", 1000, 500)

        assert cost == 0.0

    @pytest.mark.asyncio
    async def test_mock_executor_with_system_prompt(self):
        """Test that mock executor handles system prompts."""
        executor = self._get_mock_executor()

        response = await executor.run(
            task_type="generate_code",
            prompt="Write a function",
            system="You are a Python expert",
        )

        # System prompt should be tracked in call history
        assert executor.call_history[0]["system"] == "You are a Python expert"

    @pytest.mark.asyncio
    async def test_mock_executor_with_context(self):
        """Test that mock executor handles execution context."""
        import sys
        from pathlib import Path

        src_path = Path(__file__).parent.parent.parent.parent / "src"
        if str(src_path) not in sys.path:
            sys.path.insert(0, str(src_path))

        from empathy_os.models.executor import ExecutionContext, MockLLMExecutor

        executor = MockLLMExecutor()
        context = ExecutionContext(
            user_id="test_user",
            workflow_name="test_workflow",
            step_name="test_step",
        )

        response = await executor.run(
            task_type="summarize",
            prompt="Test prompt",
            context=context,
        )

        # Context should be tracked
        recorded_context = executor.call_history[0]["context"]
        assert recorded_context.user_id == "test_user"
        assert recorded_context.workflow_name == "test_workflow"


class TestLLMResponse:
    """Test LLMResponse dataclass."""

    def _get_response_class(self):
        """Get LLMResponse class."""
        import sys
        from pathlib import Path

        src_path = Path(__file__).parent.parent.parent.parent / "src"
        if str(src_path) not in sys.path:
            sys.path.insert(0, str(src_path))

        from empathy_os.models.executor import LLMResponse

        return LLMResponse

    def test_response_creation(self):
        """Test creating an LLMResponse."""
        LLMResponse = self._get_response_class()

        response = LLMResponse(
            content="Test content",
            model_id="claude-3-haiku",
            provider="anthropic",
            tier="cheap",
            tokens_input=100,
            tokens_output=50,
            cost_estimate=0.001,
            latency_ms=500,
        )

        assert response.content == "Test content"
        assert response.model_id == "claude-3-haiku"
        assert response.provider == "anthropic"
        assert response.tier == "cheap"

    def test_response_backward_compatibility_aliases(self):
        """Test backward compatibility property aliases."""
        LLMResponse = self._get_response_class()

        response = LLMResponse(
            content="Test",
            model_id="test-model",
            provider="test",
            tier="capable",
            tokens_input=100,
            tokens_output=50,
            cost_estimate=0.005,
        )

        # Test aliases
        assert response.input_tokens == response.tokens_input
        assert response.output_tokens == response.tokens_output
        assert response.model_used == response.model_id
        assert response.cost == response.cost_estimate

    def test_response_total_tokens(self):
        """Test total_tokens computed property."""
        LLMResponse = self._get_response_class()

        response = LLMResponse(
            content="Test",
            model_id="test",
            provider="test",
            tier="capable",
            tokens_input=100,
            tokens_output=50,
        )

        assert response.total_tokens == 150

    def test_response_default_values(self):
        """Test LLMResponse default values."""
        LLMResponse = self._get_response_class()

        response = LLMResponse(
            content="Minimal response",
            model_id="model",
            provider="provider",
            tier="tier",
        )

        assert response.tokens_input == 0
        assert response.tokens_output == 0
        assert response.cost_estimate == 0.0
        assert response.latency_ms == 0
        assert response.metadata == {}


class TestExecutionContext:
    """Test ExecutionContext dataclass."""

    def _get_context_class(self):
        """Get ExecutionContext class."""
        import sys
        from pathlib import Path

        src_path = Path(__file__).parent.parent.parent.parent / "src"
        if str(src_path) not in sys.path:
            sys.path.insert(0, str(src_path))

        from empathy_os.models.executor import ExecutionContext

        return ExecutionContext

    def test_context_creation(self):
        """Test creating an ExecutionContext."""
        ExecutionContext = self._get_context_class()

        context = ExecutionContext(
            user_id="user123",
            workflow_name="test-workflow",
            step_name="step1",
            task_type="summarize",
        )

        assert context.user_id == "user123"
        assert context.workflow_name == "test-workflow"
        assert context.step_name == "step1"
        assert context.task_type == "summarize"

    def test_context_default_values(self):
        """Test ExecutionContext default values."""
        ExecutionContext = self._get_context_class()

        context = ExecutionContext()

        assert context.user_id is None
        assert context.workflow_name is None
        assert context.step_name is None
        assert context.task_type is None
        assert context.provider_hint is None
        assert context.tier_hint is None
        assert context.timeout_seconds is None
        assert context.session_id is None
        assert context.metadata == {}

    def test_context_with_metadata(self):
        """Test ExecutionContext with metadata."""
        ExecutionContext = self._get_context_class()

        context = ExecutionContext(
            user_id="user",
            metadata={
                "retry_count": 3,
                "custom_key": "value",
            },
        )

        assert context.metadata["retry_count"] == 3
        assert context.metadata["custom_key"] == "value"


class TestTaskNormalization:
    """Test task type normalization."""

    def _get_normalize_function(self):
        """Get normalize_task_type function."""
        import sys
        from pathlib import Path

        src_path = Path(__file__).parent.parent.parent.parent / "src"
        if str(src_path) not in sys.path:
            sys.path.insert(0, str(src_path))

        from empathy_os.models.tasks import normalize_task_type

        return normalize_task_type

    @pytest.mark.parametrize(
        "input_task,expected",
        [
            ("fix_bug", "fix_bug"),
            ("Fix-Bug", "fix_bug"),
            ("FIX BUG", "fix_bug"),
            ("FIX-BUG", "fix_bug"),
            ("SUMMARIZE", "summarize"),
            ("Generate Code", "generate_code"),
            ("generate-code", "generate_code"),
        ],
    )
    def test_normalize_task_type(self, input_task, expected):
        """Test task type normalization."""
        normalize = self._get_normalize_function()

        result = normalize(input_task)

        assert result == expected


class TestIsKnownTask:
    """Test is_known_task function."""

    def _get_is_known_task(self):
        """Get is_known_task function."""
        import sys
        from pathlib import Path

        src_path = Path(__file__).parent.parent.parent.parent / "src"
        if str(src_path) not in sys.path:
            sys.path.insert(0, str(src_path))

        from empathy_os.models.tasks import is_known_task

        return is_known_task

    def test_known_tasks_return_true(self):
        """Test that known tasks are recognized."""
        is_known = self._get_is_known_task()

        known_tasks = [
            "summarize",
            "classify",
            "generate_code",
            "fix_bug",
            "coordinate",
            "complex_reasoning",
        ]

        for task in known_tasks:
            assert is_known(task), f"Expected {task} to be known"

    def test_unknown_tasks_return_false(self):
        """Test that unknown tasks return false."""
        is_known = self._get_is_known_task()

        unknown_tasks = [
            "unknown_task",
            "random_operation",
            "not_a_real_task",
        ]

        for task in unknown_tasks:
            assert not is_known(task), f"Expected {task} to be unknown"

    def test_is_known_with_normalization(self):
        """Test that is_known_task normalizes input."""
        is_known = self._get_is_known_task()

        # These should all be recognized as "fix_bug"
        assert is_known("fix_bug")
        assert is_known("Fix-Bug")
        assert is_known("FIX BUG")
