"""Tests for cross-session agent communication.

Tests the CrossSessionCoordinator, BackgroundService, and session discovery
functionality for multi-session agent coordination.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest

from empathy_os.memory.cross_session import (
    KEY_ACTIVE_AGENTS,
    KEY_SERVICE_LOCK,
    STALE_THRESHOLD_SECONDS,
    BackgroundService,
    ConflictStrategy,
    CrossSessionCoordinator,
    SessionInfo,
    SessionType,
    check_redis_cross_session_support,
    generate_agent_id,
)
from empathy_os.memory.short_term import AccessTier, RedisShortTermMemory


class TestGenerateAgentId:
    """Tests for generate_agent_id function."""

    def test_generates_unique_ids(self):
        """Each call should produce a unique ID."""
        ids = [generate_agent_id(SessionType.CLAUDE) for _ in range(10)]
        assert len(set(ids)) == 10  # All unique

    def test_includes_session_type(self):
        """ID should include the session type prefix."""
        claude_id = generate_agent_id(SessionType.CLAUDE)
        service_id = generate_agent_id(SessionType.SERVICE)
        worker_id = generate_agent_id(SessionType.WORKER)

        assert claude_id.startswith("claude_")
        assert service_id.startswith("service_")
        assert worker_id.startswith("worker_")

    def test_includes_timestamp(self):
        """ID should include a timestamp component."""
        agent_id = generate_agent_id(SessionType.CLAUDE)
        parts = agent_id.split("_")
        assert len(parts) == 3
        # Second part should be a timestamp (14 digits: YYYYMMDDHHmmss)
        assert len(parts[1]) == 14
        assert parts[1].isdigit()


class TestSessionInfo:
    """Tests for SessionInfo dataclass."""

    def test_to_dict_and_from_dict(self):
        """Should round-trip through dict conversion."""
        original = SessionInfo(
            agent_id="claude_20260120_abc123",
            session_type=SessionType.CLAUDE,
            access_tier=AccessTier.CONTRIBUTOR,
            capabilities=["stash", "retrieve"],
            started_at=datetime(2026, 1, 20, 10, 0, 0),
            last_heartbeat=datetime(2026, 1, 20, 10, 5, 0),
            metadata={"key": "value"},
        )

        as_dict = original.to_dict()
        restored = SessionInfo.from_dict(as_dict)

        assert restored.agent_id == original.agent_id
        assert restored.session_type == original.session_type
        assert restored.access_tier == original.access_tier
        assert restored.capabilities == original.capabilities
        assert restored.started_at == original.started_at
        assert restored.last_heartbeat == original.last_heartbeat
        assert restored.metadata == original.metadata

    def test_is_stale_fresh_session(self):
        """Recent heartbeat should not be stale."""
        session = SessionInfo(
            agent_id="test",
            session_type=SessionType.CLAUDE,
            access_tier=AccessTier.CONTRIBUTOR,
            capabilities=[],
            started_at=datetime.now(),
            last_heartbeat=datetime.now(),
        )
        assert not session.is_stale

    def test_is_stale_old_heartbeat(self):
        """Old heartbeat should be stale."""
        old_time = datetime.now() - timedelta(seconds=STALE_THRESHOLD_SECONDS + 10)
        session = SessionInfo(
            agent_id="test",
            session_type=SessionType.CLAUDE,
            access_tier=AccessTier.CONTRIBUTOR,
            capabilities=[],
            started_at=old_time,
            last_heartbeat=old_time,
        )
        assert session.is_stale


class TestCrossSessionCoordinatorMockMode:
    """Tests that verify mock mode raises appropriate errors."""

    def test_raises_on_mock_mode(self):
        """Should raise ValueError when memory is in mock mode."""
        memory = RedisShortTermMemory(use_mock=True)

        with pytest.raises(ValueError, match="requires Redis"):
            CrossSessionCoordinator(memory=memory)


class TestCrossSessionCoordinatorWithRedis:
    """Tests for CrossSessionCoordinator with mocked Redis client."""

    @pytest.fixture
    def mock_redis_memory(self):
        """Create a memory instance with mocked Redis client."""
        memory = RedisShortTermMemory(use_mock=True)
        # Override the use_mock flag directly (it's an instance attribute)
        memory.use_mock = False
        memory._client = MagicMock()
        return memory

    def test_announce_registers_session(self, mock_redis_memory):
        """Announce should register session in Redis."""
        coordinator = CrossSessionCoordinator(
            memory=mock_redis_memory,
            auto_announce=False,
        )

        coordinator.announce()

        # Should have called hset to register
        mock_redis_memory._client.hset.assert_called()
        call_args = mock_redis_memory._client.hset.call_args
        assert call_args[0][0] == KEY_ACTIVE_AGENTS
        assert coordinator.agent_id in call_args[0][1]

        # Should have published announcement
        mock_redis_memory._client.publish.assert_called()

    def test_depart_removes_session(self, mock_redis_memory):
        """Depart should remove session from Redis."""
        coordinator = CrossSessionCoordinator(
            memory=mock_redis_memory,
            auto_announce=False,
        )

        coordinator.depart()

        # Should have called hdel to remove
        mock_redis_memory._client.hdel.assert_called_with(
            KEY_ACTIVE_AGENTS,
            coordinator.agent_id,
        )

    def test_get_active_sessions_parses_data(self, mock_redis_memory):
        """Should parse session data from Redis."""
        now = datetime.now()
        session_data = SessionInfo(
            agent_id="other_agent",
            session_type=SessionType.CLAUDE,
            access_tier=AccessTier.CONTRIBUTOR,
            capabilities=["stash"],
            started_at=now,
            last_heartbeat=now,
        )

        mock_redis_memory._client.hgetall.return_value = {
            b"other_agent": json.dumps(session_data.to_dict()).encode(),
        }

        coordinator = CrossSessionCoordinator(
            memory=mock_redis_memory,
            auto_announce=False,
        )

        sessions = coordinator.get_active_sessions()

        assert len(sessions) == 1
        assert sessions[0].agent_id == "other_agent"

    def test_get_active_sessions_filters_stale(self, mock_redis_memory):
        """Should filter out stale sessions and clean them up."""
        old_time = datetime.now() - timedelta(seconds=STALE_THRESHOLD_SECONDS + 100)
        stale_session = SessionInfo(
            agent_id="stale_agent",
            session_type=SessionType.CLAUDE,
            access_tier=AccessTier.CONTRIBUTOR,
            capabilities=[],
            started_at=old_time,
            last_heartbeat=old_time,
        )

        mock_redis_memory._client.hgetall.return_value = {
            b"stale_agent": json.dumps(stale_session.to_dict()).encode(),
        }

        coordinator = CrossSessionCoordinator(
            memory=mock_redis_memory,
            auto_announce=False,
        )

        sessions = coordinator.get_active_sessions()

        # Should be empty (stale filtered)
        assert len(sessions) == 0

        # Should have cleaned up stale session
        mock_redis_memory._client.hdel.assert_called_with(
            KEY_ACTIVE_AGENTS,
            "stale_agent",
        )


class TestConflictResolution:
    """Tests for conflict resolution strategies."""

    @pytest.fixture
    def mock_redis_memory(self):
        """Create a memory instance with mocked Redis client."""
        memory = RedisShortTermMemory(use_mock=True)
        memory.use_mock = False
        memory._client = MagicMock()
        return memory

    def test_priority_resolution_higher_tier_wins(self, mock_redis_memory):
        """Higher access tier should win in priority-based resolution."""
        # Create coordinator with STEWARD tier
        coordinator = CrossSessionCoordinator(
            memory=mock_redis_memory,
            access_tier=AccessTier.STEWARD,
            auto_announce=False,
        )

        # Other session with CONTRIBUTOR tier
        other_session = SessionInfo(
            agent_id="other_agent",
            session_type=SessionType.CLAUDE,
            access_tier=AccessTier.CONTRIBUTOR,
            capabilities=[],
            started_at=datetime.now(),
            last_heartbeat=datetime.now(),
        )

        mock_redis_memory._client.hget.return_value = json.dumps(
            other_session.to_dict()
        ).encode()

        result = coordinator.resolve_conflict(
            resource_key="test_resource",
            other_agent_id="other_agent",
            strategy=ConflictStrategy.PRIORITY_BASED,
        )

        assert result.winner_agent_id == coordinator.agent_id
        assert result.loser_agent_id == "other_agent"
        assert "Higher tier" in result.reason

    def test_priority_resolution_lower_tier_loses(self, mock_redis_memory):
        """Lower access tier should lose in priority-based resolution."""
        # Create coordinator with OBSERVER tier
        coordinator = CrossSessionCoordinator(
            memory=mock_redis_memory,
            access_tier=AccessTier.OBSERVER,
            auto_announce=False,
        )

        # Other session with STEWARD tier
        other_session = SessionInfo(
            agent_id="admin_agent",
            session_type=SessionType.SERVICE,
            access_tier=AccessTier.STEWARD,
            capabilities=[],
            started_at=datetime.now(),
            last_heartbeat=datetime.now(),
        )

        mock_redis_memory._client.hget.return_value = json.dumps(
            other_session.to_dict()
        ).encode()

        result = coordinator.resolve_conflict(
            resource_key="test_resource",
            other_agent_id="admin_agent",
            strategy=ConflictStrategy.PRIORITY_BASED,
        )

        assert result.winner_agent_id == "admin_agent"
        assert result.loser_agent_id == coordinator.agent_id

    def test_last_write_wins_strategy(self, mock_redis_memory):
        """Last write wins should always favor current writer."""
        # Mock hget to return None (no other session)
        mock_redis_memory._client.hget.return_value = None

        coordinator = CrossSessionCoordinator(
            memory=mock_redis_memory,
            access_tier=AccessTier.CONTRIBUTOR,
            auto_announce=False,
        )

        result = coordinator.resolve_conflict(
            resource_key="test_resource",
            other_agent_id="other_agent",
            strategy=ConflictStrategy.LAST_WRITE_WINS,
        )

        assert result.winner_agent_id == coordinator.agent_id
        assert result.strategy_used == ConflictStrategy.LAST_WRITE_WINS


class TestDistributedLocking:
    """Tests for distributed lock operations."""

    @pytest.fixture
    def mock_redis_memory(self):
        """Create a memory instance with mocked Redis client."""
        memory = RedisShortTermMemory(use_mock=True)
        memory.use_mock = False
        memory._client = MagicMock()
        return memory

    def test_acquire_lock_success(self, mock_redis_memory):
        """Should acquire lock when available."""
        mock_redis_memory._client.setnx.return_value = True

        coordinator = CrossSessionCoordinator(
            memory=mock_redis_memory,
            auto_announce=False,
        )

        result = coordinator.acquire_lock("resource_1")

        assert result is True
        mock_redis_memory._client.setnx.assert_called()
        mock_redis_memory._client.expire.assert_called()

    def test_acquire_lock_failure(self, mock_redis_memory):
        """Should fail when lock is held by another."""
        mock_redis_memory._client.setnx.return_value = False

        coordinator = CrossSessionCoordinator(
            memory=mock_redis_memory,
            auto_announce=False,
        )

        result = coordinator.acquire_lock("resource_1")

        assert result is False

    def test_release_lock_when_owner(self, mock_redis_memory):
        """Should release lock when we are the owner."""
        coordinator = CrossSessionCoordinator(
            memory=mock_redis_memory,
            auto_announce=False,
        )

        mock_redis_memory._client.get.return_value = coordinator.agent_id.encode()

        result = coordinator.release_lock("resource_1")

        assert result is True
        mock_redis_memory._client.delete.assert_called()

    def test_release_lock_when_not_owner(self, mock_redis_memory):
        """Should not release lock when we are not the owner."""
        coordinator = CrossSessionCoordinator(
            memory=mock_redis_memory,
            auto_announce=False,
        )

        mock_redis_memory._client.get.return_value = b"other_agent"

        result = coordinator.release_lock("resource_1")

        assert result is False
        mock_redis_memory._client.delete.assert_not_called()


class TestBackgroundService:
    """Tests for BackgroundService."""

    def test_raises_on_mock_mode(self):
        """Should raise ValueError when memory is in mock mode."""
        memory = RedisShortTermMemory(use_mock=True)

        with pytest.raises(ValueError, match="requires Redis"):
            BackgroundService(memory=memory)

    def test_service_start_acquires_lock(self):
        """Service start should acquire the service lock."""
        import os

        memory = RedisShortTermMemory(use_mock=True)
        memory.use_mock = False
        memory._client = MagicMock()
        memory._client.setnx.return_value = True
        memory._client.hgetall.return_value = {}

        service = BackgroundService(memory=memory)
        result = service.start()

        assert result is True
        assert service.is_running is True
        # Service uses os.getpid() as lock value
        memory._client.setnx.assert_called_with(KEY_SERVICE_LOCK, os.getpid())

        # Cleanup
        service.stop()

    def test_service_start_fails_if_lock_held(self):
        """Service start should fail if lock is already held."""
        memory = RedisShortTermMemory(use_mock=True)
        memory.use_mock = False
        memory._client = MagicMock()
        memory._client.setnx.return_value = False  # Lock already held

        service = BackgroundService(memory=memory)
        result = service.start()

        assert result is False
        assert service.is_running is False


class TestCheckRedisCrossSessionSupport:
    """Tests for check_redis_cross_session_support helper."""

    def test_returns_false_for_mock(self):
        """Should return False for mock mode."""
        memory = RedisShortTermMemory(use_mock=True)
        assert check_redis_cross_session_support(memory) is False

    def test_returns_true_with_client(self):
        """Should return True when client is available."""
        memory = RedisShortTermMemory(use_mock=True)
        memory.use_mock = False
        memory._client = MagicMock()

        assert check_redis_cross_session_support(memory) is True


class TestShortTermMemoryCrossSessionIntegration:
    """Tests for cross-session integration in RedisShortTermMemory."""

    def test_cross_session_available_mock(self):
        """Should return False in mock mode."""
        memory = RedisShortTermMemory(use_mock=True)
        assert memory.cross_session_available() is False

    def test_cross_session_available_with_client(self):
        """Should return True with Redis client."""
        memory = RedisShortTermMemory(use_mock=True)
        memory.use_mock = False
        memory._client = MagicMock()

        assert memory.cross_session_available() is True

    def test_enable_cross_session_mock_raises(self):
        """Should raise error in mock mode."""
        memory = RedisShortTermMemory(use_mock=True)

        with pytest.raises(ValueError, match="requires Redis"):
            memory.enable_cross_session()

    def test_enable_cross_session_returns_coordinator(self):
        """Should return a CrossSessionCoordinator."""
        memory = RedisShortTermMemory(use_mock=True)
        memory.use_mock = False
        memory._client = MagicMock()
        memory._client.hgetall.return_value = {}

        coordinator = memory.enable_cross_session(
            access_tier=AccessTier.CONTRIBUTOR,
            auto_announce=False,
        )

        assert isinstance(coordinator, CrossSessionCoordinator)
        assert coordinator.credentials.tier == AccessTier.CONTRIBUTOR


# =============================================================================
# Additional Tests for Coverage Improvement
# =============================================================================


class TestCrossSessionCoordinatorProperties:
    """Test CrossSessionCoordinator property accessors."""

    @pytest.fixture
    def mock_redis_memory(self):
        """Create a memory instance with mocked Redis client."""
        memory = RedisShortTermMemory(use_mock=True)
        memory.use_mock = False
        memory._client = MagicMock()
        return memory

    def test_session_info_property(self, mock_redis_memory):
        """Test accessing session_info property."""
        coordinator = CrossSessionCoordinator(
            memory=mock_redis_memory,
            auto_announce=False,
        )

        info = coordinator.session_info
        assert isinstance(info, SessionInfo)
        assert info.agent_id == coordinator.agent_id

    def test_agent_id_property(self, mock_redis_memory):
        """Test accessing agent_id property."""
        coordinator = CrossSessionCoordinator(
            memory=mock_redis_memory,
            auto_announce=False,
        )

        assert coordinator.agent_id is not None
        assert isinstance(coordinator.agent_id, str)

    def test_credentials_property(self, mock_redis_memory):
        """Test accessing credentials property."""
        coordinator = CrossSessionCoordinator(
            memory=mock_redis_memory,
            access_tier=AccessTier.STEWARD,
            auto_announce=False,
        )

        creds = coordinator.credentials
        assert creds.tier == AccessTier.STEWARD


class TestCrossSessionCoordinatorNullClient:
    """Test CrossSessionCoordinator when client is None."""

    @pytest.fixture
    def memory_with_null_client(self):
        """Create a memory instance where client is None."""
        memory = RedisShortTermMemory(use_mock=True)
        memory.use_mock = False  # Pretend not mock mode
        memory._client = None  # But no actual client
        return memory

    def test_announce_with_null_client_no_op(self, memory_with_null_client):
        """Announce should be a no-op when client is None."""
        coordinator = CrossSessionCoordinator(
            memory=memory_with_null_client,
            auto_announce=False,
        )

        # Should not raise, just return early
        coordinator.announce()

    def test_depart_with_null_client_no_op(self, memory_with_null_client):
        """Depart should be a no-op when client is None."""
        coordinator = CrossSessionCoordinator(
            memory=memory_with_null_client,
            auto_announce=False,
        )

        # Should not raise, just return early
        coordinator.depart()

    def test_get_active_sessions_with_null_client(self, memory_with_null_client):
        """get_active_sessions should return empty list when client is None."""
        coordinator = CrossSessionCoordinator(
            memory=memory_with_null_client,
            auto_announce=False,
        )

        sessions = coordinator.get_active_sessions()
        assert sessions == []


class TestCrossSessionCoordinatorGetSession:
    """Test CrossSessionCoordinator.get_session method."""

    @pytest.fixture
    def mock_redis_memory(self):
        """Create a memory instance with mocked Redis client."""
        memory = RedisShortTermMemory(use_mock=True)
        memory.use_mock = False
        memory._client = MagicMock()
        return memory

    def test_get_session_found(self, mock_redis_memory):
        """get_session should return SessionInfo for existing session."""
        now = datetime.now()
        session_data = SessionInfo(
            agent_id="target_agent",
            session_type=SessionType.SERVICE,
            access_tier=AccessTier.VALIDATOR,
            capabilities=["manage"],
            started_at=now,
            last_heartbeat=now,
        )

        mock_redis_memory._client.hget.return_value = json.dumps(
            session_data.to_dict()
        ).encode()

        coordinator = CrossSessionCoordinator(
            memory=mock_redis_memory,
            auto_announce=False,
        )

        result = coordinator.get_session("target_agent")
        assert result is not None
        assert result.agent_id == "target_agent"
        assert result.session_type == SessionType.SERVICE

    def test_get_session_not_found(self, mock_redis_memory):
        """get_session should return None for nonexistent session."""
        mock_redis_memory._client.hget.return_value = None

        coordinator = CrossSessionCoordinator(
            memory=mock_redis_memory,
            auto_announce=False,
        )

        result = coordinator.get_session("nonexistent_agent")
        assert result is None

    def test_get_session_stale_returns_none(self, mock_redis_memory):
        """get_session should return None for stale session."""
        old_time = datetime.now() - timedelta(seconds=STALE_THRESHOLD_SECONDS + 100)
        session_data = SessionInfo(
            agent_id="stale_agent",
            session_type=SessionType.WORKER,
            access_tier=AccessTier.CONTRIBUTOR,
            capabilities=[],
            started_at=old_time,
            last_heartbeat=old_time,
        )

        mock_redis_memory._client.hget.return_value = json.dumps(
            session_data.to_dict()
        ).encode()

        coordinator = CrossSessionCoordinator(
            memory=mock_redis_memory,
            auto_announce=False,
        )

        result = coordinator.get_session("stale_agent")
        assert result is None


class TestCrossSessionCoordinatorInvalidData:
    """Test handling of invalid session data."""

    @pytest.fixture
    def mock_redis_memory(self):
        """Create a memory instance with mocked Redis client."""
        memory = RedisShortTermMemory(use_mock=True)
        memory.use_mock = False
        memory._client = MagicMock()
        return memory

    def test_get_active_sessions_handles_invalid_json(self, mock_redis_memory):
        """Should handle invalid JSON gracefully."""
        now = datetime.now()
        mock_redis_memory._client.hgetall.return_value = {
            b"good_agent": json.dumps({
                "agent_id": "good_agent",
                "session_type": "claude",
                "access_tier": 2,  # CONTRIBUTOR = 2
                "capabilities": [],
                "started_at": now.isoformat(),
                "last_heartbeat": now.isoformat(),
                "metadata": {},
            }).encode(),
            b"bad_agent": b"not valid json {{{",
        }

        coordinator = CrossSessionCoordinator(
            memory=mock_redis_memory,
            auto_announce=False,
        )

        sessions = coordinator.get_active_sessions()
        # Should only return the good session
        assert len(sessions) == 1
        assert sessions[0].agent_id == "good_agent"

    def test_get_active_sessions_handles_missing_fields(self, mock_redis_memory):
        """Should handle sessions with missing fields gracefully."""
        mock_redis_memory._client.hgetall.return_value = {
            b"incomplete_agent": json.dumps({
                "agent_id": "incomplete_agent",
                # Missing required fields
            }).encode(),
        }

        coordinator = CrossSessionCoordinator(
            memory=mock_redis_memory,
            auto_announce=False,
        )

        sessions = coordinator.get_active_sessions()
        # Should skip invalid sessions
        assert len(sessions) == 0


class TestCrossSessionCoordinatorHeartbeat:
    """Test heartbeat functionality."""

    @pytest.fixture
    def mock_redis_memory(self):
        """Create a memory instance with mocked Redis client."""
        memory = RedisShortTermMemory(use_mock=True)
        memory.use_mock = False
        memory._client = MagicMock()
        return memory

    def test_send_heartbeat_private(self, mock_redis_memory):
        """Test sending a single heartbeat via private method."""
        coordinator = CrossSessionCoordinator(
            memory=mock_redis_memory,
            auto_announce=False,
        )

        # Call the private method
        coordinator._send_heartbeat()

        # Should have updated the session in Redis
        mock_redis_memory._client.hset.assert_called()

    def test_start_and_stop_heartbeat(self, mock_redis_memory):
        """Test starting and stopping heartbeat thread."""
        coordinator = CrossSessionCoordinator(
            memory=mock_redis_memory,
            auto_announce=False,
        )

        # Start heartbeat
        coordinator.start_heartbeat()
        assert coordinator._heartbeat_thread is not None

        # Stop heartbeat
        coordinator.stop_heartbeat()
        # Thread should be stopped

    def test_stop_heartbeat_when_not_running(self, mock_redis_memory):
        """Stop heartbeat should be safe when not running."""
        coordinator = CrossSessionCoordinator(
            memory=mock_redis_memory,
            auto_announce=False,
        )

        # Should not raise
        coordinator.stop_heartbeat()


class TestBackgroundServiceAdditional:
    """Additional tests for BackgroundService."""

    @pytest.fixture
    def mock_redis_memory(self):
        """Create a memory instance with mocked Redis client."""
        memory = RedisShortTermMemory(use_mock=True)
        memory.use_mock = False
        memory._client = MagicMock()
        # Default to not holding lock
        memory._client.set.return_value = True
        memory._client.get.return_value = None
        return memory

    def test_service_is_running_property(self, mock_redis_memory):
        """Test is_running property."""
        service = BackgroundService(
            memory=mock_redis_memory,
        )

        assert service.is_running is False

    def test_service_stop_when_not_started(self, mock_redis_memory):
        """Stop should be safe when not started."""
        service = BackgroundService(
            memory=mock_redis_memory,
        )

        # Should not raise
        service.stop()
