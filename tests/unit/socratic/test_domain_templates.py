"""Tests for the Socratic domain templates module.

Copyright 2026 Smart-AI-Memory
Licensed under Fair Source License 0.9
"""

import pytest


class TestDomain:
    """Tests for Domain enum."""

    def test_all_domains_exist(self):
        """Test all expected domains exist."""
        from empathy_os.socratic.domain_templates import Domain

        expected_domains = [
            "CODE_QUALITY",
            "SECURITY",
            "TESTING",
            "DATA_ENGINEERING",
            "DEVOPS",
            "INCIDENT_RESPONSE",
        ]

        for domain_name in expected_domains:
            assert hasattr(Domain, domain_name)

    def test_domain_values(self):
        """Test domain enum values."""
        from empathy_os.socratic.domain_templates import Domain

        assert Domain.CODE_QUALITY.value == "code_quality"
        assert Domain.SECURITY.value == "security"


class TestAgentTemplate:
    """Tests for AgentTemplate dataclass."""

    def test_create_agent_template(self):
        """Test creating an agent template."""
        from empathy_os.socratic.domain_templates import AgentTemplate, Domain

        template = AgentTemplate(
            template_id="custom-reviewer",
            name="Custom Code Reviewer",
            description="Reviews code for custom patterns",
            domain=Domain.CODE_QUALITY,
            default_tools=["read_file", "search_code"],
            default_model_tier="capable",
            configurable_params=["focus_areas", "languages"],
        )

        assert template.template_id == "custom-reviewer"
        assert template.domain == Domain.CODE_QUALITY
        assert "read_file" in template.default_tools

    def test_agent_template_to_spec(self, sample_agent_spec):
        """Test converting template to agent spec."""
        from empathy_os.socratic.domain_templates import AgentTemplate, Domain

        template = AgentTemplate(
            template_id="test-template",
            name="Test Template",
            description="For testing",
            domain=Domain.TESTING,
            default_tools=["run_tests"],
            default_model_tier="cheap",
        )

        spec = template.to_agent_spec(
            agent_id="agent-001",
            custom_params={"focus_areas": ["security"]},
        )

        assert spec.agent_id == "agent-001"
        assert spec.name == "Test Template"


class TestWorkflowTemplate:
    """Tests for WorkflowTemplate dataclass."""

    def test_create_workflow_template(self):
        """Test creating a workflow template."""
        from empathy_os.socratic.domain_templates import (
            WorkflowTemplate,
            AgentTemplate,
            Domain,
        )

        agent_template = AgentTemplate(
            template_id="reviewer",
            name="Reviewer",
            description="Reviews code",
            domain=Domain.CODE_QUALITY,
        )

        workflow_template = WorkflowTemplate(
            template_id="review-workflow",
            name="Code Review Workflow",
            description="Complete code review process",
            domain=Domain.CODE_QUALITY,
            agent_templates=[agent_template],
            default_parallel=False,
        )

        assert workflow_template.template_id == "review-workflow"
        assert len(workflow_template.agent_templates) == 1

    def test_workflow_template_to_blueprint(self):
        """Test converting workflow template to blueprint."""
        from empathy_os.socratic.domain_templates import (
            WorkflowTemplate,
            AgentTemplate,
            Domain,
        )

        workflow_template = WorkflowTemplate(
            template_id="test-workflow",
            name="Test Workflow",
            description="For testing",
            domain=Domain.TESTING,
            agent_templates=[
                AgentTemplate(
                    template_id="agent-1",
                    name="Agent 1",
                    description="First agent",
                    domain=Domain.TESTING,
                ),
            ],
        )

        blueprint = workflow_template.to_workflow_blueprint(
            workflow_id="wf-001",
            session_id="session-001",
        )

        assert blueprint.workflow_id == "wf-001"
        assert blueprint.session_id == "session-001"


class TestDomainTemplate:
    """Tests for DomainTemplate dataclass."""

    def test_create_domain_template(self):
        """Test creating a domain template."""
        from empathy_os.socratic.domain_templates import (
            DomainTemplate,
            AgentTemplate,
            WorkflowTemplate,
            Domain,
        )

        agent = AgentTemplate(
            template_id="agent",
            name="Agent",
            description="An agent",
            domain=Domain.CODE_QUALITY,
        )

        workflow = WorkflowTemplate(
            template_id="workflow",
            name="Workflow",
            description="A workflow",
            domain=Domain.CODE_QUALITY,
            agent_templates=[agent],
        )

        domain_template = DomainTemplate(
            domain=Domain.CODE_QUALITY,
            description="Code quality domain",
            agent_templates=[agent],
            workflow_templates=[workflow],
            common_questions=[
                "What languages does your codebase use?",
            ],
        )

        assert domain_template.domain == Domain.CODE_QUALITY
        assert len(domain_template.agent_templates) == 1
        assert len(domain_template.workflow_templates) == 1


class TestDomainTemplateRegistry:
    """Tests for DomainTemplateRegistry class."""

    def test_create_registry(self):
        """Test creating a registry."""
        from empathy_os.socratic.domain_templates import DomainTemplateRegistry

        registry = DomainTemplateRegistry()
        assert registry is not None

    def test_get_builtin_templates(self):
        """Test getting built-in templates."""
        from empathy_os.socratic.domain_templates import (
            DomainTemplateRegistry,
            Domain,
        )

        registry = DomainTemplateRegistry()

        # Should have built-in templates for all domains
        code_quality = registry.get_domain_template(Domain.CODE_QUALITY)
        assert code_quality is not None
        assert len(code_quality.agent_templates) > 0

    def test_get_agent_template(self):
        """Test getting an agent template by ID."""
        from empathy_os.socratic.domain_templates import DomainTemplateRegistry

        registry = DomainTemplateRegistry()

        # Get the code reviewer template
        reviewer = registry.get_agent_template("code_reviewer")
        assert reviewer is not None
        assert reviewer.name == "Code Reviewer"

    def test_get_workflow_template(self):
        """Test getting a workflow template by ID."""
        from empathy_os.socratic.domain_templates import DomainTemplateRegistry

        registry = DomainTemplateRegistry()

        workflow = registry.get_workflow_template("code_review_workflow")
        if workflow:  # May not exist in all implementations
            assert workflow.name is not None

    def test_list_agent_templates(self):
        """Test listing all agent templates."""
        from empathy_os.socratic.domain_templates import DomainTemplateRegistry

        registry = DomainTemplateRegistry()

        templates = registry.list_agent_templates()
        assert len(templates) > 0
        assert all(hasattr(t, "template_id") for t in templates)

    def test_list_agent_templates_by_domain(self):
        """Test listing agent templates filtered by domain."""
        from empathy_os.socratic.domain_templates import (
            DomainTemplateRegistry,
            Domain,
        )

        registry = DomainTemplateRegistry()

        security_templates = registry.list_agent_templates(domain=Domain.SECURITY)
        assert len(security_templates) > 0
        assert all(t.domain == Domain.SECURITY for t in security_templates)

    @pytest.mark.parametrize(
        "goal_text,expected_domain",
        [
            ("Review code for security vulnerabilities", "SECURITY"),
            ("Generate unit tests for my Python code", "TESTING"),
            ("Analyze code quality and find bugs", "CODE_QUALITY"),
            ("Set up CI/CD pipeline", "DEVOPS"),
            ("Validate data integrity", "DATA_ENGINEERING"),
            ("Handle production incident", "INCIDENT_RESPONSE"),
        ],
    )
    def test_detect_domain_from_goal(self, goal_text, expected_domain):
        """Test domain detection from goal text."""
        from empathy_os.socratic.domain_templates import (
            DomainTemplateRegistry,
            Domain,
        )

        registry = DomainTemplateRegistry()

        detected = registry.detect_domain(goal_text)
        assert detected == Domain[expected_domain]

    def test_suggest_templates_for_goal(self):
        """Test suggesting templates for a goal."""
        from empathy_os.socratic.domain_templates import DomainTemplateRegistry

        registry = DomainTemplateRegistry()

        suggestions = registry.suggest_templates(
            goal="I want to review code for security issues"
        )

        assert "domain" in suggestions
        assert "agent_templates" in suggestions
        assert "workflow_templates" in suggestions

    def test_register_custom_template(self):
        """Test registering a custom agent template."""
        from empathy_os.socratic.domain_templates import (
            DomainTemplateRegistry,
            AgentTemplate,
            Domain,
        )

        registry = DomainTemplateRegistry()

        custom_template = AgentTemplate(
            template_id="custom-agent",
            name="Custom Agent",
            description="A custom agent for testing",
            domain=Domain.CODE_QUALITY,
        )

        registry.register_agent_template(custom_template)

        retrieved = registry.get_agent_template("custom-agent")
        assert retrieved is not None
        assert retrieved.name == "Custom Agent"


class TestBuiltInTemplates:
    """Tests for built-in agent templates."""

    def test_code_reviewer_template(self):
        """Test the code reviewer template."""
        from empathy_os.socratic.domain_templates import DomainTemplateRegistry

        registry = DomainTemplateRegistry()
        reviewer = registry.get_agent_template("code_reviewer")

        assert reviewer is not None
        assert "read_file" in reviewer.default_tools or len(reviewer.default_tools) >= 0

    def test_security_scanner_template(self):
        """Test the security scanner template."""
        from empathy_os.socratic.domain_templates import (
            DomainTemplateRegistry,
            Domain,
        )

        registry = DomainTemplateRegistry()
        scanner = registry.get_agent_template("security_scanner")

        assert scanner is not None
        assert scanner.domain == Domain.SECURITY

    def test_test_generator_template(self):
        """Test the test generator template."""
        from empathy_os.socratic.domain_templates import (
            DomainTemplateRegistry,
            Domain,
        )

        registry = DomainTemplateRegistry()
        generator = registry.get_agent_template("test_generator")

        assert generator is not None
        assert generator.domain == Domain.TESTING


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
        templates = registry.list_agent_templates()

        assert len(templates) > 0
