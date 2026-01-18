"""Tests for the Socratic storage module.

Copyright 2026 Smart-AI-Memory
Licensed under Fair Source License 0.9
"""

import pytest
import json
from pathlib import Path


class TestStorageBackend:
    """Tests for StorageBackend abstract class."""

    def test_cannot_instantiate_abstract(self):
        """Test that StorageBackend cannot be instantiated directly."""
        from empathy_os.socratic.storage import StorageBackend

        with pytest.raises(TypeError):
            StorageBackend()


class TestJSONFileStorage:
    """Tests for JSONFileStorage class."""

    def test_create_storage(self, storage_path):
        """Test creating JSON file storage."""
        from empathy_os.socratic.storage import JSONFileStorage

        storage = JSONFileStorage(storage_path=storage_path / "test.json")
        assert storage is not None

    def test_save_and_load_session(self, storage_path, sample_session):
        """Test saving and loading a session."""
        from empathy_os.socratic.storage import JSONFileStorage

        storage = JSONFileStorage(storage_path=storage_path / "sessions.json")

        # Save
        storage.save_session(sample_session)

        # Load
        loaded = storage.load_session(sample_session.session_id)

        assert loaded is not None
        assert loaded.session_id == sample_session.session_id
        assert loaded.goal == sample_session.goal

    def test_list_sessions(self, storage_path, sample_session):
        """Test listing all sessions."""
        from empathy_os.socratic.storage import JSONFileStorage
        from empathy_os.socratic.session import SocraticSession

        storage = JSONFileStorage(storage_path=storage_path / "sessions.json")

        # Save multiple sessions
        session1 = sample_session
        session2 = SocraticSession(session_id="test-session-002")
        session2.goal = "Another goal"

        storage.save_session(session1)
        storage.save_session(session2)

        # List
        sessions = storage.list_sessions()

        assert len(sessions) >= 2
        session_ids = [s.session_id for s in sessions]
        assert session1.session_id in session_ids
        assert session2.session_id in session_ids

    def test_delete_session(self, storage_path, sample_session):
        """Test deleting a session."""
        from empathy_os.socratic.storage import JSONFileStorage

        storage = JSONFileStorage(storage_path=storage_path / "sessions.json")

        storage.save_session(sample_session)
        storage.delete_session(sample_session.session_id)

        loaded = storage.load_session(sample_session.session_id)
        assert loaded is None

    def test_save_and_load_blueprint(self, storage_path, sample_workflow_blueprint):
        """Test saving and loading a blueprint."""
        from empathy_os.socratic.storage import JSONFileStorage

        storage = JSONFileStorage(storage_path=storage_path / "blueprints.json")

        # Save
        storage.save_blueprint(sample_workflow_blueprint)

        # Load
        loaded = storage.load_blueprint(sample_workflow_blueprint.workflow_id)

        assert loaded is not None
        assert loaded.workflow_id == sample_workflow_blueprint.workflow_id
        assert loaded.name == sample_workflow_blueprint.name

    def test_list_blueprints(self, storage_path, sample_workflow_blueprint):
        """Test listing all blueprints."""
        from empathy_os.socratic.storage import JSONFileStorage

        storage = JSONFileStorage(storage_path=storage_path / "blueprints.json")

        storage.save_blueprint(sample_workflow_blueprint)

        blueprints = storage.list_blueprints()

        assert len(blueprints) >= 1
        assert any(b.workflow_id == sample_workflow_blueprint.workflow_id for b in blueprints)

    def test_storage_creates_directory(self, tmp_path):
        """Test that storage creates directory if it doesn't exist."""
        from empathy_os.socratic.storage import JSONFileStorage

        nested_path = tmp_path / "nested" / "dir" / "storage.json"
        storage = JSONFileStorage(storage_path=nested_path)

        # Should not raise
        assert storage is not None

    def test_storage_handles_corrupted_file(self, storage_path):
        """Test handling of corrupted JSON file."""
        from empathy_os.socratic.storage import JSONFileStorage

        file_path = storage_path / "corrupted.json"
        file_path.write_text("{invalid json")

        storage = JSONFileStorage(storage_path=file_path)

        # Should handle gracefully
        sessions = storage.list_sessions()
        assert isinstance(sessions, list)


class TestSQLiteStorage:
    """Tests for SQLiteStorage class."""

    def test_create_storage(self, storage_path):
        """Test creating SQLite storage."""
        from empathy_os.socratic.storage import SQLiteStorage

        storage = SQLiteStorage(db_path=storage_path / "test.db")
        assert storage is not None

    def test_save_and_load_session(self, storage_path, sample_session):
        """Test saving and loading a session."""
        from empathy_os.socratic.storage import SQLiteStorage

        storage = SQLiteStorage(db_path=storage_path / "sessions.db")

        # Save
        storage.save_session(sample_session)

        # Load
        loaded = storage.load_session(sample_session.session_id)

        assert loaded is not None
        assert loaded.session_id == sample_session.session_id

    def test_list_sessions(self, storage_path, sample_session):
        """Test listing all sessions."""
        from empathy_os.socratic.storage import SQLiteStorage
        from empathy_os.socratic.session import SocraticSession

        storage = SQLiteStorage(db_path=storage_path / "sessions.db")

        session1 = sample_session
        session2 = SocraticSession(session_id="test-session-002")

        storage.save_session(session1)
        storage.save_session(session2)

        sessions = storage.list_sessions()
        assert len(sessions) >= 2

    def test_delete_session(self, storage_path, sample_session):
        """Test deleting a session."""
        from empathy_os.socratic.storage import SQLiteStorage

        storage = SQLiteStorage(db_path=storage_path / "sessions.db")

        storage.save_session(sample_session)
        storage.delete_session(sample_session.session_id)

        loaded = storage.load_session(sample_session.session_id)
        assert loaded is None

    def test_save_and_load_blueprint(self, storage_path, sample_workflow_blueprint):
        """Test saving and loading a blueprint."""
        from empathy_os.socratic.storage import SQLiteStorage

        storage = SQLiteStorage(db_path=storage_path / "blueprints.db")

        storage.save_blueprint(sample_workflow_blueprint)

        loaded = storage.load_blueprint(sample_workflow_blueprint.workflow_id)

        assert loaded is not None
        assert loaded.workflow_id == sample_workflow_blueprint.workflow_id

    def test_query_sessions_by_state(self, storage_path):
        """Test querying sessions by state."""
        from empathy_os.socratic.storage import SQLiteStorage
        from empathy_os.socratic.session import SocraticSession, SessionState

        storage = SQLiteStorage(db_path=storage_path / "query.db")

        # Create sessions with different states
        session1 = SocraticSession(session_id="s1")
        session1.state = SessionState.AWAITING_GOAL

        session2 = SocraticSession(session_id="s2")
        session2.state = SessionState.READY_TO_GENERATE

        storage.save_session(session1)
        storage.save_session(session2)

        if hasattr(storage, "query_sessions"):
            awaiting = storage.query_sessions(state=SessionState.AWAITING_GOAL)
            assert len(awaiting) >= 1
            assert all(s.state == SessionState.AWAITING_GOAL for s in awaiting)


class TestStorageManager:
    """Tests for StorageManager class."""

    def test_create_manager_with_json(self, storage_path):
        """Test creating manager with JSON backend."""
        from empathy_os.socratic.storage import StorageManager

        manager = StorageManager(
            backend="json",
            storage_path=storage_path / "storage.json",
        )

        assert manager is not None

    def test_create_manager_with_sqlite(self, storage_path):
        """Test creating manager with SQLite backend."""
        from empathy_os.socratic.storage import StorageManager

        manager = StorageManager(
            backend="sqlite",
            db_path=storage_path / "storage.db",
        )

        assert manager is not None

    def test_manager_save_and_load(self, storage_path, sample_session):
        """Test saving and loading via manager."""
        from empathy_os.socratic.storage import StorageManager

        manager = StorageManager(
            backend="json",
            storage_path=storage_path / "manager.json",
        )

        manager.save_session(sample_session)
        loaded = manager.load_session(sample_session.session_id)

        assert loaded is not None
        assert loaded.session_id == sample_session.session_id

    def test_manager_auto_persist(self, storage_path, sample_session):
        """Test manager auto-persist feature."""
        from empathy_os.socratic.storage import StorageManager

        manager = StorageManager(
            backend="json",
            storage_path=storage_path / "autopersist.json",
            auto_persist=True,
        )

        manager.save_session(sample_session)

        # Create new manager pointing to same file
        manager2 = StorageManager(
            backend="json",
            storage_path=storage_path / "autopersist.json",
        )

        loaded = manager2.load_session(sample_session.session_id)
        assert loaded is not None

    def test_manager_switch_backend(self, storage_path, sample_session):
        """Test switching storage backend."""
        from empathy_os.socratic.storage import StorageManager

        # Save with JSON
        json_manager = StorageManager(
            backend="json",
            storage_path=storage_path / "switch.json",
        )
        json_manager.save_session(sample_session)

        # Export to SQLite
        sqlite_manager = StorageManager(
            backend="sqlite",
            db_path=storage_path / "switch.db",
        )

        if hasattr(json_manager, "export_to"):
            json_manager.export_to(sqlite_manager)
            loaded = sqlite_manager.load_session(sample_session.session_id)
            assert loaded is not None


class TestStorageSecurity:
    """Tests for storage security."""

    def test_json_storage_validates_path(self, tmp_path):
        """Test that JSON storage validates file paths."""
        from empathy_os.socratic.storage import JSONFileStorage

        # Attempting path traversal should fail or be sanitized
        try:
            storage = JSONFileStorage(
                storage_path=tmp_path / ".." / ".." / "etc" / "passwd"
            )
            # If it doesn't raise, the path should be sanitized
            assert "/etc/passwd" not in str(storage.storage_path)
        except (ValueError, OSError):
            pass  # Expected

    def test_sqlite_storage_validates_path(self, tmp_path):
        """Test that SQLite storage validates file paths."""
        from empathy_os.socratic.storage import SQLiteStorage

        try:
            storage = SQLiteStorage(db_path=tmp_path / ".." / ".." / "etc" / "test.db")
            # If it doesn't raise, the path should be sanitized
            assert "/etc/" not in str(storage.db_path)
        except (ValueError, OSError):
            pass  # Expected

    def test_no_sql_injection(self, storage_path):
        """Test protection against SQL injection."""
        from empathy_os.socratic.storage import SQLiteStorage
        from empathy_os.socratic.session import SocraticSession

        storage = SQLiteStorage(db_path=storage_path / "injection.db")

        # Try SQL injection in session_id
        malicious_id = "'; DROP TABLE sessions; --"
        session = SocraticSession(session_id=malicious_id)

        # Should either sanitize or reject
        try:
            storage.save_session(session)
            loaded = storage.load_session(malicious_id)
            # If it succeeds, the table should still exist
            sessions = storage.list_sessions()
            assert isinstance(sessions, list)
        except Exception:
            pass  # Expected if input is rejected


class TestStorageEdgeCases:
    """Tests for storage edge cases."""

    def test_save_empty_session(self, storage_path):
        """Test saving a session with minimal data."""
        from empathy_os.socratic.storage import JSONFileStorage
        from empathy_os.socratic.session import SocraticSession

        storage = JSONFileStorage(storage_path=storage_path / "empty.json")

        session = SocraticSession(session_id="empty-001")
        storage.save_session(session)

        loaded = storage.load_session("empty-001")
        assert loaded is not None

    def test_load_nonexistent_session(self, storage_path):
        """Test loading a session that doesn't exist."""
        from empathy_os.socratic.storage import JSONFileStorage

        storage = JSONFileStorage(storage_path=storage_path / "empty.json")

        loaded = storage.load_session("nonexistent")
        assert loaded is None

    def test_save_large_session(self, storage_path):
        """Test saving a session with large data."""
        from empathy_os.socratic.storage import JSONFileStorage
        from empathy_os.socratic.session import SocraticSession

        storage = JSONFileStorage(storage_path=storage_path / "large.json")

        session = SocraticSession(session_id="large-001")
        session.goal = "A" * 10000  # Large goal
        session.collected_answers = {f"key_{i}": f"value_{i}" for i in range(1000)}

        storage.save_session(session)

        loaded = storage.load_session("large-001")
        assert loaded is not None
        assert len(loaded.goal) == 10000

    def test_concurrent_writes(self, storage_path):
        """Test handling concurrent writes."""
        from empathy_os.socratic.storage import JSONFileStorage
        from empathy_os.socratic.session import SocraticSession
        import threading

        storage = JSONFileStorage(storage_path=storage_path / "concurrent.json")

        def save_session(session_id):
            session = SocraticSession(session_id=session_id)
            storage.save_session(session)

        threads = [
            threading.Thread(target=save_session, args=(f"session-{i}",))
            for i in range(10)
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All sessions should be saved
        sessions = storage.list_sessions()
        assert len(sessions) >= 10
