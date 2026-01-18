"""Agent and Workflow Blueprints

Intermediate representation for generating agents and workflows.

Blueprints capture the design decisions made through Socratic questioning
before actual agent generation. This allows for:
- Review before generation
- Modification of the design
- Serialization/persistence
- Template reuse

Copyright 2026 Smart-AI-Memory
Licensed under Fair Source License 0.9
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class AgentRole(Enum):
    """Standard agent roles for team composition."""

    # Analysis agents
    ANALYZER = "analyzer"  # Examines input, identifies patterns
    REVIEWER = "reviewer"  # Evaluates quality, finds issues
    AUDITOR = "auditor"  # Deep-dive security/compliance checks

    # Action agents
    GENERATOR = "generator"  # Creates new content/code
    FIXER = "fixer"  # Applies corrections and improvements
    REFACTORER = "refactorer"  # Restructures without changing behavior

    # Coordination agents
    ORCHESTRATOR = "orchestrator"  # Coordinates other agents
    VALIDATOR = "validator"  # Verifies outputs and quality
    REPORTER = "reporter"  # Synthesizes and presents results

    # Specialized agents
    SPECIALIST = "specialist"  # Domain-specific expertise
    ASSISTANT = "assistant"  # General-purpose helper


class ToolCategory(Enum):
    """Categories of tools agents can use."""

    # Code intelligence
    CODE_ANALYSIS = "code_analysis"  # AST parsing, complexity metrics
    CODE_SEARCH = "code_search"  # Grep, file search
    CODE_MODIFICATION = "code_modification"  # Edit, write, refactor

    # Quality tools
    TESTING = "testing"  # Run tests, coverage
    LINTING = "linting"  # Static analysis
    SECURITY = "security"  # Security scanners

    # Documentation
    DOCUMENTATION = "documentation"  # Doc generation, README
    KNOWLEDGE = "knowledge"  # Pattern library, memory

    # External
    API = "api"  # External API calls
    DATABASE = "database"  # Data storage/retrieval
    FILESYSTEM = "filesystem"  # File operations


@dataclass
class ToolSpec:
    """Specification for a tool an agent can use.

    Example:
        >>> tool = ToolSpec(
        ...     id="grep_codebase",
        ...     name="Code Search",
        ...     category=ToolCategory.CODE_SEARCH,
        ...     description="Search codebase for patterns",
        ...     parameters={
        ...         "pattern": {"type": "string", "required": True},
        ...         "file_type": {"type": "string", "required": False}
        ...     }
        ... )
    """

    # Unique tool identifier
    id: str

    # Display name
    name: str

    # Tool category
    category: ToolCategory

    # Description of what the tool does
    description: str

    # Parameter schema
    parameters: dict[str, dict[str, Any]] = field(default_factory=dict)

    # Whether tool requires confirmation before use
    requires_confirmation: bool = False

    # Whether tool can modify state
    is_mutating: bool = False

    # Cost tier (for expensive operations)
    cost_tier: str = "cheap"  # cheap, moderate, expensive

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "category": self.category.value,
            "description": self.description,
            "parameters": self.parameters,
            "requires_confirmation": self.requires_confirmation,
            "is_mutating": self.is_mutating,
            "cost_tier": self.cost_tier,
        }


@dataclass
class AgentSpec:
    """Specification for a single agent.

    Example:
        >>> agent = AgentSpec(
        ...     id="security_reviewer",
        ...     name="Security Reviewer",
        ...     role=AgentRole.REVIEWER,
        ...     goal="Identify security vulnerabilities in code",
        ...     backstory="Expert in OWASP Top 10 and secure coding",
        ...     tools=[security_scan_tool, grep_tool],
        ...     quality_focus=["security"],
        ...     model_tier="capable"
        ... )
    """

    # Unique agent identifier
    id: str

    # Display name
    name: str

    # Agent's role in the team
    role: AgentRole

    # What this agent aims to achieve
    goal: str

    # Agent's expertise and personality
    backstory: str

    # Tools this agent can use
    tools: list[ToolSpec] = field(default_factory=list)

    # Quality attributes this agent focuses on
    quality_focus: list[str] = field(default_factory=list)

    # Model tier for this agent (cheap, capable, premium)
    model_tier: str = "capable"

    # Custom instructions for this agent
    custom_instructions: list[str] = field(default_factory=list)

    # Languages this agent specializes in
    languages: list[str] = field(default_factory=list)

    # Whether this agent is optional in the workflow
    is_optional: bool = False

    # Conditions for including this agent
    include_when: dict[str, Any] | None = None

    # Priority (higher = runs earlier in parallel execution)
    priority: int = 5

    # Maximum retries on failure
    max_retries: int = 2

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "role": self.role.value,
            "goal": self.goal,
            "backstory": self.backstory,
            "tools": [t.to_dict() for t in self.tools],
            "quality_focus": self.quality_focus,
            "model_tier": self.model_tier,
            "custom_instructions": self.custom_instructions,
            "languages": self.languages,
            "is_optional": self.is_optional,
            "include_when": self.include_when,
            "priority": self.priority,
            "max_retries": self.max_retries,
        }


@dataclass
class StageSpec:
    """Specification for a workflow stage.

    Stages define when and how agents execute in the workflow.
    """

    # Stage identifier
    id: str

    # Display name
    name: str

    # Description of what happens in this stage
    description: str

    # Agents that execute in this stage (can be parallel)
    agent_ids: list[str]

    # Whether agents in this stage run in parallel
    parallel: bool = False

    # Conditions for running this stage
    run_when: dict[str, Any] | None = None

    # Stage this must complete before
    depends_on: list[str] = field(default_factory=list)

    # Data passed to agents in this stage
    input_mapping: dict[str, str] = field(default_factory=dict)

    # How to combine outputs from parallel agents
    output_aggregation: str = "merge"  # merge, first, vote, custom

    # Timeout for this stage (seconds)
    timeout: int = 300

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "agent_ids": self.agent_ids,
            "parallel": self.parallel,
            "run_when": self.run_when,
            "depends_on": self.depends_on,
            "input_mapping": self.input_mapping,
            "output_aggregation": self.output_aggregation,
            "timeout": self.timeout,
        }


@dataclass
class AgentBlueprint:
    """Blueprint for generating an agent.

    Contains all information needed to instantiate an agent.
    """

    # The agent specification
    spec: AgentSpec

    # Generation metadata
    generated_from: str = "socratic"  # socratic, template, manual

    # Template ID if based on a template
    template_id: str | None = None

    # Customizations applied
    customizations: dict[str, Any] = field(default_factory=dict)

    # Validation status
    validated: bool = False

    # Validation errors if any
    validation_errors: list[str] = field(default_factory=list)

    def validate(self) -> bool:
        """Validate the blueprint.

        Returns:
            True if valid, False otherwise
        """
        self.validation_errors = []

        if not self.spec.id:
            self.validation_errors.append("Agent must have an ID")

        if not self.spec.name:
            self.validation_errors.append("Agent must have a name")

        if not self.spec.goal:
            self.validation_errors.append("Agent must have a goal")

        if not self.spec.backstory:
            self.validation_errors.append("Agent must have a backstory")

        self.validated = len(self.validation_errors) == 0
        return self.validated


@dataclass
class WorkflowBlueprint:
    """Blueprint for a complete workflow with agents.

    Example:
        >>> blueprint = WorkflowBlueprint(
        ...     id="code_review_workflow",
        ...     name="Automated Code Review",
        ...     description="Multi-agent code review pipeline",
        ...     agents=[security_agent, style_agent, complexity_agent],
        ...     stages=[analysis_stage, synthesis_stage],
        ...     success_criteria=success_spec
        ... )
    """

    # Unique workflow identifier
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    # Workflow name
    name: str = ""

    # Description of what this workflow does
    description: str = ""

    # Agent blueprints in this workflow
    agents: list[AgentBlueprint] = field(default_factory=list)

    # Stage definitions
    stages: list[StageSpec] = field(default_factory=list)

    # Success criteria specification
    success_criteria: Any = None  # SuccessCriteria, imported lazily

    # Input schema (what the workflow accepts)
    input_schema: dict[str, Any] = field(default_factory=dict)

    # Output schema (what the workflow produces)
    output_schema: dict[str, Any] = field(default_factory=dict)

    # Domain this workflow is for
    domain: str = "general"

    # Languages this workflow supports
    supported_languages: list[str] = field(default_factory=list)

    # Quality attributes this workflow optimizes for
    quality_focus: list[str] = field(default_factory=list)

    # Automation level
    automation_level: str = "semi_auto"

    # Estimated cost tier
    cost_tier: str = "moderate"

    # Version for tracking changes
    version: str = "1.0.0"

    # Generation timestamp
    generated_at: str = ""

    # Source session ID
    source_session_id: str | None = None

    # Additional metadata
    metadata: dict[str, Any] = field(default_factory=dict)

    def get_agent_by_id(self, agent_id: str) -> AgentBlueprint | None:
        """Get an agent blueprint by ID."""
        for agent in self.agents:
            if agent.spec.id == agent_id:
                return agent
        return None

    def get_stage_by_id(self, stage_id: str) -> StageSpec | None:
        """Get a stage specification by ID."""
        for stage in self.stages:
            if stage.id == stage_id:
                return stage
        return None

    def validate(self) -> tuple[bool, list[str]]:
        """Validate the entire blueprint.

        Returns:
            Tuple of (is_valid, list of error messages)
        """
        errors = []

        if not self.name:
            errors.append("Workflow must have a name")

        if not self.agents:
            errors.append("Workflow must have at least one agent")

        if not self.stages:
            errors.append("Workflow must have at least one stage")

        # Validate all agents
        for agent in self.agents:
            if not agent.validate():
                errors.extend(
                    f"Agent '{agent.spec.id}': {e}" for e in agent.validation_errors
                )

        # Validate stages reference valid agents
        agent_ids = {a.spec.id for a in self.agents}
        for stage in self.stages:
            for agent_id in stage.agent_ids:
                if agent_id not in agent_ids:
                    errors.append(
                        f"Stage '{stage.id}' references unknown agent '{agent_id}'"
                    )

        # Validate stage dependencies
        stage_ids = {s.id for s in self.stages}
        for stage in self.stages:
            for dep in stage.depends_on:
                if dep not in stage_ids:
                    errors.append(
                        f"Stage '{stage.id}' depends on unknown stage '{dep}'"
                    )

        return len(errors) == 0, errors

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "agents": [
                {
                    "spec": a.spec.to_dict(),
                    "generated_from": a.generated_from,
                    "template_id": a.template_id,
                    "customizations": a.customizations,
                }
                for a in self.agents
            ],
            "stages": [s.to_dict() for s in self.stages],
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
            "domain": self.domain,
            "supported_languages": self.supported_languages,
            "quality_focus": self.quality_focus,
            "automation_level": self.automation_level,
            "cost_tier": self.cost_tier,
            "version": self.version,
            "generated_at": self.generated_at,
            "source_session_id": self.source_session_id,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WorkflowBlueprint:
        """Deserialize from dictionary."""
        blueprint = cls(
            id=data.get("id", str(uuid.uuid4())),
            name=data.get("name", ""),
            description=data.get("description", ""),
            domain=data.get("domain", "general"),
            supported_languages=data.get("supported_languages", []),
            quality_focus=data.get("quality_focus", []),
            automation_level=data.get("automation_level", "semi_auto"),
            cost_tier=data.get("cost_tier", "moderate"),
            version=data.get("version", "1.0.0"),
            generated_at=data.get("generated_at", ""),
            source_session_id=data.get("source_session_id"),
            metadata=data.get("metadata", {}),
            input_schema=data.get("input_schema", {}),
            output_schema=data.get("output_schema", {}),
        )

        # Parse agents
        for agent_data in data.get("agents", []):
            spec_data = agent_data.get("spec", {})
            spec = AgentSpec(
                id=spec_data.get("id", ""),
                name=spec_data.get("name", ""),
                role=AgentRole(spec_data.get("role", "specialist")),
                goal=spec_data.get("goal", ""),
                backstory=spec_data.get("backstory", ""),
                quality_focus=spec_data.get("quality_focus", []),
                model_tier=spec_data.get("model_tier", "capable"),
                custom_instructions=spec_data.get("custom_instructions", []),
                languages=spec_data.get("languages", []),
                is_optional=spec_data.get("is_optional", False),
                priority=spec_data.get("priority", 5),
                max_retries=spec_data.get("max_retries", 2),
            )

            # Parse tools
            for tool_data in spec_data.get("tools", []):
                spec.tools.append(ToolSpec(
                    id=tool_data.get("id", ""),
                    name=tool_data.get("name", ""),
                    category=ToolCategory(tool_data.get("category", "code_analysis")),
                    description=tool_data.get("description", ""),
                    parameters=tool_data.get("parameters", {}),
                    requires_confirmation=tool_data.get("requires_confirmation", False),
                    is_mutating=tool_data.get("is_mutating", False),
                    cost_tier=tool_data.get("cost_tier", "cheap"),
                ))

            blueprint.agents.append(AgentBlueprint(
                spec=spec,
                generated_from=agent_data.get("generated_from", "socratic"),
                template_id=agent_data.get("template_id"),
                customizations=agent_data.get("customizations", {}),
            ))

        # Parse stages
        for stage_data in data.get("stages", []):
            blueprint.stages.append(StageSpec(
                id=stage_data.get("id", ""),
                name=stage_data.get("name", ""),
                description=stage_data.get("description", ""),
                agent_ids=stage_data.get("agent_ids", []),
                parallel=stage_data.get("parallel", False),
                run_when=stage_data.get("run_when"),
                depends_on=stage_data.get("depends_on", []),
                input_mapping=stage_data.get("input_mapping", {}),
                output_aggregation=stage_data.get("output_aggregation", "merge"),
                timeout=stage_data.get("timeout", 300),
            ))

        return blueprint
