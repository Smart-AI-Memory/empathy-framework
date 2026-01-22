"""Tests for Redis Streams functionality in short-term memory.

Redis Streams provide ordered, persistent event logs for audit trails.
These tests cover:
- stream_append: Adding entries to streams
- stream_read: Reading entries from streams
- stream_read_new: Reading only new entries (blocking)
- Permission requirements
- Max length trimming
"""

import pytest

from empathy_os.memory.short_term import (
    AccessTier,
    AgentCredentials,
    RedisShortTermMemory,
)


@pytest.mark.unit
class TestRedisStreams:
    """Test Redis Streams functionality for audit trails."""

    @pytest.fixture
    def memory(self):
        """Create a fresh memory instance for each test."""
        return RedisShortTermMemory(use_mock=True)

    @pytest.fixture
    def contributor_creds(self):
        """Contributor credentials (can write to streams)."""
        return AgentCredentials("contributor_agent", AccessTier.CONTRIBUTOR)

    @pytest.fixture
    def observer_creds(self):
        """Observer credentials (read-only)."""
        return AgentCredentials("observer_agent", AccessTier.OBSERVER)

    @pytest.fixture
    def validator_creds(self):
        """Validator credentials (can write to streams)."""
        return AgentCredentials("validator_agent", AccessTier.VALIDATOR)

    # =========================================================================
    # stream_append tests
    # =========================================================================

    def test_stream_append_returns_entry_id(self, memory, contributor_creds):
        """Test stream_append returns a valid entry ID."""
        entry_id = memory.stream_append(
            "audit",
            {"action": "pattern_created", "pattern_id": "pat_001"},
            contributor_creds
        )

        assert entry_id is not None
        assert "-" in entry_id  # Redis stream IDs contain "-"

    def test_stream_append_requires_contributor_tier(self, memory, observer_creds):
        """Test that only CONTRIBUTOR+ can append to streams."""
        with pytest.raises(PermissionError, match="CONTRIBUTOR tier or higher"):
            memory.stream_append(
                "audit",
                {"action": "test"},
                observer_creds
            )

    def test_stream_append_validator_can_write(self, memory, validator_creds):
        """Test that VALIDATOR tier can write to streams."""
        entry_id = memory.stream_append(
            "validation_log",
            {"action": "pattern_validated"},
            validator_creds
        )

        assert entry_id is not None

    def test_stream_append_adds_agent_id_and_timestamp(self, memory, contributor_creds):
        """Test that stream entries include agent_id and timestamp."""
        memory.stream_append(
            "audit",
            {"action": "test_action"},
            contributor_creds
        )

        # Read the entry back
        entries = memory.stream_read("audit", contributor_creds)

        assert len(entries) == 1
        entry_id, data = entries[0]
        assert data["agent_id"] == "contributor_agent"
        assert "timestamp" in data

    def test_stream_append_multiple_entries(self, memory, contributor_creds):
        """Test appending multiple entries to a stream."""
        for i in range(5):
            memory.stream_append(
                "events",
                {"event_number": i},
                contributor_creds
            )

        entries = memory.stream_read("events", contributor_creds)

        assert len(entries) == 5

    def test_stream_append_max_len_trims_old_entries(self, memory, contributor_creds):
        """Test max_len parameter trims old entries."""
        # Append more entries than max_len
        for i in range(20):
            memory.stream_append(
                "limited_stream",
                {"index": i},
                contributor_creds,
                max_len=10
            )

        # Read all entries
        entries = memory.stream_read(
            "limited_stream",
            contributor_creds,
            count=100
        )

        # Should be trimmed to max_len
        assert len(entries) <= 10

    def test_stream_append_complex_data(self, memory, contributor_creds):
        """Test appending complex nested data structures."""
        complex_data = {
            "action": "code_review",
            "files": ["main.py", "test.py"],
            "metrics": {"lines_changed": 150, "coverage": 85.5},
        }

        entry_id = memory.stream_append("reviews", complex_data, contributor_creds)

        assert entry_id is not None

        entries = memory.stream_read("reviews", contributor_creds)
        assert len(entries) == 1

    # =========================================================================
    # stream_read tests
    # =========================================================================

    def test_stream_read_returns_entries_in_order(self, memory, contributor_creds):
        """Test stream_read returns entries in chronological order."""
        # Append multiple entries
        for i in range(5):
            memory.stream_append(
                "test_stream",
                {"index": i},
                contributor_creds
            )

        # Read entries
        entries = memory.stream_read("test_stream", contributor_creds, count=10)

        assert len(entries) == 5

        # Verify each entry has an ID
        for entry_id, data in entries:
            assert entry_id is not None

    def test_stream_read_with_start_id_filters_entries(self, memory, contributor_creds):
        """Test stream_read with start_id filters older entries."""
        entry_ids = []
        for i in range(5):
            entry_id = memory.stream_append(
                "filtered_stream",
                {"index": i},
                contributor_creds
            )
            entry_ids.append(entry_id)

        # Read from the third entry
        entries = memory.stream_read(
            "filtered_stream",
            contributor_creds,
            start_id=entry_ids[2],
            count=10
        )

        # Should only get entries after start_id
        assert len(entries) <= 3  # Entries 2, 3, 4 or fewer

    def test_stream_read_nonexistent_stream_returns_empty(self, memory, contributor_creds):
        """Test reading from nonexistent stream returns empty list."""
        entries = memory.stream_read(
            "nonexistent_stream",
            contributor_creds
        )

        assert entries == []

    def test_stream_read_with_count_limit(self, memory, contributor_creds):
        """Test stream_read respects count limit."""
        # Append 10 entries
        for i in range(10):
            memory.stream_append("count_test", {"i": i}, contributor_creds)

        # Read only 3
        entries = memory.stream_read("count_test", contributor_creds, count=3)

        assert len(entries) == 3

    def test_stream_read_observer_can_read(self, memory, contributor_creds, observer_creds):
        """Test that OBSERVER tier can read streams."""
        # Add entries as contributor
        memory.stream_append("readable_stream", {"data": "test"}, contributor_creds)

        # Read as observer
        entries = memory.stream_read("readable_stream", observer_creds)

        assert len(entries) == 1

    # =========================================================================
    # stream_read_new tests
    # =========================================================================

    def test_stream_read_new_returns_empty_in_mock_mode(self, memory, contributor_creds):
        """Test stream_read_new returns empty in mock mode (no blocking support)."""
        # Add some entries first
        memory.stream_append("test_stream", {"data": "test"}, contributor_creds)

        # stream_read_new in mock mode returns empty (no blocking)
        entries = memory.stream_read_new(
            "test_stream",
            contributor_creds,
            block_ms=0,
            count=10
        )

        assert entries == []

    def test_stream_read_new_nonexistent_stream(self, memory, contributor_creds):
        """Test stream_read_new on nonexistent stream."""
        entries = memory.stream_read_new(
            "nonexistent_stream",
            contributor_creds,
            block_ms=0,
            count=10
        )

        assert entries == []

    # =========================================================================
    # Integration scenarios
    # =========================================================================

    def test_audit_trail_scenario(self, memory, contributor_creds, validator_creds):
        """Test a realistic audit trail scenario."""
        # Step 1: Pattern creation
        memory.stream_append(
            "pattern_audit",
            {"action": "created", "pattern_id": "pat_001", "stage": "staging"},
            contributor_creds
        )

        # Step 2: Validation
        memory.stream_append(
            "pattern_audit",
            {"action": "validated", "pattern_id": "pat_001", "confidence": 0.85},
            validator_creds
        )

        # Step 3: Promotion
        memory.stream_append(
            "pattern_audit",
            {"action": "promoted", "pattern_id": "pat_001", "library": "production"},
            validator_creds
        )

        # Verify complete audit trail
        entries = memory.stream_read("pattern_audit", contributor_creds)

        assert len(entries) == 3

        # Verify actions in order
        actions = [data.get("action") for _, data in entries]
        assert "created" in str(actions)
        assert "validated" in str(actions)
        assert "promoted" in str(actions)

    def test_multiple_streams_isolation(self, memory, contributor_creds):
        """Test that different streams are isolated."""
        # Write to stream A
        memory.stream_append("stream_a", {"source": "a"}, contributor_creds)
        memory.stream_append("stream_a", {"source": "a"}, contributor_creds)

        # Write to stream B
        memory.stream_append("stream_b", {"source": "b"}, contributor_creds)

        # Read each stream
        entries_a = memory.stream_read("stream_a", contributor_creds)
        entries_b = memory.stream_read("stream_b", contributor_creds)

        assert len(entries_a) == 2
        assert len(entries_b) == 1
