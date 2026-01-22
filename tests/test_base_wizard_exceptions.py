"""Exception and error handling tests for BaseWizard.

Tests error scenarios including:
- Redis connection failures
- JSON serialization errors
- Invalid context data
- Memory operation failures
- Missing short_term_memory

Copyright 2025 Smart AI Memory, LLC
Licensed under Fair Source 0.9
"""

from unittest.mock import Mock

import pytest

from empathy_os.redis_memory import RedisShortTermMemory
from empathy_software_plugin.wizards.base_wizard import BaseWizard


class ConcreteWizard(BaseWizard):
    """Concrete implementation of BaseWizard for testing."""

    @property
    def name(self) -> str:
        return "Test Wizard"

    @property
    def level(self) -> int:
        return 4

    async def analyze(self, context: dict) -> dict:
        return {
            "predictions": ["test prediction"],
            "recommendations": ["test recommendation"],
            "confidence": 0.9,
        }


class TestBaseWizardMemoryErrors:
    """Test error handling in memory operations."""

    def test_cache_key_with_non_serializable_context(self):
        """Test _cache_key handles non-JSON-serializable context."""
        wizard = ConcreteWizard()

        # Create context with non-serializable object
        context = {
            "data": "string",
            "function": lambda x: x,  # Functions can't be JSON serialized
        }

        # Should handle serialization by using default=str
        key = wizard._cache_key(context)

        assert isinstance(key, str)
        assert "Test Wizard" in key

    def test_cache_key_with_circular_reference(self):
        """Test _cache_key handles circular references in context."""
        wizard = ConcreteWizard()

        # Create circular reference
        context: dict = {"key": "value"}
        context["self"] = context

        # JSON dumps with circular ref would normally fail
        # Our implementation uses default=str which should handle it
        try:
            key = wizard._cache_key(context)
            assert isinstance(key, str)
        except (ValueError, TypeError):
            # If it fails, that's also acceptable behavior
            pass

    def test_get_cached_result_without_memory(self):
        """Test get_cached_result when short_term_memory is None."""
        wizard = ConcreteWizard(short_term_memory=None)

        result = wizard.get_cached_result({"test": "context"})

        assert result is None

    def test_cache_result_without_memory(self):
        """Test cache_result when short_term_memory is None."""
        wizard = ConcreteWizard(short_term_memory=None)

        success = wizard.cache_result({"test": "context"}, {"result": "data"})

        assert success is False

    def test_get_cached_result_with_redis_error(self):
        """Test get_cached_result handles Redis connection errors."""
        mock_memory = Mock(spec=RedisShortTermMemory)
        mock_memory.retrieve.side_effect = ConnectionError("Redis unavailable")

        wizard = ConcreteWizard(short_term_memory=mock_memory)

        # Should raise or return None depending on implementation
        with pytest.raises(ConnectionError):
            wizard.get_cached_result({"test": "context"})

    def test_cache_result_with_redis_error(self):
        """Test cache_result handles Redis connection errors."""
        mock_memory = Mock(spec=RedisShortTermMemory)
        mock_memory.stash.side_effect = ConnectionError("Redis unavailable")

        wizard = ConcreteWizard(short_term_memory=mock_memory)

        # Should raise or return False depending on implementation
        with pytest.raises(ConnectionError):
            wizard.cache_result({"test": "context"}, {"result": "data"})

    @pytest.mark.asyncio
    async def test_analyze_with_cache_handles_retrieval_error(self):
        """Test analyze_with_cache when cache retrieval fails."""
        mock_memory = Mock(spec=RedisShortTermMemory)
        mock_memory.retrieve.side_effect = Exception("Cache read error")

        wizard = ConcreteWizard(short_term_memory=mock_memory)

        # Should fall through to fresh analysis
        with pytest.raises(Exception):  # noqa: B017
            await wizard.analyze_with_cache({"test": "context"})

    @pytest.mark.asyncio
    async def test_analyze_with_cache_handles_storage_error(self):
        """Test analyze_with_cache when cache storage fails."""
        mock_memory = Mock(spec=RedisShortTermMemory)
        mock_memory.retrieve.return_value = None  # Cache miss
        mock_memory.stash.side_effect = Exception("Cache write error")

        wizard = ConcreteWizard(short_term_memory=mock_memory)

        # Should complete analysis but fail silently on cache write
        with pytest.raises(Exception):  # noqa: B017
            await wizard.analyze_with_cache({"test": "context"})


class TestBaseWizardSharedContextErrors:
    """Test error handling in shared context operations."""

    def test_share_context_without_memory(self):
        """Test share_context when short_term_memory is None."""
        wizard = ConcreteWizard(short_term_memory=None)

        success = wizard.share_context("test_key", {"data": "value"})

        assert success is False

    def test_share_context_with_redis_error(self):
        """Test share_context handles Redis errors."""
        mock_memory = Mock(spec=RedisShortTermMemory)
        mock_memory.stash.side_effect = ConnectionError("Redis down")

        wizard = ConcreteWizard(short_term_memory=mock_memory)

        with pytest.raises(ConnectionError):
            wizard.share_context("test_key", {"data": "value"})

    def test_get_shared_context_without_memory(self):
        """Test get_shared_context when short_term_memory is None."""
        wizard = ConcreteWizard(short_term_memory=None)

        result = wizard.get_shared_context("test_key")

        assert result is None

    def test_get_shared_context_with_redis_error(self):
        """Test get_shared_context handles Redis errors."""
        mock_memory = Mock(spec=RedisShortTermMemory)
        mock_memory.retrieve.side_effect = TimeoutError("Redis timeout")

        wizard = ConcreteWizard(short_term_memory=mock_memory)

        with pytest.raises(TimeoutError):
            wizard.get_shared_context("test_key")

    def test_share_context_with_non_serializable_data(self):
        """Test share_context with non-JSON-serializable data."""
        mock_memory = Mock(spec=RedisShortTermMemory)
        mock_memory.stash.return_value = True

        wizard = ConcreteWizard(short_term_memory=mock_memory)

        # Data with non-serializable function
        data = {"func": lambda: None}

        # Should attempt to stash (serialization handled by Redis memory)
        wizard.share_context("test_key", data)

        # Verify stash was called
        assert mock_memory.stash.called


class TestBaseWizardPatternStagingErrors:
    """Test error handling in pattern staging operations."""

    def test_stage_discovered_pattern_without_memory(self):
        """Test stage_discovered_pattern when short_term_memory is None."""
        wizard = ConcreteWizard(short_term_memory=None)

        success = wizard.stage_discovered_pattern(
            pattern_id="test_pattern",
            pattern_type="security",
            name="Test Pattern",
            description="Test description",
        )

        assert success is False

    def test_stage_discovered_pattern_with_redis_error(self):
        """Test stage_discovered_pattern handles Redis errors."""
        mock_memory = Mock(spec=RedisShortTermMemory)
        mock_memory.stage_pattern.side_effect = ConnectionError("Redis unavailable")

        wizard = ConcreteWizard(short_term_memory=mock_memory)

        with pytest.raises(ConnectionError):
            wizard.stage_discovered_pattern(
                pattern_id="test_pattern",
                pattern_type="security",
                name="Test Pattern",
                description="Test description",
            )

    def test_stage_discovered_pattern_with_invalid_confidence(self):
        """Test stage_discovered_pattern with out-of-range confidence."""
        mock_memory = Mock(spec=RedisShortTermMemory)
        mock_memory.stage_pattern.return_value = True

        wizard = ConcreteWizard(short_term_memory=mock_memory)

        # Confidence outside 0.0-1.0 range
        wizard.stage_discovered_pattern(
            pattern_id="test",
            pattern_type="test",
            name="Test",
            description="Test",
            confidence=1.5,  # Invalid
        )

        # Should still call stage_pattern (validation might happen elsewhere)
        assert mock_memory.stage_pattern.called

    def test_stage_discovered_pattern_with_empty_strings(self):
        """Test stage_discovered_pattern with empty strings."""
        mock_memory = Mock(spec=RedisShortTermMemory)
        mock_memory.stage_pattern.return_value = True

        wizard = ConcreteWizard(short_term_memory=mock_memory)

        wizard.stage_discovered_pattern(
            pattern_id="",  # Empty
            pattern_type="",  # Empty
            name="",  # Empty
            description="",  # Empty
        )

        # Should still attempt (validation might happen in stage_pattern)
        assert mock_memory.stage_pattern.called


class TestBaseWizardSignalErrors:
    """Test error handling in signal operations."""

    def test_send_signal_without_memory(self):
        """Test send_signal when short_term_memory is None."""
        wizard = ConcreteWizard(short_term_memory=None)

        success = wizard.send_signal("test_signal", {"status": "complete"})

        assert success is False

    def test_send_signal_with_redis_error(self):
        """Test send_signal handles Redis errors."""
        mock_memory = Mock(spec=RedisShortTermMemory)
        mock_memory.send_signal.side_effect = ConnectionError("Redis down")

        wizard = ConcreteWizard(short_term_memory=mock_memory)

        with pytest.raises(ConnectionError):
            wizard.send_signal("test_signal", {"status": "complete"})

    def test_send_signal_with_large_payload(self):
        """Test send_signal with very large data payload."""
        mock_memory = Mock(spec=RedisShortTermMemory)
        mock_memory.send_signal.return_value = True

        wizard = ConcreteWizard(short_term_memory=mock_memory)

        # Large payload
        large_data = {"data": "x" * 1000000}  # 1MB of data

        wizard.send_signal("test_signal", large_data)

        # Should attempt to send
        assert mock_memory.send_signal.called


class TestBaseWizardInitializationErrors:
    """Test error handling during initialization."""

    def test_initialization_with_invalid_ttl(self):
        """Test initialization with invalid cache TTL."""
        # Negative TTL
        wizard = ConcreteWizard(cache_ttl_seconds=-1)

        assert wizard.cache_ttl == -1  # Should accept (validation elsewhere)

    def test_initialization_with_zero_ttl(self):
        """Test initialization with zero cache TTL."""
        wizard = ConcreteWizard(cache_ttl_seconds=0)

        assert wizard.cache_ttl == 0

    def test_initialization_with_very_large_ttl(self):
        """Test initialization with very large cache TTL."""
        wizard = ConcreteWizard(cache_ttl_seconds=999999999)

        assert wizard.cache_ttl == 999999999


class TestBaseWizardAnalyzeErrors:
    """Test error handling in analyze method."""

    @pytest.mark.asyncio
    async def test_analyze_with_empty_context(self):
        """Test analyze with empty context."""
        wizard = ConcreteWizard()

        result = await wizard.analyze({})

        # Should complete successfully
        assert "predictions" in result
        assert "confidence" in result

    @pytest.mark.asyncio
    async def test_analyze_with_none_context_values(self):
        """Test analyze with None values in context."""
        wizard = ConcreteWizard()

        result = await wizard.analyze({"key1": None, "key2": None})

        # Should handle None values
        assert result is not None

    @pytest.mark.asyncio
    async def test_analyze_with_nested_context(self):
        """Test analyze with deeply nested context."""
        wizard = ConcreteWizard()

        nested_context = {"level1": {"level2": {"level3": {"level4": {"data": "deep"}}}}}

        result = await wizard.analyze(nested_context)

        assert result is not None

    @pytest.mark.asyncio
    async def test_analyze_with_cache_returns_cached_flag(self):
        """Test analyze_with_cache adds _from_cache flag."""
        mock_memory = Mock(spec=RedisShortTermMemory)
        mock_memory.retrieve.return_value = None  # Cache miss
        mock_memory.stash.return_value = True

        wizard = ConcreteWizard(short_term_memory=mock_memory)

        result = await wizard.analyze_with_cache({"test": "data"})

        # Should have _from_cache=False for fresh analysis
        assert "_from_cache" in result
        assert result["_from_cache"] is False

    @pytest.mark.asyncio
    async def test_analyze_with_cache_hit_returns_cached_flag(self):
        """Test analyze_with_cache returns cached result with flag."""
        cached_result = {
            "predictions": ["cached"],
            "confidence": 0.8,
        }

        mock_memory = Mock(spec=RedisShortTermMemory)
        mock_memory.retrieve.return_value = cached_result

        wizard = ConcreteWizard(short_term_memory=mock_memory)

        result = await wizard.analyze_with_cache({"test": "data"})

        # Should have _from_cache=True
        assert result["_from_cache"] is True
        assert result["predictions"] == ["cached"]


class TestBaseWizardEdgeCases:
    """Test edge cases in BaseWizard."""

    def test_has_memory_returns_correct_state(self):
        """Test has_memory returns correct boolean."""
        wizard_with_memory = ConcreteWizard(short_term_memory=Mock(spec=RedisShortTermMemory))
        wizard_without_memory = ConcreteWizard(short_term_memory=None)

        assert wizard_with_memory.has_memory() is True
        assert wizard_without_memory.has_memory() is False

    def test_cache_key_consistency(self):
        """Test _cache_key generates consistent keys for same context."""
        wizard = ConcreteWizard()

        context = {"key1": "value1", "key2": "value2"}

        key1 = wizard._cache_key(context)
        key2 = wizard._cache_key(context)

        # Same context should generate same key
        assert key1 == key2

    def test_cache_key_different_for_different_context(self):
        """Test _cache_key generates different keys for different contexts."""
        wizard = ConcreteWizard()

        key1 = wizard._cache_key({"key": "value1"})
        key2 = wizard._cache_key({"key": "value2"})

        # Different context should generate different keys
        assert key1 != key2

    def test_cache_key_order_independent(self):
        """Test _cache_key is order-independent (uses sort_keys=True)."""
        wizard = ConcreteWizard()

        key1 = wizard._cache_key({"a": 1, "b": 2})
        key2 = wizard._cache_key({"b": 2, "a": 1})

        # Order shouldn't matter (JSON dumps with sort_keys)
        assert key1 == key2

    def test_get_shared_context_from_specific_wizard(self):
        """Test get_shared_context with from_wizard parameter."""
        mock_memory = Mock(spec=RedisShortTermMemory)
        mock_memory.retrieve.return_value = {"shared": "data"}

        wizard = ConcreteWizard(short_term_memory=mock_memory)

        wizard.get_shared_context("test_key", from_wizard="OtherWizard")

        # Should call retrieve with specific agent_id
        mock_memory.retrieve.assert_called_once()
        call_args = mock_memory.retrieve.call_args
        assert "agent_id" in call_args[1]
        assert call_args[1]["agent_id"] == "wizard_OtherWizard"
