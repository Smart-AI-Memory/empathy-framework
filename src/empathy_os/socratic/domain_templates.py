"""Domain-Specific Agent Templates

Pre-configured agent templates optimized for specific knowledge domains
and use cases. Templates include:
- Agent configurations (role, tools, model tier)
- Workflow patterns (stages, dependencies)
- Success metrics
- Domain-specific prompts and examples

Supported Domains:
- Software Development (code review, testing, refactoring)
- Security (vulnerability scanning, compliance, penetration testing)
- Data Science (data validation, model evaluation, reporting)
- DevOps (CI/CD, infrastructure, monitoring)
- Legal (contract review, compliance checking)
- Healthcare (clinical notes, HIPAA compliance)
- Financial (risk analysis, fraud detection, reporting)

Copyright 2026 Smart-AI-Memory
Licensed under Fair Source License 0.9
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .blueprint import AgentRole, ToolCategory


# =============================================================================
# DOMAIN DEFINITIONS
# =============================================================================


class Domain(Enum):
    """Supported knowledge domains."""

    # Software Development
    CODE_REVIEW = "code_review"
    TESTING = "testing"
    REFACTORING = "refactoring"
    DOCUMENTATION = "documentation"
    PERFORMANCE = "performance"

    # Security
    SECURITY_AUDIT = "security_audit"
    VULNERABILITY_SCAN = "vulnerability_scan"
    COMPLIANCE = "compliance"
    PENETRATION_TESTING = "penetration_testing"

    # Data Science
    DATA_VALIDATION = "data_validation"
    MODEL_EVALUATION = "model_evaluation"
    DATA_PIPELINE = "data_pipeline"
    REPORTING = "reporting"

    # DevOps
    CI_CD = "ci_cd"
    INFRASTRUCTURE = "infrastructure"
    MONITORING = "monitoring"
    INCIDENT_RESPONSE = "incident_response"

    # Legal
    CONTRACT_REVIEW = "contract_review"
    LEGAL_COMPLIANCE = "legal_compliance"
    IP_ANALYSIS = "ip_analysis"

    # Healthcare
    CLINICAL_NOTES = "clinical_notes"
    HIPAA_COMPLIANCE = "hipaa_compliance"
    MEDICAL_CODING = "medical_coding"

    # Financial
    RISK_ANALYSIS = "risk_analysis"
    FRAUD_DETECTION = "fraud_detection"
    FINANCIAL_REPORTING = "financial_reporting"

    # General
    GENERAL = "general"


# =============================================================================
# TEMPLATE DATA STRUCTURES
# =============================================================================


@dataclass
class AgentTemplate:
    """Template for configuring an agent."""

    template_id: str
    name: str
    description: str
    role: AgentRole
    tools: list[str]
    model_tier: str = "capable"  # cheap, capable, premium
    system_prompt: str = ""
    example_prompts: list[str] = field(default_factory=list)
    configuration: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)


@dataclass
class WorkflowTemplate:
    """Template for configuring a workflow."""

    template_id: str
    name: str
    description: str
    domain: Domain
    agents: list[str]  # Agent template IDs
    stages: list[dict[str, Any]]
    success_metrics: list[dict[str, Any]]
    estimated_duration: str  # fast, moderate, slow
    estimated_cost: str  # cheap, moderate, expensive
    configuration: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)


@dataclass
class DomainTemplate:
    """Complete template for a domain."""

    domain: Domain
    name: str
    description: str
    agents: list[AgentTemplate]
    workflows: list[WorkflowTemplate]
    default_workflow: str  # Default workflow template ID
    keywords: list[str]  # Keywords for domain detection
    required_tools: list[str]
    optional_tools: list[str]


# =============================================================================
# AGENT TEMPLATES
# =============================================================================


# Software Development Agents
CODE_REVIEWER = AgentTemplate(
    template_id="code_reviewer",
    name="Code Reviewer",
    description="Reviews code for quality, maintainability, and best practices",
    role=AgentRole.REVIEWER,
    tools=["read_file", "grep_code", "analyze_ast", "run_linter"],
    model_tier="capable",
    system_prompt="""You are an expert code reviewer focused on code quality and maintainability.
Review code for:
- Clear naming and documentation
- Proper error handling
- Code organization and structure
- Adherence to language idioms
- Potential bugs or logic errors
- Performance considerations

Provide specific, actionable feedback with code examples when helpful.""",
    example_prompts=[
        "Review this function for maintainability issues",
        "Check this module for proper error handling",
        "Analyze this code for potential bugs",
    ],
    tags=["code_review", "quality", "maintainability"],
)

SECURITY_SCANNER = AgentTemplate(
    template_id="security_scanner",
    name="Security Scanner",
    description="Scans code for security vulnerabilities and unsafe patterns",
    role=AgentRole.AUDITOR,
    tools=["read_file", "grep_code", "security_scan", "analyze_ast"],
    model_tier="capable",
    system_prompt="""You are a security expert scanning code for vulnerabilities.
Focus on:
- OWASP Top 10 vulnerabilities
- Injection flaws (SQL, command, XSS)
- Authentication and authorization issues
- Sensitive data exposure
- Security misconfigurations
- Unsafe dependencies

Rate each finding by severity (CRITICAL, HIGH, MEDIUM, LOW) and provide remediation guidance.""",
    example_prompts=[
        "Scan this code for SQL injection vulnerabilities",
        "Check authentication implementation for flaws",
        "Review this API for security issues",
    ],
    configuration={
        "severity_threshold": "medium",
        "include_cwe": True,
        "include_owasp": True,
    },
    tags=["security", "vulnerability", "audit"],
)

TEST_GENERATOR = AgentTemplate(
    template_id="test_generator",
    name="Test Generator",
    description="Generates unit and integration tests for code",
    role=AgentRole.GENERATOR,
    tools=["read_file", "analyze_ast", "run_tests", "write_file"],
    model_tier="capable",
    system_prompt="""You are an expert test engineer generating comprehensive tests.
Generate tests that:
- Cover happy path and edge cases
- Test error conditions and validation
- Are independent and deterministic
- Use appropriate assertions
- Follow testing best practices for the language
- Include meaningful test names and documentation

Aim for high coverage while keeping tests maintainable.""",
    example_prompts=[
        "Generate unit tests for this function",
        "Create integration tests for this API endpoint",
        "Write tests for error handling scenarios",
    ],
    configuration={
        "test_framework": "auto",  # Detect from project
        "coverage_target": 80,
        "include_edge_cases": True,
    },
    tags=["testing", "unit_tests", "coverage"],
)

PERFORMANCE_ANALYZER = AgentTemplate(
    template_id="performance_analyzer",
    name="Performance Analyzer",
    description="Analyzes code for performance issues and optimization opportunities",
    role=AgentRole.ANALYZER,
    tools=["read_file", "analyze_ast", "grep_code", "run_profiler"],
    model_tier="capable",
    system_prompt="""You are a performance optimization expert.
Analyze code for:
- Time complexity issues (O(n²) patterns, unnecessary iterations)
- Memory leaks and excessive allocation
- I/O bottlenecks
- Database query optimization
- Caching opportunities
- Parallelization potential

Provide specific optimization suggestions with expected impact.""",
    configuration={
        "complexity_threshold": "O(n^2)",
        "include_memory_analysis": True,
    },
    tags=["performance", "optimization", "profiling"],
)

DOCUMENTATION_WRITER = AgentTemplate(
    template_id="documentation_writer",
    name="Documentation Writer",
    description="Generates and improves code documentation",
    role=AgentRole.GENERATOR,
    tools=["read_file", "analyze_ast", "write_file"],
    model_tier="capable",
    system_prompt="""You are a technical writer creating clear, helpful documentation.
Generate:
- Function and class docstrings
- API documentation
- README files and guides
- Architecture documentation
- Usage examples

Documentation should be:
- Clear and concise
- Technically accurate
- Well-organized
- Include examples where helpful""",
    tags=["documentation", "docstrings", "readme"],
)

REFACTORING_ADVISOR = AgentTemplate(
    template_id="refactoring_advisor",
    name="Refactoring Advisor",
    description="Identifies refactoring opportunities and provides guidance",
    role=AgentRole.ANALYZER,
    tools=["read_file", "analyze_ast", "grep_code"],
    model_tier="capable",
    system_prompt="""You are a software architect identifying refactoring opportunities.
Look for:
- Code duplication (DRY violations)
- Long methods that should be split
- Complex conditionals that could be simplified
- Poor abstraction or missing interfaces
- Coupling issues
- Design pattern opportunities

Prioritize refactorings by impact and risk.""",
    tags=["refactoring", "design", "architecture"],
)

# Security Domain Agents
COMPLIANCE_AUDITOR = AgentTemplate(
    template_id="compliance_auditor",
    name="Compliance Auditor",
    description="Audits code and configurations for compliance requirements",
    role=AgentRole.AUDITOR,
    tools=["read_file", "grep_code", "security_scan"],
    model_tier="premium",
    system_prompt="""You are a compliance expert auditing for regulatory requirements.
Check for:
- SOC 2 compliance requirements
- GDPR data handling
- PCI-DSS requirements (if applicable)
- Industry-specific regulations
- Internal security policies

Document findings with specific control references and remediation steps.""",
    configuration={
        "frameworks": ["soc2", "gdpr", "pci-dss"],
        "evidence_required": True,
    },
    tags=["compliance", "audit", "regulatory"],
)

PENETRATION_TESTER = AgentTemplate(
    template_id="penetration_tester",
    name="Penetration Tester",
    description="Simulates attacks to find exploitable vulnerabilities",
    role=AgentRole.AUDITOR,
    tools=["read_file", "grep_code", "security_scan", "analyze_ast"],
    model_tier="premium",
    system_prompt="""You are a penetration testing expert identifying exploitable vulnerabilities.
Focus on:
- Authentication bypass techniques
- Authorization escalation
- Injection attack vectors
- Session management weaknesses
- API abuse scenarios
- Business logic flaws

For each finding, demonstrate the attack path and provide proof of concept.""",
    configuration={
        "attack_depth": "comprehensive",
        "include_poc": True,
    },
    tags=["security", "penetration_testing", "offensive"],
)

# Data Science Agents
DATA_VALIDATOR = AgentTemplate(
    template_id="data_validator",
    name="Data Validator",
    description="Validates data quality and schema compliance",
    role=AgentRole.ANALYZER,
    tools=["read_file", "run_script", "grep_code"],
    model_tier="capable",
    system_prompt="""You are a data quality expert validating datasets.
Check for:
- Schema compliance
- Data type correctness
- Missing values and nulls
- Outliers and anomalies
- Consistency across related fields
- Format validation

Generate validation reports with statistics and recommendations.""",
    configuration={
        "null_threshold": 0.05,
        "outlier_method": "iqr",
    },
    tags=["data", "validation", "quality"],
)

MODEL_EVALUATOR = AgentTemplate(
    template_id="model_evaluator",
    name="Model Evaluator",
    description="Evaluates ML model performance and fairness",
    role=AgentRole.ANALYZER,
    tools=["read_file", "run_script", "analyze_ast"],
    model_tier="premium",
    system_prompt="""You are an ML expert evaluating model performance and fairness.
Analyze:
- Model accuracy metrics (precision, recall, F1, AUC)
- Bias and fairness across protected groups
- Calibration and confidence
- Feature importance
- Robustness to distribution shift
- Explainability

Provide recommendations for model improvement.""",
    configuration={
        "fairness_groups": [],
        "confidence_calibration": True,
    },
    tags=["ml", "model", "evaluation", "fairness"],
)

# DevOps Agents
CI_CD_ANALYZER = AgentTemplate(
    template_id="ci_cd_analyzer",
    name="CI/CD Analyzer",
    description="Analyzes and optimizes CI/CD pipelines",
    role=AgentRole.ANALYZER,
    tools=["read_file", "grep_code", "run_script"],
    model_tier="capable",
    system_prompt="""You are a DevOps expert optimizing CI/CD pipelines.
Analyze:
- Pipeline efficiency and parallelization
- Build time optimization
- Test reliability and flakiness
- Deployment safety
- Rollback capabilities
- Security scanning integration

Provide specific recommendations with expected time savings.""",
    tags=["devops", "ci_cd", "pipeline"],
)

INFRASTRUCTURE_REVIEWER = AgentTemplate(
    template_id="infrastructure_reviewer",
    name="Infrastructure Reviewer",
    description="Reviews infrastructure code and configurations",
    role=AgentRole.REVIEWER,
    tools=["read_file", "grep_code", "security_scan"],
    model_tier="capable",
    system_prompt="""You are an infrastructure expert reviewing IaC and configurations.
Review:
- Terraform/CloudFormation/Pulumi code
- Kubernetes manifests
- Docker configurations
- Cloud resource configurations
- Network security groups
- IAM policies

Check for security, cost optimization, and best practices.""",
    tags=["infrastructure", "iac", "cloud"],
)

INCIDENT_RESPONDER = AgentTemplate(
    template_id="incident_responder",
    name="Incident Responder",
    description="Assists with incident analysis and response",
    role=AgentRole.ANALYZER,
    tools=["read_file", "grep_code", "run_script"],
    model_tier="premium",
    system_prompt="""You are an SRE expert assisting with incident response.
Help with:
- Root cause analysis
- Impact assessment
- Mitigation strategies
- Communication templates
- Post-mortem preparation
- Preventive measures

Prioritize by customer impact and provide clear action items.""",
    configuration={
        "severity_levels": ["SEV1", "SEV2", "SEV3", "SEV4"],
    },
    tags=["incident", "sre", "response"],
)

# Result Synthesizer (used across domains)
RESULT_SYNTHESIZER = AgentTemplate(
    template_id="result_synthesizer",
    name="Result Synthesizer",
    description="Aggregates and synthesizes results from multiple agents",
    role=AgentRole.ORCHESTRATOR,
    tools=["read_file"],
    model_tier="capable",
    system_prompt="""You are an expert at synthesizing findings from multiple analyses.
Your job is to:
- Aggregate findings from multiple agents
- Prioritize by severity and impact
- Identify patterns across findings
- Remove duplicates and consolidate
- Generate executive summary
- Provide prioritized action items

Format output clearly for both technical and non-technical audiences.""",
    tags=["synthesis", "aggregation", "reporting"],
)


# =============================================================================
# WORKFLOW TEMPLATES
# =============================================================================


CODE_REVIEW_WORKFLOW = WorkflowTemplate(
    template_id="code_review_standard",
    name="Standard Code Review",
    description="Comprehensive code review covering quality, security, and tests",
    domain=Domain.CODE_REVIEW,
    agents=["code_reviewer", "security_scanner", "result_synthesizer"],
    stages=[
        {
            "stage_id": "analysis",
            "name": "Code Analysis",
            "agents": ["code_reviewer", "security_scanner"],
            "parallel": True,
        },
        {
            "stage_id": "synthesis",
            "name": "Result Synthesis",
            "agents": ["result_synthesizer"],
            "parallel": False,
            "dependencies": ["analysis"],
        },
    ],
    success_metrics=[
        {
            "metric_id": "issues_found",
            "name": "Issues Identified",
            "type": "count",
            "direction": "higher_is_better",
        },
        {
            "metric_id": "critical_issues",
            "name": "Critical Issues",
            "type": "count",
            "target": 0,
            "direction": "lower_is_better",
        },
    ],
    estimated_duration="moderate",
    estimated_cost="moderate",
    tags=["code_review", "quality"],
)

SECURITY_AUDIT_WORKFLOW = WorkflowTemplate(
    template_id="security_audit_comprehensive",
    name="Comprehensive Security Audit",
    description="Full security audit including vulnerability scanning and compliance",
    domain=Domain.SECURITY_AUDIT,
    agents=["security_scanner", "compliance_auditor", "result_synthesizer"],
    stages=[
        {
            "stage_id": "scanning",
            "name": "Security Scanning",
            "agents": ["security_scanner"],
            "parallel": False,
        },
        {
            "stage_id": "compliance",
            "name": "Compliance Check",
            "agents": ["compliance_auditor"],
            "parallel": False,
            "dependencies": ["scanning"],
        },
        {
            "stage_id": "synthesis",
            "name": "Report Generation",
            "agents": ["result_synthesizer"],
            "parallel": False,
            "dependencies": ["scanning", "compliance"],
        },
    ],
    success_metrics=[
        {
            "metric_id": "vulnerabilities_found",
            "name": "Vulnerabilities Found",
            "type": "count",
        },
        {
            "metric_id": "compliance_score",
            "name": "Compliance Score",
            "type": "percentage",
            "target": 90,
            "direction": "higher_is_better",
        },
    ],
    estimated_duration="slow",
    estimated_cost="expensive",
    tags=["security", "compliance", "audit"],
)

TESTING_WORKFLOW = WorkflowTemplate(
    template_id="test_generation_comprehensive",
    name="Comprehensive Test Generation",
    description="Generate unit tests with high coverage",
    domain=Domain.TESTING,
    agents=["test_generator", "code_reviewer", "result_synthesizer"],
    stages=[
        {
            "stage_id": "generation",
            "name": "Test Generation",
            "agents": ["test_generator"],
            "parallel": False,
        },
        {
            "stage_id": "review",
            "name": "Test Review",
            "agents": ["code_reviewer"],
            "parallel": False,
            "dependencies": ["generation"],
        },
        {
            "stage_id": "synthesis",
            "name": "Summary",
            "agents": ["result_synthesizer"],
            "parallel": False,
            "dependencies": ["review"],
        },
    ],
    success_metrics=[
        {
            "metric_id": "tests_generated",
            "name": "Tests Generated",
            "type": "count",
            "direction": "higher_is_better",
        },
        {
            "metric_id": "coverage_improvement",
            "name": "Coverage Improvement",
            "type": "percentage",
            "target": 80,
            "direction": "higher_is_better",
        },
    ],
    estimated_duration="moderate",
    estimated_cost="moderate",
    tags=["testing", "coverage", "quality"],
)

PERFORMANCE_WORKFLOW = WorkflowTemplate(
    template_id="performance_analysis",
    name="Performance Analysis",
    description="Analyze and optimize code performance",
    domain=Domain.PERFORMANCE,
    agents=["performance_analyzer", "refactoring_advisor", "result_synthesizer"],
    stages=[
        {
            "stage_id": "analysis",
            "name": "Performance Analysis",
            "agents": ["performance_analyzer"],
            "parallel": False,
        },
        {
            "stage_id": "optimization",
            "name": "Optimization Recommendations",
            "agents": ["refactoring_advisor"],
            "parallel": False,
            "dependencies": ["analysis"],
        },
        {
            "stage_id": "synthesis",
            "name": "Summary",
            "agents": ["result_synthesizer"],
            "parallel": False,
            "dependencies": ["optimization"],
        },
    ],
    success_metrics=[
        {
            "metric_id": "bottlenecks_found",
            "name": "Bottlenecks Identified",
            "type": "count",
        },
        {
            "metric_id": "optimization_potential",
            "name": "Optimization Potential",
            "type": "percentage",
        },
    ],
    estimated_duration="moderate",
    estimated_cost="moderate",
    tags=["performance", "optimization"],
)

DEVOPS_CI_CD_WORKFLOW = WorkflowTemplate(
    template_id="ci_cd_optimization",
    name="CI/CD Pipeline Optimization",
    description="Analyze and optimize CI/CD pipelines",
    domain=Domain.CI_CD,
    agents=["ci_cd_analyzer", "security_scanner", "result_synthesizer"],
    stages=[
        {
            "stage_id": "pipeline_analysis",
            "name": "Pipeline Analysis",
            "agents": ["ci_cd_analyzer"],
            "parallel": False,
        },
        {
            "stage_id": "security_check",
            "name": "Security Check",
            "agents": ["security_scanner"],
            "parallel": False,
            "dependencies": ["pipeline_analysis"],
        },
        {
            "stage_id": "synthesis",
            "name": "Recommendations",
            "agents": ["result_synthesizer"],
            "parallel": False,
            "dependencies": ["security_check"],
        },
    ],
    success_metrics=[
        {
            "metric_id": "pipeline_time_reduction",
            "name": "Time Reduction Potential",
            "type": "percentage",
        },
        {
            "metric_id": "security_issues",
            "name": "Security Issues",
            "type": "count",
            "target": 0,
        },
    ],
    estimated_duration="moderate",
    estimated_cost="moderate",
    tags=["devops", "ci_cd", "pipeline"],
)


# =============================================================================
# DOMAIN TEMPLATE REGISTRY
# =============================================================================


class DomainTemplateRegistry:
    """Registry of domain templates."""

    def __init__(self):
        """Initialize registry with built-in templates."""
        self._agents: dict[str, AgentTemplate] = {}
        self._workflows: dict[str, WorkflowTemplate] = {}
        self._domains: dict[Domain, DomainTemplate] = {}

        # Register built-in templates
        self._register_builtins()

    def _register_builtins(self):
        """Register built-in agent and workflow templates."""
        # Register agent templates
        agents = [
            CODE_REVIEWER,
            SECURITY_SCANNER,
            TEST_GENERATOR,
            PERFORMANCE_ANALYZER,
            DOCUMENTATION_WRITER,
            REFACTORING_ADVISOR,
            COMPLIANCE_AUDITOR,
            PENETRATION_TESTER,
            DATA_VALIDATOR,
            MODEL_EVALUATOR,
            CI_CD_ANALYZER,
            INFRASTRUCTURE_REVIEWER,
            INCIDENT_RESPONDER,
            RESULT_SYNTHESIZER,
        ]
        for agent in agents:
            self._agents[agent.template_id] = agent

        # Register workflow templates
        workflows = [
            CODE_REVIEW_WORKFLOW,
            SECURITY_AUDIT_WORKFLOW,
            TESTING_WORKFLOW,
            PERFORMANCE_WORKFLOW,
            DEVOPS_CI_CD_WORKFLOW,
        ]
        for workflow in workflows:
            self._workflows[workflow.template_id] = workflow

        # Create domain templates
        self._domains[Domain.CODE_REVIEW] = DomainTemplate(
            domain=Domain.CODE_REVIEW,
            name="Code Review",
            description="Automated code review and quality analysis",
            agents=[CODE_REVIEWER, SECURITY_SCANNER, RESULT_SYNTHESIZER],
            workflows=[CODE_REVIEW_WORKFLOW],
            default_workflow="code_review_standard",
            keywords=["review", "quality", "lint", "style", "clean", "readable"],
            required_tools=["read_file", "grep_code"],
            optional_tools=["analyze_ast", "run_linter"],
        )

        self._domains[Domain.SECURITY_AUDIT] = DomainTemplate(
            domain=Domain.SECURITY_AUDIT,
            name="Security Audit",
            description="Security vulnerability scanning and compliance auditing",
            agents=[SECURITY_SCANNER, COMPLIANCE_AUDITOR, RESULT_SYNTHESIZER],
            workflows=[SECURITY_AUDIT_WORKFLOW],
            default_workflow="security_audit_comprehensive",
            keywords=["security", "vulnerability", "audit", "compliance", "penetration", "CVE", "OWASP"],
            required_tools=["read_file", "security_scan"],
            optional_tools=["grep_code", "analyze_ast"],
        )

        self._domains[Domain.TESTING] = DomainTemplate(
            domain=Domain.TESTING,
            name="Testing",
            description="Automated test generation and coverage improvement",
            agents=[TEST_GENERATOR, CODE_REVIEWER, RESULT_SYNTHESIZER],
            workflows=[TESTING_WORKFLOW],
            default_workflow="test_generation_comprehensive",
            keywords=["test", "coverage", "unit", "integration", "e2e", "pytest", "jest"],
            required_tools=["read_file", "run_tests", "write_file"],
            optional_tools=["analyze_ast"],
        )

        self._domains[Domain.PERFORMANCE] = DomainTemplate(
            domain=Domain.PERFORMANCE,
            name="Performance",
            description="Performance analysis and optimization",
            agents=[PERFORMANCE_ANALYZER, REFACTORING_ADVISOR, RESULT_SYNTHESIZER],
            workflows=[PERFORMANCE_WORKFLOW],
            default_workflow="performance_analysis",
            keywords=["performance", "optimize", "speed", "memory", "profile", "bottleneck"],
            required_tools=["read_file", "analyze_ast"],
            optional_tools=["run_profiler"],
        )

        self._domains[Domain.CI_CD] = DomainTemplate(
            domain=Domain.CI_CD,
            name="CI/CD",
            description="CI/CD pipeline analysis and optimization",
            agents=[CI_CD_ANALYZER, SECURITY_SCANNER, RESULT_SYNTHESIZER],
            workflows=[DEVOPS_CI_CD_WORKFLOW],
            default_workflow="ci_cd_optimization",
            keywords=["ci", "cd", "pipeline", "github actions", "jenkins", "deployment"],
            required_tools=["read_file", "grep_code"],
            optional_tools=["run_script"],
        )

    def get_agent(self, template_id: str) -> AgentTemplate | None:
        """Get agent template by ID."""
        return self._agents.get(template_id)

    def get_workflow(self, template_id: str) -> WorkflowTemplate | None:
        """Get workflow template by ID."""
        return self._workflows.get(template_id)

    def get_domain(self, domain: Domain) -> DomainTemplate | None:
        """Get domain template."""
        return self._domains.get(domain)

    def list_agents(self, domain: Domain | None = None) -> list[AgentTemplate]:
        """List agent templates, optionally filtered by domain."""
        if domain is None:
            return list(self._agents.values())

        domain_template = self._domains.get(domain)
        if domain_template:
            return domain_template.agents
        return []

    def list_workflows(self, domain: Domain | None = None) -> list[WorkflowTemplate]:
        """List workflow templates, optionally filtered by domain."""
        if domain is None:
            return list(self._workflows.values())

        domain_template = self._domains.get(domain)
        if domain_template:
            return domain_template.workflows
        return []

    def list_domains(self) -> list[Domain]:
        """List all supported domains."""
        return list(self._domains.keys())

    def detect_domain(self, goal: str) -> tuple[Domain, float]:
        """Detect domain from goal text.

        Args:
            goal: Goal text

        Returns:
            (domain, confidence) tuple
        """
        goal_lower = goal.lower()
        scores: dict[Domain, float] = {}

        for domain, template in self._domains.items():
            score = 0.0
            for keyword in template.keywords:
                if keyword in goal_lower:
                    score += 1.0
                    # Bonus for word boundary match
                    if f" {keyword} " in f" {goal_lower} ":
                        score += 0.5

            if score > 0:
                # Normalize by number of keywords
                scores[domain] = score / len(template.keywords)

        if not scores:
            return Domain.GENERAL, 0.3

        best_domain = max(scores, key=scores.get)
        confidence = min(scores[best_domain] * 2, 1.0)  # Scale up, cap at 1.0

        return best_domain, confidence

    def get_default_workflow(self, domain: Domain) -> WorkflowTemplate | None:
        """Get default workflow for a domain."""
        domain_template = self._domains.get(domain)
        if domain_template:
            return self._workflows.get(domain_template.default_workflow)
        return None

    def register_agent(self, template: AgentTemplate):
        """Register a custom agent template."""
        self._agents[template.template_id] = template

    def register_workflow(self, template: WorkflowTemplate):
        """Register a custom workflow template."""
        self._workflows[template.template_id] = template

    def register_domain(self, template: DomainTemplate):
        """Register a custom domain template."""
        self._domains[template.domain] = template


# Global registry instance
REGISTRY = DomainTemplateRegistry()


def get_registry() -> DomainTemplateRegistry:
    """Get the global domain template registry."""
    return REGISTRY
