"""Tests for the Socratic A/B testing module.

Copyright 2026 Smart-AI-Memory
Licensed under Fair Source License 0.9
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch


class TestExperiment:
    """Tests for Experiment dataclass."""

    def test_create_experiment(self):
        """Test creating an experiment."""
        from empathy_os.socratic.ab_testing import Experiment, AllocationStrategy

        experiment = Experiment(
            experiment_id="exp-001",
            name="Test Experiment",
            description="Testing workflow variations",
        )

        assert experiment.experiment_id == "exp-001"
        assert experiment.name == "Test Experiment"
        assert experiment.allocation_strategy == AllocationStrategy.FIXED
        assert experiment.is_active is True

    def test_experiment_with_custom_allocation(self):
        """Test experiment with custom allocation strategy."""
        from empathy_os.socratic.ab_testing import Experiment, AllocationStrategy

        experiment = Experiment(
            experiment_id="exp-002",
            name="Thompson Sampling Test",
            allocation_strategy=AllocationStrategy.THOMPSON_SAMPLING,
            allocation_params={"prior_alpha": 1, "prior_beta": 1},
        )

        assert experiment.allocation_strategy == AllocationStrategy.THOMPSON_SAMPLING
        assert experiment.allocation_params["prior_alpha"] == 1


class TestVariant:
    """Tests for Variant dataclass."""

    def test_create_variant(self, sample_workflow_blueprint):
        """Test creating a variant."""
        from empathy_os.socratic.ab_testing import Variant

        variant = Variant(
            variant_id="var-001",
            name="Control",
            workflow_blueprint=sample_workflow_blueprint,
            weight=0.5,
        )

        assert variant.variant_id == "var-001"
        assert variant.weight == 0.5
        assert variant.impressions == 0
        assert variant.conversions == 0

    def test_variant_conversion_rate(self, sample_workflow_blueprint):
        """Test variant conversion rate calculation."""
        from empathy_os.socratic.ab_testing import Variant

        variant = Variant(
            variant_id="var-001",
            name="Test",
            workflow_blueprint=sample_workflow_blueprint,
        )
        variant.impressions = 100
        variant.conversions = 25

        assert variant.conversion_rate == 0.25

    def test_variant_zero_impressions(self, sample_workflow_blueprint):
        """Test conversion rate with zero impressions."""
        from empathy_os.socratic.ab_testing import Variant

        variant = Variant(
            variant_id="var-001",
            name="Test",
            workflow_blueprint=sample_workflow_blueprint,
        )

        assert variant.conversion_rate == 0.0


class TestAllocationStrategy:
    """Tests for allocation strategies."""

    def test_fixed_allocation(self):
        """Test fixed weight allocation."""
        from empathy_os.socratic.ab_testing import AllocationStrategy

        assert AllocationStrategy.FIXED.value == "fixed"

    def test_epsilon_greedy(self):
        """Test epsilon-greedy strategy exists."""
        from empathy_os.socratic.ab_testing import AllocationStrategy

        assert AllocationStrategy.EPSILON_GREEDY.value == "epsilon_greedy"

    def test_thompson_sampling(self):
        """Test Thompson sampling strategy exists."""
        from empathy_os.socratic.ab_testing import AllocationStrategy

        assert AllocationStrategy.THOMPSON_SAMPLING.value == "thompson_sampling"

    def test_ucb(self):
        """Test UCB strategy exists."""
        from empathy_os.socratic.ab_testing import AllocationStrategy

        assert AllocationStrategy.UCB.value == "ucb"


class TestExperimentManager:
    """Tests for ExperimentManager class."""

    def test_create_manager(self, storage_path):
        """Test creating an experiment manager."""
        from empathy_os.socratic.ab_testing import ExperimentManager

        manager = ExperimentManager(storage_path=storage_path / "experiments.json")

        assert manager.active_experiment_count == 0

    def test_create_experiment(self, storage_path, sample_workflow_blueprint):
        """Test creating an experiment via manager."""
        from empathy_os.socratic.ab_testing import ExperimentManager, Variant

        manager = ExperimentManager(storage_path=storage_path / "experiments.json")

        variants = [
            Variant(
                variant_id="control",
                name="Control",
                workflow_blueprint=sample_workflow_blueprint,
                weight=0.5,
            ),
            Variant(
                variant_id="treatment",
                name="Treatment",
                workflow_blueprint=sample_workflow_blueprint,
                weight=0.5,
            ),
        ]

        experiment = manager.create_experiment(
            name="Code Review Test",
            description="Testing different code review workflows",
            variants=variants,
        )

        assert experiment.experiment_id is not None
        assert len(experiment.variants) == 2
        assert manager.active_experiment_count == 1

    def test_allocate_variant_fixed(self, storage_path, sample_workflow_blueprint):
        """Test allocating variant with fixed strategy."""
        from empathy_os.socratic.ab_testing import (
            ExperimentManager,
            Variant,
            AllocationStrategy,
        )

        manager = ExperimentManager(storage_path=storage_path / "experiments.json")

        variants = [
            Variant(
                variant_id="control",
                name="Control",
                workflow_blueprint=sample_workflow_blueprint,
                weight=0.7,
            ),
            Variant(
                variant_id="treatment",
                name="Treatment",
                workflow_blueprint=sample_workflow_blueprint,
                weight=0.3,
            ),
        ]

        experiment = manager.create_experiment(
            name="Test",
            variants=variants,
            allocation_strategy=AllocationStrategy.FIXED,
        )

        # Allocate many times and check distribution
        allocations = {"control": 0, "treatment": 0}
        for _ in range(1000):
            variant = manager.allocate_variant(experiment.experiment_id)
            allocations[variant.variant_id] += 1

        # Should roughly match weights (70/30)
        control_ratio = allocations["control"] / 1000
        assert 0.60 < control_ratio < 0.80

    def test_record_outcome(self, storage_path, sample_workflow_blueprint):
        """Test recording experiment outcome."""
        from empathy_os.socratic.ab_testing import ExperimentManager, Variant

        manager = ExperimentManager(storage_path=storage_path / "experiments.json")

        variants = [
            Variant(
                variant_id="control",
                name="Control",
                workflow_blueprint=sample_workflow_blueprint,
            ),
        ]

        experiment = manager.create_experiment(name="Test", variants=variants)

        # Record outcomes
        manager.record_impression(experiment.experiment_id, "control")
        manager.record_impression(experiment.experiment_id, "control")
        manager.record_conversion(experiment.experiment_id, "control")

        updated = manager.get_experiment(experiment.experiment_id)
        control_variant = updated.variants[0]

        assert control_variant.impressions == 2
        assert control_variant.conversions == 1

    def test_stop_experiment(self, storage_path, sample_workflow_blueprint):
        """Test stopping an experiment."""
        from empathy_os.socratic.ab_testing import ExperimentManager, Variant

        manager = ExperimentManager(storage_path=storage_path / "experiments.json")

        variants = [
            Variant(
                variant_id="control",
                name="Control",
                workflow_blueprint=sample_workflow_blueprint,
            ),
        ]

        experiment = manager.create_experiment(name="Test", variants=variants)

        manager.stop_experiment(experiment.experiment_id)

        updated = manager.get_experiment(experiment.experiment_id)
        assert updated.is_active is False


class TestStatisticalAnalyzer:
    """Tests for StatisticalAnalyzer class."""

    def test_create_analyzer(self):
        """Test creating a statistical analyzer."""
        from empathy_os.socratic.ab_testing import StatisticalAnalyzer

        analyzer = StatisticalAnalyzer()
        assert analyzer is not None

    def test_z_test(self):
        """Test z-test for proportions."""
        from empathy_os.socratic.ab_testing import StatisticalAnalyzer

        analyzer = StatisticalAnalyzer()

        # Control: 100/1000 = 10% conversion
        # Treatment: 150/1000 = 15% conversion
        result = analyzer.z_test(
            control_conversions=100,
            control_trials=1000,
            treatment_conversions=150,
            treatment_trials=1000,
        )

        assert "z_score" in result
        assert "p_value" in result
        assert "significant" in result

    def test_wilson_confidence_interval(self):
        """Test Wilson score confidence interval."""
        from empathy_os.socratic.ab_testing import StatisticalAnalyzer

        analyzer = StatisticalAnalyzer()

        lower, upper = analyzer.wilson_confidence_interval(
            successes=100,
            trials=1000,
            confidence=0.95,
        )

        # 10% conversion rate, interval should contain it
        assert lower < 0.10 < upper
        assert lower > 0
        assert upper < 1

    def test_required_sample_size(self):
        """Test sample size calculation."""
        from empathy_os.socratic.ab_testing import StatisticalAnalyzer

        analyzer = StatisticalAnalyzer()

        sample_size = analyzer.required_sample_size(
            baseline_rate=0.10,
            minimum_detectable_effect=0.02,
            power=0.80,
            alpha=0.05,
        )

        # Should require substantial sample for detecting 2% lift
        assert sample_size > 1000


class TestWorkflowABTester:
    """Tests for WorkflowABTester class."""

    def test_create_tester(self, storage_path):
        """Test creating a workflow A/B tester."""
        from empathy_os.socratic.ab_testing import WorkflowABTester

        tester = WorkflowABTester(storage_path=storage_path / "ab_tests.json")

        assert tester is not None

    def test_create_workflow_test(self, storage_path, sample_workflow_blueprint):
        """Test creating a workflow A/B test."""
        from empathy_os.socratic.ab_testing import WorkflowABTester

        tester = WorkflowABTester(storage_path=storage_path / "ab_tests.json")

        # Create a modified blueprint as treatment
        treatment_blueprint = sample_workflow_blueprint

        experiment_id = tester.create_test(
            name="Review Workflow Test",
            control_workflow=sample_workflow_blueprint,
            treatment_workflow=treatment_blueprint,
            description="Testing enhanced review workflow",
        )

        assert experiment_id is not None

    def test_get_workflow_for_user(self, storage_path, sample_workflow_blueprint):
        """Test getting workflow for a user."""
        from empathy_os.socratic.ab_testing import WorkflowABTester

        tester = WorkflowABTester(storage_path=storage_path / "ab_tests.json")

        experiment_id = tester.create_test(
            name="Test",
            control_workflow=sample_workflow_blueprint,
            treatment_workflow=sample_workflow_blueprint,
        )

        workflow, variant_id = tester.get_workflow_for_user(
            experiment_id=experiment_id,
            user_id="user-123",
        )

        assert workflow is not None
        assert variant_id in ["control", "treatment"]

    def test_record_workflow_success(self, storage_path, sample_workflow_blueprint):
        """Test recording workflow execution success."""
        from empathy_os.socratic.ab_testing import WorkflowABTester

        tester = WorkflowABTester(storage_path=storage_path / "ab_tests.json")

        experiment_id = tester.create_test(
            name="Test",
            control_workflow=sample_workflow_blueprint,
            treatment_workflow=sample_workflow_blueprint,
        )

        workflow, variant_id = tester.get_workflow_for_user(
            experiment_id=experiment_id,
            user_id="user-123",
        )

        # Record success
        tester.record_success(
            experiment_id=experiment_id,
            variant_id=variant_id,
        )

        results = tester.get_results(experiment_id)
        assert results is not None


class TestExperimentResult:
    """Tests for ExperimentResult dataclass."""

    def test_create_result(self):
        """Test creating an experiment result."""
        from empathy_os.socratic.ab_testing import ExperimentResult

        result = ExperimentResult(
            experiment_id="exp-001",
            winner_variant_id="treatment",
            confidence_level=0.95,
            lift=0.15,
            p_value=0.03,
            recommendation="Deploy treatment variant",
        )

        assert result.winner_variant_id == "treatment"
        assert result.lift == 0.15
        assert result.p_value < 0.05
