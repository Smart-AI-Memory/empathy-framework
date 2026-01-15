"""Pytest configuration for Empathy Framework tests."""

from pathlib import Path

import pytest


def pytest_configure(config):
    """Configure pytest with custom settings."""
    # Add ini settings dynamically based on markers
    config.addinivalue_line("markers", "unit: Unit tests that import and test modules directly")
    config.addinivalue_line(
        "markers",
        "integration: Integration tests that run via subprocess (no coverage)",
    )


def pytest_collection_modifyitems(config, items):
    """Modify test collection to handle coverage properly."""
    # If running with coverage, only run unit tests unless explicitly requested
    cov_source = getattr(config.option, "cov_source", None)
    if cov_source and not config.option.markexpr:
        skip_integration = pytest.mark.skip(reason="Integration tests don't provide coverage")
        for item in items:
            if "integration" in item.keywords:
                item.add_marker(skip_integration)


@pytest.fixture(autouse=True, scope="function")
def setup_test_environment(tmp_path, monkeypatch, request):
    """Automatically set up test environment for all tests.

    Creates necessary directories (.empathy, .claude, etc.) in the current directory.
    This prevents tests from failing due to missing directories.

    Args:
        tmp_path: pytest fixture providing a temporary directory
        monkeypatch: pytest fixture for modifying environment
        request: pytest request object

    Yields:
        Path: The current working directory with .empathy structure
    """
    # Create .empathy directory structure in current directory
    empathy_dir = Path.cwd() / ".empathy"
    empathy_dir.mkdir(parents=True, exist_ok=True)

    # Create subdirectories that might be needed
    (empathy_dir / "cost_tracking").mkdir(exist_ok=True)
    (empathy_dir / "telemetry").mkdir(exist_ok=True)
    (empathy_dir / "patterns").mkdir(exist_ok=True)

    # Create .claude directory if needed
    claude_dir = Path.cwd() / ".claude"
    claude_dir.mkdir(parents=True, exist_ok=True)

    yield Path.cwd()
