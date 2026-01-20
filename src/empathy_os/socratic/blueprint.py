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
    RESEARCHER = "researcher"  # Gathers information and context

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


# =============================================================================
# TEAM MANAGER BLUEPRINT
# =============================================================================


class CoordinationStrategy(Enum):
    """Coordination strategies for team managers."""

    SEQUENTIAL_PIPELINE = "sequential_pipeline"  # Each output feeds the next
    PARALLEL_FAN_OUT = "parallel_fan_out"  # Run simultaneously, merge results
    ADAPTIVE = "adaptive"  # Manager decides based on task complexity
    HIERARCHICAL = "hierarchical"  # Sub-managers for complex subtasks


class CommunicationPattern(Enum):
    """Communication patterns between agents."""

    SHARED_CONTEXT = "shared_context"  # All agents read shared context
    MESSAGE_PASSING = "message_passing"  # Explicit messages between agents
    BLACKBOARD = "blackboard"  # Central knowledge store
    DIRECT_HANDOFF = "direct_handoff"  # Output becomes next input


class FailureHandling(Enum):
    """Failure handling strategies."""

    RETRY_SAME = "retry_same"  # Retry with same agent
    FALLBACK_DIFFERENT = "fallback_different"  # Try alternative agent
    ESCALATE_HUMAN = "escalate_human"  # Pause and ask user
    SKIP_CONTINUE = "skip_continue"  # Log failure and continue


class OutputFormat(Enum):
    """Output format options."""

    STRUCTURED_JSON = "structured_json"
    MARKDOWN_REPORT = "markdown_report"
    CODE_CHANGES = "code_changes"
    MIXED = "mixed"


class MemoryType(Enum):
    """Memory types for team managers."""

    NONE = "none"
    SESSION = "session"
    PERSISTENT = "persistent"
    FULL = "full"


@dataclass
class AgentPoolConfig:
    """Configuration for the agent pool managed by the team manager."""

    # Agent types available to spawn
    available_types: list[str] = field(default_factory=list)

    # How agents are spawned based on coordination strategy
    spawn_strategy: CoordinationStrategy = CoordinationStrategy.SEQUENTIAL_PIPELINE

    # Maximum concurrent agents
    max_concurrent: int = 3

    # Model tier preferences by agent type
    tier_preferences: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "available_types": self.available_types,
            "spawn_strategy": self.spawn_strategy.value,
            "max_concurrent": self.max_concurrent,
            "tier_preferences": self.tier_preferences,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentPoolConfig:
        """Deserialize from dictionary."""
        return cls(
            available_types=data.get("available_types", []),
            spawn_strategy=CoordinationStrategy(
                data.get("spawn_strategy", "sequential_pipeline")
            ),
            max_concurrent=data.get("max_concurrent", 3),
            tier_preferences=data.get("tier_preferences", {}),
        )


@dataclass
class CoordinationConfig:
    """Configuration for agent coordination."""

    # Overall coordination strategy
    strategy: CoordinationStrategy = CoordinationStrategy.SEQUENTIAL_PIPELINE

    # How agents communicate
    communication: CommunicationPattern = CommunicationPattern.SHARED_CONTEXT

    # How failures are handled
    failure_handling: FailureHandling = FailureHandling.RETRY_SAME

    # Maximum retries before escalation
    max_retries: int = 3

    # Timeout for individual agents (seconds)
    agent_timeout: int = 300

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "strategy": self.strategy.value,
            "communication": self.communication.value,
            "failure_handling": self.failure_handling.value,
            "max_retries": self.max_retries,
            "agent_timeout": self.agent_timeout,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CoordinationConfig:
        """Deserialize from dictionary."""
        return cls(
            strategy=CoordinationStrategy(
                data.get("strategy", "sequential_pipeline")
            ),
            communication=CommunicationPattern(
                data.get("communication", "shared_context")
            ),
            failure_handling=FailureHandling(
                data.get("failure_handling", "retry_same")
            ),
            max_retries=data.get("max_retries", 3),
            agent_timeout=data.get("agent_timeout", 300),
        )


@dataclass
class OutputConfig:
    """Configuration for team output."""

    # Output format
    format: OutputFormat = OutputFormat.STRUCTURED_JSON

    # Include execution metadata in output
    include_metadata: bool = True

    # Include individual agent logs
    include_agent_logs: bool = False

    # Custom output schema (JSON Schema)
    custom_schema: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "format": self.format.value,
            "include_metadata": self.include_metadata,
            "include_agent_logs": self.include_agent_logs,
            "custom_schema": self.custom_schema,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OutputConfig:
        """Deserialize from dictionary."""
        return cls(
            format=OutputFormat(data.get("format", "structured_json")),
            include_metadata=data.get("include_metadata", True),
            include_agent_logs=data.get("include_agent_logs", False),
            custom_schema=data.get("custom_schema"),
        )


@dataclass
class MemoryConfig:
    """Configuration for team manager memory."""

    # Whether memory is enabled
    enabled: bool = False

    # Memory type
    memory_type: MemoryType = MemoryType.NONE

    # Patterns to store
    store_patterns: list[str] = field(default_factory=lambda: ["success", "failure"])

    # Keywords to search for relevant history
    search_keywords: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "enabled": self.enabled,
            "type": self.memory_type.value,
            "store_patterns": self.store_patterns,
            "search_keywords": self.search_keywords,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MemoryConfig:
        """Deserialize from dictionary."""
        return cls(
            enabled=data.get("enabled", False),
            memory_type=MemoryType(data.get("type", "none")),
            store_patterns=data.get("store_patterns", ["success", "failure"]),
            search_keywords=data.get("search_keywords", []),
        )


@dataclass
class ManagerSpec:
    """Specification for the team manager agent itself."""

    # Manager role (always orchestrator)
    role: str = "orchestrator"

    # Model tier for the manager
    model_tier: str = "capable"

    # Manager's goal
    goal: str = "Coordinate sub-agents to accomplish complex tasks efficiently"

    # Manager's backstory/expertise
    backstory: str = (
        "Expert team coordinator skilled in task decomposition, "
        "delegation, and result synthesis."
    )

    # Manager capabilities
    capabilities: list[str] = field(
        default_factory=lambda: [
            "task_decomposition",
            "agent_spawning",
            "result_aggregation",
            "failure_handling",
        ]
    )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "role": self.role,
            "model_tier": self.model_tier,
            "goal": self.goal,
            "backstory": self.backstory,
            "capabilities": self.capabilities,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ManagerSpec:
        """Deserialize from dictionary."""
        return cls(
            role=data.get("role", "orchestrator"),
            model_tier=data.get("model_tier", "capable"),
            goal=data.get("goal", ""),
            backstory=data.get("backstory", ""),
            capabilities=data.get("capabilities", []),
        )


@dataclass
class TeamManagerBlueprint:
    """Blueprint for a Team Management Agent.

    A Team Manager is an orchestrator agent that dynamically spawns and
    coordinates sub-agents to accomplish complex tasks. Unlike static
    WorkflowBlueprint which defines fixed agents and stages, TeamManagerBlueprint
    defines the manager's capabilities and the pool of agents it can spawn.

    Example:
        >>> blueprint = TeamManagerBlueprint(
        ...     id="code-quality-manager",
        ...     name="Code Quality Manager",
        ...     mission="code_quality_pipeline",
        ...     manager=ManagerSpec(
        ...         goal="Ensure code quality through comprehensive review"
        ...     ),
        ...     agent_pool=AgentPoolConfig(
        ...         available_types=["analyzer", "reviewer", "generator"]
        ...     ),
        ...     coordination=CoordinationConfig(
        ...         strategy=CoordinationStrategy.SEQUENTIAL_PIPELINE
        ...     )
        ... )
        >>> json_output = blueprint.to_dict()
    """

    # Unique identifier
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    # Display name
    name: str = ""

    # Version for tracking changes
    version: str = "1.0.0"

    # Team mission (from wizard selection)
    mission: str = ""

    # Manager agent specification
    manager: ManagerSpec = field(default_factory=ManagerSpec)

    # Agent pool configuration
    agent_pool: AgentPoolConfig = field(default_factory=AgentPoolConfig)

    # Coordination configuration
    coordination: CoordinationConfig = field(default_factory=CoordinationConfig)

    # Output configuration
    output: OutputConfig = field(default_factory=OutputConfig)

    # Memory configuration
    memory: MemoryConfig = field(default_factory=MemoryConfig)

    # Generation timestamp
    generated_at: str = ""

    # Source session ID (from Socratic wizard)
    source_session_id: str | None = None

    # Additional metadata
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary (JSON-compatible).

        Returns:
            Dictionary representation suitable for JSON serialization.

        Example:
            >>> blueprint = TeamManagerBlueprint(name="Test Manager")
            >>> data = blueprint.to_dict()
            >>> import json
            >>> json_str = json.dumps(data, indent=2)
        """
        return {
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "mission": self.mission,
            "manager": self.manager.to_dict(),
            "agent_pool": self.agent_pool.to_dict(),
            "coordination": self.coordination.to_dict(),
            "output": self.output.to_dict(),
            "memory": self.memory.to_dict(),
            "generated_at": self.generated_at,
            "source_session_id": self.source_session_id,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TeamManagerBlueprint:
        """Deserialize from dictionary.

        Args:
            data: Dictionary containing blueprint data.

        Returns:
            TeamManagerBlueprint instance.

        Example:
            >>> data = {"name": "Test Manager", "mission": "code_quality"}
            >>> blueprint = TeamManagerBlueprint.from_dict(data)
        """
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            name=data.get("name", ""),
            version=data.get("version", "1.0.0"),
            mission=data.get("mission", ""),
            manager=ManagerSpec.from_dict(data.get("manager", {})),
            agent_pool=AgentPoolConfig.from_dict(data.get("agent_pool", {})),
            coordination=CoordinationConfig.from_dict(data.get("coordination", {})),
            output=OutputConfig.from_dict(data.get("output", {})),
            memory=MemoryConfig.from_dict(data.get("memory", {})),
            generated_at=data.get("generated_at", ""),
            source_session_id=data.get("source_session_id"),
            metadata=data.get("metadata", {}),
        )

    def validate(self) -> tuple[bool, list[str]]:
        """Validate the blueprint.

        Returns:
            Tuple of (is_valid, list of error messages).
        """
        errors = []

        if not self.name:
            errors.append("Team manager must have a name")

        if not self.mission:
            errors.append("Team manager must have a mission")

        if not self.agent_pool.available_types:
            errors.append("Agent pool must have at least one agent type")

        if self.agent_pool.max_concurrent < 1:
            errors.append("Max concurrent agents must be at least 1")

        return len(errors) == 0, errors

    def to_skill_file(self) -> str:
        """Generate a Claude Code skill file from this blueprint.

        Returns:
            Markdown content for .claude/commands/[name].md file.
        """
        from datetime import datetime

        # Generate skill name from blueprint name
        skill_name = self.name.lower().replace(" ", "-").replace("_", "-")

        # Build agent pool description
        agent_types = ", ".join(self.agent_pool.available_types) or "general"

        # Strategy description
        strategy_descriptions = {
            CoordinationStrategy.SEQUENTIAL_PIPELINE: "Sequential Pipeline - each agent's output feeds the next",
            CoordinationStrategy.PARALLEL_FAN_OUT: "Parallel Fan-Out - run agents simultaneously and merge",
            CoordinationStrategy.ADAPTIVE: "Adaptive - strategy chosen based on task complexity",
            CoordinationStrategy.HIERARCHICAL: "Hierarchical - sub-managers for complex subtasks",
        }
        strategy_desc = strategy_descriptions.get(
            self.coordination.strategy,
            self.coordination.strategy.value
        )

        content = f"""# {self.name}

{self.manager.goal}

**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}
**Version:** {self.version}

## What This Does

Orchestrates a team of specialized agents to accomplish: **{self.mission}**

- **Manager**: Coordinates all sub-agents and synthesizes results
- **Agent Pool**: {agent_types}
- **Strategy**: {strategy_desc}

## Usage

/{skill_name} [task description]

## Instructions for Claude

When the user invokes /{skill_name}, act as the Team Manager agent.

### Phase 1: Task Analysis

1. Analyze the user's request
2. Decompose into subtasks
3. Identify which agent types are needed: {agent_types}
4. Create a task plan

### Phase 2: Agent Execution

Strategy: **{self.coordination.strategy.value}**

Execute subtasks using the Task tool with appropriate subagent_type.
Communication: {self.coordination.communication.value}
Failure handling: {self.coordination.failure_handling.value}

### Phase 3: Result Aggregation

Output format: **{self.output.format.value}**

Collect all agent outputs and synthesize into final result.

## Cost

**$0** - Runs entirely within Claude Code using your Max subscription.
"""

        if self.memory.enabled:
            content += f"""
## Memory Integration

Memory type: {self.memory.memory_type.value}

Store execution patterns for future reference.
"""

        return content


# Inter-agent message format for structured communication
@dataclass
class AgentMessage:
    """Standardized message format for inter-agent communication.

    Used by team managers to route messages between agents.

    Example:
        >>> msg = AgentMessage(
        ...     from_agent="analyzer_1",
        ...     to_agent="manager",
        ...     message_type="result",
        ...     content={"summary": "Found 3 issues", "data": [...]}
        ... )
        >>> json_msg = msg.to_dict()
    """

    # Sender agent ID
    from_agent: str

    # Recipient agent ID (or "manager")
    to_agent: str

    # Message type
    message_type: str  # result, request, error, status

    # Message content
    content: dict[str, Any]

    # Confidence level (0-1)
    confidence: float = 1.0

    # Timestamp (ISO format)
    timestamp: str = ""

    # Execution ID for tracking
    execution_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        from datetime import datetime

        return {
            "from_agent": self.from_agent,
            "to_agent": self.to_agent,
            "message_type": self.message_type,
            "content": self.content,
            "metadata": {
                "confidence": self.confidence,
                "timestamp": self.timestamp or datetime.now().isoformat(),
                "execution_id": self.execution_id,
            },
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentMessage:
        """Deserialize from dictionary."""
        metadata = data.get("metadata", {})
        return cls(
            from_agent=data.get("from_agent", ""),
            to_agent=data.get("to_agent", ""),
            message_type=data.get("message_type", ""),
            content=data.get("content", {}),
            confidence=metadata.get("confidence", 1.0),
            timestamp=metadata.get("timestamp", ""),
            execution_id=metadata.get("execution_id", ""),
        )
