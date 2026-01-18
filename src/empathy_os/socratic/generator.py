"""Agent and Workflow Generator

Generates concrete agents and workflows from blueprints.

This module transforms abstract blueprints (from Socratic questioning)
into runnable agent instances and workflow configurations.

Copyright 2026 Smart-AI-Memory
Licensed under Fair Source License 0.9
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any

from .blueprint import (
    AgentBlueprint,
    AgentRole,
    AgentSpec,
    StageSpec,
    ToolCategory,
    ToolSpec,
    WorkflowBlueprint,
)
from .success import SuccessCriteria

if TYPE_CHECKING:
    from ..workflows.xml_enhanced_crew import XMLAgent

logger = logging.getLogger(__name__)


# =============================================================================
# AGENT TEMPLATES
# =============================================================================


@dataclass
class AgentTemplate:
    """Template for generating specialized agents.

    Templates provide pre-configured agent specifications that can be
    customized based on Socratic questioning results.
    """

    id: str
    name: str
    role: AgentRole
    base_goal: str
    base_backstory: str
    default_tools: list[str]
    quality_focus: list[str]
    languages: list[str]  # Empty = all languages
    model_tier: str = "capable"
    custom_instructions: list[str] = field(default_factory=list)

    def create_spec(
        self,
        customizations: dict[str, Any] | None = None,
    ) -> AgentSpec:
        """Create an AgentSpec from this template.

        Args:
            customizations: Override template defaults

        Returns:
            AgentSpec with customizations applied
        """
        customizations = customizations or {}

        # Build goal with customizations
        goal = customizations.get("goal", self.base_goal)
        if "goal_suffix" in customizations:
            goal = f"{goal} {customizations['goal_suffix']}"

        # Build backstory with customizations
        backstory = customizations.get("backstory", self.base_backstory)
        if "expertise" in customizations:
            backstory = f"{backstory} Specialized in: {', '.join(customizations['expertise'])}."

        # Merge languages
        languages = customizations.get("languages", self.languages)

        # Merge quality focus
        quality = list(self.quality_focus)
        if "quality_focus" in customizations:
            quality.extend(customizations["quality_focus"])
            quality = list(dict.fromkeys(quality))  # Dedupe preserving order

        # Build tools
        tools = self._build_tools(customizations.get("tools", []))

        return AgentSpec(
            id=customizations.get("id", self.id),
            name=customizations.get("name", self.name),
            role=self.role,
            goal=goal,
            backstory=backstory,
            tools=tools,
            quality_focus=quality,
            model_tier=customizations.get("model_tier", self.model_tier),
            custom_instructions=self.custom_instructions + customizations.get("instructions", []),
            languages=languages,
        )

    def _build_tools(self, additional_tools: list[str]) -> list[ToolSpec]:
        """Build tool specifications."""
        tools = []
        all_tool_ids = list(dict.fromkeys(self.default_tools + additional_tools))

        for tool_id in all_tool_ids:
            tool_spec = TOOL_REGISTRY.get(tool_id)
            if tool_spec:
                tools.append(tool_spec)

        return tools


# =============================================================================
# TOOL REGISTRY
# =============================================================================


TOOL_REGISTRY: dict[str, ToolSpec] = {
    "grep_code": ToolSpec(
        id="grep_code",
        name="Code Search",
        category=ToolCategory.CODE_SEARCH,
        description="Search codebase for patterns using regex",
        parameters={
            "pattern": {"type": "string", "required": True},
            "file_glob": {"type": "string", "required": False},
            "case_sensitive": {"type": "boolean", "default": False},
        },
    ),
    "read_file": ToolSpec(
        id="read_file",
        name="Read File",
        category=ToolCategory.CODE_ANALYSIS,
        description="Read file contents",
        parameters={
            "path": {"type": "string", "required": True},
            "start_line": {"type": "integer", "required": False},
            "end_line": {"type": "integer", "required": False},
        },
    ),
    "analyze_ast": ToolSpec(
        id="analyze_ast",
        name="AST Analysis",
        category=ToolCategory.CODE_ANALYSIS,
        description="Parse and analyze code abstract syntax tree",
        parameters={
            "code": {"type": "string", "required": True},
            "language": {"type": "string", "required": True},
        },
    ),
    "security_scan": ToolSpec(
        id="security_scan",
        name="Security Scanner",
        category=ToolCategory.SECURITY,
        description="Run security vulnerability scanner",
        parameters={
            "path": {"type": "string", "required": True},
            "rules": {"type": "array", "required": False},
        },
        cost_tier="moderate",
    ),
    "run_linter": ToolSpec(
        id="run_linter",
        name="Run Linter",
        category=ToolCategory.LINTING,
        description="Run code linter and return issues",
        parameters={
            "path": {"type": "string", "required": True},
            "config": {"type": "string", "required": False},
        },
    ),
    "run_tests": ToolSpec(
        id="run_tests",
        name="Run Tests",
        category=ToolCategory.TESTING,
        description="Execute test suite and return results",
        parameters={
            "path": {"type": "string", "required": False},
            "coverage": {"type": "boolean", "default": True},
        },
        cost_tier="moderate",
    ),
    "edit_file": ToolSpec(
        id="edit_file",
        name="Edit File",
        category=ToolCategory.CODE_MODIFICATION,
        description="Make targeted edits to a file",
        parameters={
            "path": {"type": "string", "required": True},
            "old_text": {"type": "string", "required": True},
            "new_text": {"type": "string", "required": True},
        },
        is_mutating=True,
        requires_confirmation=True,
    ),
    "query_patterns": ToolSpec(
        id="query_patterns",
        name="Query Pattern Library",
        category=ToolCategory.KNOWLEDGE,
        description="Search learned patterns for similar issues",
        parameters={
            "query": {"type": "string", "required": True},
            "limit": {"type": "integer", "default": 5},
        },
    ),
    "complexity_analysis": ToolSpec(
        id="complexity_analysis",
        name="Complexity Analysis",
        category=ToolCategory.CODE_ANALYSIS,
        description="Calculate code complexity metrics",
        parameters={
            "path": {"type": "string", "required": True},
        },
    ),
}


# =============================================================================
# AGENT TEMPLATE REGISTRY
# =============================================================================


AGENT_TEMPLATES: dict[str, AgentTemplate] = {
    "security_reviewer": AgentTemplate(
        id="security_reviewer",
        name="Security Reviewer",
        role=AgentRole.AUDITOR,
        base_goal="Identify security vulnerabilities and recommend mitigations",
        base_backstory=(
            "Expert security analyst with deep knowledge of OWASP Top 10, "
            "secure coding practices, and common vulnerability patterns."
        ),
        default_tools=["grep_code", "read_file", "security_scan", "query_patterns"],
        quality_focus=["security"],
        languages=[],
        model_tier="capable",
        custom_instructions=[
            "Prioritize critical and high severity issues",
            "Provide specific code locations for each finding",
            "Include remediation recommendations",
        ],
    ),
    "code_quality_reviewer": AgentTemplate(
        id="code_quality_reviewer",
        name="Code Quality Reviewer",
        role=AgentRole.REVIEWER,
        base_goal="Assess code quality, maintainability, and adherence to best practices",
        base_backstory=(
            "Experienced code reviewer with expertise in clean code principles, "
            "design patterns, and maintainability best practices."
        ),
        default_tools=["grep_code", "read_file", "run_linter", "complexity_analysis"],
        quality_focus=["maintainability", "reliability"],
        languages=[],
        model_tier="capable",
    ),
    "performance_analyzer": AgentTemplate(
        id="performance_analyzer",
        name="Performance Analyzer",
        role=AgentRole.ANALYZER,
        base_goal="Identify performance bottlenecks and optimization opportunities",
        base_backstory=(
            "Performance optimization specialist with expertise in algorithmic "
            "complexity, memory management, and scalability patterns."
        ),
        default_tools=["grep_code", "read_file", "complexity_analysis", "analyze_ast"],
        quality_focus=["performance"],
        languages=[],
        model_tier="capable",
    ),
    "test_generator": AgentTemplate(
        id="test_generator",
        name="Test Generator",
        role=AgentRole.GENERATOR,
        base_goal="Generate comprehensive test cases for untested code",
        base_backstory=(
            "Testing expert skilled in unit testing, integration testing, "
            "and test-driven development methodologies."
        ),
        default_tools=["read_file", "analyze_ast", "run_tests", "edit_file"],
        quality_focus=["testability", "reliability"],
        languages=[],
        model_tier="capable",
        custom_instructions=[
            "Generate both happy path and edge case tests",
            "Follow the existing test patterns in the codebase",
            "Ensure tests are deterministic and isolated",
        ],
    ),
    "documentation_writer": AgentTemplate(
        id="documentation_writer",
        name="Documentation Writer",
        role=AgentRole.GENERATOR,
        base_goal="Generate clear, comprehensive documentation",
        base_backstory=(
            "Technical writer with expertise in API documentation, "
            "code comments, and developer guides."
        ),
        default_tools=["read_file", "analyze_ast", "grep_code"],
        quality_focus=["maintainability"],
        languages=[],
        model_tier="cheap",
    ),
    "style_enforcer": AgentTemplate(
        id="style_enforcer",
        name="Style Enforcer",
        role=AgentRole.REVIEWER,
        base_goal="Ensure code follows team style guidelines",
        base_backstory=(
            "Code style expert with knowledge of language-specific "
            "conventions and formatting standards."
        ),
        default_tools=["run_linter", "read_file"],
        quality_focus=["maintainability"],
        languages=[],
        model_tier="cheap",
    ),
    "result_synthesizer": AgentTemplate(
        id="result_synthesizer",
        name="Result Synthesizer",
        role=AgentRole.REPORTER,
        base_goal="Synthesize findings into clear, actionable reports",
        base_backstory=(
            "Technical communicator skilled at translating complex "
            "findings into understandable recommendations."
        ),
        default_tools=["query_patterns"],
        quality_focus=[],
        languages=[],
        model_tier="cheap",
    ),
}


# =============================================================================
# AGENT GENERATOR
# =============================================================================


class AgentGenerator:
    """Generates agents and workflows from blueprints.

    Example:
        >>> generator = AgentGenerator()
        >>>
        >>> # Generate from blueprint
        >>> blueprint = WorkflowBlueprint(...)
        >>> workflow = generator.generate_workflow(blueprint)
        >>>
        >>> # Generate from template
        >>> agent = generator.generate_agent_from_template(
        ...     "security_reviewer",
        ...     customizations={"languages": ["python"]}
        ... )
    """

    def __init__(self):
        """Initialize the generator."""
        self.templates = AGENT_TEMPLATES.copy()
        self.tools = TOOL_REGISTRY.copy()

    def register_template(self, template: AgentTemplate) -> None:
        """Register a custom agent template."""
        self.templates[template.id] = template

    def register_tool(self, tool: ToolSpec) -> None:
        """Register a custom tool."""
        self.tools[tool.id] = tool

    def generate_agent_from_template(
        self,
        template_id: str,
        customizations: dict[str, Any] | None = None,
    ) -> AgentBlueprint:
        """Generate an agent blueprint from a template.

        Args:
            template_id: ID of the template to use
            customizations: Override template defaults

        Returns:
            AgentBlueprint ready for instantiation

        Raises:
            ValueError: If template not found
        """
        template = self.templates.get(template_id)
        if not template:
            raise ValueError(f"Unknown template: {template_id}")

        spec = template.create_spec(customizations)

        return AgentBlueprint(
            spec=spec,
            generated_from="template",
            template_id=template_id,
            customizations=customizations or {},
        )

    def generate_agents_for_requirements(
        self,
        requirements: dict[str, Any],
    ) -> list[AgentBlueprint]:
        """Generate appropriate agents based on requirements.

        This is the core intelligent generation that maps requirements
        (from Socratic questioning) to agent configurations.

        Args:
            requirements: Requirements gathered from Socratic session
                - quality_focus: list of quality attributes
                - languages: list of programming languages
                - automation_level: advisory/semi_auto/fully_auto
                - domain: domain (e.g., "code_review", "testing")

        Returns:
            List of AgentBlueprints for a complete team
        """
        agents: list[AgentBlueprint] = []
        quality_focus = requirements.get("quality_focus", [])
        languages = requirements.get("languages", [])
        automation = requirements.get("automation_level", "semi_auto")

        # Map quality focus to agent templates
        quality_to_templates = {
            "security": ["security_reviewer"],
            "performance": ["performance_analyzer"],
            "maintainability": ["code_quality_reviewer", "documentation_writer"],
            "reliability": ["code_quality_reviewer", "test_generator"],
            "testability": ["test_generator"],
        }

        # Collect needed templates
        needed_templates: set[str] = set()
        for quality in quality_focus:
            templates = quality_to_templates.get(quality, [])
            needed_templates.update(templates)

        # Default to basic code review if no specific focus
        if not needed_templates:
            needed_templates.add("code_quality_reviewer")

        # Add synthesizer for results aggregation
        if len(needed_templates) > 1:
            needed_templates.add("result_synthesizer")

        # Generate agent for each template
        for template_id in needed_templates:
            customizations = {
                "languages": languages,
                "quality_focus": quality_focus,
            }

            # Adjust for automation level
            if automation == "fully_auto":
                customizations["instructions"] = [
                    "Apply fixes automatically where safe",
                    "Minimize human review requirements",
                ]
            elif automation == "advisory":
                customizations["instructions"] = [
                    "Provide recommendations only",
                    "Do not modify any files",
                ]

            try:
                agent = self.generate_agent_from_template(template_id, customizations)
                agents.append(agent)
            except ValueError:
                logger.warning(f"Template not found: {template_id}")

        return agents

    def generate_workflow(
        self,
        blueprint: WorkflowBlueprint,
    ) -> GeneratedWorkflow:
        """Generate a complete workflow from a blueprint.

        Args:
            blueprint: The workflow blueprint to generate from

        Returns:
            GeneratedWorkflow ready for execution
        """
        # Validate blueprint
        is_valid, errors = blueprint.validate()
        if not is_valid:
            raise ValueError(f"Invalid blueprint: {'; '.join(errors)}")

        # Generate XML agents from blueprints
        xml_agents = []
        for agent_bp in blueprint.agents:
            xml_agent = self._create_xml_agent(agent_bp.spec)
            xml_agents.append(xml_agent)

        # Build stage configuration
        stages_config = []
        for stage in blueprint.stages:
            stages_config.append({
                "id": stage.id,
                "name": stage.name,
                "agents": stage.agent_ids,
                "parallel": stage.parallel,
                "depends_on": stage.depends_on,
                "timeout": stage.timeout,
            })

        return GeneratedWorkflow(
            blueprint=blueprint,
            agents=xml_agents,
            stages=stages_config,
            generated_at=datetime.now().isoformat(),
        )

    def _create_xml_agent(self, spec: AgentSpec) -> "XMLAgent":
        """Create an XMLAgent from a spec."""
        from ..workflows.xml_enhanced_crew import XMLAgent

        return XMLAgent(
            role=spec.name,
            goal=spec.goal,
            backstory=spec.backstory,
            expertise_level="expert" if spec.model_tier != "cheap" else "competent",
            custom_instructions=spec.custom_instructions,
        )

    def create_workflow_blueprint(
        self,
        name: str,
        description: str,
        agents: list[AgentBlueprint],
        quality_focus: list[str],
        automation_level: str,
        success_criteria: SuccessCriteria | None = None,
    ) -> WorkflowBlueprint:
        """Create a workflow blueprint with automatic staging.

        Args:
            name: Workflow name
            description: Workflow description
            agents: Agent blueprints to include
            quality_focus: Quality attributes to optimize for
            automation_level: Level of automation
            success_criteria: Optional success criteria

        Returns:
            Complete WorkflowBlueprint
        """
        # Group agents by role for staging
        analyzers = [a for a in agents if a.spec.role in (AgentRole.ANALYZER, AgentRole.REVIEWER, AgentRole.AUDITOR)]
        generators = [a for a in agents if a.spec.role == AgentRole.GENERATOR]
        reporters = [a for a in agents if a.spec.role == AgentRole.REPORTER]

        stages = []

        # Stage 1: Analysis (parallel)
        if analyzers:
            stages.append(StageSpec(
                id="analysis",
                name="Analysis",
                description="Analyze code and identify issues",
                agent_ids=[a.spec.id for a in analyzers],
                parallel=True,
                output_aggregation="merge",
            ))

        # Stage 2: Generation (sequential, depends on analysis)
        if generators:
            stages.append(StageSpec(
                id="generation",
                name="Generation",
                description="Generate fixes and improvements",
                agent_ids=[a.spec.id for a in generators],
                parallel=False,
                depends_on=["analysis"] if analyzers else [],
            ))

        # Stage 3: Synthesis (always last)
        if reporters:
            depends = []
            if analyzers:
                depends.append("analysis")
            if generators:
                depends.append("generation")

            stages.append(StageSpec(
                id="synthesis",
                name="Synthesis",
                description="Synthesize findings into report",
                agent_ids=[a.spec.id for a in reporters],
                parallel=False,
                depends_on=depends,
            ))

        return WorkflowBlueprint(
            name=name,
            description=description,
            agents=agents,
            stages=stages,
            quality_focus=quality_focus,
            automation_level=automation_level,
            success_criteria=success_criteria,
            generated_at=datetime.now().isoformat(),
        )


@dataclass
class GeneratedWorkflow:
    """A generated, runnable workflow.

    Contains all the components needed to execute the workflow.
    """

    # Source blueprint
    blueprint: WorkflowBlueprint

    # Generated XMLAgent instances
    agents: list[Any]  # XMLAgent

    # Stage configuration
    stages: list[dict[str, Any]]

    # Generation timestamp
    generated_at: str = ""

    # Whether workflow has been validated
    validated: bool = False

    async def execute(
        self,
        input_data: dict[str, Any],
        progress_callback: Any = None,
    ) -> dict[str, Any]:
        """Execute the workflow.

        Args:
            input_data: Input data for the workflow
            progress_callback: Optional progress callback

        Returns:
            Workflow results
        """
        # This is a simplified execution - real implementation would
        # integrate with BaseWorkflow
        results: dict[str, Any] = {
            "stages": {},
            "agents": {},
            "final_output": None,
            "success": False,
        }

        for stage_config in self.stages:
            stage_id = stage_config["id"]
            agent_ids = stage_config["agents"]

            stage_results = []
            for agent_id in agent_ids:
                # Find agent
                agent = next(
                    (a for a in self.agents if hasattr(a, "role") and self._match_agent(a, agent_id)),
                    None
                )
                if agent:
                    # Execute agent (simplified)
                    result = {
                        "agent_id": agent_id,
                        "status": "completed",
                        "output": f"Agent {agent_id} completed",
                    }
                    stage_results.append(result)

            results["stages"][stage_id] = stage_results

        results["success"] = True
        results["final_output"] = results["stages"]

        return results

    def _match_agent(self, agent: Any, agent_id: str) -> bool:
        """Check if an agent matches an ID."""
        # Match by role name (simplified)
        if hasattr(agent, "role"):
            return agent_id.replace("_", " ").lower() in agent.role.lower()
        return False

    def describe(self) -> str:
        """Get human-readable description of the workflow."""
        lines = [
            f"Workflow: {self.blueprint.name}",
            f"Description: {self.blueprint.description}",
            "",
            f"Agents ({len(self.agents)}):",
        ]

        for agent in self.agents:
            if hasattr(agent, "role"):
                lines.append(f"  - {agent.role}: {getattr(agent, 'goal', 'N/A')}")

        lines.append("")
        lines.append(f"Stages ({len(self.stages)}):")

        for stage in self.stages:
            parallel = "parallel" if stage.get("parallel") else "sequential"
            lines.append(f"  - {stage['name']} ({parallel}): {', '.join(stage['agents'])}")

        return "\n".join(lines)
