"""Pytest configuration for Socratic performance benchmarks.

Copyright 2026 Smart-AI-Memory
Licensed under Fair Source License 0.9
"""

import pytest


@pytest.fixture
def benchmark_storage_path(tmp_path):
    """Provide a temporary storage path for benchmarks."""
    storage_dir = tmp_path / "benchmark_storage"
    storage_dir.mkdir(parents=True, exist_ok=True)
    return storage_dir
