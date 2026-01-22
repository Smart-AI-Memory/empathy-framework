"""Pytest configuration for workflow tests.

Provides shared fixtures for workflow testing with proper isolation.
"""

import pytest

from empathy_os.cost_tracker import CostTracker


@pytest.fixture
def cost_tracker(tmp_path):
    """Create isolated CostTracker for testing.

    Uses tmp_path to ensure tests don't interfere with each other
    or pollute the project directory.

    Args:
        tmp_path: pytest fixture providing temporary directory

    Returns:
        CostTracker instance with isolated storage
    """
    storage_dir = tmp_path / ".empathy"
    return CostTracker(storage_dir=str(storage_dir))


@pytest.fixture
def security_audit_workflow(cost_tracker):
    """Create SecurityAuditWorkflow with isolated storage.

    Args:
        cost_tracker: Isolated CostTracker fixture

    Returns:
        SecurityAuditWorkflow instance ready for testing
    """
    from empathy_os.workflows.security_audit import SecurityAuditWorkflow

    return SecurityAuditWorkflow(cost_tracker=cost_tracker)


@pytest.fixture
def code_review_workflow(cost_tracker):
    """Create CodeReviewWorkflow with isolated storage.

    Args:
        cost_tracker: Isolated CostTracker fixture

    Returns:
        CodeReviewWorkflow instance ready for testing
    """
    from empathy_os.workflows.code_review import CodeReviewWorkflow

    return CodeReviewWorkflow(cost_tracker=cost_tracker)


@pytest.fixture
def bug_predict_workflow(cost_tracker):
    """Create BugPredictWorkflow with isolated storage.

    Args:
        cost_tracker: Isolated CostTracker fixture

    Returns:
        BugPredictWorkflow instance ready for testing
    """
    from empathy_os.workflows.bug_predict import BugPredictionWorkflow

    return BugPredictionWorkflow(cost_tracker=cost_tracker)


@pytest.fixture
def dependency_check_workflow(cost_tracker):
    """Create DependencyCheckWorkflow with isolated storage.

    Args:
        cost_tracker: Isolated CostTracker fixture

    Returns:
        DependencyCheckWorkflow instance ready for testing
    """
    from empathy_os.workflows.dependency_check import DependencyCheckWorkflow

    return DependencyCheckWorkflow(cost_tracker=cost_tracker)
