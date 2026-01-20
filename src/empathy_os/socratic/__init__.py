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

# A/B testing
from .ab_testing import (
    AllocationStrategy,
    Experiment,
    ExperimentManager,
    ExperimentResult,
    Variant,
    WorkflowABTester,
)
from .blueprint import (
    AgentBlueprint,
    AgentMessage,
    AgentPoolConfig,
    AgentSpec,
    CommunicationPattern,
    CoordinationConfig,
    CoordinationStrategy,
    FailureHandling,
    ManagerSpec,
    MemoryConfig,
    MemoryType,
    OutputConfig,
    OutputFormat as BlueprintOutputFormat,
    TeamManagerBlueprint,
    ToolSpec,
    WorkflowBlueprint,
)

# CLI interface
from .cli import Console

# Collaboration
from .collaboration import (
    Change,
    ChangeType,
    CollaborationManager,
    CollaborativeSession,
    Comment,
    InvitationManager,
    Participant,
    ParticipantRole,
    SyncAdapter,
    Vote,
    VoteType,
    VotingResult,
)

# Domain templates
from .domain_templates import (
    AgentTemplate,
    Domain,
    DomainTemplate,
    DomainTemplateRegistry,
    WorkflowTemplate,
    get_registry,
)

# Vector embeddings for semantic matching
from .embeddings import (
    AnthropicEmbeddingProvider,
    EmbeddedGoal,
    EmbeddingProvider,
    SemanticGoalMatcher,
    SimilarityResult,
    TFIDFEmbeddingProvider,
    VectorStore,
)
from .engine import SocraticWorkflowBuilder

# Workflow explainer
from .explainer import (
    AudienceLevel,
    DetailLevel,
    Explanation,
    LLMExplanationGenerator,
    OutputFormat,
    WorkflowExplainer,
    explain_workflow,
)

# Feedback loop
from .feedback import (
    AdaptiveAgentGenerator,
    AgentPerformance,
    FeedbackCollector,
    FeedbackLoop,
    WorkflowPattern,
)
from .forms import (
    FieldType,
    Form,
    FormField,
    FormResponse,
    ValidationResult,
)
from .generator import AgentGenerator

# LLM-powered analysis
from .llm_analyzer import (
    LLMAgentRecommendation,
    LLMAnalysisResult,
    LLMGoalAnalyzer,
    LLMQuestionResult,
    llm_questions_to_form,
)

# MCP server
from .mcp_server import SOCRATIC_TOOLS, SocraticMCPServer
from .session import SessionState, SocraticSession

# Persistent storage
from .storage import (
    JSONFileStorage,
    SQLiteStorage,
    StorageBackend,
    StorageManager,
)
from .success import MetricType, SuccessCriteria, SuccessMetric

# Visual editor
from .visual_editor import (
    ASCIIVisualizer,
    EditorEdge,
    EditorNode,
    EditorState,
    VisualWorkflowEditor,
    WorkflowVisualizer,
    generate_editor_html,
    generate_react_flow_schema,
)

# Web UI components
from .web_ui import (
    ReactBlueprintSchema,
    ReactFormSchema,
    ReactSessionSchema,
    create_blueprint_response,
    create_form_response,
    render_complete_page,
    render_form_html,
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
    # Team Manager Blueprint
    "TeamManagerBlueprint",
    "ManagerSpec",
    "AgentPoolConfig",
    "CoordinationConfig",
    "CoordinationStrategy",
    "CommunicationPattern",
    "FailureHandling",
    "OutputConfig",
    "BlueprintOutputFormat",
    "MemoryConfig",
    "MemoryType",
    "AgentMessage",
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
    # MCP server
    "SocraticMCPServer",
    "SOCRATIC_TOOLS",
    # Vector embeddings
    "VectorStore",
    "SemanticGoalMatcher",
    "EmbeddingProvider",
    "TFIDFEmbeddingProvider",
    "AnthropicEmbeddingProvider",
    "EmbeddedGoal",
    "SimilarityResult",
    # A/B testing
    "ExperimentManager",
    "WorkflowABTester",
    "Experiment",
    "Variant",
    "ExperimentResult",
    "AllocationStrategy",
    # Domain templates
    "DomainTemplateRegistry",
    "Domain",
    "AgentTemplate",
    "WorkflowTemplate",
    "DomainTemplate",
    "get_registry",
    # Visual editor
    "VisualWorkflowEditor",
    "ASCIIVisualizer",
    "WorkflowVisualizer",
    "EditorState",
    "EditorNode",
    "EditorEdge",
    "generate_react_flow_schema",
    "generate_editor_html",
    # Workflow explainer
    "WorkflowExplainer",
    "LLMExplanationGenerator",
    "Explanation",
    "AudienceLevel",
    "DetailLevel",
    "OutputFormat",
    "explain_workflow",
    # Collaboration
    "CollaborationManager",
    "CollaborativeSession",
    "Participant",
    "ParticipantRole",
    "Comment",
    "Vote",
    "VoteType",
    "Change",
    "ChangeType",
    "VotingResult",
    "InvitationManager",
    "SyncAdapter",
]
