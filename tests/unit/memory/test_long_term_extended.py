"""Extended tests for long-term memory module.

These tests cover additional functionality not in test_long_term_methods.py:
- LongTermMemory class (store, retrieve, delete, list_keys, clear)
- EncryptionManager (when cryptography is available)
- SecureMemDocsIntegration get_statistics and list_patterns
"""

import os
from datetime import datetime

import pytest

from empathy_os.memory.long_term import (
    HAS_ENCRYPTION,
    Classification,
    EncryptionManager,
    LongTermMemory,
    MemDocsStorage,
    SecureMemDocsIntegration,
    SecurityError,
)

# =============================================================================
# LongTermMemory Tests
# =============================================================================


@pytest.mark.unit
class TestLongTermMemoryBasics:
    """Test basic LongTermMemory operations."""

    @pytest.fixture
    def memory(self, tmp_path):
        """Create a LongTermMemory instance with a temp directory."""
        return LongTermMemory(storage_path=str(tmp_path / "ltm_storage"))

    def test_store_and_retrieve_simple_data(self, memory):
        """Test storing and retrieving simple data."""
        data = {"message": "Hello, World!", "count": 42}

        success = memory.store("test_key", data)
        assert success is True

        retrieved = memory.retrieve("test_key")
        assert retrieved == data

    def test_store_with_classification(self, memory):
        """Test storing data with explicit classification."""
        data = {"sensitive_info": "classified"}

        success = memory.store(
            "classified_key",
            data,
            classification=Classification.INTERNAL
        )
        assert success is True

        retrieved = memory.retrieve("classified_key")
        assert retrieved == data

    def test_retrieve_nonexistent_key_returns_none(self, memory):
        """Test retrieving a nonexistent key returns None."""
        result = memory.retrieve("nonexistent_key")
        assert result is None

    def test_store_complex_nested_data(self, memory):
        """Test storing complex nested data structures."""
        complex_data = {
            "analysis": {
                "patterns": [
                    {"id": "p1", "confidence": 0.9},
                    {"id": "p2", "confidence": 0.7},
                ],
                "metrics": {
                    "total": 100,
                    "passed": 95,
                    "coverage": 85.5,
                },
            },
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "version": "1.0.0",
            },
        }

        success = memory.store("complex_key", complex_data)
        assert success is True

        retrieved = memory.retrieve("complex_key")
        assert retrieved["analysis"]["patterns"][0]["id"] == "p1"
        assert retrieved["analysis"]["metrics"]["coverage"] == 85.5

    def test_store_overwrites_existing_data(self, memory):
        """Test that storing with same key overwrites."""
        memory.store("overwrite_key", {"version": 1})
        memory.store("overwrite_key", {"version": 2})

        retrieved = memory.retrieve("overwrite_key")
        assert retrieved["version"] == 2


@pytest.mark.unit
class TestLongTermMemoryDelete:
    """Test LongTermMemory delete operations."""

    @pytest.fixture
    def memory(self, tmp_path):
        return LongTermMemory(storage_path=str(tmp_path / "ltm_delete"))

    def test_delete_existing_key(self, memory):
        """Test deleting an existing key."""
        memory.store("delete_me", {"data": "test"})

        result = memory.delete("delete_me")
        assert result is True

        # Verify it's gone
        assert memory.retrieve("delete_me") is None

    def test_delete_nonexistent_key(self, memory):
        """Test deleting a nonexistent key returns False."""
        result = memory.delete("nonexistent")
        assert result is False

    def test_delete_and_re_store(self, memory):
        """Test that a key can be deleted and re-stored."""
        memory.store("recycle_key", {"data": "original"})
        memory.delete("recycle_key")
        memory.store("recycle_key", {"data": "new"})

        retrieved = memory.retrieve("recycle_key")
        assert retrieved["data"] == "new"


@pytest.mark.unit
class TestLongTermMemoryListKeys:
    """Test LongTermMemory list_keys operations."""

    @pytest.fixture
    def memory(self, tmp_path):
        return LongTermMemory(storage_path=str(tmp_path / "ltm_list"))

    def test_list_keys_empty_storage(self, memory):
        """Test listing keys on empty storage."""
        keys = memory.list_keys()
        assert keys == []

    def test_list_keys_returns_all_keys(self, memory):
        """Test listing all stored keys."""
        memory.store("key_a", {"data": "a"})
        memory.store("key_b", {"data": "b"})
        memory.store("key_c", {"data": "c"})

        keys = memory.list_keys()

        assert len(keys) == 3
        assert "key_a" in keys
        assert "key_b" in keys
        assert "key_c" in keys

    def test_list_keys_with_classification_filter(self, memory):
        """Test filtering keys by classification."""
        memory.store("public_key", {"data": "public"}, classification=Classification.PUBLIC)
        memory.store("internal_key", {"data": "internal"}, classification=Classification.INTERNAL)
        memory.store("sensitive_key", {"data": "sensitive"}, classification=Classification.SENSITIVE)

        # Filter by PUBLIC
        public_keys = memory.list_keys(classification=Classification.PUBLIC)
        assert "public_key" in public_keys
        assert "internal_key" not in public_keys

    def test_list_keys_after_deletion(self, memory):
        """Test that deleted keys don't appear in list."""
        memory.store("keep_key", {"data": "keep"})
        memory.store("delete_key", {"data": "delete"})

        memory.delete("delete_key")

        keys = memory.list_keys()
        assert "keep_key" in keys
        assert "delete_key" not in keys


@pytest.mark.unit
class TestLongTermMemoryClear:
    """Test LongTermMemory clear operations."""

    @pytest.fixture
    def memory(self, tmp_path):
        return LongTermMemory(storage_path=str(tmp_path / "ltm_clear"))

    def test_clear_removes_all_keys(self, memory):
        """Test clear() removes all stored data."""
        # Store multiple items
        for i in range(5):
            memory.store(f"key_{i}", {"value": i})

        # Verify stored
        assert len(memory.list_keys()) == 5

        # Clear
        count = memory.clear()

        # Verify cleared
        assert count == 5
        assert len(memory.list_keys()) == 0

    def test_clear_returns_count_of_deleted(self, memory):
        """Test clear() returns accurate count of deleted items."""
        memory.store("key1", {"a": 1})
        memory.store("key2", {"b": 2})
        memory.store("key3", {"c": 3})

        count = memory.clear()

        assert count == 3

    def test_clear_empty_storage_returns_zero(self, memory):
        """Test clear() on empty storage returns 0."""
        count = memory.clear()
        assert count == 0

    def test_operations_work_after_clear(self, memory):
        """Test that storage is usable after clear()."""
        memory.store("before_clear", {"data": "old"})
        memory.clear()

        # Should be able to store new data
        success = memory.store("after_clear", {"data": "new"})
        assert success is True

        # Should be able to retrieve
        retrieved = memory.retrieve("after_clear")
        assert retrieved == {"data": "new"}


# =============================================================================
# EncryptionManager Tests
# =============================================================================


@pytest.mark.unit
@pytest.mark.skipif(not HAS_ENCRYPTION, reason="cryptography not installed")
class TestEncryptionManager:
    """Test AES-256-GCM encryption functionality."""

    def test_encrypt_decrypt_roundtrip(self):
        """Test that encryption and decryption produce original data."""
        manager = EncryptionManager()

        plaintext = "This is sensitive patient data"

        encrypted = manager.encrypt(plaintext)
        decrypted = manager.decrypt(encrypted)

        assert decrypted == plaintext

    def test_encrypted_data_differs_from_plaintext(self):
        """Test that encrypted data is different from plaintext."""
        manager = EncryptionManager()

        plaintext = "Secret message"
        encrypted = manager.encrypt(plaintext)

        assert encrypted != plaintext
        assert plaintext not in encrypted

    def test_each_encryption_produces_unique_ciphertext(self):
        """Test encrypting same plaintext produces different ciphertext (random nonce)."""
        manager = EncryptionManager()

        plaintext = "Same message"

        encrypted1 = manager.encrypt(plaintext)
        encrypted2 = manager.encrypt(plaintext)

        # Different nonces should produce different ciphertext
        assert encrypted1 != encrypted2

        # Both should decrypt to same plaintext
        assert manager.decrypt(encrypted1) == plaintext
        assert manager.decrypt(encrypted2) == plaintext

    def test_decrypt_with_wrong_key_raises_security_error(self):
        """Test decryption with wrong key fails."""
        manager1 = EncryptionManager(master_key=os.urandom(32))
        manager2 = EncryptionManager(master_key=os.urandom(32))

        plaintext = "Secret data"
        encrypted = manager1.encrypt(plaintext)

        with pytest.raises(SecurityError, match="Decryption failed"):
            manager2.decrypt(encrypted)

    def test_decrypt_corrupted_ciphertext_raises_security_error(self):
        """Test decryption of corrupted data fails safely."""
        manager = EncryptionManager()

        plaintext = "Test data"
        encrypted = manager.encrypt(plaintext)

        # Corrupt the ciphertext
        corrupted = encrypted[:-5] + "XXXXX"

        with pytest.raises(SecurityError, match="Decryption failed"):
            manager.decrypt(corrupted)

    def test_encrypt_unicode_content(self):
        """Test encryption handles Unicode correctly."""
        manager = EncryptionManager()

        unicode_text = "Patient data - 患者数据 🏥"

        encrypted = manager.encrypt(unicode_text)
        decrypted = manager.decrypt(encrypted)

        assert decrypted == unicode_text

    def test_encrypt_empty_string(self):
        """Test encryption handles empty string."""
        manager = EncryptionManager()

        encrypted = manager.encrypt("")
        decrypted = manager.decrypt(encrypted)

        assert decrypted == ""

    def test_encryption_manager_enabled(self):
        """Test enabled property is True when cryptography available."""
        manager = EncryptionManager()
        assert manager.enabled is True


@pytest.mark.unit
@pytest.mark.skipif(HAS_ENCRYPTION, reason="Test for when cryptography not installed")
class TestEncryptionManagerWithoutCryptography:
    """Test EncryptionManager behavior when cryptography is not installed."""

    def test_encryption_disabled_flag(self):
        """Test enabled flag is False when cryptography unavailable."""
        manager = EncryptionManager()
        assert manager.enabled is False


# =============================================================================
# SecureMemDocsIntegration Tests
# =============================================================================


@pytest.mark.unit
class TestSecureMemDocsStatistics:
    """Test get_statistics() method."""

    @pytest.fixture
    def integration(self, tmp_path):
        return SecureMemDocsIntegration(
            storage_dir=str(tmp_path / "storage"),
            audit_log_dir=str(tmp_path / "audit"),
            enable_encryption=False,
        )

    def test_statistics_empty_storage(self, integration):
        """Test statistics with no stored patterns."""
        stats = integration.get_statistics()

        assert stats["total_patterns"] == 0
        assert stats["by_classification"]["PUBLIC"] == 0
        assert stats["by_classification"]["INTERNAL"] == 0
        assert stats["by_classification"]["SENSITIVE"] == 0

    def test_statistics_counts_patterns(self, integration):
        """Test statistics counts patterns correctly."""
        # Store some patterns
        integration.store_pattern(
            "Pattern 1 content",
            "tutorial",
            "user1@example.com",
            explicit_classification=Classification.PUBLIC
        )
        integration.store_pattern(
            "Pattern 2 content",
            "architecture",
            "user1@example.com",
            explicit_classification=Classification.INTERNAL
        )

        stats = integration.get_statistics()

        assert stats["total_patterns"] == 2

    def test_statistics_counts_by_classification(self, integration):
        """Test statistics correctly counts patterns by classification."""
        integration.store_pattern(
            "Public 1", "tutorial", "user@test.com",
            explicit_classification=Classification.PUBLIC
        )
        integration.store_pattern(
            "Public 2", "tutorial", "user@test.com",
            explicit_classification=Classification.PUBLIC
        )
        integration.store_pattern(
            "Internal 1", "architecture", "user@test.com",
            explicit_classification=Classification.INTERNAL
        )

        stats = integration.get_statistics()

        assert stats["by_classification"]["PUBLIC"] == 2
        assert stats["by_classification"]["INTERNAL"] == 1
        assert stats["by_classification"]["SENSITIVE"] == 0


@pytest.mark.unit
class TestSecureMemDocsListPatterns:
    """Test list_patterns() method with various filters."""

    @pytest.fixture
    def integration_with_patterns(self, tmp_path):
        """Create integration with pre-populated patterns."""
        integration = SecureMemDocsIntegration(
            storage_dir=str(tmp_path / "storage"),
            audit_log_dir=str(tmp_path / "audit"),
            enable_encryption=False,
        )

        # Store patterns with different classifications and types
        integration.store_pattern(
            "Tutorial content",
            "tutorial",
            "user1@example.com",
            explicit_classification=Classification.PUBLIC
        )
        integration.store_pattern(
            "Architecture diagram",
            "architecture",
            "user2@example.com",
            explicit_classification=Classification.INTERNAL
        )
        integration.store_pattern(
            "API documentation",
            "api_docs",
            "user1@example.com",
            explicit_classification=Classification.INTERNAL
        )

        return integration

    def test_list_patterns_returns_all(self, integration_with_patterns):
        """Test listing all accessible patterns."""
        patterns = integration_with_patterns.list_patterns("user1@example.com")

        # Should see PUBLIC and INTERNAL patterns
        assert len(patterns) >= 2

    def test_list_patterns_filter_by_classification(self, integration_with_patterns):
        """Test filtering patterns by classification."""
        patterns = integration_with_patterns.list_patterns(
            "user1@example.com",
            classification=Classification.PUBLIC
        )

        for pattern in patterns:
            assert pattern["classification"] == "PUBLIC"

    def test_list_patterns_filter_by_pattern_type(self, integration_with_patterns):
        """Test filtering patterns by pattern_type."""
        patterns = integration_with_patterns.list_patterns(
            "user1@example.com",
            pattern_type="architecture"
        )

        for pattern in patterns:
            assert pattern["pattern_type"] == "architecture"


# =============================================================================
# MemDocsStorage Tests
# =============================================================================


@pytest.mark.unit
class TestMemDocsStorage:
    """Test MemDocsStorage basic operations."""

    @pytest.fixture
    def storage(self, tmp_path):
        return MemDocsStorage(storage_dir=str(tmp_path / "memdocs"))

    def test_store_and_retrieve(self, storage):
        """Test basic store and retrieve."""
        content = "This is test content"
        metadata = {"type": "test", "created": "2026-01-21"}

        success = storage.store("test_pattern", content, metadata)
        assert success is True

        result = storage.retrieve("test_pattern")
        assert result is not None
        assert result["content"] == content
        assert result["metadata"]["type"] == "test"

    def test_retrieve_nonexistent(self, storage):
        """Test retrieving nonexistent pattern."""
        result = storage.retrieve("nonexistent")
        assert result is None

    def test_delete_pattern(self, storage):
        """Test deleting a pattern."""
        storage.store("delete_me", "content", {"type": "test"})

        result = storage.delete("delete_me")
        assert result is True

        # Verify it's gone
        assert storage.retrieve("delete_me") is None

    def test_delete_nonexistent(self, storage):
        """Test deleting nonexistent pattern returns False."""
        result = storage.delete("nonexistent")
        assert result is False

    def test_list_patterns(self, storage):
        """Test listing patterns."""
        storage.store("pattern_1", "content 1", {"type": "a"})
        storage.store("pattern_2", "content 2", {"type": "b"})
        storage.store("pattern_3", "content 3", {"type": "a"})

        # List all
        patterns = storage.list_patterns()
        assert len(patterns) == 3

    def test_list_patterns_with_classification_filter(self, storage):
        """Test listing patterns with classification filter."""
        storage.store("pattern_1", "content 1", {"classification": "PUBLIC"})
        storage.store("pattern_2", "content 2", {"classification": "INTERNAL"})
        storage.store("pattern_3", "content 3", {"classification": "PUBLIC"})

        patterns = storage.list_patterns(classification="PUBLIC")
        assert len(patterns) == 2

    def test_list_patterns_with_created_by_filter(self, storage):
        """Test listing patterns with created_by filter."""
        storage.store("pattern_1", "content 1", {"created_by": "user_a"})
        storage.store("pattern_2", "content 2", {"created_by": "user_b"})
        storage.store("pattern_3", "content 3", {"created_by": "user_a"})

        patterns = storage.list_patterns(created_by="user_a")
        assert len(patterns) == 2

    def test_list_patterns_combined_filters(self, storage):
        """Test listing patterns with multiple filters."""
        storage.store("pattern_1", "content 1", {"classification": "PUBLIC", "created_by": "user_a"})
        storage.store("pattern_2", "content 2", {"classification": "PUBLIC", "created_by": "user_b"})
        storage.store("pattern_3", "content 3", {"classification": "INTERNAL", "created_by": "user_a"})

        patterns = storage.list_patterns(classification="PUBLIC", created_by="user_a")
        assert len(patterns) == 1


# =============================================================================
# EncryptionManager Tests (with mocking)
# =============================================================================


@pytest.mark.unit
class TestEncryptionManagerWithMocking:
    """Test EncryptionManager behavior with mocked cryptography."""

    def test_encryption_disabled_when_library_unavailable(self):
        """Test EncryptionManager.enabled is False when cryptography unavailable."""
        manager = EncryptionManager()
        # If HAS_ENCRYPTION is False, manager.enabled should be False
        if not HAS_ENCRYPTION:
            assert manager.enabled is False

    def test_encrypt_raises_when_disabled(self):
        """Test encrypt raises SecurityError when disabled."""
        manager = EncryptionManager()
        if not manager.enabled:
            with pytest.raises(SecurityError, match="Encryption not available"):
                manager.encrypt("test data")

    def test_decrypt_raises_when_disabled(self):
        """Test decrypt raises SecurityError when disabled."""
        manager = EncryptionManager()
        if not manager.enabled:
            with pytest.raises(SecurityError, match="Encryption not available"):
                manager.decrypt("test_ciphertext")

    @pytest.mark.skipif(not HAS_ENCRYPTION, reason="cryptography library required")
    def test_encrypt_decrypt_roundtrip(self):
        """Test encrypt/decrypt roundtrip when cryptography is available."""
        manager = EncryptionManager()
        plaintext = "Sensitive data to encrypt"

        ciphertext = manager.encrypt(plaintext)
        assert ciphertext != plaintext

        decrypted = manager.decrypt(ciphertext)
        assert decrypted == plaintext

    @pytest.mark.skipif(not HAS_ENCRYPTION, reason="cryptography library required")
    def test_encrypt_with_custom_key(self):
        """Test encryption with custom master key."""
        # Generate a valid 32-byte key
        import os
        custom_key = os.urandom(32)
        manager = EncryptionManager(master_key=custom_key)

        plaintext = "Test with custom key"
        ciphertext = manager.encrypt(plaintext)
        decrypted = manager.decrypt(ciphertext)

        assert decrypted == plaintext


# =============================================================================
# SecureMemDocsIntegration Additional Tests
# =============================================================================


@pytest.mark.unit
class TestSecureMemDocsIntegrationEdgeCases:
    """Test edge cases and additional paths in SecureMemDocsIntegration."""

    @pytest.fixture
    def integration(self, tmp_path):
        """Create SecureMemDocsIntegration instance."""
        return SecureMemDocsIntegration(
            storage_dir=str(tmp_path / "memdocs"),
            audit_log_dir=str(tmp_path / "audit"),
            enable_encryption=False,  # Disable to avoid encryption dependency
        )

    def test_store_with_explicit_classification(self, integration):
        """Test storing pattern with explicit classification."""
        result = integration.store_pattern(
            content="Test pattern content",
            pattern_type="test_type",
            user_id="test_user",
            explicit_classification=Classification.PUBLIC,
        )

        assert result["classification"] == "PUBLIC"

    def test_store_with_internal_classification(self, integration):
        """Test storing pattern with INTERNAL classification."""
        result = integration.store_pattern(
            content="Internal document",
            pattern_type="internal_doc",
            user_id="test_user",
            explicit_classification=Classification.INTERNAL,
        )

        assert result["classification"] == "INTERNAL"

    def test_store_with_custom_metadata(self, integration):
        """Test storing pattern with custom metadata."""
        custom_meta = {"project": "test_project", "version": "1.0"}

        result = integration.store_pattern(
            content="Pattern with metadata",
            pattern_type="metadata_test",
            user_id="test_user",
            custom_metadata=custom_meta,
        )

        assert result["pattern_id"] is not None

    def test_retrieve_pattern_with_access_control(self, integration):
        """Test retrieving pattern checks access control."""
        # Store a pattern
        result = integration.store_pattern(
            content="Test content",
            pattern_type="test",
            user_id="owner@test.com",
            explicit_classification=Classification.PUBLIC,
        )

        # Retrieve it
        pattern = integration.retrieve_pattern(
            pattern_id=result["pattern_id"],
            user_id="any_user@test.com",  # PUBLIC allows all users
        )

        assert pattern is not None

    def test_list_patterns_returns_list(self, integration):
        """Test list_patterns returns a list of pattern IDs."""
        # Store a couple patterns
        integration.store_pattern(
            content="Pattern 1",
            pattern_type="test",
            user_id="user1@test.com",
            explicit_classification=Classification.PUBLIC,
        )
        integration.store_pattern(
            content="Pattern 2",
            pattern_type="test",
            user_id="user2@test.com",
            explicit_classification=Classification.PUBLIC,
        )

        patterns = integration.list_patterns(user_id="user1@test.com")
        assert isinstance(patterns, list)
        assert len(patterns) >= 2

    def test_get_statistics(self, integration):
        """Test get_statistics returns statistics dict."""
        # Store some patterns
        integration.store_pattern(
            content="Test pattern",
            pattern_type="stats_test",
            user_id="test_user",
            explicit_classification=Classification.PUBLIC,
        )

        stats = integration.get_statistics()
        assert isinstance(stats, dict)
        assert "total_patterns" in stats


# =============================================================================
# LongTermMemory Edge Cases
# =============================================================================


@pytest.mark.unit
class TestLongTermMemoryEdgeCases:
    """Test edge cases for LongTermMemory."""

    @pytest.fixture
    def memory(self, tmp_path):
        """Create LongTermMemory instance."""
        return LongTermMemory(storage_path=str(tmp_path / "ltm"))

    def test_delete_existing_key(self, memory):
        """Test deleting an existing key."""
        memory.store("delete_test", {"data": "to delete"})

        result = memory.delete("delete_test")
        assert result is True

        # Verify it's gone
        assert memory.retrieve("delete_test") is None

    def test_delete_nonexistent_key(self, memory):
        """Test deleting a nonexistent key returns False."""
        result = memory.delete("nonexistent_key_12345")
        assert result is False

    def test_list_keys_empty(self, memory):
        """Test list_keys returns empty list when no data."""
        keys = memory.list_keys()
        assert keys == []

    def test_list_keys_after_store(self, memory):
        """Test list_keys returns stored keys."""
        memory.store("key1", {"data": 1})
        memory.store("key2", {"data": 2})
        memory.store("key3", {"data": 3})

        keys = memory.list_keys()
        assert len(keys) == 3
        assert "key1" in keys
        assert "key2" in keys
        assert "key3" in keys

    def test_clear_removes_all_data(self, memory):
        """Test clear removes all stored data."""
        memory.store("clear_test_1", {"data": 1})
        memory.store("clear_test_2", {"data": 2})

        memory.clear()

        assert memory.list_keys() == []
        assert memory.retrieve("clear_test_1") is None
        assert memory.retrieve("clear_test_2") is None

    def test_store_with_sensitive_classification(self, memory):
        """Test storing with SENSITIVE classification."""
        result = memory.store(
            "sensitive_key",
            {"secret": "data"},
            classification=Classification.SENSITIVE,
        )

        # Should succeed (even without encryption, stores with warning)
        assert result is True
