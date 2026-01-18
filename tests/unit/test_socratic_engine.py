"""Tests for Socratic Agent Generation System

Copyright 2026 Smart-AI-Memory
Licensed under Fair Source License 0.9
"""

import pytest

from empathy_os.socratic import (
    SocraticWorkflowBuilder,
    SocraticSession,
    SessionState,
    Form,
    FormField,
    FieldType,
    FieldValidation,
    FormResponse,
    AgentBlueprint,
    AgentSpec,
    WorkflowBlueprint,
    SuccessCriteria,
    SuccessMetric,
    MetricType,
)
from empathy_os.socratic.engine import detect_domain, extract_keywords, identify_ambiguities
from empathy_os.socratic.generator import AgentGenerator, AGENT_TEMPLATES
from empathy_os.socratic.session import GoalAnalysis, RequirementSet


class TestDomainDetection:
    """Tests for domain detection from goals."""

    def test_detect_code_review_domain(self):
        """Test detection of code review domain."""
        goal = "I want to automate code reviews for my team"
        domain, confidence = detect_domain(goal)

        assert domain == "code_review"
        assert confidence > 0.5

    def test_detect_security_domain(self):
        """Test detection of security domain."""
        goal = "Find security vulnerabilities in my codebase"
        domain, confidence = detect_domain(goal)

        assert domain == "security"
        assert confidence > 0.5

    def test_detect_testing_domain(self):
        """Test detection of testing domain."""
        goal = "Generate unit tests to increase coverage"
        domain, confidence = detect_domain(goal)

        assert domain == "testing"
        assert confidence > 0.5

    def test_detect_general_domain(self):
        """Test fallback to general domain."""
        goal = "Help me with my project"
        domain, confidence = detect_domain(goal)

        assert domain == "general"
        assert confidence == 0.5

    def test_keyword_extraction(self):
        """Test keyword extraction from goals."""
        goal = "I want to automate security reviews for Python code"
        keywords = extract_keywords(goal)

        assert "automate" in keywords
        assert "security" in keywords
        assert "python" in keywords
        # Stop words should be filtered
        assert "want" not in keywords
        assert "for" not in keywords


class TestGoalAnalysis:
    """Tests for goal analysis."""

    def test_identify_ambiguities_missing_language(self):
        """Test ambiguity detection for missing language."""
        goal = "Review my code for issues"
        ambiguities = identify_ambiguities(goal, "code_review")

        assert any("language" in a.lower() for a in ambiguities)

    def test_identify_ambiguities_vague_terms(self):
        """Test ambiguity detection for vague terms."""
        goal = "Review some of my code files"
        ambiguities = identify_ambiguities(goal, "code_review")

        assert any("vague" in a.lower() for a in ambiguities)

    def test_no_ambiguities_with_specifics(self):
        """Test that specific goals have fewer ambiguities."""
        goal = "Security review my Python authentication module"
        ambiguities = identify_ambiguities(goal, "security")

        # Should have fewer ambiguities when language is specified
        language_ambiguity = [a for a in ambiguities if "language" in a.lower()]
        assert len(language_ambiguity) == 0


class TestFormSystem:
    """Tests for the form/questionnaire system."""

    def test_form_field_validation_required(self):
        """Test required field validation."""
        field = FormField(
            id="test",
            field_type=FieldType.TEXT,
            label="Test Field",
            validation=FieldValidation(required=True),
        )

        # Empty value should fail
        is_valid, error = field.validate("")
        assert not is_valid
        assert "required" in error.lower()

        # Non-empty value should pass
        is_valid, error = field.validate("hello")
        assert is_valid
        assert error == ""

    def test_form_field_validation_length(self):
        """Test min/max length validation."""
        field = FormField(
            id="test",
            field_type=FieldType.TEXT,
            label="Test Field",
            validation=FieldValidation(min_length=5, max_length=10),
        )

        # Too short
        is_valid, error = field.validate("hi")
        assert not is_valid

        # Too long
        is_valid, error = field.validate("this is way too long")
        assert not is_valid

        # Just right
        is_valid, error = field.validate("perfect")
        assert is_valid

    def test_form_field_conditional_show(self):
        """Test conditional field visibility."""
        field = FormField(
            id="security_details",
            field_type=FieldType.TEXT,
            label="Security Details",
            show_when={"quality_focus": "security"},
        )

        # Should show when condition met
        assert field.should_show({"quality_focus": "security"})

        # Should hide when condition not met
        assert not field.should_show({"quality_focus": "performance"})

    def test_form_response_validation(self):
        """Test form response validation."""
        form = Form(
            id="test_form",
            title="Test Form",
            fields=[
                FormField(
                    id="required_field",
                    field_type=FieldType.TEXT,
                    label="Required",
                    validation=FieldValidation(required=True),
                ),
                FormField(
                    id="optional_field",
                    field_type=FieldType.TEXT,
                    label="Optional",
                ),
            ],
        )

        # Missing required field
        response = FormResponse(
            form_id="test_form",
            answers={"optional_field": "value"},
        )
        result = response.validate(form)
        assert not result.is_valid
        assert "required_field" in result.field_errors

        # All fields provided
        response = FormResponse(
            form_id="test_form",
            answers={
                "required_field": "value",
                "optional_field": "value",
            },
        )
        result = response.validate(form)
        assert result.is_valid


class TestSocraticSession:
    """Tests for Socratic session management."""

    def test_session_creation(self):
        """Test session creation with defaults."""
        session = SocraticSession()

        assert session.session_id is not None
        assert session.state == SessionState.AWAITING_GOAL
        assert session.current_round == 0
        assert session.is_active()

    def test_session_can_generate(self):
        """Test session readiness for generation."""
        session = SocraticSession()

        # Without goal analysis, cannot generate
        assert not session.can_generate()

        # With high confidence, can generate
        session.goal_analysis = GoalAnalysis(
            raw_goal="test",
            intent="test",
            domain="code_review",
            confidence=0.9,
        )
        assert session.can_generate()

    def test_session_serialization(self):
        """Test session serialization and deserialization."""
        session = SocraticSession(
            goal="Test goal",
            current_round=2,
        )
        session.goal_analysis = GoalAnalysis(
            raw_goal="Test goal",
            intent="testing",
            domain="testing",
            confidence=0.8,
        )
        session.requirements.must_have = ["requirement 1"]

        # Serialize
        data = session.to_dict()

        # Deserialize
        restored = SocraticSession.from_dict(data)

        assert restored.goal == session.goal
        assert restored.current_round == session.current_round
        assert restored.goal_analysis is not None
        assert restored.goal_analysis.domain == "testing"


class TestAgentGenerator:
    """Tests for agent generation."""

    def test_generate_from_template(self):
        """Test generating agent from template."""
        generator = AgentGenerator()

        agent = generator.generate_agent_from_template(
            "security_reviewer",
            customizations={"languages": ["python"]},
        )

        assert agent.spec.name == "Security Reviewer"
        assert "python" in agent.spec.languages
        assert agent.template_id == "security_reviewer"

    def test_generate_from_unknown_template(self):
        """Test error on unknown template."""
        generator = AgentGenerator()

        with pytest.raises(ValueError, match="Unknown template"):
            generator.generate_agent_from_template("nonexistent")

    def test_generate_agents_for_requirements(self):
        """Test generating appropriate agents for requirements."""
        generator = AgentGenerator()

        agents = generator.generate_agents_for_requirements({
            "quality_focus": ["security", "performance"],
            "languages": ["python"],
            "automation_level": "semi_auto",
        })

        # Should have security and performance agents
        agent_ids = [a.spec.id for a in agents]
        assert "security_reviewer" in agent_ids
        assert "performance_analyzer" in agent_ids

    def test_create_workflow_blueprint(self):
        """Test workflow blueprint creation."""
        generator = AgentGenerator()

        agents = generator.generate_agents_for_requirements({
            "quality_focus": ["security"],
            "languages": ["python"],
        })

        blueprint = generator.create_workflow_blueprint(
            name="Test Workflow",
            description="Test description",
            agents=agents,
            quality_focus=["security"],
            automation_level="semi_auto",
        )

        assert blueprint.name == "Test Workflow"
        assert len(blueprint.agents) > 0
        assert len(blueprint.stages) > 0


class TestSuccessCriteria:
    """Tests for success criteria evaluation."""

    def test_metric_evaluation_count(self):
        """Test count metric evaluation."""
        metric = SuccessMetric(
            id="issues_found",
            name="Issues Found",
            metric_type=MetricType.COUNT,
            minimum_value=5,
        )

        # Below minimum
        met, score, _ = metric.evaluate(3)
        assert not met
        assert score < 1.0

        # At minimum
        met, score, _ = metric.evaluate(5)
        assert met
        assert score == 1.0

        # Above minimum
        met, score, _ = metric.evaluate(10)
        assert met

    def test_metric_evaluation_percentage(self):
        """Test percentage metric evaluation."""
        metric = SuccessMetric(
            id="coverage",
            name="Coverage",
            metric_type=MetricType.PERCENTAGE,
            minimum_value=80,
        )

        # Below minimum
        met, score, _ = metric.evaluate(70)
        assert not met

        # At minimum
        met, score, _ = metric.evaluate(80)
        assert met

    def test_success_criteria_evaluation(self):
        """Test full success criteria evaluation."""
        criteria = SuccessCriteria(
            id="test",
            name="Test Criteria",
            metrics=[
                SuccessMetric(
                    id="count",
                    name="Count",
                    metric_type=MetricType.COUNT,
                    minimum_value=5,
                    is_primary=True,
                    extraction_path="count",
                ),
                SuccessMetric(
                    id="completed",
                    name="Completed",
                    metric_type=MetricType.BOOLEAN,
                    extraction_path="completed",
                ),
            ],
            success_threshold=0.7,
        )

        # Evaluate passing case
        result = criteria.evaluate({
            "count": 10,
            "completed": True,
        })

        assert result.overall_success
        assert result.overall_score >= 0.7

        # Evaluate failing case
        result = criteria.evaluate({
            "count": 2,
            "completed": False,
        })

        assert not result.overall_success


class TestSocraticWorkflowBuilder:
    """Integration tests for the Socratic workflow builder."""

    def test_full_flow(self):
        """Test complete flow from goal to workflow."""
        builder = SocraticWorkflowBuilder()

        # Start session
        session = builder.start_session()
        assert session.state == SessionState.AWAITING_GOAL

        # Set goal
        session = builder.set_goal(
            session,
            "I want to automate security code reviews for Python",
        )
        assert session.state == SessionState.AWAITING_ANSWERS
        assert session.goal_analysis is not None
        assert session.goal_analysis.domain == "security"

        # Get questions
        form = builder.get_next_questions(session)
        assert form is not None
        assert len(form.fields) > 0

        # Submit answers
        session = builder.submit_answers(session, {
            "languages": ["python"],
            "quality_focus": ["security"],
            "automation_level": "semi_auto",
        })

        # Should be ready to generate
        assert builder.is_ready_to_generate(session)

        # Generate workflow
        workflow = builder.generate_workflow(session)
        assert workflow is not None
        assert len(workflow.agents) > 0
        assert session.state == SessionState.COMPLETED

    def test_session_persistence(self):
        """Test that sessions are persisted and retrievable."""
        builder = SocraticWorkflowBuilder()

        session = builder.start_session("Test goal")
        session_id = session.session_id

        # Should be retrievable
        retrieved = builder.get_session(session_id)
        assert retrieved is not None
        assert retrieved.goal == "Test goal"

    def test_get_session_summary(self):
        """Test session summary generation."""
        builder = SocraticWorkflowBuilder()
        session = builder.start_session("Security review my Python code")

        summary = builder.get_session_summary(session)

        assert "session_id" in summary
        assert "state" in summary
        assert "domain" in summary
        assert summary["domain"] == "security"


class TestWorkflowBlueprint:
    """Tests for workflow blueprint."""

    def test_blueprint_validation(self):
        """Test blueprint validation."""
        from empathy_os.socratic.blueprint import AgentRole, StageSpec

        # Valid blueprint
        blueprint = WorkflowBlueprint(
            name="Test",
            agents=[
                AgentBlueprint(
                    spec=AgentSpec(
                        id="agent1",
                        name="Agent 1",
                        role=AgentRole.ANALYZER,
                        goal="Test goal",
                        backstory="Test backstory",
                    )
                )
            ],
            stages=[
                StageSpec(
                    id="stage1",
                    name="Stage 1",
                    description="Test stage",
                    agent_ids=["agent1"],
                )
            ],
        )

        is_valid, errors = blueprint.validate()
        assert is_valid
        assert len(errors) == 0

        # Invalid - missing agent reference
        blueprint.stages[0].agent_ids = ["nonexistent"]
        is_valid, errors = blueprint.validate()
        assert not is_valid
        assert any("unknown agent" in e.lower() for e in errors)

    def test_blueprint_serialization(self):
        """Test blueprint serialization."""
        from empathy_os.socratic.blueprint import AgentRole, StageSpec

        blueprint = WorkflowBlueprint(
            name="Test Workflow",
            description="Test description",
            agents=[
                AgentBlueprint(
                    spec=AgentSpec(
                        id="agent1",
                        name="Agent 1",
                        role=AgentRole.ANALYZER,
                        goal="Test goal",
                        backstory="Test backstory",
                    )
                )
            ],
            stages=[
                StageSpec(
                    id="stage1",
                    name="Stage 1",
                    description="Test",
                    agent_ids=["agent1"],
                )
            ],
        )

        # Serialize
        data = blueprint.to_dict()
        assert data["name"] == "Test Workflow"
        assert len(data["agents"]) == 1

        # Deserialize
        restored = WorkflowBlueprint.from_dict(data)
        assert restored.name == blueprint.name
        assert len(restored.agents) == 1
        assert restored.agents[0].spec.id == "agent1"
