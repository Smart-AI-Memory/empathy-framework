"""Manage documentation

Stages:
1. process - Process

Copyright 2025 Smart-AI-Memory
Licensed under Fair Source License 0.9
"""

import logging
from typing import Any

from empathy_os.workflows.base import BaseWorkflow, ModelTier

logger = logging.getLogger(__name__)


class ManageDocsWorkflow(BaseWorkflow):
    """Manage documentation


    Usage:
        workflow = ManageDocsWorkflow()
        result = await workflow.execute(
            # Add parameters here
        )
    """

    name = "manage-docs"
    description = "Manage documentation"
    stages = ["process"]
    tier_map = {
        "process": ModelTier.CAPABLE,
    }

    def __init__(
        self,
        **kwargs: Any,
    ):
        """Initialize manage-docs workflow.

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
        """Execute the single processing stage."""
        if stage_name == "process":
            return await self._process(input_data, tier)
        raise ValueError(f"Unknown stage: {stage_name}")

    async def _process(
        self,
        input_data: Any,
        tier: ModelTier,
    ) -> tuple[Any, int, int]:
        """Process documentation - analyze, identify gaps, and generate improvements.

        Args:
            input_data: Documentation content, file list, or project structure
            tier: Model tier to use (CAPABLE for thorough analysis)

        Returns:
            Tuple of (documentation_report, input_tokens, output_tokens)

        """
        prompt = f"""You are a technical documentation specialist.
Analyze the following documentation or project structure and provide a comprehensive assessment:

Input:
{input_data}

Perform the following analysis:

## 1. Documentation Structure Analysis
- Evaluate the organization and hierarchy of docs
- Check for logical grouping of topics
- Assess navigation and discoverability
- Identify structural inconsistencies

## 2. Coverage Assessment
Identify missing documentation for:
- **API Documentation**: Undocumented functions, classes, or modules
- **User Guides**: Missing how-to guides or tutorials
- **Architecture Docs**: Missing system design or architecture docs
- **Setup/Installation**: Incomplete onboarding documentation
- **Changelog/Release Notes**: Missing version history
- **Contributing Guidelines**: Missing contributor docs

## 3. Quality Assessment
For existing documentation, evaluate:
- **Accuracy**: Is the information current and correct?
- **Completeness**: Are there gaps in explanations?
- **Clarity**: Is the language clear and accessible?
- **Examples**: Are there sufficient code examples?
- **Formatting**: Is markdown/formatting consistent?

## 4. Outdated Content Detection
Flag documentation that may be outdated:
- References to deprecated features
- Old version numbers or dates
- Broken links or missing references
- Inconsistencies with current code

## 5. Improvement Recommendations
Provide prioritized suggestions:
- **Critical**: Must-fix issues (broken docs, incorrect info)
- **High**: Important additions (missing core docs)
- **Medium**: Quality improvements (better examples, clarity)
- **Low**: Nice-to-have enhancements

## 6. Action Items
Generate specific, actionable tasks:
- Document to create (with suggested outline)
- Document to update (with specific changes)
- Document to archive or remove

Format the response as structured JSON with keys:
structure_analysis, coverage_gaps, quality_issues, outdated_content, recommendations, action_items"""

        # Use LLM executor if available
        if self._executor:
            result = await self._executor.run(
                task_type="workflow_stage",
                prompt=prompt,
                tier=tier.to_unified() if hasattr(tier, "to_unified") else tier,
            )
            return result.content, result.input_tokens, result.output_tokens

        # Fallback to basic processing
        return {
            "status": "no_executor",
            "message": "Documentation analysis requires LLM executor",
            "input": input_data,
        }, 0, 0
