"""Tests for fallback pattern implementation.

These tests cover:
- Fallback dataclass and chain execution
- @fallback decorator for sync/async functions
- with_fallback helper function
- Error handling and default values
"""

import asyncio

import pytest

from empathy_os.resilience.fallback import Fallback, fallback, with_fallback


@pytest.mark.unit
class TestFallbackDataclass:
    """Test Fallback dataclass."""

    def test_create_fallback_with_name(self):
        """Test creating fallback with name."""
        fb = Fallback(name="test_fallback")

        assert fb.name == "test_fallback"
        assert fb.functions == []
        assert fb.default_value is None

    def test_create_fallback_with_default(self):
        """Test creating fallback with default value."""
        fb = Fallback(name="test", default_value="default_result")

        assert fb.default_value == "default_result"

    def test_add_function_returns_self(self):
        """Test add() returns self for chaining."""
        fb = Fallback(name="test")

        result = fb.add(lambda: "value")

        assert result is fb

    def test_add_multiple_functions(self):
        """Test adding multiple functions."""
        fb = Fallback(name="test")

        fb.add(lambda: "first").add(lambda: "second").add(lambda: "third")

        assert len(fb.functions) == 3

    @pytest.mark.asyncio
    async def test_execute_first_function_succeeds(self):
        """Test execute uses first successful function."""
        fb = Fallback(name="test")
        fb.add(lambda: "first_value")
        fb.add(lambda: "second_value")

        result = await fb.execute()

        assert result == "first_value"

    @pytest.mark.asyncio
    async def test_execute_falls_back_on_failure(self):
        """Test execute falls back when first function fails."""
        fb = Fallback(name="test")

        def fail_func():
            raise ValueError("Failed")

        fb.add(fail_func)
        fb.add(lambda: "fallback_value")

        result = await fb.execute()

        assert result == "fallback_value"

    @pytest.mark.asyncio
    async def test_execute_multiple_failures_uses_last_working(self):
        """Test execute continues until success."""
        fb = Fallback(name="test")

        fb.add(lambda: (_ for _ in ()).throw(ValueError("fail 1")))
        fb.add(lambda: (_ for _ in ()).throw(ValueError("fail 2")))
        fb.add(lambda: "success")

        # Need different approach since lambdas can't raise directly
        call_count = [0]

        def fail1():
            call_count[0] += 1
            raise ValueError("fail 1")

        def fail2():
            call_count[0] += 1
            raise ValueError("fail 2")

        def succeed():
            call_count[0] += 1
            return "success"

        fb2 = Fallback(name="test")
        fb2.add(fail1).add(fail2).add(succeed)

        result = await fb2.execute()

        assert result == "success"
        assert call_count[0] == 3

    @pytest.mark.asyncio
    async def test_execute_uses_default_when_all_fail(self):
        """Test execute returns default when all functions fail."""
        fb = Fallback(name="test", default_value="default")

        def fail():
            raise ValueError("Failed")

        fb.add(fail)

        result = await fb.execute()

        assert result == "default"

    @pytest.mark.asyncio
    async def test_execute_raises_last_exception_no_default(self):
        """Test execute raises last exception when no default."""
        fb = Fallback(name="test")

        def fail():
            raise ValueError("Final error")

        fb.add(fail)

        with pytest.raises(ValueError, match="Final error"):
            await fb.execute()

    @pytest.mark.asyncio
    async def test_execute_with_no_functions_raises(self):
        """Test execute raises when no functions added."""
        fb = Fallback(name="empty")

        with pytest.raises(RuntimeError, match="no functions to execute"):
            await fb.execute()

    @pytest.mark.asyncio
    async def test_execute_async_function(self):
        """Test execute handles async functions."""
        fb = Fallback(name="test")

        async def async_func():
            await asyncio.sleep(0.01)
            return "async_result"

        fb.add(async_func)

        result = await fb.execute()

        assert result == "async_result"

    @pytest.mark.asyncio
    async def test_execute_mixed_sync_async(self):
        """Test execute handles mix of sync and async functions."""
        fb = Fallback(name="test")

        async def async_fail():
            raise ValueError("async failed")

        def sync_succeed():
            return "sync_result"

        fb.add(async_fail).add(sync_succeed)

        result = await fb.execute()

        assert result == "sync_result"

    @pytest.mark.asyncio
    async def test_execute_passes_arguments(self):
        """Test execute passes args and kwargs to functions."""
        fb = Fallback(name="test")

        def func_with_args(x, y, z=None):
            return f"{x}-{y}-{z}"

        fb.add(func_with_args)

        result = await fb.execute("a", "b", z="c")

        assert result == "a-b-c"


@pytest.mark.unit
class TestFallbackDecorator:
    """Test @fallback decorator."""

    def test_decorator_preserves_function_name(self):
        """Test decorator preserves function metadata."""

        @fallback(default="default")
        def my_function():
            return "value"

        assert my_function.__name__ == "my_function"

    def test_sync_function_returns_value(self):
        """Test decorated sync function returns value."""

        @fallback(default="default")
        def get_value():
            return "primary_value"

        result = get_value()

        assert result == "primary_value"

    def test_sync_function_uses_fallback(self):
        """Test decorated sync function uses fallback on failure."""

        def fallback_func():
            return "fallback_value"

        @fallback(fallback_func)
        def failing_func():
            raise ValueError("Failed")

        result = failing_func()

        assert result == "fallback_value"

    def test_sync_function_uses_default(self):
        """Test decorated sync function uses default when all fail."""

        def also_fails():
            raise ValueError("Also failed")

        @fallback(also_fails, default="default_value")
        def failing_func():
            raise ValueError("Failed")

        result = failing_func()

        assert result == "default_value"

    def test_sync_function_raises_when_no_default(self):
        """Test decorated sync function raises when all fail and no default."""

        def also_fails():
            raise ValueError("Fallback failed")

        @fallback(also_fails)
        def failing_func():
            raise ValueError("Primary failed")

        with pytest.raises(RuntimeError, match="All fallbacks failed"):
            failing_func()

    @pytest.mark.asyncio
    async def test_async_function_returns_value(self):
        """Test decorated async function returns value."""

        @fallback(default="default")
        async def get_value():
            return "primary_value"

        result = await get_value()

        assert result == "primary_value"

    @pytest.mark.asyncio
    async def test_async_function_uses_fallback(self):
        """Test decorated async function uses fallback on failure."""

        def fallback_func():
            return "fallback_value"

        @fallback(fallback_func)
        async def failing_func():
            raise ValueError("Failed")

        result = await failing_func()

        assert result == "fallback_value"

    @pytest.mark.asyncio
    async def test_async_function_with_async_fallback(self):
        """Test decorated async function with async fallback."""

        async def async_fallback():
            await asyncio.sleep(0.01)
            return "async_fallback_value"

        @fallback(async_fallback)
        async def failing_func():
            raise ValueError("Failed")

        result = await failing_func()

        assert result == "async_fallback_value"

    @pytest.mark.asyncio
    async def test_async_function_uses_default(self):
        """Test decorated async function uses default when all fail."""

        async def also_fails():
            raise ValueError("Fallback failed")

        @fallback(also_fails, default="default_value")
        async def failing_func():
            raise ValueError("Primary failed")

        result = await failing_func()

        assert result == "default_value"

    @pytest.mark.asyncio
    async def test_async_function_raises_when_no_default(self):
        """Test decorated async function raises when all fail and no default."""

        def also_fails():
            raise ValueError("Fallback failed")

        @fallback(also_fails)
        async def failing_func():
            raise ValueError("Primary failed")

        with pytest.raises(RuntimeError, match="All fallbacks failed"):
            await failing_func()

    def test_multiple_fallbacks(self):
        """Test decorator with multiple fallback functions."""

        def fallback1():
            raise ValueError("Fallback 1 failed")

        def fallback2():
            raise ValueError("Fallback 2 failed")

        def fallback3():
            return "fallback3_value"

        @fallback(fallback1, fallback2, fallback3)
        def failing_func():
            raise ValueError("Primary failed")

        result = failing_func()

        assert result == "fallback3_value"

    def test_log_failures_true_by_default(self, caplog):
        """Test decorator logs failures by default."""
        import logging

        caplog.set_level(logging.WARNING)

        def fallback_func():
            return "fallback"

        @fallback(fallback_func, log_failures=True)
        def failing_func():
            raise ValueError("Primary error")

        failing_func()

        assert "Primary function failing_func failed" in caplog.text

    def test_log_failures_false(self, caplog):
        """Test decorator doesn't log when log_failures=False."""
        import logging

        caplog.set_level(logging.WARNING)

        def fallback_func():
            return "fallback"

        @fallback(fallback_func, log_failures=False)
        def failing_func():
            raise ValueError("Primary error")

        failing_func()

        assert "Primary function failing_func failed" not in caplog.text

    def test_passes_arguments(self):
        """Test decorated function passes arguments."""

        def fallback_func(x, y):
            return f"fallback-{x}-{y}"

        @fallback(fallback_func)
        def func(x, y):
            raise ValueError("Failed")

        result = func("a", "b")

        assert result == "fallback-a-b"


@pytest.mark.unit
class TestWithFallback:
    """Test with_fallback helper function."""

    @pytest.mark.asyncio
    async def test_with_fallback_primary_succeeds(self):
        """Test with_fallback uses primary when it succeeds."""

        def primary():
            return "primary_value"

        wrapped = with_fallback(primary, [])

        result = await wrapped()

        assert result == "primary_value"

    @pytest.mark.asyncio
    async def test_with_fallback_uses_fallback(self):
        """Test with_fallback uses fallback when primary fails."""

        def primary():
            raise ValueError("Failed")

        def fallback_func():
            return "fallback_value"

        wrapped = with_fallback(primary, [fallback_func])

        result = await wrapped()

        assert result == "fallback_value"

    @pytest.mark.asyncio
    async def test_with_fallback_multiple_fallbacks(self):
        """Test with_fallback with multiple fallbacks."""

        def primary():
            raise ValueError("Primary failed")

        def fallback1():
            raise ValueError("Fallback 1 failed")

        def fallback2():
            return "fallback2_value"

        wrapped = with_fallback(primary, [fallback1, fallback2])

        result = await wrapped()

        assert result == "fallback2_value"

    @pytest.mark.asyncio
    async def test_with_fallback_uses_default(self):
        """Test with_fallback uses default when all fail."""

        def primary():
            raise ValueError("Failed")

        def fallback_func():
            raise ValueError("Fallback failed")

        wrapped = with_fallback(primary, [fallback_func], default="default_value")

        result = await wrapped()

        assert result == "default_value"

    @pytest.mark.asyncio
    async def test_with_fallback_raises_when_no_default(self):
        """Test with_fallback raises when all fail and no default."""

        def primary():
            raise ValueError("Primary failed")

        def fallback_func():
            raise ValueError("Fallback failed")

        wrapped = with_fallback(primary, [fallback_func])

        with pytest.raises(ValueError, match="Fallback failed"):
            await wrapped()

    @pytest.mark.asyncio
    async def test_with_fallback_passes_arguments(self):
        """Test with_fallback passes arguments to functions."""

        def primary(x, y, z=None):
            raise ValueError("Failed")

        def fallback_func(x, y, z=None):
            return f"{x}-{y}-{z}"

        wrapped = with_fallback(primary, [fallback_func])

        result = await wrapped("a", "b", z="c")

        assert result == "a-b-c"

    @pytest.mark.asyncio
    async def test_with_fallback_async_primary(self):
        """Test with_fallback with async primary function."""

        async def primary():
            await asyncio.sleep(0.01)
            return "async_primary"

        wrapped = with_fallback(primary, [])

        result = await wrapped()

        assert result == "async_primary"

    @pytest.mark.asyncio
    async def test_with_fallback_async_fallback(self):
        """Test with_fallback with async fallback function."""

        def primary():
            raise ValueError("Failed")

        async def fallback_func():
            await asyncio.sleep(0.01)
            return "async_fallback"

        wrapped = with_fallback(primary, [fallback_func])

        result = await wrapped()

        assert result == "async_fallback"


@pytest.mark.unit
class TestFallbackEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_none_default_value(self):
        """Test None default value doesn't trigger fallback."""
        # Note: None default_value means no default, not default=None
        fb = Fallback(name="test", default_value=None)

        def fail():
            raise ValueError("Failed")

        fb.add(fail)

        with pytest.raises(ValueError):
            await fb.execute()

    @pytest.mark.asyncio
    async def test_empty_fallbacks_list(self):
        """Test with_fallback with empty fallbacks list."""

        def primary():
            return "primary"

        wrapped = with_fallback(primary, [])

        result = await wrapped()

        assert result == "primary"

    def test_decorated_function_preserves_docstring(self):
        """Test decorator preserves function docstring."""

        @fallback(default=None)
        def documented_func():
            """This is the docstring."""
            return "value"

        assert documented_func.__doc__ == "This is the docstring."

    @pytest.mark.asyncio
    async def test_fallback_chain_order_preserved(self):
        """Test functions are called in order added."""
        call_order = []

        def func1():
            call_order.append(1)
            raise ValueError("1")

        def func2():
            call_order.append(2)
            raise ValueError("2")

        def func3():
            call_order.append(3)
            return "success"

        fb = Fallback(name="test")
        fb.add(func1).add(func2).add(func3)

        await fb.execute()

        assert call_order == [1, 2, 3]

    def test_fallback_with_zero_default(self):
        """Test fallback with 0 as default (falsy but valid)."""

        def fail():
            raise ValueError("Failed")

        @fallback(fail, default=0)
        def get_value():
            raise ValueError("Primary failed")

        result = get_value()

        # 0 is falsy but should still be returned as valid default
        # Note: Current implementation uses `if default is not None`
        # so 0 should be returned
        assert result == 0

    def test_fallback_with_empty_string_default(self):
        """Test fallback with empty string as default."""

        def fail():
            raise ValueError("Failed")

        @fallback(fail, default="")
        def get_value():
            raise ValueError("Primary failed")

        result = get_value()

        assert result == ""
