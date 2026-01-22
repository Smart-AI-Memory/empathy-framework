"""Tests for atomic pattern promotion in short-term memory.

Atomic promotion uses Redis transactions (MULTI/EXEC) to ensure:
- Pattern exists and meets confidence threshold
- Pattern is removed from staging atomically
- No race conditions with concurrent operations

These tests cover:
- Successful promotion
- Confidence threshold validation
- Permission requirements
- Error handling
"""

import pytest

from empathy_os.memory.short_term import (
    AccessTier,
    AgentCredentials,
    RedisShortTermMemory,
    StagedPattern,
)


@pytest.mark.unit
class TestAtomicPromotePattern:
    """Test atomic pattern promotion with validation."""

    @pytest.fixture
    def memory(self):
        """Create a fresh memory instance for each test."""
        return RedisShortTermMemory(use_mock=True)

    @pytest.fixture
    def validator_creds(self):
        """Validator credentials (can promote patterns)."""
        return AgentCredentials("validator_agent", AccessTier.VALIDATOR)

    @pytest.fixture
    def contributor_creds(self):
        """Contributor credentials (can stage but not promote)."""
        return AgentCredentials("contributor_agent", AccessTier.CONTRIBUTOR)

    @pytest.fixture
    def steward_creds(self):
        """Steward credentials (full admin access)."""
        return AgentCredentials("steward_agent", AccessTier.STEWARD)

    def _stage_pattern(self, memory, contributor_creds, pattern_id, confidence=0.85):
        """Helper to stage a pattern for testing."""
        pattern = StagedPattern(
            pattern_id=pattern_id,
            agent_id="contributor_agent",
            pattern_type="bug_detection",
            name="Test Pattern",
            description="A test pattern for atomic promotion",
            confidence=confidence,
        )
        memory.stage_pattern(pattern, contributor_creds)
        return pattern

    # =========================================================================
    # Successful promotion tests
    # =========================================================================

    def test_atomic_promote_success(self, memory, validator_creds, contributor_creds):
        """Test successful atomic pattern promotion."""
        # Stage a pattern
        self._stage_pattern(memory, contributor_creds, "pat_atomic_001", confidence=0.85)

        # Promote atomically
        success, promoted_pattern, message = memory.atomic_promote_pattern(
            "pat_atomic_001",
            validator_creds,
            min_confidence=0.5
        )

        assert success is True
        assert promoted_pattern is not None
        assert promoted_pattern.pattern_id == "pat_atomic_001"
        assert "successfully" in message

    def test_atomic_promote_removes_from_staging(self, memory, validator_creds, contributor_creds):
        """Test that promotion removes pattern from staging."""
        self._stage_pattern(memory, contributor_creds, "pat_remove_001", confidence=0.85)

        # Verify pattern is staged
        staged = memory.get_staged_pattern("pat_remove_001", validator_creds)
        assert staged is not None

        # Promote
        success, _, _ = memory.atomic_promote_pattern(
            "pat_remove_001",
            validator_creds,
            min_confidence=0.5
        )

        assert success is True

        # Pattern should be removed from staging
        staged = memory.get_staged_pattern("pat_remove_001", validator_creds)
        assert staged is None

    def test_atomic_promote_returns_correct_pattern(self, memory, validator_creds, contributor_creds):
        """Test that promotion returns the correct pattern data."""
        pattern = StagedPattern(
            pattern_id="pat_data_001",
            agent_id="contributor_agent",
            pattern_type="security",
            name="SQL Injection Detector",
            description="Detects SQL injection vulnerabilities",
            code="if 'SELECT' in user_input:",
            confidence=0.92,
            interests=["security", "database"],
        )
        memory.stage_pattern(pattern, contributor_creds)

        success, promoted, _ = memory.atomic_promote_pattern(
            "pat_data_001",
            validator_creds,
            min_confidence=0.5
        )

        assert success is True
        assert promoted.pattern_type == "security"
        assert promoted.name == "SQL Injection Detector"
        assert promoted.confidence == 0.92
        assert "security" in promoted.interests

    def test_atomic_promote_steward_can_promote(self, memory, steward_creds, contributor_creds):
        """Test that STEWARD tier can also promote patterns."""
        self._stage_pattern(memory, contributor_creds, "pat_steward_001", confidence=0.85)

        success, pattern, message = memory.atomic_promote_pattern(
            "pat_steward_001",
            steward_creds,
            min_confidence=0.5
        )

        assert success is True
        assert pattern is not None

    # =========================================================================
    # Confidence threshold tests
    # =========================================================================

    def test_atomic_promote_below_confidence_threshold(
        self, memory, validator_creds, contributor_creds
    ):
        """Test promotion fails when confidence below threshold."""
        self._stage_pattern(memory, contributor_creds, "pat_low_conf", confidence=0.3)

        success, promoted_pattern, message = memory.atomic_promote_pattern(
            "pat_low_conf",
            validator_creds,
            min_confidence=0.7  # Higher threshold
        )

        assert success is False
        assert promoted_pattern is None
        assert "below threshold" in message

    def test_atomic_promote_pattern_stays_staged_on_failure(
        self, memory, validator_creds, contributor_creds
    ):
        """Test that pattern stays staged when promotion fails."""
        self._stage_pattern(memory, contributor_creds, "pat_stay_staged", confidence=0.3)

        # Try to promote with high threshold
        success, _, _ = memory.atomic_promote_pattern(
            "pat_stay_staged",
            validator_creds,
            min_confidence=0.8
        )

        assert success is False

        # Pattern should still be staged
        staged = memory.get_staged_pattern("pat_stay_staged", validator_creds)
        assert staged is not None

    def test_atomic_promote_exact_confidence_threshold(
        self, memory, validator_creds, contributor_creds
    ):
        """Test promotion succeeds when confidence equals threshold."""
        self._stage_pattern(memory, contributor_creds, "pat_exact", confidence=0.7)

        success, pattern, _ = memory.atomic_promote_pattern(
            "pat_exact",
            validator_creds,
            min_confidence=0.7  # Exact match
        )

        assert success is True
        assert pattern is not None

    def test_atomic_promote_zero_confidence_threshold(
        self, memory, validator_creds, contributor_creds
    ):
        """Test promotion with zero confidence threshold (accepts all)."""
        self._stage_pattern(memory, contributor_creds, "pat_zero", confidence=0.1)

        success, pattern, _ = memory.atomic_promote_pattern(
            "pat_zero",
            validator_creds,
            min_confidence=0.0
        )

        assert success is True

    def test_atomic_promote_max_confidence_threshold(
        self, memory, validator_creds, contributor_creds
    ):
        """Test promotion with maximum confidence threshold."""
        self._stage_pattern(memory, contributor_creds, "pat_max", confidence=1.0)

        success, pattern, _ = memory.atomic_promote_pattern(
            "pat_max",
            validator_creds,
            min_confidence=1.0
        )

        assert success is True

    # =========================================================================
    # Permission tests
    # =========================================================================

    def test_atomic_promote_requires_validator_tier(
        self, memory, contributor_creds
    ):
        """Test that only VALIDATOR+ can promote patterns."""
        pattern = StagedPattern(
            pattern_id="pat_no_perm",
            agent_id="contributor_agent",
            pattern_type="test",
            name="Test",
            description="Test",
            confidence=0.9,
        )
        memory.stage_pattern(pattern, contributor_creds)

        success, promoted_pattern, message = memory.atomic_promote_pattern(
            "pat_no_perm",
            contributor_creds,  # Not validator tier
            min_confidence=0.5
        )

        assert success is False
        assert promoted_pattern is None
        assert "VALIDATOR tier or higher" in message

    def test_atomic_promote_observer_cannot_promote(self, memory, contributor_creds):
        """Test that OBSERVER tier cannot promote patterns."""
        self._stage_pattern(memory, contributor_creds, "pat_observer", confidence=0.9)

        observer = AgentCredentials("observer", AccessTier.OBSERVER)

        success, pattern, message = memory.atomic_promote_pattern(
            "pat_observer",
            observer,
            min_confidence=0.5
        )

        assert success is False
        assert "VALIDATOR tier or higher" in message

    # =========================================================================
    # Error handling tests
    # =========================================================================

    def test_atomic_promote_nonexistent_pattern(self, memory, validator_creds):
        """Test promotion fails for nonexistent pattern."""
        success, promoted_pattern, message = memory.atomic_promote_pattern(
            "nonexistent_pattern",
            validator_creds,
            min_confidence=0.5
        )

        assert success is False
        assert promoted_pattern is None
        assert "not found" in message

    def test_atomic_promote_empty_pattern_id_raises_value_error(
        self, memory, validator_creds
    ):
        """Test empty pattern_id raises ValueError."""
        with pytest.raises(ValueError, match="pattern_id cannot be empty"):
            memory.atomic_promote_pattern("", validator_creds)

    def test_atomic_promote_whitespace_pattern_id_raises_value_error(
        self, memory, validator_creds
    ):
        """Test whitespace-only pattern_id raises ValueError."""
        with pytest.raises(ValueError, match="pattern_id cannot be empty"):
            memory.atomic_promote_pattern("   ", validator_creds)

    def test_atomic_promote_confidence_above_one_raises_value_error(
        self, memory, validator_creds
    ):
        """Test min_confidence > 1.0 raises ValueError."""
        with pytest.raises(ValueError, match="min_confidence must be between"):
            memory.atomic_promote_pattern(
                "pat_001",
                validator_creds,
                min_confidence=1.5  # Invalid: > 1.0
            )

    def test_atomic_promote_negative_confidence_raises_value_error(
        self, memory, validator_creds
    ):
        """Test min_confidence < 0.0 raises ValueError."""
        with pytest.raises(ValueError, match="min_confidence must be between"):
            memory.atomic_promote_pattern(
                "pat_001",
                validator_creds,
                min_confidence=-0.1  # Invalid: < 0.0
            )

    # =========================================================================
    # Integration scenarios
    # =========================================================================

    def test_promote_multiple_patterns_sequentially(
        self, memory, validator_creds, contributor_creds
    ):
        """Test promoting multiple patterns one after another."""
        # Stage multiple patterns
        for i in range(5):
            self._stage_pattern(
                memory, contributor_creds, f"pat_multi_{i}", confidence=0.8
            )

        # Promote all of them
        promoted_count = 0
        for i in range(5):
            success, _, _ = memory.atomic_promote_pattern(
                f"pat_multi_{i}",
                validator_creds,
                min_confidence=0.5
            )
            if success:
                promoted_count += 1

        assert promoted_count == 5

        # Verify all are removed from staging
        for i in range(5):
            staged = memory.get_staged_pattern(f"pat_multi_{i}", validator_creds)
            assert staged is None

    def test_mixed_promotion_results(self, memory, validator_creds, contributor_creds):
        """Test mixed promotion results based on confidence."""
        # Stage patterns with different confidence levels
        confidences = [0.3, 0.5, 0.7, 0.9, 0.4]
        threshold = 0.6

        for i, conf in enumerate(confidences):
            self._stage_pattern(
                memory, contributor_creds, f"pat_mixed_{i}", confidence=conf
            )

        # Try to promote all with threshold 0.6
        results = []
        for i in range(5):
            success, _, _ = memory.atomic_promote_pattern(
                f"pat_mixed_{i}",
                validator_creds,
                min_confidence=threshold
            )
            results.append(success)

        # Only patterns with confidence >= 0.6 should succeed
        # Index 2 (0.7) and 3 (0.9) should succeed
        assert results == [False, False, True, True, False]

    def test_idempotent_promotion_fails_on_second_attempt(
        self, memory, validator_creds, contributor_creds
    ):
        """Test that promoting the same pattern twice fails the second time."""
        self._stage_pattern(memory, contributor_creds, "pat_once", confidence=0.85)

        # First promotion succeeds
        success1, _, msg1 = memory.atomic_promote_pattern(
            "pat_once",
            validator_creds,
            min_confidence=0.5
        )

        assert success1 is True
        assert "successfully" in msg1

        # Second promotion fails (pattern no longer staged)
        success2, _, msg2 = memory.atomic_promote_pattern(
            "pat_once",
            validator_creds,
            min_confidence=0.5
        )

        assert success2 is False
        assert "not found" in msg2
