"""Release Preparation Crew - Multi-Agent Workflow

Comprehensive release readiness assessment using a multi-agent crew.

Pattern: Crew
- Multiple specialized AI agents collaborate on the task
- Process Type: parallel (agents run simultaneously)
- Agents: 4

Agents:
- Security Agent: Vulnerability scanning and security audit
- Testing Agent: Test coverage analysis and quality validation
- Quality Agent: Code quality review and best practices check
- Documentation Agent: Documentation completeness verification

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
class QualityGate:
    """Quality gate threshold for release readiness."""

    name: str
    threshold: float
    actual: float = 0.0
    passed: bool = False
    critical: bool = True
    message: str = ""

    def __post_init__(self):
        """Generate message if not provided."""
        if not self.message:
            status = "✅ PASS" if self.passed else "❌ FAIL"
            self.message = (
                f"{self.name}: {status} "
                f"(actual: {self.actual:.1f}, threshold: {self.threshold:.1f})"
            )


@dataclass
class ReleasePreparationCrewResult:
    """Result from ReleasePreparationCrew execution."""

    success: bool
    approved: bool  # Overall release approval
    confidence: str  # "high", "medium", "low"

    # Quality gates
    quality_gates: list[QualityGate] = field(default_factory=list)

    # Agent findings
    security_findings: dict = field(default_factory=dict)
    testing_findings: dict = field(default_factory=dict)
    quality_findings: dict = field(default_factory=dict)
    documentation_findings: dict = field(default_factory=dict)

    # Aggregate metrics
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)

    # Cost tracking
    cost: float = 0.0
    duration_ms: int = 0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        """Convert result to dictionary."""
        return {
            "success": self.success,
            "approved": self.approved,
            "confidence": self.confidence,
            "quality_gates": [
                {
                    "name": gate.name,
                    "threshold": gate.threshold,
                    "actual": gate.actual,
                    "passed": gate.passed,
                    "critical": gate.critical,
                    "message": gate.message,
                }
                for gate in self.quality_gates
            ],
            "security_findings": self.security_findings,
            "testing_findings": self.testing_findings,
            "quality_findings": self.quality_findings,
            "documentation_findings": self.documentation_findings,
            "blockers": self.blockers,
            "warnings": self.warnings,
            "recommendations": self.recommendations,
            "cost": self.cost,
            "duration_ms": self.duration_ms,
            "timestamp": self.timestamp,
        }

    @property
    def formatted_report(self) -> str:
        """Generate human-readable formatted report."""
        return format_release_prep_report(self)


@dataclass
class Agent:
    """Agent configuration for the crew with XML-enhanced prompting."""

    role: str
    goal: str
    backstory: str
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
4. Be specific and cite file paths when relevant
5. Structure your output according to the requested format
</instructions>

<output_structure>
Always structure your response as:

<thinking>
[Your step-by-step reasoning process]
- What you observe in the context
- How you analyze the situation
- What conclusions you draw
</thinking>

<answer>
[Your final output in the requested format]
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
                # Use underscores for tag names
                tag_name = key.replace(" ", "_").replace("-", "_").lower()
                # Wrap in appropriate tags
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
2. Structure your response using <thinking> and <answer> tags as defined in your system prompt
3. Match the expected output format exactly
4. Be thorough and specific in your analysis
</instructions>"""


def parse_xml_response(response: str) -> dict:
    """Parse XML-structured agent response.

    Args:
        response: Raw agent response potentially containing XML tags

    Returns:
        Dict with 'thinking' and 'answer' sections (if found) or raw response
    """
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

    # If no XML structure found, use full response as answer
    if not result["has_xml_structure"]:
        result["answer"] = response

    return result


def format_release_prep_report(result: ReleasePreparationCrewResult) -> str:
    """Format release preparation result as human-readable text."""
    lines = []

    # Header
    lines.append("=" * 70)
    lines.append("RELEASE READINESS REPORT (CrewAI Multi-Agent)")
    lines.append("=" * 70)
    lines.append("")

    # Status
    status_icon = "✅" if result.approved else "❌"
    status_text = "APPROVED FOR RELEASE" if result.approved else "NOT READY FOR RELEASE"
    lines.append(f"Status: {status_icon} {status_text}")
    lines.append(f"Confidence: {result.confidence.upper()}")
    lines.append(f"Generated: {result.timestamp}")
    lines.append(f"Duration: {result.duration_ms}ms ({result.duration_ms / 1000:.1f}s)")
    lines.append(f"Cost: ${result.cost:.4f}")
    lines.append("")

    # Quality Gates
    if result.quality_gates:
        lines.append("-" * 70)
        lines.append("QUALITY GATES")
        lines.append("-" * 70)
        for gate in result.quality_gates:
            icon = "✅" if gate.passed else ("🔴" if gate.critical else "⚠️")
            lines.append(f"{icon} {gate.message}")
        lines.append("")

    # Blockers
    if result.blockers:
        lines.append("-" * 70)
        lines.append("🚫 RELEASE BLOCKERS")
        lines.append("-" * 70)
        for blocker in result.blockers:
            lines.append(f"  • {blocker}")
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

    # Agent Findings Summary
    lines.append("-" * 70)
    lines.append("AGENT FINDINGS")
    lines.append("-" * 70)

    if result.security_findings:
        lines.append("\n🔒 Security Agent:")
        lines.append(f"   {result.security_findings.get('summary', 'No summary available')}")

    if result.testing_findings:
        lines.append("\n🧪 Testing Agent:")
        lines.append(f"   {result.testing_findings.get('summary', 'No summary available')}")

    if result.quality_findings:
        lines.append("\n⚡ Quality Agent:")
        lines.append(f"   {result.quality_findings.get('summary', 'No summary available')}")

    if result.documentation_findings:
        lines.append("\n📝 Documentation Agent:")
        lines.append(f"   {result.documentation_findings.get('summary', 'No summary available')}")

    lines.append("")

    # Footer
    lines.append("=" * 70)
    if result.approved:
        lines.append("✅ Release preparation complete - ready to ship")
    else:
        lines.append("❌ Release blocked - address issues above before shipping")
    lines.append("=" * 70)

    return "\n".join(lines)


class ReleasePreparationCrew:
    """Release Preparation Crew - Multi-agent release readiness assessment.

    Uses 4 specialized agents running in parallel to comprehensively
    evaluate release readiness across security, testing, quality, and documentation.

    Process Type: parallel

    Agents:
    - Security Agent: Vulnerability scanning and security audit
    - Testing Agent: Test coverage analysis and quality validation
    - Quality Agent: Code quality review and best practices check
    - Documentation Agent: Documentation completeness verification

    Usage:
        crew = ReleasePreparationCrew()
        result = await crew.execute(path="./src")

        if result.approved:
            print("✅ Ready for release!")
        else:
            for blocker in result.blockers:
                print(f"BLOCKER: {blocker}")
    """

    name = "Release_Preparation_Crew"
    description = "Comprehensive release readiness assessment using multi-agent crew"
    process_type = "parallel"

    def __init__(
        self, project_root: str = ".", quality_gates: dict[str, float] | None = None, **kwargs: Any
    ):
        """Initialize the crew with configured agents.

        Args:
            project_root: Root directory of project to analyze
            quality_gates: Optional quality gate thresholds
                - security: 0 critical issues (default)
                - coverage: 80% test coverage (default)
                - quality: 7.0 quality score (default)
                - documentation: 100% doc coverage (default)
            **kwargs: Additional configuration
        """
        self.config = kwargs
        self.project_root = project_root
        self._executor = None
        self._project_index = None
        self._total_cost = 0.0
        self._total_input_tokens = 0
        self._total_output_tokens = 0

        # Set default quality gates
        self.quality_gates = {
            "security": 0.0,  # No critical issues
            "coverage": 80.0,  # 80% test coverage
            "quality": 7.0,  # Quality score ≥ 7
            "documentation": 100.0,  # 100% doc coverage
        }
        if quality_gates:
            self.quality_gates.update(quality_gates)

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
                    # Index doesn't exist or is stale, refresh it
                    print("  [ProjectIndex] Building index (first run)...")
                    self._project_index.refresh()
            except Exception as e:
                print(f"  [ProjectIndex] Warning: Could not load index: {e}")

        # Define agents
        self.security_agent = Agent(
            role="Security Auditor",
            goal="Perform comprehensive security audit and vulnerability scan",
            backstory="Expert security auditor specializing in OWASP Top 10 vulnerabilities, dependency security, and security best practices. Skilled at identifying critical security issues that would block release.",
            expertise_level="expert",
        )

        self.testing_agent = Agent(
            role="Test Coverage Analyst",
            goal="Analyze test coverage and validate testing quality",
            backstory="Testing expert focused on test coverage metrics, test quality, and identifying critical gaps. Ensures adequate testing before release.",
            expertise_level="expert",
        )

        self.quality_agent = Agent(
            role="Code Quality Reviewer",
            goal="Review code quality and adherence to best practices",
            backstory="Senior code reviewer focused on code maintainability, complexity, and best practices. Identifies code quality issues that impact long-term project health.",
            expertise_level="expert",
        )

        self.documentation_agent = Agent(
            role="Documentation Specialist",
            goal="Verify documentation completeness and accuracy",
            backstory="Technical writer and documentation expert. Ensures all code is properly documented, README is up-to-date, and API docs are complete.",
            expertise_level="expert",
        )

        # Store all agents
        self.agents = [
            self.security_agent,
            self.testing_agent,
            self.quality_agent,
            self.documentation_agent,
        ]

    def define_tasks(self) -> list[Task]:
        """Define the tasks for this crew."""
        return [
            Task(
                description=f"Perform security audit: 1) Scan for OWASP Top 10 vulnerabilities, 2) Check dependency security, 3) Review authentication/authorization, 4) Identify critical security issues. Quality gate: ≤{self.quality_gates['security']} critical issues",
                expected_output="JSON with: critical_issues_count, high_issues_count, findings (list of issues with severity/details), recommendation (GO/NO_GO)",
                agent=self.security_agent,
            ),
            Task(
                description=f"Analyze test coverage: 1) Calculate current test coverage percentage, 2) Identify critical gaps in coverage, 3) Assess test quality, 4) Verify tests pass. Quality gate: ≥{self.quality_gates['coverage']}% coverage",
                expected_output="JSON with: coverage_percentage, critical_gaps_count, tests_passing (true/false), recommendation (GO/NO_GO)",
                agent=self.testing_agent,
            ),
            Task(
                description=f"Review code quality: 1) Calculate code quality score (0-10), 2) Check for code smells and anti-patterns, 3) Verify linting passes, 4) Assess maintainability. Quality gate: ≥{self.quality_gates['quality']} quality score",
                expected_output="JSON with: quality_score, complexity_issues, linting_errors, recommendation (GO/NO_GO)",
                agent=self.quality_agent,
            ),
            Task(
                description=f"Verify documentation: 1) Check docstring coverage, 2) Verify README is current, 3) Validate API documentation, 4) Check for missing docs. Quality gate: ≥{self.quality_gates['documentation']}% doc coverage",
                expected_output="JSON with: docstring_coverage_percentage, readme_current (true/false), missing_docs_count, recommendation (GO/NO_GO)",
                agent=self.documentation_agent,
            ),
        ]

    async def _call_llm(
        self,
        agent: Agent,
        task: Task,
        context: dict,
        task_type: str = "release_validation",
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
                task_type=task_type,
                workflow_name="release-prep",
                step_name=agent.role,
            )

            # Execute with timeout using correct LLMExecutor API
            result = await asyncio.wait_for(
                self._executor.run(
                    task_type=task_type,
                    prompt=user_prompt,
                    system=system_prompt,
                    context=exec_context,
                ),
                timeout=120.0,  # 2 minute timeout
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
        # Simulate brief delay
        await asyncio.sleep(0.1)

        mock_findings = {
            "Security Auditor": f"""[Mock Security Audit - {reason}]

<thinking>
Performing security audit of the codebase...
- Scanning for OWASP Top 10 vulnerabilities
- Checking dependency versions
- Reviewing authentication mechanisms
</thinking>

<answer>
{{
  "critical_issues_count": 0,
  "high_issues_count": 2,
  "findings": [
    {{"severity": "high", "details": "Outdated dependency: requests 2.25.0 (CVE-2024-XXXX)"}},
    {{"severity": "medium", "details": "Missing rate limiting on API endpoints"}}
  ],
  "recommendation": "GO (no critical blockers, address high issues post-release)"
}}
</answer>

Note: This is a mock response. Configure ANTHROPIC_API_KEY for real analysis.""",
            "Test Coverage Analyst": f"""[Mock Coverage Analysis - {reason}]

<thinking>
Analyzing test coverage across the codebase...
- Running coverage tools
- Identifying critical gaps
- Verifying tests pass
</thinking>

<answer>
{{
  "coverage_percentage": 75.5,
  "critical_gaps_count": 3,
  "tests_passing": true,
  "recommendation": "NO_GO (coverage below 80% threshold)"
}}
</answer>

Note: This is a mock response. Configure ANTHROPIC_API_KEY for real analysis.""",
            "Code Quality Reviewer": f"""[Mock Quality Review - {reason}]

<thinking>
Reviewing code quality metrics...
- Calculating complexity scores
- Checking linting status
- Assessing maintainability
</thinking>

<answer>
{{
  "quality_score": 8.2,
  "complexity_issues": 2,
  "linting_errors": 0,
  "recommendation": "GO (quality score above threshold)"
}}
</answer>

Note: This is a mock response. Configure ANTHROPIC_API_KEY for real analysis.""",
            "Documentation Specialist": f"""[Mock Documentation Check - {reason}]

<thinking>
Verifying documentation completeness...
- Checking docstring coverage
- Reviewing README currency
- Validating API docs
</thinking>

<answer>
{{
  "docstring_coverage_percentage": 92.0,
  "readme_current": false,
  "missing_docs_count": 5,
  "recommendation": "CONDITIONAL (README needs update)"
}}
</answer>

Note: This is a mock response. Configure ANTHROPIC_API_KEY for real analysis.""",
        }

        response = mock_findings.get(agent.role, f"Mock response for {agent.role}")
        return (response, 0, 0, 0.0)

    def _get_index_context(self) -> dict[str, Any]:
        """Get release validation context from ProjectIndex if available."""
        if self._project_index is None:
            return {}

        try:
            return self._project_index.get_context_for_workflow("release_prep")
        except Exception as e:
            print(f"  [ProjectIndex] Warning: Could not get context: {e}")
            return {}

    async def execute(
        self,
        path: str = ".",
        context: dict | None = None,
        **kwargs: Any,
    ) -> ReleasePreparationCrewResult:
        """Execute the release preparation crew.

        Args:
            path: Path to analyze for release readiness
            context: Additional context for agents
            **kwargs: Additional arguments

        Returns:
            ReleasePreparationCrewResult with approval status and findings
        """
        started_at = datetime.now()
        context = context or {}

        print("\n" + "=" * 70)
        print("  RELEASE PREPARATION CREW (CrewAI)")
        print("=" * 70)
        print(f"\n  Project Path: {path}")
        print(f"  Agents: {len(self.agents)} (running in parallel)")
        print("")

        # Try to get rich context from ProjectIndex
        index_context = self._get_index_context()

        if index_context:
            print("  [ProjectIndex] Using indexed project data")
            agent_context = {
                "path": path,
                **index_context,
                **context,
            }
        else:
            # Fallback: basic context
            agent_context = {
                "path": path,
                "quality_gates": self.quality_gates,
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

        # Parse agent responses
        agent_findings = []
        for agent, _task, (response, _input_tokens, _output_tokens, _cost) in zip(
            self.agents, tasks, results, strict=False
        ):
            parsed = parse_xml_response(response)
            agent_findings.append(
                {
                    "agent": agent.role,
                    "response": response,
                    "thinking": parsed["thinking"],
                    "answer": parsed["answer"],
                    "has_xml_structure": parsed["has_xml_structure"],
                    "cost": _cost,
                    "input_tokens": _input_tokens,
                    "output_tokens": _output_tokens,
                }
            )

        # Extract structured findings from each agent
        security_findings = self._extract_security_findings(agent_findings[0])
        testing_findings = self._extract_testing_findings(agent_findings[1])
        quality_findings = self._extract_quality_findings(agent_findings[2])
        documentation_findings = self._extract_documentation_findings(agent_findings[3])

        # Evaluate quality gates
        quality_gates = self._evaluate_quality_gates(
            security_findings, testing_findings, quality_findings, documentation_findings
        )

        # Determine approval status
        blockers = []
        warnings = []
        recommendations = []

        for gate in quality_gates:
            if not gate.passed:
                if gate.critical:
                    blockers.append(f"{gate.name} failed: {gate.message}")
                else:
                    warnings.append(f"{gate.name} below threshold: {gate.message}")

        approved = len(blockers) == 0
        confidence = (
            "high" if approved and len(warnings) == 0 else ("medium" if approved else "low")
        )

        # Calculate duration
        duration_ms = int((datetime.now() - started_at).total_seconds() * 1000)

        # Build result
        result = ReleasePreparationCrewResult(
            success=True,
            approved=approved,
            confidence=confidence,
            quality_gates=quality_gates,
            security_findings=security_findings,
            testing_findings=testing_findings,
            quality_findings=quality_findings,
            documentation_findings=documentation_findings,
            blockers=blockers,
            warnings=warnings,
            recommendations=recommendations,
            cost=self._total_cost,
            duration_ms=duration_ms,
        )

        # Add formatted report
        print(result.formatted_report)

        return result

    def _parse_json_answer(self, answer: str) -> dict | None:
        """Parse JSON from agent answer, handling markdown code blocks.

        Args:
            answer: Agent answer text (may contain ```json...```)

        Returns:
            Parsed JSON dict or None if parsing fails
        """
        import json
        import re

        try:
            # Remove markdown code blocks if present
            answer_cleaned = re.sub(r"```json\s*", "", answer)
            answer_cleaned = re.sub(r"```\s*$", "", answer_cleaned)
            answer_cleaned = answer_cleaned.strip()

            # Parse as JSON
            return json.loads(answer_cleaned)
        except Exception:
            return None

    def _extract_security_findings(self, agent_finding: dict) -> dict:
        """Extract structured security findings from agent response."""
        answer = agent_finding.get("answer", "")
        data = self._parse_json_answer(answer)

        if data:
            return {
                "critical_count": data.get("critical_issues_count", 0),
                "high_count": data.get("high_issues_count", 0),
                "findings": data.get("findings", []),
                "recommendation": data.get("recommendation", "UNKNOWN"),
                "summary": f"{data.get('critical_issues_count', 0)} critical, {data.get('high_issues_count', 0)} high issues found",
            }

        # Fallback
        return {
            "critical_count": 0,
            "high_count": 0,
            "findings": [],
            "recommendation": "UNKNOWN",
            "summary": "Could not parse security findings",
        }

    def _extract_testing_findings(self, agent_finding: dict) -> dict:
        """Extract structured testing findings from agent response."""
        answer = agent_finding.get("answer", "")
        data = self._parse_json_answer(answer)

        if data:
            return {
                "coverage": data.get("coverage_percentage", 0.0),
                "gaps_count": data.get("critical_gaps_count", 0),
                "tests_passing": data.get("tests_passing", False),
                "recommendation": data.get("recommendation", "UNKNOWN"),
                "summary": f"{data.get('coverage_percentage', 0)}% coverage, {data.get('critical_gaps_count', 0)} critical gaps",
            }

        return {
            "coverage": 0.0,
            "gaps_count": 0,
            "tests_passing": False,
            "recommendation": "UNKNOWN",
            "summary": "Could not parse testing findings",
        }

    def _extract_quality_findings(self, agent_finding: dict) -> dict:
        """Extract structured quality findings from agent response."""
        answer = agent_finding.get("answer", "")
        data = self._parse_json_answer(answer)

        if data:
            return {
                "quality_score": data.get("quality_score", 0.0),
                "complexity_issues": data.get("complexity_issues", 0),
                "linting_errors": data.get("linting_errors", 0),
                "recommendation": data.get("recommendation", "UNKNOWN"),
                "summary": f"Quality score: {data.get('quality_score', 0)}/10, {data.get('complexity_issues', 0)} complexity issues",
            }

        return {
            "quality_score": 0.0,
            "complexity_issues": 0,
            "linting_errors": 0,
            "recommendation": "UNKNOWN",
            "summary": "Could not parse quality findings",
        }

    def _extract_documentation_findings(self, agent_finding: dict) -> dict:
        """Extract structured documentation findings from agent response."""
        answer = agent_finding.get("answer", "")
        data = self._parse_json_answer(answer)

        if data:
            return {
                "docstring_coverage": data.get("docstring_coverage_percentage", 0.0),
                "readme_current": data.get("readme_current", False),
                "missing_docs_count": data.get("missing_docs_count", 0),
                "recommendation": data.get("recommendation", "UNKNOWN"),
                "summary": f"{data.get('docstring_coverage_percentage', 0)}% docstring coverage, README {'current' if data.get('readme_current') else 'needs update'}",
            }

        return {
            "docstring_coverage": 0.0,
            "readme_current": False,
            "missing_docs_count": 0,
            "recommendation": "UNKNOWN",
            "summary": "Could not parse documentation findings",
        }

    def _evaluate_quality_gates(
        self,
        security_findings: dict,
        testing_findings: dict,
        quality_findings: dict,
        documentation_findings: dict,
    ) -> list[QualityGate]:
        """Evaluate quality gates based on agent findings."""
        gates = []

        # Security gate: no critical issues
        sec_gate = QualityGate(
            name="Security",
            threshold=self.quality_gates["security"],
            actual=float(security_findings.get("critical_count", 0)),
            critical=True,
        )
        sec_gate.passed = sec_gate.actual <= sec_gate.threshold
        gates.append(sec_gate)

        # Test coverage gate
        cov_gate = QualityGate(
            name="Test Coverage",
            threshold=self.quality_gates["coverage"],
            actual=testing_findings.get("coverage", 0.0),
            critical=True,
        )
        cov_gate.passed = cov_gate.actual >= cov_gate.threshold
        gates.append(cov_gate)

        # Code quality gate
        qual_gate = QualityGate(
            name="Code Quality",
            threshold=self.quality_gates["quality"],
            actual=quality_findings.get("quality_score", 0.0),
            critical=True,
        )
        qual_gate.passed = qual_gate.actual >= qual_gate.threshold
        gates.append(qual_gate)

        # Documentation gate
        doc_gate = QualityGate(
            name="Documentation",
            threshold=self.quality_gates["documentation"],
            actual=documentation_findings.get("docstring_coverage", 0.0),
            critical=False,  # Non-critical warning
        )
        doc_gate.passed = doc_gate.actual >= doc_gate.threshold
        gates.append(doc_gate)

        return gates
