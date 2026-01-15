"""Multi-Model Workflow Templates for Empathy Framework

Cost-optimized workflow patterns that leverage 3-tier model routing:
- Haiku (cheap): Summarization, classification, triage
- Sonnet (capable): Analysis, code generation, security review
- Opus (premium): Synthesis, architectural decisions, coordination

Usage:
    from empathy_os.workflows import ResearchSynthesisWorkflow

    workflow = ResearchSynthesisWorkflow()
    result = await workflow.execute(
        sources=["doc1.md", "doc2.md"],
        question="What are the key patterns?"
    )

    print(f"Cost: ${result.cost_report.total_cost:.4f}")
    print(f"Saved: {result.cost_report.savings_percent:.1f}% vs premium-only")

Workflow Discovery:
    Workflows can be discovered via entry points (pyproject.toml):

    [project.entry-points."empathy.workflows"]
    my-workflow = "my_package.workflows:MyWorkflow"

    Then call discover_workflows() to load all registered workflows.

Copyright 2025 Smart-AI-Memory
Licensed under Fair Source License 0.9
"""

import importlib.metadata
import importlib.util
import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .base import BaseWorkflow

from .base import (
    PROVIDER_MODELS,
    BaseWorkflow,
    CostReport,
    ModelProvider,
    ModelTier,
    WorkflowResult,
    WorkflowStage,
    get_workflow_stats,
)

# New high-value workflows
from .bug_predict import BugPredictionWorkflow
from .code_review import CodeReviewWorkflow

# Code review crew integration (v3.1)
from .code_review_pipeline import CodeReviewPipeline, CodeReviewPipelineResult
from .config import DEFAULT_MODELS, ModelConfig, WorkflowConfig, create_example_config, get_model
from .dependency_check import DependencyCheckWorkflow
from .document_gen import DocumentGenerationWorkflow

# User-generated workflows
from .document_manager import DocumentManagerWorkflow
from .documentation_orchestrator import DocumentationOrchestrator, OrchestratorResult
from .health_check import HealthCheckWorkflow
from .health_check_crew import HealthCheckCrew, HealthCheckCrewResult

# Keyboard Conductor (v3.6) - keyboard shortcut generation
from .keyboard_shortcuts import KeyboardShortcutWorkflow
from .manage_documentation import ManageDocumentationCrew, ManageDocumentationCrewResult

# Meta-orchestration workflows (v4.0)
from .orchestrated_health_check import HealthCheckReport, OrchestratedHealthCheckWorkflow
from .orchestrated_release_prep import OrchestratedReleasePrepWorkflow, ReleaseReadinessReport
from .perf_audit import PerformanceAuditWorkflow
from .pr_review import PRReviewResult, PRReviewWorkflow
from .refactor_plan import RefactorPlanWorkflow
from .release_prep import ReleasePreparationWorkflow

# CrewAI-based crews (working replacements for broken orchestrator)
from .release_prep_crew import ReleasePreparationCrew, ReleasePreparationCrewResult
from .research_synthesis import ResearchSynthesisWorkflow

# Security crew integration (v3.0)
from .secure_release import SecureReleasePipeline, SecureReleaseResult
from .security_audit import SecurityAuditWorkflow
from .step_config import WorkflowStepConfig, steps_from_tier_map, validate_step_config
from .test5 import Test5Workflow
from .test_gen import TestGenerationWorkflow

# Re-export CLI commands from workflow_commands.py
_parent_dir = os.path.dirname(os.path.dirname(__file__))
_workflows_module_path = os.path.join(_parent_dir, "workflow_commands.py")

# Initialize to None for type checking
cmd_morning = None
cmd_ship = None
cmd_fix_all = None
cmd_learn = None

if os.path.exists(_workflows_module_path):
    _spec = importlib.util.spec_from_file_location("_workflows_cli", _workflows_module_path)
    if _spec is not None and _spec.loader is not None:
        _workflows_cli = importlib.util.module_from_spec(_spec)
        _spec.loader.exec_module(_workflows_cli)

        # Re-export CLI commands
        cmd_morning = _workflows_cli.cmd_morning
        cmd_ship = _workflows_cli.cmd_ship
        cmd_fix_all = _workflows_cli.cmd_fix_all
        cmd_learn = _workflows_cli.cmd_learn

# Default workflow registry (statically defined for backwards compatibility)
# Note: Some entries are composite pipelines, not direct BaseWorkflow subclasses
_DEFAULT_WORKFLOWS: dict[str, type] = {
    # Core workflows
    "code-review": CodeReviewWorkflow,
    "doc-gen": DocumentGenerationWorkflow,
    # Analysis workflows
    "bug-predict": BugPredictionWorkflow,
    "security-audit": SecurityAuditWorkflow,
    "perf-audit": PerformanceAuditWorkflow,
    # Generation workflows
    "test-gen": TestGenerationWorkflow,  # Enabled by default for test coverage
    "refactor-plan": RefactorPlanWorkflow,
    # Operational workflows
    "dependency-check": DependencyCheckWorkflow,
    "release-prep-legacy": ReleasePreparationWorkflow,  # Old single-agent version
    # Composite security pipeline (v3.0)
    "secure-release": SecureReleasePipeline,
    # Code review crew integration (v3.1)
    "pro-review": CodeReviewPipeline,
    "pr-review": PRReviewWorkflow,
    # Health check crew integration (v3.1)
    "health-check-legacy": HealthCheckWorkflow,  # Old single-agent version
    # Documentation management (v3.5)
    "doc-orchestrator": DocumentationOrchestrator,
    "manage-docs": ManageDocumentationCrew,
    # Keyboard Conductor (v3.6) - keyboard shortcut generation
    "keyboard-shortcuts": KeyboardShortcutWorkflow,
    # User-generated workflows
    "document-manager": DocumentManagerWorkflow,
    "test5": Test5Workflow,
    # CrewAI-based multi-agent workflows (v4.0.0 - production ready)
    "health-check": HealthCheckCrew,  # Multi-agent health check (3-6 agents)
    "release-prep": ReleasePreparationCrew,  # Multi-agent release validation (4 agents)
    # Meta-orchestration workflows (v4.0.0 - production ready with real analysis tools)
    "orchestrated-health-check": OrchestratedHealthCheckWorkflow,  # Real security/coverage/quality analysis
    "orchestrated-release-prep": OrchestratedReleasePrepWorkflow,  # Real quality gate validation
    # Experimental aliases (backward compat)
    "orchestrated-health-check-experimental": OrchestratedHealthCheckWorkflow,  # ALIAS
    "orchestrated-release-prep-experimental": OrchestratedReleasePrepWorkflow,  # ALIAS
}

# Opt-in workflows - not included by default, must be explicitly enabled
# Currently empty - all workflows are enabled by default
# Use disabled_workflows in config to turn off specific workflows
_OPT_IN_WORKFLOWS: dict[str, type] = {}

# Workflow registry populated at module load
WORKFLOW_REGISTRY: dict[str, type[BaseWorkflow]] = {}


def discover_workflows(
    include_defaults: bool = True,
    config: "WorkflowConfig | None" = None,
) -> dict[str, type[BaseWorkflow]]:
    """Discover workflows via entry points and config.

    This function loads workflows registered as entry points under the
    'empathy.workflows' group. This allows third-party packages to register
    custom workflows that integrate with the Empathy Framework.

    Workflow availability is controlled by:
    1. Default workflows (always included unless disabled)
    2. Opt-in workflows (test-gen) - must be explicitly enabled OR compliance_mode=hipaa
    3. enabled_workflows config - explicitly enable specific workflows
    4. disabled_workflows config - explicitly disable specific workflows
    5. Entry point discovery - third-party workflows

    Args:
        include_defaults: Whether to include default built-in workflows
        config: Optional WorkflowConfig for enabled/disabled workflows

    Returns:
        Dictionary mapping workflow names to workflow classes

    Example:
        # In your pyproject.toml:
        [project.entry-points."empathy.workflows"]
        my-workflow = "my_package.workflows:MyCustomWorkflow"

        # In your code:
        from empathy_os.workflows import discover_workflows
        workflows = discover_workflows()
        MyWorkflow = workflows.get("my-workflow")

        # With HIPAA mode (enables test-gen):
        config = WorkflowConfig.load()  # compliance_mode: hipaa
        workflows = discover_workflows(config=config)

    """
    discovered: dict[str, type[BaseWorkflow]] = {}

    # Include default workflows if requested
    if include_defaults:
        discovered.update(_DEFAULT_WORKFLOWS)

    # Add opt-in workflows based on config
    if config is not None:
        # HIPAA mode auto-enables healthcare workflows
        if config.is_hipaa_mode():
            discovered.update(_OPT_IN_WORKFLOWS)

        # Explicitly enabled workflows
        for workflow_name in config.enabled_workflows:
            if workflow_name in _OPT_IN_WORKFLOWS:
                discovered[workflow_name] = _OPT_IN_WORKFLOWS[workflow_name]

        # Explicitly disabled workflows
        for workflow_name in config.disabled_workflows:
            discovered.pop(workflow_name, None)

    # Discover via entry points
    try:
        eps = importlib.metadata.entry_points(group="empathy.workflows")
        for ep in eps:
            try:
                workflow_cls = ep.load()
                # Validate it's a proper workflow class
                if isinstance(workflow_cls, type) and hasattr(workflow_cls, "execute"):
                    # Check if disabled in config
                    if config is None or ep.name not in config.disabled_workflows:
                        discovered[ep.name] = workflow_cls
            except Exception:
                # Skip invalid entry points silently
                pass
    except Exception:
        # If entry point discovery fails, just use defaults
        pass

    return discovered


def refresh_workflow_registry(config: "WorkflowConfig | None" = None) -> None:
    """Refresh the global WORKFLOW_REGISTRY by re-discovering all workflows.

    Call this after installing new packages that register workflows,
    or after changing the WorkflowConfig (e.g., enabling HIPAA mode).

    Args:
        config: Optional WorkflowConfig for enabled/disabled workflows

    """
    global WORKFLOW_REGISTRY
    WORKFLOW_REGISTRY.clear()
    WORKFLOW_REGISTRY.update(discover_workflows(config=config))


def get_opt_in_workflows() -> dict[str, type]:
    """Get the list of opt-in workflows that require explicit enabling.

    Returns:
        Dictionary of workflow name to class for opt-in workflows

    """
    return dict(_OPT_IN_WORKFLOWS)


# Initialize registry on module load
WORKFLOW_REGISTRY.update(discover_workflows())


def get_workflow(name: str) -> type[BaseWorkflow]:
    """Get a workflow class by name.

    Args:
        name: Workflow name (e.g., "research", "code-review", "doc-gen")

    Returns:
        Workflow class

    Raises:
        KeyError: If workflow not found

    """
    if name not in WORKFLOW_REGISTRY:
        available = ", ".join(WORKFLOW_REGISTRY.keys())
        raise KeyError(f"Unknown workflow: {name}. Available: {available}")
    return WORKFLOW_REGISTRY[name]


def list_workflows() -> list[dict]:
    """List all available workflows with descriptions.

    Returns:
        List of workflow info dicts

    """
    workflows = []
    for name, cls in WORKFLOW_REGISTRY.items():
        # Handle both BaseWorkflow subclasses and composite pipelines
        stages = getattr(cls, "stages", [])
        tier_map = getattr(cls, "tier_map", {})
        description = getattr(cls, "description", "No description")

        workflows.append(
            {
                "name": name,
                "class": cls.__name__,
                "description": description,
                "stages": stages,
                "tier_map": {k: v.value for k, v in tier_map.items()} if tier_map else {},
            },
        )
    return workflows


__all__ = [
    "DEFAULT_MODELS",
    "PROVIDER_MODELS",
    # Registry and discovery
    "WORKFLOW_REGISTRY",
    # Base classes
    "BaseWorkflow",
    # New high-value workflows
    "BugPredictionWorkflow",
    # Code review crew integration (v3.1)
    "CodeReviewPipeline",
    "CodeReviewPipelineResult",
    "CodeReviewWorkflow",
    "CostReport",
    "DependencyCheckWorkflow",
    "DocumentGenerationWorkflow",
    "DocumentManagerWorkflow",
    # Documentation management (v3.5)
    "DocumentationOrchestrator",
    # Health check crew integration (v3.1)
    "HealthCheckWorkflow",
    "HealthCheckReport",
    # Keyboard Conductor (v3.6)
    "KeyboardShortcutWorkflow",
    "ManageDocumentationCrew",
    "ManageDocumentationCrewResult",
    "ModelConfig",
    "ModelProvider",
    "ModelTier",
    "OrchestratorResult",
    "PRReviewResult",
    "PRReviewWorkflow",
    "PerformanceAuditWorkflow",
    "RefactorPlanWorkflow",
    "ReleasePreparationWorkflow",
    # Workflow implementations
    "ResearchSynthesisWorkflow",
    # Security crew integration (v3.0)
    "SecureReleasePipeline",
    "SecureReleaseResult",
    "SecurityAuditWorkflow",
    "TestGenerationWorkflow",
    # Configuration
    "WorkflowConfig",
    "WorkflowResult",
    "WorkflowStage",
    # Step configuration (new)
    "WorkflowStepConfig",
    "cmd_fix_all",
    "cmd_learn",
    # CLI commands (re-exported from workflow_commands.py)
    "cmd_morning",
    "cmd_ship",
    "create_example_config",
    "discover_workflows",
    "get_model",
    "get_workflow",
    # Stats for dashboard
    "get_workflow_stats",
    "list_workflows",
    "refresh_workflow_registry",
    "steps_from_tier_map",
    "validate_step_config",
    # CrewAI-based multi-agent workflows (v4.0.0)
    "HealthCheckCrew",
    "HealthCheckCrewResult",
    "ReleasePreparationCrew",
    "ReleasePreparationCrewResult",
    # Meta-orchestration workflows (v4.0)
    "OrchestratedHealthCheckWorkflow",
    "OrchestratedReleasePrepWorkflow",
    "HealthCheckReport",
    "ReleaseReadinessReport",
]
