"""A team leader that has 10 years of experiance coding.

Stages:
1. analyze - Analyze
2. process - Process
3. report - Report

Copyright 2025 Smart-AI-Memory
Licensed under Fair Source License 0.9
"""

import logging
from typing import Any

from empathy_os.workflows.base import BaseWorkflow, ModelTier

logger = logging.getLogger(__name__)


class NewSampleWorkflow1Workflow(BaseWorkflow):
    """A team leader that has 10 years of experiance coding.


    Usage:
        workflow = NewSampleWorkflow1Workflow()
        result = await workflow.execute(
            # Add parameters here
        )
    """

    name = "new-sample-workflow1"
    description = "A team leader that has 10 years of experiance coding."
    stages = ["analyze", "process", "report"]
    tier_map = {
        "analyze": ModelTier.CHEAP,
        "process": ModelTier.CAPABLE,
        "report": ModelTier.PREMIUM,
    }

    def __init__(
        self,
        **kwargs: Any,
    ):
        """Initialize new-sample-workflow1 workflow.

        Args:
            **kwargs: Additional arguments passed to BaseWorkflow

        """
        super().__init__(**kwargs)

    async def run_stage(
        self,
        stage_name: str,
        tier: ModelTier,
        input_data: Any,
    ) -> tuple[Any, int, int]:
        """Route to specific stage implementation."""
        if stage_name == "analyze":
            return await self._analyze(input_data, tier)
        if stage_name == "process":
            return await self._process(input_data, tier)
        if stage_name == "report":
            return await self._report(input_data, tier)
        raise ValueError(f"Unknown stage: {stage_name}")

    async def _analyze(
        self,
        input_data: Any,
        tier: ModelTier,
    ) -> tuple[Any, int, int]:
        """Analyze stage - identify code issues, patterns, and best practices.

        Args:
            input_data: Code or project information to analyze
            tier: Model tier to use (CHEAP for initial analysis)

        Returns:
            Tuple of (analysis_result, input_tokens, output_tokens)

        """
        prompt = f"""You are a senior team leader with 10 years of coding experience.
Analyze the following code or project information for:

1. **Code Quality Issues**: Identify bugs, anti-patterns, and code smells
2. **Best Practice Violations**: Check against industry standards (SOLID, DRY, KISS)
3. **Security Concerns**: Flag potential vulnerabilities or unsafe patterns
4. **Performance Issues**: Identify inefficient algorithms or resource usage
5. **Maintainability**: Assess readability, documentation, and test coverage

Input to analyze:
{input_data}

Provide a structured analysis with:
- Issue severity (HIGH/MEDIUM/LOW)
- Location in code (if applicable)
- Brief description of each finding
- Initial recommendation hints

Format as JSON with keys: issues, patterns_found, security_flags, performance_notes"""

        if self._executor:
            result = await self._executor.run(
                task_type="workflow_stage",
                prompt=prompt,
                tier=tier.to_unified() if hasattr(tier, "to_unified") else tier,
            )
            return result.content, result.input_tokens, result.output_tokens

        return {"stage": "analyze", "input": input_data, "status": "no_executor"}, 0, 0

    async def _process(
        self,
        input_data: Any,
        tier: ModelTier,
    ) -> tuple[Any, int, int]:
        """Process stage - generate refactoring recommendations and improvements.

        Args:
            input_data: Analysis results from the analyze stage
            tier: Model tier to use (CAPABLE for detailed recommendations)

        Returns:
            Tuple of (recommendations, input_tokens, output_tokens)

        """
        prompt = f"""You are a senior team leader with 10 years of coding experience.
Based on the following analysis, generate detailed refactoring recommendations:

Analysis Results:
{input_data}

For each issue identified, provide:

1. **Refactoring Plan**:
   - Specific code changes needed
   - Step-by-step implementation approach
   - Estimated effort (hours/days)

2. **Code Examples**:
   - Before/after snippets where applicable
   - Alternative approaches if multiple solutions exist

3. **Priority Matrix**:
   - Quick wins (low effort, high impact)
   - Strategic improvements (high effort, high impact)
   - Technical debt items (address later)

4. **Risk Assessment**:
   - Breaking changes to watch for
   - Testing requirements for each change
   - Rollback considerations

5. **Dependencies**:
   - Which changes should be done first
   - Changes that can be parallelized

Format as JSON with keys: refactoring_plans, code_examples, priority_matrix, risks, dependencies"""

        if self._executor:
            result = await self._executor.run(
                task_type="workflow_stage",
                prompt=prompt,
                tier=tier.to_unified() if hasattr(tier, "to_unified") else tier,
            )
            return result.content, result.input_tokens, result.output_tokens

        return {"stage": "process", "input": input_data, "status": "no_executor"}, 0, 0

    async def _report(
        self,
        input_data: Any,
        tier: ModelTier,
    ) -> tuple[Any, int, int]:
        """Report stage - create comprehensive summary for stakeholders.

        Args:
            input_data: Recommendations from the process stage
            tier: Model tier to use (PREMIUM for high-quality report)

        Returns:
            Tuple of (report, input_tokens, output_tokens)

        """
        prompt = f"""You are a senior team leader with 10 years of coding experience.
Create a comprehensive code review report for stakeholders based on the analysis and recommendations:

Recommendations Data:
{input_data}

Generate a professional report with:

## Executive Summary
- Overall code health score (1-10)
- Critical issues count and brief description
- Recommended immediate actions (top 3)

## Detailed Findings

### Critical Issues (Must Fix)
- Issue description, impact, and recommended fix
- Business risk if not addressed

### Important Improvements (Should Fix)
- Improvements that enhance quality/performance
- Estimated ROI for each

### Nice-to-Have Enhancements
- Lower priority items for future sprints

## Implementation Roadmap
- Sprint 1: Critical fixes (estimated hours)
- Sprint 2: Important improvements
- Backlog: Nice-to-have items

## Metrics & KPIs
- Current state metrics
- Target metrics after improvements
- How to measure success

## Team Recommendations
- Skills or training needed
- Process improvements suggested
- Tools that could help

Format the report in clean markdown with clear sections and actionable items."""

        if self._executor:
            result = await self._executor.run(
                task_type="workflow_stage",
                prompt=prompt,
                tier=tier.to_unified() if hasattr(tier, "to_unified") else tier,
            )
            return result.content, result.input_tokens, result.output_tokens

        return {"stage": "report", "input": input_data, "status": "no_executor"}, 0, 0
