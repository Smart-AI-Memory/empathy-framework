"""Base Workflow Class for Multi-Model Pipelines

Provides a framework for creating cost-optimized workflows that
route tasks to the appropriate model tier.

Integration with empathy_os.models:
- Uses unified ModelTier/ModelProvider from empathy_os.models
- Supports LLMExecutor for abstracted LLM calls
- Supports TelemetryBackend for telemetry storage
- WorkflowStepConfig for declarative step definitions

Copyright 2025 Smart-AI-Memory
Licensed under Fair Source License 0.9
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .tier_tracking import WorkflowTierTracker

# Load .env file for API keys if python-dotenv is available
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed, rely on environment variables

# Import caching infrastructure
from empathy_os.cache import BaseCache, auto_setup_cache, create_cache
from empathy_os.config import _validate_file_path
from empathy_os.cost_tracker import MODEL_PRICING, CostTracker

# Import unified types from empathy_os.models
from empathy_os.models import (
    ExecutionContext,
    LLMCallRecord,
    LLMExecutor,
    TaskRoutingRecord,
    TelemetryBackend,
    WorkflowRunRecord,
    WorkflowStageRecord,
    get_telemetry_store,
)
from empathy_os.models import ModelProvider as UnifiedModelProvider
from empathy_os.models import ModelTier as UnifiedModelTier

# Import progress tracking
from .progress import ProgressCallback, ProgressTracker

# Import telemetry tracking
try:
    from empathy_os.telemetry import UsageTracker

    TELEMETRY_AVAILABLE = True
except ImportError:
    TELEMETRY_AVAILABLE = False
    UsageTracker = None  # type: ignore

if TYPE_CHECKING:
    from .config import WorkflowConfig
    from .step_config import WorkflowStepConfig

logger = logging.getLogger(__name__)

# Default path for workflow run history
WORKFLOW_HISTORY_FILE = ".empathy/workflow_runs.json"


# Local enums for backward compatibility
# New code should use empathy_os.models.ModelTier/ModelProvider
class ModelTier(Enum):
    """Model tier for cost optimization."""

    CHEAP = "cheap"  # Haiku/GPT-4o-mini - $0.25-1.25/M tokens
    CAPABLE = "capable"  # Sonnet/GPT-4o - $3-15/M tokens
    PREMIUM = "premium"  # Opus/o1 - $15-75/M tokens

    def to_unified(self) -> UnifiedModelTier:
        """Convert to unified ModelTier from empathy_os.models."""
        return UnifiedModelTier(self.value)


class ModelProvider(Enum):
    """Supported model providers."""

    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    GOOGLE = "google"  # Google Gemini models
    OLLAMA = "ollama"
    HYBRID = "hybrid"  # Mix of best models from different providers
    CUSTOM = "custom"  # User-defined custom models

    def to_unified(self) -> UnifiedModelProvider:
        """Convert to unified ModelProvider from empathy_os.models."""
        return UnifiedModelProvider(self.value)


# Import unified MODEL_REGISTRY as single source of truth
# This import is placed here intentionally to avoid circular imports
from empathy_os.models import MODEL_REGISTRY  # noqa: E402


def _build_provider_models() -> dict[ModelProvider, dict[ModelTier, str]]:
    """Build PROVIDER_MODELS from MODEL_REGISTRY.

    This ensures PROVIDER_MODELS stays in sync with the single source of truth.
    """
    result: dict[ModelProvider, dict[ModelTier, str]] = {}

    # Map string provider names to ModelProvider enum
    provider_map = {
        "anthropic": ModelProvider.ANTHROPIC,
        "openai": ModelProvider.OPENAI,
        "google": ModelProvider.GOOGLE,
        "ollama": ModelProvider.OLLAMA,
        "hybrid": ModelProvider.HYBRID,
    }

    # Map string tier names to ModelTier enum
    tier_map = {
        "cheap": ModelTier.CHEAP,
        "capable": ModelTier.CAPABLE,
        "premium": ModelTier.PREMIUM,
    }

    for provider_str, tiers in MODEL_REGISTRY.items():
        if provider_str not in provider_map:
            continue  # Skip custom providers
        provider_enum = provider_map[provider_str]
        result[provider_enum] = {}
        for tier_str, model_info in tiers.items():
            if tier_str in tier_map:
                result[provider_enum][tier_map[tier_str]] = model_info.id

    return result


# Model mappings by provider and tier (derived from MODEL_REGISTRY)
PROVIDER_MODELS: dict[ModelProvider, dict[ModelTier, str]] = _build_provider_models()


@dataclass
class WorkflowStage:
    """Represents a single stage in a workflow."""

    name: str
    tier: ModelTier
    description: str
    input_tokens: int = 0
    output_tokens: int = 0
    cost: float = 0.0
    result: Any = None
    duration_ms: int = 0
    skipped: bool = False
    skip_reason: str | None = None


@dataclass
class CostReport:
    """Cost breakdown for a workflow execution."""

    total_cost: float
    baseline_cost: float  # If all stages used premium
    savings: float
    savings_percent: float
    by_stage: dict[str, float] = field(default_factory=dict)
    by_tier: dict[str, float] = field(default_factory=dict)
    # Cache metrics
    cache_hits: int = 0
    cache_misses: int = 0
    cache_hit_rate: float = 0.0
    estimated_cost_without_cache: float = 0.0
    savings_from_cache: float = 0.0


@dataclass
class StageQualityMetrics:
    """Quality metrics for stage output validation."""

    execution_succeeded: bool
    output_valid: bool
    quality_improved: bool  # Workflow-specific (e.g., health score improved)
    error_type: str | None
    validation_error: str | None


@dataclass
class WorkflowResult:
    """Result of a workflow execution."""

    success: bool
    stages: list[WorkflowStage]
    final_output: Any
    cost_report: CostReport
    started_at: datetime
    completed_at: datetime
    total_duration_ms: int
    provider: str = "unknown"
    error: str | None = None
    # Structured error taxonomy for reliability
    error_type: str | None = None  # "config" | "runtime" | "provider" | "timeout" | "validation"
    transient: bool = False  # True if retry is reasonable (e.g., provider timeout)


def _load_workflow_history(history_file: str = WORKFLOW_HISTORY_FILE) -> list[dict]:
    """Load workflow run history from disk."""
    path = Path(history_file)
    if not path.exists():
        return []
    try:
        with open(path) as f:
            data = json.load(f)
            return list(data) if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def _save_workflow_run(
    workflow_name: str,
    provider: str,
    result: WorkflowResult,
    history_file: str = WORKFLOW_HISTORY_FILE,
    max_history: int = 100,
) -> None:
    """Save a workflow run to history."""
    path = Path(history_file)
    path.parent.mkdir(parents=True, exist_ok=True)

    history = _load_workflow_history(history_file)

    # Create run record
    run: dict = {
        "workflow": workflow_name,
        "provider": provider,
        "success": result.success,
        "started_at": result.started_at.isoformat(),
        "completed_at": result.completed_at.isoformat(),
        "duration_ms": result.total_duration_ms,
        "cost": result.cost_report.total_cost,
        "baseline_cost": result.cost_report.baseline_cost,
        "savings": result.cost_report.savings,
        "savings_percent": result.cost_report.savings_percent,
        "stages": [
            {
                "name": s.name,
                "tier": s.tier.value,
                "skipped": s.skipped,
                "cost": s.cost,
                "duration_ms": s.duration_ms,
            }
            for s in result.stages
        ],
        "error": result.error,
    }

    # Extract XML-parsed fields from final_output if present
    if isinstance(result.final_output, dict):
        if result.final_output.get("xml_parsed"):
            run["xml_parsed"] = True
            run["summary"] = result.final_output.get("summary")
            run["findings"] = result.final_output.get("findings", [])
            run["checklist"] = result.final_output.get("checklist", [])

    # Add to history and trim
    history.append(run)
    history = history[-max_history:]

    validated_path = _validate_file_path(str(path))
    with open(validated_path, "w") as f:
        json.dump(history, f, indent=2)


def get_workflow_stats(history_file: str = WORKFLOW_HISTORY_FILE) -> dict:
    """Get workflow statistics for dashboard.

    Returns:
        Dictionary with workflow stats including:
        - total_runs: Total workflow runs
        - by_workflow: Per-workflow stats
        - by_provider: Per-provider stats
        - recent_runs: Last 10 runs
        - total_savings: Total cost savings

    """
    history = _load_workflow_history(history_file)

    if not history:
        return {
            "total_runs": 0,
            "by_workflow": {},
            "by_provider": {},
            "by_tier": {"cheap": 0, "capable": 0, "premium": 0},
            "recent_runs": [],
            "total_cost": 0.0,
            "total_savings": 0.0,
            "avg_savings_percent": 0.0,
        }

    # Aggregate stats
    by_workflow: dict[str, dict] = {}
    by_provider: dict[str, dict] = {}
    by_tier: dict[str, float] = {"cheap": 0.0, "capable": 0.0, "premium": 0.0}
    total_cost = 0.0
    total_savings = 0.0
    successful_runs = 0

    for run in history:
        wf_name = run.get("workflow", "unknown")
        provider = run.get("provider", "unknown")
        cost = run.get("cost", 0.0)
        savings = run.get("savings", 0.0)

        # By workflow
        if wf_name not in by_workflow:
            by_workflow[wf_name] = {"runs": 0, "cost": 0.0, "savings": 0.0, "success": 0}
        by_workflow[wf_name]["runs"] += 1
        by_workflow[wf_name]["cost"] += cost
        by_workflow[wf_name]["savings"] += savings
        if run.get("success"):
            by_workflow[wf_name]["success"] += 1

        # By provider
        if provider not in by_provider:
            by_provider[provider] = {"runs": 0, "cost": 0.0}
        by_provider[provider]["runs"] += 1
        by_provider[provider]["cost"] += cost

        # By tier (from stages)
        for stage in run.get("stages", []):
            if not stage.get("skipped"):
                tier = stage.get("tier", "capable")
                by_tier[tier] = by_tier.get(tier, 0.0) + stage.get("cost", 0.0)

        total_cost += cost
        total_savings += savings
        if run.get("success"):
            successful_runs += 1

    # Calculate average savings percent
    avg_savings_percent = 0.0
    if history:
        savings_percents = [r.get("savings_percent", 0) for r in history if r.get("success")]
        if savings_percents:
            avg_savings_percent = sum(savings_percents) / len(savings_percents)

    return {
        "total_runs": len(history),
        "successful_runs": successful_runs,
        "by_workflow": by_workflow,
        "by_provider": by_provider,
        "by_tier": by_tier,
        "recent_runs": history[-10:][::-1],  # Last 10, most recent first
        "total_cost": total_cost,
        "total_savings": total_savings,
        "avg_savings_percent": avg_savings_percent,
    }


class BaseWorkflow(ABC):
    """Base class for multi-model workflows.

    Subclasses define stages and tier mappings:

        class MyWorkflow(BaseWorkflow):
            name = "my-workflow"
            description = "Does something useful"
            stages = ["stage1", "stage2", "stage3"]
            tier_map = {
                "stage1": ModelTier.CHEAP,
                "stage2": ModelTier.CAPABLE,
                "stage3": ModelTier.PREMIUM,
            }

            async def run_stage(self, stage_name, tier, input_data):
                # Implement stage logic
                return output_data
    """

    name: str = "base-workflow"
    description: str = "Base workflow template"
    stages: list[str] = []
    tier_map: dict[str, ModelTier] = {}

    def __init__(
        self,
        cost_tracker: CostTracker | None = None,
        provider: ModelProvider | str | None = None,
        config: WorkflowConfig | None = None,
        executor: LLMExecutor | None = None,
        telemetry_backend: TelemetryBackend | None = None,
        progress_callback: ProgressCallback | None = None,
        cache: BaseCache | None = None,
        enable_cache: bool = True,
        enable_tier_tracking: bool = True,
        enable_tier_fallback: bool = False,
    ):
        """Initialize workflow with optional cost tracker, provider, and config.

        Args:
            cost_tracker: CostTracker instance for logging costs
            provider: Model provider (anthropic, openai, ollama) or ModelProvider enum.
                     If None, uses config or defaults to anthropic.
            config: WorkflowConfig for model customization. If None, loads from
                   .empathy/workflows.yaml or uses defaults.
            executor: LLMExecutor for abstracted LLM calls (optional).
                     If provided, enables unified execution with telemetry.
            telemetry_backend: TelemetryBackend for storing telemetry records.
                     Defaults to TelemetryStore (JSONL file backend).
            progress_callback: Callback for real-time progress updates.
                     If provided, enables live progress tracking during execution.
            cache: Optional cache instance. If None and enable_cache=True,
                   auto-creates cache with one-time setup prompt.
            enable_cache: Whether to enable caching (default True).
            enable_tier_tracking: Whether to enable automatic tier tracking (default True).
            enable_tier_fallback: Whether to enable intelligent tier fallback
                     (CHEAP → CAPABLE → PREMIUM). Opt-in feature (default False).

        """
        from .config import WorkflowConfig

        self.cost_tracker = cost_tracker or CostTracker()
        self._stages_run: list[WorkflowStage] = []

        # Progress tracking
        self._progress_callback = progress_callback
        self._progress_tracker: ProgressTracker | None = None

        # New: LLMExecutor support
        self._executor = executor
        self._telemetry_backend = telemetry_backend or get_telemetry_store()
        self._run_id: str | None = None  # Set at start of execute()
        self._api_key: str | None = None  # For default executor creation

        # Cache support
        self._cache: BaseCache | None = cache
        self._enable_cache = enable_cache
        self._cache_setup_attempted = False

        # Tier tracking support
        self._enable_tier_tracking = enable_tier_tracking
        self._tier_tracker: WorkflowTierTracker | None = None

        # Tier fallback support
        self._enable_tier_fallback = enable_tier_fallback
        self._tier_progression: list[tuple[str, str, bool]] = []  # (stage, tier, success)

        # Telemetry tracking (singleton instance)
        self._telemetry_tracker: UsageTracker | None = None
        self._enable_telemetry = True  # Enable by default
        if TELEMETRY_AVAILABLE and UsageTracker is not None:
            try:
                self._telemetry_tracker = UsageTracker.get_instance()
            except (OSError, PermissionError) as e:
                # File system errors - log but disable telemetry
                logger.debug(f"Failed to initialize telemetry tracker (file system error): {e}")
                self._enable_telemetry = False
            except (AttributeError, TypeError, ValueError) as e:
                # Configuration or initialization errors
                logger.debug(f"Failed to initialize telemetry tracker (config error): {e}")
                self._enable_telemetry = False

        # Load config if not provided
        self._config = config or WorkflowConfig.load()

        # Determine provider (priority: arg > config > default)
        if provider is None:
            provider = self._config.get_provider_for_workflow(self.name)

        # Handle string provider input
        if isinstance(provider, str):
            provider_str = provider.lower()
            try:
                provider = ModelProvider(provider_str)
                self._provider_str = provider_str
            except ValueError:
                # Custom provider, keep as string
                self._provider_str = provider_str
                provider = ModelProvider.CUSTOM
        else:
            self._provider_str = provider.value

        self.provider = provider

    def get_tier_for_stage(self, stage_name: str) -> ModelTier:
        """Get the model tier for a stage."""
        return self.tier_map.get(stage_name, ModelTier.CAPABLE)

    def get_model_for_tier(self, tier: ModelTier) -> str:
        """Get the model for a tier based on configured provider and config."""
        from .config import get_model

        provider_str = getattr(self, "_provider_str", self.provider.value)

        # Use config-aware model lookup
        model = get_model(provider_str, tier.value, self._config)
        return model

    def _maybe_setup_cache(self) -> None:
        """Set up cache with one-time user prompt if needed.

        This is called lazily on first workflow execution to avoid
        blocking workflow initialization.
        """
        if not self._enable_cache:
            return

        if self._cache_setup_attempted:
            return

        self._cache_setup_attempted = True

        # If cache already provided, use it
        if self._cache is not None:
            return

        # Otherwise, trigger auto-setup (which may prompt user)
        try:
            auto_setup_cache()
            self._cache = create_cache()
            logger.info(f"Cache initialized for workflow: {self.name}")
        except ImportError as e:
            # Hybrid cache dependencies not available, fall back to hash-only
            logger.info(
                f"Using hash-only cache (install empathy-framework[cache] for semantic caching): {e}"
            )
            self._cache = create_cache(cache_type="hash")
        except (OSError, PermissionError) as e:
            # File system errors - disable cache
            logger.warning(f"Cache setup failed (file system error): {e}, continuing without cache")
            self._enable_cache = False
        except (ValueError, TypeError, AttributeError) as e:
            # Configuration errors - disable cache
            logger.warning(f"Cache setup failed (config error): {e}, continuing without cache")
            self._enable_cache = False

    async def _call_llm(
        self,
        tier: ModelTier,
        system: str,
        user_message: str,
        max_tokens: int = 4096,
        stage_name: str | None = None,
    ) -> tuple[str, int, int]:
        """Provider-agnostic LLM call using the configured provider.

        This method uses run_step_with_executor internally to make LLM calls
        that respect the configured provider (anthropic, openai, google, etc.).

        Supports automatic caching to reduce API costs and latency.
        Tracks telemetry for usage analysis and cost savings measurement.

        Args:
            tier: Model tier to use (CHEAP, CAPABLE, PREMIUM)
            system: System prompt
            user_message: User message/prompt
            max_tokens: Maximum tokens in response
            stage_name: Optional stage name for cache key (defaults to tier)

        Returns:
            Tuple of (response_content, input_tokens, output_tokens)

        """
        from .step_config import WorkflowStepConfig

        # Start timing for telemetry
        start_time = time.time()

        # Determine stage name for cache key
        stage = stage_name or f"llm_call_{tier.value}"
        model = self.get_model_for_tier(tier)
        cache_type = None

        # Try cache lookup if enabled
        if self._enable_cache and self._cache is not None:
            try:
                # Combine system + user message for cache key
                full_prompt = f"{system}\n\n{user_message}" if system else user_message
                cached_response = self._cache.get(self.name, stage, full_prompt, model)

                if cached_response is not None:
                    logger.debug(f"Cache hit for {self.name}:{stage}")
                    # Determine cache type
                    if hasattr(self._cache, "cache_type"):
                        ct = self._cache.cache_type
                        # Ensure it's a string (not a Mock object)
                        cache_type = str(ct) if ct and isinstance(ct, str) else "hash"
                    else:
                        cache_type = "hash"  # Default assumption

                    # Track telemetry for cache hit
                    duration_ms = int((time.time() - start_time) * 1000)
                    in_tokens = cached_response["input_tokens"]
                    out_tokens = cached_response["output_tokens"]
                    cost = self._calculate_cost(tier, in_tokens, out_tokens)

                    self._track_telemetry(
                        stage=stage,
                        tier=tier,
                        model=model,
                        cost=cost,
                        tokens={"input": in_tokens, "output": out_tokens},
                        cache_hit=True,
                        cache_type=cache_type,
                        duration_ms=duration_ms,
                    )

                    # Cached response is dict with content, input_tokens, output_tokens
                    return (
                        cached_response["content"],
                        cached_response["input_tokens"],
                        cached_response["output_tokens"],
                    )
            except (KeyError, TypeError, ValueError) as e:
                # Malformed cache data - continue with LLM call
                logger.debug(f"Cache lookup failed (malformed data): {e}, continuing with LLM call")
            except (OSError, PermissionError) as e:
                # File system errors - continue with LLM call
                logger.debug(
                    f"Cache lookup failed (file system error): {e}, continuing with LLM call"
                )

        # Create a step config for this call
        step = WorkflowStepConfig(
            name=stage,
            task_type="general",
            tier_hint=tier.value,
            description="LLM call",
            max_tokens=max_tokens,
        )

        try:
            content, in_tokens, out_tokens, cost = await self.run_step_with_executor(
                step=step,
                prompt=user_message,
                system=system,
            )

            # Calculate duration
            duration_ms = int((time.time() - start_time) * 1000)

            # Track telemetry for actual LLM call
            self._track_telemetry(
                stage=stage,
                tier=tier,
                model=model,
                cost=cost,
                tokens={"input": in_tokens, "output": out_tokens},
                cache_hit=False,
                cache_type=None,
                duration_ms=duration_ms,
            )

            # Store in cache if enabled
            if self._enable_cache and self._cache is not None:
                try:
                    full_prompt = f"{system}\n\n{user_message}" if system else user_message
                    response_data = {
                        "content": content,
                        "input_tokens": in_tokens,
                        "output_tokens": out_tokens,
                    }
                    self._cache.put(self.name, stage, full_prompt, model, response_data)
                    logger.debug(f"Cached response for {self.name}:{stage}")
                except (OSError, PermissionError) as e:
                    # File system errors - log but continue
                    logger.debug(f"Failed to cache response (file system error): {e}")
                except (ValueError, TypeError, KeyError) as e:
                    # Data serialization errors - log but continue
                    logger.debug(f"Failed to cache response (serialization error): {e}")

            return content, in_tokens, out_tokens
        except (ValueError, TypeError, KeyError) as e:
            # Invalid input or configuration errors
            logger.warning(f"LLM call failed (invalid input): {e}")
            return f"Error calling LLM (invalid input): {e}", 0, 0
        except (TimeoutError, RuntimeError, ConnectionError) as e:
            # Timeout, API errors, or connection failures
            logger.warning(f"LLM call failed (timeout/API/connection error): {e}")
            return f"Error calling LLM (timeout/API error): {e}", 0, 0
        except (OSError, PermissionError) as e:
            # File system or permission errors
            logger.warning(f"LLM call failed (file system error): {e}")
            return f"Error calling LLM (file system error): {e}", 0, 0
        except Exception as e:
            # INTENTIONAL: Graceful degradation - return error message rather than crashing workflow
            logger.exception(f"Unexpected error calling LLM: {e}")
            return f"Error calling LLM: {type(e).__name__}", 0, 0

    def _track_telemetry(
        self,
        stage: str,
        tier: ModelTier,
        model: str,
        cost: float,
        tokens: dict[str, int],
        cache_hit: bool,
        cache_type: str | None,
        duration_ms: int,
    ) -> None:
        """Track telemetry for an LLM call.

        Args:
            stage: Stage name
            tier: Model tier used
            model: Model ID used
            cost: Cost in USD
            tokens: Dictionary with "input" and "output" token counts
            cache_hit: Whether this was a cache hit
            cache_type: Cache type if cache hit
            duration_ms: Duration in milliseconds

        """
        if not self._enable_telemetry or self._telemetry_tracker is None:
            return

        try:
            provider_str = getattr(self, "_provider_str", "unknown")
            self._telemetry_tracker.track_llm_call(
                workflow=self.name,
                stage=stage,
                tier=tier.value.upper(),
                model=model,
                provider=provider_str,
                cost=cost,
                tokens=tokens,
                cache_hit=cache_hit,
                cache_type=cache_type,
                duration_ms=duration_ms,
            )
        except (AttributeError, TypeError, ValueError) as e:
            # INTENTIONAL: Telemetry tracking failures should never crash workflows
            logger.debug(f"Failed to track telemetry (config/data error): {e}")
        except (OSError, PermissionError) as e:
            # File system errors - log but never crash workflow
            logger.debug(f"Failed to track telemetry (file system error): {e}")

    def _calculate_cost(self, tier: ModelTier, input_tokens: int, output_tokens: int) -> float:
        """Calculate cost for a stage."""
        tier_name = tier.value
        pricing = MODEL_PRICING.get(tier_name, MODEL_PRICING["capable"])
        input_cost = (input_tokens / 1_000_000) * pricing["input"]
        output_cost = (output_tokens / 1_000_000) * pricing["output"]
        return input_cost + output_cost

    def _calculate_baseline_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Calculate what the cost would be using premium tier."""
        pricing = MODEL_PRICING["premium"]
        input_cost = (input_tokens / 1_000_000) * pricing["input"]
        output_cost = (output_tokens / 1_000_000) * pricing["output"]
        return input_cost + output_cost

    def _generate_cost_report(self) -> CostReport:
        """Generate cost report from completed stages."""
        total_cost = 0.0
        baseline_cost = 0.0
        by_stage: dict[str, float] = {}
        by_tier: dict[str, float] = {}

        for stage in self._stages_run:
            if stage.skipped:
                continue

            total_cost += stage.cost
            by_stage[stage.name] = stage.cost

            tier_name = stage.tier.value
            by_tier[tier_name] = by_tier.get(tier_name, 0.0) + stage.cost

            # Calculate what this would cost at premium tier
            baseline_cost += self._calculate_baseline_cost(stage.input_tokens, stage.output_tokens)

        savings = baseline_cost - total_cost
        savings_percent = (savings / baseline_cost * 100) if baseline_cost > 0 else 0.0

        # Calculate cache metrics if cache is enabled
        cache_hits = 0
        cache_misses = 0
        cache_hit_rate = 0.0
        estimated_cost_without_cache = total_cost
        savings_from_cache = 0.0

        if self._cache is not None:
            try:
                stats = self._cache.get_stats()
                cache_hits = stats.hits
                cache_misses = stats.misses
                cache_hit_rate = stats.hit_rate

                # Estimate cost without cache (assumes cache hits would have incurred full cost)
                # This is a conservative estimate
                if cache_hits > 0:
                    # Average cost per non-cached call
                    avg_cost_per_call = total_cost / cache_misses if cache_misses > 0 else 0.0
                    # Estimated additional cost if cache hits were actual API calls
                    estimated_additional_cost = cache_hits * avg_cost_per_call
                    estimated_cost_without_cache = total_cost + estimated_additional_cost
                    savings_from_cache = estimated_additional_cost
            except (AttributeError, TypeError):
                # Cache doesn't support stats or error occurred
                pass

        return CostReport(
            total_cost=total_cost,
            baseline_cost=baseline_cost,
            savings=savings,
            savings_percent=savings_percent,
            by_stage=by_stage,
            by_tier=by_tier,
            cache_hits=cache_hits,
            cache_misses=cache_misses,
            cache_hit_rate=cache_hit_rate,
            estimated_cost_without_cache=estimated_cost_without_cache,
            savings_from_cache=savings_from_cache,
        )

    @abstractmethod
    async def run_stage(
        self,
        stage_name: str,
        tier: ModelTier,
        input_data: Any,
    ) -> tuple[Any, int, int]:
        """Execute a single workflow stage.

        Args:
            stage_name: Name of the stage to run
            tier: Model tier to use
            input_data: Input for this stage

        Returns:
            Tuple of (output_data, input_tokens, output_tokens)

        """

    def should_skip_stage(self, stage_name: str, input_data: Any) -> tuple[bool, str | None]:
        """Determine if a stage should be skipped.

        Override in subclasses for conditional stage execution.

        Args:
            stage_name: Name of the stage
            input_data: Current workflow data

        Returns:
            Tuple of (should_skip, reason)

        """
        return False, None

    def validate_output(self, stage_output: dict) -> tuple[bool, str | None]:
        """Validate stage output quality for tier fallback decisions.

        This is called after each stage execution when tier fallback is enabled.
        Override in subclasses to add workflow-specific validation logic.

        Default implementation checks:
        - No exceptions during execution (execution_succeeded)
        - Output is not empty (output_valid)
        - Required keys present if defined in stage config

        Args:
            stage_output: Output dict from run_stage()

        Returns:
            Tuple of (is_valid, failure_reason)
            - is_valid: True if output passes quality gates
            - failure_reason: Error code if validation failed (e.g., "output_empty",
              "health_score_low", "tests_failed")

        Example:
            >>> def validate_output(self, stage_output):
            ...     # Check health score for health-check workflow
            ...     health_score = stage_output.get("health_score", 0)
            ...     if health_score < 80:
            ...         return False, "health_score_low"
            ...     return True, None

        """
        # Default validation: check output is not empty
        if not stage_output:
            return False, "output_empty"

        # Check for error indicators in output
        if stage_output.get("error") is not None:
            return False, "execution_error"

        # Output is valid by default
        return True, None

    def _assess_complexity(self, input_data: dict[str, Any]) -> str:
        """Assess task complexity based on workflow stages and input.

        Args:
            input_data: Workflow input data

        Returns:
            Complexity level: "simple", "moderate", or "complex"

        """
        # Simple heuristic: based on number of stages and tier requirements
        num_stages = len(self.stages)
        premium_stages = sum(
            1 for s in self.stages if self.get_tier_for_stage(s) == ModelTier.PREMIUM
        )

        if num_stages <= 2 and premium_stages == 0:
            return "simple"
        elif num_stages <= 4 and premium_stages <= 1:
            return "moderate"
        else:
            return "complex"

    async def execute(self, **kwargs: Any) -> WorkflowResult:
        """Execute the full workflow.

        Args:
            **kwargs: Initial input data for the workflow

        Returns:
            WorkflowResult with stages, output, and cost report

        """
        # Set up cache (one-time setup with user prompt if needed)
        self._maybe_setup_cache()

        # Set run ID for telemetry correlation
        self._run_id = str(uuid.uuid4())

        # Log task routing (Tier 1 automation monitoring)
        routing_id = f"routing-{self._run_id}"
        routing_record = TaskRoutingRecord(
            routing_id=routing_id,
            timestamp=datetime.utcnow().isoformat() + "Z",
            task_description=f"{self.name}: {self.description}",
            task_type=self.name,
            task_complexity=self._assess_complexity(kwargs),
            assigned_agent=self.name,
            assigned_tier=getattr(self, "_provider_str", "unknown"),
            routing_strategy="rule_based",
            confidence_score=1.0,
            status="running",
            started_at=datetime.utcnow().isoformat() + "Z",
        )

        # Log routing start
        try:
            self._telemetry_backend.log_task_routing(routing_record)
        except Exception as e:
            logger.debug(f"Failed to log task routing: {e}")

        # Auto tier recommendation
        if self._enable_tier_tracking:
            try:
                from .tier_tracking import WorkflowTierTracker

                self._tier_tracker = WorkflowTierTracker(self.name, self.description)
                files_affected = kwargs.get("files_affected") or kwargs.get("path")
                if files_affected and not isinstance(files_affected, list):
                    files_affected = [str(files_affected)]
                self._tier_tracker.show_recommendation(files_affected)
            except Exception as e:
                logger.debug(f"Tier tracking disabled: {e}")
                self._enable_tier_tracking = False

        started_at = datetime.now()
        self._stages_run = []
        current_data = kwargs
        error = None

        # Initialize progress tracker if callback provided
        if self._progress_callback:
            self._progress_tracker = ProgressTracker(
                workflow_name=self.name,
                workflow_id=self._run_id,
                stage_names=self.stages,
            )
            self._progress_tracker.add_callback(self._progress_callback)
            self._progress_tracker.start_workflow()

        try:
            # Tier fallback mode: try CHEAP → CAPABLE → PREMIUM with validation
            if self._enable_tier_fallback:
                tier_chain = [ModelTier.CHEAP, ModelTier.CAPABLE, ModelTier.PREMIUM]

                for stage_name in self.stages:
                    # Check if stage should be skipped
                    should_skip, skip_reason = self.should_skip_stage(stage_name, current_data)

                    if should_skip:
                        tier = self.get_tier_for_stage(stage_name)
                        stage = WorkflowStage(
                            name=stage_name,
                            tier=tier,
                            description=f"Stage: {stage_name}",
                            skipped=True,
                            skip_reason=skip_reason,
                        )
                        self._stages_run.append(stage)

                        # Report skip to progress tracker
                        if self._progress_tracker:
                            self._progress_tracker.skip_stage(stage_name, skip_reason or "")

                        continue

                    # Try each tier in fallback chain
                    stage_succeeded = False
                    tier_index = 0

                    for tier in tier_chain:
                        stage_start = datetime.now()

                        # Report stage start to progress tracker with current tier
                        model_id = self.get_model_for_tier(tier)
                        if self._progress_tracker:
                            # On first attempt, start stage. On retry, update tier.
                            if tier_index == 0:
                                self._progress_tracker.start_stage(stage_name, tier.value, model_id)
                            else:
                                # Show tier upgrade (e.g., CHEAP → CAPABLE)
                                prev_tier = tier_chain[tier_index - 1].value
                                self._progress_tracker.update_tier(
                                    stage_name, tier.value, f"{prev_tier}_failed"
                                )

                        try:
                            # Run the stage at current tier
                            output, input_tokens, output_tokens = await self.run_stage(
                                stage_name,
                                tier,
                                current_data,
                            )

                            stage_end = datetime.now()
                            duration_ms = int((stage_end - stage_start).total_seconds() * 1000)
                            cost = self._calculate_cost(tier, input_tokens, output_tokens)

                            # Create stage output dict for validation
                            stage_output = (
                                output if isinstance(output, dict) else {"result": output}
                            )

                            # Validate output quality
                            is_valid, failure_reason = self.validate_output(stage_output)

                            if is_valid:
                                # Success - record stage and move to next
                                stage = WorkflowStage(
                                    name=stage_name,
                                    tier=tier,
                                    description=f"Stage: {stage_name}",
                                    input_tokens=input_tokens,
                                    output_tokens=output_tokens,
                                    cost=cost,
                                    result=output,
                                    duration_ms=duration_ms,
                                )
                                self._stages_run.append(stage)

                                # Report stage completion to progress tracker
                                if self._progress_tracker:
                                    self._progress_tracker.complete_stage(
                                        stage_name,
                                        cost=cost,
                                        tokens_in=input_tokens,
                                        tokens_out=output_tokens,
                                    )

                                # Log to cost tracker
                                self.cost_tracker.log_request(
                                    model=model_id,
                                    input_tokens=input_tokens,
                                    output_tokens=output_tokens,
                                    task_type=f"workflow:{self.name}:{stage_name}",
                                )

                                # Track telemetry for this stage
                                self._track_telemetry(
                                    stage=stage_name,
                                    tier=tier,
                                    model=model_id,
                                    cost=cost,
                                    tokens={"input": input_tokens, "output": output_tokens},
                                    cache_hit=False,
                                    cache_type=None,
                                    duration_ms=duration_ms,
                                )

                                # Record successful tier usage
                                self._tier_progression.append((stage_name, tier.value, True))
                                stage_succeeded = True

                                # Pass output to next stage
                                current_data = stage_output
                                break  # Success - move to next stage

                            else:
                                # Quality gate failed - try next tier
                                self._tier_progression.append((stage_name, tier.value, False))
                                logger.info(
                                    f"Stage {stage_name} failed quality validation with {tier.value}: "
                                    f"{failure_reason}"
                                )

                                # Check if more tiers available
                                if tier_index < len(tier_chain) - 1:
                                    logger.info("Retrying with higher tier...")
                                else:
                                    logger.error(f"All tiers exhausted for {stage_name}")

                        except Exception as e:
                            # Exception during stage execution - try next tier
                            self._tier_progression.append((stage_name, tier.value, False))
                            logger.warning(
                                f"Stage {stage_name} error with {tier.value}: {type(e).__name__}: {e}"
                            )

                            # Check if more tiers available
                            if tier_index < len(tier_chain) - 1:
                                logger.info("Retrying with higher tier...")
                            else:
                                logger.error(f"All tiers exhausted for {stage_name}")

                        tier_index += 1

                    # Check if stage succeeded with any tier
                    if not stage_succeeded:
                        error_msg = (
                            f"Stage {stage_name} failed with all tiers: CHEAP, CAPABLE, PREMIUM"
                        )
                        if self._progress_tracker:
                            self._progress_tracker.fail_stage(stage_name, error_msg)
                        raise ValueError(error_msg)

            # Standard mode: use configured tier_map (backward compatible)
            else:
                for stage_name in self.stages:
                    tier = self.get_tier_for_stage(stage_name)
                    stage_start = datetime.now()

                    # Check if stage should be skipped
                    should_skip, skip_reason = self.should_skip_stage(stage_name, current_data)

                    if should_skip:
                        stage = WorkflowStage(
                            name=stage_name,
                            tier=tier,
                            description=f"Stage: {stage_name}",
                            skipped=True,
                            skip_reason=skip_reason,
                        )
                        self._stages_run.append(stage)

                        # Report skip to progress tracker
                        if self._progress_tracker:
                            self._progress_tracker.skip_stage(stage_name, skip_reason or "")

                        continue

                    # Report stage start to progress tracker
                    model_id = self.get_model_for_tier(tier)
                    if self._progress_tracker:
                        self._progress_tracker.start_stage(stage_name, tier.value, model_id)

                    # Run the stage
                    output, input_tokens, output_tokens = await self.run_stage(
                        stage_name,
                        tier,
                        current_data,
                    )

                    stage_end = datetime.now()
                    duration_ms = int((stage_end - stage_start).total_seconds() * 1000)
                    cost = self._calculate_cost(tier, input_tokens, output_tokens)

                    stage = WorkflowStage(
                        name=stage_name,
                        tier=tier,
                        description=f"Stage: {stage_name}",
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        cost=cost,
                        result=output,
                        duration_ms=duration_ms,
                    )
                    self._stages_run.append(stage)

                    # Report stage completion to progress tracker
                    if self._progress_tracker:
                        self._progress_tracker.complete_stage(
                            stage_name,
                            cost=cost,
                            tokens_in=input_tokens,
                            tokens_out=output_tokens,
                        )

                    # Log to cost tracker
                    self.cost_tracker.log_request(
                        model=model_id,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        task_type=f"workflow:{self.name}:{stage_name}",
                    )

                    # Track telemetry for this stage
                    self._track_telemetry(
                        stage=stage_name,
                        tier=tier,
                        model=model_id,
                        cost=cost,
                        tokens={"input": input_tokens, "output": output_tokens},
                        cache_hit=False,
                        cache_type=None,
                        duration_ms=duration_ms,
                    )

                    # Pass output to next stage
                    current_data = output if isinstance(output, dict) else {"result": output}

        except (ValueError, TypeError, KeyError) as e:
            # Data validation or configuration errors
            error = f"Workflow execution error (data/config): {e}"
            logger.error(error)
            if self._progress_tracker:
                self._progress_tracker.fail_workflow(error)
        except (TimeoutError, RuntimeError, ConnectionError) as e:
            # Timeout, API errors, or connection failures
            error = f"Workflow execution error (timeout/API/connection): {e}"
            logger.error(error)
            if self._progress_tracker:
                self._progress_tracker.fail_workflow(error)
        except (OSError, PermissionError) as e:
            # File system or permission errors
            error = f"Workflow execution error (file system): {e}"
            logger.error(error)
            if self._progress_tracker:
                self._progress_tracker.fail_workflow(error)
        except Exception as e:
            # INTENTIONAL: Workflow orchestration - catch all errors to report failure gracefully
            logger.exception(f"Unexpected error in workflow execution: {type(e).__name__}")
            error = f"Workflow execution failed: {type(e).__name__}"
            if self._progress_tracker:
                self._progress_tracker.fail_workflow(error)

        completed_at = datetime.now()
        total_duration_ms = int((completed_at - started_at).total_seconds() * 1000)

        # Get final output from last non-skipped stage
        final_output = None
        for stage in reversed(self._stages_run):
            if not stage.skipped and stage.result is not None:
                final_output = stage.result
                break

        # Classify error type and transient status
        error_type = None
        transient = False
        if error:
            error_lower = error.lower()
            if "timeout" in error_lower or "timed out" in error_lower:
                error_type = "timeout"
                transient = True
            elif "config" in error_lower or "configuration" in error_lower:
                error_type = "config"
                transient = False
            elif "api" in error_lower or "rate limit" in error_lower or "quota" in error_lower:
                error_type = "provider"
                transient = True
            elif "validation" in error_lower or "invalid" in error_lower:
                error_type = "validation"
                transient = False
            else:
                error_type = "runtime"
                transient = False

        provider_str = getattr(self, "_provider_str", "unknown")
        result = WorkflowResult(
            success=error is None,
            stages=self._stages_run,
            final_output=final_output,
            cost_report=self._generate_cost_report(),
            started_at=started_at,
            completed_at=completed_at,
            total_duration_ms=total_duration_ms,
            provider=provider_str,
            error=error,
            error_type=error_type,
            transient=transient,
        )

        # Report workflow completion to progress tracker
        if self._progress_tracker and error is None:
            self._progress_tracker.complete_workflow()

        # Save to workflow history for dashboard
        try:
            _save_workflow_run(self.name, provider_str, result)
        except (OSError, PermissionError):
            # File system errors saving history - log but don't crash workflow
            logger.warning("Failed to save workflow history (file system error)")
        except (ValueError, TypeError, KeyError):
            # Data serialization errors - log but don't crash workflow
            logger.warning("Failed to save workflow history (serialization error)")
        except Exception:
            # INTENTIONAL: History save is optional diagnostics - never crash workflow
            logger.exception("Unexpected error saving workflow history")

        # Emit workflow telemetry to backend
        self._emit_workflow_telemetry(result)

        # Auto-save tier progression
        if self._enable_tier_tracking and self._tier_tracker:
            try:
                files_affected = kwargs.get("files_affected") or kwargs.get("path")
                if files_affected and not isinstance(files_affected, list):
                    files_affected = [str(files_affected)]

                # Determine bug type from workflow name
                bug_type_map = {
                    "code-review": "code_quality",
                    "bug-predict": "bug_prediction",
                    "security-audit": "security_issue",
                    "test-gen": "test_coverage",
                    "refactor-plan": "refactoring",
                    "health-check": "health_check",
                }
                bug_type = bug_type_map.get(self.name, "workflow_run")

                # Pass tier_progression data if tier fallback was enabled
                tier_progression_data = (
                    self._tier_progression if self._enable_tier_fallback else None
                )

                self._tier_tracker.save_progression(
                    workflow_result=result,
                    files_affected=files_affected,
                    bug_type=bug_type,
                    tier_progression=tier_progression_data,
                )
            except Exception as e:
                logger.debug(f"Failed to save tier progression: {e}")

        # Update routing record with completion status (Tier 1 automation monitoring)
        routing_record.status = "completed" if result.success else "failed"
        routing_record.completed_at = datetime.utcnow().isoformat() + "Z"
        routing_record.success = result.success
        routing_record.actual_cost = sum(s.cost for s in result.stages)

        if not result.success and result.error:
            routing_record.error_type = result.error_type or "unknown"
            routing_record.error_message = result.error

        # Log routing completion
        try:
            self._telemetry_backend.log_task_routing(routing_record)
        except Exception as e:
            logger.debug(f"Failed to log task routing completion: {e}")

        return result

    def describe(self) -> str:
        """Get a human-readable description of the workflow."""
        lines = [
            f"Workflow: {self.name}",
            f"Description: {self.description}",
            "",
            "Stages:",
        ]

        for stage_name in self.stages:
            tier = self.get_tier_for_stage(stage_name)
            model = self.get_model_for_tier(tier)
            lines.append(f"  {stage_name}: {tier.value} ({model})")

        return "\n".join(lines)

    def _build_cached_system_prompt(
        self,
        role: str,
        guidelines: list[str] | None = None,
        documentation: str | None = None,
        examples: list[dict[str, str]] | None = None,
    ) -> str:
        """Build system prompt optimized for Anthropic prompt caching.

        Prompt caching works best with:
        - Static content (guidelines, docs, coding standards)
        - Frequent reuse (>3 requests within 5 min)
        - Large context (>1024 tokens)

        Structure: Static content goes first (cacheable), dynamic content
        goes in user messages (not cached).

        Args:
            role: The role for the AI (e.g., "expert code reviewer")
            guidelines: List of static guidelines/rules
            documentation: Static documentation or reference material
            examples: Static examples for few-shot learning

        Returns:
            System prompt with static content first for optimal caching

        Example:
            >>> prompt = workflow._build_cached_system_prompt(
            ...     role="code reviewer",
            ...     guidelines=[
            ...         "Follow PEP 8 style guide",
            ...         "Check for security vulnerabilities",
            ...     ],
            ...     documentation="Coding standards:\\n- Use type hints\\n- Add docstrings",
            ... )
            >>> # This prompt will be cached by Anthropic for 5 minutes
            >>> # Subsequent calls with same prompt read from cache (90% cost reduction)
        """
        parts = []

        # 1. Role definition (static)
        parts.append(f"You are a {role}.")

        # 2. Guidelines (static - most important for caching)
        if guidelines:
            parts.append("\n# Guidelines\n")
            for i, guideline in enumerate(guidelines, 1):
                parts.append(f"{i}. {guideline}")

        # 3. Documentation (static - good caching candidate)
        if documentation:
            parts.append("\n# Reference Documentation\n")
            parts.append(documentation)

        # 4. Examples (static - excellent for few-shot learning)
        if examples:
            parts.append("\n# Examples\n")
            for i, example in enumerate(examples, 1):
                input_text = example.get("input", "")
                output_text = example.get("output", "")
                parts.append(f"\nExample {i}:")
                parts.append(f"Input: {input_text}")
                parts.append(f"Output: {output_text}")

        # Dynamic content (user-specific context, current task) should go
        # in the user message, NOT in system prompt
        parts.append(
            "\n# Instructions\n"
            "The user will provide the specific task context in their message. "
            "Apply the above guidelines and reference documentation to their request."
        )

        return "\n".join(parts)

    # =========================================================================
    # New infrastructure methods (Phase 4)
    # =========================================================================

    def _create_execution_context(
        self,
        step_name: str,
        task_type: str,
        user_id: str | None = None,
        session_id: str | None = None,
    ) -> ExecutionContext:
        """Create an ExecutionContext for a step execution.

        Args:
            step_name: Name of the workflow step
            task_type: Task type for routing
            user_id: Optional user ID
            session_id: Optional session ID

        Returns:
            ExecutionContext populated with workflow info

        """
        return ExecutionContext(
            workflow_name=self.name,
            step_name=step_name,
            user_id=user_id,
            session_id=session_id,
            metadata={
                "task_type": task_type,
                "run_id": self._run_id,
                "provider": self._provider_str,
            },
        )

    def _create_default_executor(self) -> LLMExecutor:
        """Create a default EmpathyLLMExecutor with optional resilience wrapper.

        This method is called lazily when run_step_with_executor is used
        without a pre-configured executor.

        When tier fallback is enabled (enable_tier_fallback=True), the base
        executor is returned without the ResilientExecutor wrapper to avoid
        double fallback (tier-level + LLM-level).

        When tier fallback is disabled (default), the executor is wrapped with
        resilience features (retry, fallback, circuit breaker).

        Returns:
            LLMExecutor instance (optionally wrapped with ResilientExecutor)

        """
        from empathy_os.models.empathy_executor import EmpathyLLMExecutor
        from empathy_os.models.fallback import ResilientExecutor

        # Create the base executor
        base_executor = EmpathyLLMExecutor(
            provider=self._provider_str,
            api_key=self._api_key,
            telemetry_store=self._telemetry_backend,
        )

        # When tier fallback is enabled, skip LLM-level fallback
        # to avoid double fallback (tier-level + LLM-level)
        if self._enable_tier_fallback:
            return base_executor

        # Standard mode: wrap with resilience layer (retry, fallback, circuit breaker)
        return ResilientExecutor(executor=base_executor)

    def _get_executor(self) -> LLMExecutor:
        """Get or create the LLM executor.

        Returns the configured executor or creates a default one.

        Returns:
            LLMExecutor instance

        """
        if self._executor is None:
            self._executor = self._create_default_executor()
        return self._executor

    def _emit_call_telemetry(
        self,
        step_name: str,
        task_type: str,
        tier: str,
        model_id: str,
        input_tokens: int,
        output_tokens: int,
        cost: float,
        latency_ms: int,
        success: bool = True,
        error_message: str | None = None,
        fallback_used: bool = False,
    ) -> None:
        """Emit an LLMCallRecord to the telemetry backend.

        Args:
            step_name: Name of the workflow step
            task_type: Task type used for routing
            tier: Model tier used
            model_id: Model ID used
            input_tokens: Input token count
            output_tokens: Output token count
            cost: Estimated cost
            latency_ms: Latency in milliseconds
            success: Whether the call succeeded
            error_message: Error message if failed
            fallback_used: Whether fallback was used

        """
        record = LLMCallRecord(
            call_id=str(uuid.uuid4()),
            timestamp=datetime.now().isoformat(),
            workflow_name=self.name,
            step_name=step_name,
            task_type=task_type,
            provider=self._provider_str,
            tier=tier,
            model_id=model_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_cost=cost,
            latency_ms=latency_ms,
            success=success,
            error_message=error_message,
            fallback_used=fallback_used,
            metadata={"run_id": self._run_id},
        )
        try:
            self._telemetry_backend.log_call(record)
        except (AttributeError, ValueError, TypeError):
            # Telemetry backend errors - log but don't crash workflow
            logger.debug("Failed to log call telemetry (backend error)")
        except OSError:
            # File system errors - log but don't crash workflow
            logger.debug("Failed to log call telemetry (file system error)")
        except Exception:  # noqa: BLE001
            # INTENTIONAL: Telemetry is optional diagnostics - never crash workflow
            logger.debug("Unexpected error logging call telemetry")

    def _emit_workflow_telemetry(self, result: WorkflowResult) -> None:
        """Emit a WorkflowRunRecord to the telemetry backend.

        Args:
            result: The workflow result to record

        """
        # Build stage records
        stages = [
            WorkflowStageRecord(
                stage_name=s.name,
                tier=s.tier.value,
                model_id=self.get_model_for_tier(s.tier),
                input_tokens=s.input_tokens,
                output_tokens=s.output_tokens,
                cost=s.cost,
                latency_ms=s.duration_ms,
                success=not s.skipped and result.error is None,
                skipped=s.skipped,
                skip_reason=s.skip_reason,
            )
            for s in result.stages
        ]

        record = WorkflowRunRecord(
            run_id=self._run_id or str(uuid.uuid4()),
            workflow_name=self.name,
            started_at=result.started_at.isoformat(),
            completed_at=result.completed_at.isoformat(),
            stages=stages,
            total_input_tokens=sum(s.input_tokens for s in result.stages if not s.skipped),
            total_output_tokens=sum(s.output_tokens for s in result.stages if not s.skipped),
            total_cost=result.cost_report.total_cost,
            baseline_cost=result.cost_report.baseline_cost,
            savings=result.cost_report.savings,
            savings_percent=result.cost_report.savings_percent,
            total_duration_ms=result.total_duration_ms,
            success=result.success,
            error=result.error,
            providers_used=[self._provider_str],
            tiers_used=list(result.cost_report.by_tier.keys()),
        )
        try:
            self._telemetry_backend.log_workflow(record)
        except (AttributeError, ValueError, TypeError):
            # Telemetry backend errors - log but don't crash workflow
            logger.debug("Failed to log workflow telemetry (backend error)")
        except OSError:
            # File system errors - log but don't crash workflow
            logger.debug("Failed to log workflow telemetry (file system error)")
        except Exception:  # noqa: BLE001
            # INTENTIONAL: Telemetry is optional diagnostics - never crash workflow
            logger.debug("Unexpected error logging workflow telemetry")

    async def run_step_with_executor(
        self,
        step: WorkflowStepConfig,
        prompt: str,
        system: str | None = None,
        **kwargs: Any,
    ) -> tuple[str, int, int, float]:
        """Run a workflow step using the LLMExecutor.

        This method provides a unified interface for executing steps with
        automatic routing, telemetry, and cost tracking. If no executor
        was provided at construction, a default EmpathyLLMExecutor is created.

        Args:
            step: WorkflowStepConfig defining the step
            prompt: The prompt to send
            system: Optional system prompt
            **kwargs: Additional arguments passed to executor

        Returns:
            Tuple of (content, input_tokens, output_tokens, cost)

        """
        executor = self._get_executor()

        context = self._create_execution_context(
            step_name=step.name,
            task_type=step.task_type,
        )

        start_time = datetime.now()
        response = await executor.run(
            task_type=step.task_type,
            prompt=prompt,
            system=system,
            context=context,
            **kwargs,
        )
        end_time = datetime.now()
        latency_ms = int((end_time - start_time).total_seconds() * 1000)

        # Emit telemetry
        self._emit_call_telemetry(
            step_name=step.name,
            task_type=step.task_type,
            tier=response.tier,
            model_id=response.model_id,
            input_tokens=response.tokens_input,
            output_tokens=response.tokens_output,
            cost=response.cost_estimate,
            latency_ms=latency_ms,
            success=True,
        )

        return (
            response.content,
            response.tokens_input,
            response.tokens_output,
            response.cost_estimate,
        )

    # =========================================================================
    # XML Prompt Integration (Phase 4)
    # =========================================================================

    def _get_xml_config(self) -> dict[str, Any]:
        """Get XML prompt configuration for this workflow.

        Returns:
            Dictionary with XML configuration settings.

        """
        if self._config is None:
            return {}
        return self._config.get_xml_config_for_workflow(self.name)

    def _is_xml_enabled(self) -> bool:
        """Check if XML prompts are enabled for this workflow."""
        config = self._get_xml_config()
        return bool(config.get("enabled", False))

    def _render_xml_prompt(
        self,
        role: str,
        goal: str,
        instructions: list[str],
        constraints: list[str],
        input_type: str,
        input_payload: str,
        extra: dict[str, Any] | None = None,
    ) -> str:
        """Render a prompt using XML template if enabled.

        Args:
            role: The role for the AI (e.g., "security analyst").
            goal: The primary objective.
            instructions: Step-by-step instructions.
            constraints: Rules and guidelines.
            input_type: Type of input ("code", "diff", "document").
            input_payload: The content to process.
            extra: Additional context data.

        Returns:
            Rendered prompt string (XML if enabled, plain text otherwise).

        """
        from empathy_os.prompts import PromptContext, XmlPromptTemplate, get_template

        config = self._get_xml_config()

        if not config.get("enabled", False):
            # Fall back to plain text
            return self._render_plain_prompt(
                role,
                goal,
                instructions,
                constraints,
                input_type,
                input_payload,
            )

        # Create context
        context = PromptContext(
            role=role,
            goal=goal,
            instructions=instructions,
            constraints=constraints,
            input_type=input_type,
            input_payload=input_payload,
            extra=extra or {},
        )

        # Get template
        template_name = config.get("template_name", self.name)
        template = get_template(template_name)

        if template is None:
            # Create a basic XML template if no built-in found
            template = XmlPromptTemplate(
                name=self.name,
                schema_version=config.get("schema_version", "1.0"),
            )

        return template.render(context)

    def _render_plain_prompt(
        self,
        role: str,
        goal: str,
        instructions: list[str],
        constraints: list[str],
        input_type: str,
        input_payload: str,
    ) -> str:
        """Render a plain text prompt (fallback when XML is disabled)."""
        parts = [f"You are a {role}.", "", f"Goal: {goal}", ""]

        if instructions:
            parts.append("Instructions:")
            for i, inst in enumerate(instructions, 1):
                parts.append(f"{i}. {inst}")
            parts.append("")

        if constraints:
            parts.append("Guidelines:")
            for constraint in constraints:
                parts.append(f"- {constraint}")
            parts.append("")

        if input_payload:
            parts.append(f"Input ({input_type}):")
            parts.append(input_payload)

        return "\n".join(parts)

    def _parse_xml_response(self, response: str) -> dict[str, Any]:
        """Parse an XML response if XML enforcement is enabled.

        Args:
            response: The LLM response text.

        Returns:
            Dictionary with parsed fields or raw response data.

        """
        from empathy_os.prompts import XmlResponseParser

        config = self._get_xml_config()

        if not config.get("enforce_response_xml", False):
            # No parsing needed, return as-is
            return {
                "_parsed_response": None,
                "_raw": response,
            }

        fallback = config.get("fallback_on_parse_error", True)
        parser = XmlResponseParser(fallback_on_error=fallback)
        parsed = parser.parse(response)

        return {
            "_parsed_response": parsed,
            "_raw": response,
            "summary": parsed.summary,
            "findings": [f.to_dict() for f in parsed.findings],
            "checklist": parsed.checklist,
            "xml_parsed": parsed.success,
            "parse_errors": parsed.errors,
        }

    def _extract_findings_from_response(
        self,
        response: str,
        files_changed: list[str],
        code_context: str = "",
    ) -> list[dict[str, Any]]:
        """Extract structured findings from LLM response.

        Tries multiple strategies in order:
        1. XML parsing (if XML tags present)
        2. Regex-based extraction for file:line patterns
        3. Returns empty list if no findings extractable

        Args:
            response: Raw LLM response text
            files_changed: List of files being analyzed (for context)
            code_context: Original code being reviewed (optional)

        Returns:
            List of findings matching WorkflowFinding schema:
            [
                {
                    "id": "unique-id",
                    "file": "relative/path.py",
                    "line": 42,
                    "column": 10,
                    "severity": "high",
                    "category": "security",
                    "message": "Brief message",
                    "details": "Extended explanation",
                    "recommendation": "Fix suggestion"
                }
            ]

        """
        import re
        import uuid

        findings: list[dict[str, Any]] = []

        # Strategy 1: Try XML parsing first
        response_lower = response.lower()
        if (
            "<finding>" in response_lower
            or "<issue>" in response_lower
            or "<findings>" in response_lower
        ):
            # Parse XML directly (bypass config checks)
            from empathy_os.prompts import XmlResponseParser

            parser = XmlResponseParser(fallback_on_error=True)
            parsed = parser.parse(response)

            if parsed.success and parsed.findings:
                for raw_finding in parsed.findings:
                    enriched = self._enrich_finding_with_location(
                        raw_finding.to_dict(),
                        files_changed,
                    )
                    findings.append(enriched)
                return findings

        # Strategy 2: Regex-based extraction for common patterns
        # Match patterns like:
        # - "src/auth.py:42: SQL injection found"
        # - "In file src/auth.py line 42"
        # - "auth.py (line 42, column 10)"
        patterns = [
            # Pattern 1: file.py:line:column: message
            r"([^\s:]+\.(?:py|ts|tsx|js|jsx|java|go|rb|php)):(\d+):(\d+):\s*(.+)",
            # Pattern 2: file.py:line: message
            r"([^\s:]+\.(?:py|ts|tsx|js|jsx|java|go|rb|php)):(\d+):\s*(.+)",
            # Pattern 3: in file X line Y
            r"(?:in file|file)\s+([^\s]+\.(?:py|ts|tsx|js|jsx|java|go|rb|php))\s+line\s+(\d+)",
            # Pattern 4: file.py (line X)
            r"([^\s]+\.(?:py|ts|tsx|js|jsx|java|go|rb|php))\s*\(line\s+(\d+)(?:,\s*col(?:umn)?\s+(\d+))?\)",
        ]

        for pattern in patterns:
            matches = re.findall(pattern, response, re.IGNORECASE)
            for match in matches:
                if len(match) >= 2:
                    file_path = match[0]
                    line = int(match[1])

                    # Handle different pattern formats
                    if len(match) == 4 and match[2].isdigit():
                        # Pattern 1: file:line:col:message
                        column = int(match[2])
                        message = match[3]
                    elif len(match) == 3 and match[2] and not match[2].isdigit():
                        # Pattern 2: file:line:message
                        column = 1
                        message = match[2]
                    elif len(match) == 3 and match[2].isdigit():
                        # Pattern 4: file (line col)
                        column = int(match[2])
                        message = ""
                    else:
                        # Pattern 3: in file X line Y (no message)
                        column = 1
                        message = ""

                    # Determine severity from keywords in message
                    severity = self._infer_severity(message)
                    category = self._infer_category(message)

                    findings.append(
                        {
                            "id": str(uuid.uuid4())[:8],
                            "file": file_path,
                            "line": line,
                            "column": column,
                            "severity": severity,
                            "category": category,
                            "message": message.strip() if message else "",
                            "details": "",
                            "recommendation": "",
                        },
                    )

        # Deduplicate by file:line
        seen = set()
        unique_findings = []
        for finding in findings:
            key = (finding["file"], finding["line"])
            if key not in seen:
                seen.add(key)
                unique_findings.append(finding)

        return unique_findings

    def _enrich_finding_with_location(
        self,
        raw_finding: dict[str, Any],
        files_changed: list[str],
    ) -> dict[str, Any]:
        """Enrich a finding from XML parser with file/line/column fields.

        Args:
            raw_finding: Finding dict from XML parser (has 'location' string field)
            files_changed: List of files being analyzed

        Returns:
            Enriched finding dict with file, line, column fields

        """
        import uuid

        location_str = raw_finding.get("location", "")
        file_path, line, column = self._parse_location_string(location_str, files_changed)

        # Map category from severity or title keywords
        category = self._infer_category(
            raw_finding.get("title", "") + " " + raw_finding.get("details", ""),
        )

        return {
            "id": str(uuid.uuid4())[:8],
            "file": file_path,
            "line": line,
            "column": column,
            "severity": raw_finding.get("severity", "medium"),
            "category": category,
            "message": raw_finding.get("title", ""),
            "details": raw_finding.get("details", ""),
            "recommendation": raw_finding.get("fix", ""),
        }

    def _parse_location_string(
        self,
        location: str,
        files_changed: list[str],
    ) -> tuple[str, int, int]:
        """Parse a location string to extract file, line, column.

        Handles formats like:
        - "src/auth.py:42:10"
        - "src/auth.py:42"
        - "auth.py line 42"
        - "line 42 in auth.py"

        Args:
            location: Location string from finding
            files_changed: List of files being analyzed (for fallback)

        Returns:
            Tuple of (file_path, line_number, column_number)
            Defaults: ("", 1, 1) if parsing fails

        """
        import re

        if not location:
            # Fallback: use first file if available
            return (files_changed[0] if files_changed else "", 1, 1)

        # Try colon-separated format: file.py:line:col
        match = re.search(
            r"([^\s:]+\.(?:py|ts|tsx|js|jsx|java|go|rb|php)):(\d+)(?::(\d+))?",
            location,
        )
        if match:
            file_path = match.group(1)
            line = int(match.group(2))
            column = int(match.group(3)) if match.group(3) else 1
            return (file_path, line, column)

        # Try "line X in file.py" format
        match = re.search(
            r"line\s+(\d+)\s+(?:in|of)\s+([^\s]+\.(?:py|ts|tsx|js|jsx|java|go|rb|php))",
            location,
            re.IGNORECASE,
        )
        if match:
            line = int(match.group(1))
            file_path = match.group(2)
            return (file_path, line, 1)

        # Try "file.py line X" format
        match = re.search(
            r"([^\s]+\.(?:py|ts|tsx|js|jsx|java|go|rb|php))\s+line\s+(\d+)",
            location,
            re.IGNORECASE,
        )
        if match:
            file_path = match.group(1)
            line = int(match.group(2))
            return (file_path, line, 1)

        # Extract just line number if present
        match = re.search(r"line\s+(\d+)", location, re.IGNORECASE)
        if match:
            line = int(match.group(1))
            # Use first file from files_changed as fallback
            file_path = files_changed[0] if files_changed else ""
            return (file_path, line, 1)

        # Couldn't parse - return defaults
        return (files_changed[0] if files_changed else "", 1, 1)

    def _infer_severity(self, text: str) -> str:
        """Infer severity from keywords in text.

        Args:
            text: Message or title text

        Returns:
            Severity level: critical, high, medium, low, or info

        """
        text_lower = text.lower()

        if any(
            word in text_lower
            for word in [
                "critical",
                "severe",
                "exploit",
                "vulnerability",
                "injection",
                "remote code execution",
                "rce",
            ]
        ):
            return "critical"

        if any(
            word in text_lower
            for word in [
                "high",
                "security",
                "unsafe",
                "dangerous",
                "xss",
                "csrf",
                "auth",
                "password",
                "secret",
            ]
        ):
            return "high"

        if any(
            word in text_lower
            for word in [
                "warning",
                "issue",
                "problem",
                "bug",
                "error",
                "deprecated",
                "leak",
            ]
        ):
            return "medium"

        if any(word in text_lower for word in ["low", "minor", "style", "format", "typo"]):
            return "low"

        return "info"

    def _infer_category(self, text: str) -> str:
        """Infer finding category from keywords.

        Args:
            text: Message or title text

        Returns:
            Category: security, performance, maintainability, style, or correctness

        """
        text_lower = text.lower()

        if any(
            word in text_lower
            for word in [
                "security",
                "vulnerability",
                "injection",
                "xss",
                "csrf",
                "auth",
                "encrypt",
                "password",
                "secret",
                "unsafe",
            ]
        ):
            return "security"

        if any(
            word in text_lower
            for word in [
                "performance",
                "slow",
                "memory",
                "leak",
                "inefficient",
                "optimization",
                "cache",
            ]
        ):
            return "performance"

        if any(
            word in text_lower
            for word in [
                "complex",
                "refactor",
                "duplicate",
                "maintainability",
                "readability",
                "documentation",
            ]
        ):
            return "maintainability"

        if any(
            word in text_lower for word in ["style", "format", "lint", "convention", "whitespace"]
        ):
            return "style"

        return "correctness"
