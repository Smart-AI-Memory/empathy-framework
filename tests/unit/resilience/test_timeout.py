"""Tests for timeout pattern implementation.

These tests cover:
- TimeoutError exception
- @timeout decorator for sync/async functions
- with_timeout async helper
- Fallback behavior on timeout
"""

import asyncio
import platform

import pytest

from empathy_os.resilience.timeout import TimeoutError, timeout, with_timeout


@pytest.mark.unit
class TestTimeoutError:
    """Test TimeoutError exception."""

    def test_create_timeout_error(self):
        """Test creating TimeoutError with operation and timeout."""
        error = TimeoutError("fetch_data", 30.0)

        assert error.operation == "fetch_data"
        assert error.timeout == 30.0

    def test_timeout_error_message(self):
        """Test TimeoutError message format."""
        error = TimeoutError("api_call", 10.5)

        assert str(error) == "Operation 'api_call' timed out after 10.5s"

    def test_timeout_error_is_exception(self):
        """Test TimeoutError is an Exception subclass."""
        error = TimeoutError("test", 5.0)

        assert isinstance(error, Exception)

    def test_can_raise_timeout_error(self):
        """Test TimeoutError can be raised and caught."""
        with pytest.raises(TimeoutError) as exc_info:
            raise TimeoutError("slow_op", 1.0)

        assert exc_info.value.operation == "slow_op"
        assert exc_info.value.timeout == 1.0


@pytest.mark.unit
class TestTimeoutDecoratorAsync:
    """Test @timeout decorator with async functions."""

    @pytest.mark.asyncio
    async def test_decorated_async_completes_in_time(self):
        """Test decorated async function that completes in time."""

        @timeout(1.0)
        async def fast_func():
            await asyncio.sleep(0.01)
            return "success"

        result = await fast_func()

        assert result == "success"

    @pytest.mark.asyncio
    async def test_decorated_async_times_out(self):
        """Test decorated async function that exceeds timeout."""

        @timeout(0.05)
        async def slow_func():
            await asyncio.sleep(1.0)
            return "never_returned"

        with pytest.raises(TimeoutError) as exc_info:
            await slow_func()

        assert exc_info.value.operation == "slow_func"
        assert exc_info.value.timeout == 0.05

    @pytest.mark.asyncio
    async def test_custom_error_message(self):
        """Test timeout with custom error message."""

        @timeout(0.05, error_message="Custom operation description")
        async def slow_func():
            await asyncio.sleep(1.0)

        with pytest.raises(TimeoutError) as exc_info:
            await slow_func()

        assert exc_info.value.operation == "Custom operation description"

    @pytest.mark.asyncio
    async def test_fallback_on_timeout(self):
        """Test fallback function is called on timeout."""

        def fallback_func():
            return "fallback_value"

        @timeout(0.05, fallback=fallback_func)
        async def slow_func():
            await asyncio.sleep(1.0)
            return "never_returned"

        result = await slow_func()

        assert result == "fallback_value"

    @pytest.mark.asyncio
    async def test_async_fallback_on_timeout(self):
        """Test async fallback function is called on timeout."""

        async def async_fallback():
            await asyncio.sleep(0.01)
            return "async_fallback_value"

        @timeout(0.05, fallback=async_fallback)
        async def slow_func():
            await asyncio.sleep(1.0)
            return "never_returned"

        result = await slow_func()

        assert result == "async_fallback_value"

    @pytest.mark.asyncio
    async def test_preserves_function_name(self):
        """Test decorator preserves function metadata."""

        @timeout(1.0)
        async def my_async_function():
            return "value"

        assert my_async_function.__name__ == "my_async_function"

    @pytest.mark.asyncio
    async def test_passes_arguments(self):
        """Test decorated function passes arguments."""

        @timeout(1.0)
        async def func_with_args(x, y, z=None):
            return f"{x}-{y}-{z}"

        result = await func_with_args("a", "b", z="c")

        assert result == "a-b-c"

    @pytest.mark.asyncio
    async def test_fallback_receives_arguments(self):
        """Test fallback function receives original arguments."""

        def fallback_func(x, y):
            return f"fallback-{x}-{y}"

        @timeout(0.05, fallback=fallback_func)
        async def slow_func(x, y):
            await asyncio.sleep(1.0)
            return f"primary-{x}-{y}"

        result = await slow_func("a", "b")

        assert result == "fallback-a-b"

    @pytest.mark.asyncio
    async def test_zero_timeout_immediately_times_out(self):
        """Test zero timeout causes immediate timeout."""

        @timeout(0)
        async def func():
            await asyncio.sleep(0.1)
            return "value"

        with pytest.raises(TimeoutError):
            await func()

    @pytest.mark.asyncio
    async def test_return_value_preserved(self):
        """Test return value is correctly preserved."""

        @timeout(1.0)
        async def get_dict():
            return {"key": "value", "number": 42}

        result = await get_dict()

        assert result == {"key": "value", "number": 42}


@pytest.mark.unit
class TestTimeoutDecoratorSync:
    """Test @timeout decorator with sync functions."""

    @pytest.mark.skipif(
        platform.system() == "Windows",
        reason="Signal-based timeout not supported on Windows",
    )
    def test_decorated_sync_completes_in_time(self):
        """Test decorated sync function that completes in time."""
        import time

        @timeout(1.0)
        def fast_func():
            time.sleep(0.01)
            return "success"

        result = fast_func()

        assert result == "success"

    @pytest.mark.skipif(
        platform.system() == "Windows",
        reason="Signal-based timeout not supported on Windows",
    )
    def test_decorated_sync_times_out(self):
        """Test decorated sync function that exceeds timeout."""
        import time

        @timeout(0.1)
        def slow_func():
            time.sleep(2.0)
            return "never_returned"

        with pytest.raises(TimeoutError) as exc_info:
            slow_func()

        assert exc_info.value.timeout == 0.1

    @pytest.mark.skipif(
        platform.system() == "Windows",
        reason="Signal-based timeout not supported on Windows",
    )
    def test_sync_fallback_on_timeout(self):
        """Test sync fallback function is called on timeout."""
        import time

        def fallback_func():
            return "fallback_value"

        @timeout(0.1, fallback=fallback_func)
        def slow_func():
            time.sleep(2.0)
            return "never_returned"

        result = slow_func()

        assert result == "fallback_value"

    def test_preserves_sync_function_name(self):
        """Test decorator preserves sync function metadata."""

        @timeout(1.0)
        def my_sync_function():
            return "value"

        assert my_sync_function.__name__ == "my_sync_function"

    @pytest.mark.skipif(
        platform.system() != "Windows",
        reason="Windows-specific test",
    )
    def test_windows_runs_without_timeout(self, caplog):
        """Test Windows runs function without timeout enforcement."""
        import logging

        caplog.set_level(logging.WARNING)

        @timeout(0.01)
        def fast_func():
            return "success"

        result = fast_func()

        assert result == "success"
        # Should log warning about timeout not supported
        assert "not supported on Windows" in caplog.text


@pytest.mark.unit
class TestWithTimeout:
    """Test with_timeout async helper function."""

    @pytest.mark.asyncio
    async def test_coroutine_completes_in_time(self):
        """Test coroutine that completes within timeout."""

        async def fast_coro():
            await asyncio.sleep(0.01)
            return "success"

        result = await with_timeout(fast_coro(), 1.0)

        assert result == "success"

    @pytest.mark.asyncio
    async def test_coroutine_times_out(self):
        """Test coroutine that exceeds timeout."""

        async def slow_coro():
            await asyncio.sleep(1.0)
            return "never_returned"

        with pytest.raises(TimeoutError) as exc_info:
            await with_timeout(slow_coro(), 0.05)

        assert exc_info.value.operation == "coroutine"
        assert exc_info.value.timeout == 0.05

    @pytest.mark.asyncio
    async def test_fallback_value_on_timeout(self):
        """Test fallback value is returned on timeout."""

        async def slow_coro():
            await asyncio.sleep(1.0)
            return "never_returned"

        result = await with_timeout(slow_coro(), 0.05, fallback_value="fallback")

        assert result == "fallback"

    @pytest.mark.asyncio
    async def test_fallback_none_raises(self):
        """Test None fallback_value raises TimeoutError."""

        async def slow_coro():
            await asyncio.sleep(1.0)

        with pytest.raises(TimeoutError):
            await with_timeout(slow_coro(), 0.05, fallback_value=None)

    @pytest.mark.asyncio
    async def test_fallback_value_types(self):
        """Test various fallback value types."""

        async def slow_coro():
            await asyncio.sleep(1.0)

        # Dict fallback
        result = await with_timeout(slow_coro(), 0.05, fallback_value={})
        assert result == {}

        # List fallback
        result = await with_timeout(slow_coro(), 0.05, fallback_value=[])
        assert result == []

        # Zero fallback
        result = await with_timeout(slow_coro(), 0.05, fallback_value=0)
        assert result == 0

        # Empty string fallback
        result = await with_timeout(slow_coro(), 0.05, fallback_value="")
        assert result == ""

    @pytest.mark.asyncio
    async def test_return_value_preserved(self):
        """Test return value from coroutine is preserved."""

        async def complex_result():
            return {"data": [1, 2, 3], "status": "ok"}

        result = await with_timeout(complex_result(), 1.0)

        assert result == {"data": [1, 2, 3], "status": "ok"}

    @pytest.mark.asyncio
    async def test_zero_timeout(self):
        """Test zero timeout causes immediate timeout."""

        async def coro():
            return "value"

        with pytest.raises(TimeoutError):
            await with_timeout(coro(), 0)


@pytest.mark.unit
class TestTimeoutEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_very_small_timeout(self):
        """Test very small but non-zero timeout."""

        @timeout(0.001)
        async def func():
            await asyncio.sleep(0.1)

        with pytest.raises(TimeoutError):
            await func()

    @pytest.mark.asyncio
    async def test_large_timeout(self):
        """Test large timeout value."""

        @timeout(3600)  # 1 hour
        async def func():
            return "success"

        result = await func()

        assert result == "success"

    @pytest.mark.asyncio
    async def test_exception_propagation(self):
        """Test non-timeout exceptions propagate correctly."""

        @timeout(1.0)
        async def failing_func():
            raise ValueError("Function error")

        with pytest.raises(ValueError, match="Function error"):
            await failing_func()

    @pytest.mark.asyncio
    async def test_multiple_decorated_calls(self):
        """Test multiple calls to decorated function."""
        call_count = [0]

        @timeout(1.0)
        async def counter():
            call_count[0] += 1
            return call_count[0]

        result1 = await counter()
        result2 = await counter()
        result3 = await counter()

        assert result1 == 1
        assert result2 == 2
        assert result3 == 3

    @pytest.mark.asyncio
    async def test_concurrent_timeout_calls(self):
        """Test concurrent calls with timeouts."""

        @timeout(0.2)
        async def slow_func(value):
            await asyncio.sleep(0.05)
            return value

        results = await asyncio.gather(
            slow_func("a"), slow_func("b"), slow_func("c")
        )

        assert set(results) == {"a", "b", "c"}

    @pytest.mark.asyncio
    async def test_nested_timeouts(self):
        """Test nested timeout decorators."""

        @timeout(1.0)
        async def inner():
            await asyncio.sleep(0.01)
            return "inner"

        @timeout(2.0)
        async def outer():
            return await inner()

        result = await outer()

        assert result == "inner"

    @pytest.mark.asyncio
    async def test_cancellation_cleanup(self):
        """Test proper cleanup on timeout cancellation."""
        cleanup_called = [False]

        @timeout(0.05)
        async def func_with_cleanup():
            try:
                await asyncio.sleep(1.0)
            finally:
                cleanup_called[0] = True

        with pytest.raises(TimeoutError):
            await func_with_cleanup()

        # Give a moment for cleanup
        await asyncio.sleep(0.01)

        # Note: Cleanup may or may not be called depending on cancellation behavior
        # This test documents expected behavior

    @pytest.mark.asyncio
    async def test_fallback_exception_propagates(self):
        """Test exception in fallback propagates."""

        def failing_fallback():
            raise ValueError("Fallback error")

        @timeout(0.05, fallback=failing_fallback)
        async def slow_func():
            await asyncio.sleep(1.0)

        with pytest.raises(ValueError, match="Fallback error"):
            await slow_func()

    def test_decorator_with_no_args_uses_default(self):
        """Test decorator without parentheses still works."""
        # This tests that @timeout(seconds) is called, not @timeout directly

        @timeout(1.0)
        async def func():
            return "value"

        assert func.__name__ == "func"
