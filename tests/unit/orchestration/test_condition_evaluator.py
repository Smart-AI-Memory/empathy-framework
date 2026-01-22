"""Tests for condition evaluation in execution strategies.

These tests cover:
- Condition dataclass
- ConditionType enum
- ConditionEvaluator class
- JSON predicate operators
- Natural language fallback
"""

from unittest.mock import MagicMock

import pytest

from empathy_os.orchestration.execution_strategies import (
    Branch,
    Condition,
    ConditionalStrategy,
    ConditionEvaluator,
    ConditionType,
    MultiConditionalStrategy,
)


@pytest.mark.unit
class TestConditionType:
    """Test ConditionType enum."""

    def test_json_predicate_exists(self):
        """Test JSON_PREDICATE type exists."""
        assert ConditionType.JSON_PREDICATE is not None
        assert ConditionType.JSON_PREDICATE.value == "json"

    def test_natural_language_exists(self):
        """Test NATURAL_LANGUAGE type exists."""
        assert ConditionType.NATURAL_LANGUAGE is not None
        assert ConditionType.NATURAL_LANGUAGE.value == "natural"

    def test_composite_exists(self):
        """Test COMPOSITE type exists."""
        assert ConditionType.COMPOSITE is not None
        assert ConditionType.COMPOSITE.value == "composite"


@pytest.mark.unit
class TestCondition:
    """Test Condition dataclass."""

    def test_create_json_predicate_condition(self):
        """Test creating JSON predicate condition."""
        condition = Condition(
            predicate={"confidence": {"$gt": 0.8}},
            description="High confidence check",
        )

        assert condition.condition_type == ConditionType.JSON_PREDICATE
        assert condition.predicate == {"confidence": {"$gt": 0.8}}

    def test_create_natural_language_condition(self):
        """Test creating natural language condition."""
        condition = Condition(
            predicate="Is the code coverage above 80 percent?",
            condition_type=ConditionType.NATURAL_LANGUAGE,
            description="Coverage check",
        )

        assert condition.condition_type == ConditionType.NATURAL_LANGUAGE
        assert condition.predicate == "Is the code coverage above 80 percent?"

    def test_auto_detect_json_type(self):
        """Test auto-detection of JSON predicate type."""
        condition = Condition(
            predicate={"errors": {"$exists": False}},
        )

        assert condition.condition_type == ConditionType.JSON_PREDICATE

    def test_auto_detect_natural_language_type(self):
        """Test auto-detection of natural language type."""
        condition = Condition(
            predicate="Should we proceed with deployment?",
        )

        assert condition.condition_type == ConditionType.NATURAL_LANGUAGE

    def test_validate_eq_operator(self):
        """Test $eq operator validation."""
        condition = Condition(
            predicate={"status": {"$eq": "success"}},
        )
        # Should not raise
        assert condition.predicate is not None

    def test_validate_ne_operator(self):
        """Test $ne operator validation."""
        condition = Condition(
            predicate={"error": {"$ne": None}},
        )
        assert condition.predicate is not None

    def test_validate_gt_operator(self):
        """Test $gt operator validation."""
        condition = Condition(
            predicate={"score": {"$gt": 50}},
        )
        assert condition.predicate is not None

    def test_validate_in_operator(self):
        """Test $in operator validation."""
        condition = Condition(
            predicate={"tier": {"$in": ["cheap", "capable"]}},
        )
        assert condition.predicate is not None

    def test_validate_regex_operator(self):
        """Test $regex operator validation."""
        condition = Condition(
            predicate={"name": {"$regex": "^test_"}},
        )
        assert condition.predicate is not None

    def test_validate_and_operator(self):
        """Test $and operator validation."""
        condition = Condition(
            predicate={
                "$and": [
                    {"success": {"$eq": True}},
                    {"confidence": {"$gt": 0.5}},
                ]
            },
        )
        assert condition.predicate is not None

    def test_validate_or_operator(self):
        """Test $or operator validation."""
        condition = Condition(
            predicate={
                "$or": [
                    {"tier": {"$eq": "premium"}},
                    {"confidence": {"$gt": 0.9}},
                ]
            },
        )
        assert condition.predicate is not None


@pytest.mark.unit
class TestConditionEvaluator:
    """Test ConditionEvaluator class."""

    @pytest.fixture
    def evaluator(self):
        """Create evaluator instance."""
        return ConditionEvaluator()

    @pytest.fixture
    def test_context(self):
        """Create test context."""
        return {
            "confidence": 0.85,
            "success": True,
            "tier": "capable",
            "errors": [],
            "coverage": 75.5,
            "nested": {"value": 42},
        }

    def test_evaluate_eq_true(self, evaluator, test_context):
        """Test $eq evaluates to True."""
        condition = Condition(predicate={"success": {"$eq": True}})
        result = evaluator.evaluate(condition, test_context)
        assert result is True

    def test_evaluate_eq_false(self, evaluator, test_context):
        """Test $eq evaluates to False."""
        condition = Condition(predicate={"success": {"$eq": False}})
        result = evaluator.evaluate(condition, test_context)
        assert result is False

    def test_evaluate_ne_true(self, evaluator, test_context):
        """Test $ne evaluates to True."""
        condition = Condition(predicate={"tier": {"$ne": "premium"}})
        result = evaluator.evaluate(condition, test_context)
        assert result is True

    def test_evaluate_gt_true(self, evaluator, test_context):
        """Test $gt evaluates to True."""
        condition = Condition(predicate={"confidence": {"$gt": 0.8}})
        result = evaluator.evaluate(condition, test_context)
        assert result is True

    def test_evaluate_gt_false(self, evaluator, test_context):
        """Test $gt evaluates to False."""
        condition = Condition(predicate={"confidence": {"$gt": 0.9}})
        result = evaluator.evaluate(condition, test_context)
        assert result is False

    def test_evaluate_gte_true(self, evaluator, test_context):
        """Test $gte evaluates to True."""
        condition = Condition(predicate={"confidence": {"$gte": 0.85}})
        result = evaluator.evaluate(condition, test_context)
        assert result is True

    def test_evaluate_lt_true(self, evaluator, test_context):
        """Test $lt evaluates to True."""
        condition = Condition(predicate={"coverage": {"$lt": 80}})
        result = evaluator.evaluate(condition, test_context)
        assert result is True

    def test_evaluate_lte_true(self, evaluator, test_context):
        """Test $lte evaluates to True."""
        condition = Condition(predicate={"coverage": {"$lte": 75.5}})
        result = evaluator.evaluate(condition, test_context)
        assert result is True

    def test_evaluate_in_true(self, evaluator, test_context):
        """Test $in evaluates to True."""
        condition = Condition(
            predicate={"tier": {"$in": ["cheap", "capable", "premium"]}}
        )
        result = evaluator.evaluate(condition, test_context)
        assert result is True

    def test_evaluate_in_false(self, evaluator, test_context):
        """Test $in evaluates to False."""
        condition = Condition(predicate={"tier": {"$in": ["premium"]}})
        result = evaluator.evaluate(condition, test_context)
        assert result is False

    def test_evaluate_nin_true(self, evaluator, test_context):
        """Test $nin evaluates to True."""
        condition = Condition(predicate={"tier": {"$nin": ["premium"]}})
        result = evaluator.evaluate(condition, test_context)
        assert result is True

    def test_evaluate_exists_true(self, evaluator, test_context):
        """Test $exists evaluates to True."""
        condition = Condition(predicate={"confidence": {"$exists": True}})
        result = evaluator.evaluate(condition, test_context)
        assert result is True

    def test_evaluate_exists_false(self, evaluator, test_context):
        """Test $exists evaluates to False for missing field."""
        condition = Condition(predicate={"missing_field": {"$exists": True}})
        result = evaluator.evaluate(condition, test_context)
        assert result is False

    def test_evaluate_regex_true(self, evaluator):
        """Test $regex evaluates to True."""
        context = {"name": "test_function"}
        condition = Condition(predicate={"name": {"$regex": "^test_"}})
        result = evaluator.evaluate(condition, context)
        assert result is True

    def test_evaluate_regex_false(self, evaluator):
        """Test $regex evaluates to False."""
        context = {"name": "main_function"}
        condition = Condition(predicate={"name": {"$regex": "^test_"}})
        result = evaluator.evaluate(condition, context)
        assert result is False

    def test_evaluate_nested_value(self, evaluator, test_context):
        """Test nested value access with dot notation."""
        condition = Condition(predicate={"nested.value": {"$eq": 42}})
        result = evaluator.evaluate(condition, test_context)
        assert result is True

    def test_evaluate_and_true(self, evaluator, test_context):
        """Test $and evaluates to True when all conditions pass."""
        condition = Condition(
            predicate={
                "$and": [
                    {"success": {"$eq": True}},
                    {"confidence": {"$gt": 0.8}},
                ]
            }
        )
        result = evaluator.evaluate(condition, test_context)
        assert result is True

    def test_evaluate_and_false(self, evaluator, test_context):
        """Test $and evaluates to False when one condition fails."""
        condition = Condition(
            predicate={
                "$and": [
                    {"success": {"$eq": True}},
                    {"confidence": {"$gt": 0.9}},
                ]
            }
        )
        result = evaluator.evaluate(condition, test_context)
        assert result is False

    def test_evaluate_or_true(self, evaluator, test_context):
        """Test $or evaluates to True when one condition passes."""
        condition = Condition(
            predicate={
                "$or": [
                    {"tier": {"$eq": "premium"}},
                    {"confidence": {"$gt": 0.8}},
                ]
            }
        )
        result = evaluator.evaluate(condition, test_context)
        assert result is True

    def test_evaluate_or_false(self, evaluator, test_context):
        """Test $or evaluates to False when all conditions fail."""
        condition = Condition(
            predicate={
                "$or": [
                    {"tier": {"$eq": "premium"}},
                    {"confidence": {"$gt": 0.9}},
                ]
            }
        )
        result = evaluator.evaluate(condition, test_context)
        assert result is False

    def test_evaluate_not_true(self, evaluator, test_context):
        """Test $not inverts condition."""
        condition = Condition(
            predicate={"$not": {"tier": {"$eq": "premium"}}}
        )
        result = evaluator.evaluate(condition, test_context)
        assert result is True


@pytest.mark.unit
class TestBranch:
    """Test Branch dataclass."""

    def test_create_branch_with_strategy_name(self):
        """Test creating branch with strategy name."""
        branch = Branch(
            agents=["code_reviewer"],
            strategy="sequential",
        )

        assert branch.agents == ["code_reviewer"]
        assert branch.strategy == "sequential"

    def test_create_branch_with_multiple_agents(self):
        """Test creating branch with multiple agents."""
        branch = Branch(
            agents=["security_auditor", "code_reviewer"],
            strategy="parallel",
        )

        assert len(branch.agents) == 2
        assert branch.strategy == "parallel"


@pytest.mark.unit
class TestConditionalStrategy:
    """Test ConditionalStrategy class."""

    @pytest.fixture
    def mock_agents(self):
        """Create mock agents."""
        return {
            "reviewer": MagicMock(id="reviewer", tier="capable"),
            "auditor": MagicMock(id="auditor", tier="cheap"),
        }

    def test_init_with_condition_and_branches(self):
        """Test initializing conditional strategy."""
        condition = Condition(predicate={"success": {"$eq": True}})
        then_branch = Branch(agents=["reviewer"], strategy="sequential")
        else_branch = Branch(agents=["auditor"], strategy="sequential")

        strategy = ConditionalStrategy(
            condition=condition,
            then_branch=then_branch,
            else_branch=else_branch,
        )

        assert strategy.condition == condition
        assert strategy.then_branch == then_branch
        assert strategy.else_branch == else_branch

    def test_init_without_else_branch(self):
        """Test initializing without else branch."""
        condition = Condition(predicate={"success": {"$eq": True}})
        then_branch = Branch(agents=["reviewer"], strategy="sequential")

        strategy = ConditionalStrategy(
            condition=condition,
            then_branch=then_branch,
        )

        assert strategy.else_branch is None


@pytest.mark.unit
class TestMultiConditionalStrategy:
    """Test MultiConditionalStrategy class."""

    def test_init_with_conditions(self):
        """Test initializing multi-conditional strategy."""
        condition1 = Condition(predicate={"tier": {"$eq": "premium"}})
        condition2 = Condition(predicate={"tier": {"$eq": "capable"}})

        conditions = [
            (condition1, Branch(agents=["premium_reviewer"], strategy="sequential")),
            (condition2, Branch(agents=["standard_reviewer"], strategy="sequential")),
        ]

        default_branch = Branch(agents=["basic_reviewer"], strategy="sequential")

        strategy = MultiConditionalStrategy(
            conditions=conditions,
            default_branch=default_branch,
        )

        assert len(strategy.conditions) == 2
        assert strategy.default_branch == default_branch


@pytest.mark.unit
class TestConditionalStrategyExecute:
    """Test ConditionalStrategy execute method."""

    @pytest.fixture
    def mock_strategy_result(self):
        """Create a mock strategy result."""
        from empathy_os.orchestration.execution_strategies import StrategyResult

        return StrategyResult(
            success=True,
            outputs=[],
            aggregated_output={"result": "test_output"},
            total_duration=1.0,
        )

    @pytest.mark.asyncio
    async def test_execute_takes_then_branch_when_condition_true(self, mock_strategy_result):
        """Test execute takes then_branch when condition is True."""
        from unittest.mock import AsyncMock, patch

        condition = Condition(predicate={"success": {"$eq": True}})
        then_branch = Branch(agents=["reviewer"], strategy="sequential")
        else_branch = Branch(agents=["auditor"], strategy="sequential")

        strategy = ConditionalStrategy(
            condition=condition,
            then_branch=then_branch,
            else_branch=else_branch,
        )

        mock_branch_strategy = AsyncMock()
        mock_branch_strategy.execute.return_value = mock_strategy_result

        context = {"success": True}

        with patch(
            "empathy_os.orchestration.execution_strategies.get_strategy",
            return_value=mock_branch_strategy,
        ):
            result = await strategy.execute([], context)

        assert result.success is True
        assert result.aggregated_output["_conditional"]["branch_taken"] == "then"
        assert result.aggregated_output["_conditional"]["condition_met"] is True

    @pytest.mark.asyncio
    async def test_execute_takes_else_branch_when_condition_false(self, mock_strategy_result):
        """Test execute takes else_branch when condition is False."""
        from unittest.mock import AsyncMock, patch

        condition = Condition(predicate={"success": {"$eq": True}})
        then_branch = Branch(agents=["reviewer"], strategy="sequential")
        else_branch = Branch(agents=["auditor"], strategy="sequential")

        strategy = ConditionalStrategy(
            condition=condition,
            then_branch=then_branch,
            else_branch=else_branch,
        )

        mock_branch_strategy = AsyncMock()
        mock_branch_strategy.execute.return_value = mock_strategy_result

        context = {"success": False}

        with patch(
            "empathy_os.orchestration.execution_strategies.get_strategy",
            return_value=mock_branch_strategy,
        ):
            result = await strategy.execute([], context)

        assert result.success is True
        assert result.aggregated_output["_conditional"]["branch_taken"] == "else"
        assert result.aggregated_output["_conditional"]["condition_met"] is False

    @pytest.mark.asyncio
    async def test_execute_returns_empty_result_when_no_else_branch(self):
        """Test execute returns empty result when condition False and no else_branch."""
        condition = Condition(predicate={"success": {"$eq": True}})
        then_branch = Branch(agents=["reviewer"], strategy="sequential")

        strategy = ConditionalStrategy(
            condition=condition,
            then_branch=then_branch,
            else_branch=None,
        )

        context = {"success": False}

        result = await strategy.execute([], context)

        assert result.success is True
        assert result.outputs == []
        assert result.aggregated_output["branch_taken"] is None
        assert result.total_duration == 0.0

    @pytest.mark.asyncio
    async def test_execute_adds_conditional_to_context(self, mock_strategy_result):
        """Test execute adds _conditional info to branch context."""
        from unittest.mock import AsyncMock, patch

        condition = Condition(predicate={"count": {"$gt": 0}})
        then_branch = Branch(agents=["processor"], strategy="sequential")

        strategy = ConditionalStrategy(
            condition=condition,
            then_branch=then_branch,
        )

        mock_branch_strategy = AsyncMock()
        mock_branch_strategy.execute.return_value = mock_strategy_result

        context = {"count": 5}

        with patch(
            "empathy_os.orchestration.execution_strategies.get_strategy",
            return_value=mock_branch_strategy,
        ):
            await strategy.execute([], context)

        # Verify context passed to branch includes _conditional
        call_context = mock_branch_strategy.execute.call_args[0][1]
        assert "_conditional" in call_context
        assert call_context["_conditional"]["condition_met"] is True
        assert call_context["_conditional"]["branch"] == "then"

    @pytest.mark.asyncio
    async def test_execute_with_complex_condition(self, mock_strategy_result):
        """Test execute with $and condition."""
        from unittest.mock import AsyncMock, patch

        condition = Condition(
            predicate={
                "$and": [
                    {"coverage": {"$gte": 80}},
                    {"tests_passing": {"$eq": True}},
                ]
            }
        )
        then_branch = Branch(agents=["deployer"], strategy="sequential")
        else_branch = Branch(agents=["fixer"], strategy="sequential")

        strategy = ConditionalStrategy(
            condition=condition,
            then_branch=then_branch,
            else_branch=else_branch,
        )

        mock_branch_strategy = AsyncMock()
        mock_branch_strategy.execute.return_value = mock_strategy_result

        context = {"coverage": 85, "tests_passing": True}

        with patch(
            "empathy_os.orchestration.execution_strategies.get_strategy",
            return_value=mock_branch_strategy,
        ):
            result = await strategy.execute([], context)

        assert result.aggregated_output["_conditional"]["branch_taken"] == "then"


@pytest.mark.unit
class TestMultiConditionalStrategyExecute:
    """Test MultiConditionalStrategy execute method."""

    @pytest.fixture
    def mock_strategy_result(self):
        """Create a mock strategy result."""
        from empathy_os.orchestration.execution_strategies import StrategyResult

        return StrategyResult(
            success=True,
            outputs=[],
            aggregated_output={"result": "test_output"},
            total_duration=1.0,
        )

    @pytest.mark.asyncio
    async def test_execute_matches_first_condition(self, mock_strategy_result):
        """Test execute takes first matching condition."""
        from unittest.mock import AsyncMock, patch

        conditions = [
            (Condition(predicate={"tier": {"$eq": "premium"}}), Branch(agents=["premium"], strategy="sequential")),
            (Condition(predicate={"tier": {"$eq": "capable"}}), Branch(agents=["standard"], strategy="sequential")),
        ]

        strategy = MultiConditionalStrategy(conditions=conditions)

        mock_branch_strategy = AsyncMock()
        mock_branch_strategy.execute.return_value = mock_strategy_result

        context = {"tier": "premium"}

        with patch(
            "empathy_os.orchestration.execution_strategies.get_strategy",
            return_value=mock_branch_strategy,
        ):
            result = await strategy.execute([], context)

        assert result.success is True
        assert result.aggregated_output["_matched_index"] == 0

    @pytest.mark.asyncio
    async def test_execute_matches_second_condition(self, mock_strategy_result):
        """Test execute takes second matching condition when first fails."""
        from unittest.mock import AsyncMock, patch

        conditions = [
            (Condition(predicate={"tier": {"$eq": "premium"}}), Branch(agents=["premium"], strategy="sequential")),
            (Condition(predicate={"tier": {"$eq": "capable"}}), Branch(agents=["standard"], strategy="sequential")),
        ]

        strategy = MultiConditionalStrategy(conditions=conditions)

        mock_branch_strategy = AsyncMock()
        mock_branch_strategy.execute.return_value = mock_strategy_result

        context = {"tier": "capable"}

        with patch(
            "empathy_os.orchestration.execution_strategies.get_strategy",
            return_value=mock_branch_strategy,
        ):
            result = await strategy.execute([], context)

        assert result.success is True
        assert result.aggregated_output["_matched_index"] == 1

    @pytest.mark.asyncio
    async def test_execute_uses_default_branch_when_no_match(self, mock_strategy_result):
        """Test execute uses default_branch when no conditions match."""
        from unittest.mock import AsyncMock, patch

        conditions = [
            (Condition(predicate={"tier": {"$eq": "premium"}}), Branch(agents=["premium"], strategy="sequential")),
        ]
        default_branch = Branch(agents=["basic"], strategy="sequential")

        strategy = MultiConditionalStrategy(
            conditions=conditions,
            default_branch=default_branch,
        )

        mock_branch_strategy = AsyncMock()
        mock_branch_strategy.execute.return_value = mock_strategy_result

        context = {"tier": "cheap"}

        with patch(
            "empathy_os.orchestration.execution_strategies.get_strategy",
            return_value=mock_branch_strategy,
        ):
            result = await strategy.execute([], context)

        assert result.success is True
        # Default branch doesn't set _matched_index
        assert "_matched_index" not in result.aggregated_output

    @pytest.mark.asyncio
    async def test_execute_returns_empty_result_when_no_match_and_no_default(self):
        """Test execute returns empty result when no conditions match and no default."""
        conditions = [
            (Condition(predicate={"tier": {"$eq": "premium"}}), Branch(agents=["premium"], strategy="sequential")),
        ]

        strategy = MultiConditionalStrategy(conditions=conditions, default_branch=None)

        context = {"tier": "cheap"}

        result = await strategy.execute([], context)

        assert result.success is True
        assert result.outputs == []
        assert result.aggregated_output["reason"] == "No conditions matched"
        assert result.total_duration == 0.0

    @pytest.mark.asyncio
    async def test_execute_stops_on_first_match(self, mock_strategy_result):
        """Test execute stops evaluating after first match."""
        from unittest.mock import AsyncMock, patch

        # Both conditions would match, but only first should be used
        conditions = [
            (Condition(predicate={"score": {"$gt": 50}}), Branch(agents=["first"], strategy="sequential")),
            (Condition(predicate={"score": {"$gt": 50}}), Branch(agents=["second"], strategy="sequential")),
        ]

        strategy = MultiConditionalStrategy(conditions=conditions)

        mock_branch_strategy = AsyncMock()
        mock_branch_strategy.execute.return_value = mock_strategy_result

        context = {"score": 75}

        with patch(
            "empathy_os.orchestration.execution_strategies.get_strategy",
            return_value=mock_branch_strategy,
        ):
            result = await strategy.execute([], context)

        # Should match first condition, not second
        assert result.aggregated_output["_matched_index"] == 0

    @pytest.mark.asyncio
    async def test_execute_with_or_condition(self, mock_strategy_result):
        """Test execute with $or condition."""
        from unittest.mock import AsyncMock, patch

        conditions = [
            (
                Condition(
                    predicate={
                        "$or": [
                            {"tier": {"$eq": "premium"}},
                            {"priority": {"$eq": "high"}},
                        ]
                    }
                ),
                Branch(agents=["fast_track"], strategy="parallel"),
            ),
        ]

        strategy = MultiConditionalStrategy(conditions=conditions)

        mock_branch_strategy = AsyncMock()
        mock_branch_strategy.execute.return_value = mock_strategy_result

        context = {"tier": "capable", "priority": "high"}

        with patch(
            "empathy_os.orchestration.execution_strategies.get_strategy",
            return_value=mock_branch_strategy,
        ):
            result = await strategy.execute([], context)

        assert result.success is True
        assert result.aggregated_output["_matched_index"] == 0
