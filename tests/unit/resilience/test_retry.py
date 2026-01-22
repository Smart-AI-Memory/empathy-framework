"""Tests for retry resilience pattern.

These tests cover:
- RetryConfig dataclass
- Exponential backoff calculation
- Jitter behavior
- Retry decorator (sync and async)
- Retryable exception filtering
- on_retry callback
"""


import pytest

from empathy_os.resilience.retry import RetryConfig, retry, retry_with_backoff


@pytest.mark.unit
class TestRetryConfig:
    """Test RetryConfig dataclass."""

    def test_default_values(self):
        """Test RetryConfig default values."""
        config = RetryConfig()

        assert config.max_attempts == 3
        assert config.backoff_factor == 2.0
        assert config.initial_delay == 1.0
        assert config.max_delay == 60.0
        assert config.jitter is True

    def test_custom_values(self):
        """Test RetryConfig with custom values."""
        config = RetryConfig(
            max_attempts=5,
            backoff_factor=3.0,
            initial_delay=0.5,
            max_delay=30.0,
            jitter=False,
        )

        assert config.max_attempts == 5
        assert config.backoff_factor == 3.0
        assert config.initial_delay == 0.5
        assert config.max_delay == 30.0
        assert config.jitter is False


@pytest.mark.unit
class TestRetryConfigDelay:
    """Test delay calculation."""

    def test_get_delay_first_attempt(self):
        """Test delay for first attempt is initial_delay."""
        config = RetryConfig(initial_delay=1.0, jitter=False)

        delay = config.get_delay(attempt=1)

        assert delay == 1.0

    def test_get_delay_exponential_growth(self):
        """Test delay grows exponentially."""
        config = RetryConfig(
            initial_delay=1.0, backoff_factor=2.0, jitter=False, max_delay=100
        )

        assert config.get_delay(1) == 1.0  # 1 * 2^0
        assert config.get_delay(2) == 2.0  # 1 * 2^1
        assert config.get_delay(3) == 4.0  # 1 * 2^2
        assert config.get_delay(4) == 8.0  # 1 * 2^3

    def test_get_delay_capped_at_max(self):
        """Test delay is capped at max_delay."""
        config = RetryConfig(
            initial_delay=1.0, backoff_factor=10.0, max_delay=5.0, jitter=False
        )

        delay = config.get_delay(10)  # Would be huge without cap

        assert delay == 5.0

    def test_get_delay_with_jitter(self):
        """Test delay with jitter has variation."""
        config = RetryConfig(initial_delay=1.0, jitter=True)

        delays = [config.get_delay(1) for _ in range(10)]

        # Should have some variation
        assert len(set(delays)) > 1
        # Should be within jitter range (0.75x to 1.25x)
        for d in delays:
            assert 0.75 <= d <= 1.25


@pytest.mark.unit
class TestRetryDecorator:
    """Test retry decorator."""

    def test_succeeds_on_first_attempt(self):
        """Test function succeeds without retries."""
        call_count = 0

        @retry(max_attempts=3)
        def always_succeeds():
            nonlocal call_count
            call_count += 1
            return "success"

        result = always_succeeds()

        assert result == "success"
        assert call_count == 1

    def test_succeeds_after_transient_failures(self):
        """Test function succeeds after transient failures."""
        call_count = 0

        @retry(max_attempts=5, initial_delay=0.01)
        def fails_twice():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("transient error")
            return "success"

        result = fails_twice()

        assert result == "success"
        assert call_count == 3

    def test_raises_after_max_attempts(self):
        """Test raises exception after max attempts exhausted."""
        call_count = 0

        @retry(max_attempts=3, initial_delay=0.01)
        def always_fails():
            nonlocal call_count
            call_count += 1
            raise ValueError("always fails")

        with pytest.raises(ValueError, match="always fails"):
            always_fails()

        assert call_count == 3

    def test_retryable_exceptions_filter(self):
        """Test only retryable exceptions are retried."""
        call_count = 0

        @retry(max_attempts=3, retryable_exceptions=(ValueError,), initial_delay=0.01)
        def raises_type_error():
            nonlocal call_count
            call_count += 1
            raise TypeError("not retryable")

        with pytest.raises(TypeError):
            raises_type_error()

        # Should not retry TypeError
        assert call_count == 1

    def test_on_retry_callback_called(self):
        """Test on_retry callback is called on each retry."""
        retry_events = []

        def on_retry_handler(exception, attempt):
            retry_events.append((str(exception), attempt))

        call_count = 0

        @retry(max_attempts=3, initial_delay=0.01, on_retry=on_retry_handler)
        def fails_twice():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError(f"attempt {call_count}")
            return "success"

        fails_twice()

        assert len(retry_events) == 2
        assert "attempt 1" in retry_events[0][0]
        assert retry_events[0][1] == 1


@pytest.mark.unit
class TestRetryDecoratorAsync:
    """Test retry decorator with async functions."""

    @pytest.mark.asyncio
    async def test_async_succeeds_on_first_attempt(self):
        """Test async function succeeds without retries."""
        call_count = 0

        @retry(max_attempts=3)
        async def async_success():
            nonlocal call_count
            call_count += 1
            return "async success"

        result = await async_success()

        assert result == "async success"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_async_succeeds_after_failures(self):
        """Test async function succeeds after transient failures."""
        call_count = 0

        @retry(max_attempts=5, initial_delay=0.01)
        async def async_fails_twice():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("transient")
            return "success"

        result = await async_fails_twice()

        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_async_raises_after_max_attempts(self):
        """Test async raises exception after max attempts."""
        call_count = 0

        @retry(max_attempts=3, initial_delay=0.01)
        async def async_always_fails():
            nonlocal call_count
            call_count += 1
            raise ValueError("always fails")

        with pytest.raises(ValueError):
            await async_always_fails()

        assert call_count == 3


@pytest.mark.unit
class TestRetryWithBackoff:
    """Test retry_with_backoff function."""

    @pytest.mark.asyncio
    async def test_retry_with_backoff_success(self):
        """Test retry_with_backoff with successful function."""
        call_count = 0

        async def my_func():
            nonlocal call_count
            call_count += 1
            return "result"

        config = RetryConfig(max_attempts=3)
        result = await retry_with_backoff(my_func, config=config)

        assert result == "result"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_retry_with_backoff_transient_failure(self):
        """Test retry_with_backoff retries on failure."""
        call_count = 0

        async def my_func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("fail")
            return "success"

        config = RetryConfig(max_attempts=3, initial_delay=0.01)
        result = await retry_with_backoff(my_func, config=config)

        assert result == "success"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_retry_with_backoff_sync_function(self):
        """Test retry_with_backoff works with sync functions."""
        call_count = 0

        def sync_func():
            nonlocal call_count
            call_count += 1
            return "sync result"

        config = RetryConfig(max_attempts=3)
        result = await retry_with_backoff(sync_func, config=config)

        assert result == "sync result"
        assert call_count == 1
