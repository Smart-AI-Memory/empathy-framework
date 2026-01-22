"""Tests for cache base classes and data structures.

These tests cover:
- CacheEntry dataclass (creation, expiration)
- CacheStats dataclass (hit rate calculation)
- BaseCache abstract class (_create_cache_key)
"""

import time

import pytest

from empathy_os.cache.base import BaseCache, CacheEntry, CacheStats


@pytest.mark.unit
class TestCacheEntry:
    """Test CacheEntry dataclass."""

    def test_create_entry_with_all_fields(self):
        """Test creating entry with all required fields."""
        entry = CacheEntry(
            key="test_key",
            response={"result": "test"},
            workflow="test_workflow",
            stage="test_stage",
            model="gpt-4",
            prompt_hash="abc123",
            timestamp=time.time(),
            ttl=3600,
        )

        assert entry.key == "test_key"
        assert entry.response == {"result": "test"}
        assert entry.workflow == "test_workflow"
        assert entry.ttl == 3600

    def test_create_entry_without_ttl(self):
        """Test creating entry without TTL (infinite cache)."""
        entry = CacheEntry(
            key="test_key",
            response="result",
            workflow="wf",
            stage="s",
            model="m",
            prompt_hash="h",
            timestamp=time.time(),
        )

        assert entry.ttl is None

    def test_is_expired_with_no_ttl_returns_false(self):
        """Test that entry without TTL never expires."""
        entry = CacheEntry(
            key="k",
            response="r",
            workflow="w",
            stage="s",
            model="m",
            prompt_hash="h",
            timestamp=time.time() - 86400 * 365,  # 1 year ago
            ttl=None,
        )

        assert entry.is_expired(time.time()) is False

    def test_is_expired_within_ttl_returns_false(self):
        """Test that entry within TTL is not expired."""
        now = time.time()
        entry = CacheEntry(
            key="k",
            response="r",
            workflow="w",
            stage="s",
            model="m",
            prompt_hash="h",
            timestamp=now,
            ttl=3600,  # 1 hour TTL
        )

        # Check 30 minutes later
        assert entry.is_expired(now + 1800) is False

    def test_is_expired_at_exact_ttl_returns_false(self):
        """Test that entry at exact TTL boundary is not expired."""
        now = time.time()
        entry = CacheEntry(
            key="k",
            response="r",
            workflow="w",
            stage="s",
            model="m",
            prompt_hash="h",
            timestamp=now,
            ttl=3600,
        )

        # Check exactly at TTL
        assert entry.is_expired(now + 3600) is False

    def test_is_expired_after_ttl_returns_true(self):
        """Test that entry after TTL is expired."""
        now = time.time()
        entry = CacheEntry(
            key="k",
            response="r",
            workflow="w",
            stage="s",
            model="m",
            prompt_hash="h",
            timestamp=now,
            ttl=3600,
        )

        # Check 1 second after TTL
        assert entry.is_expired(now + 3601) is True

    def test_entry_stores_complex_response(self):
        """Test that entry can store complex nested responses."""
        complex_response = {
            "result": "analysis complete",
            "findings": [
                {"type": "bug", "severity": "high", "line": 42},
                {"type": "smell", "severity": "low", "line": 100},
            ],
            "metrics": {
                "coverage": 85.5,
                "complexity": 12,
            },
        }

        entry = CacheEntry(
            key="k",
            response=complex_response,
            workflow="w",
            stage="s",
            model="m",
            prompt_hash="h",
            timestamp=time.time(),
        )

        assert entry.response == complex_response
        assert entry.response["findings"][0]["severity"] == "high"


@pytest.mark.unit
class TestCacheStats:
    """Test CacheStats dataclass."""

    def test_default_values(self):
        """Test stats initialize with zeros."""
        stats = CacheStats()

        assert stats.hits == 0
        assert stats.misses == 0
        assert stats.evictions == 0

    def test_total_property(self):
        """Test total returns sum of hits and misses."""
        stats = CacheStats(hits=10, misses=5)

        assert stats.total == 15

    def test_hit_rate_with_zero_total_returns_zero(self):
        """Test hit rate is 0 when no requests made."""
        stats = CacheStats()

        assert stats.hit_rate == 0.0

    def test_hit_rate_all_hits(self):
        """Test hit rate is 100 when all requests are hits."""
        stats = CacheStats(hits=100, misses=0)

        assert stats.hit_rate == 100.0

    def test_hit_rate_all_misses(self):
        """Test hit rate is 0 when all requests are misses."""
        stats = CacheStats(hits=0, misses=100)

        assert stats.hit_rate == 0.0

    def test_hit_rate_mixed(self):
        """Test hit rate with mixed hits and misses."""
        stats = CacheStats(hits=75, misses=25)

        assert stats.hit_rate == 75.0

    def test_hit_rate_fractional(self):
        """Test hit rate with fractional result."""
        stats = CacheStats(hits=1, misses=2)

        assert abs(stats.hit_rate - 33.33333) < 0.01

    def test_to_dict(self):
        """Test stats serialization to dict."""
        stats = CacheStats(hits=10, misses=5, evictions=2)

        result = stats.to_dict()

        assert result["hits"] == 10
        assert result["misses"] == 5
        assert result["evictions"] == 2
        assert result["total"] == 15
        assert "hit_rate" in result


@pytest.mark.unit
class TestBaseCacheKeyGeneration:
    """Test BaseCache._create_cache_key method."""

    class ConcreteCache(BaseCache):
        """Concrete implementation for testing abstract class."""

        def get(self, workflow, stage, prompt, model):
            return None

        def put(self, workflow, stage, prompt, model, response, ttl=None):
            pass

        def clear(self):
            pass

        def get_stats(self):
            return self.stats

    def test_cache_key_is_deterministic(self):
        """Test same inputs produce same cache key."""
        cache = self.ConcreteCache()

        key1 = cache._create_cache_key("workflow", "stage", "prompt", "model")
        key2 = cache._create_cache_key("workflow", "stage", "prompt", "model")

        assert key1 == key2

    def test_cache_key_is_64_chars(self):
        """Test cache key is SHA256 hex digest (64 chars)."""
        cache = self.ConcreteCache()

        key = cache._create_cache_key("w", "s", "p", "m")

        assert len(key) == 64
        assert all(c in "0123456789abcdef" for c in key)

    def test_different_inputs_produce_different_keys(self):
        """Test different inputs produce different cache keys."""
        cache = self.ConcreteCache()

        key1 = cache._create_cache_key("workflow1", "stage", "prompt", "model")
        key2 = cache._create_cache_key("workflow2", "stage", "prompt", "model")
        key3 = cache._create_cache_key("workflow1", "stage", "different", "model")

        assert key1 != key2
        assert key1 != key3
        assert key2 != key3

    def test_default_ttl_is_one_day(self):
        """Test default TTL is 86400 seconds (1 day)."""
        cache = self.ConcreteCache()

        assert cache.default_ttl == 86400

    def test_custom_max_size_and_ttl(self):
        """Test custom max_size and TTL values."""
        cache = self.ConcreteCache(max_size_mb=1000, default_ttl=7200)

        assert cache.max_size_mb == 1000
        assert cache.default_ttl == 7200

    def test_stats_initialized(self):
        """Test stats object is initialized."""
        cache = self.ConcreteCache()

        assert isinstance(cache.stats, CacheStats)
        assert cache.stats.hits == 0
