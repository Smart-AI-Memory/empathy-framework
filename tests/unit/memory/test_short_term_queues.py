"""Tests for Redis List-based task queue functionality in short-term memory.

Task queues provide FIFO job processing for agent coordination.
These tests cover:
- queue_push: Adding tasks to queues
- queue_pop: Removing tasks from queues
- queue_length: Getting queue size
- queue_peek: Viewing tasks without removing
- Priority queues (LPUSH vs RPUSH)
- Permission requirements
"""

import pytest

from empathy_os.memory.short_term import (
    AccessTier,
    AgentCredentials,
    RedisShortTermMemory,
)


@pytest.mark.unit
class TestTaskQueues:
    """Test Redis List-based task queue functionality."""

    @pytest.fixture
    def memory(self):
        """Create a fresh memory instance for each test."""
        return RedisShortTermMemory(use_mock=True)

    @pytest.fixture
    def contributor_creds(self):
        """Contributor credentials (can push to queues)."""
        return AgentCredentials("contributor_agent", AccessTier.CONTRIBUTOR)

    @pytest.fixture
    def observer_creds(self):
        """Observer credentials (read-only)."""
        return AgentCredentials("observer_agent", AccessTier.OBSERVER)

    # =========================================================================
    # queue_push tests
    # =========================================================================

    def test_queue_push_returns_queue_length(self, memory, contributor_creds):
        """Test queue_push returns the new queue length."""
        length = memory.queue_push(
            "tasks",
            {"type": "analyze", "file": "main.py"},
            contributor_creds
        )

        assert length == 1

        length = memory.queue_push(
            "tasks",
            {"type": "test", "file": "test_main.py"},
            contributor_creds
        )

        assert length == 2

    def test_queue_push_requires_contributor_tier(self, memory, observer_creds):
        """Test that only CONTRIBUTOR+ can push to queues."""
        with pytest.raises(PermissionError, match="CONTRIBUTOR tier or higher"):
            memory.queue_push("tasks", {"data": "test"}, observer_creds)

    def test_queue_push_priority_adds_to_front(self, memory, contributor_creds):
        """Test priority=True adds task to front of queue."""
        # Add normal tasks
        memory.queue_push("tasks", {"order": 1}, contributor_creds)
        memory.queue_push("tasks", {"order": 2}, contributor_creds)

        # Add priority task
        memory.queue_push(
            "tasks",
            {"order": "priority"},
            contributor_creds,
            priority=True
        )

        # Pop should return priority task first
        task = memory.queue_pop("tasks", contributor_creds)
        assert task["task"]["order"] == "priority"

    def test_queue_push_normal_adds_to_back(self, memory, contributor_creds):
        """Test normal push (priority=False) adds task to back of queue."""
        memory.queue_push("tasks", {"order": 1}, contributor_creds)
        memory.queue_push("tasks", {"order": 2}, contributor_creds)
        memory.queue_push("tasks", {"order": 3}, contributor_creds)

        # Pop should return first task
        task = memory.queue_pop("tasks", contributor_creds)
        assert task["task"]["order"] == 1

    def test_queue_push_adds_metadata(self, memory, contributor_creds):
        """Test that queue_push adds queued_by and queued_at metadata."""
        memory.queue_push("tasks", {"action": "test"}, contributor_creds)

        task = memory.queue_pop("tasks", contributor_creds)

        assert task["queued_by"] == "contributor_agent"
        assert "queued_at" in task

    def test_queue_push_complex_task(self, memory, contributor_creds):
        """Test pushing a complex task with nested data."""
        complex_task = {
            "type": "code_review",
            "files": ["a.py", "b.py", "c.py"],
            "options": {"strict": True, "timeout": 300},
            "metadata": {"priority": "high"},
        }

        length = memory.queue_push("review_tasks", complex_task, contributor_creds)

        assert length == 1

        task = memory.queue_pop("review_tasks", contributor_creds)
        assert task["task"]["type"] == "code_review"
        assert len(task["task"]["files"]) == 3

    # =========================================================================
    # queue_pop tests
    # =========================================================================

    def test_queue_pop_returns_fifo_order(self, memory, contributor_creds):
        """Test queue_pop returns tasks in FIFO order."""
        # Add tasks
        for i in range(3):
            memory.queue_push("fifo_queue", {"index": i}, contributor_creds)

        # Pop should return in order
        for i in range(3):
            task = memory.queue_pop("fifo_queue", contributor_creds)
            assert task["task"]["index"] == i

    def test_queue_pop_empty_returns_none(self, memory, contributor_creds):
        """Test queue_pop on empty queue returns None."""
        result = memory.queue_pop("empty_queue", contributor_creds)
        assert result is None

    def test_queue_pop_removes_item(self, memory, contributor_creds):
        """Test that queue_pop removes the item from the queue."""
        memory.queue_push("pop_test", {"data": "test"}, contributor_creds)

        assert memory.queue_length("pop_test") == 1

        memory.queue_pop("pop_test", contributor_creds)

        assert memory.queue_length("pop_test") == 0

    def test_queue_pop_multiple_items(self, memory, contributor_creds):
        """Test popping multiple items from a queue."""
        for i in range(5):
            memory.queue_push("multi_queue", {"i": i}, contributor_creds)

        # Pop 3 items
        popped = []
        for _ in range(3):
            task = memory.queue_pop("multi_queue", contributor_creds)
            popped.append(task)

        assert len(popped) == 3
        assert memory.queue_length("multi_queue") == 2

    # =========================================================================
    # queue_length tests
    # =========================================================================

    def test_queue_length_returns_correct_count(self, memory, contributor_creds):
        """Test queue_length returns correct number of items."""
        queue_name = "counted_queue"

        assert memory.queue_length(queue_name) == 0

        for i in range(5):
            memory.queue_push(queue_name, {"index": i}, contributor_creds)

        assert memory.queue_length(queue_name) == 5

        memory.queue_pop(queue_name, contributor_creds)

        assert memory.queue_length(queue_name) == 4

    def test_queue_length_empty_queue(self, memory):
        """Test queue_length on empty queue returns 0."""
        assert memory.queue_length("nonexistent_queue") == 0

    def test_queue_length_after_multiple_operations(self, memory, contributor_creds):
        """Test queue_length accuracy after various operations."""
        q = "ops_queue"

        # Add 10 items
        for i in range(10):
            memory.queue_push(q, {"i": i}, contributor_creds)

        assert memory.queue_length(q) == 10

        # Pop 4 items
        for _ in range(4):
            memory.queue_pop(q, contributor_creds)

        assert memory.queue_length(q) == 6

        # Add 2 more
        memory.queue_push(q, {"new": 1}, contributor_creds)
        memory.queue_push(q, {"new": 2}, contributor_creds)

        assert memory.queue_length(q) == 8

    # =========================================================================
    # queue_peek tests
    # =========================================================================

    def test_queue_peek_doesnt_remove_items(self, memory, contributor_creds):
        """Test queue_peek returns items without removing them."""
        queue_name = "peek_queue"

        # Add tasks
        memory.queue_push(queue_name, {"data": "first"}, contributor_creds)
        memory.queue_push(queue_name, {"data": "second"}, contributor_creds)

        # Peek
        peeked = memory.queue_peek(queue_name, contributor_creds, count=2)

        # Items should still be in queue
        assert memory.queue_length(queue_name) == 2
        assert len(peeked) == 2

    def test_queue_peek_returns_front_items(self, memory, contributor_creds):
        """Test queue_peek returns items from front of queue."""
        queue_name = "ordered_queue"

        for i in range(5):
            memory.queue_push(queue_name, {"index": i}, contributor_creds)

        peeked = memory.queue_peek(queue_name, contributor_creds, count=2)

        # Should get first 2 items
        assert len(peeked) == 2
        assert peeked[0]["task"]["index"] == 0
        assert peeked[1]["task"]["index"] == 1

    def test_queue_peek_empty_queue(self, memory, contributor_creds):
        """Test queue_peek on empty queue returns empty list."""
        peeked = memory.queue_peek("empty_peek", contributor_creds, count=5)
        assert peeked == []

    def test_queue_peek_count_larger_than_queue(self, memory, contributor_creds):
        """Test queue_peek when count is larger than queue size."""
        memory.queue_push("small_queue", {"data": 1}, contributor_creds)
        memory.queue_push("small_queue", {"data": 2}, contributor_creds)

        peeked = memory.queue_peek("small_queue", contributor_creds, count=10)

        assert len(peeked) == 2  # Only returns what exists

    def test_queue_peek_default_count_is_one(self, memory, contributor_creds):
        """Test queue_peek with default count."""
        for i in range(3):
            memory.queue_push("default_peek", {"i": i}, contributor_creds)

        peeked = memory.queue_peek("default_peek", contributor_creds)

        assert len(peeked) == 1
        assert peeked[0]["task"]["i"] == 0

    # =========================================================================
    # Integration scenarios
    # =========================================================================

    def test_task_processing_scenario(self, memory, contributor_creds):
        """Test a realistic task processing scenario."""
        queue_name = "processing_queue"

        # Producer adds tasks
        tasks = [
            {"type": "analyze", "file": "main.py"},
            {"type": "analyze", "file": "utils.py"},
            {"type": "test", "module": "tests/"},
        ]

        for task in tasks:
            memory.queue_push(queue_name, task, contributor_creds)

        assert memory.queue_length(queue_name) == 3

        # Consumer processes tasks
        processed = []
        while (task := memory.queue_pop(queue_name, contributor_creds)) is not None:
            processed.append(task["task"])

        assert len(processed) == 3
        assert processed[0]["type"] == "analyze"
        assert processed[2]["type"] == "test"

    def test_priority_queue_scenario(self, memory, contributor_creds):
        """Test priority queue where urgent tasks jump to front."""
        queue_name = "priority_queue"

        # Add normal tasks
        memory.queue_push(queue_name, {"priority": "normal", "id": 1}, contributor_creds)
        memory.queue_push(queue_name, {"priority": "normal", "id": 2}, contributor_creds)
        memory.queue_push(queue_name, {"priority": "normal", "id": 3}, contributor_creds)

        # Add urgent task with priority=True
        memory.queue_push(
            queue_name,
            {"priority": "urgent", "id": "urgent"},
            contributor_creds,
            priority=True
        )

        # Pop - should get urgent first
        task = memory.queue_pop(queue_name, contributor_creds)
        assert task["task"]["priority"] == "urgent"

        # Then normal tasks in order
        task = memory.queue_pop(queue_name, contributor_creds)
        assert task["task"]["id"] == 1

    def test_multiple_queues_isolation(self, memory, contributor_creds):
        """Test that different queues are isolated."""
        # Write to queue A
        memory.queue_push("queue_a", {"source": "a"}, contributor_creds)
        memory.queue_push("queue_a", {"source": "a"}, contributor_creds)

        # Write to queue B
        memory.queue_push("queue_b", {"source": "b"}, contributor_creds)

        assert memory.queue_length("queue_a") == 2
        assert memory.queue_length("queue_b") == 1

        # Pop from A doesn't affect B
        memory.queue_pop("queue_a", contributor_creds)
        assert memory.queue_length("queue_a") == 1
        assert memory.queue_length("queue_b") == 1
