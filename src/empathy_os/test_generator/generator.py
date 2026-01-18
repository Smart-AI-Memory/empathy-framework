"""Test generator core implementation.

Generates comprehensive tests for wizards using Jinja2 templates
and risk-based prioritization.

Copyright 2025 Smart AI Memory, LLC
Licensed under Fair Source 0.9
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

from patterns import get_pattern_registry
from patterns.structural import LinearFlowPattern, PhasedProcessingPattern

from .risk_analyzer import RiskAnalyzer

logger = logging.getLogger(__name__)


class TestGenerator:
    """Generates tests for wizards based on patterns and risk analysis.

    Uses Jinja2 templates to generate:
    - Unit tests with risk-prioritized coverage
    - Integration tests for multi-step workflows
    - E2E tests for critical paths
    - Test fixtures for common patterns
    """

    def __init__(self, template_dir: Path | None = None):
        """Initialize test generator.

        Args:
            template_dir: Directory containing Jinja2 templates
                         (defaults to test_generator/templates/)

        """
        if template_dir is None:
            template_dir = Path(__file__).parent / "templates"

        self.template_dir = template_dir
        self.env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            trim_blocks=True,
            lstrip_blocks=True,
            autoescape=True,  # Enable autoescape for security (test gen templates should be safe)
        )

        self.risk_analyzer = RiskAnalyzer()
        self.registry = get_pattern_registry()

    def generate_tests(
        self,
        wizard_id: str,
        pattern_ids: list[str],
        wizard_module: str | None = None,
        wizard_class: str | None = None,
    ) -> dict[str, str | None]:
        """Generate tests for a wizard.

        Args:
            wizard_id: Wizard identifier
            pattern_ids: List of pattern IDs used by wizard
            wizard_module: Python module path (e.g., "wizards.soap_note")
            wizard_class: Wizard class name (e.g., "SOAPNoteWizard")

        Returns:
            Dictionary with test types:
                {
                    "unit": "...",  # Unit test code
                    "integration": "...",  # Integration test code (if applicable)
                    "fixtures": "...",  # Test fixtures
                }

        """
        logger.info(f"Generating tests for wizard: {wizard_id}")

        # Perform risk analysis
        risk_analysis = self.risk_analyzer.analyze(wizard_id, pattern_ids)

        # Infer module and class if not provided
        if not wizard_module:
            wizard_module = self._infer_module(wizard_id)

        if not wizard_class:
            wizard_class = self._infer_class_name(wizard_id)

        # Gather template context
        context = self._build_template_context(
            wizard_id=wizard_id,
            pattern_ids=pattern_ids,
            wizard_module=wizard_module,
            wizard_class=wizard_class,
            risk_analysis=risk_analysis,
        )

        # Generate unit tests (always)
        unit_tests = self._generate_unit_tests(context)

        # Generate integration tests (for multi-step wizards)
        integration_tests = None
        if self._needs_integration_tests(pattern_ids):
            integration_tests = self._generate_integration_tests(context)

        # Generate test fixtures
        fixtures = self._generate_fixtures(context)

        logger.info(
            f"Generated tests for {wizard_id}: "
            f"unit={len(unit_tests)} chars, "
            f"integration={'yes' if integration_tests else 'no'}, "
            f"fixtures={len(fixtures)} chars"
        )

        return {
            "unit": unit_tests,
            "integration": integration_tests,
            "fixtures": fixtures,
        }

    def _build_template_context(
        self,
        wizard_id: str,
        pattern_ids: list[str],
        wizard_module: str,
        wizard_class: str,
        risk_analysis: Any,
    ) -> dict:
        """Build Jinja2 template context.

        Args:
            wizard_id: Wizard identifier
            pattern_ids: Pattern IDs
            wizard_module: Module path
            wizard_class: Class name
            risk_analysis: RiskAnalysis object

        Returns:
            Context dictionary for templates

        """
        # Get pattern details
        patterns = [self.registry.get(pid) for pid in pattern_ids if self.registry.get(pid)]

        # Check for specific patterns
        has_linear_flow = "linear_flow" in pattern_ids
        has_phased = "phased_processing" in pattern_ids
        has_approval = "approval" in pattern_ids
        has_async = True  # Assume async by default for modern wizards

        # Get linear flow details if present
        total_steps = None
        if has_linear_flow:
            linear_pattern = self.registry.get("linear_flow")
            if isinstance(linear_pattern, LinearFlowPattern):
                total_steps = linear_pattern.total_steps

        # Get phases if present
        phases = []
        if has_phased:
            phased_pattern = self.registry.get("phased_processing")
            if isinstance(phased_pattern, PhasedProcessingPattern):
                phases = phased_pattern.phases

        return {
            "wizard_id": wizard_id,
            "wizard_module": wizard_module,
            "wizard_class": wizard_class,
            "pattern_ids": pattern_ids,
            "patterns": patterns,
            "risk_analysis": risk_analysis,
            "has_async": has_async,
            "has_linear_flow": has_linear_flow,
            "has_phased": has_phased,
            "has_approval": has_approval,
            "total_steps": total_steps,
            "phases": phases,
            "timestamp": datetime.now().isoformat(),
        }

    def _generate_unit_tests(self, context: dict) -> str:
        """Generate unit tests from template.

        Args:
            context: Template context

        Returns:
            Generated unit test code

        """
        template = self.env.get_template("unit_test.py.jinja2")
        return template.render(**context)

    def _generate_integration_tests(self, context: dict) -> str:
        """Generate integration tests.

        Args:
            context: Template context

        Returns:
            Generated integration test code

        """
        # Build step completion code based on wizard pattern
        step_completion_code = self._build_step_completion_code(context)

        # For now, return a simple integration test template
        # In full implementation, would use integration_test.py.jinja2
        return f'''"""Integration tests for {context["wizard_id"]} wizard.

Auto-generated by Empathy Framework Test Generator
Tests end-to-end wizard workflows.
"""

import pytest
from {context["wizard_module"]} import {context["wizard_class"]}


class TestIntegration{context["wizard_class"]}:
    """Integration tests for {context["wizard_id"]} wizard."""

    @pytest.fixture
    async def wizard(self):
        """Create wizard instance."""
        return {context["wizard_class"]}()

    @pytest.mark.asyncio
    async def test_complete_wizard_workflow(self, wizard):
        """Test complete wizard workflow end-to-end."""
        # Start wizard
        session = await wizard.start()
        wizard_id = session["wizard_id"]

        # Complete all steps with valid data
{step_completion_code}

        # Verify final state
        assert session.get("completed", False) is True
'''

    def _build_step_completion_code(self, context: dict) -> str:
        """Build step completion code based on wizard pattern.

        Args:
            context: Template context containing pattern info

        Returns:
            Generated step completion code as indented string

        """
        indent = "        "  # 8 spaces for method body indentation

        if context.get("has_linear_flow") and context.get("total_steps"):
            # Linear flow wizard - iterate through numbered steps
            total_steps = context["total_steps"]
            lines = [
                f"{indent}# Linear flow wizard with {total_steps} steps",
                f"{indent}for step_num in range(1, {total_steps + 1}):",
                f"{indent}    step_data = {{\"step\": step_num, \"data\": f\"test_value_{{step_num}}\"}}",
                f"{indent}    session = await wizard.submit_step(wizard_id, step_num, step_data)",
                f"{indent}    assert session.get(\"current_step\") == step_num + 1 or session.get(\"completed\")",
            ]
            return "\n".join(lines)

        elif context.get("has_phased") and context.get("phases"):
            # Phased processing wizard - iterate through named phases
            phases = context["phases"]
            lines = [f"{indent}# Phased processing wizard"]
            for phase in phases:
                phase_name = phase if isinstance(phase, str) else phase.get("name", "unknown")
                lines.append(f"{indent}# Phase: {phase_name}")
                lines.append(f'{indent}session = await wizard.complete_phase(wizard_id, "{phase_name}", {{}})')
                lines.append(f'{indent}assert "{phase_name}" in session.get("completed_phases", [])')
            return "\n".join(lines)

        else:
            # Generic wizard - single completion call
            lines = [
                f"{indent}# Complete wizard with test data",
                f'{indent}completion_data = {{"action": "complete", "data": {{}}}}',
                f"{indent}session = await wizard.complete(wizard_id, completion_data)",
            ]
            return "\n".join(lines)

    def _generate_fixtures(self, context: dict) -> str:
        """Generate test fixtures.

        Args:
            context: Template context

        Returns:
            Generated fixture code

        """
        return f'''"""Test fixtures for {context["wizard_id"]} wizard.

Auto-generated by Empathy Framework Test Generator
Provides common test data and mocks.
"""

import pytest
from unittest.mock import MagicMock


@pytest.fixture
def sample_{context["wizard_id"]}_data():
    """Sample data for {context["wizard_id"]} wizard."""
    return {{
        "field1": "test value 1",
        "field2": "test value 2",
    }}


@pytest.fixture
def mock_{context["wizard_id"]}_dependencies():
    """Mock dependencies for {context["wizard_id"]} wizard."""
    return {{
        "database": MagicMock(),
        "api_client": MagicMock(),
    }}
'''

    def _needs_integration_tests(self, pattern_ids: list[str]) -> bool:
        """Determine if integration tests are needed.

        Args:
            pattern_ids: Pattern IDs

        Returns:
            True if integration tests recommended

        """
        # Integration tests for multi-step or phased wizards
        return "linear_flow" in pattern_ids or "phased_processing" in pattern_ids

    def _infer_module(self, wizard_id: str) -> str:
        """Infer module path from wizard ID.

        Args:
            wizard_id: Wizard identifier

        Returns:
            Inferred module path

        """
        # Try to determine wizard location
        # This is a simple heuristic - can be improved
        if wizard_id in ["soap_note", "sbar", "care_plan"]:
            return f"wizards.{wizard_id}"
        elif wizard_id in ["debugging", "testing", "security"]:
            return f"coach_wizards.{wizard_id}_wizard"
        else:
            return f"wizards.{wizard_id}_wizard"

    def _infer_class_name(self, wizard_id: str) -> str:
        """Infer wizard class name from ID.

        Args:
            wizard_id: Wizard identifier

        Returns:
            Inferred class name

        """
        # Convert snake_case to PascalCase and add "Wizard"
        parts = wizard_id.split("_")
        class_name = "".join(part.capitalize() for part in parts)
        return f"{class_name}Wizard"
