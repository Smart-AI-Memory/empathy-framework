"""Pytest configuration for models module tests.

Provides shared fixtures for model testing.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture
def mock_anthropic_client():
    """Create mock Anthropic client for testing.

    Returns:
        MagicMock configured as Anthropic client
    """
    mock = MagicMock()
    mock.messages = MagicMock()
    mock.messages.create = AsyncMock(
        return_value=MagicMock(
            content=[MagicMock(text="Mock LLM response")],
            usage=MagicMock(input_tokens=100, output_tokens=50),
        )
    )
    return mock


@pytest.fixture
def sample_model_config():
    """Sample model configuration for testing.

    Returns:
        Dict with model configuration
    """
    return {
        "provider": "anthropic",
        "model": "claude-3-haiku-20240307",
        "max_tokens": 4096,
        "temperature": 0.7,
    }


@pytest.fixture
def sample_tier_config():
    """Sample tier configuration for testing.

    Returns:
        Dict with tier routing configuration
    """
    return {
        "cheap": {
            "model": "claude-3-haiku-20240307",
            "max_tokens": 2048,
            "cost_per_1k_input": 0.00025,
            "cost_per_1k_output": 0.00125,
        },
        "capable": {
            "model": "claude-3-5-sonnet-20241022",
            "max_tokens": 4096,
            "cost_per_1k_input": 0.003,
            "cost_per_1k_output": 0.015,
        },
        "premium": {
            "model": "claude-3-opus-20240229",
            "max_tokens": 4096,
            "cost_per_1k_input": 0.015,
            "cost_per_1k_output": 0.075,
        },
    }
