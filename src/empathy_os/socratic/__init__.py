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

# LLM-powered analysis
from .llm_analyzer import (
    LLMGoalAnalyzer,
    LLMAnalysisResult,
    LLMQuestionResult,
    LLMAgentRecommendation,
    llm_questions_to_form,
)

# Persistent storage
from .storage import (
    StorageBackend,
    JSONFileStorage,
    SQLiteStorage,
    StorageManager,
)

# CLI interface
from .cli import SocraticCLI, Console

# Web UI components
from .web_ui import (
    ReactFormSchema,
    ReactSessionSchema,
    ReactBlueprintSchema,
    render_form_html,
    render_complete_page,
    create_form_response,
    create_blueprint_response,
)

# Feedback loop
from .feedback import (
    FeedbackLoop,
    FeedbackCollector,
    AdaptiveAgentGenerator,
    AgentPerformance,
    WorkflowPattern,
)

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
    # LLM-powered analysis
    "LLMGoalAnalyzer",
    "LLMAnalysisResult",
    "LLMQuestionResult",
    "LLMAgentRecommendation",
    "llm_questions_to_form",
    # Persistent storage
    "StorageBackend",
    "JSONFileStorage",
    "SQLiteStorage",
    "StorageManager",
    # CLI interface
    "SocraticCLI",
    "Console",
    # Web UI components
    "ReactFormSchema",
    "ReactSessionSchema",
    "ReactBlueprintSchema",
    "render_form_html",
    "render_complete_page",
    "create_form_response",
    "create_blueprint_response",
    # Feedback loop
    "FeedbackLoop",
    "FeedbackCollector",
    "AdaptiveAgentGenerator",
    "AgentPerformance",
    "WorkflowPattern",
]
