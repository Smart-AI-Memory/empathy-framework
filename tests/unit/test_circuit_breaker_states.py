"""Comprehensive Circuit Breaker State Transition Tests.

Tests for all state transitions and edge cases:
- CLOSED -> OPEN (failure threshold exceeded)
- OPEN -> HALF_OPEN (timeout elapsed)
- HALF_OPEN -> CLOSED (successful recovery)
- HALF_OPEN -> OPEN (failure during recovery)

Copyright 2026 Smart-AI-Memory
Licensed under Fair Source License 0.9
"""

import sys
import time
from pathlib import Path
from unittest.mock import patch

import pytest

# Add src to path
src_path = Path(__file__).parent.parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from empathy_os.resilience.circuit_breaker import (
    CircuitBreaker,
    CircuitOpenError,
    CircuitState,
    circuit_breaker,
    get_circuit_breaker,
)


# =============================================================================
# State Transition Tests
# =============================================================================


class TestClosedToOpen:
    """Test CLOSED -> OPEN state transition."""

    def test_transition_at_exact_threshold(self):
        """Test circuit opens at exactly failure_threshold failures."""
        cb = CircuitBreaker(name="test_exact", failure_threshold=5)

        # Record exactly threshold - 1 failures (should stay CLOSED)
        for i in range(4):
            cb.record_failure(ValueError(f"error {i}"))
            assert cb.state == CircuitState.CLOSED, f"Should be CLOSED after {i+1} failures"

        # The threshold-th failure should open
        cb.record_failure(ValueError("final error"))
        assert cb.state == CircuitState.OPEN

    def test_no_transition_below_threshold(self):
        """Test circuit stays closed below threshold."""
        cb = CircuitBreaker(name="test_below", failure_threshold=10)

        for i in range(9):
            cb.record_failure(ValueError(f"error {i}"))

        assert cb.state == CircuitState.CLOSED
        assert cb._failure_count == 9

    def test_multiple_failures_past_threshold(self):
        """Test that failures continue to be recorded after opening."""
        cb = CircuitBreaker(name="test_past", failure_threshold=3)

        # Open the circuit
        for _ in range(3):
            cb.record_failure(ValueError("error"))
        assert cb.state == CircuitState.OPEN

        # Additional failures still recorded
        cb.record_failure(ValueError("another error"))
        assert cb._failure_count == 4

    def test_success_resets_failure_count(self):
        """Test that success resets failure count in CLOSED state."""
        cb = CircuitBreaker(name="test_reset", failure_threshold=5)

        # Record some failures
        cb.record_failure(ValueError("error 1"))
        cb.record_failure(ValueError("error 2"))
        cb.record_failure(ValueError("error 3"))
        assert cb._failure_count == 3

        # Success should reset
        cb.record_success()
        assert cb._failure_count == 0
        assert cb.state == CircuitState.CLOSED

        # Now need full threshold again
        for _ in range(4):
            cb.record_failure(ValueError("error"))
        assert cb.state == CircuitState.CLOSED  # Still closed, only 4 failures


class TestOpenToHalfOpen:
    """Test OPEN -> HALF_OPEN state transition."""

    def test_transition_after_timeout(self):
        """Test circuit transitions to HALF_OPEN after reset_timeout."""
        cb = CircuitBreaker(name="test_timeout", failure_threshold=2, reset_timeout=0.05)

        # Open the circuit
        cb.record_failure(ValueError("error 1"))
        cb.record_failure(ValueError("error 2"))
        assert cb.state == CircuitState.OPEN

        # Wait for timeout
        time.sleep(0.06)

        # Accessing state should trigger transition
        assert cb.state == CircuitState.HALF_OPEN

    def test_no_transition_before_timeout(self):
        """Test circuit stays OPEN before timeout."""
        cb = CircuitBreaker(name="test_no_timeout", failure_threshold=2, reset_timeout=1.0)

        cb.record_failure(ValueError("error 1"))
        cb.record_failure(ValueError("error 2"))
        assert cb.state == CircuitState.OPEN

        # Don't wait, check immediately
        assert cb.state == CircuitState.OPEN

    def test_half_open_resets_counters(self):
        """Test that transitioning to HALF_OPEN resets appropriate counters."""
        cb = CircuitBreaker(name="test_counters", failure_threshold=2, reset_timeout=0.01)

        cb.record_failure(ValueError("error 1"))
        cb.record_failure(ValueError("error 2"))
        assert cb._half_open_calls == 0

        time.sleep(0.02)
        _ = cb.state  # Trigger transition

        assert cb._half_open_calls == 0
        assert cb._success_count == 0


class TestHalfOpenToClosed:
    """Test HALF_OPEN -> CLOSED state transition."""

    def test_transition_after_successful_recovery(self):
        """Test circuit closes after half_open_max_calls successes."""
        cb = CircuitBreaker(
            name="test_recovery",
            failure_threshold=2,
            reset_timeout=0.01,
            half_open_max_calls=3,
        )

        # Open and transition to half-open
        cb.record_failure(ValueError("error 1"))
        cb.record_failure(ValueError("error 2"))
        time.sleep(0.02)
        assert cb.state == CircuitState.HALF_OPEN

        # Record successful calls
        cb.record_success()
        assert cb.state == CircuitState.HALF_OPEN  # Not yet recovered
        cb.record_success()
        assert cb.state == CircuitState.HALF_OPEN  # Not yet recovered
        cb.record_success()

        # Now should be closed
        assert cb.state == CircuitState.CLOSED

    def test_partial_success_not_enough(self):
        """Test that fewer than half_open_max_calls successes don't close."""
        cb = CircuitBreaker(
            name="test_partial",
            failure_threshold=2,
            reset_timeout=0.01,
            half_open_max_calls=5,
        )

        # Open and transition to half-open
        cb.record_failure(ValueError("error"))
        cb.record_failure(ValueError("error"))
        time.sleep(0.02)
        assert cb.state == CircuitState.HALF_OPEN

        # Record some successes, but not enough
        for _ in range(4):
            cb.record_success()

        assert cb.state == CircuitState.HALF_OPEN
        assert cb._success_count == 4

    def test_closed_resets_all_counters(self):
        """Test that closing resets all tracking counters."""
        cb = CircuitBreaker(
            name="test_close_reset",
            failure_threshold=2,
            reset_timeout=0.01,
            half_open_max_calls=2,
        )

        # Open and close
        cb.record_failure(ValueError("error"))
        cb.record_failure(ValueError("error"))
        time.sleep(0.02)
        cb.record_success()
        cb.record_success()

        assert cb.state == CircuitState.CLOSED
        assert cb._failure_count == 0
        assert cb._success_count == 0
        assert cb._half_open_calls == 0


class TestHalfOpenToOpen:
    """Test HALF_OPEN -> OPEN state transition."""

    def test_transition_on_any_failure(self):
        """Test that any failure in HALF_OPEN reopens circuit."""
        cb = CircuitBreaker(
            name="test_reopen",
            failure_threshold=5,
            reset_timeout=0.01,
            half_open_max_calls=3,
        )

        # Open and transition to half-open
        for _ in range(5):
            cb.record_failure(ValueError("error"))
        time.sleep(0.02)
        assert cb.state == CircuitState.HALF_OPEN

        # Record a success, then a failure
        cb.record_success()
        cb.record_failure(ValueError("recovery failure"))

        # Should be back to OPEN
        assert cb.state == CircuitState.OPEN

    def test_immediate_failure_reopens(self):
        """Test that first call failure in HALF_OPEN reopens."""
        cb = CircuitBreaker(
            name="test_immediate",
            failure_threshold=2,
            reset_timeout=0.01,
            half_open_max_calls=5,
        )

        cb.record_failure(ValueError("error"))
        cb.record_failure(ValueError("error"))
        time.sleep(0.02)
        assert cb.state == CircuitState.HALF_OPEN

        # Immediate failure
        cb.record_failure(ValueError("immediate failure"))
        assert cb.state == CircuitState.OPEN


# =============================================================================
# Excluded Exceptions Tests
# =============================================================================


class TestExcludedExceptions:
    """Test excluded exception handling."""

    def test_excluded_exception_not_counted(self):
        """Test that excluded exceptions don't count as failures."""
        cb = CircuitBreaker(
            name="test_excluded",
            failure_threshold=3,
            excluded_exceptions=(ValueError,),
        )

        # Record excluded exceptions (shouldn't count)
        cb.record_failure(ValueError("excluded"))
        cb.record_failure(ValueError("also excluded"))
        cb.record_failure(ValueError("still excluded"))

        # Should still be closed
        assert cb.state == CircuitState.CLOSED
        assert cb._failure_count == 0

    def test_non_excluded_exception_counted(self):
        """Test that non-excluded exceptions count normally."""
        cb = CircuitBreaker(
            name="test_non_excluded",
            failure_threshold=3,
            excluded_exceptions=(ValueError,),
        )

        # Record non-excluded exceptions
        cb.record_failure(RuntimeError("counted"))
        cb.record_failure(RuntimeError("also counted"))
        cb.record_failure(RuntimeError("opens circuit"))

        assert cb.state == CircuitState.OPEN
        assert cb._failure_count == 3

    def test_mixed_exceptions(self):
        """Test mix of excluded and non-excluded exceptions."""
        cb = CircuitBreaker(
            name="test_mixed",
            failure_threshold=3,
            excluded_exceptions=(ValueError, TypeError),
        )

        # Mix of exceptions
        cb.record_failure(ValueError("excluded"))
        cb.record_failure(RuntimeError("counted: 1"))
        cb.record_failure(TypeError("excluded"))
        cb.record_failure(RuntimeError("counted: 2"))
        cb.record_failure(ValueError("excluded"))
        cb.record_failure(RuntimeError("counted: 3 - opens"))

        assert cb.state == CircuitState.OPEN
        assert cb._failure_count == 3  # Only RuntimeErrors counted

    def test_excluded_subclass(self):
        """Test that subclasses of excluded exceptions are also excluded."""

        class CustomValueError(ValueError):
            pass

        cb = CircuitBreaker(
            name="test_subclass",
            failure_threshold=3,
            excluded_exceptions=(ValueError,),
        )

        # Subclass should also be excluded
        cb.record_failure(CustomValueError("subclass"))
        cb.record_failure(CustomValueError("also subclass"))
        cb.record_failure(CustomValueError("still subclass"))

        assert cb.state == CircuitState.CLOSED


# =============================================================================
# Time Tracking Tests
# =============================================================================


class TestTimeTracking:
    """Test time-related functionality."""

    def test_get_time_until_reset(self):
        """Test time until reset calculation."""
        cb = CircuitBreaker(name="test_time", failure_threshold=2, reset_timeout=1.0)

        cb.record_failure(ValueError("error"))
        cb.record_failure(ValueError("error"))
        assert cb.state == CircuitState.OPEN

        time_remaining = cb.get_time_until_reset()
        assert 0.9 < time_remaining <= 1.0  # Should be close to 1.0

    def test_time_until_reset_decreases(self):
        """Test that time until reset decreases over time."""
        cb = CircuitBreaker(name="test_decrease", failure_threshold=2, reset_timeout=1.0)

        cb.record_failure(ValueError("error"))
        cb.record_failure(ValueError("error"))

        initial = cb.get_time_until_reset()
        time.sleep(0.1)
        later = cb.get_time_until_reset()

        assert later < initial
        assert abs(initial - later - 0.1) < 0.05  # Approximately 0.1s difference

    def test_time_until_reset_zero_when_elapsed(self):
        """Test time until reset is 0 after timeout."""
        cb = CircuitBreaker(name="test_zero", failure_threshold=2, reset_timeout=0.01)

        cb.record_failure(ValueError("error"))
        cb.record_failure(ValueError("error"))
        time.sleep(0.02)

        assert cb.get_time_until_reset() == 0.0

    def test_time_until_reset_no_failure(self):
        """Test time until reset when no failures recorded."""
        cb = CircuitBreaker(name="test_no_failure", failure_threshold=2)

        # No failures, no last_failure_time
        assert cb.get_time_until_reset() == 0.0


# =============================================================================
# Statistics Tests
# =============================================================================


class TestStatistics:
    """Test statistics reporting."""

    def test_get_stats_closed(self):
        """Test stats in CLOSED state."""
        cb = CircuitBreaker(name="stats_closed", failure_threshold=5)

        stats = cb.get_stats()

        assert stats["name"] == "stats_closed"
        assert stats["state"] == "closed"
        assert stats["failure_count"] == 0
        assert stats["success_count"] == 0

    def test_get_stats_open(self):
        """Test stats in OPEN state."""
        cb = CircuitBreaker(name="stats_open", failure_threshold=3)

        cb.record_failure(ValueError("error 1"))
        cb.record_failure(ValueError("error 2"))
        cb.record_failure(ValueError("error 3"))

        stats = cb.get_stats()

        assert stats["state"] == "open"
        assert stats["failure_count"] == 3
        assert stats["time_until_reset"] > 0

    def test_get_stats_half_open(self):
        """Test stats in HALF_OPEN state."""
        cb = CircuitBreaker(
            name="stats_half",
            failure_threshold=2,
            reset_timeout=0.01,
        )

        cb.record_failure(ValueError("error"))
        cb.record_failure(ValueError("error"))
        time.sleep(0.02)

        stats = cb.get_stats()

        assert stats["state"] == "half_open"


# =============================================================================
# Manual Reset Tests
# =============================================================================


class TestManualReset:
    """Test manual reset functionality."""

    def test_reset_from_open(self):
        """Test manually resetting from OPEN state."""
        cb = CircuitBreaker(name="manual_open", failure_threshold=3)

        cb.record_failure(ValueError("error"))
        cb.record_failure(ValueError("error"))
        cb.record_failure(ValueError("error"))
        assert cb.state == CircuitState.OPEN

        cb.reset()

        assert cb.state == CircuitState.CLOSED
        assert cb._failure_count == 0

    def test_reset_from_half_open(self):
        """Test manually resetting from HALF_OPEN state."""
        cb = CircuitBreaker(
            name="manual_half",
            failure_threshold=2,
            reset_timeout=0.01,
        )

        cb.record_failure(ValueError("error"))
        cb.record_failure(ValueError("error"))
        time.sleep(0.02)
        assert cb.state == CircuitState.HALF_OPEN

        cb.reset()

        assert cb.state == CircuitState.CLOSED

    def test_reset_clears_all_state(self):
        """Test that reset clears all internal state."""
        cb = CircuitBreaker(
            name="manual_clear",
            failure_threshold=2,
            reset_timeout=0.01,
            half_open_max_calls=3,
        )

        cb.record_failure(ValueError("error"))
        cb.record_failure(ValueError("error"))
        time.sleep(0.02)
        cb.record_success()  # In half-open

        cb.reset()

        assert cb._failure_count == 0
        assert cb._success_count == 0
        assert cb._half_open_calls == 0


# =============================================================================
# Edge Cases
# =============================================================================


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_threshold_of_one(self):
        """Test circuit with failure_threshold=1."""
        cb = CircuitBreaker(name="threshold_one", failure_threshold=1)

        cb.record_failure(ValueError("single failure"))

        assert cb.state == CircuitState.OPEN

    def test_half_open_max_calls_of_one(self):
        """Test recovery with half_open_max_calls=1."""
        cb = CircuitBreaker(
            name="single_recovery",
            failure_threshold=2,
            reset_timeout=0.01,
            half_open_max_calls=1,
        )

        cb.record_failure(ValueError("error"))
        cb.record_failure(ValueError("error"))
        time.sleep(0.02)
        assert cb.state == CircuitState.HALF_OPEN

        cb.record_success()
        assert cb.state == CircuitState.CLOSED

    def test_rapid_state_transitions(self):
        """Test rapid open-halfopen-open cycles."""
        cb = CircuitBreaker(
            name="rapid",
            failure_threshold=1,
            reset_timeout=0.01,
            half_open_max_calls=1,
        )

        # First cycle
        cb.record_failure(ValueError("error"))
        assert cb.state == CircuitState.OPEN
        time.sleep(0.02)
        assert cb.state == CircuitState.HALF_OPEN
        cb.record_failure(ValueError("recovery fail"))
        assert cb.state == CircuitState.OPEN

        # Second cycle
        time.sleep(0.02)
        assert cb.state == CircuitState.HALF_OPEN
        cb.record_success()
        assert cb.state == CircuitState.CLOSED

    def test_very_long_timeout(self):
        """Test circuit with very long timeout."""
        cb = CircuitBreaker(
            name="long_timeout",
            failure_threshold=2,
            reset_timeout=3600.0,  # 1 hour
        )

        cb.record_failure(ValueError("error"))
        cb.record_failure(ValueError("error"))

        # Should stay open
        assert cb.state == CircuitState.OPEN
        assert cb.get_time_until_reset() > 3599.0

    def test_is_open_and_is_closed_properties(self):
        """Test convenience properties."""
        cb = CircuitBreaker(name="props", failure_threshold=2)

        assert cb.is_closed is True
        assert cb.is_open is False

        cb.record_failure(ValueError("error"))
        cb.record_failure(ValueError("error"))

        assert cb.is_closed is False
        assert cb.is_open is True


# =============================================================================
# Decorator Integration Tests
# =============================================================================


class TestDecoratorIntegration:
    """Test circuit_breaker decorator edge cases."""

    def test_sync_function_with_circuit(self):
        """Test synchronous function with circuit breaker."""
        call_count = 0

        @circuit_breaker(name="sync_test", failure_threshold=2)
        def sync_func():
            nonlocal call_count
            call_count += 1
            raise ValueError("sync error")

        # First two calls go through
        with pytest.raises(ValueError):
            sync_func()
        with pytest.raises(ValueError):
            sync_func()

        # Third call should be blocked
        with pytest.raises(CircuitOpenError):
            sync_func()

        assert call_count == 2

    @pytest.mark.asyncio
    async def test_async_function_with_circuit(self):
        """Test async function with circuit breaker."""
        call_count = 0

        @circuit_breaker(name="async_test", failure_threshold=2)
        async def async_func():
            nonlocal call_count
            call_count += 1
            raise ValueError("async error")

        with pytest.raises(ValueError):
            await async_func()
        with pytest.raises(ValueError):
            await async_func()

        with pytest.raises(CircuitOpenError):
            await async_func()

        assert call_count == 2

    def test_get_circuit_breaker_by_name(self):
        """Test retrieving circuit breaker by name."""

        @circuit_breaker(name="retrievable", failure_threshold=5)
        def some_func():
            pass

        some_func()  # Create the circuit breaker

        cb = get_circuit_breaker("retrievable")
        assert cb is not None
        assert cb.name == "retrievable"
        assert cb.failure_threshold == 5

    def test_circuit_open_error_contains_info(self):
        """Test CircuitOpenError contains useful information."""
        cb = CircuitBreaker(name="error_info", failure_threshold=1, reset_timeout=30.0)

        cb.record_failure(ValueError("error"))
        assert cb.is_open

        error = CircuitOpenError(cb.name, cb.get_time_until_reset())

        assert "error_info" in str(error)
        assert error.name == "error_info"
        assert error.reset_time > 0
