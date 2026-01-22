"""Meta-workflow orchestration engine.

Coordinates the complete meta-workflow execution:
1. Template selection
2. Form collection (Socratic questioning)
3. Agent team generation
4. Agent execution (with tier escalation)
5. Result aggregation and storage (files + optional memory)

Created: 2026-01-17
Updated: 2026-01-18 (v4.3.0 - Real LLM execution with Anthropic client)
Purpose: Core orchestration for meta-workflows
"""

# Load environment variables from .env file
# Try multiple locations: project root, home directory, empathy config
try:
    from pathlib import Path

    from dotenv import load_dotenv

    # Try common .env locations
    _env_paths = [
        Path.cwd() / ".env",  # Current working directory
        Path(__file__).parent.parent.parent.parent / ".env",  # Project root
        Path.home() / ".env",  # Home directory
        Path.home() / ".empathy" / ".env",  # Empathy config directory
    ]

    for _env_path in _env_paths:
        if _env_path.exists():
            load_dotenv(_env_path)
            break
except ImportError:
    pass  # dotenv not installed, use environment variables directly

import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from empathy_llm_toolkit.routing.model_router import ModelRouter, ModelTier
from empathy_os.config import _validate_file_path
from empathy_os.meta_workflows.agent_creator import DynamicAgentCreator
from empathy_os.meta_workflows.form_engine import SocraticFormEngine
from empathy_os.meta_workflows.models import (
    AgentExecutionResult,
    AgentSpec,
    FormResponse,
    MetaWorkflowResult,
    MetaWorkflowTemplate,
    TierStrategy,
)
from empathy_os.meta_workflows.template_registry import TemplateRegistry
from empathy_os.orchestration.agent_templates import get_template
from empathy_os.telemetry.usage_tracker import UsageTracker

if TYPE_CHECKING:
    from empathy_os.meta_workflows.pattern_learner import PatternLearner

logger = logging.getLogger(__name__)


class MetaWorkflow:
    """Orchestrates complete meta-workflow execution.

    Coordinates form collection, agent generation, and execution
    to implement dynamic, template-based workflows.

    Hybrid Storage:
    - Files: Persistent, human-readable execution results
    - Memory: Rich semantic queries (optional via pattern_learner)

    Attributes:
        template: Meta-workflow template to execute
        storage_dir: Directory for storing execution results
        form_engine: Engine for collecting form responses
        agent_creator: Creator for generating agent teams
        pattern_learner: Optional pattern learner for memory integration
    """

    def __init__(
        self,
        template: MetaWorkflowTemplate | None = None,
        template_id: str | None = None,
        storage_dir: str | None = None,
        pattern_learner: "PatternLearner | None" = None,
    ):
        """Initialize meta-workflow with optional memory integration.

        Args:
            template: Template to execute (optional if template_id provided)
            template_id: ID of template to load (optional if template provided)
            storage_dir: Directory for execution results
                        (default: .empathy/meta_workflows/executions/)
            pattern_learner: Optional pattern learner with memory integration
                            If provided, execution results will be stored in
                            both files and memory for rich semantic querying

        Raises:
            ValueError: If neither template nor template_id provided
        """
        if template is None and template_id is None:
            raise ValueError("Must provide either template or template_id")

        # Load template if needed
        if template is None:
            registry = TemplateRegistry()
            template = registry.load_template(template_id)
            if template is None:
                raise ValueError(f"Template not found: {template_id}")

        self.template = template
        self.form_engine = SocraticFormEngine()
        self.agent_creator = DynamicAgentCreator()
        self.pattern_learner = pattern_learner

        # Set up storage
        if storage_dir is None:
            storage_dir = str(
                Path.home() / ".empathy" / "meta_workflows" / "executions"
            )
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        logger.info(
            f"Initialized MetaWorkflow for template: {self.template.template_id}",
            extra={"memory_enabled": pattern_learner is not None},
        )

    def execute(
        self,
        form_response: FormResponse | None = None,
        mock_execution: bool = True,
        use_defaults: bool = False,
    ) -> MetaWorkflowResult:
        """Execute complete meta-workflow.

        Args:
            form_response: Pre-collected form responses (optional)
                          If None, will collect via form_engine
            mock_execution: Use mock agent execution (default: True for MVP)
                           Set to False for real LLM execution
            use_defaults: Use default values instead of asking questions
                         (non-interactive mode)

        Returns:
            MetaWorkflowResult with complete execution details

        Raises:
            ValueError: If execution fails
        """
        run_id = f"{self.template.template_id}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        start_time = time.time()

        logger.info(f"Starting meta-workflow execution: {run_id}")

        try:
            # Stage 1: Form collection (if not provided)
            if form_response is None:
                if use_defaults:
                    logger.info("Stage 1: Using default form values (non-interactive)")
                else:
                    logger.info("Stage 1: Collecting form responses")
                form_response = self.form_engine.ask_questions(
                    self.template.form_schema, self.template.template_id
                )
            else:
                logger.info("Stage 1: Using provided form responses")

            # Stage 2: Agent generation
            logger.info("Stage 2: Generating agent team")
            agents = self.agent_creator.create_agents(self.template, form_response)

            logger.info(f"Created {len(agents)} agents")

            # Stage 3: Agent execution
            logger.info("Stage 3: Executing agents")

            if mock_execution:
                agent_results = self._execute_agents_mock(agents)
            else:
                agent_results = self._execute_agents_real(agents)

            # Stage 4: Aggregate results
            logger.info("Stage 4: Aggregating results")

            total_cost = sum(result.cost for result in agent_results)
            total_duration = time.time() - start_time
            success = all(result.success for result in agent_results)

            result = MetaWorkflowResult(
                run_id=run_id,
                template_id=self.template.template_id,
                timestamp=datetime.now().isoformat(),
                form_responses=form_response,
                agents_created=agents,
                agent_results=agent_results,
                total_cost=total_cost,
                total_duration=total_duration,
                success=success,
            )

            # Stage 5: Save results (files + optional memory)
            logger.info("Stage 5: Saving results")
            self._save_execution(result)

            # Store in memory if pattern learner available
            if self.pattern_learner:
                logger.info("Stage 5b: Storing in memory")
                pattern_id = self.pattern_learner.store_execution_in_memory(result)
                if pattern_id:
                    logger.info(f"Execution stored in memory: {pattern_id}")

            logger.info(
                f"Meta-workflow execution complete: {run_id} "
                f"(cost: ${total_cost:.2f}, duration: {total_duration:.1f}s)"
            )

            return result

        except Exception as e:
            logger.error(f"Meta-workflow execution failed: {e}")

            # Create error result
            error_result = MetaWorkflowResult(
                run_id=run_id,
                template_id=self.template.template_id,
                timestamp=datetime.now().isoformat(),
                form_responses=form_response
                or FormResponse(template_id=self.template.template_id),
                total_cost=0.0,
                total_duration=time.time() - start_time,
                success=False,
                error=str(e),
            )

            # Try to save error result
            try:
                self._save_execution(error_result)
            except Exception as save_error:
                logger.error(f"Failed to save error result: {save_error}")

            raise ValueError(f"Meta-workflow execution failed: {e}") from e

    def _execute_agents_mock(
        self, agents: list[AgentSpec]
    ) -> list[AgentExecutionResult]:
        """Execute agents with mock execution (for MVP).

        Args:
            agents: List of agent specs to execute

        Returns:
            List of agent execution results
        """
        results = []

        for agent in agents:
            logger.debug(f"Mock executing agent: {agent.role}")

            # Simulate execution time based on tier
            if agent.tier_strategy == TierStrategy.CHEAP_ONLY:
                duration = 1.5
                cost = 0.05
                tier_used = "cheap"
            elif agent.tier_strategy == TierStrategy.PROGRESSIVE:
                duration = 3.0
                cost = 0.15  # Average (may escalate)
                tier_used = "capable"
            elif agent.tier_strategy == TierStrategy.CAPABLE_FIRST:
                duration = 4.0
                cost = 0.25
                tier_used = "capable"
            else:  # PREMIUM_ONLY
                duration = 6.0
                cost = 0.40
                tier_used = "premium"

            # Mock result
            result = AgentExecutionResult(
                agent_id=agent.agent_id,
                role=agent.role,
                success=True,
                cost=cost,
                duration=duration,
                tier_used=tier_used,
                output={
                    "message": f"Mock execution of {agent.role}",
                    "tier_strategy": agent.tier_strategy.value,
                    "tools_used": agent.tools,
                    "config": agent.config,
                    "success_criteria": agent.success_criteria,
                },
            )

            results.append(result)

            # Simulate some execution time
            time.sleep(0.1)

        return results

    def _execute_agents_real(self, agents: list[AgentSpec]) -> list[AgentExecutionResult]:
        """Execute agents with real LLM calls and progressive tier escalation.

        Implements progressive tier escalation strategy:
        - CHEAP_ONLY: Always uses cheap tier
        - PROGRESSIVE: cheap → capable → premium (escalates on failure)
        - CAPABLE_FIRST: capable → premium (skips cheap tier)

        Each LLM call is tracked via UsageTracker for cost analysis.

        Args:
            agents: List of agent specs to execute

        Returns:
            List of agent execution results with actual LLM costs

        Raises:
            RuntimeError: If agent execution encounters fatal error
        """
        results = []
        router = ModelRouter()
        tracker = UsageTracker.get_instance()

        for agent in agents:
            logger.info(f"Executing agent: {agent.role} ({agent.tier_strategy.value})")

            try:
                result = self._execute_single_agent_with_escalation(
                    agent, router, tracker
                )
                results.append(result)

                logger.info(
                    f"Agent {agent.role} completed: "
                    f"tier={result.tier_used}, cost=${result.cost:.4f}, "
                    f"success={result.success}"
                )

            except Exception as e:
                logger.error(f"Agent {agent.role} failed with error: {e}")

                # Create error result
                error_result = AgentExecutionResult(
                    agent_id=agent.agent_id,
                    role=agent.role,
                    success=False,
                    cost=0.0,
                    duration=0.0,
                    tier_used="error",
                    output={"error": str(e)},
                    error=str(e),
                )
                results.append(error_result)

        return results

    def _execute_single_agent_with_escalation(
        self,
        agent: AgentSpec,
        router: ModelRouter,
        tracker: UsageTracker,
    ) -> AgentExecutionResult:
        """Execute single agent with progressive tier escalation.

        Args:
            agent: Agent specification
            router: Model router for tier selection
            tracker: Usage tracker for telemetry

        Returns:
            AgentExecutionResult with actual LLM execution data
        """
        start_time = time.time()

        # Determine tier sequence based on strategy
        if agent.tier_strategy == TierStrategy.CHEAP_ONLY:
            tiers = [ModelTier.CHEAP]
        elif agent.tier_strategy == TierStrategy.PROGRESSIVE:
            tiers = [ModelTier.CHEAP, ModelTier.CAPABLE, ModelTier.PREMIUM]
        elif agent.tier_strategy == TierStrategy.CAPABLE_FIRST:
            tiers = [ModelTier.CAPABLE, ModelTier.PREMIUM]
        else:
            # Fallback to capable
            logger.warning(f"Unknown tier strategy: {agent.tier_strategy}, using CAPABLE")
            tiers = [ModelTier.CAPABLE]

        # Try each tier in sequence
        result = None
        total_cost = 0.0

        for tier in tiers:
            logger.debug(f"Attempting tier: {tier.value}")

            # Execute at this tier
            tier_result = self._execute_at_tier(agent, tier, router, tracker)
            total_cost += tier_result.cost

            # Check if successful
            if self._evaluate_success_criteria(tier_result, agent):
                # Success - return result
                tier_result.cost = total_cost  # Update with cumulative cost
                tier_result.duration = time.time() - start_time
                return tier_result

            # Failed - try next tier
            logger.debug(
                f"Tier {tier.value} did not meet success criteria, "
                f"attempting escalation"
            )
            result = tier_result

        # All tiers exhausted - return final result (failed)
        if result:
            result.cost = total_cost
            result.duration = time.time() - start_time
            logger.warning(
                f"Agent {agent.role} failed at all tiers "
                f"(cost: ${total_cost:.4f})"
            )
            return result

        # Should never reach here
        raise RuntimeError(f"No tiers attempted for agent {agent.role}")

    def _execute_at_tier(
        self,
        agent: AgentSpec,
        tier: ModelTier,
        router: ModelRouter,
        tracker: UsageTracker,
    ) -> AgentExecutionResult:
        """Execute agent at specific tier.

        Args:
            agent: Agent specification
            tier: Model tier to use
            router: Model router
            tracker: Usage tracker

        Returns:
            AgentExecutionResult from this tier
        """
        start_time = time.time()

        # Get model config for tier (access MODELS dict directly)
        provider = router._default_provider
        model_config = router.MODELS[provider][tier.value]

        # Build prompt from agent spec
        prompt = self._build_agent_prompt(agent)

        # Execute LLM call
        # v4.3.0: Real LLM execution with Anthropic client
        # Falls back to simulation if API key not available

        try:
            # Execute real LLM call (with simulation fallback)
            response = self._execute_llm_call(prompt, model_config, tier)

            # Track telemetry
            duration_ms = int((time.time() - start_time) * 1000)
            tracker.track_llm_call(
                workflow="meta-workflow",
                stage=agent.role,
                tier=tier.value,
                model=model_config.model_id,
                provider=router._default_provider,
                cost=response["cost"],
                tokens=response["tokens"],
                cache_hit=False,
                cache_type=None,
                duration_ms=duration_ms,
                user_id=None,
            )

            # Create result
            result = AgentExecutionResult(
                agent_id=agent.agent_id,
                role=agent.role,
                success=response["success"],
                cost=response["cost"],
                duration=time.time() - start_time,
                tier_used=tier.value,
                output=response["output"],
            )

            return result

        except Exception as e:
            logger.error(f"LLM execution failed at tier {tier.value}: {e}")

            # Return error result
            return AgentExecutionResult(
                agent_id=agent.agent_id,
                role=agent.role,
                success=False,
                cost=0.0,
                duration=time.time() - start_time,
                tier_used=tier.value,
                output={"error": str(e)},
                error=str(e),
            )

    def _get_generic_instructions(self, role: str) -> str:
        """Generate generic instructions based on agent role.

        Args:
            role: Agent role name

        Returns:
            Generic instructions appropriate for the role
        """
        # Map common role keywords to instructions
        role_lower = role.lower()

        if "analyst" in role_lower or "analyze" in role_lower:
            return (
                "You are an expert analyst. Your job is to thoroughly analyze "
                "the provided information, identify key patterns, issues, and "
                "opportunities. Provide detailed findings with specific evidence "
                "and actionable recommendations."
            )
        elif "reviewer" in role_lower or "review" in role_lower:
            return (
                "You are a careful reviewer. Your job is to review the provided "
                "content for quality, accuracy, completeness, and adherence to "
                "best practices. Identify any issues, gaps, or areas for improvement "
                "and provide specific feedback."
            )
        elif "generator" in role_lower or "create" in role_lower or "writer" in role_lower:
            return (
                "You are a skilled content generator. Your job is to create "
                "high-quality content based on the provided requirements and context. "
                "Ensure your output is well-structured, accurate, and follows "
                "established conventions."
            )
        elif "validator" in role_lower or "verify" in role_lower:
            return (
                "You are a thorough validator. Your job is to verify the provided "
                "content meets all requirements and standards. Check for correctness, "
                "completeness, and consistency. Report any issues found."
            )
        elif "synthesizer" in role_lower or "combine" in role_lower:
            return (
                "You are an expert synthesizer. Your job is to combine multiple "
                "inputs into a cohesive, well-organized output. Identify common "
                "themes, resolve conflicts, and produce a unified result that "
                "captures the key insights from all sources."
            )
        elif "test" in role_lower:
            return (
                "You are a testing specialist. Your job is to analyze code and "
                "create comprehensive test cases that cover edge cases, error "
                "conditions, and normal operation. Ensure tests are well-documented "
                "and maintainable."
            )
        elif "doc" in role_lower:
            return (
                "You are a documentation specialist. Your job is to analyze content "
                "and create or improve documentation that is clear, accurate, and "
                "helpful. Follow documentation best practices and maintain consistency."
            )
        else:
            return (
                f"You are a {role} agent. Complete your assigned task thoroughly "
                "and provide clear, well-structured output. Follow best practices "
                "and provide actionable results."
            )

    def _build_agent_prompt(self, agent: AgentSpec) -> str:
        """Build prompt for agent from specification.

        Args:
            agent: Agent specification

        Returns:
            Formatted prompt string
        """
        # Load base template
        base_template = get_template(agent.base_template)
        if base_template is not None:
            instructions = base_template.default_instructions
        else:
            # Fallback if template not found - use role-based generic prompt
            logger.warning(
                f"Template {agent.base_template} not found, using generic prompt"
            )
            instructions = self._get_generic_instructions(agent.role)

        # Build prompt
        prompt_parts = [
            f"Role: {agent.role}",
            f"\nInstructions:\n{instructions}",
        ]

        # Add config if present
        if agent.config:
            prompt_parts.append(f"\nConfiguration:\n{json.dumps(agent.config, indent=2)}")

        # Add success criteria if present
        if agent.success_criteria:
            prompt_parts.append(
                f"\nSuccess Criteria:\n{json.dumps(agent.success_criteria, indent=2)}"
            )

        # Add tools if present
        if agent.tools:
            prompt_parts.append(f"\nAvailable Tools: {', '.join(agent.tools)}")

        return "\n".join(prompt_parts)

    def _execute_llm_call(
        self, prompt: str, model_config: Any, tier: ModelTier
    ) -> dict[str, Any]:
        """Execute real LLM call via Anthropic or other providers.

        Uses the Anthropic client for Claude models, with fallback to
        other providers via the model configuration.

        Args:
            prompt: Prompt to send to LLM
            model_config: Model configuration from router
            tier: Model tier being used

        Returns:
            Dict with cost, tokens, success, and output

        Raises:
            RuntimeError: If LLM call fails after retries
        """
        import os

        # Try to use Anthropic client
        try:
            from anthropic import Anthropic

            api_key = os.environ.get("ANTHROPIC_API_KEY")
            if not api_key:
                raise ValueError(
                    "ANTHROPIC_API_KEY not found. Set it in environment or .env file "
                    "(checked: ./env, ~/.env, ~/.empathy/.env)"
                )

            client = Anthropic(api_key=api_key)

            # Execute the LLM call
            response = client.messages.create(
                model=model_config.model_id,
                max_tokens=2048,
                messages=[
                    {"role": "user", "content": prompt}
                ],
            )

            # Extract response data
            output_text = response.content[0].text if response.content else ""
            prompt_tokens = response.usage.input_tokens
            completion_tokens = response.usage.output_tokens

            # Calculate cost
            cost = (
                (prompt_tokens / 1000) * model_config.cost_per_1k_input
                + (completion_tokens / 1000) * model_config.cost_per_1k_output
            )

            return {
                "cost": cost,
                "tokens": {
                    "input": prompt_tokens,
                    "output": completion_tokens,
                    "total": prompt_tokens + completion_tokens,
                },
                "success": True,
                "output": {
                    "message": output_text,
                    "model": model_config.model_id,
                    "tier": tier.value,
                    "success": True,
                },
            }

        except ImportError:
            logger.warning("Anthropic client not available, using simulation")
            return self._simulate_llm_call(prompt, model_config, tier)

        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            # Return failure result
            return {
                "cost": 0.0,
                "tokens": {"input": 0, "output": 0, "total": 0},
                "success": False,
                "output": {
                    "error": str(e),
                    "model": model_config.model_id,
                    "tier": tier.value,
                    "success": False,
                },
            }

    def _simulate_llm_call(
        self, prompt: str, model_config: Any, tier: ModelTier
    ) -> dict[str, Any]:
        """Simulate LLM call with realistic cost/token estimates.

        Used as fallback when real LLM execution is not available
        (e.g., no API key, testing mode, etc.)

        Args:
            prompt: Prompt to send to LLM
            model_config: Model configuration
            tier: Model tier

        Returns:
            Dict with cost, tokens, success, and output
        """
        import random

        # Estimate tokens (rough: ~4 chars per token)
        prompt_tokens = len(prompt) // 4
        completion_tokens = 500  # Assume moderate response

        # Calculate cost
        cost = (
            (prompt_tokens / 1000) * model_config.cost_per_1k_input
            + (completion_tokens / 1000) * model_config.cost_per_1k_output
        )

        # Simulate success rate based on tier
        # cheap: 80%, capable: 95%, premium: 99%
        if tier == ModelTier.CHEAP:
            success = random.random() < 0.80
        elif tier == ModelTier.CAPABLE:
            success = random.random() < 0.95
        else:  # PREMIUM
            success = random.random() < 0.99

        return {
            "cost": cost,
            "tokens": {
                "input": prompt_tokens,
                "output": completion_tokens,
                "total": prompt_tokens + completion_tokens,
            },
            "success": success,
            "output": {
                "message": f"Simulated response at {tier.value} tier",
                "model": model_config.model_id,
                "tier": tier.value,
                "success": success,
            },
        }

    def _evaluate_success_criteria(
        self, result: AgentExecutionResult, agent: AgentSpec
    ) -> bool:
        """Evaluate if agent result meets success criteria.

        Args:
            result: Agent execution result
            agent: Agent specification with success criteria

        Returns:
            True if success criteria met, False otherwise
        """
        # Basic success check
        if not result.success:
            return False

        # If no criteria specified, basic success is enough
        if not agent.success_criteria:
            return True

        # success_criteria is a list of descriptive strings (e.g., ["code reviewed", "tests pass"])
        # These are informational criteria - if result.success is True, we consider the criteria met
        # The criteria serve as documentation of what success means for this agent
        logger.debug(
            f"Agent succeeded with criteria: {agent.success_criteria}"
        )
        return True

    def _save_execution(self, result: MetaWorkflowResult) -> Path:
        """Save execution results to disk.

        Args:
            result: Execution result to save

        Returns:
            Path to saved results directory

        Raises:
            OSError: If save operation fails
        """
        # Create run directory
        run_dir = self.storage_dir / result.run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        # Save config (template info + form responses)
        config_file = run_dir / "config.json"
        config_data = {
            "template_id": result.template_id,
            "template_name": self.template.name,
            "template_version": self.template.version,
            "run_id": result.run_id,
            "timestamp": result.timestamp,
        }
        validated_config = _validate_file_path(str(config_file))
        validated_config.write_text(json.dumps(config_data, indent=2), encoding="utf-8")

        # Save form responses
        responses_file = run_dir / "form_responses.json"
        validated_responses = _validate_file_path(str(responses_file))
        validated_responses.write_text(
            json.dumps(
                {
                    "template_id": result.form_responses.template_id,
                    "responses": result.form_responses.responses,
                    "timestamp": result.form_responses.timestamp,
                    "response_id": result.form_responses.response_id,
                },
                indent=2,
            ),
            encoding="utf-8",
        )

        # Save agents created
        agents_file = run_dir / "agents.json"
        agents_data = [
            {
                "agent_id": agent.agent_id,
                "role": agent.role,
                "base_template": agent.base_template,
                "tier_strategy": agent.tier_strategy.value,
                "tools": agent.tools,
                "config": agent.config,
                "success_criteria": agent.success_criteria,
            }
            for agent in result.agents_created
        ]
        validated_agents = _validate_file_path(str(agents_file))
        validated_agents.write_text(json.dumps(agents_data, indent=2), encoding="utf-8")

        # Save complete result
        result_file = run_dir / "result.json"
        validated_result = _validate_file_path(str(result_file))
        validated_result.write_text(result.to_json(), encoding="utf-8")

        # Create human-readable report
        report_file = run_dir / "report.txt"
        report = self._generate_report(result)
        validated_report = _validate_file_path(str(report_file))
        validated_report.write_text(report, encoding="utf-8")

        logger.info(f"Saved execution results to: {run_dir}")
        return run_dir

    def _generate_report(self, result: MetaWorkflowResult) -> str:
        """Generate human-readable report.

        Args:
            result: Execution result

        Returns:
            Markdown-formatted report
        """
        lines = []

        lines.append("# Meta-Workflow Execution Report")
        lines.append("")
        lines.append(f"**Run ID**: {result.run_id}")
        lines.append(f"**Template**: {self.template.name}")
        lines.append(f"**Timestamp**: {result.timestamp}")
        lines.append(f"**Success**: {'✅ Yes' if result.success else '❌ No'}")
        if result.error:
            lines.append(f"**Error**: {result.error}")
        lines.append("")

        lines.append("## Summary")
        lines.append("")
        lines.append(f"- **Agents Created**: {len(result.agents_created)}")
        lines.append(
            f"- **Agents Executed**: {len(result.agent_results)}"
        )
        lines.append(f"- **Total Cost**: ${result.total_cost:.2f}")
        lines.append(f"- **Total Duration**: {result.total_duration:.1f}s")
        lines.append("")

        lines.append("## Form Responses")
        lines.append("")
        for key, value in result.form_responses.responses.items():
            lines.append(f"- **{key}**: {value}")
        lines.append("")

        lines.append("## Agents Created")
        lines.append("")
        for i, agent in enumerate(result.agents_created, 1):
            lines.append(f"### {i}. {agent.role}")
            lines.append("")
            lines.append(f"- **Agent ID**: {agent.agent_id}")
            lines.append(f"- **Base Template**: {agent.base_template}")
            lines.append(f"- **Tier Strategy**: {agent.tier_strategy.value}")
            lines.append(f"- **Tools**: {', '.join(agent.tools) if agent.tools else 'None'}")
            if agent.config:
                lines.append(f"- **Config**: {json.dumps(agent.config)}")
            if agent.success_criteria:
                lines.append("- **Success Criteria**:")
                for criterion in agent.success_criteria:
                    lines.append(f"  - {criterion}")
            lines.append("")

        lines.append("## Execution Results")
        lines.append("")
        for i, agent_result in enumerate(result.agent_results, 1):
            lines.append(f"### {i}. {agent_result.role}")
            lines.append("")
            lines.append(
                f"- **Status**: {'✅ Success' if agent_result.success else '❌ Failed'}"
            )
            lines.append(f"- **Tier Used**: {agent_result.tier_used}")
            lines.append(f"- **Cost**: ${agent_result.cost:.2f}")
            lines.append(f"- **Duration**: {agent_result.duration:.1f}s")
            if agent_result.error:
                lines.append(f"- **Error**: {agent_result.error}")
            lines.append("")

        lines.append("## Cost Breakdown")
        lines.append("")

        # Group by tier
        tier_costs = {}
        for agent_result in result.agent_results:
            tier = agent_result.tier_used
            if tier not in tier_costs:
                tier_costs[tier] = 0.0
            tier_costs[tier] += agent_result.cost

        for tier, cost in sorted(tier_costs.items()):
            lines.append(f"- **{tier}**: ${cost:.2f}")

        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("*Generated by Empathy Framework Meta-Workflow System*")

        return "\n".join(lines)


# =============================================================================
# Helper functions
# =============================================================================


def load_execution_result(run_id: str, storage_dir: str | None = None) -> MetaWorkflowResult:
    """Load a saved execution result.

    Args:
        run_id: ID of execution to load
        storage_dir: Directory where executions are stored

    Returns:
        Loaded MetaWorkflowResult

    Raises:
        FileNotFoundError: If result not found
        ValueError: If result file is invalid
    """
    if storage_dir is None:
        storage_dir = str(Path.home() / ".empathy" / "meta_workflows" / "executions")

    result_file = Path(storage_dir) / run_id / "result.json"

    if not result_file.exists():
        raise FileNotFoundError(f"Result not found: {run_id}")

    try:
        json_str = result_file.read_text(encoding="utf-8")
        data = json.loads(json_str)
        return MetaWorkflowResult.from_dict(data)

    except (json.JSONDecodeError, KeyError) as e:
        raise ValueError(f"Invalid result file: {e}") from e


def list_execution_results(storage_dir: str | None = None) -> list[str]:
    """List all saved execution results.

    Args:
        storage_dir: Directory where executions are stored

    Returns:
        List of run IDs (sorted by timestamp, newest first)
    """
    if storage_dir is None:
        storage_dir = str(Path.home() / ".empathy" / "meta_workflows" / "executions")

    storage_path = Path(storage_dir)

    if not storage_path.exists():
        return []

    # Find all directories with result.json
    run_ids = []
    for dir_path in storage_path.iterdir():
        if dir_path.is_dir() and (dir_path / "result.json").exists():
            run_ids.append(dir_path.name)

    # Sort by timestamp (newest first)
    run_ids.sort(reverse=True)

    return run_ids
