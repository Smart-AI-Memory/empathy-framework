"""Persistence Layer for Empathy Framework

Provides:
- Pattern library save/load (JSON, SQLite)
- Collaboration state persistence
- Metrics and telemetry tracking

Copyright 2025 Smart AI Memory, LLC
Licensed under Fair Source 0.9
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import _validate_file_path
from .core import CollaborationState
from .pattern_library import Pattern, PatternLibrary


class PatternPersistence:
    """Save and load PatternLibrary to/from files

    Supports:
    - JSON format (human-readable, good for backups)
    - SQLite format (queryable, good for production)
    """

    @staticmethod
    def save_to_json(library: PatternLibrary, filepath: str):
        """Save pattern library to JSON file

        Args:
            library: PatternLibrary instance to save
            filepath: Path to JSON file

        Example:
            >>> library = PatternLibrary()
            >>> PatternPersistence.save_to_json(library, "patterns.json")

        """
        patterns_list: list[dict[str, Any]] = []
        data: dict[str, Any] = {
            "patterns": patterns_list,
            "agent_contributions": library.agent_contributions,
            "metadata": {
                "saved_at": datetime.now().isoformat(),
                "pattern_count": len(library.patterns),
                "version": "1.0",
            },
        }

        # Serialize each pattern
        for _pattern_id, pattern in library.patterns.items():
            patterns_list.append(
                {
                    "id": pattern.id,
                    "agent_id": pattern.agent_id,
                    "pattern_type": pattern.pattern_type,
                    "name": pattern.name,
                    "description": pattern.description,
                    "context": pattern.context,
                    "code": pattern.code,
                    "confidence": pattern.confidence,
                    "usage_count": pattern.usage_count,
                    "success_count": pattern.success_count,
                    "failure_count": pattern.failure_count,
                    "tags": pattern.tags,
                    "discovered_at": pattern.discovered_at.isoformat(),
                    "last_used": pattern.last_used.isoformat() if pattern.last_used else None,
                },
            )

        # Write to file
        validated_path = _validate_file_path(filepath)
        with open(validated_path, "w") as f:
            json.dump(data, f, indent=2)

    @staticmethod
    def load_from_json(filepath: str) -> PatternLibrary:
        """Load pattern library from JSON file

        Args:
            filepath: Path to JSON file

        Returns:
            PatternLibrary instance

        Raises:
            FileNotFoundError: If file doesn't exist
            json.JSONDecodeError: If file is not valid JSON

        Example:
            >>> library = PatternPersistence.load_from_json("patterns.json")

        """
        with open(filepath) as f:
            data = json.load(f)

        library = PatternLibrary()

        # Restore patterns
        for pattern_data in data["patterns"]:
            pattern = Pattern(
                id=pattern_data["id"],
                agent_id=pattern_data["agent_id"],
                pattern_type=pattern_data["pattern_type"],
                name=pattern_data["name"],
                description=pattern_data["description"],
                context=pattern_data.get("context", {}),
                code=pattern_data.get("code"),
                confidence=pattern_data.get("confidence", 0.5),
                usage_count=pattern_data.get("usage_count", 0),
                success_count=pattern_data.get("success_count", 0),
                failure_count=pattern_data.get("failure_count", 0),
                tags=pattern_data.get("tags", []),
                discovered_at=datetime.fromisoformat(pattern_data["discovered_at"]),
                last_used=(
                    datetime.fromisoformat(pattern_data["last_used"])
                    if pattern_data.get("last_used")
                    else None
                ),
            )
            library.contribute_pattern(pattern.agent_id, pattern)

        # Restore agent_contributions index
        library.agent_contributions = data.get("agent_contributions", {})

        return library

    @staticmethod
    def save_to_sqlite(library: PatternLibrary, db_path: str):
        """Save pattern library to SQLite database

        Args:
            library: PatternLibrary instance to save
            db_path: Path to SQLite database file

        Creates tables:
            - patterns: Core pattern data
            - pattern_usage: Usage history

        Example:
            >>> library = PatternLibrary()
            >>> PatternPersistence.save_to_sqlite(library, "patterns.db")

        """
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Create tables
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS patterns (
                id TEXT PRIMARY KEY,
                agent_id TEXT NOT NULL,
                pattern_type TEXT NOT NULL,
                name TEXT NOT NULL,
                description TEXT,
                context TEXT,
                code TEXT,
                confidence REAL DEFAULT 0.5,
                usage_count INTEGER DEFAULT 0,
                success_count INTEGER DEFAULT 0,
                failure_count INTEGER DEFAULT 0,
                tags TEXT,
                discovered_at TIMESTAMP,
                last_used TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """,
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS pattern_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pattern_id TEXT NOT NULL,
                agent_id TEXT NOT NULL,
                success BOOLEAN NOT NULL,
                used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (pattern_id) REFERENCES patterns(id)
            )
        """,
        )

        # Insert or update patterns
        for pattern in library.patterns.values():
            cursor.execute(
                """
                INSERT OR REPLACE INTO patterns (
                    id, agent_id, pattern_type, name, description, context,
                    code, confidence, usage_count, success_count, failure_count,
                    tags, discovered_at, last_used, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
                (
                    pattern.id,
                    pattern.agent_id,
                    pattern.pattern_type,
                    pattern.name,
                    pattern.description,
                    json.dumps(pattern.context),
                    pattern.code,
                    pattern.confidence,
                    pattern.usage_count,
                    pattern.success_count,
                    pattern.failure_count,
                    json.dumps(pattern.tags),
                    pattern.discovered_at.isoformat(),
                    pattern.last_used.isoformat() if pattern.last_used else None,
                ),
            )

        conn.commit()
        conn.close()

    @staticmethod
    def load_from_sqlite(db_path: str) -> PatternLibrary:
        """Load pattern library from SQLite database

        Args:
            db_path: Path to SQLite database file

        Returns:
            PatternLibrary instance

        Example:
            >>> library = PatternPersistence.load_from_sqlite("patterns.db")

        """
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row  # Access columns by name
        cursor = conn.cursor()

        library = PatternLibrary()

        # Load patterns
        cursor.execute("SELECT * FROM patterns")
        rows = cursor.fetchall()

        for row in rows:
            pattern = Pattern(
                id=row["id"],
                agent_id=row["agent_id"],
                pattern_type=row["pattern_type"],
                name=row["name"],
                description=row["description"],
                context=json.loads(row["context"]),
                code=row["code"],
                confidence=row["confidence"],
                usage_count=row["usage_count"],
                success_count=row["success_count"],
                failure_count=row["failure_count"],
                tags=json.loads(row["tags"]),
                discovered_at=datetime.fromisoformat(row["discovered_at"]),
                last_used=datetime.fromisoformat(row["last_used"]) if row["last_used"] else None,
            )
            library.contribute_pattern(pattern.agent_id, pattern)

        conn.close()
        return library


class StateManager:
    """Persist collaboration state across sessions

    Enables:
    - Long-term trust tracking
    - Historical analytics
    - User personalization
    """

    def __init__(self, storage_path: str = "./empathy_state"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(exist_ok=True, parents=True)

    def save_state(self, user_id: str, state: CollaborationState):
        """Save user's collaboration state to JSON

        Args:
            user_id: User identifier
            state: CollaborationState instance

        Example:
            >>> manager = StateManager()
            >>> manager.save_state("user123", empathy.collaboration_state)

        """
        filepath = self.storage_path / f"{user_id}.json"

        data = {
            "user_id": user_id,
            "trust_level": state.trust_level,
            "total_interactions": state.total_interactions,
            "successful_interventions": state.successful_interventions,
            "failed_interventions": state.failed_interventions,
            "session_start": state.session_start.isoformat(),
            "trust_trajectory": state.trust_trajectory,
            "shared_context": state.shared_context,
            "saved_at": datetime.now().isoformat(),
        }

        validated_path = _validate_file_path(str(filepath))
        with open(validated_path, "w") as f:
            json.dump(data, f, indent=2)

    def load_state(self, user_id: str) -> CollaborationState | None:
        """Load user's previous state

        Args:
            user_id: User identifier

        Returns:
            CollaborationState if found, None otherwise

        Example:
            >>> manager = StateManager()
            >>> state = manager.load_state("user123")
            >>> if state:
            ...     empathy = EmpathyOS(user_id="user123", target_level=4)
            ...     empathy.collaboration_state = state

        """
        filepath = self.storage_path / f"{user_id}.json"

        if not filepath.exists():
            return None

        try:
            with open(filepath) as f:
                data = json.load(f)

            state = CollaborationState()
            state.trust_level = data["trust_level"]
            state.total_interactions = data["total_interactions"]
            state.successful_interventions = data["successful_interventions"]
            state.failed_interventions = data["failed_interventions"]
            state.session_start = datetime.fromisoformat(data["session_start"])
            state.trust_trajectory = data.get("trust_trajectory", [])
            state.shared_context = data.get("shared_context", {})

            return state

        except (json.JSONDecodeError, KeyError, ValueError):
            # Corrupted file - return None
            return None

    def list_users(self) -> list[str]:
        """List all users with saved state

        Returns:
            List of user IDs

        Example:
            >>> manager = StateManager()
            >>> users = manager.list_users()
            >>> print(f"Found {len(users)} users")

        """
        return [p.stem for p in self.storage_path.glob("*.json")]

    def delete_state(self, user_id: str) -> bool:
        """Delete user's saved state

        Args:
            user_id: User identifier

        Returns:
            True if deleted, False if didn't exist

        Example:
            >>> manager = StateManager()
            >>> deleted = manager.delete_state("user123")

        """
        filepath = self.storage_path / f"{user_id}.json"

        if filepath.exists():
            filepath.unlink()
            return True
        return False


class MetricsCollector:
    """Collect and persist empathy framework metrics

    Tracks:
    - Empathy level usage
    - Success rates by level
    - Average response times
    - Trust trajectory trends
    """

    def __init__(self, db_path: str = "./metrics.db"):
        self.db_path = db_path
        self._init_database()

    def _init_database(self):
        """Initialize SQLite database for metrics"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                empathy_level INTEGER NOT NULL,
                success BOOLEAN NOT NULL,
                response_time_ms REAL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT
            )
        """,
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_user_level
            ON metrics(user_id, empathy_level)
        """,
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_timestamp
            ON metrics(timestamp)
        """,
        )

        conn.commit()
        conn.close()

    def record_metric(
        self,
        user_id: str,
        empathy_level: int,
        success: bool,
        response_time_ms: float,
        metadata: dict | None = None,
    ):
        """Record a single metric event

        Args:
            user_id: User identifier
            empathy_level: 1-5 empathy level used
            success: Whether the operation succeeded
            response_time_ms: Response time in milliseconds
            metadata: Optional additional data

        Example:
            >>> collector = MetricsCollector()
            >>> collector.record_metric(
            ...     user_id="user123",
            ...     empathy_level=4,
            ...     success=True,
            ...     response_time_ms=250.5,
            ...     metadata={"bottlenecks_predicted": 3}
            ... )

        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO metrics (
                user_id, empathy_level, success, response_time_ms, metadata
            ) VALUES (?, ?, ?, ?, ?)
        """,
            (
                user_id,
                empathy_level,
                success,
                response_time_ms,
                json.dumps(metadata) if metadata else None,
            ),
        )

        conn.commit()
        conn.close()

    def get_user_stats(self, user_id: str) -> dict:
        """Get aggregated statistics for a user

        Args:
            user_id: User identifier

        Returns:
            Dict with statistics

        Example:
            >>> collector = MetricsCollector()
            >>> stats = collector.get_user_stats("user123")
            >>> print(f"Success rate: {stats['success_rate']:.1%}")

        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT
                COUNT(*) as total_operations,
                SUM(CASE WHEN success THEN 1 ELSE 0 END) as successes,
                AVG(response_time_ms) as avg_response_time,
                MIN(timestamp) as first_use,
                MAX(timestamp) as last_use
            FROM metrics
            WHERE user_id = ?
        """,
            (user_id,),
        )

        row = cursor.fetchone()

        if not row or row["total_operations"] == 0:
            conn.close()
            return {
                "total_operations": 0,
                "success_rate": 0.0,
                "avg_response_time_ms": 0.0,
                "first_use": None,
                "last_use": None,
            }

        # Get per-level breakdown
        cursor.execute(
            """
            SELECT
                empathy_level,
                COUNT(*) as operations,
                SUM(CASE WHEN success THEN 1 ELSE 0 END) as successes
            FROM metrics
            WHERE user_id = ?
            GROUP BY empathy_level
            ORDER BY empathy_level
        """,
            (user_id,),
        )

        level_stats = {}
        for level_row in cursor.fetchall():
            level = level_row["empathy_level"]
            ops = level_row["operations"]
            level_stats[f"level_{level}"] = {
                "operations": ops,
                "success_rate": level_row["successes"] / ops if ops > 0 else 0.0,
            }

        conn.close()

        return {
            "total_operations": row["total_operations"],
            "success_rate": row["successes"] / row["total_operations"],
            "avg_response_time_ms": row["avg_response_time"],
            "first_use": row["first_use"],
            "last_use": row["last_use"],
            "by_level": level_stats,
        }
