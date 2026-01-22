"""Tests for health check resilience pattern.

These tests cover:
- HealthStatus enum
- HealthCheckResult dataclass
- SystemHealth dataclass
- HealthCheck class
- Health check registration and execution
"""

import asyncio
from datetime import datetime

import pytest

from empathy_os.resilience.health import (
    HealthCheck,
    HealthCheckResult,
    HealthStatus,
    SystemHealth,
    get_health_check,
)


@pytest.mark.unit
class TestHealthStatus:
    """Test HealthStatus enum."""

    def test_healthy_status(self):
        """Test HEALTHY status exists."""
        assert HealthStatus.HEALTHY is not None
        assert HealthStatus.HEALTHY.value in ["healthy", "HEALTHY", 0]

    def test_degraded_status(self):
        """Test DEGRADED status exists."""
        assert HealthStatus.DEGRADED is not None

    def test_unhealthy_status(self):
        """Test UNHEALTHY status exists."""
        assert HealthStatus.UNHEALTHY is not None

    def test_unknown_status(self):
        """Test UNKNOWN status exists."""
        assert HealthStatus.UNKNOWN is not None


@pytest.mark.unit
class TestHealthCheckResult:
    """Test HealthCheckResult dataclass."""

    def test_create_healthy_result(self):
        """Test creating a healthy check result."""
        result = HealthCheckResult(
            name="test_check", status=HealthStatus.HEALTHY, message="All good"
        )

        assert result.name == "test_check"
        assert result.status == HealthStatus.HEALTHY
        assert result.message == "All good"

    def test_create_result_with_details(self):
        """Test creating result with additional details."""
        result = HealthCheckResult(
            name="db_check",
            status=HealthStatus.HEALTHY,
            message="Connected",
            latency_ms=5.2,
            details={"connections": 10, "pool_size": 20},
        )

        assert result.latency_ms == 5.2
        assert result.details["connections"] == 10

    def test_result_has_timestamp(self):
        """Test result has timestamp."""
        result = HealthCheckResult(name="test", status=HealthStatus.HEALTHY)

        assert result.timestamp is not None
        assert isinstance(result.timestamp, datetime)


@pytest.mark.unit
class TestSystemHealth:
    """Test SystemHealth dataclass."""

    def test_create_system_health(self):
        """Test creating system health status."""
        checks = [
            HealthCheckResult(name="check1", status=HealthStatus.HEALTHY),
            HealthCheckResult(name="check2", status=HealthStatus.HEALTHY),
        ]

        health = SystemHealth(
            status=HealthStatus.HEALTHY, checks=checks, version="1.0.0", uptime_seconds=3600
        )

        assert health.status == HealthStatus.HEALTHY
        assert len(health.checks) == 2
        assert health.version == "1.0.0"
        assert health.uptime_seconds == 3600

    def test_to_dict(self):
        """Test serialization to dictionary."""
        checks = [HealthCheckResult(name="check1", status=HealthStatus.HEALTHY)]

        health = SystemHealth(
            status=HealthStatus.HEALTHY, checks=checks, version="1.0.0"
        )

        result = health.to_dict()

        assert "status" in result
        assert "checks" in result
        assert "version" in result
        assert "timestamp" in result


@pytest.mark.unit
class TestHealthCheckClass:
    """Test HealthCheck class."""

    @pytest.fixture
    def health(self):
        """Create a fresh health check instance."""
        return HealthCheck(version="test-1.0")

    def test_register_check_as_decorator(self, health):
        """Test registering health check as decorator."""
        @health.register("my_check")
        def check_func():
            return True

        # Verify check is registered
        assert "my_check" in health._checks

    def test_register_check_with_timeout(self, health):
        """Test registering check with custom timeout."""
        @health.register("slow_check", timeout=30.0)
        def slow_check():
            return True

        assert "slow_check" in health._checks

    def test_register_critical_check(self, health):
        """Test registering critical check."""
        @health.register("critical_check", critical=True)
        def critical_func():
            return True

        assert "critical_check" in health._checks

    @pytest.mark.asyncio
    async def test_run_check_returns_healthy(self, health):
        """Test running check that returns True."""
        @health.register("healthy_check")
        def healthy():
            return True

        result = await health.run_check("healthy_check")

        assert result.status == HealthStatus.HEALTHY

    @pytest.mark.asyncio
    async def test_run_check_returns_unhealthy(self, health):
        """Test running check that returns False."""
        @health.register("unhealthy_check")
        def unhealthy():
            return False

        result = await health.run_check("unhealthy_check")

        assert result.status == HealthStatus.UNHEALTHY

    @pytest.mark.asyncio
    async def test_run_check_with_dict_response(self, health):
        """Test running check that returns dict."""
        @health.register("dict_check")
        def dict_response():
            return {"healthy": True, "connections": 5}

        result = await health.run_check("dict_check")

        assert result.status == HealthStatus.HEALTHY

    @pytest.mark.asyncio
    async def test_run_check_handles_exception(self, health):
        """Test running check that raises exception."""
        @health.register("error_check")
        def raises_error():
            raise ValueError("Something went wrong")

        result = await health.run_check("error_check")

        assert result.status == HealthStatus.UNHEALTHY
        assert "Something went wrong" in result.message

    @pytest.mark.asyncio
    async def test_run_check_tracks_latency(self, health):
        """Test that run_check tracks execution latency."""
        @health.register("latency_check")
        async def slow_check():
            await asyncio.sleep(0.05)
            return True

        result = await health.run_check("latency_check")

        assert result.latency_ms >= 50

    @pytest.mark.asyncio
    async def test_run_all_checks(self, health):
        """Test running all registered checks."""
        @health.register("check1")
        def check1():
            return True

        @health.register("check2")
        def check2():
            return True

        system_health = await health.run_all()

        assert system_health.status == HealthStatus.HEALTHY
        assert len(system_health.checks) == 2

    @pytest.mark.asyncio
    async def test_run_all_with_unhealthy_check(self, health):
        """Test run_all with one unhealthy check."""
        @health.register("healthy")
        def healthy():
            return True

        @health.register("unhealthy")
        def unhealthy():
            return False

        system_health = await health.run_all()

        # Overall should be UNHEALTHY if any check is unhealthy
        assert system_health.status != HealthStatus.HEALTHY

    def test_run_all_sync(self, health):
        """Test synchronous run_all wrapper."""
        @health.register("sync_check")
        def sync_check():
            return True

        system_health = health.run_all_sync()

        assert system_health is not None
        assert len(system_health.checks) >= 1


@pytest.mark.unit
class TestHealthCheckAsync:
    """Test async health checks."""

    @pytest.fixture
    def health(self):
        return HealthCheck(version="test-async")

    @pytest.mark.asyncio
    async def test_async_check_function(self, health):
        """Test registering and running async check."""
        @health.register("async_check")
        async def async_healthy():
            await asyncio.sleep(0.01)
            return True

        result = await health.run_check("async_check")

        assert result.status == HealthStatus.HEALTHY

    @pytest.mark.asyncio
    async def test_run_all_parallel(self, health):
        """Test run_all executes checks in parallel."""
        start_time = asyncio.get_event_loop().time()

        @health.register("slow1")
        async def slow1():
            await asyncio.sleep(0.05)
            return True

        @health.register("slow2")
        async def slow2():
            await asyncio.sleep(0.05)
            return True

        system_health = await health.run_all()
        elapsed = asyncio.get_event_loop().time() - start_time

        # If run in parallel, should take ~50ms not 100ms
        assert elapsed < 0.15  # Allow some overhead
        assert len(system_health.checks) == 2


@pytest.mark.unit
class TestGlobalHealthCheck:
    """Test global health check instance."""

    def test_get_health_check_returns_instance(self):
        """Test get_health_check returns HealthCheck instance."""
        health = get_health_check()

        assert health is not None
        assert isinstance(health, HealthCheck)

    def test_get_health_check_returns_same_instance(self):
        """Test get_health_check returns same instance on multiple calls."""
        health1 = get_health_check()
        health2 = get_health_check()

        # Should be the same instance (singleton)
        assert health1 is health2
