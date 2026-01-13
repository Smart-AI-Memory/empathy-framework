"""Test Coverage Boost Crew - Multi-agent test generation workflow.

This module provides a CrewAI-based workflow that uses 3 specialized agents
to analyze coverage gaps, generate tests, and validate improvements.

Copyright 2025 Smart AI Memory, LLC
Licensed under Fair Source 0.9
"""

import asyncio
import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from empathy_os.models.executor import ExecutionContext


@dataclass
class Agent:
    """Agent configuration for test coverage boost."""

    role: str
    goal: str
    backstory: str
    expertise_level: str = "expert"
    weight: float = 1.0

    def get_system_prompt(self) -> str:
        """Generate system prompt for this agent."""
        return f"""You are a {self.role}.

{self.backstory}

Your goal: {self.goal}

Expertise level: {self.expertise_level}

Provide your response in this format:
<thinking>
[Your analysis and reasoning]
</thinking>

<answer>
[Your JSON response matching the expected format]
</answer>"""


@dataclass
class Task:
    """Task configuration for an agent."""

    description: str
    expected_output: str
    context_keys: list[str] = field(default_factory=list)

    def get_user_prompt(self, context: dict) -> str:
        """Generate user prompt with context data."""
        # Build context section
        context_lines = ["<context>"]
        for key in self.context_keys:
            if key in context:
                value = context[key]
                if isinstance(value, dict | list):
                    value = json.dumps(value, indent=2)
                context_lines.append(f"<{key}>")
                context_lines.append(str(value))
                context_lines.append(f"</{key}>")
        context_lines.append("</context>")

        return f"""{self.description}

{chr(10).join(context_lines)}

<expected_output>
{self.expected_output}
</expected_output>

<instructions>
1. Review all context data in the <context> tags above
2. Structure your response using <thinking> and <answer> tags
3. Provide a JSON response in the <answer> section matching the expected output format exactly
</instructions>"""


@dataclass
class CoverageGap:
    """Represents a gap in test coverage."""

    file_path: str
    function_name: str
    line_start: int
    line_end: int
    priority: float  # 0-1, higher = more important
    reason: str


@dataclass
class GeneratedTest:
    """Represents a generated test case."""

    test_name: str
    test_code: str
    target_function: str
    target_file: str
    coverage_impact: float  # Estimated coverage improvement


@dataclass
class TestCoverageBoostCrewResult:
    """Result from TestCoverageBoostCrew execution."""

    success: bool
    current_coverage: float  # 0-100
    target_coverage: float  # 0-100
    final_coverage: float  # 0-100
    coverage_improvement: float  # Percentage points gained

    # Detailed results
    gaps_found: int
    tests_generated: int
    tests_passing: int
    gaps_analyzed: list[CoverageGap] = field(default_factory=list)
    generated_tests: list[GeneratedTest] = field(default_factory=list)

    # Execution metadata
    agents_executed: int = 3
    cost: float = 0.0
    duration_ms: int = 0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    errors: list[str] = field(default_factory=list)


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


class TestCoverageBoostCrew:
    """Test Coverage Boost Crew - Multi-agent test generation.

    Uses 3 specialized agents to analyze coverage gaps, generate tests,
    and validate improvements.

    Agents:
    - Gap Analyzer: Identifies untested code and prioritizes gaps
    - Test Generator: Creates comprehensive test cases
    - Test Validator: Validates generated tests and measures improvement

    Usage:
        crew = TestCoverageBoostCrew(target_coverage=85.0)
        result = await crew.execute(project_root="./src")

        print(f"Coverage improved by {result.coverage_improvement}%")
    """

    name = "Test_Coverage_Boost_Crew"
    description = "Multi-agent test generation with gap analysis and validation"
    process_type = "sequential"

    def __init__(
        self,
        target_coverage: float = 80.0,
        project_root: str = ".",
        **kwargs,  # Accept extra CLI arguments
    ):
        """Initialize the test coverage boost crew.

        Args:
            target_coverage: Target coverage percentage (0-100)
            project_root: Root directory of project to analyze
            **kwargs: Additional arguments (ignored, for CLI compatibility)
        """
        if not 0 <= target_coverage <= 100:
            raise ValueError("target_coverage must be between 0 and 100")

        self.target_coverage = target_coverage
        self.project_root = Path(project_root).resolve()

        # Initialize tracking
        self._total_cost = 0.0
        self._total_input_tokens = 0
        self._total_output_tokens = 0
        self._executor = None
        self._project_index = None

        # Initialize ProjectIndex if available
        try:
            from empathy_os.project_index import ProjectIndex

            self._project_index = ProjectIndex(str(self.project_root))
            if not self._project_index.load():
                print("  [ProjectIndex] Building index (first run)...")
                self._project_index.refresh()
            else:
                print("  [ProjectIndex] Loaded existing index")
        except Exception as e:
            print(f"  [ProjectIndex] Warning: Could not load index: {e}")
            self._project_index = None

        # Define agents
        self.agents = [
            Agent(
                role="Gap Analyzer",
                goal="Identify critical gaps in test coverage and prioritize them",
                backstory="Expert code analyzer specializing in identifying untested code paths. "
                "You understand which functions are most critical to test based on complexity, "
                "usage patterns, and risk. You prioritize gaps by impact and provide actionable insights.",
                expertise_level="expert",
            ),
            Agent(
                role="Test Generator",
                goal="Generate comprehensive, high-quality test cases for coverage gaps",
                backstory="Senior test engineer who writes clean, maintainable, effective tests. "
                "You follow testing best practices, use appropriate assertions, cover edge cases, "
                "and write tests that are both thorough and readable.",
                expertise_level="expert",
            ),
            Agent(
                role="Test Validator",
                goal="Validate generated tests and measure coverage improvement",
                backstory="QA specialist focused on test quality and coverage metrics. "
                "You verify that tests are correct, run successfully, and actually improve coverage. "
                "You identify issues with generated tests and recommend fixes.",
                expertise_level="expert",
            ),
        ]

    def _initialize_executor(self):
        """Initialize LLM executor for agent calls."""
        if self._executor is not None:
            return

        try:
            from empathy_os.models.empathy_executor import EmpathyLLMExecutor

            self._executor = EmpathyLLMExecutor(provider="anthropic")
        except Exception as e:
            print(f"  [LLM] Warning: Could not initialize executor: {e}")
            print("  [LLM] Workflow will use mock responses")
            self._executor = None

    def define_tasks(self) -> list[Task]:
        """Define tasks for each agent."""
        return [
            Task(
                description="Analyze the codebase and identify critical test coverage gaps",
                expected_output="""JSON object with:
{
  "gaps": [
    {
      "file_path": "path/to/file.py",
      "function": "function_name",
      "line_start": 10,
      "line_end": 50,
      "priority": 0.9,
      "reason": "High complexity function with no tests"
    }
  ],
  "current_coverage": 65.0,
  "summary": "Found 5 critical gaps in high-impact files"
}""",
                context_keys=[
                    "project_root",
                    "target_coverage",
                    "project_stats",
                    "coverage_data",
                    "files_to_analyze",
                    "high_impact_files",
                ],
            ),
            Task(
                description="Generate comprehensive test cases for the identified coverage gaps",
                expected_output="""JSON object with properly escaped strings:
{
  "tests": [
    {
      "test_name": "test_function_name_edge_case",
      "test_code": "def test_function_name_edge_case():\\n    assert result == \\"expected\\"\\n    assert x != \\"bad\\"",
      "target_function": "function_name",
      "target_file": "path/to/file.py",
      "coverage_impact": 5.2
    }
  ],
  "total_tests": 5,
  "estimated_coverage_gain": 12.5
}

CRITICAL FORMATTING RULES:
1. ALWAYS escape quotes in test_code: Use \\" not "
2. Use \\n for newlines in test_code
3. Example CORRECT: "test_code": "def test():\\n    assert x == \\"value\\""
4. Example WRONG: "test_code": "def test(): assert x == "value""
5. Keep test_code concise - max 5 lines per test""",
                context_keys=["gaps", "project_root", "existing_tests"],
            ),
            Task(
                description="Validate the generated tests and measure actual coverage improvement",
                expected_output="""JSON object with:
{
  "tests_passing": 4,
  "tests_failing": 1,
  "final_coverage": 77.5,
  "coverage_improvement": 12.5,
  "issues": ["test_foo failed: assertion error"],
  "recommendations": ["Add fixture for database setup"]
}""",
                context_keys=["generated_tests", "target_coverage"],
            ),
        ]

    def _get_file_contents_for_analysis(self, files: list) -> list[dict]:
        """Read actual file contents for analysis.

        Args:
            files: List of FileRecord objects

        Returns:
            List of dicts with path, code, and metadata
        """
        result = []
        for file in files:
            try:
                file_path = self.project_root / file.path
                if not file_path.exists() or not file_path.suffix == ".py":
                    continue

                code = file_path.read_text(encoding="utf-8")

                # Limit code size to avoid token bloat (max ~5000 chars per file)
                if len(code) > 5000:
                    code = code[:5000] + f"\n... (truncated, {len(code)-5000} more chars)"

                result.append(
                    {
                        "path": str(file.path),
                        "complexity": file.complexity_score,
                        "lines": file.lines_of_code,
                        "has_test": file.tests_exist,
                        "coverage": file.coverage_percent,
                        "code": code,
                    }
                )
            except Exception:
                # Skip files that can't be read
                continue

        return result

    def _get_project_context(self) -> dict:
        """Get project context from ProjectIndex."""
        if self._project_index is None:
            return {
                "project_root": str(self.project_root),
                "target_coverage": self.target_coverage,
            }

        try:
            summary = self._project_index.get_summary()

            # Get files needing tests for gap analysis
            files_needing_tests = self._project_index.get_files_needing_tests()

            # Get high impact files for prioritization
            high_impact_files = self._project_index.get_high_impact_files()

            return {
                "project_root": str(self.project_root),
                "target_coverage": self.target_coverage,
                "project_stats": {
                    "total_files": summary.total_files,
                    "source_files": summary.source_files,
                    "test_files": summary.test_files,
                    "total_loc": summary.total_lines_of_code,
                    "avg_complexity": summary.avg_complexity,
                    "test_coverage_avg": summary.test_coverage_avg,
                },
                "coverage_data": {
                    "current_coverage": summary.test_coverage_avg,
                    "files_without_tests": summary.files_without_tests,
                    "files_needing_tests": len(files_needing_tests),
                },
                "files_to_analyze": self._get_file_contents_for_analysis(
                    files_needing_tests[:5]
                ),  # Top 5 files with code
                "high_impact_files": [
                    {
                        "path": str(file.path),
                        "impact_score": file.impact_score,
                        "complexity": file.complexity_score,
                        "lines": file.lines_of_code,
                    }
                    for file in high_impact_files[:5]  # Top 5 high-impact files
                ],
            }
        except Exception as e:
            print(f"  [ProjectIndex] Could not load project data: {e}")
            return {
                "project_root": str(self.project_root),
                "target_coverage": self.target_coverage,
            }

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
                task_type="test_generation",
                workflow_name="test-coverage-boost",
                step_name=agent.role,
            )

            # Execute with timeout using correct LLMExecutor API
            result = await asyncio.wait_for(
                self._executor.run(
                    task_type="test_generation",
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
        self,
        agent: Agent,
        task: Task,
        reason: str = "Executor not available",
    ) -> tuple[str, int, int, float]:
        """Return mock response when LLM is unavailable."""
        print(f"  [LLM] Using mock response for {agent.role}: {reason}")

        # Simple mock responses based on agent role
        if "Gap Analyzer" in agent.role:
            response = json.dumps(
                {
                    "gaps": [
                        {
                            "file_path": "src/core.py",
                            "function": "process_data",
                            "line_start": 10,
                            "line_end": 50,
                            "priority": 0.9,
                            "reason": "High complexity function with no tests",
                        }
                    ],
                    "current_coverage": 65.0,
                    "summary": "Mock response - no real gaps analyzed",
                }
            )
        elif "Test Generator" in agent.role:
            response = json.dumps({"tests": [], "total_tests": 0, "estimated_coverage_gain": 0.0})
        else:  # Validator
            response = json.dumps(
                {
                    "tests_passing": 0,
                    "tests_failing": 0,
                    "final_coverage": 65.0,
                    "coverage_improvement": 0.0,
                    "issues": ["Mock response - no real validation performed"],
                    "recommendations": [],
                }
            )

        return (response, 0, 0, 0.0)

    async def execute(
        self,
        project_root: str | None = None,
        context: dict | None = None,
        **kwargs,  # Accept extra parameters from CLI
    ) -> TestCoverageBoostCrewResult:
        """Execute the test coverage boost crew.

        Args:
            project_root: Path to project root (overrides init value)
            context: Additional context for agents
            **kwargs: Additional arguments (e.g., target_coverage passed by CLI)

        Returns:
            TestCoverageBoostCrewResult with detailed outcomes
        """
        if project_root:
            self.project_root = Path(project_root).resolve()

        # Merge kwargs into context for CLI compatibility
        context = context or {}
        context.update(kwargs)

        started_at = datetime.now()

        print("\n" + "=" * 70)
        print("  TEST COVERAGE BOOST CREW")
        print("=" * 70)
        print(f"\n  Project Root: {self.project_root}")
        print(f"  Target Coverage: {self.target_coverage}%")
        print(f"  Agents: {len(self.agents)} (sequential execution)")
        print("")

        # Initialize executor
        self._initialize_executor()

        # Get project context
        agent_context = self._get_project_context()
        agent_context.update(context)

        # Define tasks
        tasks = self.define_tasks()

        # Execute agents sequentially, passing results forward
        print("  🚀 Executing agents sequentially...\n")

        # Agent 1: Gap Analyzer
        print(f"     • {self.agents[0].role}")
        gap_response, _, _, _ = await self._call_llm(self.agents[0], tasks[0], agent_context)
        gap_data = self._parse_gap_analysis(gap_response)
        agent_context["gaps"] = gap_data.get("gaps", [])
        agent_context["current_coverage"] = gap_data.get("current_coverage", 0.0)

        # Agent 2: Test Generator
        print(f"     • {self.agents[1].role}")
        gen_response, _, _, _ = await self._call_llm(self.agents[1], tasks[1], agent_context)
        test_data = self._parse_test_generation(gen_response)
        agent_context["generated_tests"] = test_data.get("tests", [])

        # Agent 3: Test Validator
        print(f"     • {self.agents[2].role}")
        val_response, _, _, _ = await self._call_llm(self.agents[2], tasks[2], agent_context)
        validation_data = self._parse_validation(val_response)

        print("\n  ✓ All agents completed\n")

        # Build result
        current_coverage = gap_data.get("current_coverage", 0.0)
        final_coverage = validation_data.get("final_coverage", current_coverage)
        coverage_improvement = final_coverage - current_coverage

        # Parse gaps into CoverageGap objects
        gaps_analyzed = []
        for gap in gap_data.get("gaps", [])[:5]:  # Top 5 gaps
            gaps_analyzed.append(
                CoverageGap(
                    file_path=gap.get("file_path", "unknown"),
                    function_name=gap.get("function", "unknown"),
                    line_start=gap.get("line_start", 0),
                    line_end=gap.get("line_end", 0),
                    priority=gap.get("priority", 0.5),
                    reason=gap.get("reason", "No reason provided"),
                )
            )

        # Parse generated tests into GeneratedTest objects
        generated_tests = []
        for test in test_data.get("tests", []):
            generated_tests.append(
                GeneratedTest(
                    test_name=test.get("test_name", "test_unknown"),
                    test_code=test.get("test_code", ""),
                    target_function=test.get("target_function", "unknown"),
                    target_file=test.get("target_file", "unknown"),
                    coverage_impact=test.get("coverage_impact", 0.0),
                )
            )

        # Calculate duration
        duration_ms = int((datetime.now() - started_at).total_seconds() * 1000)

        result = TestCoverageBoostCrewResult(
            success=True,
            current_coverage=current_coverage,
            target_coverage=self.target_coverage,
            final_coverage=final_coverage,
            coverage_improvement=coverage_improvement,
            gaps_found=len(gap_data.get("gaps", [])),
            tests_generated=test_data.get("total_tests", 0),
            tests_passing=validation_data.get("tests_passing", 0),
            gaps_analyzed=gaps_analyzed,
            generated_tests=generated_tests,
            agents_executed=len(self.agents),
            cost=self._total_cost,
            duration_ms=duration_ms,
        )

        # Print formatted report
        print(self._format_report(result))

        return result

    def _parse_gap_analysis(self, response: str) -> dict:
        """Parse gap analysis response."""
        parsed = parse_xml_response(response)
        answer = parsed["answer"]

        # Clean up answer - strip ALL XML tags and code blocks
        answer = re.sub(r"</?answer>", "", answer)  # Remove all <answer> and </answer> tags
        answer = re.sub(r"```json\s*", "", answer)  # Remove ```json
        answer = re.sub(r"```\s*", "", answer)  # Remove closing ```
        answer = answer.strip()

        try:
            data = json.loads(answer)
            return data
        except json.JSONDecodeError:
            # Try regex extraction
            gaps = []
            current_coverage = 0.0

            # Extract coverage
            cov_match = re.search(r'"current_coverage"\s*:\s*(\d+\.?\d*)', answer)
            if cov_match:
                current_coverage = float(cov_match.group(1))

            return {
                "gaps": gaps,
                "current_coverage": current_coverage,
                "summary": "Could not parse gap analysis",
            }

    def _parse_test_generation(self, response: str) -> dict:
        """Parse test generation response."""
        parsed = parse_xml_response(response)
        answer = parsed["answer"]

        # Clean up answer - strip ALL XML tags and code blocks
        answer = re.sub(r"</?answer>", "", answer)  # Remove all <answer> and </answer> tags
        answer = re.sub(r"```json\s*", "", answer)  # Remove ```json
        answer = re.sub(r"```\s*", "", answer)  # Remove closing ```
        answer = answer.strip()

        try:
            data = json.loads(answer)
            return data
        except json.JSONDecodeError:
            # JSON parsing failed - attempt regex extraction
            tests = []

            # Pattern to extract test objects (handles malformed JSON)
            # More lenient pattern - looks for key fields in any order
            test_blocks = re.finditer(
                r'\{[^}]*"test_name"\s*:\s*"([^"]+)"[^}]*\}', answer, re.DOTALL
            )

            for match in test_blocks:
                block_text = match.group(0)

                # Extract test_name
                test_name_match = re.search(r'"test_name"\s*:\s*"([^"]+)"', block_text)
                test_name = test_name_match.group(1) if test_name_match else "test_unknown"

                # Extract test_code (handles escaped quotes)
                test_code_match = re.search(
                    r'"test_code"\s*:\s*"((?:[^"\\]|\\.)*?)"', block_text, re.DOTALL
                )
                test_code = test_code_match.group(1) if test_code_match else ""

                # Extract target_function
                func_match = re.search(r'"target_function"\s*:\s*"([^"]*)"', block_text)
                target_function = func_match.group(1) if func_match else "unknown"

                # Extract target_file
                file_match = re.search(r'"target_file"\s*:\s*"([^"]*)"', block_text)
                target_file = file_match.group(1) if file_match else "unknown"

                # Unescape the test code
                test_code = test_code.replace("\\n", "\n").replace('\\"', '"').replace("\\\\", "\\")

                tests.append(
                    {
                        "test_name": test_name,
                        "test_code": test_code,
                        "target_function": target_function,
                        "target_file": target_file,
                        "coverage_impact": 0.0,
                    }
                )

            # Try to extract total_tests
            total_tests = len(tests)
            total_match = re.search(r'"total_tests"\s*:\s*(\d+)', answer)
            if total_match:
                total_tests = max(total_tests, int(total_match.group(1)))

            # Extract estimated coverage gain
            coverage_gain = 0.0
            gain_match = re.search(r'"estimated_coverage_gain"\s*:\s*(\d+\.?\d*)', answer)
            if gain_match:
                coverage_gain = float(gain_match.group(1))

            return {
                "tests": tests,
                "total_tests": total_tests,
                "estimated_coverage_gain": coverage_gain,
            }

    def _parse_validation(self, response: str) -> dict:
        """Parse validation response."""
        parsed = parse_xml_response(response)
        answer = parsed["answer"]

        # Clean up answer - strip ALL XML tags and code blocks
        answer = re.sub(r"</?answer>", "", answer)  # Remove all <answer> and </answer> tags
        answer = re.sub(r"```json\s*", "", answer)  # Remove ```json
        answer = re.sub(r"```\s*", "", answer)  # Remove closing ```
        answer = answer.strip()

        try:
            data = json.loads(answer)
            return data
        except json.JSONDecodeError:
            return {
                "tests_passing": 0,
                "tests_failing": 0,
                "final_coverage": 0.0,
                "coverage_improvement": 0.0,
                "issues": ["Could not parse validation results"],
                "recommendations": [],
            }

    def _format_report(self, result: TestCoverageBoostCrewResult) -> str:
        """Format result as human-readable report."""
        lines = []

        lines.append("=" * 70)
        lines.append("TEST COVERAGE BOOST RESULTS")
        lines.append("=" * 70)
        lines.append("")
        lines.append(f"Current Coverage: {result.current_coverage:.1f}%")
        lines.append(f"Target Coverage: {result.target_coverage:.1f}%")
        lines.append(f"Final Coverage: {result.final_coverage:.1f}%")
        lines.append(f"Improvement: +{result.coverage_improvement:.1f}%")
        lines.append("")
        lines.append(f"Gaps Found: {result.gaps_found}")
        lines.append(f"Tests Generated: {result.tests_generated}")
        lines.append(f"Tests Passing: {result.tests_passing}")
        lines.append("")
        lines.append(f"Cost: ${result.cost:.4f}")
        lines.append(f"Duration: {result.duration_ms}ms ({result.duration_ms/1000:.1f}s)")
        lines.append("")

        if result.gaps_analyzed:
            lines.append("-" * 70)
            lines.append("TOP COVERAGE GAPS")
            lines.append("-" * 70)
            for i, gap in enumerate(result.gaps_analyzed[:5], 1):
                lines.append(
                    f"{i}. {gap.file_path}::{gap.function_name} (priority: {gap.priority:.2f})"
                )
                lines.append(f"   {gap.reason}")
            lines.append("")

        if result.generated_tests:
            lines.append("-" * 70)
            lines.append("GENERATED TESTS")
            lines.append("-" * 70)
            for i, test in enumerate(result.generated_tests[:3], 1):
                lines.append(f"{i}. {test.test_name}")
                lines.append(f"   Target: {test.target_file}::{test.target_function}")
                lines.append(f"   Impact: +{test.coverage_impact:.1f}%")
            lines.append("")

        lines.append("=" * 70)
        if result.coverage_improvement > 0:
            lines.append(f"✅ Coverage improved by {result.coverage_improvement:.1f}%")
        else:
            lines.append("⚠️  No coverage improvement achieved")
        lines.append("=" * 70)

        return "\n".join(lines)
