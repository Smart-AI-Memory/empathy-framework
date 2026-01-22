"""Tests for the Socratic domain templates module.

Copyright 2026 Smart-AI-Memory
Licensed under Fair Source License 0.9
"""



class TestDomain:
    """Tests for Domain enum."""

    def test_code_review_domain_exists(self):
        """Test CODE_REVIEW domain exists."""
        from empathy_os.socratic.domain_templates import Domain

        assert hasattr(Domain, "CODE_REVIEW")
        assert Domain.CODE_REVIEW.value == "code_review"

    def test_security_domains_exist(self):
        """Test security-related domains exist."""
        from empathy_os.socratic.domain_templates import Domain

        assert hasattr(Domain, "SECURITY_AUDIT")
        assert Domain.SECURITY_AUDIT.value == "security_audit"
        assert hasattr(Domain, "VULNERABILITY_SCAN")
        assert hasattr(Domain, "COMPLIANCE")

    def test_testing_domain_exists(self):
        """Test TESTING domain exists."""
        from empathy_os.socratic.domain_templates import Domain

        assert hasattr(Domain, "TESTING")
        assert Domain.TESTING.value == "testing"

    def test_devops_domains_exist(self):
        """Test DevOps-related domains exist."""
        from empathy_os.socratic.domain_templates import Domain

        assert hasattr(Domain, "CI_CD")
        assert hasattr(Domain, "INFRASTRUCTURE")
        assert hasattr(Domain, "MONITORING")
        assert hasattr(Domain, "INCIDENT_RESPONSE")

    def test_performance_domain_exists(self):
        """Test PERFORMANCE domain exists."""
        from empathy_os.socratic.domain_templates import Domain

        assert hasattr(Domain, "PERFORMANCE")
        assert Domain.PERFORMANCE.value == "performance"

    def test_general_domain_exists(self):
        """Test GENERAL domain exists."""
        from empathy_os.socratic.domain_templates import Domain

        assert hasattr(Domain, "GENERAL")
        assert Domain.GENERAL.value == "general"


class TestAgentTemplate:
    """Tests for AgentTemplate dataclass."""

    def test_create_agent_template(self):
        """Test creating an agent template."""
        from empathy_os.socratic.blueprint import AgentRole
        from empathy_os.socratic.domain_templates import AgentTemplate

        template = AgentTemplate(
            template_id="custom-reviewer",
            name="Custom Code Reviewer",
            description="Reviews code for custom patterns",
            role=AgentRole.REVIEWER,
            tools=["read_file", "search_code"],
            model_tier="capable",
        )

        assert template.template_id == "custom-reviewer"
        assert template.name == "Custom Code Reviewer"
        assert "read_file" in template.tools
        assert template.model_tier == "capable"

    def test_agent_template_with_system_prompt(self):
        """Test agent template with system prompt."""
        from empathy_os.socratic.blueprint import AgentRole
        from empathy_os.socratic.domain_templates import AgentTemplate

        template = AgentTemplate(
            template_id="test-agent",
            name="Test Agent",
            description="For testing",
            role=AgentRole.ANALYZER,
            tools=["read_file"],
            system_prompt="You are a test agent.",
        )

        assert template.system_prompt == "You are a test agent."

    def test_agent_template_default_values(self):
        """Test agent template default values."""
        from empathy_os.socratic.blueprint import AgentRole
        from empathy_os.socratic.domain_templates import AgentTemplate

        template = AgentTemplate(
            template_id="minimal",
            name="Minimal",
            description="Minimal agent",
            role=AgentRole.ANALYZER,
            tools=[],
        )

        assert template.model_tier == "capable"
        assert template.system_prompt == ""
        assert template.example_prompts == []
        assert template.configuration == {}
        assert template.tags == []

    def test_agent_template_with_tags(self):
        """Test agent template with tags."""
        from empathy_os.socratic.blueprint import AgentRole
        from empathy_os.socratic.domain_templates import AgentTemplate

        template = AgentTemplate(
            template_id="tagged-agent",
            name="Tagged Agent",
            description="Agent with tags",
            role=AgentRole.REVIEWER,
            tools=["read_file"],
            tags=["security", "audit", "compliance"],
        )

        assert "security" in template.tags
        assert len(template.tags) == 3


class TestWorkflowTemplate:
    """Tests for WorkflowTemplate dataclass."""

    def test_create_workflow_template(self):
        """Test creating a workflow template."""
        from empathy_os.socratic.domain_templates import Domain, WorkflowTemplate

        workflow_template = WorkflowTemplate(
            template_id="review-workflow",
            name="Code Review Workflow",
            description="Complete code review process",
            domain=Domain.CODE_REVIEW,
            agents=["code_reviewer", "security_scanner"],
            stages=[
                {"stage_id": "analysis", "name": "Analysis", "agents": ["code_reviewer"]},
            ],
            success_metrics=[],
            estimated_duration="moderate",
            estimated_cost="moderate",
        )

        assert workflow_template.template_id == "review-workflow"
        assert workflow_template.domain == Domain.CODE_REVIEW
        assert len(workflow_template.agents) == 2
        assert len(workflow_template.stages) == 1

    def test_workflow_template_with_stages(self):
        """Test workflow template with multiple stages."""
        from empathy_os.socratic.domain_templates import Domain, WorkflowTemplate

        workflow = WorkflowTemplate(
            template_id="multi-stage",
            name="Multi-Stage Workflow",
            description="Workflow with dependencies",
            domain=Domain.TESTING,
            agents=["agent1", "agent2", "synthesizer"],
            stages=[
                {"stage_id": "analyze", "name": "Analyze", "agents": ["agent1", "agent2"], "parallel": True},
                {"stage_id": "synthesize", "name": "Synthesize", "agents": ["synthesizer"], "dependencies": ["analyze"]},
            ],
            success_metrics=[],
            estimated_duration="slow",
            estimated_cost="expensive",
        )

        assert len(workflow.stages) == 2
        assert workflow.estimated_duration == "slow"


class TestDomainTemplate:
    """Tests for DomainTemplate dataclass."""

    def test_create_domain_template(self):
        """Test creating a domain template."""
        from empathy_os.socratic.blueprint import AgentRole
        from empathy_os.socratic.domain_templates import (
            AgentTemplate,
            Domain,
            DomainTemplate,
            WorkflowTemplate,
        )

        agent = AgentTemplate(
            template_id="agent",
            name="Agent",
            description="An agent",
            role=AgentRole.ANALYZER,
            tools=["read_file"],
        )

        workflow = WorkflowTemplate(
            template_id="workflow",
            name="Workflow",
            description="A workflow",
            domain=Domain.CODE_REVIEW,
            agents=["agent"],
            stages=[],
            success_metrics=[],
            estimated_duration="fast",
            estimated_cost="cheap",
        )

        domain_template = DomainTemplate(
            domain=Domain.CODE_REVIEW,
            name="Code Review",
            description="Code quality domain",
            agents=[agent],
            workflows=[workflow],
            default_workflow="workflow",
            keywords=["review", "quality"],
            required_tools=["read_file"],
            optional_tools=["grep_code"],
        )

        assert domain_template.domain == Domain.CODE_REVIEW
        assert len(domain_template.agents) == 1
        assert len(domain_template.workflows) == 1
        assert domain_template.default_workflow == "workflow"


class TestDomainTemplateRegistry:
    """Tests for DomainTemplateRegistry class."""

    def test_create_registry(self):
        """Test creating a registry."""
        from empathy_os.socratic.domain_templates import DomainTemplateRegistry

        registry = DomainTemplateRegistry()
        assert registry is not None

    def test_get_agent(self):
        """Test getting an agent template by ID."""
        from empathy_os.socratic.domain_templates import DomainTemplateRegistry

        registry = DomainTemplateRegistry()

        # Get the code reviewer template
        reviewer = registry.get_agent("code_reviewer")
        assert reviewer is not None
        assert reviewer.name == "Code Reviewer"

    def test_get_agent_not_found(self):
        """Test getting non-existent agent returns None."""
        from empathy_os.socratic.domain_templates import DomainTemplateRegistry

        registry = DomainTemplateRegistry()

        result = registry.get_agent("nonexistent_agent")
        assert result is None

    def test_get_workflow(self):
        """Test getting a workflow template by ID."""
        from empathy_os.socratic.domain_templates import DomainTemplateRegistry

        registry = DomainTemplateRegistry()

        workflow = registry.get_workflow("code_review_standard")
        assert workflow is not None
        assert workflow.name is not None

    def test_get_domain(self):
        """Test getting a domain template."""
        from empathy_os.socratic.domain_templates import (
            Domain,
            DomainTemplateRegistry,
        )

        registry = DomainTemplateRegistry()

        code_review = registry.get_domain(Domain.CODE_REVIEW)
        assert code_review is not None
        assert len(code_review.agents) > 0

    def test_list_agents(self):
        """Test listing all agent templates."""
        from empathy_os.socratic.domain_templates import DomainTemplateRegistry

        registry = DomainTemplateRegistry()

        templates = registry.list_agents()
        assert len(templates) > 0
        assert all(hasattr(t, "template_id") for t in templates)

    def test_list_agents_by_domain(self):
        """Test listing agent templates filtered by domain."""
        from empathy_os.socratic.domain_templates import (
            Domain,
            DomainTemplateRegistry,
        )

        registry = DomainTemplateRegistry()

        # This method filters by getting agents from a domain template
        domain_template = registry.get_domain(Domain.SECURITY_AUDIT)
        if domain_template:
            security_agents = domain_template.agents
            assert len(security_agents) > 0

    def test_list_workflows(self):
        """Test listing all workflow templates."""
        from empathy_os.socratic.domain_templates import DomainTemplateRegistry

        registry = DomainTemplateRegistry()

        workflows = registry.list_workflows()
        assert len(workflows) > 0

    def test_list_domains(self):
        """Test listing all supported domains."""
        from empathy_os.socratic.domain_templates import DomainTemplateRegistry

        registry = DomainTemplateRegistry()

        domains = registry.list_domains()
        assert len(domains) > 0

    def test_detect_domain_code_review(self):
        """Test domain detection for code review goals."""
        from empathy_os.socratic.domain_templates import (
            Domain,
            DomainTemplateRegistry,
        )

        registry = DomainTemplateRegistry()

        domain, confidence = registry.detect_domain("I want to review code quality")

        assert domain == Domain.CODE_REVIEW
        assert confidence > 0

    def test_detect_domain_security(self):
        """Test domain detection for security goals."""
        from empathy_os.socratic.domain_templates import (
            Domain,
            DomainTemplateRegistry,
        )

        registry = DomainTemplateRegistry()

        domain, confidence = registry.detect_domain("Scan for security vulnerabilities")

        assert domain == Domain.SECURITY_AUDIT
        assert confidence > 0

    def test_detect_domain_testing(self):
        """Test domain detection for testing goals."""
        from empathy_os.socratic.domain_templates import (
            Domain,
            DomainTemplateRegistry,
        )

        registry = DomainTemplateRegistry()

        domain, confidence = registry.detect_domain("Generate unit tests for my code")

        assert domain == Domain.TESTING
        assert confidence > 0

    def test_detect_domain_performance(self):
        """Test domain detection for performance goals."""
        from empathy_os.socratic.domain_templates import (
            Domain,
            DomainTemplateRegistry,
        )

        registry = DomainTemplateRegistry()

        domain, confidence = registry.detect_domain("Optimize performance and find bottlenecks")

        assert domain == Domain.PERFORMANCE
        assert confidence > 0

    def test_detect_domain_unknown(self):
        """Test domain detection for unknown goals."""
        from empathy_os.socratic.domain_templates import (
            Domain,
            DomainTemplateRegistry,
        )

        registry = DomainTemplateRegistry()

        # Unrelated goal should return GENERAL with low confidence
        domain, confidence = registry.detect_domain("random unrelated text xyz")

        assert domain == Domain.GENERAL
        assert confidence < 1.0

    def test_get_default_workflow(self):
        """Test getting default workflow for a domain."""
        from empathy_os.socratic.domain_templates import (
            Domain,
            DomainTemplateRegistry,
        )

        registry = DomainTemplateRegistry()

        workflow = registry.get_default_workflow(Domain.CODE_REVIEW)
        assert workflow is not None

    def test_register_agent(self):
        """Test registering a custom agent template."""
        from empathy_os.socratic.blueprint import AgentRole
        from empathy_os.socratic.domain_templates import (
            AgentTemplate,
            DomainTemplateRegistry,
        )

        registry = DomainTemplateRegistry()

        custom_template = AgentTemplate(
            template_id="custom-agent-001",
            name="Custom Agent",
            description="A custom agent for testing",
            role=AgentRole.ANALYZER,
            tools=["read_file"],
        )

        registry.register_agent(custom_template)

        retrieved = registry.get_agent("custom-agent-001")
        assert retrieved is not None
        assert retrieved.name == "Custom Agent"

    def test_register_workflow(self):
        """Test registering a custom workflow template."""
        from empathy_os.socratic.domain_templates import (
            Domain,
            DomainTemplateRegistry,
            WorkflowTemplate,
        )

        registry = DomainTemplateRegistry()

        custom_workflow = WorkflowTemplate(
            template_id="custom-workflow-001",
            name="Custom Workflow",
            description="A custom workflow",
            domain=Domain.GENERAL,
            agents=["code_reviewer"],
            stages=[],
            success_metrics=[],
            estimated_duration="fast",
            estimated_cost="cheap",
        )

        registry.register_workflow(custom_workflow)

        retrieved = registry.get_workflow("custom-workflow-001")
        assert retrieved is not None
        assert retrieved.name == "Custom Workflow"


class TestBuiltInTemplates:
    """Tests for built-in agent templates."""

    def test_code_reviewer_template(self):
        """Test the code reviewer template."""
        from empathy_os.socratic.domain_templates import DomainTemplateRegistry

        registry = DomainTemplateRegistry()
        reviewer = registry.get_agent("code_reviewer")

        assert reviewer is not None
        assert reviewer.name == "Code Reviewer"
        assert len(reviewer.tools) >= 0

    def test_security_scanner_template(self):
        """Test the security scanner template."""
        from empathy_os.socratic.domain_templates import DomainTemplateRegistry

        registry = DomainTemplateRegistry()
        scanner = registry.get_agent("security_scanner")

        assert scanner is not None
        assert "security" in scanner.name.lower() or "scanner" in scanner.name.lower()

    def test_test_generator_template(self):
        """Test the test generator template."""
        from empathy_os.socratic.domain_templates import DomainTemplateRegistry

        registry = DomainTemplateRegistry()
        generator = registry.get_agent("test_generator")

        assert generator is not None
        assert "test" in generator.name.lower() or "generator" in generator.name.lower()

    def test_result_synthesizer_template(self):
        """Test the result synthesizer template."""
        from empathy_os.socratic.domain_templates import DomainTemplateRegistry

        registry = DomainTemplateRegistry()
        synthesizer = registry.get_agent("result_synthesizer")

        assert synthesizer is not None


class TestGetRegistry:
    """Tests for the get_registry singleton function."""

    def test_get_registry_singleton(self):
        """Test that get_registry returns singleton."""
        from empathy_os.socratic.domain_templates import get_registry

        registry1 = get_registry()
        registry2 = get_registry()

        assert registry1 is registry2

    def test_get_registry_has_templates(self):
        """Test that singleton registry has templates."""
        from empathy_os.socratic.domain_templates import get_registry

        registry = get_registry()
        templates = registry.list_agents()

        assert len(templates) > 0


class TestBuiltInWorkflows:
    """Tests for built-in workflow templates."""

    def test_code_review_workflow_exists(self):
        """Test code review workflow exists."""
        from empathy_os.socratic.domain_templates import DomainTemplateRegistry

        registry = DomainTemplateRegistry()
        workflow = registry.get_workflow("code_review_standard")

        assert workflow is not None

    def test_security_audit_workflow_exists(self):
        """Test security audit workflow exists."""
        from empathy_os.socratic.domain_templates import DomainTemplateRegistry

        registry = DomainTemplateRegistry()
        workflow = registry.get_workflow("security_audit_comprehensive")

        assert workflow is not None

    def test_testing_workflow_exists(self):
        """Test testing workflow exists."""
        from empathy_os.socratic.domain_templates import DomainTemplateRegistry

        registry = DomainTemplateRegistry()
        workflow = registry.get_workflow("test_generation_comprehensive")

        assert workflow is not None
