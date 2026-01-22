"""Tests for TimeWindowQuery class in short-term memory.

These tests cover:
- TimeWindowQuery dataclass creation
- start_score and end_score computed properties
- Default values
- Edge cases with None datetimes
"""

from datetime import datetime, timedelta

import pytest

from empathy_os.memory.short_term import TimeWindowQuery


@pytest.mark.unit
class TestTimeWindowQuery:
    """Test TimeWindowQuery dataclass and computed properties."""

    def test_start_score_with_none_returns_negative_infinity(self):
        """Test start_score property returns -inf when start_time is None."""
        query = TimeWindowQuery(start_time=None, end_time=datetime.now())

        assert query.start_score == float("-inf")

    def test_end_score_with_none_returns_positive_infinity(self):
        """Test end_score property returns +inf when end_time is None."""
        query = TimeWindowQuery(start_time=datetime.now(), end_time=None)

        assert query.end_score == float("+inf")

    def test_start_score_with_datetime_returns_timestamp(self):
        """Test start_score converts datetime to timestamp."""
        now = datetime.now()
        query = TimeWindowQuery(start_time=now, end_time=None)

        assert query.start_score == now.timestamp()

    def test_end_score_with_datetime_returns_timestamp(self):
        """Test end_score converts datetime to timestamp."""
        now = datetime.now()
        query = TimeWindowQuery(start_time=None, end_time=now)

        assert query.end_score == now.timestamp()

    def test_default_limit_is_100(self):
        """Test default limit value."""
        query = TimeWindowQuery()

        assert query.limit == 100

    def test_default_offset_is_0(self):
        """Test default offset value."""
        query = TimeWindowQuery()

        assert query.offset == 0

    def test_both_times_none_returns_full_range(self):
        """Test that None for both times represents full time range."""
        query = TimeWindowQuery()

        assert query.start_score == float("-inf")
        assert query.end_score == float("+inf")

    def test_full_query_with_all_parameters(self):
        """Test creating query with all parameters specified."""
        start = datetime(2026, 1, 1, 0, 0, 0)
        end = datetime(2026, 1, 31, 23, 59, 59)

        query = TimeWindowQuery(
            start_time=start,
            end_time=end,
            limit=50,
            offset=10
        )

        assert query.start_score == start.timestamp()
        assert query.end_score == end.timestamp()
        assert query.limit == 50
        assert query.offset == 10

    def test_time_range_ordering(self):
        """Test that start time is always before end time in scores."""
        start = datetime.now() - timedelta(hours=1)
        end = datetime.now()

        query = TimeWindowQuery(start_time=start, end_time=end)

        assert query.start_score < query.end_score

    def test_same_start_and_end_time(self):
        """Test when start and end time are the same."""
        now = datetime.now()
        query = TimeWindowQuery(start_time=now, end_time=now)

        assert query.start_score == query.end_score

    def test_custom_limit_value(self):
        """Test setting a custom limit."""
        query = TimeWindowQuery(limit=500)

        assert query.limit == 500

    def test_custom_offset_value(self):
        """Test setting a custom offset for pagination."""
        query = TimeWindowQuery(offset=25)

        assert query.offset == 25

    def test_query_for_last_hour(self):
        """Test creating a query for the last hour (common use case)."""
        end = datetime.now()
        start = end - timedelta(hours=1)

        query = TimeWindowQuery(start_time=start, end_time=end, limit=100)

        # Verify the range is approximately 1 hour (3600 seconds)
        time_range = query.end_score - query.start_score
        assert 3599 <= time_range <= 3601  # Allow for tiny timing differences

    def test_query_for_specific_day(self):
        """Test creating a query for a specific day."""
        day_start = datetime(2026, 1, 15, 0, 0, 0)
        day_end = datetime(2026, 1, 15, 23, 59, 59)

        query = TimeWindowQuery(start_time=day_start, end_time=day_end)

        # Should be approximately 24 hours (86399 seconds)
        time_range = query.end_score - query.start_score
        assert 86398 <= time_range <= 86400
