"""Pytest configuration and fixtures for Socratic integration tests.

Copyright 2026 Smart-AI-Memory
Licensed under Fair Source License 0.9
"""

import pytest
from pathlib import Path


@pytest.fixture
def integration_storage_path(tmp_path):
    """Provide a temporary storage path for integration tests."""
    storage_dir = tmp_path / "integration_storage"
    storage_dir.mkdir(parents=True, exist_ok=True)
    return storage_dir


@pytest.fixture
def integration_builder(integration_storage_path):
    """Provide a configured SocraticWorkflowBuilder for integration tests."""
    from empathy_os.socratic import SocraticWorkflowBuilder

    return SocraticWorkflowBuilder(
        storage_path=integration_storage_path / "builder.json"
    )
