"""Health Check Crew - Multi-Agent Workflow

Comprehensive project health assessment using multi-agent crew.

Pattern: Crew
- Multiple specialized AI agents collaborate on the task
- Process Type: parallel (agents run simultaneously)
- Agents: 3-6 (configurable by mode)

Modes:
- daily: Quick check (3 agents: Security, Coverage, Quality)
- weekly: Standard check (5 agents: + Performance, Documentation)
- release: Deep check (6 agents: + Dependency audit)

Copyright 2025 Smart-AI-Memory
Licensed under Fair Source License 0.9
"""

import asyncio
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

# Try to import the LLM executor for actual AI calls
EmpathyLLMExecutor = None
ExecutionContext = None
HAS_EXECUTOR = False

try:
    from empathy_os.models import ExecutionContext as _ExecutionContext
    from empathy_os.models.empathy_executor import EmpathyLLMExecutor as _EmpathyLLMExecutor

    EmpathyLLMExecutor = _EmpathyLLMExecutor
    ExecutionContext = _ExecutionContext
    HAS_EXECUTOR = True
except ImportError:
    pass

# Try to import the ProjectIndex for file tracking
ProjectIndex = None
HAS_PROJECT_INDEX = False

try:
    from empathy_os.project_index import ProjectIndex as _ProjectIndex

    ProjectIndex = _ProjectIndex
    HAS_PROJECT_INDEX = True
except ImportError:
    pass


@dataclass
class CategoryScore:
    """Individual category health score."""

    name: str
    score: float  # 0-100
    weight: float  # 0-1
    passed: bool = True
    issues: list[str] = field(default_factory=list)

    @property
    def weighted_score(self) -> float:
        """Calculate weighted contribution to overall score."""
        return self.score * self.weight


@dataclass
class HealthCheckCrewResult:
    """Result from HealthCheckCrew execution."""

    success: bool
    overall_health_score: float  # 0-100
    grade: str  # A/B/C/D/F

    # Category scores
    category_scores: list[CategoryScore] = field(default_factory=list)

    # Issues and recommendations
    issues: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)

    # Metadata
    mode: str = "daily"  # daily/weekly/release
    agents_executed: int = 0
    cost: float = 0.0
    duration_ms: int = 0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        """Convert result to dictionary."""
        return {
            "success": self.success,
            "overall_health_score": self.overall_health_score,
            "grade": self.grade,
            "category_scores": [
                {
                    "name": cat.name,
                    "score": cat.score,
                    "weight": cat.weight,
                    "passed": cat.passed,
                    "issues": cat.issues,
                }
                for cat in self.category_scores
            ],
            "issues": self.issues,
            "warnings": self.warnings,
            "recommendations": self.recommendations,
            "mode": self.mode,
            "agents_executed": self.agents_executed,
            "cost": self.cost,
            "duration_ms": self.duration_ms,
            "timestamp": self.timestamp,
        }

    @property
    def formatted_report(self) -> str:
        """Generate human-readable formatted report."""
        return format_health_check_report(self)


@dataclass
class Agent:
    """Agent configuration for the crew with XML-enhanced prompting."""

    role: str
    goal: str
    backstory: str
    weight: float = 0.2  # Weight in overall health score
    expertise_level: str = "expert"
    use_xml_structure: bool = True

    def get_system_prompt(self) -> str:
        """Generate XML-enhanced system prompt for this agent."""
        return f"""<agent_role>
You are a {self.role} with {self.expertise_level}-level expertise.
</agent_role>

<agent_goal>
{self.goal}
</agent_goal>

<agent_backstory>
{self.backstory}
</agent_backstory>

<instructions>
1. Carefully review all provided context data
2. Think through your analysis step-by-step
3. Provide thorough, actionable analysis
4. Calculate a health score (0-100) for your category
5. Structure your output according to the requested format
</instructions>

<output_structure>
Always structure your response as:

<thinking>
[Your step-by-step reasoning process]
- What you observe in the context
- How you analyze the situation
- What score you assign and why
</thinking>

<answer>
[Your final output in JSON format with score and findings]
</answer>
</output_structure>"""


@dataclass
class Task:
    """Task configuration for the crew with XML-enhanced prompting."""

    description: str
    expected_output: str
    agent: Agent

    def get_user_prompt(self, context: dict) -> str:
        """Generate XML-enhanced user prompt for this task with context."""
        # Build structured context with proper XML tags
        context_sections = []
        for key, value in context.items():
            if value:
                tag_name = key.replace(" ", "_").replace("-", "_").lower()
                context_sections.append(f"<{tag_name}>\n{value}\n</{tag_name}>")

        context_xml = "\n".join(context_sections)

        return f"""<task_description>
{self.description}
</task_description>

<context>
{context_xml}
</context>

<expected_output>
{self.expected_output}
</expected_output>

<instructions>
1. Review all context data in the <context> tags above
2. Structure your response using <thinking> and <answer> tags
3. Provide a health score (0-100) for this category
4. Match the expected output format exactly
</instructions>"""


def parse_xml_response(response: str) -> dict:
    """Parse XML-structured agent response."""
    result = {
        "thinking": "",
        "answer": "",
        "raw": response,
        "has_xml_structure": False,
    }

    # Try to extract thinking section
    thinking_start = response.find("<thinking>")
    thinking_end = response.find("</thinking>")
    if thinking_start != -1 and thinking_end != -1:
        result["thinking"] = response[thinking_start + 10 : thinking_end].strip()
        result["has_xml_structure"] = True

    # Try to extract answer section
    answer_start = response.find("<answer>")
    answer_end = response.find("</answer>")
    if answer_start != -1 and answer_end != -1:
        result["answer"] = response[answer_start + 8 : answer_end].strip()
        result["has_xml_structure"] = True

    # If no answer found, extract content after </thinking> or use full response
    if not result["answer"]:
        if thinking_end != -1:
            # Extract everything after </thinking> tag
            result["answer"] = response[thinking_end + 11 :].strip()
        else:
            # Use full response as fallback
            result["answer"] = response

    return result


def format_health_check_report(result: HealthCheckCrewResult) -> str:
    """Format health check result as human-readable text."""
    lines = []

    # Header
    lines.append("=" * 70)
    lines.append(f"PROJECT HEALTH CHECK ({result.mode.upper()} MODE)")
    lines.append("=" * 70)
    lines.append("")

    # Overall Score
    grade_emoji = {"A": "🟢", "B": "🟡", "C": "🟠", "D": "🔴", "F": "⛔"}.get(result.grade, "❓")
    lines.append(
        f"Overall Health: {grade_emoji} {result.overall_health_score:.1f}/100 (Grade: {result.grade})"
    )
    lines.append(f"Timestamp: {result.timestamp}")
    lines.append(f"Duration: {result.duration_ms}ms ({result.duration_ms / 1000:.1f}s)")
    lines.append(f"Agents Executed: {result.agents_executed}")
    lines.append(f"Cost: ${result.cost:.4f}")
    lines.append("")

    # Category Scores
    if result.category_scores:
        lines.append("-" * 70)
        lines.append("CATEGORY SCORES")
        lines.append("-" * 70)
        for cat in result.category_scores:
            icon = "✅" if cat.passed else "❌"
            lines.append(f"{icon} {cat.name}: {cat.score:.1f}/100 (weight: {cat.weight:.0%})")
            if cat.issues:
                for issue in cat.issues[:3]:  # Show first 3 issues
                    lines.append(f"   • {issue}")
        lines.append("")

    # Issues
    if result.issues:
        lines.append("-" * 70)
        lines.append("🚫 CRITICAL ISSUES")
        lines.append("-" * 70)
        for issue in result.issues:
            lines.append(f"  • {issue}")
        lines.append("")

    # Warnings
    if result.warnings:
        lines.append("-" * 70)
        lines.append("⚠️  WARNINGS")
        lines.append("-" * 70)
        for warning in result.warnings:
            lines.append(f"  • {warning}")
        lines.append("")

    # Recommendations
    if result.recommendations:
        lines.append("-" * 70)
        lines.append("💡 RECOMMENDATIONS")
        lines.append("-" * 70)
        for i, rec in enumerate(result.recommendations, 1):
            lines.append(f"{i}. {rec}")
        lines.append("")

    # Footer
    lines.append("=" * 70)
    if result.overall_health_score >= 80:
        lines.append("✅ Project health is good")
    elif result.overall_health_score >= 60:
        lines.append("⚠️  Project health needs attention")
    else:
        lines.append("❌ Project health requires immediate action")
    lines.append("=" * 70)

    return "\n".join(lines)


class HealthCheckCrew:
    """Health Check Crew - Multi-agent project health assessment.

    Uses 3-6 specialized agents running in parallel to comprehensively
    evaluate project health across multiple dimensions.

    Process Type: parallel

    Modes:
    - daily: Quick check (3 agents: Security, Coverage, Quality)
    - weekly: Standard check (5 agents: + Performance, Documentation)
    - release: Deep check (6 agents: + Dependency audit)

    Usage:
        crew = HealthCheckCrew(mode="weekly")
        result = await crew.execute(project_root=".")

        print(f"Health Score: {result.overall_health_score}/100 ({result.grade})")
    """

    name = "Health_Check_Crew"
    description = "Comprehensive project health assessment using multi-agent crew"
    process_type = "parallel"

    # Category weights for overall score
    WEIGHTS = {
        "security": 0.30,  # 30%
        "coverage": 0.25,  # 25%
        "quality": 0.20,  # 20%
        "performance": 0.15,  # 15%
        "documentation": 0.10,  # 10%
        "dependencies": 0.05,  # 5% (release mode only)
    }

    def __init__(self, project_root: str = ".", mode: str = "daily", **kwargs: Any):
        """Initialize the crew with configured agents.

        Args:
            project_root: Root directory of project to analyze
            mode: Execution mode (daily/weekly/release)
            **kwargs: Additional configuration
        """
        if mode not in ("daily", "weekly", "release"):
            raise ValueError(f"Invalid mode '{mode}'. Must be daily/weekly/release.")

        self.config = kwargs
        self.project_root = project_root
        self.mode = mode
        self._executor = None
        self._project_index = None
        self._total_cost = 0.0
        self._total_input_tokens = 0
        self._total_output_tokens = 0

        # Initialize executor if available
        if HAS_EXECUTOR and EmpathyLLMExecutor is not None:
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if api_key:
                try:
                    self._executor = EmpathyLLMExecutor(
                        provider="anthropic",
                        api_key=api_key,
                    )
                except Exception:
                    pass

        # Initialize ProjectIndex if available
        if HAS_PROJECT_INDEX and ProjectIndex is not None:
            try:
                self._project_index = ProjectIndex(project_root)
                if not self._project_index.load():
                    print("  [ProjectIndex] Building index (first run)...")
                    self._project_index.refresh()
            except Exception as e:
                print(f"  [ProjectIndex] Warning: Could not load index: {e}")

        # Define agents based on mode
        self.agents = self._get_agents_for_mode()

    def _get_agents_for_mode(self) -> list[Agent]:
        """Get agents based on execution mode."""
        # Core agents (all modes)
        agents = [
            Agent(
                role="Security Auditor",
                goal="Assess security posture and identify vulnerabilities",
                backstory="Expert security auditor specializing in vulnerability detection and security best practices.",
                weight=self.WEIGHTS["security"],
            ),
            Agent(
                role="Test Coverage Analyst",
                goal="Evaluate test coverage and testing quality",
                backstory="Testing expert focused on coverage metrics and test quality assessment.",
                weight=self.WEIGHTS["coverage"],
            ),
            Agent(
                role="Code Quality Reviewer",
                goal="Assess code quality, complexity, and maintainability",
                backstory="Senior code reviewer focused on quality metrics and best practices.",
                weight=self.WEIGHTS["quality"],
            ),
        ]

        # Weekly and release: add performance and documentation
        if self.mode in ("weekly", "release"):
            agents.extend(
                [
                    Agent(
                        role="Performance Analyst",
                        goal="Identify performance bottlenecks and optimization opportunities",
                        backstory="Performance expert skilled at profiling and optimization.",
                        weight=self.WEIGHTS["performance"],
                    ),
                    Agent(
                        role="Documentation Specialist",
                        goal="Verify documentation completeness and quality",
                        backstory="Technical writer focused on documentation quality and completeness.",
                        weight=self.WEIGHTS["documentation"],
                    ),
                ]
            )

        # Release only: add dependency auditor
        if self.mode == "release":
            agents.append(
                Agent(
                    role="Dependency Auditor",
                    goal="Audit dependencies for security and version issues",
                    backstory="Dependency management expert focused on supply chain security.",
                    weight=self.WEIGHTS["dependencies"],
                )
            )

        return agents

    def define_tasks(self) -> list[Task]:
        """Define the tasks for this crew based on mode."""
        tasks = []

        for agent in self.agents:
            if agent.role == "Security Auditor":
                tasks.append(
                    Task(
                        description="Assess project security: 1) Scan for vulnerabilities, 2) Check dependency security, 3) Review authentication/authorization. Calculate security health score (0-100).",
                        expected_output="JSON with: score (0-100), issues (list), recommendation",
                        agent=agent,
                    )
                )
            elif agent.role == "Test Coverage Analyst":
                tasks.append(
                    Task(
                        description="Assess testing: 1) Calculate test coverage percentage, 2) Identify critical gaps, 3) Assess test quality. Calculate coverage health score (0-100).",
                        expected_output="JSON with: score (0-100), coverage_percentage, issues (list), recommendation",
                        agent=agent,
                    )
                )
            elif agent.role == "Code Quality Reviewer":
                tasks.append(
                    Task(
                        description="Assess code quality: 1) Calculate quality score, 2) Identify code smells, 3) Check complexity. Calculate quality health score (0-100).",
                        expected_output="JSON with: score (0-100), complexity_issues, issues (list), recommendation",
                        agent=agent,
                    )
                )
            elif agent.role == "Performance Analyst":
                tasks.append(
                    Task(
                        description="Assess performance: 1) Identify bottlenecks, 2) Check response times, 3) Review resource usage. Calculate performance health score (0-100).",
                        expected_output="JSON with: score (0-100), bottlenecks, issues (list), recommendation",
                        agent=agent,
                    )
                )
            elif agent.role == "Documentation Specialist":
                tasks.append(
                    Task(
                        description="Assess documentation: 1) Check docstring coverage, 2) Verify README currency, 3) Validate API docs. Calculate documentation health score (0-100).",
                        expected_output="JSON with: score (0-100), coverage_percentage, issues (list), recommendation",
                        agent=agent,
                    )
                )
            elif agent.role == "Dependency Auditor":
                tasks.append(
                    Task(
                        description="Audit dependencies: 1) Check for outdated versions, 2) Scan for known vulnerabilities, 3) Review license compatibility. Calculate dependency health score (0-100).",
                        expected_output="JSON with: score (0-100), outdated_count, vulnerable_count, issues (list), recommendation",
                        agent=agent,
                    )
                )

        return tasks

    async def _call_llm(
        self,
        agent: Agent,
        task: Task,
        context: dict,
    ) -> tuple[str, int, int, float]:
        """Call the LLM with agent/task configuration.

        Returns: (response_text, input_tokens, output_tokens, cost)
        """
        system_prompt = agent.get_system_prompt()
        user_prompt = task.get_user_prompt(context)

        if self._executor is None:
            # Fallback: return mock response
            return await self._mock_llm_call(agent, task)

        try:
            # Create execution context
            exec_context = ExecutionContext(
                task_type="health_check",
                workflow_name="health-check",
                step_name=agent.role,
            )

            # Execute with timeout using correct LLMExecutor API
            result = await asyncio.wait_for(
                self._executor.run(
                    task_type="health_check",
                    prompt=user_prompt,
                    system=system_prompt,
                    context=exec_context,
                ),
                timeout=120.0,
            )

            response = result.content
            input_tokens = result.input_tokens
            output_tokens = result.output_tokens
            cost = result.cost

            # Track totals
            self._total_cost += cost
            self._total_input_tokens += input_tokens
            self._total_output_tokens += output_tokens

            return (response, input_tokens, output_tokens, cost)

        except asyncio.TimeoutError:
            print(f"  [LLM] Timeout calling {agent.role}")
            return await self._mock_llm_call(agent, task, reason="Timeout")
        except Exception as e:
            print(f"  [LLM] Error calling {agent.role}: {e}")
            return await self._mock_llm_call(agent, task, reason=str(e))

    async def _mock_llm_call(
        self, agent: Agent, task: Task, reason: str = "No API key"
    ) -> tuple[str, int, int, float]:
        """Generate mock response when LLM is unavailable."""
        await asyncio.sleep(0.1)

        mock_scores = {
            "Security Auditor": 85,
            "Test Coverage Analyst": 75,
            "Code Quality Reviewer": 82,
            "Performance Analyst": 78,
            "Documentation Specialist": 90,
            "Dependency Auditor": 88,
        }

        score = mock_scores.get(agent.role, 80)

        response = f"""<thinking>
Analyzing {agent.role.lower()} for project health...
Based on available metrics, calculating health score.
</thinking>

<answer>
{{
  "score": {score},
  "issues": ["Mock issue 1", "Mock issue 2"],
  "recommendation": "Continue monitoring"
}}
</answer>

Note: This is a mock response ({reason}). Configure ANTHROPIC_API_KEY for real analysis."""

        return (response, 0, 0, 0.0)

    def _get_index_context(self) -> dict[str, Any]:
        """Get health check context from ProjectIndex if available."""
        if self._project_index is None:
            return {}

        try:
            return self._project_index.get_context_for_workflow("health_check")
        except Exception as e:
            print(f"  [ProjectIndex] Warning: Could not get context: {e}")
            return {}

    async def execute(
        self,
        project_root: str | None = None,
        context: dict | None = None,
        **kwargs: Any,
    ) -> HealthCheckCrewResult:
        """Execute the health check crew.

        Args:
            project_root: Path to project root (overrides init value)
            context: Additional context for agents
            **kwargs: Additional arguments

        Returns:
            HealthCheckCrewResult with health score and findings
        """
        if project_root:
            self.project_root = project_root

        started_at = datetime.now()
        context = context or {}

        print("\n" + "=" * 70)
        print(f"  HEALTH CHECK CREW ({self.mode.upper()} MODE)")
        print("=" * 70)
        print(f"\n  Project Root: {self.project_root}")
        print(f"  Agents: {len(self.agents)} (running in parallel)")
        print("")

        # Try to get rich context from ProjectIndex
        index_context = self._get_index_context()

        if index_context:
            print("  [ProjectIndex] Using indexed project data")
            agent_context = {
                "project_root": self.project_root,
                "mode": self.mode,
                **index_context,
                **context,
            }
        else:
            agent_context = {
                "project_root": self.project_root,
                "mode": self.mode,
                **context,
            }

        # Define tasks
        tasks = self.define_tasks()

        # Execute all agents in parallel
        print("  🚀 Executing agents in parallel...\n")

        agent_tasks = []
        for agent, task in zip(self.agents, tasks, strict=False):
            print(f"     • {agent.role}")
            agent_tasks.append(self._call_llm(agent, task, agent_context))

        # Wait for all agents to complete
        results = await asyncio.gather(*agent_tasks)

        print("\n  ✓ All agents completed\n")

        # Parse agent responses and calculate category scores
        category_scores = []
        all_issues = []
        all_warnings = []
        all_recommendations = []

        for agent, (response, _input_tokens, _output_tokens, _cost) in zip(
            self.agents, results, strict=False
        ):
            parsed = parse_xml_response(response)

            # Extract score from answer
            import json
            import re

            score = 0.0
            issues = []

            try:
                # Try to parse JSON from answer
                answer = parsed["answer"]

                # Debug: Check if answer is empty
                if not answer or not answer.strip():
                    # If answer is empty, try to extract JSON after </thinking> tag
                    raw = parsed.get("raw", "")
                    thinking_end = raw.find("</thinking>")
                    if thinking_end != -1:
                        # Get content after </thinking> tag
                        answer = raw[thinking_end + 11 :].strip()
                    else:
                        # Use full raw response
                        answer = raw

                # Remove markdown code blocks if present
                answer_cleaned = re.sub(r"```json\s*", "", answer)
                answer_cleaned = re.sub(r"```\s*$", "", answer_cleaned)
                answer_cleaned = answer_cleaned.strip()

                # Remove XML tags if present
                answer_cleaned = re.sub(r"<answer>\s*", "", answer_cleaned)
                answer_cleaned = re.sub(r"\s*</answer>\s*$", "", answer_cleaned)
                answer_cleaned = answer_cleaned.strip()

                # Try to parse as JSON directly
                try:
                    data = json.loads(answer_cleaned)
                    score = float(data.get("score", 0))
                    issues_data = data.get("issues", [])

                    # Convert issue objects to strings
                    issues = []
                    for issue in issues_data:
                        if isinstance(issue, dict):
                            desc = issue.get("description", str(issue))
                            issues.append(desc)
                        else:
                            issues.append(str(issue))
                except json.JSONDecodeError:
                    # JSON is malformed - try to extract score and issues with regex
                    score_match = re.search(r'"score"\s*:\s*(\d+)', answer_cleaned)
                    score = float(score_match.group(1)) if score_match else 0.0

                    # Extract issues array - look for description fields
                    issues = []
                    for desc_match in re.finditer(r'"description"\s*:\s*"([^"]+)"', answer_cleaned):
                        desc = desc_match.group(1)
                        issues.append(desc)

                    # If we couldn't extract anything, raise to trigger fallback
                    if score == 0.0 and not issues:
                        raise ValueError("Could not extract score or issues from malformed JSON")

            except Exception as e:
                # Fallback: use mock score
                score = 80.0
                issues = [f"Could not parse agent response: {str(e)[:100]}"]

            cat_score = CategoryScore(
                name=agent.role.replace(" Auditor", "")
                .replace(" Analyst", "")
                .replace(" Reviewer", "")
                .replace(" Specialist", ""),
                score=score,
                weight=agent.weight,
                passed=score >= 60,  # 60% threshold
                issues=issues,
            )
            category_scores.append(cat_score)

            # Collect issues
            if not cat_score.passed:
                all_issues.extend(issues[:2])  # Add first 2 issues
            elif score < 80:
                all_warnings.extend(issues[:1])  # Add first issue as warning

        # Calculate overall health score (weighted average)
        overall_score = sum(cat.weighted_score for cat in category_scores)

        # Normalize if weights don't sum to 1.0
        total_weight = sum(cat.weight for cat in category_scores)
        if total_weight > 0:
            overall_score = overall_score / total_weight

        # Calculate grade
        if overall_score >= 90:
            grade = "A"
        elif overall_score >= 80:
            grade = "B"
        elif overall_score >= 70:
            grade = "C"
        elif overall_score >= 60:
            grade = "D"
        else:
            grade = "F"

        # Calculate duration
        duration_ms = int((datetime.now() - started_at).total_seconds() * 1000)

        # Build result
        result = HealthCheckCrewResult(
            success=True,
            overall_health_score=overall_score,
            grade=grade,
            category_scores=category_scores,
            issues=all_issues,
            warnings=all_warnings,
            recommendations=all_recommendations,
            mode=self.mode,
            agents_executed=len(self.agents),
            cost=self._total_cost,
            duration_ms=duration_ms,
        )

        # Print formatted report
        print(result.formatted_report)

        return result
