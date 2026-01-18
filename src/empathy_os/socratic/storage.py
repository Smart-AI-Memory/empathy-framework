"""Persistent Storage for Socratic Sessions and Blueprints

Provides multiple storage backends for persisting:
- Socratic sessions (in-progress and completed)
- Workflow blueprints (generated workflows)
- Success metrics history (for feedback loop)

Backends:
- JSONFileStorage: Simple file-based storage (default)
- SQLiteStorage: SQLite database for better querying
- RedisStorage: Redis for distributed/production use

Copyright 2026 Smart-AI-Memory
Licensed under Fair Source License 0.9
"""

from __future__ import annotations

import json
import logging
import sqlite3
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from .session import SocraticSession, SessionState
from .blueprint import WorkflowBlueprint
from .success import SuccessEvaluation

logger = logging.getLogger(__name__)


# =============================================================================
# STORAGE INTERFACE
# =============================================================================


class StorageBackend(ABC):
    """Abstract base for storage backends."""

    @abstractmethod
    def save_session(self, session: SocraticSession) -> None:
        """Save a Socratic session."""

    @abstractmethod
    def load_session(self, session_id: str) -> SocraticSession | None:
        """Load a session by ID."""

    @abstractmethod
    def list_sessions(
        self,
        state: SessionState | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """List sessions with optional filtering."""

    @abstractmethod
    def delete_session(self, session_id: str) -> bool:
        """Delete a session."""

    @abstractmethod
    def save_blueprint(self, blueprint: WorkflowBlueprint) -> None:
        """Save a workflow blueprint."""

    @abstractmethod
    def load_blueprint(self, blueprint_id: str) -> WorkflowBlueprint | None:
        """Load a blueprint by ID."""

    @abstractmethod
    def list_blueprints(
        self,
        domain: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """List blueprints with optional filtering."""

    @abstractmethod
    def save_evaluation(
        self,
        blueprint_id: str,
        evaluation: SuccessEvaluation,
    ) -> None:
        """Save a success evaluation for a blueprint."""

    @abstractmethod
    def get_evaluations(
        self,
        blueprint_id: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Get evaluation history for a blueprint."""


# =============================================================================
# JSON FILE STORAGE
# =============================================================================


class JSONFileStorage(StorageBackend):
    """File-based JSON storage.

    Structure:
        base_dir/
            sessions/
                {session_id}.json
            blueprints/
                {blueprint_id}.json
            evaluations/
                {blueprint_id}/
                    {timestamp}.json

    Example:
        >>> storage = JSONFileStorage(".empathy/socratic")
        >>> storage.save_session(session)
        >>> loaded = storage.load_session(session.session_id)
    """

    def __init__(self, base_dir: str = ".empathy/socratic"):
        """Initialize storage.

        Args:
            base_dir: Base directory for storage
        """
        self.base_dir = Path(base_dir)
        self.sessions_dir = self.base_dir / "sessions"
        self.blueprints_dir = self.base_dir / "blueprints"
        self.evaluations_dir = self.base_dir / "evaluations"

        # Create directories
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self.blueprints_dir.mkdir(parents=True, exist_ok=True)
        self.evaluations_dir.mkdir(parents=True, exist_ok=True)

    def save_session(self, session: SocraticSession) -> None:
        """Save a session to JSON file."""
        path = self.sessions_dir / f"{session.session_id}.json"
        data = session.to_dict()

        with path.open("w") as f:
            json.dump(data, f, indent=2, default=str)

        logger.debug(f"Saved session {session.session_id}")

    def load_session(self, session_id: str) -> SocraticSession | None:
        """Load a session from JSON file."""
        path = self.sessions_dir / f"{session_id}.json"

        if not path.exists():
            return None

        try:
            with path.open() as f:
                data = json.load(f)
            return SocraticSession.from_dict(data)
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Failed to load session {session_id}: {e}")
            return None

    def list_sessions(
        self,
        state: SessionState | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """List sessions with optional state filter."""
        sessions = []

        for path in sorted(self.sessions_dir.glob("*.json"), reverse=True):
            if len(sessions) >= limit:
                break

            try:
                with path.open() as f:
                    data = json.load(f)

                # Filter by state if specified
                if state and data.get("state") != state.value:
                    continue

                sessions.append({
                    "session_id": data.get("session_id"),
                    "state": data.get("state"),
                    "goal": data.get("goal", "")[:100],
                    "created_at": data.get("created_at"),
                    "updated_at": data.get("updated_at"),
                })
            except (json.JSONDecodeError, KeyError):
                continue

        return sessions

    def delete_session(self, session_id: str) -> bool:
        """Delete a session file."""
        path = self.sessions_dir / f"{session_id}.json"

        if path.exists():
            path.unlink()
            return True
        return False

    def save_blueprint(self, blueprint: WorkflowBlueprint) -> None:
        """Save a blueprint to JSON file."""
        path = self.blueprints_dir / f"{blueprint.id}.json"
        data = blueprint.to_dict()

        with path.open("w") as f:
            json.dump(data, f, indent=2, default=str)

        logger.debug(f"Saved blueprint {blueprint.id}")

    def load_blueprint(self, blueprint_id: str) -> WorkflowBlueprint | None:
        """Load a blueprint from JSON file."""
        path = self.blueprints_dir / f"{blueprint_id}.json"

        if not path.exists():
            return None

        try:
            with path.open() as f:
                data = json.load(f)
            return WorkflowBlueprint.from_dict(data)
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Failed to load blueprint {blueprint_id}: {e}")
            return None

    def list_blueprints(
        self,
        domain: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """List blueprints with optional domain filter."""
        blueprints = []

        for path in sorted(self.blueprints_dir.glob("*.json"), reverse=True):
            if len(blueprints) >= limit:
                break

            try:
                with path.open() as f:
                    data = json.load(f)

                # Filter by domain if specified
                if domain and data.get("domain") != domain:
                    continue

                blueprints.append({
                    "id": data.get("id"),
                    "name": data.get("name"),
                    "domain": data.get("domain"),
                    "agents_count": len(data.get("agents", [])),
                    "generated_at": data.get("generated_at"),
                })
            except (json.JSONDecodeError, KeyError):
                continue

        return blueprints

    def save_evaluation(
        self,
        blueprint_id: str,
        evaluation: SuccessEvaluation,
    ) -> None:
        """Save an evaluation to JSON file."""
        eval_dir = self.evaluations_dir / blueprint_id
        eval_dir.mkdir(exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = eval_dir / f"{timestamp}.json"

        data = evaluation.to_dict()
        with path.open("w") as f:
            json.dump(data, f, indent=2, default=str)

    def get_evaluations(
        self,
        blueprint_id: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Get evaluation history for a blueprint."""
        eval_dir = self.evaluations_dir / blueprint_id

        if not eval_dir.exists():
            return []

        evaluations = []
        for path in sorted(eval_dir.glob("*.json"), reverse=True)[:limit]:
            try:
                with path.open() as f:
                    evaluations.append(json.load(f))
            except json.JSONDecodeError:
                continue

        return evaluations


# =============================================================================
# SQLITE STORAGE
# =============================================================================


class SQLiteStorage(StorageBackend):
    """SQLite database storage for better querying.

    Example:
        >>> storage = SQLiteStorage(".empathy/socratic.db")
        >>> storage.save_session(session)
        >>> sessions = storage.list_sessions(state=SessionState.COMPLETED)
    """

    def __init__(self, db_path: str = ".empathy/socratic.db"):
        """Initialize SQLite storage.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._init_database()

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_database(self) -> None:
        """Initialize database schema."""
        with self._get_connection() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    state TEXT NOT NULL,
                    goal TEXT,
                    domain TEXT,
                    confidence REAL,
                    created_at TEXT,
                    updated_at TEXT,
                    data JSON NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_sessions_state ON sessions(state);
                CREATE INDEX IF NOT EXISTS idx_sessions_domain ON sessions(domain);
                CREATE INDEX IF NOT EXISTS idx_sessions_updated ON sessions(updated_at);

                CREATE TABLE IF NOT EXISTS blueprints (
                    blueprint_id TEXT PRIMARY KEY,
                    name TEXT,
                    domain TEXT,
                    agents_count INTEGER,
                    generated_at TEXT,
                    source_session_id TEXT,
                    data JSON NOT NULL,
                    FOREIGN KEY (source_session_id) REFERENCES sessions(session_id)
                );

                CREATE INDEX IF NOT EXISTS idx_blueprints_domain ON blueprints(domain);
                CREATE INDEX IF NOT EXISTS idx_blueprints_session ON blueprints(source_session_id);

                CREATE TABLE IF NOT EXISTS evaluations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    blueprint_id TEXT NOT NULL,
                    overall_success INTEGER,
                    overall_score REAL,
                    evaluated_at TEXT,
                    data JSON NOT NULL,
                    FOREIGN KEY (blueprint_id) REFERENCES blueprints(blueprint_id)
                );

                CREATE INDEX IF NOT EXISTS idx_evaluations_blueprint ON evaluations(blueprint_id);
            """)

    def save_session(self, session: SocraticSession) -> None:
        """Save session to database."""
        data = session.to_dict()
        domain = session.goal_analysis.domain if session.goal_analysis else None
        confidence = session.goal_analysis.confidence if session.goal_analysis else None

        with self._get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO sessions
                (session_id, state, goal, domain, confidence, created_at, updated_at, data)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                session.session_id,
                session.state.value,
                session.goal,
                domain,
                confidence,
                session.created_at.isoformat(),
                session.updated_at.isoformat(),
                json.dumps(data, default=str),
            ))

    def load_session(self, session_id: str) -> SocraticSession | None:
        """Load session from database."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT data FROM sessions WHERE session_id = ?",
                (session_id,)
            ).fetchone()

            if row:
                data = json.loads(row["data"])
                return SocraticSession.from_dict(data)
            return None

    def list_sessions(
        self,
        state: SessionState | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """List sessions from database."""
        with self._get_connection() as conn:
            if state:
                rows = conn.execute("""
                    SELECT session_id, state, goal, domain, confidence, created_at, updated_at
                    FROM sessions
                    WHERE state = ?
                    ORDER BY updated_at DESC
                    LIMIT ?
                """, (state.value, limit)).fetchall()
            else:
                rows = conn.execute("""
                    SELECT session_id, state, goal, domain, confidence, created_at, updated_at
                    FROM sessions
                    ORDER BY updated_at DESC
                    LIMIT ?
                """, (limit,)).fetchall()

            return [dict(row) for row in rows]

    def delete_session(self, session_id: str) -> bool:
        """Delete session from database."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM sessions WHERE session_id = ?",
                (session_id,)
            )
            return cursor.rowcount > 0

    def save_blueprint(self, blueprint: WorkflowBlueprint) -> None:
        """Save blueprint to database."""
        data = blueprint.to_dict()

        with self._get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO blueprints
                (blueprint_id, name, domain, agents_count, generated_at, source_session_id, data)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                blueprint.id,
                blueprint.name,
                blueprint.domain,
                len(blueprint.agents),
                blueprint.generated_at,
                blueprint.source_session_id,
                json.dumps(data, default=str),
            ))

    def load_blueprint(self, blueprint_id: str) -> WorkflowBlueprint | None:
        """Load blueprint from database."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT data FROM blueprints WHERE blueprint_id = ?",
                (blueprint_id,)
            ).fetchone()

            if row:
                data = json.loads(row["data"])
                return WorkflowBlueprint.from_dict(data)
            return None

    def list_blueprints(
        self,
        domain: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """List blueprints from database."""
        with self._get_connection() as conn:
            if domain:
                rows = conn.execute("""
                    SELECT blueprint_id as id, name, domain, agents_count, generated_at
                    FROM blueprints
                    WHERE domain = ?
                    ORDER BY generated_at DESC
                    LIMIT ?
                """, (domain, limit)).fetchall()
            else:
                rows = conn.execute("""
                    SELECT blueprint_id as id, name, domain, agents_count, generated_at
                    FROM blueprints
                    ORDER BY generated_at DESC
                    LIMIT ?
                """, (limit,)).fetchall()

            return [dict(row) for row in rows]

    def save_evaluation(
        self,
        blueprint_id: str,
        evaluation: SuccessEvaluation,
    ) -> None:
        """Save evaluation to database."""
        data = evaluation.to_dict()

        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO evaluations
                (blueprint_id, overall_success, overall_score, evaluated_at, data)
                VALUES (?, ?, ?, ?, ?)
            """, (
                blueprint_id,
                1 if evaluation.overall_success else 0,
                evaluation.overall_score,
                evaluation.evaluated_at,
                json.dumps(data, default=str),
            ))

    def get_evaluations(
        self,
        blueprint_id: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Get evaluations from database."""
        with self._get_connection() as conn:
            rows = conn.execute("""
                SELECT data FROM evaluations
                WHERE blueprint_id = ?
                ORDER BY evaluated_at DESC
                LIMIT ?
            """, (blueprint_id, limit)).fetchall()

            return [json.loads(row["data"]) for row in rows]

    def get_success_rate(self, blueprint_id: str) -> float:
        """Get overall success rate for a blueprint."""
        with self._get_connection() as conn:
            row = conn.execute("""
                SELECT
                    COUNT(*) as total,
                    SUM(overall_success) as successes
                FROM evaluations
                WHERE blueprint_id = ?
            """, (blueprint_id,)).fetchone()

            if row and row["total"] > 0:
                return row["successes"] / row["total"]
            return 0.0

    def search_blueprints(
        self,
        query: str,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Search blueprints by name or domain."""
        with self._get_connection() as conn:
            rows = conn.execute("""
                SELECT blueprint_id as id, name, domain, agents_count, generated_at
                FROM blueprints
                WHERE name LIKE ? OR domain LIKE ?
                ORDER BY generated_at DESC
                LIMIT ?
            """, (f"%{query}%", f"%{query}%", limit)).fetchall()

            return [dict(row) for row in rows]


# =============================================================================
# STORAGE MANAGER
# =============================================================================


@dataclass
class StorageConfig:
    """Storage configuration."""

    backend: str = "json"  # json, sqlite, redis
    path: str = ".empathy/socratic"
    redis_url: str | None = None


class StorageManager:
    """Manages storage backend lifecycle.

    Example:
        >>> manager = StorageManager(StorageConfig(backend="sqlite"))
        >>> storage = manager.get_storage()
        >>> storage.save_session(session)
    """

    def __init__(self, config: StorageConfig | None = None):
        """Initialize manager.

        Args:
            config: Storage configuration
        """
        self.config = config or StorageConfig()
        self._storage: StorageBackend | None = None

    def get_storage(self) -> StorageBackend:
        """Get or create storage backend."""
        if self._storage is None:
            self._storage = self._create_storage()
        return self._storage

    def _create_storage(self) -> StorageBackend:
        """Create storage backend based on config."""
        if self.config.backend == "sqlite":
            return SQLiteStorage(f"{self.config.path}.db")
        elif self.config.backend == "redis":
            # Redis would be implemented separately
            logger.warning("Redis storage not implemented, using JSON")
            return JSONFileStorage(self.config.path)
        else:
            return JSONFileStorage(self.config.path)


# Default storage instance
_default_storage: StorageBackend | None = None


def get_default_storage() -> StorageBackend:
    """Get the default storage backend."""
    global _default_storage
    if _default_storage is None:
        _default_storage = JSONFileStorage()
    return _default_storage


def set_default_storage(storage: StorageBackend) -> None:
    """Set the default storage backend."""
    global _default_storage
    _default_storage = storage
