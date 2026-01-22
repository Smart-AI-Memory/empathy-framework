"""Tests for CircuitBreaker resilience pattern.

These tests cover:
- State transitions (CLOSED -> OPEN -> HALF_OPEN -> CLOSED)
- Failure threshold triggering
- Reset timeout behavior
- Recovery in HALF_OPEN state
- Decorator usage
- Global registry
"""

import time

import pytest

from empathy_os.resilience.circuit_breaker import (
    CircuitBreaker,
    CircuitOpenError,
    CircuitState,
    circuit_breaker,
    get_circuit_breaker,
)


@pytest.mark.unit
class TestCircuitBreakerStates:
    """Test circuit breaker state transitions."""

    def test_initial_state_is_closed(self):
        """Test circuit breaker starts in CLOSED state."""
        cb = CircuitBreaker(name="test")

        assert cb.state == CircuitState.CLOSED
        assert cb.is_closed is True
        assert cb.is_open is False

    def test_opens_after_failure_threshold(self):
        """Test circuit opens after failure threshold exceeded."""
        cb = CircuitBreaker(name="test_threshold", failure_threshold=3)

        for _ in range(3):
            cb.record_failure(Exception("test"))

        assert cb.state == CircuitState.OPEN
        assert cb.is_open is True

    def test_stays_closed_below_threshold(self):
        """Test circuit stays closed below failure threshold."""
        cb = CircuitBreaker(name="test_below", failure_threshold=5)

        for _ in range(4):
            cb.record_failure(Exception("test"))

        assert cb.state == CircuitState.CLOSED

    def test_success_resets_failure_count(self):
        """Test success in CLOSED state resets failure count."""
        cb = CircuitBreaker(name="test_reset", failure_threshold=3)

        cb.record_failure(Exception("test"))
        cb.record_failure(Exception("test"))
        cb.record_success()  # Reset
        cb.record_failure(Exception("test"))

        # Should still be closed (only 1 failure since reset)
        assert cb.state == CircuitState.CLOSED

    def test_transitions_to_half_open_after_timeout(self):
        """Test circuit transitions to HALF_OPEN after timeout."""
        cb = CircuitBreaker(name="test_halfopen", failure_threshold=1, reset_timeout=0.1)

        cb.record_failure(Exception("test"))
        assert cb.state == CircuitState.OPEN

        time.sleep(0.15)

        # Accessing state triggers transition check
        assert cb.state == CircuitState.HALF_OPEN

    def test_closes_after_successful_half_open_calls(self):
        """Test circuit closes after successful calls in HALF_OPEN."""
        cb = CircuitBreaker(
            name="test_recovery",
            failure_threshold=1,
            reset_timeout=0.1,
            half_open_max_calls=2,
        )

        # Open the circuit
        cb.record_failure(Exception("test"))
        time.sleep(0.15)

        # Should be HALF_OPEN now
        assert cb.state == CircuitState.HALF_OPEN

        # Successful calls in HALF_OPEN
        cb.record_success()
        cb.record_success()

        assert cb.state == CircuitState.CLOSED

    def test_reopens_on_failure_in_half_open(self):
        """Test circuit reopens on failure in HALF_OPEN state."""
        cb = CircuitBreaker(
            name="test_reopen", failure_threshold=1, reset_timeout=0.1
        )

        # Open the circuit
        cb.record_failure(Exception("test"))
        time.sleep(0.15)

        # Should be HALF_OPEN
        assert cb.state == CircuitState.HALF_OPEN

        # Failure in HALF_OPEN reopens
        cb.record_failure(Exception("test"))

        assert cb.state == CircuitState.OPEN


@pytest.mark.unit
class TestCircuitBreakerExcludedExceptions:
    """Test excluded exceptions behavior."""

    def test_excluded_exception_does_not_count(self):
        """Test excluded exceptions don't increment failure count."""
        cb = CircuitBreaker(
            name="test_excluded",
            failure_threshold=2,
            excluded_exceptions=(ValueError,),
        )

        # ValueError is excluded
        cb.record_failure(ValueError("excluded"))
        cb.record_failure(ValueError("excluded"))
        cb.record_failure(ValueError("excluded"))

        # Should still be closed
        assert cb.state == CircuitState.CLOSED

    def test_non_excluded_exception_counts(self):
        """Test non-excluded exceptions increment failure count."""
        cb = CircuitBreaker(
            name="test_included",
            failure_threshold=2,
            excluded_exceptions=(ValueError,),
        )

        cb.record_failure(TypeError("included"))
        cb.record_failure(TypeError("included"))

        assert cb.state == CircuitState.OPEN


@pytest.mark.unit
class TestCircuitBreakerTimingMethods:
    """Test timing-related methods."""

    def test_get_time_until_reset_when_open(self):
        """Test get_time_until_reset returns positive value when OPEN."""
        cb = CircuitBreaker(name="test_time", failure_threshold=1, reset_timeout=60)

        cb.record_failure(Exception("test"))

        remaining = cb.get_time_until_reset()

        assert remaining > 0
        assert remaining <= 60

    def test_get_time_until_reset_when_closed(self):
        """Test get_time_until_reset returns 0 when CLOSED."""
        cb = CircuitBreaker(name="test_time_closed", failure_threshold=1)

        remaining = cb.get_time_until_reset()

        assert remaining == 0

    def test_manual_reset(self):
        """Test manual reset returns to CLOSED state."""
        cb = CircuitBreaker(name="test_manual_reset", failure_threshold=1)

        cb.record_failure(Exception("test"))
        assert cb.state == CircuitState.OPEN

        cb.reset()

        assert cb.state == CircuitState.CLOSED


@pytest.mark.unit
class TestCircuitBreakerStats:
    """Test statistics methods."""

    def test_get_stats_returns_dict(self):
        """Test get_stats returns statistics dictionary."""
        cb = CircuitBreaker(name="test_stats", failure_threshold=5)

        cb.record_failure(Exception("test"))
        cb.record_failure(Exception("test"))
        cb.record_success()

        stats = cb.get_stats()

        assert "state" in stats
        assert "failure_count" in stats
        assert "success_count" in stats
        assert stats["state"] == "closed"


@pytest.mark.unit
class TestCircuitBreakerDecorator:
    """Test circuit_breaker decorator."""

    def test_decorator_wraps_sync_function(self):
        """Test decorator works with sync functions."""
        call_count = 0

        @circuit_breaker(name="test_sync_dec", failure_threshold=3)
        def my_func():
            nonlocal call_count
            call_count += 1
            return "success"

        result = my_func()

        assert result == "success"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_decorator_wraps_async_function(self):
        """Test decorator works with async functions."""
        call_count = 0

        @circuit_breaker(name="test_async_dec", failure_threshold=3)
        async def my_async_func():
            nonlocal call_count
            call_count += 1
            return "async success"

        result = await my_async_func()

        assert result == "async success"
        assert call_count == 1

    def test_decorator_raises_circuit_open_error(self):
        """Test decorator raises CircuitOpenError when open."""
        @circuit_breaker(name="test_open_dec", failure_threshold=1, reset_timeout=60)
        def failing_func():
            raise ValueError("always fails")

        # Trigger circuit open
        with pytest.raises(ValueError):
            failing_func()

        # Next call should raise CircuitOpenError
        with pytest.raises(CircuitOpenError):
            failing_func()

    def test_decorator_with_fallback(self):
        """Test decorator calls fallback when circuit open."""
        def fallback_func():
            return "fallback result"

        @circuit_breaker(
            name="test_fallback_dec",
            failure_threshold=1,
            reset_timeout=60,
            fallback=fallback_func,
        )
        def failing_func():
            raise ValueError("always fails")

        # Trigger circuit open
        with pytest.raises(ValueError):
            failing_func()

        # Next call should use fallback
        result = failing_func()

        assert result == "fallback result"


@pytest.mark.unit
class TestCircuitBreakerRegistry:
    """Test global circuit breaker registry."""

    def test_get_circuit_breaker_returns_same_instance(self):
        """Test get_circuit_breaker returns same instance by name."""
        # Create circuit breaker via decorator
        @circuit_breaker(name="registry_test", failure_threshold=5)
        def test_func():
            return "test"

        test_func()

        # Get from registry
        cb = get_circuit_breaker("registry_test")

        assert cb is not None
        assert cb.name == "registry_test"

    def test_get_nonexistent_returns_none(self):
        """Test get_circuit_breaker returns None for unknown name."""
        cb = get_circuit_breaker("nonexistent_circuit")

        assert cb is None


@pytest.mark.unit
class TestCircuitOpenError:
    """Test CircuitOpenError exception."""

    def test_error_contains_name_and_reset_time(self):
        """Test error contains circuit name and reset time."""
        error = CircuitOpenError("test_circuit", 30.5)

        assert "test_circuit" in str(error)
        assert error.name == "test_circuit"
        assert error.reset_time == 30.5
