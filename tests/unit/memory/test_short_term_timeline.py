"""Tests for timeline (sorted set) functionality in short-term memory.

Timelines use Redis sorted sets for time-window queries.
These tests cover:
- timeline_add: Adding events to timelines
- timeline_query: Querying events within time windows
- timeline_count: Counting events in time windows
- TimeWindowQuery integration
- Permission requirements
"""

from datetime import datetime, timedelta

import pytest

from empathy_os.memory.short_term import (
    AccessTier,
    AgentCredentials,
    RedisShortTermMemory,
    TimeWindowQuery,
)


@pytest.mark.unit
class TestTimeline:
    """Test timeline (sorted set) functionality for time-window queries."""

    @pytest.fixture
    def memory(self):
        """Create a fresh memory instance for each test."""
        return RedisShortTermMemory(use_mock=True)

    @pytest.fixture
    def contributor_creds(self):
        """Contributor credentials (can write to timelines)."""
        return AgentCredentials("contributor_agent", AccessTier.CONTRIBUTOR)

    @pytest.fixture
    def observer_creds(self):
        """Observer credentials (read-only)."""
        return AgentCredentials("observer_agent", AccessTier.OBSERVER)

    # =========================================================================
    # timeline_add tests
    # =========================================================================

    def test_timeline_add_creates_entry(self, memory, contributor_creds):
        """Test timeline_add creates a time-ordered entry."""
        result = memory.timeline_add(
            "events",
            "event_001",
            {"type": "login", "user": "alice"},
            contributor_creds
        )

        assert result is True

    def test_timeline_add_requires_contributor_tier(self, memory, observer_creds):
        """Test that only CONTRIBUTOR+ can write to timelines."""
        with pytest.raises(PermissionError, match="CONTRIBUTOR tier or higher"):
            memory.timeline_add(
                "events",
                "event_001",
                {"data": "test"},
                observer_creds
            )

    def test_timeline_add_with_explicit_timestamp(self, memory, contributor_creds):
        """Test timeline_add with explicit timestamp."""
        past_time = datetime.now() - timedelta(hours=2)

        result = memory.timeline_add(
            "events",
            "event_past",
            {"type": "historical"},
            contributor_creds,
            timestamp=past_time
        )

        assert result is True

    def test_timeline_add_default_timestamp_is_now(self, memory, contributor_creds):
        """Test timeline_add uses current time by default."""
        before = datetime.now()

        memory.timeline_add(
            "events",
            "event_now",
            {"data": "test"},
            contributor_creds
        )

        after = datetime.now()

        # Query the event
        events = memory.timeline_query("events", contributor_creds)

        assert len(events) == 1
        event_time = datetime.fromisoformat(events[0]["timestamp"])
        assert before <= event_time <= after

    def test_timeline_add_includes_event_id_and_agent(self, memory, contributor_creds):
        """Test that timeline entries include event_id and agent_id."""
        memory.timeline_add(
            "events",
            "my_event",
            {"action": "test"},
            contributor_creds
        )

        events = memory.timeline_query("events", contributor_creds)

        assert len(events) == 1
        assert events[0]["event_id"] == "my_event"
        assert events[0]["agent_id"] == "contributor_agent"

    def test_timeline_add_multiple_events(self, memory, contributor_creds):
        """Test adding multiple events to a timeline."""
        for i in range(5):
            memory.timeline_add(
                "multi_events",
                f"event_{i}",
                {"index": i},
                contributor_creds
            )

        events = memory.timeline_query("multi_events", contributor_creds)

        assert len(events) == 5

    # =========================================================================
    # timeline_query tests
    # =========================================================================

    def test_timeline_query_returns_events_in_order(self, memory, contributor_creds):
        """Test timeline_query returns events sorted by timestamp."""
        base_time = datetime.now()

        # Add events with different timestamps
        for i in range(5):
            ts = base_time + timedelta(minutes=i)
            memory.timeline_add(
                "ordered_events",
                f"event_{i}",
                {"index": i},
                contributor_creds,
                timestamp=ts
            )

        # Query all events
        events = memory.timeline_query("ordered_events", contributor_creds)

        assert len(events) == 5

        # Verify order by checking indices
        for i, event in enumerate(events):
            assert event["data"]["index"] == i

    def test_timeline_query_with_time_window(self, memory, contributor_creds):
        """Test timeline_query filters by time window."""
        base_time = datetime.now()

        # Add events spanning 10 minutes
        for i in range(10):
            ts = base_time + timedelta(minutes=i)
            memory.timeline_add(
                "windowed_events",
                f"event_{i}",
                {"minute": i},
                contributor_creds,
                timestamp=ts
            )

        # Query middle window (minutes 3-7)
        query = TimeWindowQuery(
            start_time=base_time + timedelta(minutes=3),
            end_time=base_time + timedelta(minutes=7),
            limit=100
        )

        events = memory.timeline_query("windowed_events", contributor_creds, query)

        # Should only get events in window
        for event in events:
            minute = event["data"]["minute"]
            assert 3 <= minute <= 7

    def test_timeline_query_with_limit(self, memory, contributor_creds):
        """Test timeline_query respects limit."""
        for i in range(10):
            memory.timeline_add(
                "limited_timeline",
                f"event_{i}",
                {"i": i},
                contributor_creds
            )

        query = TimeWindowQuery(limit=3)
        events = memory.timeline_query("limited_timeline", contributor_creds, query)

        assert len(events) == 3

    def test_timeline_query_with_offset(self, memory, contributor_creds):
        """Test timeline_query respects offset for pagination."""
        base_time = datetime.now()

        for i in range(10):
            ts = base_time + timedelta(minutes=i)
            memory.timeline_add(
                "offset_timeline",
                f"event_{i}",
                {"index": i},
                contributor_creds,
                timestamp=ts
            )

        # Skip first 3, get next 3
        query = TimeWindowQuery(offset=3, limit=3)
        events = memory.timeline_query("offset_timeline", contributor_creds, query)

        assert len(events) == 3
        # First event should be index 3 (after skipping 0, 1, 2)
        assert events[0]["data"]["index"] == 3

    def test_timeline_query_empty_returns_empty_list(self, memory, contributor_creds):
        """Test querying empty timeline returns empty list."""
        events = memory.timeline_query("nonexistent_timeline", contributor_creds)

        assert events == []

    def test_timeline_query_no_matching_window(self, memory, contributor_creds):
        """Test querying with no events in time window."""
        # Add events in the past
        past_time = datetime.now() - timedelta(days=30)
        memory.timeline_add(
            "past_events",
            "old_event",
            {"data": "old"},
            contributor_creds,
            timestamp=past_time
        )

        # Query future window
        query = TimeWindowQuery(
            start_time=datetime.now() + timedelta(days=1),
            end_time=datetime.now() + timedelta(days=2)
        )

        events = memory.timeline_query("past_events", contributor_creds, query)

        assert events == []

    def test_timeline_query_observer_can_read(self, memory, contributor_creds, observer_creds):
        """Test that OBSERVER tier can query timelines."""
        memory.timeline_add(
            "readable_timeline",
            "event_1",
            {"data": "test"},
            contributor_creds
        )

        events = memory.timeline_query("readable_timeline", observer_creds)

        assert len(events) == 1

    # =========================================================================
    # timeline_count tests
    # =========================================================================

    def test_timeline_count_returns_correct_number(self, memory, contributor_creds):
        """Test timeline_count returns correct event count."""
        for i in range(8):
            memory.timeline_add(
                "counted_events",
                f"event_{i}",
                {"index": i},
                contributor_creds
            )

        count = memory.timeline_count("counted_events", contributor_creds)

        assert count == 8

    def test_timeline_count_with_time_window(self, memory, contributor_creds):
        """Test timeline_count with time window filter."""
        base_time = datetime.now()

        for i in range(10):
            ts = base_time + timedelta(minutes=i)
            memory.timeline_add(
                "count_window",
                f"event_{i}",
                {"index": i},
                contributor_creds,
                timestamp=ts
            )

        # Count only first 5 minutes
        query = TimeWindowQuery(
            start_time=base_time,
            end_time=base_time + timedelta(minutes=4),
        )

        count = memory.timeline_count("count_window", contributor_creds, query)

        assert count >= 4  # Minutes 0, 1, 2, 3, 4

    def test_timeline_count_empty_returns_zero(self, memory, contributor_creds):
        """Test counting empty timeline returns zero."""
        count = memory.timeline_count("nonexistent_timeline", contributor_creds)

        assert count == 0

    def test_timeline_count_no_matching_window(self, memory, contributor_creds):
        """Test count with no events in time window returns zero."""
        past_time = datetime.now() - timedelta(days=30)
        memory.timeline_add(
            "past_count",
            "old_event",
            {"data": "old"},
            contributor_creds,
            timestamp=past_time
        )

        query = TimeWindowQuery(
            start_time=datetime.now() + timedelta(days=1),
            end_time=datetime.now() + timedelta(days=2)
        )

        count = memory.timeline_count("past_count", contributor_creds, query)

        assert count == 0

    # =========================================================================
    # Integration scenarios
    # =========================================================================

    def test_agent_activity_tracking_scenario(self, memory, contributor_creds):
        """Test tracking agent activity over time."""
        timeline_name = "agent_activity"
        base_time = datetime.now() - timedelta(hours=2)

        # Simulate agent activity over 2 hours
        activities = [
            (0, "started", "Agent started"),
            (15, "analyzed", "Analyzed file main.py"),
            (30, "analyzed", "Analyzed file utils.py"),
            (60, "tested", "Ran test suite"),
            (90, "reported", "Generated report"),
            (120, "completed", "Task completed"),
        ]

        for minutes, action, description in activities:
            ts = base_time + timedelta(minutes=minutes)
            memory.timeline_add(
                timeline_name,
                f"activity_{action}_{minutes}",
                {"action": action, "description": description},
                contributor_creds,
                timestamp=ts
            )

        # Query last hour of activity
        query = TimeWindowQuery(
            start_time=base_time + timedelta(minutes=60),
            end_time=base_time + timedelta(minutes=120),
            limit=100
        )

        recent = memory.timeline_query(timeline_name, contributor_creds, query)

        # Should have tested, reported, completed
        assert len(recent) == 3

        # Count total activities
        total = memory.timeline_count(timeline_name, contributor_creds)
        assert total == 6

    def test_multiple_timelines_isolation(self, memory, contributor_creds):
        """Test that different timelines are isolated."""
        # Write to timeline A
        memory.timeline_add("timeline_a", "event_a1", {"source": "a"}, contributor_creds)
        memory.timeline_add("timeline_a", "event_a2", {"source": "a"}, contributor_creds)

        # Write to timeline B
        memory.timeline_add("timeline_b", "event_b1", {"source": "b"}, contributor_creds)

        # Check counts
        assert memory.timeline_count("timeline_a", contributor_creds) == 2
        assert memory.timeline_count("timeline_b", contributor_creds) == 1

    def test_pagination_scenario(self, memory, contributor_creds):
        """Test paginating through timeline results."""
        # Add 25 events
        for i in range(25):
            memory.timeline_add(
                "paginated",
                f"event_{i}",
                {"index": i},
                contributor_creds
            )

        # Get first page (0-9)
        page1 = memory.timeline_query(
            "paginated",
            contributor_creds,
            TimeWindowQuery(offset=0, limit=10)
        )
        assert len(page1) == 10

        # Get second page (10-19)
        page2 = memory.timeline_query(
            "paginated",
            contributor_creds,
            TimeWindowQuery(offset=10, limit=10)
        )
        assert len(page2) == 10

        # Get third page (20-24)
        page3 = memory.timeline_query(
            "paginated",
            contributor_creds,
            TimeWindowQuery(offset=20, limit=10)
        )
        assert len(page3) == 5

        # Verify no overlap
        page1_ids = {e["event_id"] for e in page1}
        page2_ids = {e["event_id"] for e in page2}
        page3_ids = {e["event_id"] for e in page3}

        assert len(page1_ids & page2_ids) == 0
        assert len(page2_ids & page3_ids) == 0
