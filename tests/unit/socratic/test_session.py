"""Tests for the Socratic session module.

Copyright 2026 Smart-AI-Memory
Licensed under Fair Source License 0.9
"""

import pytest
from datetime import datetime


class TestSocraticSession:
    """Tests for SocraticSession class."""

    def test_create_session(self):
        """Test creating a new session."""
        from empathy_os.socratic.session import SocraticSession, SessionState

        session = SocraticSession()

        assert session.session_id is not None
        assert len(session.session_id) == 12
        assert session.state == SessionState.AWAITING_GOAL
        assert session.goal is None
        assert session.created_at is not None

    def test_create_session_with_id(self):
        """Test creating a session with specific ID."""
        from empathy_os.socratic.session import SocraticSession

        session = SocraticSession(session_id="custom-id-123")
        assert session.session_id == "custom-id-123"

    def test_session_serialization(self, sample_session):
        """Test session serialization to dict."""
        from empathy_os.socratic.session import SocraticSession

        data = sample_session.to_dict()

        assert data["session_id"] == sample_session.session_id
        assert data["goal"] == sample_session.goal
        assert data["state"] == sample_session.state.value
        assert data["answers"] == sample_session.answers

    def test_session_deserialization(self, sample_session):
        """Test session deserialization from dict."""
        from empathy_os.socratic.session import SocraticSession

        data = sample_session.to_dict()
        restored = SocraticSession.from_dict(data)

        assert restored.session_id == sample_session.session_id
        assert restored.goal == sample_session.goal
        assert restored.state == sample_session.state


class TestSessionState:
    """Tests for SessionState enum."""

    def test_state_values(self):
        """Test all state values exist."""
        from empathy_os.socratic.session import SessionState

        assert SessionState.AWAITING_GOAL.value == "awaiting_goal"
        assert SessionState.ANALYZING_GOAL.value == "analyzing_goal"
        assert SessionState.AWAITING_ANSWERS.value == "awaiting_answers"
        assert SessionState.READY_TO_GENERATE.value == "ready_to_generate"
        assert SessionState.COMPLETED.value == "completed"


class TestGoalAnalysis:
    """Tests for GoalAnalysis dataclass."""

    def test_create_goal_analysis(self):
        """Test creating a GoalAnalysis."""
        from empathy_os.socratic.session import GoalAnalysis

        analysis = GoalAnalysis(
            raw_goal="Automate code reviews",
            refined_goal="Automated code quality review for Python",
            domain="code_review",
            confidence=0.85,
            keywords=["code", "review", "python"],
            ambiguities=["Which languages?"],
        )

        assert analysis.domain == "code_review"
        assert analysis.confidence == 0.85
        assert "code" in analysis.keywords


class TestRequirementSet:
    """Tests for RequirementSet dataclass."""

    def test_create_empty_requirement_set(self):
        """Test creating an empty RequirementSet."""
        from empathy_os.socratic.session import RequirementSet

        reqs = RequirementSet()

        assert reqs.must_have == []
        assert reqs.nice_to_have == []
        assert reqs.technical_constraints == []

    def test_add_requirements(self):
        """Test adding requirements."""
        from empathy_os.socratic.session import RequirementSet

        reqs = RequirementSet(
            must_have=["Security scanning"],
            nice_to_have=["Performance analysis"],
            technical_constraints=["Python only"],
        )

        assert len(reqs.must_have) == 1
        assert "Security scanning" in reqs.must_have
