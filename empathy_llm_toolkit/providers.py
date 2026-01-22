"""LLM Provider Adapters

Unified interface for different LLM providers (OpenAI, Anthropic, local models).

Copyright 2025 Smart AI Memory, LLC
Licensed under Fair Source 0.9
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class LLMResponse:
    """Standardized response from any LLM provider"""

    content: str
    model: str
    tokens_used: int
    finish_reason: str
    metadata: dict[str, Any]


class BaseLLMProvider(ABC):
    """Base class for all LLM providers.

    Provides unified interface regardless of backend.
    """

    def __init__(self, api_key: str | None = None, **kwargs):
        self.api_key = api_key
        self.config = kwargs

    @abstractmethod
    async def generate(
        self,
        messages: list[dict[str, str]],
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        **kwargs,
    ) -> LLMResponse:
        """Generate response from LLM.

        Args:
            messages: List of {"role": "user/assistant", "content": "..."}
            system_prompt: Optional system prompt
            temperature: Sampling temperature
            max_tokens: Maximum tokens in response
            **kwargs: Provider-specific options

        Returns:
            LLMResponse with standardized format

        """

    @abstractmethod
    def get_model_info(self) -> dict[str, Any]:
        """Get information about the model being used"""

    def estimate_tokens(self, text: str) -> int:
        """Estimate token count for text.

        Rough approximation: ~4 chars per token
        """
        return len(text) // 4


class AnthropicProvider(BaseLLMProvider):
    """Anthropic (Claude) provider with enhanced features.

    Supports Claude 3 family models with advanced capabilities:
    - Extended context windows (200K tokens)
    - Prompt caching for faster repeated queries
    - Thinking mode for complex reasoning
    - Batch processing for cost optimization
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "claude-sonnet-4-5-20250929",
        use_prompt_caching: bool = True,  # CHANGED: Default to True for 20-30% cost savings
        use_thinking: bool = False,
        use_batch: bool = False,
        **kwargs,
    ):
        super().__init__(api_key, **kwargs)
        self.model = model
        self.use_prompt_caching = use_prompt_caching
        self.use_thinking = use_thinking
        self.use_batch = use_batch

        # Validate API key is provided
        if not api_key or not api_key.strip():
            raise ValueError(
                "API key is required for Anthropic provider. "
                "Provide via api_key parameter or ANTHROPIC_API_KEY environment variable",
            )

        # Lazy import to avoid requiring anthropic if not used
        # v4.6.3: Use AsyncAnthropic for true async I/O (prevents event loop blocking)
        try:
            import anthropic

            self.client = anthropic.AsyncAnthropic(api_key=api_key)
        except ImportError as e:
            raise ImportError(
                "anthropic package required. Install with: pip install anthropic",
            ) from e

        # Initialize batch provider if needed
        if use_batch:
            self.batch_provider = AnthropicBatchProvider(api_key=api_key)
        else:
            self.batch_provider = None

    async def generate(
        self,
        messages: list[dict[str, str]],
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        **kwargs,
    ) -> LLMResponse:
        """Generate response using Anthropic API with enhanced features.

        Claude-specific enhancements:
        - Prompt caching for repeated system prompts (90% cost reduction)
        - Extended context (200K tokens) for large codebase analysis
        - Thinking mode for complex reasoning tasks

        Prompt caching is enabled by default (use_prompt_caching=True).
        This marks system prompts with cache_control for Anthropic's cache.
        Break-even: ~3 requests with same context, 5-minute TTL.
        """
        # Build kwargs for Anthropic
        api_kwargs = {
            "model": self.model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": messages,
        }

        # Enable prompt caching for system prompts (Claude-specific)
        if system_prompt and self.use_prompt_caching:
            api_kwargs["system"] = [
                {
                    "type": "text",
                    "text": system_prompt,
                    "cache_control": {"type": "ephemeral"},  # Cache for 5 minutes
                },
            ]
        elif system_prompt:
            api_kwargs["system"] = system_prompt

        # Enable extended thinking for complex tasks (Claude-specific)
        if self.use_thinking:
            api_kwargs["thinking"] = {
                "type": "enabled",
                "budget_tokens": 2000,  # Allow 2K tokens for reasoning
            }

        # Add any additional kwargs
        api_kwargs.update(kwargs)

        # Call Anthropic API (async with AsyncAnthropic)
        response = await self.client.messages.create(**api_kwargs)  # type: ignore[call-overload]

        # Extract thinking content if present
        thinking_content = None
        response_content = ""

        for block in response.content:
            if hasattr(block, "type"):
                if block.type == "thinking":
                    thinking_content = block.thinking
                elif block.type == "text":
                    response_content = block.text
            else:
                response_content = block.text

        # Convert to standardized format
        metadata = {
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
            "provider": "anthropic",
            "model_family": "claude-3",
        }

        # Add cache performance metrics if available
        if hasattr(response.usage, "cache_creation_input_tokens"):
            cache_creation = getattr(response.usage, "cache_creation_input_tokens", 0)
            cache_read = getattr(response.usage, "cache_read_input_tokens", 0)

            # Ensure values are numeric (handle mock objects in tests)
            if isinstance(cache_creation, int) and isinstance(cache_read, int):
                metadata["cache_creation_tokens"] = cache_creation
                metadata["cache_read_tokens"] = cache_read

                # Log cache performance for monitoring with detailed cost savings
                # Cache reads cost 90% less than regular input tokens
                # Cache writes cost 25% more than regular input tokens
                if cache_read > 0:
                    # Sonnet 4.5 input: $3/M tokens, cache read: $0.30/M tokens (90% discount)
                    savings_per_token = 0.003 / 1000 * 0.9  # 90% of regular cost
                    total_savings = cache_read * savings_per_token
                    logger.info(
                        f"Cache HIT: {cache_read:,} tokens read from cache "
                        f"(saved ${total_savings:.4f} vs full price)"
                    )
                if cache_creation > 0:
                    # Cache write cost: $3.75/M tokens (25% markup)
                    write_cost = cache_creation * 0.00375 / 1000
                    logger.debug(
                        f"Cache WRITE: {cache_creation:,} tokens written to cache "
                        f"(cost ${write_cost:.4f})"
                    )

        # Add thinking content if present
        if thinking_content:
            metadata["thinking"] = thinking_content

        return LLMResponse(
            content=response_content,
            model=response.model,
            tokens_used=response.usage.input_tokens + response.usage.output_tokens,
            finish_reason=response.stop_reason,
            metadata=metadata,
        )

    async def analyze_large_codebase(
        self,
        codebase_files: list[dict[str, str]],
        analysis_prompt: str,
        **kwargs,
    ) -> LLMResponse:
        """Analyze large codebases using Claude's 200K context window.

        Claude-specific feature: Can process entire repositories in one call.

        Args:
            codebase_files: List of {"path": "...", "content": "..."} dicts
            analysis_prompt: What to analyze for
            **kwargs: Additional generation parameters

        Returns:
            LLMResponse with analysis results

        """
        # Build context from all files
        file_context = "\n\n".join(
            [f"# File: {file['path']}\n{file['content']}" for file in codebase_files],
        )

        # Create system prompt with caching for file context
        system_parts = [
            {
                "type": "text",
                "text": "You are a code analysis expert using the Empathy Framework.",
            },
            {
                "type": "text",
                "text": f"Codebase files:\n\n{file_context}",
                "cache_control": {"type": "ephemeral"},  # Cache the codebase
            },
        ]

        messages = [{"role": "user", "content": analysis_prompt}]

        # Use extended max_tokens for comprehensive analysis
        return await self.generate(
            messages=messages,
            system_prompt=None,  # We'll pass it directly in api_kwargs
            max_tokens=kwargs.pop("max_tokens", 4096),
            **{**kwargs, "system": system_parts},
        )

    def get_model_info(self) -> dict[str, Any]:
        """Get Claude model information with extended context capabilities"""
        model_info = {
            "claude-3-opus-20240229": {
                "max_tokens": 200000,
                "cost_per_1m_input": 15.00,
                "cost_per_1m_output": 75.00,
                "supports_prompt_caching": True,
                "supports_thinking": True,
                "ideal_for": "Complex reasoning, large codebases",
            },
            "claude-3-5-sonnet-20241022": {
                "max_tokens": 200000,
                "cost_per_1m_input": 3.00,
                "cost_per_1m_output": 15.00,
                "supports_prompt_caching": True,
                "supports_thinking": True,
                "ideal_for": "General development, balanced cost/performance",
            },
            "claude-3-haiku-20240307": {
                "max_tokens": 200000,
                "cost_per_1m_input": 0.25,
                "cost_per_1m_output": 1.25,
                "supports_prompt_caching": True,
                "supports_thinking": False,
                "ideal_for": "Fast responses, simple tasks",
            },
        }

        return model_info.get(
            self.model,
            {
                "max_tokens": 200000,
                "cost_per_1m_input": 3.00,
                "cost_per_1m_output": 15.00,
                "supports_prompt_caching": True,
                "supports_thinking": True,
            },
        )


class AnthropicBatchProvider:
    """Provider for Anthropic Batch API (50% cost reduction).

    The Batch API processes requests asynchronously within 24 hours
    at 50% of the standard API cost. Ideal for non-urgent, bulk tasks.

    Example:
        >>> provider = AnthropicBatchProvider(api_key="sk-ant-...")
        >>> requests = [
        ...     {
        ...         "custom_id": "task_1",
        ...         "model": "claude-sonnet-4-5",
        ...         "messages": [{"role": "user", "content": "Analyze X"}],
        ...         "max_tokens": 1024
        ...     }
        ... ]
        >>> batch_id = provider.create_batch(requests)
        >>> # Wait for processing (up to 24 hours)
        >>> results = await provider.wait_for_batch(batch_id)
    """

    def __init__(self, api_key: str | None = None):
        """Initialize batch provider.

        Args:
            api_key: Anthropic API key (defaults to ANTHROPIC_API_KEY env var)
        """
        if not api_key or not api_key.strip():
            raise ValueError(
                "API key is required for Anthropic Batch API. "
                "Provide via api_key parameter or ANTHROPIC_API_KEY environment variable"
            )

        try:
            import anthropic

            self.client = anthropic.Anthropic(api_key=api_key)
            self._batch_jobs: dict[str, Any] = {}
        except ImportError as e:
            raise ImportError(
                "anthropic package required for Batch API. "
                "Install with: pip install anthropic"
            ) from e

    def create_batch(
        self, requests: list[dict[str, Any]], job_id: str | None = None
    ) -> str:
        """Create a batch job.

        Args:
            requests: List of request dicts with 'custom_id', 'model', 'messages', etc.
            job_id: Optional job identifier for tracking (unused, for API compatibility)

        Returns:
            Batch job ID for polling status

        Raises:
            ValueError: If requests is empty or invalid
            RuntimeError: If API call fails

        Example:
            >>> requests = [
            ...     {
            ...         "custom_id": "task_1",
            ...         "model": "claude-sonnet-4-5",
            ...         "messages": [{"role": "user", "content": "Test"}],
            ...         "max_tokens": 1024
            ...     }
            ... ]
            >>> batch_id = provider.create_batch(requests)
            >>> print(f"Batch created: {batch_id}")
            Batch created: batch_abc123
        """
        if not requests:
            raise ValueError("requests cannot be empty")

        try:
            batch = self.client.batches.create(requests=requests)
            self._batch_jobs[batch.id] = batch
            logger.info(f"Created batch {batch.id} with {len(requests)} requests")
            return batch.id
        except Exception as e:
            logger.error(f"Failed to create batch: {e}")
            raise RuntimeError(f"Batch creation failed: {e}") from e

    def get_batch_status(self, batch_id: str) -> Any:
        """Get status of batch job.

        Args:
            batch_id: Batch job ID

        Returns:
            BatchStatus object with status field:
            - "processing": Batch is being processed
            - "completed": Batch processing completed
            - "failed": Batch processing failed

        Example:
            >>> status = provider.get_batch_status("batch_abc123")
            >>> print(status.status)
            processing
        """
        try:
            batch = self.client.batches.retrieve(batch_id)
            self._batch_jobs[batch_id] = batch
            return batch
        except Exception as e:
            logger.error(f"Failed to get batch status for {batch_id}: {e}")
            raise RuntimeError(f"Failed to get batch status: {e}") from e

    def get_batch_results(self, batch_id: str) -> list[dict[str, Any]]:
        """Get results from completed batch.

        Args:
            batch_id: Batch job ID

        Returns:
            List of result dicts matching input order

        Raises:
            ValueError: If batch is not completed
            RuntimeError: If API call fails

        Example:
            >>> results = provider.get_batch_results("batch_abc123")
            >>> for result in results:
            ...     print(f"{result['custom_id']}: {result['response']['content']}")
        """
        status = self.get_batch_status(batch_id)

        if status.status != "completed":
            raise ValueError(
                f"Batch {batch_id} not completed (status: {status.status})"
            )

        try:
            results = self.client.batches.results(batch_id)
            return list(results)
        except Exception as e:
            logger.error(f"Failed to get batch results for {batch_id}: {e}")
            raise RuntimeError(f"Failed to get batch results: {e}") from e

    async def wait_for_batch(
        self,
        batch_id: str,
        poll_interval: int = 60,
        timeout: int = 86400,  # 24 hours
    ) -> list[dict[str, Any]]:
        """Wait for batch to complete with polling.

        Args:
            batch_id: Batch job ID
            poll_interval: Seconds between status checks (default: 60)
            timeout: Maximum wait time in seconds (default: 86400 = 24 hours)

        Returns:
            Batch results when completed

        Raises:
            TimeoutError: If batch doesn't complete within timeout
            RuntimeError: If batch processing fails

        Example:
            >>> results = await provider.wait_for_batch(
            ...     "batch_abc123",
            ...     poll_interval=300,  # Check every 5 minutes
            ... )
            >>> print(f"Batch completed: {len(results)} results")
        """

        start_time = datetime.now()

        while True:
            status = self.get_batch_status(batch_id)

            if status.status == "completed":
                logger.info(f"Batch {batch_id} completed successfully")
                return self.get_batch_results(batch_id)

            if status.status == "failed":
                error_msg = getattr(status, "error", "Unknown error")
                logger.error(f"Batch {batch_id} failed: {error_msg}")
                raise RuntimeError(f"Batch {batch_id} failed: {error_msg}")

            # Check timeout
            elapsed = (datetime.now() - start_time).total_seconds()
            if elapsed > timeout:
                raise TimeoutError(
                    f"Batch {batch_id} did not complete within {timeout}s"
                )

            # Log progress
            logger.debug(f"Batch {batch_id} status: {status.status} (elapsed: {elapsed:.0f}s)")

            # Wait before next poll
            await asyncio.sleep(poll_interval)


class OpenAIProvider(BaseLLMProvider):
    """OpenAI provider.

    Supports GPT-4, GPT-3.5, and other OpenAI models.
    """

    def __init__(self, api_key: str | None = None, model: str = "gpt-4-turbo-preview", **kwargs):
        super().__init__(api_key, **kwargs)
        self.model = model

        # Validate API key is provided
        if not api_key or not api_key.strip():
            raise ValueError(
                "API key is required for OpenAI provider. "
                "Provide via api_key parameter or OPENAI_API_KEY environment variable",
            )

        # Lazy import
        try:
            import openai

            self.client = openai.AsyncOpenAI(api_key=api_key)
        except ImportError as e:
            raise ImportError("openai package required. Install with: pip install openai") from e

    async def generate(
        self,
        messages: list[dict[str, str]],
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        **kwargs,
    ) -> LLMResponse:
        """Generate response using OpenAI API"""
        # Add system prompt if provided
        if system_prompt:
            messages = [{"role": "system", "content": system_prompt}] + messages

        # Call OpenAI API
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,  # type: ignore[arg-type]
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )

        # Convert to standardized format
        content = response.choices[0].message.content or ""
        usage = response.usage
        return LLMResponse(
            content=content,
            model=response.model,
            tokens_used=usage.total_tokens if usage else 0,
            finish_reason=response.choices[0].finish_reason,
            metadata={
                "input_tokens": usage.prompt_tokens if usage else 0,
                "output_tokens": usage.completion_tokens if usage else 0,
                "provider": "openai",
            },
        )

    def get_model_info(self) -> dict[str, Any]:
        """Get OpenAI model information"""
        model_info = {
            "gpt-4-turbo-preview": {
                "max_tokens": 128000,
                "cost_per_1m_input": 10.00,
                "cost_per_1m_output": 30.00,
            },
            "gpt-4": {"max_tokens": 8192, "cost_per_1m_input": 30.00, "cost_per_1m_output": 60.00},
            "gpt-3.5-turbo": {
                "max_tokens": 16385,
                "cost_per_1m_input": 0.50,
                "cost_per_1m_output": 1.50,
            },
        }

        return model_info.get(
            self.model,
            {"max_tokens": 128000, "cost_per_1m_input": 10.00, "cost_per_1m_output": 30.00},
        )


class GeminiProvider(BaseLLMProvider):
    """Google Gemini provider with cost tracking integration.

    Supports Gemini models:
    - gemini-2.0-flash-exp: Fast, cheap tier (1M context)
    - gemini-1.5-pro: Balanced, capable tier (2M context)
    - gemini-2.5-pro: Premium reasoning tier
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "gemini-1.5-pro",
        **kwargs,
    ):
        super().__init__(api_key, **kwargs)
        self.model = model

        # Validate API key is provided
        if not api_key or not api_key.strip():
            raise ValueError(
                "API key is required for Gemini provider. "
                "Provide via api_key parameter or GOOGLE_API_KEY environment variable",
            )

        # Lazy import to avoid requiring google-generativeai if not used
        try:
            import google.generativeai as genai

            genai.configure(api_key=api_key)
            self.genai = genai
            self.client = genai.GenerativeModel(model)
        except ImportError as e:
            raise ImportError(
                "google-generativeai package required. Install with: pip install google-generativeai",
            ) from e

    async def generate(
        self,
        messages: list[dict[str, str]],
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        **kwargs,
    ) -> LLMResponse:
        """Generate response using Google Gemini API.

        Gemini-specific features:
        - Large context windows (1M-2M tokens)
        - Multimodal support
        - Grounding with Google Search
        """
        import asyncio

        # Convert messages to Gemini format
        gemini_messages = []
        for msg in messages:
            role = "user" if msg["role"] == "user" else "model"
            gemini_messages.append({"role": role, "parts": [msg["content"]]})

        # Build generation config
        generation_config = self.genai.GenerationConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
        )

        # Create model with system instruction if provided
        if system_prompt:
            model = self.genai.GenerativeModel(
                self.model,
                system_instruction=system_prompt,
            )
        else:
            model = self.client

        # Call Gemini API (run sync in thread pool for async compatibility)
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: model.generate_content(
                gemini_messages,  # type: ignore[arg-type]
                generation_config=generation_config,
            ),
        )

        # Extract token counts from usage metadata
        input_tokens = 0
        output_tokens = 0
        if hasattr(response, "usage_metadata"):
            input_tokens = getattr(response.usage_metadata, "prompt_token_count", 0)
            output_tokens = getattr(response.usage_metadata, "candidates_token_count", 0)

        # Log to cost tracker
        try:
            from empathy_os.cost_tracker import log_request

            tier = self._get_tier()
            log_request(
                model=self.model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                task_type=kwargs.get("task_type", "gemini_generate"),
                tier=tier,
            )
        except ImportError:
            pass  # Cost tracking not available

        # Convert to standardized format
        content = ""
        if response.candidates:
            content = response.candidates[0].content.parts[0].text

        finish_reason = "stop"
        if response.candidates and hasattr(response.candidates[0], "finish_reason"):
            finish_reason = str(response.candidates[0].finish_reason.name).lower()

        return LLMResponse(
            content=content,
            model=self.model,
            tokens_used=input_tokens + output_tokens,
            finish_reason=finish_reason,
            metadata={
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "provider": "google",
                "model_family": "gemini",
            },
        )

    def _get_tier(self) -> str:
        """Determine tier from model name."""
        if "flash" in self.model.lower():
            return "cheap"
        if "2.5" in self.model or "ultra" in self.model.lower():
            return "premium"
        return "capable"

    def get_model_info(self) -> dict[str, Any]:
        """Get Gemini model information"""
        model_info = {
            "gemini-2.0-flash-exp": {
                "max_tokens": 1000000,
                "cost_per_1m_input": 0.075,
                "cost_per_1m_output": 0.30,
                "supports_vision": True,
                "ideal_for": "Fast responses, simple tasks, large context",
            },
            "gemini-1.5-pro": {
                "max_tokens": 2000000,
                "cost_per_1m_input": 1.25,
                "cost_per_1m_output": 5.00,
                "supports_vision": True,
                "ideal_for": "Complex reasoning, large codebases",
            },
            "gemini-2.5-pro": {
                "max_tokens": 1000000,
                "cost_per_1m_input": 2.50,
                "cost_per_1m_output": 10.00,
                "supports_vision": True,
                "ideal_for": "Advanced reasoning, complex tasks",
            },
        }

        return model_info.get(
            self.model,
            {
                "max_tokens": 1000000,
                "cost_per_1m_input": 1.25,
                "cost_per_1m_output": 5.00,
                "supports_vision": True,
            },
        )


class LocalProvider(BaseLLMProvider):
    """Local model provider (Ollama, LM Studio, etc.).

    For running models locally.
    """

    def __init__(self, endpoint: str = "http://localhost:11434", model: str = "llama2", **kwargs):
        super().__init__(api_key=None, **kwargs)
        self.endpoint = endpoint
        self.model = model

    async def generate(
        self,
        messages: list[dict[str, str]],
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        **kwargs,
    ) -> LLMResponse:
        """Generate response using local model"""
        import aiohttp

        # Format for Ollama-style API
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }

        if system_prompt:
            payload["system"] = system_prompt

        async with aiohttp.ClientSession() as session:
            async with session.post(f"{self.endpoint}/api/chat", json=payload) as response:
                result = await response.json()

                return LLMResponse(
                    content=result.get("message", {}).get("content", ""),
                    model=self.model,
                    tokens_used=result.get("eval_count", 0) + result.get("prompt_eval_count", 0),
                    finish_reason="stop",
                    metadata={"provider": "local", "endpoint": self.endpoint},
                )

    def get_model_info(self) -> dict[str, Any]:
        """Get local model information"""
        return {
            "max_tokens": 4096,  # Depends on model
            "cost_per_1m_input": 0.0,  # Free (local)
            "cost_per_1m_output": 0.0,
            "endpoint": self.endpoint,
        }
