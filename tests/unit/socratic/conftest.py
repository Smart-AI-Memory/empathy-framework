"""Test fixtures and utilities for Socratic module tests.

Provides reusable fixtures, mock objects, and test helpers for
comprehensive testing of the Socratic Agent Generation System.

Copyright 2026 Smart-AI-Memory
Licensed under Fair Source License 0.9
"""

import json
import os
import tempfile
from collections.abc import Generator
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

# =============================================================================
# PATH FIXTURES
# =============================================================================


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def storage_path(temp_dir: Path) -> Path:
    """Create a storage path for tests."""
    path = temp_dir / ".empathy" / "socratic"
    path.mkdir(parents=True, exist_ok=True)
    return path


# =============================================================================
# SESSION FIXTURES
# =============================================================================


@pytest.fixture
def sample_goal() -> str:
    """Sample goal for testing."""
    return "I want to automate code reviews for my Python project"


@pytest.fixture
def sample_answers() -> dict[str, Any]:
    """Sample answers for testing."""
    return {
        "languages": ["python"],
        "quality_focus": ["security", "performance"],
        "review_depth": "standard",
        "output_format": "markdown",
    }


@pytest.fixture
def sample_session():
    """Create a sample SocraticSession for testing."""
    from empathy_os.socratic.session import SessionState, SocraticSession

    session = SocraticSession(session_id="test-session-001")
    session.goal = "Automate code reviews for Python"
    session.state = SessionState.AWAITING_ANSWERS
    session.detected_domains = {"code_review"}
    session.answers = {
        "languages": ["python"],
        "quality_focus": ["security"],
    }
    return session


@pytest.fixture
def completed_session(sample_session):
    """Create a completed session for testing."""
    from empathy_os.socratic.session import SessionState

    sample_session.state = SessionState.COMPLETED
    return sample_session


# =============================================================================
# BLUEPRINT FIXTURES
# =============================================================================


@pytest.fixture
def sample_agent_spec():
    """Create a sample AgentSpec for testing."""
    from empathy_os.socratic.blueprint import AgentRole, AgentSpec, ToolCategory, ToolSpec

    return AgentSpec(
        id="test-agent-001",
        name="Test Code Reviewer",
        role=AgentRole.REVIEWER,
        goal="Review code for quality issues",
        backstory="Expert code reviewer with 10 years of experience",
        tools=[
            ToolSpec(
                id="read_file",
                name="Read File",
                description="Read file contents",
                category=ToolCategory.CODE_ANALYSIS,
            ),
            ToolSpec(
                id="grep_code",
                name="Grep Code",
                description="Search code",
                category=ToolCategory.CODE_ANALYSIS,
            ),
        ],
    )


@pytest.fixture
def sample_workflow_blueprint(sample_agent_spec):
    """Create a sample WorkflowBlueprint for testing."""
    from empathy_os.socratic.blueprint import (
        AgentBlueprint,
        AgentRole,
        AgentSpec,
        StageSpec,
        ToolCategory,
        ToolSpec,
        WorkflowBlueprint,
    )

    synthesizer = AgentSpec(
        id="synthesizer-001",
        name="Result Synthesizer",
        role=AgentRole.ORCHESTRATOR,
        goal="Synthesize results from analysis",
        backstory="Expert at combining insights from multiple sources",
        tools=[
            ToolSpec(
                id="read_file",
                name="Read File",
                description="Read file contents",
                category=ToolCategory.CODE_ANALYSIS,
            ),
        ],
    )

    return WorkflowBlueprint(
        id="test-blueprint-001",
        name="Test Code Review Workflow",
        description="A test workflow for code reviews",
        domain="code_review",
        agents=[
            AgentBlueprint(spec=sample_agent_spec),
            AgentBlueprint(spec=synthesizer),
        ],
        stages=[
            StageSpec(
                id="analysis",
                name="Code Analysis",
                description="Analyze code for issues",
                agent_ids=[sample_agent_spec.id],
                parallel=False,
            ),
            StageSpec(
                id="synthesis",
                name="Result Synthesis",
                description="Synthesize analysis results",
                agent_ids=[synthesizer.id],
                depends_on=["analysis"],
                parallel=False,
            ),
        ],
    )


# =============================================================================
# FORM FIXTURES
# =============================================================================


@pytest.fixture
def sample_form():
    """Create a sample Form for testing."""
    from empathy_os.socratic.forms import (
        FieldOption,
        FieldType,
        FieldValidation,
        Form,
        FormField,
    )

    return Form(
        id="test-form-001",
        title="Test Questions",
        description="Test form for Socratic questioning",
        fields=[
            FormField(
                id="languages",
                field_type=FieldType.MULTI_SELECT,
                label="Programming Languages",
                options=[
                    FieldOption(value="python", label="Python"),
                    FieldOption(value="javascript", label="JavaScript"),
                    FieldOption(value="typescript", label="TypeScript"),
                ],
                validation=FieldValidation(required=True),
            ),
            FormField(
                id="quality_focus",
                field_type=FieldType.MULTI_SELECT,
                label="Quality Focus",
                options=[
                    FieldOption(value="security", label="Security"),
                    FieldOption(value="performance", label="Performance"),
                    FieldOption(value="maintainability", label="Maintainability"),
                ],
            ),
            FormField(
                id="notes",
                field_type=FieldType.TEXT_AREA,
                label="Additional Notes",
                placeholder="Any other requirements...",
            ),
        ],
        round_number=1,
        progress=0.3,
    )


# =============================================================================
# SUCCESS CRITERIA FIXTURES
# =============================================================================


@pytest.fixture
def sample_success_criteria():
    """Create sample SuccessCriteria for testing."""
    from empathy_os.socratic.success import (
        MetricDirection,
        MetricType,
        SuccessCriteria,
        SuccessMetric,
    )

    return SuccessCriteria(
        criteria_id="test-criteria-001",
        name="Code Review Success",
        description="Success criteria for code review workflow",
        metrics=[
            SuccessMetric(
                metric_id="issues_found",
                name="Issues Found",
                description="Number of issues identified",
                metric_type=MetricType.COUNT,
                direction=MetricDirection.HIGHER_IS_BETTER,
            ),
            SuccessMetric(
                metric_id="coverage",
                name="Coverage",
                description="Percentage of code reviewed",
                metric_type=MetricType.PERCENTAGE,
                target_value=80.0,
                direction=MetricDirection.HIGHER_IS_BETTER,
            ),
        ],
    )


# =============================================================================
# MOCK FIXTURES
# =============================================================================


@pytest.fixture
def mock_anthropic_client():
    """Create a mock Anthropic client."""
    mock_client = MagicMock()

    # Mock response
    mock_response = MagicMock()
    mock_response.content = [
        MagicMock(text=json.dumps({
            "intent": "Automate code reviews",
            "domain": "code_review",
            "confidence": 0.85,
            "ambiguities": ["Which languages?"],
            "assumptions": ["Python codebase"],
            "constraints": [],
            "keywords": ["code", "review", "python"],
            "suggested_agents": ["code_quality_reviewer", "security_scanner"],
            "suggested_questions": [
                {
                    "id": "q1",
                    "question": "Which programming languages?",
                    "type": "multi_select",
                    "options": ["Python", "JavaScript"],
                }
            ],
        }))
    ]

    mock_client.messages.create.return_value = mock_response
    return mock_client


@pytest.fixture
def mock_llm_executor():
    """Create a mock LLM executor."""
    mock_executor = AsyncMock()

    class MockResponse:
        content = json.dumps({
            "domain": "code_review",
            "confidence": 0.8,
        })

    mock_executor.run.return_value = MockResponse()
    return mock_executor


# =============================================================================
# COLLABORATION FIXTURES
# =============================================================================


@pytest.fixture
def sample_participant():
    """Create a sample Participant for testing."""
    from empathy_os.socratic.collaboration import Participant, ParticipantRole

    return Participant(
        user_id="user-001",
        name="Test User",
        email="test@example.com",
        role=ParticipantRole.OWNER,
    )


@pytest.fixture
def sample_collaborative_session(sample_participant, storage_path):
    """Create a sample CollaborativeSession for testing."""
    from empathy_os.socratic.collaboration import CollaborativeSession

    return CollaborativeSession(
        session_id="collab-session-001",
        base_session_id="test-session-001",
        name="Test Collaboration",
        description="A test collaborative session",
        participants=[sample_participant],
    )


# =============================================================================
# EMBEDDING FIXTURES
# =============================================================================


@pytest.fixture
def sample_embedded_goal():
    """Create a sample EmbeddedGoal for testing."""
    from empathy_os.socratic.embeddings import EmbeddedGoal

    return EmbeddedGoal(
        goal_id="goal-001",
        goal_text="Automate code reviews",
        embedding=[0.1] * 256,  # 256-dimensional embedding
        domains=["code_review"],
        workflow_id="workflow-001",
        success_score=0.85,
    )


@pytest.fixture
def vector_store(storage_path):
    """Create a VectorStore for testing."""
    from empathy_os.socratic.embeddings import TFIDFEmbeddingProvider, VectorStore

    return VectorStore(
        provider=TFIDFEmbeddingProvider(dimension=64),
        storage_path=storage_path / "embeddings.json",
    )


# =============================================================================
# EXPERIMENT FIXTURES
# =============================================================================


@pytest.fixture
def sample_experiment(storage_path):
    """Create a sample Experiment for testing."""
    from empathy_os.socratic.ab_testing import (
        AllocationStrategy,
        ExperimentManager,
    )

    manager = ExperimentManager(storage_path=storage_path / "experiments.json")

    experiment = manager.create_experiment(
        name="Test Agent Configuration",
        description="Testing different agent configurations",
        hypothesis="More agents improve quality",
        control_config={"agents": ["code_reviewer"]},
        treatment_configs=[
            {"name": "Treatment A", "config": {"agents": ["code_reviewer", "security_scanner"]}},
        ],
        allocation_strategy=AllocationStrategy.FIXED,
    )

    return experiment


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def create_test_session_with_goal(goal: str):
    """Helper to create a session with a specific goal."""
    from empathy_os.socratic.session import SessionState, SocraticSession

    session = SocraticSession()
    session.goal = goal
    session.state = SessionState.ANALYZING_GOAL
    return session


def create_mock_llm_response(content: dict[str, Any]) -> MagicMock:
    """Helper to create a mock LLM response."""
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=json.dumps(content))]
    return mock_response


# =============================================================================
# ENVIRONMENT FIXTURES
# =============================================================================


@pytest.fixture
def no_api_key():
    """Ensure no API key is set for tests."""
    original = os.environ.get("ANTHROPIC_API_KEY")
    if "ANTHROPIC_API_KEY" in os.environ:
        del os.environ["ANTHROPIC_API_KEY"]
    yield
    if original is not None:
        os.environ["ANTHROPIC_API_KEY"] = original


@pytest.fixture
def mock_api_key():
    """Set a mock API key for tests."""
    original = os.environ.get("ANTHROPIC_API_KEY")
    os.environ["ANTHROPIC_API_KEY"] = "test-api-key-not-real"
    yield
    if original is not None:
        os.environ["ANTHROPIC_API_KEY"] = original
    elif "ANTHROPIC_API_KEY" in os.environ:
        del os.environ["ANTHROPIC_API_KEY"]
