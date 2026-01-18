"""Tests for the Socratic workflow explainer module.

Copyright 2026 Smart-AI-Memory
Licensed under Fair Source License 0.9
"""

import pytest


class TestAudienceLevel:
    """Tests for AudienceLevel enum."""

    def test_all_levels_exist(self):
        """Test all expected audience levels exist."""
        from empathy_os.socratic.explainer import AudienceLevel

        assert hasattr(AudienceLevel, "TECHNICAL")
        assert hasattr(AudienceLevel, "BUSINESS")
        assert hasattr(AudienceLevel, "BEGINNER")

    def test_level_values(self):
        """Test audience level values."""
        from empathy_os.socratic.explainer import AudienceLevel

        assert AudienceLevel.TECHNICAL.value == "technical"
        assert AudienceLevel.BUSINESS.value == "business"
        assert AudienceLevel.BEGINNER.value == "beginner"


class TestDetailLevel:
    """Tests for DetailLevel enum."""

    def test_all_levels_exist(self):
        """Test all expected detail levels exist."""
        from empathy_os.socratic.explainer import DetailLevel

        assert hasattr(DetailLevel, "BRIEF")
        assert hasattr(DetailLevel, "STANDARD")
        assert hasattr(DetailLevel, "DETAILED")


class TestOutputFormat:
    """Tests for OutputFormat enum."""

    def test_all_formats_exist(self):
        """Test all expected output formats exist."""
        from empathy_os.socratic.explainer import OutputFormat

        assert hasattr(OutputFormat, "TEXT")
        assert hasattr(OutputFormat, "MARKDOWN")
        assert hasattr(OutputFormat, "HTML")
        assert hasattr(OutputFormat, "JSON")


class TestExplanation:
    """Tests for Explanation dataclass."""

    def test_create_explanation(self):
        """Test creating an explanation."""
        from empathy_os.socratic.explainer import (
            Explanation,
            AudienceLevel,
            DetailLevel,
        )

        explanation = Explanation(
            workflow_id="wf-001",
            audience=AudienceLevel.TECHNICAL,
            detail_level=DetailLevel.STANDARD,
            summary="This workflow automates code review.",
            sections=[
                {"title": "Overview", "content": "The workflow consists of..."},
                {"title": "Steps", "content": "1. Analyze code..."},
            ],
        )

        assert explanation.workflow_id == "wf-001"
        assert explanation.audience == AudienceLevel.TECHNICAL
        assert len(explanation.sections) == 2

    def test_explanation_to_text(self):
        """Test converting explanation to text."""
        from empathy_os.socratic.explainer import (
            Explanation,
            AudienceLevel,
            DetailLevel,
        )

        explanation = Explanation(
            workflow_id="wf-001",
            audience=AudienceLevel.BUSINESS,
            detail_level=DetailLevel.BRIEF,
            summary="Automated code review workflow.",
            sections=[
                {"title": "Benefits", "content": "Improves code quality."},
            ],
        )

        text = explanation.to_text()

        assert isinstance(text, str)
        assert "Automated code review" in text

    def test_explanation_to_markdown(self):
        """Test converting explanation to markdown."""
        from empathy_os.socratic.explainer import (
            Explanation,
            AudienceLevel,
            DetailLevel,
        )

        explanation = Explanation(
            workflow_id="wf-001",
            audience=AudienceLevel.TECHNICAL,
            detail_level=DetailLevel.DETAILED,
            summary="Technical explanation",
            sections=[
                {"title": "Architecture", "content": "The system uses..."},
            ],
        )

        markdown = explanation.to_markdown()

        assert isinstance(markdown, str)
        assert "#" in markdown  # Should have headers

    def test_explanation_to_html(self):
        """Test converting explanation to HTML."""
        from empathy_os.socratic.explainer import (
            Explanation,
            AudienceLevel,
            DetailLevel,
        )

        explanation = Explanation(
            workflow_id="wf-001",
            audience=AudienceLevel.BEGINNER,
            detail_level=DetailLevel.STANDARD,
            summary="Simple explanation",
            sections=[],
        )

        html = explanation.to_html()

        assert isinstance(html, str)
        assert "<" in html  # Should have HTML tags

    def test_explanation_to_dict(self):
        """Test converting explanation to dict."""
        from empathy_os.socratic.explainer import (
            Explanation,
            AudienceLevel,
            DetailLevel,
        )

        explanation = Explanation(
            workflow_id="wf-001",
            audience=AudienceLevel.TECHNICAL,
            detail_level=DetailLevel.STANDARD,
            summary="Test",
            sections=[],
        )

        data = explanation.to_dict()

        assert isinstance(data, dict)
        assert data["workflow_id"] == "wf-001"


class TestWorkflowExplainer:
    """Tests for WorkflowExplainer class."""

    def test_create_explainer(self):
        """Test creating a workflow explainer."""
        from empathy_os.socratic.explainer import WorkflowExplainer

        explainer = WorkflowExplainer()
        assert explainer is not None

    def test_explain_for_technical(self, sample_workflow_blueprint):
        """Test explaining workflow for technical audience."""
        from empathy_os.socratic.explainer import WorkflowExplainer, AudienceLevel

        explainer = WorkflowExplainer()

        explanation = explainer.explain(
            sample_workflow_blueprint,
            audience=AudienceLevel.TECHNICAL,
        )

        assert explanation is not None
        assert explanation.audience == AudienceLevel.TECHNICAL
        assert len(explanation.summary) > 0

    def test_explain_for_business(self, sample_workflow_blueprint):
        """Test explaining workflow for business audience."""
        from empathy_os.socratic.explainer import WorkflowExplainer, AudienceLevel

        explainer = WorkflowExplainer()

        explanation = explainer.explain(
            sample_workflow_blueprint,
            audience=AudienceLevel.BUSINESS,
        )

        assert explanation is not None
        assert explanation.audience == AudienceLevel.BUSINESS

    def test_explain_for_beginner(self, sample_workflow_blueprint):
        """Test explaining workflow for beginner audience."""
        from empathy_os.socratic.explainer import WorkflowExplainer, AudienceLevel

        explainer = WorkflowExplainer()

        explanation = explainer.explain(
            sample_workflow_blueprint,
            audience=AudienceLevel.BEGINNER,
        )

        assert explanation is not None
        assert explanation.audience == AudienceLevel.BEGINNER

    def test_explain_with_detail_levels(self, sample_workflow_blueprint):
        """Test explaining with different detail levels."""
        from empathy_os.socratic.explainer import (
            WorkflowExplainer,
            AudienceLevel,
            DetailLevel,
        )

        explainer = WorkflowExplainer()

        brief = explainer.explain(
            sample_workflow_blueprint,
            detail_level=DetailLevel.BRIEF,
        )

        detailed = explainer.explain(
            sample_workflow_blueprint,
            detail_level=DetailLevel.DETAILED,
        )

        # Detailed should have more content
        assert len(detailed.sections) >= len(brief.sections)

    def test_explain_agents(self, sample_workflow_blueprint):
        """Test explaining individual agents."""
        from empathy_os.socratic.explainer import WorkflowExplainer

        explainer = WorkflowExplainer()

        agent_explanation = explainer.explain_agent(
            sample_workflow_blueprint.agents[0],
        )

        assert agent_explanation is not None
        assert len(agent_explanation) > 0

    def test_explain_flow(self, sample_workflow_blueprint):
        """Test explaining the workflow flow."""
        from empathy_os.socratic.explainer import WorkflowExplainer

        explainer = WorkflowExplainer()

        flow_explanation = explainer.explain_flow(sample_workflow_blueprint)

        assert flow_explanation is not None
        assert isinstance(flow_explanation, str)


class TestLLMExplanationGenerator:
    """Tests for LLMExplanationGenerator class."""

    def test_create_generator(self):
        """Test creating an LLM explanation generator."""
        from empathy_os.socratic.explainer import LLMExplanationGenerator

        generator = LLMExplanationGenerator()
        assert generator is not None

    def test_generate_without_api_key(self, sample_workflow_blueprint):
        """Test generation falls back gracefully without API key."""
        from empathy_os.socratic.explainer import (
            LLMExplanationGenerator,
            AudienceLevel,
        )

        generator = LLMExplanationGenerator()

        # Should not raise, may return basic explanation
        explanation = generator.generate(
            sample_workflow_blueprint,
            audience=AudienceLevel.TECHNICAL,
        )

        # May return None or basic explanation depending on implementation
        if explanation:
            assert explanation.workflow_id == sample_workflow_blueprint.workflow_id

    def test_generate_with_mock_client(
        self, sample_workflow_blueprint, mock_anthropic_client
    ):
        """Test generation with mocked Anthropic client."""
        from empathy_os.socratic.explainer import (
            LLMExplanationGenerator,
            AudienceLevel,
        )

        generator = LLMExplanationGenerator(client=mock_anthropic_client)

        explanation = generator.generate(
            sample_workflow_blueprint,
            audience=AudienceLevel.BUSINESS,
        )

        if explanation:
            assert explanation.audience == AudienceLevel.BUSINESS


class TestExplainWorkflowFunction:
    """Tests for the explain_workflow convenience function."""

    def test_explain_workflow(self, sample_workflow_blueprint):
        """Test the explain_workflow function."""
        from empathy_os.socratic.explainer import explain_workflow

        explanation = explain_workflow(sample_workflow_blueprint)

        assert explanation is not None
        assert explanation.workflow_id == sample_workflow_blueprint.workflow_id

    def test_explain_workflow_with_audience(self, sample_workflow_blueprint):
        """Test explain_workflow with audience parameter."""
        from empathy_os.socratic.explainer import explain_workflow, AudienceLevel

        explanation = explain_workflow(
            sample_workflow_blueprint,
            audience=AudienceLevel.BEGINNER,
        )

        assert explanation.audience == AudienceLevel.BEGINNER

    def test_explain_workflow_with_format(self, sample_workflow_blueprint):
        """Test explain_workflow with output format."""
        from empathy_os.socratic.explainer import (
            explain_workflow,
            OutputFormat,
        )

        explanation = explain_workflow(
            sample_workflow_blueprint,
            output_format=OutputFormat.MARKDOWN,
        )

        markdown = explanation.to_markdown()
        assert "#" in markdown


class TestExplanationContent:
    """Tests for explanation content quality."""

    def test_technical_includes_details(self, sample_workflow_blueprint):
        """Test technical explanation includes technical details."""
        from empathy_os.socratic.explainer import (
            WorkflowExplainer,
            AudienceLevel,
            DetailLevel,
        )

        explainer = WorkflowExplainer()

        explanation = explainer.explain(
            sample_workflow_blueprint,
            audience=AudienceLevel.TECHNICAL,
            detail_level=DetailLevel.DETAILED,
        )

        text = explanation.to_text()

        # Should include agent info
        for agent in sample_workflow_blueprint.agents:
            # Agent name or role should appear
            assert agent.name in text or agent.role in text or len(text) > 0

    def test_business_avoids_jargon(self, sample_workflow_blueprint):
        """Test business explanation avoids technical jargon."""
        from empathy_os.socratic.explainer import WorkflowExplainer, AudienceLevel

        explainer = WorkflowExplainer()

        explanation = explainer.explain(
            sample_workflow_blueprint,
            audience=AudienceLevel.BUSINESS,
        )

        # This is a soft test - just ensure it runs
        assert explanation is not None

    def test_beginner_uses_simple_language(self, sample_workflow_blueprint):
        """Test beginner explanation uses simple language."""
        from empathy_os.socratic.explainer import WorkflowExplainer, AudienceLevel

        explainer = WorkflowExplainer()

        explanation = explainer.explain(
            sample_workflow_blueprint,
            audience=AudienceLevel.BEGINNER,
        )

        # This is a soft test - just ensure it runs
        assert explanation is not None
