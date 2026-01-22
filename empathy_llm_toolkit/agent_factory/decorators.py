"""Agent Factory Decorators

Standardized decorators for agent operations including error handling,
logging, and performance monitoring.

Copyright 2025 Smart-AI-Memory
Licensed under Fair Source License 0.9
"""

import asyncio
import logging
import time
from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar

from empathy_llm_toolkit.config.unified import AgentOperationError

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


def safe_agent_operation(operation_name: str):
    """Decorator for safe agent operations with logging and error handling.

    Wraps async agent methods to:
    - Log operation start/end
    - Catch and wrap exceptions
    - Add to audit trail if available
    - Provide graceful degradation

    Args:
        operation_name: Human-readable name for the operation

    Example:
        class MyAgent(BaseAgent):
            @safe_agent_operation("invoke")
            async def invoke(self, input_data, context=None):
                # Operation code here
                pass

    """

    def decorator(func: F) -> F:
        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            start_time = time.time()
            agent_name = getattr(self, "name", self.__class__.__name__)

            logger.debug(f"[{agent_name}] Starting {operation_name}")

            try:
                result = await func(self, *args, **kwargs)

                elapsed = time.time() - start_time
                logger.debug(f"[{agent_name}] Completed {operation_name} in {elapsed:.2f}s")

                return result

            except Exception as e:
                elapsed = time.time() - start_time
                logger.error(f"[{agent_name}] {operation_name} failed after {elapsed:.2f}s: {e}")

                # Add to audit trail if available
                if hasattr(self, "add_audit_entry"):
                    state = kwargs.get("state", {})
                    if not state and args:
                        # Check if first arg is state-like
                        if isinstance(args[0], dict):
                            state = args[0]

                    try:
                        self.add_audit_entry(
                            state=state,
                            action=f"{operation_name}_error",
                            details={
                                "error": str(e),
                                "error_type": type(e).__name__,
                                "elapsed_seconds": elapsed,
                            },
                        )
                    except Exception:  # noqa: BLE001
                        # INTENTIONAL: Audit trail is optional - don't fail the main operation
                        pass

                raise AgentOperationError(operation_name, e) from e

        return wrapper  # type: ignore

    return decorator


def retry_on_failure(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,),
):
    """Decorator to retry failed operations with exponential backoff.

    Args:
        max_attempts: Maximum number of attempts
        delay: Initial delay between retries (seconds)
        backoff: Multiplier for delay after each retry
        exceptions: Tuple of exception types to catch and retry

    Example:
        @retry_on_failure(max_attempts=3, delay=1.0)
        async def call_external_api(self):
            # Flaky operation
            pass

    """

    def decorator(func: F) -> F:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            current_delay = delay

            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        logger.warning(
                            f"Attempt {attempt + 1}/{max_attempts} failed: {e}. "
                            f"Retrying in {current_delay:.1f}s...",
                        )
                        await asyncio.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        logger.error(f"All {max_attempts} attempts failed. Last error: {e}")

            raise last_exception

        return wrapper  # type: ignore

    return decorator


def log_performance(threshold_seconds: float = 1.0):
    """Decorator to log slow operations.

    Args:
        threshold_seconds: Log warning if operation exceeds this duration

    Example:
        @log_performance(threshold_seconds=2.0)
        async def heavy_computation(self):
            # Potentially slow operation
            pass

    """

    def decorator(func: F) -> F:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()

            result = await func(*args, **kwargs)

            elapsed = time.time() - start_time
            func_name = func.__name__

            if elapsed > threshold_seconds:
                logger.warning(
                    f"Slow operation: {func_name} took {elapsed:.2f}s "
                    f"(threshold: {threshold_seconds}s)",
                )
            else:
                logger.debug(f"{func_name} completed in {elapsed:.2f}s")

            return result

        return wrapper  # type: ignore

    return decorator


def validate_input(required_fields: list[str]):
    """Decorator to validate required fields in input data.

    Args:
        required_fields: List of required field names

    Example:
        @validate_input(["query", "context"])
        async def process(self, input_data: dict):
            # input_data is guaranteed to have query and context
            pass

    """

    def decorator(func: F) -> F:
        @wraps(func)
        async def wrapper(self, input_data, *args, **kwargs):
            if not isinstance(input_data, dict):
                raise ValueError(f"Input must be a dict, got {type(input_data).__name__}")

            missing = [f for f in required_fields if f not in input_data]
            if missing:
                raise ValueError(f"Missing required fields: {missing}")

            return await func(self, input_data, *args, **kwargs)

        return wrapper  # type: ignore

    return decorator


def with_cost_tracking(operation_type: str = "agent_call"):
    """Decorator to track API costs for operations.

    Args:
        operation_type: Type of operation for cost categorization

    Example:
        @with_cost_tracking(operation_type="research")
        async def research(self, query: str):
            # LLM call that should be tracked
            pass

    """

    def decorator(func: F) -> F:
        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            # Record start
            operation_id = f"{operation_type}_{time.time_ns()}"

            result = await func(self, *args, **kwargs)

            # Extract token usage if available
            if isinstance(result, dict):
                metadata = result.get("metadata", {})
                tokens_used = metadata.get("tokens_used", 0)
                model = metadata.get("model", "unknown")

                # Log for cost tracking
                if hasattr(self, "_track_cost"):
                    self._track_cost(
                        operation_id=operation_id,
                        operation_type=operation_type,
                        model=model,
                        tokens=tokens_used,
                    )

            return result

        return wrapper  # type: ignore

    return decorator


def graceful_degradation(fallback_value: Any = None, log_level: str = "warning"):
    """Decorator for graceful degradation on failure.

    Instead of raising an exception, returns a fallback value.

    Args:
        fallback_value: Value to return on failure
        log_level: Log level for the failure message

    Example:
        @graceful_degradation(fallback_value=[], log_level="warning")
        async def get_optional_data(self):
            # If this fails, return empty list instead of crashing
            pass

    """

    def decorator(func: F) -> F:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                log_func = getattr(logger, log_level.lower(), logger.warning)
                log_func(f"{func.__name__} failed, using fallback: {e}")
                return fallback_value

        return wrapper  # type: ignore

    return decorator
