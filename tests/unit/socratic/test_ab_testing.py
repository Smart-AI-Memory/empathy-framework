"""Tests for the Socratic A/B testing module.

Copyright 2026 Smart-AI-Memory
Licensed under Fair Source License 0.9
"""



class TestExperiment:
    """Tests for Experiment dataclass."""

    def test_create_experiment(self):
        """Test creating an experiment with required fields."""
        from empathy_os.socratic.ab_testing import (
            AllocationStrategy,
            Experiment,
            ExperimentStatus,
            Variant,
        )

        # Create variants first (required)
        control = Variant(
            variant_id="control",
            name="Control",
            description="Control variant",
            config={"agents": ["code_reviewer"]},
            is_control=True,
        )
        treatment = Variant(
            variant_id="treatment",
            name="Treatment",
            description="Treatment variant",
            config={"agents": ["code_reviewer", "security_scanner"]},
        )

        experiment = Experiment(
            experiment_id="exp-001",
            name="Test Experiment",
            description="Testing workflow variations",
            hypothesis="More agents improve quality",
            variants=[control, treatment],
        )

        assert experiment.experiment_id == "exp-001"
        assert experiment.name == "Test Experiment"
        assert experiment.allocation_strategy == AllocationStrategy.FIXED
        assert experiment.status == ExperimentStatus.DRAFT
        assert len(experiment.variants) == 2

    def test_experiment_with_custom_allocation(self):
        """Test experiment with custom allocation strategy."""
        from empathy_os.socratic.ab_testing import (
            AllocationStrategy,
            Experiment,
            Variant,
        )

        variant = Variant(
            variant_id="control",
            name="Control",
            description="Control",
            config={},
            is_control=True,
        )

        experiment = Experiment(
            experiment_id="exp-002",
            name="Thompson Sampling Test",
            description="Testing Thompson sampling",
            hypothesis="Thompson sampling improves allocation",
            variants=[variant],
            allocation_strategy=AllocationStrategy.THOMPSON_SAMPLING,
        )

        assert experiment.allocation_strategy == AllocationStrategy.THOMPSON_SAMPLING


class TestVariant:
    """Tests for Variant dataclass."""

    def test_create_variant(self):
        """Test creating a variant."""
        from empathy_os.socratic.ab_testing import Variant

        variant = Variant(
            variant_id="var-001",
            name="Control",
            description="Control variant for testing",
            config={"agents": ["code_reviewer"]},
            traffic_percentage=50.0,
        )

        assert variant.variant_id == "var-001"
        assert variant.traffic_percentage == 50.0
        assert variant.impressions == 0
        assert variant.conversions == 0

    def test_variant_conversion_rate(self):
        """Test variant conversion rate calculation."""
        from empathy_os.socratic.ab_testing import Variant

        variant = Variant(
            variant_id="var-001",
            name="Test",
            description="Test variant",
            config={},
        )
        variant.impressions = 100
        variant.conversions = 25

        assert variant.conversion_rate == 0.25

    def test_variant_zero_impressions(self):
        """Test conversion rate with zero impressions."""
        from empathy_os.socratic.ab_testing import Variant

        variant = Variant(
            variant_id="var-001",
            name="Test",
            description="Test variant",
            config={},
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


class TestExperimentStatus:
    """Tests for ExperimentStatus enum."""

    def test_all_statuses_exist(self):
        """Test all experiment statuses exist."""
        from empathy_os.socratic.ab_testing import ExperimentStatus

        assert ExperimentStatus.DRAFT.value == "draft"
        assert ExperimentStatus.RUNNING.value == "running"
        assert ExperimentStatus.PAUSED.value == "paused"
        assert ExperimentStatus.COMPLETED.value == "completed"
        assert ExperimentStatus.STOPPED.value == "stopped"


class TestExperimentManager:
    """Tests for ExperimentManager class."""

    def test_create_manager(self, storage_path):
        """Test creating an experiment manager."""
        from empathy_os.socratic.ab_testing import ExperimentManager

        manager = ExperimentManager(storage_path=storage_path / "experiments.json")

        assert manager is not None

    def test_create_experiment(self, storage_path):
        """Test creating an experiment via manager."""
        from empathy_os.socratic.ab_testing import ExperimentManager

        manager = ExperimentManager(storage_path=storage_path / "experiments.json")

        experiment = manager.create_experiment(
            name="Code Review Test",
            description="Testing different code review workflows",
            hypothesis="More agents improve review quality",
            control_config={"agents": ["code_reviewer"]},
            treatment_configs=[
                {"name": "Treatment A", "config": {"agents": ["code_reviewer", "security_scanner"]}},
            ],
        )

        assert experiment.experiment_id is not None
        assert len(experiment.variants) == 2  # control + 1 treatment

    def test_get_experiment(self, storage_path):
        """Test retrieving an experiment."""
        from empathy_os.socratic.ab_testing import ExperimentManager

        manager = ExperimentManager(storage_path=storage_path / "experiments.json")

        created = manager.create_experiment(
            name="Test",
            description="Test experiment",
            hypothesis="Test hypothesis",
            control_config={"agents": []},
            treatment_configs=[{"name": "T1", "config": {"agents": ["agent1"]}}],
        )

        retrieved = manager.get_experiment(created.experiment_id)

        assert retrieved is not None
        assert retrieved.experiment_id == created.experiment_id


class TestStatisticalAnalyzer:
    """Tests for StatisticalAnalyzer class."""

    def test_z_test_proportions(self):
        """Test z-test for proportions returns tuple."""
        from empathy_os.socratic.ab_testing import StatisticalAnalyzer

        # Control: 100/1000 = 10% conversion
        # Treatment: 150/1000 = 15% conversion
        z_score, p_value = StatisticalAnalyzer.z_test_proportions(
            n1=1000,
            c1=100,
            n2=1000,
            c2=150,
        )

        assert isinstance(z_score, float)
        assert isinstance(p_value, float)
        assert p_value >= 0.0 and p_value <= 1.0

    def test_confidence_interval(self):
        """Test Wilson score confidence interval."""
        from empathy_os.socratic.ab_testing import StatisticalAnalyzer

        lower, upper = StatisticalAnalyzer.confidence_interval(
            n=1000,
            successes=100,
            confidence=0.95,
        )

        # 10% conversion rate, interval should contain it
        assert lower < 0.10 < upper
        assert lower > 0
        assert upper < 1

    def test_t_test_means(self):
        """Test t-test for means."""
        from empathy_os.socratic.ab_testing import StatisticalAnalyzer

        t_score, p_value = StatisticalAnalyzer.t_test_means(
            n1=100,
            mean1=10.0,
            var1=2.0,
            n2=100,
            mean2=12.0,
            var2=2.5,
        )

        assert isinstance(t_score, float)
        assert isinstance(p_value, float)


class TestWorkflowABTester:
    """Tests for WorkflowABTester class."""

    def test_create_tester(self, storage_path):
        """Test creating a workflow A/B tester."""
        from empathy_os.socratic.ab_testing import WorkflowABTester

        tester = WorkflowABTester(storage_path=storage_path / "ab_tests.json")

        assert tester is not None

    def test_create_workflow_experiment(self, storage_path):
        """Test creating a workflow A/B experiment."""
        from empathy_os.socratic.ab_testing import WorkflowABTester

        tester = WorkflowABTester(storage_path=storage_path / "ab_tests.json")

        experiment_id = tester.create_workflow_experiment(
            name="Review Workflow Test",
            hypothesis="More agents improve quality",
            control_agents=["code_reviewer"],
            treatment_agents_list=[
                ["code_reviewer", "security_scanner"],
            ],
            domain="code_review",
        )

        assert experiment_id is not None


class TestExperimentResult:
    """Tests for ExperimentResult dataclass."""

    def test_create_result(self):
        """Test creating an experiment result."""
        from empathy_os.socratic.ab_testing import (
            Experiment,
            ExperimentResult,
            Variant,
        )

        # Create experiment and variants first
        control = Variant(
            variant_id="control",
            name="Control",
            description="Control",
            config={},
            is_control=True,
        )
        treatment = Variant(
            variant_id="treatment",
            name="Treatment",
            description="Treatment",
            config={},
        )

        experiment = Experiment(
            experiment_id="exp-001",
            name="Test",
            description="Test",
            hypothesis="Test hypothesis",
            variants=[control, treatment],
        )

        result = ExperimentResult(
            experiment=experiment,
            winner=treatment,
            is_significant=True,
            p_value=0.03,
            confidence_interval=(0.10, 0.20),
            lift=0.15,
            recommendation="Deploy treatment variant",
        )

        assert result.winner.variant_id == "treatment"
        assert result.lift == 0.15
        assert result.p_value < 0.05
        assert result.is_significant is True
