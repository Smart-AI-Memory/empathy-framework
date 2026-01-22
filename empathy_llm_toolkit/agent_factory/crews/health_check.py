"""Health Check Crew

A multi-agent crew that diagnoses and fixes project health issues.
Uses XML-enhanced prompts for structured, consistent output.

Agents:
1. Health Lead (Coordinator) - Orchestrates checks, prioritizes fixes
2. Lint Fixer - Runs ruff, generates auto-fix patches
3. Type Resolver - Runs mypy, suggests type annotations
4. Test Doctor - Runs pytest, diagnoses and fixes test failures
5. Dep Auditor - Checks outdated/vulnerable dependencies

Usage:
    from empathy_llm_toolkit.agent_factory.crews import HealthCheckCrew

    crew = HealthCheckCrew(api_key="...")
    report = await crew.check(path=".", auto_fix=True)

    print(f"Health Score: {report.health_score}")
    for fix in report.applied_fixes:
        print(f"  Fixed: {fix.title}")

Copyright 2025 Smart-AI-Memory
Licensed under Fair Source License 0.9
"""

import logging
import subprocess
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class HealthCategory(Enum):
    """Health check categories."""

    LINT = "lint"
    TYPES = "types"
    TESTS = "tests"
    DEPENDENCIES = "dependencies"
    SECURITY = "security"
    GENERAL = "general"


class IssueSeverity(Enum):
    """Issue severity levels."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class FixStatus(Enum):
    """Status of an attempted fix."""

    APPLIED = "applied"
    SUGGESTED = "suggested"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class HealthIssue:
    """A single health issue found."""

    title: str
    description: str
    category: HealthCategory
    severity: IssueSeverity
    file_path: str | None = None
    line_number: int | None = None
    code_snippet: str | None = None
    tool: str | None = None
    rule_id: str | None = None
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert issue to dictionary."""
        return {
            "title": self.title,
            "description": self.description,
            "category": self.category.value,
            "severity": self.severity.value,
            "file_path": self.file_path,
            "line_number": self.line_number,
            "code_snippet": self.code_snippet,
            "tool": self.tool,
            "rule_id": self.rule_id,
            "metadata": self.metadata,
        }


@dataclass
class HealthFix:
    """A fix applied or suggested."""

    title: str
    description: str
    category: HealthCategory
    status: FixStatus
    file_path: str | None = None
    before_code: str | None = None
    after_code: str | None = None
    patch: str | None = None
    related_issues: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert fix to dictionary."""
        return {
            "title": self.title,
            "description": self.description,
            "category": self.category.value,
            "status": self.status.value,
            "file_path": self.file_path,
            "before_code": self.before_code,
            "after_code": self.after_code,
            "patch": self.patch,
            "related_issues": self.related_issues,
            "metadata": self.metadata,
        }


@dataclass
class HealthCheckReport:
    """Complete health check report."""

    target: str
    issues: list[HealthIssue]
    fixes: list[HealthFix]
    health_score: float
    check_duration_seconds: float = 0.0
    agents_used: list[str] = field(default_factory=list)
    memory_graph_hits: int = 0
    checks_run: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)

    @property
    def critical_issues(self) -> list[HealthIssue]:
        """Get critical severity issues."""
        return [i for i in self.issues if i.severity == IssueSeverity.CRITICAL]

    @property
    def applied_fixes(self) -> list[HealthFix]:
        """Get successfully applied fixes."""
        return [f for f in self.fixes if f.status == FixStatus.APPLIED]

    @property
    def issues_by_category(self) -> dict[str, list[HealthIssue]]:
        """Group issues by category."""
        result: dict[str, list[HealthIssue]] = {}
        for issue in self.issues:
            cat = issue.category.value
            if cat not in result:
                result[cat] = []
            result[cat].append(issue)
        return result

    @property
    def is_healthy(self) -> bool:
        """Check if project is healthy (score >= 80)."""
        return self.health_score >= 80.0

    def to_dict(self) -> dict:
        """Convert report to dictionary."""
        return {
            "target": self.target,
            "issues": [i.to_dict() for i in self.issues],
            "fixes": [f.to_dict() for f in self.fixes],
            "health_score": self.health_score,
            "check_duration_seconds": self.check_duration_seconds,
            "agents_used": self.agents_used,
            "memory_graph_hits": self.memory_graph_hits,
            "checks_run": self.checks_run,
            "is_healthy": self.is_healthy,
            "issue_counts": {
                "critical": len(self.critical_issues),
                "total": len(self.issues),
                "by_category": {k: len(v) for k, v in self.issues_by_category.items()},
            },
            "fix_counts": {
                "applied": len(self.applied_fixes),
                "total": len(self.fixes),
            },
            "metadata": self.metadata,
        }


@dataclass
class HealthCheckConfig:
    """Configuration for health check crew."""

    # API Configuration
    provider: str = "anthropic"
    api_key: str | None = None

    # Check Configuration
    check_lint: bool = True
    check_types: bool = True
    check_tests: bool = True
    check_deps: bool = True
    auto_fix: bool = False  # Apply fixes automatically
    fix_safe_only: bool = True  # Only apply safe fixes

    # Paths
    target_path: str = "."
    exclude_paths: list[str] = field(default_factory=lambda: [".git", "venv", "__pycache__"])

    # Memory Graph
    memory_graph_enabled: bool = True
    memory_graph_path: str = "patterns/health_check_memory.json"

    # Agent Tiers
    lead_tier: str = "premium"
    lint_tier: str = "capable"
    types_tier: str = "capable"
    tests_tier: str = "capable"
    deps_tier: str = "capable"

    # XML Prompts
    xml_prompts_enabled: bool = True
    xml_schema_version: str = "1.0"

    # Resilience
    resilience_enabled: bool = True
    timeout_seconds: float = 300.0


# XML Prompt Templates for Health Check Agents
XML_PROMPT_TEMPLATES = {
    "health_lead": """<agent role="health_lead" version="{schema_version}">
  <identity>
    <role>Health Check Coordinator</role>
    <expertise>Project health assessment, issue prioritization, fix orchestration</expertise>
  </identity>

  <goal>
    Coordinate the health check team to diagnose and fix project issues.
    Synthesize findings from all agents into a prioritized action plan.
  </goal>

  <instructions>
    <step>Review health check results from all team members</step>
    <step>Prioritize issues by severity and impact</step>
    <step>Identify quick wins (easy fixes with high impact)</step>
    <step>Create an ordered fix plan</step>
    <step>Calculate overall health score (0-100)</step>
    <step>Generate executive summary with recommendations</step>
  </instructions>

  <constraints>
    <rule>Be conservative with auto-fix recommendations</rule>
    <rule>Prioritize breaking issues first</rule>
    <rule>Consider fix dependencies (some fixes enable others)</rule>
    <rule>Flag risky fixes that need human review</rule>
  </constraints>

  <output_format>
    <section name="summary">Executive summary of health status</section>
    <section name="health_score">Numeric score 0-100</section>
    <section name="critical_issues">Blocking issues requiring immediate attention</section>
    <section name="fix_plan">Ordered list of recommended fixes</section>
    <section name="metrics">Lint errors, type errors, test failures, dep issues</section>
  </output_format>
</agent>""",
    "lint_fixer": """<agent role="lint_fixer" version="{schema_version}">
  <identity>
    <role>Lint Analyst & Fixer</role>
    <expertise>Code style, ruff rules, auto-formatting, code quality</expertise>
  </identity>

  <goal>
    Analyze lint issues and generate fixes. Apply safe auto-fixes when enabled.
  </goal>

  <instructions>
    <step>Parse ruff output to identify all lint violations</step>
    <step>Categorize by rule type (style, error, security)</step>
    <step>Identify auto-fixable issues (ruff --fix compatible)</step>
    <step>Generate patch for complex issues requiring manual fix</step>
    <step>Explain why each fix is necessary</step>
  </instructions>

  <constraints>
    <rule>Only auto-fix style and formatting issues</rule>
    <rule>Flag security-related lint issues as high priority</rule>
    <rule>Preserve code semantics - never change behavior</rule>
    <rule>Respect noqa comments and intentional suppressions</rule>
  </constraints>

  <tools>
    <tool name="ruff">python -m ruff check --output-format=json</tool>
    <tool name="ruff_fix">python -m ruff check --fix</tool>
  </tools>

  <output_format>
    <section name="issues">List of lint issues with file, line, rule, message</section>
    <section name="auto_fixable">Issues that can be auto-fixed</section>
    <section name="manual_fixes">Issues requiring manual intervention with suggested code</section>
    <section name="summary">Count by category and severity</section>
  </output_format>
</agent>""",
    "type_resolver": """<agent role="type_resolver" version="{schema_version}">
  <identity>
    <role>Type Error Resolver</role>
    <expertise>Python type hints, mypy, type inference, generic types</expertise>
  </identity>

  <goal>
    Diagnose type errors and suggest type annotations to resolve them.
  </goal>

  <instructions>
    <step>Parse mypy output to identify all type errors</step>
    <step>Categorize errors (missing annotation, incompatible types, etc.)</step>
    <step>Infer correct types from context and usage</step>
    <step>Generate type stub suggestions for third-party libraries</step>
    <step>Suggest incremental typing strategy for untyped code</step>
  </instructions>

  <constraints>
    <rule>Prefer simple types over complex generics when possible</rule>
    <rule>Use | union syntax (Python 3.10+) over Union</rule>
    <rule>Suggest Any only as last resort</rule>
    <rule>Consider runtime type checking implications</rule>
  </constraints>

  <tools>
    <tool name="mypy">python -m mypy --output=json</tool>
  </tools>

  <output_format>
    <section name="errors">List of type errors with file, line, message</section>
    <section name="fixes">Suggested type annotations for each error</section>
    <section name="stubs">Type stubs needed for third-party packages</section>
    <section name="summary">Error count and typing coverage estimate</section>
  </output_format>
</agent>""",
    "test_doctor": """<agent role="test_doctor" version="{schema_version}">
  <identity>
    <role>Test Failure Diagnostician</role>
    <expertise>pytest, test fixtures, mocking, assertion debugging</expertise>
  </identity>

  <goal>
    Diagnose test failures and suggest fixes to make tests pass.
  </goal>

  <instructions>
    <step>Parse pytest output to identify failing tests</step>
    <step>Analyze failure type (assertion, exception, timeout, fixture)</step>
    <step>Determine root cause (test bug vs code bug)</step>
    <step>Generate fix for test-side issues</step>
    <step>Flag code-side issues for other agents</step>
    <step>Identify flaky tests that need stabilization</step>
  </instructions>

  <constraints>
    <rule>Distinguish between test bugs and code bugs</rule>
    <rule>Never suggest removing assertions to fix tests</rule>
    <rule>Prefer fixing test setup over mocking more</rule>
    <rule>Flag tests that test implementation not behavior</rule>
  </constraints>

  <tools>
    <tool name="pytest">python -m pytest --tb=short -q</tool>
    <tool name="pytest_collect">python -m pytest --collect-only -q</tool>
  </tools>

  <output_format>
    <section name="failures">List of failing tests with traceback summary</section>
    <section name="diagnosis">Root cause analysis for each failure</section>
    <section name="test_fixes">Fixes for test-side issues</section>
    <section name="code_issues">Code bugs discovered via tests</section>
    <section name="summary">Pass/fail counts and coverage if available</section>
  </output_format>
</agent>""",
    "dep_auditor": """<agent role="dep_auditor" version="{schema_version}">
  <identity>
    <role>Dependency Auditor</role>
    <expertise>pip, package versions, security advisories, compatibility</expertise>
  </identity>

  <goal>
    Audit dependencies for security vulnerabilities and outdated packages.
  </goal>

  <instructions>
    <step>Parse requirements.txt/pyproject.toml for dependencies</step>
    <step>Check for known security vulnerabilities (pip-audit)</step>
    <step>Identify outdated packages with available updates</step>
    <step>Assess update risk (major vs minor vs patch)</step>
    <step>Check for dependency conflicts</step>
    <step>Suggest safe update path</step>
  </instructions>

  <constraints>
    <rule>Prioritize security vulnerabilities over outdated packages</rule>
    <rule>Be conservative with major version upgrades</rule>
    <rule>Check changelog for breaking changes before suggesting upgrades</rule>
    <rule>Consider transitive dependency impacts</rule>
  </constraints>

  <tools>
    <tool name="pip_audit">pip-audit --format=json</tool>
    <tool name="pip_outdated">pip list --outdated --format=json</tool>
  </tools>

  <output_format>
    <section name="vulnerabilities">Security issues with CVE and severity</section>
    <section name="outdated">Packages with available updates</section>
    <section name="conflicts">Dependency conflicts detected</section>
    <section name="update_plan">Safe update sequence</section>
    <section name="summary">Vulnerability count and overall dep health</section>
  </output_format>
</agent>""",
}


class HealthCheckCrew:
    """Multi-agent crew for project health diagnosis and fixing.

    The crew consists of 5 specialized agents using XML-enhanced prompts:

    1. **Health Lead** (Coordinator)
       - Orchestrates the health check team
       - Synthesizes findings from all agents
       - Prioritizes fixes by impact
       - Calculates health score
       - Model: Premium tier

    2. **Lint Fixer** (Analyst)
       - Runs ruff for lint checking
       - Identifies auto-fixable issues
       - Generates patches for manual fixes
       - Model: Capable tier

    3. **Type Resolver** (Analyst)
       - Runs mypy for type checking
       - Suggests type annotations
       - Generates type stubs
       - Model: Capable tier

    4. **Test Doctor** (Analyst)
       - Runs pytest for test checking
       - Diagnoses test failures
       - Distinguishes test bugs from code bugs
       - Model: Capable tier

    5. **Dep Auditor** (Analyst)
       - Checks for vulnerabilities
       - Identifies outdated packages
       - Suggests safe update paths
       - Model: Capable tier

    Example:
        crew = HealthCheckCrew(api_key="...")
        report = await crew.check(path=".", auto_fix=True)

        if report.is_healthy:
            print("Project is healthy!")
        else:
            print(f"Health Score: {report.health_score}/100")
            for issue in report.critical_issues:
                print(f"  - {issue.title}")

    """

    def __init__(self, config: HealthCheckConfig | None = None, **kwargs: Any):
        """Initialize the Health Check Crew.

        Args:
            config: HealthCheckConfig or pass individual params as kwargs
            **kwargs: Individual config parameters (api_key, provider, etc.)

        """
        if config:
            self.config = config
        else:
            self.config = HealthCheckConfig(**kwargs)

        self._factory: Any = None
        self._agents: dict[str, Any] = {}
        self._workflow: Any = None
        self._graph: Any = None
        self._initialized = False

    def _render_xml_prompt(self, template_key: str) -> str:
        """Render XML prompt template with config values."""
        template = XML_PROMPT_TEMPLATES.get(template_key, "")
        return template.format(schema_version=self.config.xml_schema_version)

    def _get_system_prompt(self, agent_key: str, fallback: str) -> str:
        """Get system prompt - XML if enabled, fallback otherwise."""
        if self.config.xml_prompts_enabled:
            return self._render_xml_prompt(agent_key)
        return fallback

    async def _initialize(self) -> None:
        """Lazy initialization of agents and workflow."""
        if self._initialized:
            return

        from empathy_llm_toolkit.agent_factory import AgentFactory, Framework

        # Check if CrewAI is available
        try:
            from empathy_llm_toolkit.agent_factory.adapters.crewai_adapter import _check_crewai

            use_crewai = _check_crewai()
        except ImportError:
            use_crewai = False

        # Use CrewAI if available, otherwise fall back to Native
        framework = Framework.CREWAI if use_crewai else Framework.NATIVE

        self._factory = AgentFactory(
            framework=framework,
            provider=self.config.provider,
            api_key=self.config.api_key,
        )

        # Initialize Memory Graph if enabled
        if self.config.memory_graph_enabled:
            try:
                from empathy_os.memory import MemoryGraph

                self._graph = MemoryGraph(path=self.config.memory_graph_path)
            except ImportError:
                logger.warning("Memory Graph not available, continuing without it")

        # Create the 5 specialized agents
        await self._create_agents()

        # Create hierarchical workflow
        await self._create_workflow()

        self._initialized = True

    async def _create_agents(self) -> None:
        """Create the 5 specialized health check agents with XML prompts."""
        # 1. Health Lead (Coordinator)
        self._agents["lead"] = self._factory.create_agent(
            name="health_lead",
            role="coordinator",
            description="Senior engineer who orchestrates the health check team",
            system_prompt=self._get_system_prompt(
                "health_lead",
                """You are the Health Lead, coordinating project health checks.

Your responsibilities:
1. Coordinate the health check team
2. Synthesize findings from all checkers
3. Prioritize issues by severity and impact
4. Calculate overall health score (0-100)
5. Generate actionable fix plan

Health Score calculation:
- Start at 100
- Deduct 25 per critical issue
- Deduct 10 per high issue
- Deduct 3 per medium issue
- Deduct 1 per low issue

Be constructive and prioritize quick wins.""",
            ),
            model_tier=self.config.lead_tier,
            memory_graph_enabled=self.config.memory_graph_enabled,
            memory_graph_path=self.config.memory_graph_path,
            resilience_enabled=self.config.resilience_enabled,
        )

        # 2. Lint Fixer
        self._agents["lint"] = self._factory.create_agent(
            name="lint_fixer",
            role="analyst",
            description="Expert at identifying and fixing lint issues",
            system_prompt=self._get_system_prompt(
                "lint_fixer",
                """You are the Lint Fixer, a code quality expert.

Your focus:
1. Parse ruff output for lint violations
2. Categorize by type (style, error, security)
3. Identify auto-fixable issues
4. Generate patches for complex fixes
5. Explain each fix

Rules:
- Only auto-fix safe style issues
- Flag security-related issues as high priority
- Never change code behavior
- Respect noqa comments""",
            ),
            model_tier=self.config.lint_tier,
            memory_graph_enabled=self.config.memory_graph_enabled,
            memory_graph_path=self.config.memory_graph_path,
        )

        # 3. Type Resolver
        self._agents["types"] = self._factory.create_agent(
            name="type_resolver",
            role="analyst",
            description="Expert at resolving type errors",
            system_prompt=self._get_system_prompt(
                "type_resolver",
                """You are the Type Resolver, a typing expert.

Your focus:
1. Parse mypy output for type errors
2. Categorize errors by type
3. Infer correct types from context
4. Generate type annotations
5. Suggest typing strategy

Rules:
- Prefer simple types over complex generics
- Use | union syntax (Python 3.10+)
- Suggest Any only as last resort
- Consider runtime implications""",
            ),
            model_tier=self.config.types_tier,
            memory_graph_enabled=self.config.memory_graph_enabled,
            memory_graph_path=self.config.memory_graph_path,
        )

        # 4. Test Doctor
        self._agents["tests"] = self._factory.create_agent(
            name="test_doctor",
            role="analyst",
            description="Expert at diagnosing test failures",
            system_prompt=self._get_system_prompt(
                "test_doctor",
                """You are the Test Doctor, a testing expert.

Your focus:
1. Parse pytest output for failures
2. Analyze failure type (assertion, exception, timeout)
3. Determine root cause (test bug vs code bug)
4. Generate fixes for test issues
5. Identify flaky tests

Rules:
- Distinguish test bugs from code bugs
- Never remove assertions to fix tests
- Prefer fixing setup over mocking
- Flag implementation-coupled tests""",
            ),
            model_tier=self.config.tests_tier,
            memory_graph_enabled=self.config.memory_graph_enabled,
            memory_graph_path=self.config.memory_graph_path,
        )

        # 5. Dep Auditor
        self._agents["deps"] = self._factory.create_agent(
            name="dep_auditor",
            role="analyst",
            description="Expert at auditing dependencies",
            system_prompt=self._get_system_prompt(
                "dep_auditor",
                """You are the Dep Auditor, a dependency expert.

Your focus:
1. Check for security vulnerabilities
2. Identify outdated packages
3. Assess update risk
4. Check for conflicts
5. Suggest safe update paths

Rules:
- Prioritize security over outdated
- Be conservative with major upgrades
- Check changelogs for breaking changes
- Consider transitive impacts""",
            ),
            model_tier=self.config.deps_tier,
            memory_graph_enabled=self.config.memory_graph_enabled,
            memory_graph_path=self.config.memory_graph_path,
        )

    async def _create_workflow(self) -> None:
        """Create hierarchical workflow with Health Lead as manager."""
        agents = list(self._agents.values())

        self._workflow = self._factory.create_workflow(
            name="health_check_workflow",
            agents=agents,
            mode="hierarchical",
            description="Comprehensive health check with coordinated diagnosis and fixes",
        )

    async def check(
        self,
        path: str = ".",
        auto_fix: bool | None = None,
        context: dict | None = None,
    ) -> HealthCheckReport:
        """Perform a comprehensive health check.

        Args:
            path: Path to check (default: current directory)
            auto_fix: Override config auto_fix setting
            context: Optional context (focus areas, previous checks, etc.)

        Returns:
            HealthCheckReport with issues, fixes, and health score

        """
        import time

        start_time = time.time()

        # Initialize if needed
        await self._initialize()

        context = context or {}
        auto_fix = auto_fix if auto_fix is not None else self.config.auto_fix
        issues: list[HealthIssue] = []
        fixes: list[HealthFix] = []
        checks_run: dict[str, dict] = {}
        memory_hits = 0

        # Run the individual checks first to gather data
        if self.config.check_lint:
            lint_result = await self._run_lint_check(path)
            checks_run["lint"] = lint_result
            issues.extend(lint_result.get("issues", []))

        if self.config.check_types:
            types_result = await self._run_type_check(path)
            checks_run["types"] = types_result
            issues.extend(types_result.get("issues", []))

        if self.config.check_tests:
            tests_result = await self._run_test_check(path)
            checks_run["tests"] = tests_result
            issues.extend(tests_result.get("issues", []))

        if self.config.check_deps:
            deps_result = await self._run_dep_check(path)
            checks_run["deps"] = deps_result
            issues.extend(deps_result.get("issues", []))

        # Check Memory Graph for similar past issues
        if self._graph and self.config.memory_graph_enabled:
            try:
                similar = self._graph.find_similar(
                    {"name": f"health_check:{path}", "description": f"Health check of {path}"},
                    threshold=0.4,
                    limit=10,
                )
                if similar:
                    memory_hits = len(similar)
                    context["past_checks"] = [
                        {
                            "name": node.name,
                            "health_score": node.metadata.get("health_score", 0),
                            "issues_found": node.metadata.get("issues_found", 0),
                        }
                        for node, score in similar
                    ]
                    logger.info(f"Found {memory_hits} similar past health checks")
            except Exception as e:  # noqa: BLE001
                # INTENTIONAL: Memory Graph is optional - continue health check if unavailable
                logger.warning(f"Error querying Memory Graph: {e}")

        # Build task for the crew to analyze and generate fixes
        check_task = self._build_check_task(path, checks_run, issues, auto_fix, context)

        # Execute the workflow for analysis
        try:
            result = await self._workflow.run(check_task, initial_state=context)

            # Parse fixes from result
            fixes = self._parse_fixes(result, issues)

            # Apply auto-fixes if enabled
            if auto_fix:
                fixes = await self._apply_fixes(fixes, path)

        except Exception as e:  # noqa: BLE001
            # INTENTIONAL: Analysis failure shouldn't crash - return partial results
            logger.error(f"Health check analysis failed: {e}")

        # Calculate health score
        health_score = self._calculate_health_score(issues)

        # Build the report
        duration = time.time() - start_time
        report = HealthCheckReport(
            target=path,
            issues=issues,
            fixes=fixes,
            health_score=health_score,
            check_duration_seconds=duration,
            agents_used=list(self._agents.keys()),
            memory_graph_hits=memory_hits,
            checks_run={k: {"passed": v.get("passed", False)} for k, v in checks_run.items()},
            metadata={
                "auto_fix": auto_fix,
                "framework": str(self._factory.framework.value) if self._factory else "unknown",
                "xml_prompts": self.config.xml_prompts_enabled,
            },
        )

        # Store check in Memory Graph
        if self._graph and self.config.memory_graph_enabled:
            try:
                self._graph.add_finding(
                    "health_check_crew",
                    {
                        "type": "health_check",
                        "name": f"check:{path}",
                        "description": f"Health score: {health_score}/100",
                        "health_score": health_score,
                        "issues_found": len(issues),
                        "fixes_applied": len(report.applied_fixes),
                    },
                )
                self._graph._save()
            except Exception as e:  # noqa: BLE001
                # INTENTIONAL: Memory Graph storage is optional - continue without it
                logger.warning(f"Error storing check in Memory Graph: {e}")

        return report

    async def _run_lint_check(self, path: str) -> dict:
        """Run ruff lint check."""
        issues = []
        passed = True

        try:
            result = subprocess.run(
                ["python", "-m", "ruff", "check", path, "--output-format=json"],
                check=False,
                capture_output=True,
                text=True,
                timeout=60,
            )

            if result.returncode != 0:
                passed = False

            # Parse JSON output
            import json

            try:
                violations = json.loads(result.stdout) if result.stdout else []
                for v in violations[:50]:  # Limit to 50
                    issues.append(
                        HealthIssue(
                            title=f"{v.get('code', 'LINT')}: {v.get('message', 'Lint error')}",
                            description=v.get("message", ""),
                            category=HealthCategory.LINT,
                            severity=IssueSeverity.MEDIUM,
                            file_path=v.get("filename"),
                            line_number=v.get("location", {}).get("row"),
                            rule_id=v.get("code"),
                            tool="ruff",
                        ),
                    )
            except json.JSONDecodeError:
                pass

        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            logger.warning(f"Lint check failed: {e}")

        return {"passed": passed, "issues": issues, "tool": "ruff"}

    async def _run_type_check(self, path: str) -> dict:
        """Run mypy type check."""
        issues = []
        passed = True

        # Only scan production code packages
        production_packages = [
            "empathy_os",
            "empathy_software_plugin",
            "empathy_healthcare_plugin",
            "empathy_llm_toolkit",
            "patterns",
        ]

        # Use production packages if checking current directory
        scan_args = []
        if path in [".", "./"]:
            # Use package notation for packages in src/
            for pkg in production_packages:
                scan_args.extend(["-p", pkg])
        else:
            # For specific paths, use file notation
            scan_args.append(path)

        try:
            result = subprocess.run(
                ["python", "-m", "mypy"]
                + scan_args
                + ["--ignore-missing-imports", "--no-error-summary"],
                check=False,
                capture_output=True,
                text=True,
                timeout=120,
            )

            if result.returncode != 0:
                passed = False

            # Parse text output
            for line in result.stdout.splitlines()[:50]:
                if ": error:" in line:
                    parts = line.split(": error:", 1)
                    location = parts[0] if parts else ""
                    message = parts[1].strip() if len(parts) > 1 else line

                    file_path = None
                    line_num = None
                    if ":" in location:
                        loc_parts = location.rsplit(":", 2)
                        file_path = loc_parts[0]
                        try:
                            line_num = int(loc_parts[1]) if len(loc_parts) > 1 else None
                        except ValueError:
                            pass

                    issues.append(
                        HealthIssue(
                            title=f"Type error: {message[:60]}",
                            description=message,
                            category=HealthCategory.TYPES,
                            severity=IssueSeverity.MEDIUM,
                            file_path=file_path,
                            line_number=line_num,
                            tool="mypy",
                        ),
                    )

        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            logger.warning(f"Type check failed: {e}")

        return {"passed": passed, "issues": issues, "tool": "mypy"}

    async def _run_test_check(self, path: str) -> dict:
        """Run pytest test check."""
        issues = []
        passed = True

        # Only run tests in tests/ directory for production health check
        test_path = "tests/" if path in [".", "./"] else path

        try:
            result = subprocess.run(
                ["python", "-m", "pytest", test_path, "--collect-only", "-q"],
                check=False,
                capture_output=True,
                text=True,
                timeout=60,
            )

            if result.returncode != 0:
                passed = False

            # Check for collection errors in stderr
            error_output = result.stderr + result.stdout
            for line in error_output.splitlines()[:50]:
                if "ERROR" in line or "INTERNALERROR" in line:
                    # Only report actual errors, not counts
                    if "error" in line.lower() and not line.strip().startswith("="):
                        issues.append(
                            HealthIssue(
                                title=f"Test error: {line[:50]}",
                                description=line,
                                category=HealthCategory.TESTS,
                                severity=IssueSeverity.CRITICAL,
                                tool="pytest",
                            ),
                        )

        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            logger.warning(f"Test check failed: {e}")

        return {"passed": passed, "issues": issues, "tool": "pytest"}

    async def _run_dep_check(self, path: str) -> dict:
        """Run dependency security check."""
        issues = []
        passed = True

        # Try pip-audit first
        try:
            result = subprocess.run(
                ["pip-audit", "--format=json"],
                check=False,
                capture_output=True,
                text=True,
                timeout=60,
                cwd=path if Path(path).is_dir() else ".",
            )

            if result.returncode != 0:
                passed = False

            import json

            try:
                vulns = json.loads(result.stdout) if result.stdout else []
                # Ensure vulns is a list
                if isinstance(vulns, dict):
                    vulns = vulns.get("vulnerabilities", []) or list(vulns.values())
                if not isinstance(vulns, list):
                    vulns = []
                for v in vulns[:20]:
                    # Handle different vulnerability formats
                    if not isinstance(v, dict):
                        # Skip non-dict items or convert to basic format
                        continue

                    severity = IssueSeverity.HIGH
                    if "critical" in str(v).lower():
                        severity = IssueSeverity.CRITICAL

                    issues.append(
                        HealthIssue(
                            title=f"Vulnerability in {v.get('name', 'unknown')}",
                            description=v.get("description", str(v)),
                            category=HealthCategory.DEPENDENCIES,
                            severity=severity,
                            rule_id=v.get("id"),
                            tool="pip-audit",
                            metadata={"fix_versions": v.get("fix_versions", [])},
                        ),
                    )
            except json.JSONDecodeError:
                pass

        except (subprocess.TimeoutExpired, FileNotFoundError):
            # pip-audit not installed, try basic pip check
            try:
                result = subprocess.run(
                    ["pip", "check"],
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                if result.returncode != 0:
                    passed = False
                    for line in result.stdout.splitlines()[:10]:
                        issues.append(
                            HealthIssue(
                                title=f"Dependency conflict: {line[:50]}",
                                description=line,
                                category=HealthCategory.DEPENDENCIES,
                                severity=IssueSeverity.MEDIUM,
                                tool="pip",
                            ),
                        )
            except (subprocess.TimeoutExpired, FileNotFoundError):
                pass

        return {"passed": passed, "issues": issues, "tool": "pip-audit/pip"}

    def _build_check_task(
        self,
        path: str,
        checks_run: dict,
        issues: list[HealthIssue],
        auto_fix: bool,
        context: dict,
    ) -> str:
        """Build the check task description for the crew."""
        issues_summary = "\n".join(
            f"  - [{i.severity.value.upper()}] {i.category.value}: {i.title}" for i in issues[:30]
        )

        task = f"""Analyze health check results and generate fixes.

Target: {path}
Auto-fix enabled: {auto_fix}

Checks Run:
- Lint (ruff): {"PASS" if checks_run.get("lint", {}).get("passed") else "FAIL"}
- Types (mypy): {"PASS" if checks_run.get("types", {}).get("passed") else "FAIL"}
- Tests (pytest): {"PASS" if checks_run.get("tests", {}).get("passed") else "FAIL"}
- Dependencies: {"PASS" if checks_run.get("deps", {}).get("passed") else "FAIL"}

Issues Found ({len(issues)}):
{issues_summary}

Workflow:
1. Health Lead coordinates analysis
2. Lint Fixer analyzes and suggests fixes for lint issues
3. Type Resolver suggests type annotations
4. Test Doctor diagnoses test failures
5. Dep Auditor suggests dependency updates

For each issue, provide:
- Root cause analysis
- Fix recommendation (code if applicable)
- Safety assessment (safe to auto-fix or needs review)
- Priority (1=critical, 2=high, 3=medium, 4=low)

Generate a prioritized fix plan.
"""

        if context.get("past_checks"):
            task += f"""
Past Health Checks Found: {len(context["past_checks"])}
Consider patterns from past fixes.
"""

        return task

    def _parse_fixes(self, result: dict, issues: list[HealthIssue]) -> list[HealthFix]:
        """Parse fixes from workflow result."""
        fixes = []

        # Check for structured fixes in metadata
        metadata = result.get("metadata", {})
        if "fixes" in metadata:
            for f in metadata["fixes"]:
                fixes.append(
                    HealthFix(
                        title=f.get("title", "Fix"),
                        description=f.get("description", ""),
                        category=HealthCategory(f.get("category", "general")),
                        status=FixStatus.SUGGESTED,
                        file_path=f.get("file_path"),
                        before_code=f.get("before_code"),
                        after_code=f.get("after_code"),
                        patch=f.get("patch"),
                    ),
                )
            return fixes

        # Generate suggested fixes based on issues
        for issue in issues:
            if issue.category == HealthCategory.LINT and issue.rule_id:
                fixes.append(
                    HealthFix(
                        title=f"Fix {issue.rule_id}",
                        description=f"Run: ruff check --fix --select {issue.rule_id}",
                        category=issue.category,
                        status=FixStatus.SUGGESTED,
                        file_path=issue.file_path,
                        related_issues=[issue.title],
                    ),
                )

        return fixes

    async def _apply_fixes(self, fixes: list[HealthFix], path: str) -> list[HealthFix]:
        """Apply safe auto-fixes."""
        updated_fixes = []

        for fix in fixes:
            if fix.category == HealthCategory.LINT and self.config.fix_safe_only:
                # Run ruff --fix for lint issues
                try:
                    result = subprocess.run(
                        ["python", "-m", "ruff", "check", path, "--fix"],
                        check=False,
                        capture_output=True,
                        text=True,
                        timeout=60,
                    )
                    fix.status = FixStatus.APPLIED if result.returncode == 0 else FixStatus.FAILED
                except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
                    fix.status = FixStatus.FAILED
            else:
                fix.status = FixStatus.SUGGESTED

            updated_fixes.append(fix)

        return updated_fixes

    def _calculate_health_score(self, issues: list[HealthIssue]) -> float:
        """Calculate health score from issues.

        Uses category-capped deductions to prevent one category (e.g., lint)
        from dominating the score. This makes the score more meaningful -
        50 lint warnings shouldn't tank a project that passes tests and has
        no security issues.

        Category caps:
        - lint: max -15 points
        - types: max -20 points
        - tests: max -25 points
        - security/dependencies: max -30 points
        - general: max -10 points
        """
        if not issues:
            return 100.0

        # Per-issue deductions by severity
        severity_deductions = {
            IssueSeverity.CRITICAL: 15,
            IssueSeverity.HIGH: 8,
            IssueSeverity.MEDIUM: 2,
            IssueSeverity.LOW: 0.5,
            IssueSeverity.INFO: 0,
        }

        # Maximum deduction per category (prevents one area from tanking score)
        category_caps = {
            HealthCategory.LINT: 15,
            HealthCategory.TYPES: 20,
            HealthCategory.TESTS: 25,
            HealthCategory.DEPENDENCIES: 30,
            HealthCategory.SECURITY: 30,
            HealthCategory.GENERAL: 10,
        }

        # Calculate deductions per category
        category_deductions: dict[HealthCategory, float] = {}
        for issue in issues:
            cat = issue.category
            deduction = severity_deductions.get(issue.severity, 0)
            category_deductions[cat] = category_deductions.get(cat, 0) + deduction

        # Apply caps per category
        total_deduction = 0.0
        for cat, deduction in category_deductions.items():
            cap = category_caps.get(cat, 10)
            total_deduction += min(deduction, cap)

        return max(0.0, 100.0 - total_deduction)

    @property
    def agents(self) -> dict[str, Any]:
        """Get the crew's agents."""
        return self._agents

    @property
    def is_initialized(self) -> bool:
        """Check if crew is initialized."""
        return self._initialized

    async def get_agent_stats(self) -> dict:
        """Get statistics about crew agents."""
        await self._initialize()

        agents_dict: dict = {}
        stats: dict = {
            "agent_count": len(self._agents),
            "agents": agents_dict,
            "framework": self._factory.framework.value if self._factory else "unknown",
            "memory_graph_enabled": self.config.memory_graph_enabled,
            "xml_prompts_enabled": self.config.xml_prompts_enabled,
        }

        for name, agent in self._agents.items():
            agents_dict[name] = {
                "role": agent.config.role if hasattr(agent, "config") else "unknown",
                "model_tier": getattr(agent.config, "model_tier", "unknown"),
            }

        return stats
