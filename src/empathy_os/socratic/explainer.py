"""Workflow Explainer

Generates human-readable explanations of workflows, agents, and their behavior.
Supports multiple output formats and detail levels.

Features:
- Natural language workflow narratives
- Agent capability explanations
- Success criteria descriptions
- Technical vs non-technical audiences
- Multiple output formats (text, markdown, HTML)

Copyright 2026 Smart-AI-Memory
Licensed under Fair Source License 0.9
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum
from typing import Any

from .blueprint import WorkflowBlueprint, AgentSpec, StageSpec, AgentRole
from .success import SuccessCriteria, SuccessMetric


# =============================================================================
# EXPLANATION LEVELS
# =============================================================================


class AudienceLevel(Enum):
    """Target audience for explanations."""

    TECHNICAL = "technical"  # Developers, engineers
    BUSINESS = "business"  # Managers, stakeholders
    BEGINNER = "beginner"  # New users learning the system


class DetailLevel(Enum):
    """Level of detail in explanations."""

    BRIEF = "brief"  # One-liner summary
    STANDARD = "standard"  # Normal explanation
    DETAILED = "detailed"  # Full technical details


class OutputFormat(Enum):
    """Output format for explanations."""

    TEXT = "text"
    MARKDOWN = "markdown"
    HTML = "html"
    JSON = "json"


# =============================================================================
# DATA STRUCTURES
# =============================================================================


@dataclass
class Explanation:
    """A generated explanation."""

    title: str
    summary: str
    sections: list[dict[str, str]]
    audience: AudienceLevel
    detail_level: DetailLevel

    def to_text(self) -> str:
        """Convert to plain text."""
        lines = [self.title, "=" * len(self.title), "", self.summary, ""]

        for section in self.sections:
            lines.append(section["heading"])
            lines.append("-" * len(section["heading"]))
            lines.append(section["content"])
            lines.append("")

        return "\n".join(lines)

    def to_markdown(self) -> str:
        """Convert to markdown."""
        lines = [f"# {self.title}", "", self.summary, ""]

        for section in self.sections:
            lines.append(f"## {section['heading']}")
            lines.append("")
            lines.append(section["content"])
            lines.append("")

        return "\n".join(lines)

    def to_html(self) -> str:
        """Convert to HTML."""
        html = [
            "<article class='workflow-explanation'>",
            f"<h1>{self.title}</h1>",
            f"<p class='summary'>{self.summary}</p>",
        ]

        for section in self.sections:
            html.append(f"<section>")
            html.append(f"<h2>{section['heading']}</h2>")
            html.append(f"<p>{section['content']}</p>")
            html.append("</section>")

        html.append("</article>")
        return "\n".join(html)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "title": self.title,
            "summary": self.summary,
            "sections": self.sections,
            "audience": self.audience.value,
            "detail_level": self.detail_level.value,
        }


# =============================================================================
# ROLE DESCRIPTIONS
# =============================================================================


ROLE_DESCRIPTIONS = {
    AudienceLevel.TECHNICAL: {
        AgentRole.ANALYZER: "performs static analysis and data extraction",
        AgentRole.REVIEWER: "evaluates code quality and adherence to standards",
        AgentRole.AUDITOR: "conducts security and compliance audits",
        AgentRole.GENERATOR: "generates new code, tests, or documentation",
        AgentRole.FIXER: "automatically remediate identified issues",
        AgentRole.ORCHESTRATOR: "coordinates multi-agent workflows",
        AgentRole.RESEARCHER: "gathers information and context",
        AgentRole.VALIDATOR: "validates outputs against specifications",
    },
    AudienceLevel.BUSINESS: {
        AgentRole.ANALYZER: "examines the codebase to find patterns and issues",
        AgentRole.REVIEWER: "checks code quality and best practices",
        AgentRole.AUDITOR: "verifies security and compliance requirements",
        AgentRole.GENERATOR: "creates new content automatically",
        AgentRole.FIXER: "automatically corrects problems",
        AgentRole.ORCHESTRATOR: "manages the overall process",
        AgentRole.RESEARCHER: "collects relevant information",
        AgentRole.VALIDATOR: "ensures outputs meet requirements",
    },
    AudienceLevel.BEGINNER: {
        AgentRole.ANALYZER: "looks at your code to understand what it does",
        AgentRole.REVIEWER: "checks if your code follows good practices",
        AgentRole.AUDITOR: "makes sure your code is safe and follows the rules",
        AgentRole.GENERATOR: "writes new code or documentation for you",
        AgentRole.FIXER: "fixes problems it finds",
        AgentRole.ORCHESTRATOR: "manages all the other helpers",
        AgentRole.RESEARCHER: "finds information you need",
        AgentRole.VALIDATOR: "double-checks that everything is correct",
    },
}


# =============================================================================
# WORKFLOW EXPLAINER
# =============================================================================


class WorkflowExplainer:
    """Generates human-readable workflow explanations."""

    def __init__(
        self,
        audience: AudienceLevel = AudienceLevel.TECHNICAL,
        detail_level: DetailLevel = DetailLevel.STANDARD,
        use_llm: bool = False,
        api_key: str | None = None,
    ):
        """Initialize the explainer.

        Args:
            audience: Target audience level
            detail_level: Level of detail
            use_llm: Whether to use LLM for richer explanations
            api_key: API key for LLM (if use_llm=True)
        """
        self.audience = audience
        self.detail_level = detail_level
        self.use_llm = use_llm
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self._client = None

    def explain_workflow(
        self,
        blueprint: WorkflowBlueprint,
        success_criteria: SuccessCriteria | None = None,
    ) -> Explanation:
        """Generate explanation for a workflow.

        Args:
            blueprint: The workflow blueprint
            success_criteria: Optional success criteria

        Returns:
            Explanation object
        """
        sections: list[dict[str, str]] = []

        # Overview section
        sections.append({
            "heading": "Overview",
            "content": self._explain_overview(blueprint),
        })

        # Agents section
        sections.append({
            "heading": "Agents Involved",
            "content": self._explain_agents(blueprint.agents),
        })

        # Process section
        sections.append({
            "heading": "How It Works",
            "content": self._explain_process(blueprint.stages, blueprint.agents),
        })

        # Success criteria section (if provided)
        if success_criteria:
            sections.append({
                "heading": "Success Metrics",
                "content": self._explain_success_criteria(success_criteria),
            })

        # Summary
        summary = self._generate_summary(blueprint)

        return Explanation(
            title=f"Workflow: {blueprint.name}",
            summary=summary,
            sections=sections,
            audience=self.audience,
            detail_level=self.detail_level,
        )

    def explain_agent(self, agent: AgentSpec) -> Explanation:
        """Generate explanation for a single agent.

        Args:
            agent: The agent specification

        Returns:
            Explanation object
        """
        sections: list[dict[str, str]] = []

        # Role section
        role_desc = ROLE_DESCRIPTIONS.get(self.audience, {}).get(
            agent.role, "performs automated tasks"
        )
        sections.append({
            "heading": "Role",
            "content": f"This agent {role_desc}.",
        })

        # Capabilities section
        sections.append({
            "heading": "Capabilities",
            "content": self._explain_tools(agent.tools),
        })

        # How it helps section
        sections.append({
            "heading": "How It Helps",
            "content": self._explain_agent_value(agent),
        })

        summary = f"{agent.name} is a {agent.role.value} agent that {agent.description.lower()}"

        return Explanation(
            title=f"Agent: {agent.name}",
            summary=summary,
            sections=sections,
            audience=self.audience,
            detail_level=self.detail_level,
        )

    def _explain_overview(self, blueprint: WorkflowBlueprint) -> str:
        """Generate workflow overview."""
        if self.audience == AudienceLevel.BEGINNER:
            return (
                f"This workflow uses {len(blueprint.agents)} AI helpers to "
                f"complete {len(blueprint.stages)} steps. "
                f"It focuses on: {', '.join(blueprint.domains)}."
            )
        elif self.audience == AudienceLevel.BUSINESS:
            return (
                f"This automated workflow deploys {len(blueprint.agents)} specialized agents "
                f"across {len(blueprint.stages)} execution stages. "
                f"Target domains: {', '.join(blueprint.domains)}."
            )
        else:
            return (
                f"Multi-agent workflow with {len(blueprint.agents)} agents, "
                f"{len(blueprint.stages)} stages. "
                f"Domains: {', '.join(blueprint.domains)}. "
                f"Created: {blueprint.created_at.strftime('%Y-%m-%d') if blueprint.created_at else 'N/A'}."
            )

    def _explain_agents(self, agents: list[AgentSpec]) -> str:
        """Generate agents explanation."""
        lines = []

        for agent in agents:
            role_desc = ROLE_DESCRIPTIONS.get(self.audience, {}).get(
                agent.role, "works on the task"
            )

            if self.detail_level == DetailLevel.BRIEF:
                lines.append(f"• {agent.name}: {role_desc}")
            else:
                tool_count = len(agent.tools)
                tool_str = f" ({tool_count} tools)" if self.detail_level == DetailLevel.DETAILED else ""
                lines.append(f"• **{agent.name}**{tool_str}: {agent.description}")

        return "\n".join(lines)

    def _explain_process(
        self,
        stages: list[StageSpec],
        agents: list[AgentSpec],
    ) -> str:
        """Generate process explanation."""
        agent_lookup = {a.agent_id: a for a in agents}
        lines = []

        for i, stage in enumerate(stages, 1):
            agent_names = [
                agent_lookup[aid].name
                for aid in stage.agent_ids
                if aid in agent_lookup
            ]

            if self.audience == AudienceLevel.BEGINNER:
                if stage.parallel:
                    lines.append(
                        f"{i}. **{stage.name}**: {', '.join(agent_names)} work together at the same time"
                    )
                else:
                    lines.append(
                        f"{i}. **{stage.name}**: {', '.join(agent_names)} work one after another"
                    )
            else:
                parallel_str = " (parallel)" if stage.parallel else ""
                lines.append(
                    f"{i}. **{stage.name}**{parallel_str}: {', '.join(agent_names)}"
                )

            if self.detail_level == DetailLevel.DETAILED and stage.dependencies:
                lines.append(f"   Depends on: {', '.join(stage.dependencies)}")

        return "\n".join(lines)

    def _explain_tools(self, tools: list[Any]) -> str:
        """Generate tools explanation."""
        tool_explanations = {
            "read_file": "read and analyze files",
            "write_file": "create or modify files",
            "grep_code": "search through code",
            "analyze_ast": "understand code structure",
            "run_linter": "check code style",
            "run_tests": "execute test suites",
            "security_scan": "detect vulnerabilities",
        }

        if self.detail_level == DetailLevel.BRIEF:
            return f"This agent has access to {len(tools)} tools."

        lines = ["This agent can:"]
        for tool in tools:
            tool_id = tool.tool_id if hasattr(tool, 'tool_id') else str(tool)
            explanation = tool_explanations.get(tool_id, f"use {tool_id}")
            lines.append(f"• {explanation}")

        return "\n".join(lines)

    def _explain_agent_value(self, agent: AgentSpec) -> str:
        """Generate explanation of agent's value."""
        value_by_role = {
            AgentRole.ANALYZER: "identifying patterns, issues, and opportunities in your codebase",
            AgentRole.REVIEWER: "ensuring code quality and catching problems before they reach production",
            AgentRole.AUDITOR: "keeping your code secure and compliant with regulations",
            AgentRole.GENERATOR: "saving time by automatically creating code, tests, or documentation",
            AgentRole.FIXER: "automatically resolving issues without manual intervention",
            AgentRole.ORCHESTRATOR: "managing complex workflows efficiently",
            AgentRole.RESEARCHER: "providing relevant context and information",
            AgentRole.VALIDATOR: "ensuring outputs meet quality standards",
        }

        base_value = value_by_role.get(agent.role, "automating important tasks")

        if self.audience == AudienceLevel.BEGINNER:
            return f"This helper saves you time by {base_value}."
        else:
            return f"This agent adds value by {base_value}."

    def _explain_success_criteria(self, criteria: SuccessCriteria) -> str:
        """Generate success criteria explanation."""
        lines = ["The workflow is considered successful when:"]

        for metric in criteria.metrics:
            if self.audience == AudienceLevel.BEGINNER:
                lines.append(f"• {metric.name}: {metric.description}")
            else:
                target = f" (target: {metric.target_value})" if metric.target_value is not None else ""
                lines.append(f"• **{metric.name}**{target}: {metric.description}")

        return "\n".join(lines)

    def _generate_summary(self, blueprint: WorkflowBlueprint) -> str:
        """Generate workflow summary."""
        if self.audience == AudienceLevel.BEGINNER:
            return (
                f"This workflow automatically helps you with {', '.join(blueprint.domains)}. "
                f"It uses {len(blueprint.agents)} AI helpers that work together in "
                f"{len(blueprint.stages)} steps to get the job done."
            )
        elif self.audience == AudienceLevel.BUSINESS:
            return (
                f"{blueprint.description} "
                f"The workflow orchestrates {len(blueprint.agents)} specialized agents "
                f"to deliver results efficiently and consistently."
            )
        else:
            return blueprint.description or f"A {len(blueprint.stages)}-stage workflow for {', '.join(blueprint.domains)}."

    def generate_narrative(self, blueprint: WorkflowBlueprint) -> str:
        """Generate a narrative story-like explanation.

        Args:
            blueprint: The workflow blueprint

        Returns:
            Narrative explanation string
        """
        agent_lookup = {a.agent_id: a for a in blueprint.agents}

        lines = [
            f"## The {blueprint.name} Story",
            "",
            f"*{blueprint.description}*",
            "",
            "---",
            "",
        ]

        # Introduction
        lines.append(
            f"When you run this workflow, a team of {len(blueprint.agents)} specialized "
            f"AI agents springs into action. Here's what happens:"
        )
        lines.append("")

        # Walk through stages
        for i, stage in enumerate(blueprint.stages, 1):
            lines.append(f"### Step {i}: {stage.name}")
            lines.append("")

            agents_in_stage = [
                agent_lookup[aid] for aid in stage.agent_ids if aid in agent_lookup
            ]

            if stage.parallel and len(agents_in_stage) > 1:
                lines.append("Working in parallel:")
                for agent in agents_in_stage:
                    role_desc = ROLE_DESCRIPTIONS.get(self.audience, {}).get(
                        agent.role, "works"
                    )
                    lines.append(f"- **{agent.name}** {role_desc}")
            else:
                for agent in agents_in_stage:
                    role_desc = ROLE_DESCRIPTIONS.get(self.audience, {}).get(
                        agent.role, "works"
                    )
                    lines.append(f"**{agent.name}** {role_desc}.")

            lines.append("")

        # Conclusion
        lines.append("### The Result")
        lines.append("")
        lines.append(
            "After all stages complete, you receive a comprehensive report with "
            "findings, recommendations, and any automated fixes that were applied."
        )

        return "\n".join(lines)


# =============================================================================
# EXPLANATION GENERATOR (LLM-POWERED)
# =============================================================================


class LLMExplanationGenerator:
    """Uses LLM to generate richer, more natural explanations."""

    EXPLAIN_PROMPT = """Generate a clear, helpful explanation of this workflow for a {audience} audience.

Workflow: {name}
Description: {description}
Domains: {domains}
Agents: {agents}
Stages: {stages}

Write a {detail_level} explanation that:
1. Explains what the workflow does in plain language
2. Describes each agent's role
3. Walks through the process step by step
4. Highlights the value and benefits

Format as markdown with clear sections."""

    def __init__(self, api_key: str | None = None):
        """Initialize the generator.

        Args:
            api_key: Anthropic API key
        """
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self._client = None

    def _get_client(self):
        """Lazy-load Anthropic client."""
        if self._client is None and self.api_key:
            try:
                import anthropic
                self._client = anthropic.Anthropic(api_key=self.api_key)
            except ImportError:
                pass
        return self._client

    def generate(
        self,
        blueprint: WorkflowBlueprint,
        audience: AudienceLevel = AudienceLevel.BUSINESS,
        detail_level: DetailLevel = DetailLevel.STANDARD,
    ) -> str:
        """Generate LLM-powered explanation.

        Args:
            blueprint: The workflow blueprint
            audience: Target audience
            detail_level: Level of detail

        Returns:
            Generated explanation markdown
        """
        client = self._get_client()
        if not client:
            # Fallback to rule-based explainer
            explainer = WorkflowExplainer(audience=audience, detail_level=detail_level)
            return explainer.explain_workflow(blueprint).to_markdown()

        # Format workflow info for prompt
        agents_str = "\n".join(
            f"- {a.name} ({a.role.value}): {a.description}"
            for a in blueprint.agents
        )

        stages_str = "\n".join(
            f"- {s.name}: {', '.join(s.agent_ids)}"
            + (" (parallel)" if s.parallel else "")
            for s in blueprint.stages
        )

        prompt = self.EXPLAIN_PROMPT.format(
            audience=audience.value,
            name=blueprint.name,
            description=blueprint.description,
            domains=", ".join(blueprint.domains),
            agents=agents_str,
            stages=stages_str,
            detail_level=detail_level.value,
        )

        try:
            response = client.messages.create(
                model="claude-3-5-haiku-20241022",
                max_tokens=1500,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text if response.content else ""
        except Exception:
            # Fallback
            explainer = WorkflowExplainer(audience=audience, detail_level=detail_level)
            return explainer.explain_workflow(blueprint).to_markdown()


# =============================================================================
# HIGH-LEVEL API
# =============================================================================


def explain_workflow(
    blueprint: WorkflowBlueprint,
    audience: AudienceLevel | str = AudienceLevel.BUSINESS,
    detail_level: DetailLevel | str = DetailLevel.STANDARD,
    format: OutputFormat | str = OutputFormat.MARKDOWN,
    use_llm: bool = False,
) -> str:
    """Generate explanation for a workflow.

    Args:
        blueprint: The workflow blueprint
        audience: Target audience (technical, business, beginner)
        detail_level: Level of detail (brief, standard, detailed)
        format: Output format (text, markdown, html, json)
        use_llm: Whether to use LLM for richer explanations

    Returns:
        Formatted explanation string
    """
    # Convert string args to enums
    if isinstance(audience, str):
        audience = AudienceLevel(audience)
    if isinstance(detail_level, str):
        detail_level = DetailLevel(detail_level)
    if isinstance(format, str):
        format = OutputFormat(format)

    if use_llm:
        generator = LLMExplanationGenerator()
        markdown = generator.generate(blueprint, audience, detail_level)

        if format == OutputFormat.MARKDOWN:
            return markdown
        elif format == OutputFormat.TEXT:
            # Simple markdown to text conversion
            import re
            text = re.sub(r'#{1,6}\s+', '', markdown)  # Remove headers
            text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)  # Remove bold
            text = re.sub(r'\*([^*]+)\*', r'\1', text)  # Remove italic
            return text
        elif format == OutputFormat.HTML:
            # Simple markdown to HTML
            html = f"<div class='explanation'>{markdown}</div>"
            return html
        else:
            return markdown

    explainer = WorkflowExplainer(audience=audience, detail_level=detail_level)
    explanation = explainer.explain_workflow(blueprint)

    if format == OutputFormat.TEXT:
        return explanation.to_text()
    elif format == OutputFormat.MARKDOWN:
        return explanation.to_markdown()
    elif format == OutputFormat.HTML:
        return explanation.to_html()
    elif format == OutputFormat.JSON:
        import json
        return json.dumps(explanation.to_dict(), indent=2)
    else:
        return explanation.to_markdown()
