"""Tests for the Socratic blueprint module.

Copyright 2026 Smart-AI-Memory
Licensed under Fair Source License 0.9
"""

import pytest
from datetime import datetime


class TestAgentSpec:
    """Tests for AgentSpec class."""

    def test_create_agent_spec(self, sample_agent_spec):
        """Test creating an AgentSpec."""
        assert sample_agent_spec.agent_id == "test-agent-001"
        assert sample_agent_spec.name == "Test Code Reviewer"
        assert len(sample_agent_spec.tools) == 2

    def test_agent_role(self, sample_agent_spec):
        """Test agent role."""
        from empathy_os.socratic.blueprint import AgentRole

        assert sample_agent_spec.role == AgentRole.REVIEWER

    def test_agent_serialization(self, sample_agent_spec):
        """Test agent serialization."""
        from empathy_os.socratic.blueprint import AgentSpec

        data = sample_agent_spec.to_dict()

        assert data["agent_id"] == sample_agent_spec.agent_id
        assert data["name"] == sample_agent_spec.name
        assert data["role"] == sample_agent_spec.role.value

    def test_agent_deserialization(self, sample_agent_spec):
        """Test agent deserialization."""
        from empathy_os.socratic.blueprint import AgentSpec

        data = sample_agent_spec.to_dict()
        restored = AgentSpec.from_dict(data)

        assert restored.agent_id == sample_agent_spec.agent_id
        assert restored.role == sample_agent_spec.role


class TestToolSpec:
    """Tests for ToolSpec class."""

    def test_create_tool_spec(self):
        """Test creating a ToolSpec."""
        from empathy_os.socratic.blueprint import ToolSpec, ToolCategory

        tool = ToolSpec(
            tool_id="security_scan",
            name="Security Scanner",
            description="Scans for vulnerabilities",
            category=ToolCategory.SECURITY,
        )

        assert tool.tool_id == "security_scan"
        assert tool.category == ToolCategory.SECURITY


class TestStageSpec:
    """Tests for StageSpec class."""

    def test_create_stage_spec(self):
        """Test creating a StageSpec."""
        from empathy_os.socratic.blueprint import StageSpec

        stage = StageSpec(
            stage_id="analysis",
            name="Code Analysis",
            agent_ids=["agent1", "agent2"],
            parallel=True,
        )

        assert stage.stage_id == "analysis"
        assert stage.parallel is True
        assert len(stage.agent_ids) == 2

    def test_stage_with_dependencies(self):
        """Test stage with dependencies."""
        from empathy_os.socratic.blueprint import StageSpec

        stage = StageSpec(
            stage_id="synthesis",
            name="Result Synthesis",
            agent_ids=["synthesizer"],
            dependencies=["analysis", "review"],
        )

        assert len(stage.dependencies) == 2
        assert "analysis" in stage.dependencies


class TestWorkflowBlueprint:
    """Tests for WorkflowBlueprint class."""

    def test_create_workflow_blueprint(self, sample_workflow_blueprint):
        """Test creating a WorkflowBlueprint."""
        assert sample_workflow_blueprint.blueprint_id == "test-blueprint-001"
        assert sample_workflow_blueprint.name == "Test Code Review Workflow"
        assert len(sample_workflow_blueprint.agents) == 2
        assert len(sample_workflow_blueprint.stages) == 2

    def test_workflow_domains(self, sample_workflow_blueprint):
        """Test workflow domains."""
        assert "code_review" in sample_workflow_blueprint.domains

    def test_workflow_serialization(self, sample_workflow_blueprint):
        """Test workflow serialization."""
        from empathy_os.socratic.blueprint import WorkflowBlueprint

        data = sample_workflow_blueprint.to_dict()

        assert data["blueprint_id"] == sample_workflow_blueprint.blueprint_id
        assert len(data["agents"]) == 2
        assert len(data["stages"]) == 2

    def test_workflow_deserialization(self, sample_workflow_blueprint):
        """Test workflow deserialization."""
        from empathy_os.socratic.blueprint import WorkflowBlueprint

        data = sample_workflow_blueprint.to_dict()
        restored = WorkflowBlueprint.from_dict(data)

        assert restored.blueprint_id == sample_workflow_blueprint.blueprint_id
        assert len(restored.agents) == len(sample_workflow_blueprint.agents)


class TestAgentRole:
    """Tests for AgentRole enum."""

    def test_all_roles_exist(self):
        """Test all agent roles exist."""
        from empathy_os.socratic.blueprint import AgentRole

        roles = [
            AgentRole.ANALYZER,
            AgentRole.REVIEWER,
            AgentRole.AUDITOR,
            AgentRole.GENERATOR,
            AgentRole.FIXER,
            AgentRole.ORCHESTRATOR,
            AgentRole.RESEARCHER,
            AgentRole.VALIDATOR,
        ]

        assert len(roles) == 8


class TestToolCategory:
    """Tests for ToolCategory enum."""

    def test_all_categories_exist(self):
        """Test all tool categories exist."""
        from empathy_os.socratic.blueprint import ToolCategory

        categories = [
            ToolCategory.CODE_ANALYSIS,
            ToolCategory.SECURITY,
            ToolCategory.TESTING,
            ToolCategory.DOCUMENTATION,
            ToolCategory.MODIFICATION,
            ToolCategory.COMMUNICATION,
        ]

        assert len(categories) == 6
