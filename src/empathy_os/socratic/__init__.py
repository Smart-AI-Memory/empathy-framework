"""Socratic Agent Generation System

Generate optimized agent workflows through guided questioning.

This module provides a Socratic approach to agent generation where:
1. User provides a free-form goal
2. System asks clarifying questions to understand requirements
3. Agents and workflows are generated based on refined understanding
4. Success criteria are defined for measuring completion

Example:
    >>> from empathy_os.socratic import SocraticWorkflowBuilder
    >>>
    >>> builder = SocraticWorkflowBuilder()
    >>> session = builder.start_session("I want to automate code reviews")
    >>>
    >>> # Get clarifying questions
    >>> form = builder.get_next_questions(session)
    >>> print(form.questions[0].text)
    "What programming languages does your team primarily use?"
    >>>
    >>> # Answer questions
    >>> session = builder.submit_answers(session, {
    ...     "languages": ["python", "typescript"],
    ...     "focus_areas": ["security", "performance"]
    ... })
    >>>
    >>> # Generate workflow when ready
    >>> if builder.is_ready_to_generate(session):
    ...     workflow = builder.generate_workflow(session)
    ...     print(f"Generated {len(workflow.agents)} agents")

Copyright 2026 Smart-AI-Memory
Licensed under Fair Source License 0.9
"""

from .engine import SocraticWorkflowBuilder
from .forms import (
    Form,
    FormField,
    FieldType,
    FormResponse,
    ValidationResult,
)
from .blueprint import (
    AgentBlueprint,
    AgentSpec,
    WorkflowBlueprint,
    ToolSpec,
)
from .generator import AgentGenerator
from .success import SuccessCriteria, SuccessMetric, MetricType
from .session import SocraticSession, SessionState

__all__ = [
    # Core engine
    "SocraticWorkflowBuilder",
    # Forms
    "Form",
    "FormField",
    "FieldType",
    "FormResponse",
    "ValidationResult",
    # Blueprints
    "AgentBlueprint",
    "AgentSpec",
    "WorkflowBlueprint",
    "ToolSpec",
    # Generation
    "AgentGenerator",
    # Success measurement
    "SuccessCriteria",
    "SuccessMetric",
    "MetricType",
    # Session
    "SocraticSession",
    "SessionState",
]
