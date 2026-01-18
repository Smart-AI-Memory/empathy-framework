"""Tests for the Socratic engine module.

Copyright 2026 Smart-AI-Memory
Licensed under Fair Source License 0.9
"""

import pytest


class TestSocraticWorkflowBuilder:
    """Tests for SocraticWorkflowBuilder class."""

    def test_create_builder(self):
        """Test creating a workflow builder."""
        from empathy_os.socratic.engine import SocraticWorkflowBuilder

        builder = SocraticWorkflowBuilder()
        assert builder is not None

    def test_start_session(self):
        """Test starting a new session."""
        from empathy_os.socratic.engine import SocraticWorkflowBuilder
        from empathy_os.socratic.session import SessionState

        builder = SocraticWorkflowBuilder()
        session = builder.start_session()

        assert session is not None
        assert session.state == SessionState.AWAITING_GOAL

    def test_start_session_with_goal(self, sample_goal):
        """Test starting a session with initial goal."""
        from empathy_os.socratic.engine import SocraticWorkflowBuilder
        from empathy_os.socratic.session import SessionState

        builder = SocraticWorkflowBuilder()
        session = builder.start_session(sample_goal)

        assert session.goal == sample_goal
        assert session.state in [SessionState.ANALYZING_GOAL, SessionState.AWAITING_ANSWERS]

    def test_set_goal(self):
        """Test setting goal on existing session."""
        from empathy_os.socratic.engine import SocraticWorkflowBuilder

        builder = SocraticWorkflowBuilder()
        session = builder.start_session()

        session = builder.set_goal(session, "I want to automate testing")

        assert session.goal == "I want to automate testing"
        assert session.detected_domains is not None

    def test_detect_domains_code_review(self):
        """Test domain detection for code review."""
        from empathy_os.socratic.engine import SocraticWorkflowBuilder

        builder = SocraticWorkflowBuilder()
        domains = builder._detect_domains("I want to review code quality")

        assert "code_review" in domains

    def test_detect_domains_security(self):
        """Test domain detection for security."""
        from empathy_os.socratic.engine import SocraticWorkflowBuilder

        builder = SocraticWorkflowBuilder()
        domains = builder._detect_domains("Scan for security vulnerabilities")

        assert "security" in domains

    def test_detect_domains_testing(self):
        """Test domain detection for testing."""
        from empathy_os.socratic.engine import SocraticWorkflowBuilder

        builder = SocraticWorkflowBuilder()
        domains = builder._detect_domains("Generate unit tests for coverage")

        assert "testing" in domains

    def test_get_next_questions(self, sample_session):
        """Test getting next questions."""
        from empathy_os.socratic.engine import SocraticWorkflowBuilder
        from empathy_os.socratic.session import SessionState

        builder = SocraticWorkflowBuilder()
        sample_session.state = SessionState.AWAITING_ANSWERS

        form = builder.get_next_questions(sample_session)

        assert form is not None
        assert len(form.fields) > 0

    def test_submit_answers(self, sample_session, sample_answers):
        """Test submitting answers."""
        from empathy_os.socratic.engine import SocraticWorkflowBuilder

        builder = SocraticWorkflowBuilder()
        session = builder.submit_answers(sample_session, sample_answers)

        assert session.answers is not None
        assert "languages" in session.answers

    def test_is_ready_to_generate(self, sample_session):
        """Test checking if ready to generate."""
        from empathy_os.socratic.engine import SocraticWorkflowBuilder
        from empathy_os.socratic.session import SessionState

        builder = SocraticWorkflowBuilder()

        # Not ready in AWAITING_ANSWERS state
        sample_session.state = SessionState.AWAITING_ANSWERS
        assert not builder.is_ready_to_generate(sample_session)

        # Ready in READY_TO_GENERATE state
        sample_session.state = SessionState.READY_TO_GENERATE
        assert builder.is_ready_to_generate(sample_session)

    def test_generate_workflow(self):
        """Test generating a workflow."""
        from empathy_os.socratic.engine import SocraticWorkflowBuilder
        from empathy_os.socratic.session import SessionState

        builder = SocraticWorkflowBuilder()

        # Create a session ready for generation
        session = builder.start_session("Automate code reviews for Python")
        session = builder.submit_answers(session, {
            "languages": ["python"],
            "quality_focus": ["security", "maintainability"],
        })
        session.state = SessionState.READY_TO_GENERATE

        workflow = builder.generate_workflow(session)

        assert workflow is not None
        assert workflow.blueprint is not None
        assert len(workflow.blueprint.agents) > 0


class TestDomainDetection:
    """Tests for domain detection functionality."""

    @pytest.mark.parametrize("goal,expected_domain", [
        ("Review my code for bugs", "code_review"),
        ("Check for security vulnerabilities", "security"),
        ("Generate unit tests", "testing"),
        ("Write documentation", "documentation"),
        ("Optimize performance", "performance"),
        ("Refactor this module", "refactoring"),
    ])
    def test_domain_detection_keywords(self, goal, expected_domain):
        """Test domain detection with various keywords."""
        from empathy_os.socratic.engine import SocraticWorkflowBuilder

        builder = SocraticWorkflowBuilder()
        domains = builder._detect_domains(goal)

        assert expected_domain in domains


class TestQuestionGeneration:
    """Tests for question generation."""

    def test_generate_initial_questions(self):
        """Test generating initial questions."""
        from empathy_os.socratic.engine import SocraticWorkflowBuilder

        builder = SocraticWorkflowBuilder()
        session = builder.start_session("Code review automation")

        form = builder.generate_initial_questions(session)

        assert form is not None
        assert form.round_number == 1

    def test_generate_followup_questions(self, sample_session):
        """Test generating follow-up questions."""
        from empathy_os.socratic.engine import SocraticWorkflowBuilder

        builder = SocraticWorkflowBuilder()
        sample_session.answers = {"languages": ["python"]}

        form = builder.generate_followup_questions(sample_session, round_number=2)

        # May or may not have follow-up questions depending on answers
        # Just verify it doesn't error
        assert form is None or hasattr(form, 'fields')
