"""Pytest configuration for memory module tests.

Provides shared fixtures for memory testing with proper isolation.
"""

from unittest.mock import MagicMock

import pytest


@pytest.fixture
def temp_memory_dir(tmp_path):
    """Create isolated memory storage directory.

    Args:
        tmp_path: pytest fixture providing temporary directory

    Returns:
        Path to isolated memory storage
    """
    memory_dir = tmp_path / "memory"
    memory_dir.mkdir(parents=True, exist_ok=True)
    return memory_dir


@pytest.fixture
def mock_redis():
    """Create mock Redis client for testing without Redis server.

    Returns:
        MagicMock configured as Redis client
    """
    mock = MagicMock()
    mock.ping.return_value = True
    mock.get.return_value = None
    mock.set.return_value = True
    mock.delete.return_value = 1
    mock.exists.return_value = False
    mock.keys.return_value = []
    return mock


@pytest.fixture
def sample_memory_data():
    """Sample data for memory tests.

    Returns:
        Dict with test data for memory operations
    """
    return {
        "key": "test_pattern",
        "value": {
            "pattern_type": "debugging",
            "context": "test context",
            "solution": "test solution",
            "confidence": 0.85,
        },
        "metadata": {
            "created_at": "2026-01-21T12:00:00Z",
            "updated_at": "2026-01-21T12:00:00Z",
            "access_count": 0,
        },
    }
