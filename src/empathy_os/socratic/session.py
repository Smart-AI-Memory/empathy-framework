"""Socratic Session Management

Tracks the state of a Socratic questioning session as it progresses
from initial goal capture through requirements refinement to generation.

Copyright 2026 Smart-AI-Memory
Licensed under Fair Source License 0.9
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class SessionState(Enum):
    """State machine for Socratic sessions."""

    # Initial state - waiting for goal
    AWAITING_GOAL = "awaiting_goal"

    # Goal received, analyzing for questions
    ANALYZING_GOAL = "analyzing_goal"

    # Questions generated, waiting for answers
    AWAITING_ANSWERS = "awaiting_answers"

    # Answers received, determining if more questions needed
    PROCESSING_ANSWERS = "processing_answers"

    # Requirements sufficient, ready to generate
    READY_TO_GENERATE = "ready_to_generate"

    # Generation in progress
    GENERATING = "generating"

    # Workflow generated successfully
    COMPLETED = "completed"

    # User cancelled or session expired
    CANCELLED = "cancelled"


@dataclass
class GoalAnalysis:
    """Analysis of the user's stated goal.

    Captures what we understand and what needs clarification.
    """

    # Original goal statement
    raw_goal: str

    # Extracted intent (what they want to achieve)
    intent: str

    # Domain detected (e.g., "code_review", "testing", "documentation")
    domain: str

    # Confidence in our understanding (0-1)
    confidence: float

    # Identified ambiguities that need clarification
    ambiguities: list[str] = field(default_factory=list)

    # Assumptions we're making (need validation)
    assumptions: list[str] = field(default_factory=list)

    # Constraints mentioned or implied
    constraints: list[str] = field(default_factory=list)

    # Keywords extracted for matching
    keywords: list[str] = field(default_factory=list)

    def needs_clarification(self) -> bool:
        """Check if goal needs more clarification."""
        return self.confidence < 0.8 or len(self.ambiguities) > 0


@dataclass
class RequirementSet:
    """Accumulated requirements from Socratic questioning."""

    # Core requirements (must have)
    must_have: list[str] = field(default_factory=list)

    # Nice to have requirements
    should_have: list[str] = field(default_factory=list)

    # Explicitly excluded requirements
    must_not_have: list[str] = field(default_factory=list)

    # Technical constraints (languages, frameworks, etc.)
    technical_constraints: dict[str, Any] = field(default_factory=dict)

    # Quality attributes (performance, security, etc.)
    quality_attributes: dict[str, float] = field(default_factory=dict)

    # Domain-specific requirements
    domain_specific: dict[str, Any] = field(default_factory=dict)

    # User preferences
    preferences: dict[str, Any] = field(default_factory=dict)

    def completeness_score(self) -> float:
        """Calculate how complete the requirements are (0-1)."""
        scores = []

        # Must have at least one core requirement
        if self.must_have:
            scores.append(1.0)
        else:
            scores.append(0.0)

        # Technical constraints help
        if self.technical_constraints:
            scores.append(min(len(self.technical_constraints) / 3, 1.0))
        else:
            scores.append(0.3)  # Can work without, but less optimal

        # Quality attributes help prioritization
        if self.quality_attributes:
            scores.append(min(len(self.quality_attributes) / 2, 1.0))
        else:
            scores.append(0.5)  # Can use defaults

        return sum(scores) / len(scores) if scores else 0.0


@dataclass
class SocraticSession:
    """A Socratic questioning session.

    Tracks the full state of a session from goal to generated workflow.
    """

    # Unique session identifier
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    # Current state in the state machine
    state: SessionState = SessionState.AWAITING_GOAL

    # When the session started
    created_at: datetime = field(default_factory=datetime.now)

    # Last activity timestamp
    updated_at: datetime = field(default_factory=datetime.now)

    # The user's original goal statement
    goal: str = ""

    # Analysis of the goal
    goal_analysis: GoalAnalysis | None = None

    # Accumulated requirements
    requirements: RequirementSet = field(default_factory=RequirementSet)

    # History of question rounds
    question_rounds: list[dict[str, Any]] = field(default_factory=list)

    # Current round number
    current_round: int = 0

    # Maximum rounds before forcing generation
    max_rounds: int = 5

    # Generated blueprint (when ready)
    blueprint: Any = None  # WorkflowBlueprint, imported lazily

    # Generated workflow (when complete)
    workflow: Any = None  # GeneratedWorkflow, imported lazily

    # Error message if something went wrong
    error: str | None = None

    # Metadata for extensibility
    metadata: dict[str, Any] = field(default_factory=dict)

    def touch(self) -> None:
        """Update the last activity timestamp."""
        self.updated_at = datetime.now()

    def is_active(self) -> bool:
        """Check if session is still active."""
        return self.state not in (SessionState.COMPLETED, SessionState.CANCELLED)

    def can_generate(self) -> bool:
        """Check if we have enough information to generate."""
        if self.goal_analysis is None:
            return False

        # Either high confidence or we've done enough rounds
        if self.goal_analysis.confidence >= 0.8:
            return True

        if self.current_round >= self.max_rounds:
            return True

        if self.requirements.completeness_score() >= 0.7:
            return True

        return False

    def add_question_round(
        self,
        questions: list[dict[str, Any]],
        answers: dict[str, Any],
    ) -> None:
        """Record a round of questions and answers."""
        self.question_rounds.append({
            "round": self.current_round,
            "questions": questions,
            "answers": answers,
            "timestamp": datetime.now().isoformat(),
        })
        self.current_round += 1
        self.touch()

    def get_context_summary(self) -> dict[str, Any]:
        """Get a summary of accumulated context for display."""
        return {
            "session_id": self.session_id,
            "state": self.state.value,
            "goal": self.goal,
            "rounds_completed": self.current_round,
            "requirements_count": len(self.requirements.must_have),
            "confidence": self.goal_analysis.confidence if self.goal_analysis else 0.0,
            "ready_to_generate": self.can_generate(),
        }

    def to_dict(self) -> dict[str, Any]:
        """Serialize session to dictionary."""
        return {
            "session_id": self.session_id,
            "state": self.state.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "goal": self.goal,
            "goal_analysis": {
                "intent": self.goal_analysis.intent,
                "domain": self.goal_analysis.domain,
                "confidence": self.goal_analysis.confidence,
                "ambiguities": self.goal_analysis.ambiguities,
                "assumptions": self.goal_analysis.assumptions,
            } if self.goal_analysis else None,
            "requirements": {
                "must_have": self.requirements.must_have,
                "should_have": self.requirements.should_have,
                "must_not_have": self.requirements.must_not_have,
                "technical_constraints": self.requirements.technical_constraints,
                "quality_attributes": self.requirements.quality_attributes,
            },
            "question_rounds": self.question_rounds,
            "current_round": self.current_round,
            "error": self.error,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SocraticSession:
        """Deserialize session from dictionary."""
        session = cls(
            session_id=data.get("session_id", str(uuid.uuid4())),
            state=SessionState(data.get("state", "awaiting_goal")),
            goal=data.get("goal", ""),
            current_round=data.get("current_round", 0),
            error=data.get("error"),
            metadata=data.get("metadata", {}),
        )

        # Parse timestamps
        if "created_at" in data:
            session.created_at = datetime.fromisoformat(data["created_at"])
        if "updated_at" in data:
            session.updated_at = datetime.fromisoformat(data["updated_at"])

        # Parse goal analysis
        if data.get("goal_analysis"):
            ga = data["goal_analysis"]
            session.goal_analysis = GoalAnalysis(
                raw_goal=session.goal,
                intent=ga.get("intent", ""),
                domain=ga.get("domain", "general"),
                confidence=ga.get("confidence", 0.0),
                ambiguities=ga.get("ambiguities", []),
                assumptions=ga.get("assumptions", []),
            )

        # Parse requirements
        if data.get("requirements"):
            req = data["requirements"]
            session.requirements = RequirementSet(
                must_have=req.get("must_have", []),
                should_have=req.get("should_have", []),
                must_not_have=req.get("must_not_have", []),
                technical_constraints=req.get("technical_constraints", {}),
                quality_attributes=req.get("quality_attributes", {}),
            )

        # Parse question rounds
        session.question_rounds = data.get("question_rounds", [])

        return session
