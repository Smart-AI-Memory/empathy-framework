"""Project Index - Main index class with persistence.

Manages the project index, persists to JSON, syncs with Redis.

Copyright 2025 Smart AI Memory, LLC
Licensed under Fair Source 0.9
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from empathy_os.config import _validate_file_path

from .models import FileRecord, IndexConfig, ProjectSummary
from .scanner import ProjectScanner

logger = logging.getLogger(__name__)


class ProjectIndex:
    """Central project index with file metadata.

    Features:
    - JSON persistence in .empathy/project_index.json
    - Optional Redis sync for real-time access
    - Query API for workflows and agents
    - Update API for writing metadata
    """

    SCHEMA_VERSION = "1.0"
    DEFAULT_INDEX_PATH = ".empathy/project_index.json"

    def __init__(
        self,
        project_root: str,
        config: IndexConfig | None = None,
        redis_client: Any | None = None,
    ):
        self.project_root = Path(project_root)
        self.config = config or IndexConfig()
        self.redis_client = redis_client

        # In-memory state
        self._records: dict[str, FileRecord] = {}
        self._summary: ProjectSummary = ProjectSummary()
        self._generated_at: datetime | None = None

        # Index file path
        self._index_path = self.project_root / self.DEFAULT_INDEX_PATH

    # ===== Persistence =====

    def load(self) -> bool:
        """Load index from JSON file.

        Returns:
            True if loaded successfully, False otherwise

        """
        if not self._index_path.exists():
            logger.info(f"No index found at {self._index_path}")
            return False

        try:
            with open(self._index_path, encoding="utf-8") as f:
                data = json.load(f)

            # Validate schema version
            if data.get("schema_version") != self.SCHEMA_VERSION:
                logger.warning("Schema version mismatch, regenerating index")
                return False

            # Load config
            if "config" in data:
                self.config = IndexConfig.from_dict(data["config"])

            # Load summary
            if "summary" in data:
                self._summary = ProjectSummary.from_dict(data["summary"])

            # Load records
            self._records = {}
            for path, record_data in data.get("files", {}).items():
                self._records[path] = FileRecord.from_dict(record_data)

            # Load timestamp
            if data.get("generated_at"):
                self._generated_at = datetime.fromisoformat(data["generated_at"])

            logger.info(f"Loaded index with {len(self._records)} files")
            return True

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.error(f"Failed to load index: {e}")
            return False

    def save(self) -> bool:
        """Save index to JSON file.

        Returns:
            True if saved successfully, False otherwise

        """
        try:
            # Ensure directory exists
            self._index_path.parent.mkdir(parents=True, exist_ok=True)

            data = {
                "schema_version": self.SCHEMA_VERSION,
                "project": self.project_root.name,
                "generated_at": datetime.now().isoformat(),
                "config": self.config.to_dict(),
                "summary": self._summary.to_dict(),
                "files": {path: record.to_dict() for path, record in self._records.items()},
            }

            validated_path = _validate_file_path(str(self._index_path))
            with open(validated_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, default=str)

            logger.info(f"Saved index with {len(self._records)} files to {validated_path}")

            # Sync to Redis if enabled
            if self.redis_client and self.config.use_redis:
                self._sync_to_redis()

            return True

        except OSError as e:
            logger.error(f"Failed to save index: {e}")
            return False

    def _sync_to_redis(self) -> None:
        """Sync index to Redis for real-time access."""
        if not self.redis_client:
            return

        try:
            prefix = self.config.redis_key_prefix

            # Store summary
            self.redis_client.set(
                f"{prefix}:summary",
                json.dumps(self._summary.to_dict()),
            )

            # Store each file record
            for path, record in self._records.items():
                self.redis_client.hset(
                    f"{prefix}:files",
                    path,
                    json.dumps(record.to_dict()),
                )

            # Store metadata
            self.redis_client.set(
                f"{prefix}:meta",
                json.dumps(
                    {
                        "generated_at": datetime.now().isoformat(),
                        "file_count": len(self._records),
                    },
                ),
            )

            logger.info(f"Synced index to Redis with prefix {prefix}")

        except Exception as e:
            logger.error(f"Failed to sync to Redis: {e}")

    # ===== Index Operations =====

    def refresh(self) -> None:
        """Refresh the entire index by scanning the project.

        This rebuilds the index from scratch.
        """
        logger.info(f"Refreshing index for {self.project_root}")

        scanner = ProjectScanner(str(self.project_root), self.config)
        records, summary = scanner.scan()

        # Update internal state
        self._records = {r.path: r for r in records}
        self._summary = summary
        self._generated_at = datetime.now()

        # Save to disk
        self.save()

        logger.info(
            f"Index refreshed: {len(self._records)} files, {summary.files_needing_attention} need attention",
        )

    def update_file(self, path: str, **updates: Any) -> bool:
        """Update metadata for a specific file.

        This is the write API for workflows and agents.

        Args:
            path: Relative path to the file
            **updates: Key-value pairs to update

        Returns:
            True if updated successfully

        """
        if path not in self._records:
            logger.warning(f"File not in index: {path}")
            return False

        record = self._records[path]

        # Apply updates
        for key, value in updates.items():
            if hasattr(record, key):
                setattr(record, key, value)
            else:
                # Store in metadata
                record.metadata[key] = value

        record.last_indexed = datetime.now()

        # Save changes
        self.save()

        return True

    def update_coverage(self, coverage_data: dict[str, float]) -> int:
        """Update coverage data for files.

        Args:
            coverage_data: Dict mapping file paths to coverage percentages

        Returns:
            Number of files updated

        """
        updated = 0

        for path, coverage in coverage_data.items():
            # Normalize path
            path = path.removeprefix("./")

            if path in self._records:
                self._records[path].coverage_percent = coverage
                updated += 1

        if updated > 0:
            # Recalculate summary
            self._recalculate_summary()
            self.save()

        logger.info(f"Updated coverage for {updated} files")
        return updated

    def _recalculate_summary(self) -> None:
        """Recalculate summary from current records."""
        records = list(self._records.values())

        # Testing health with coverage
        covered = [r for r in records if r.coverage_percent > 0]
        if covered:
            self._summary.test_coverage_avg = sum(r.coverage_percent for r in covered) / len(
                covered,
            )

    # ===== Query API =====

    def get_file(self, path: str) -> FileRecord | None:
        """Get record for a specific file."""
        return self._records.get(path)

    def get_summary(self) -> ProjectSummary:
        """Get project summary."""
        return self._summary

    def get_all_files(self) -> list[FileRecord]:
        """Get all file records."""
        return list(self._records.values())

    def get_files_needing_tests(self) -> list[FileRecord]:
        """Get files that need tests but don't have them."""
        return [
            r
            for r in self._records.values()
            if r.test_requirement.value == "required" and not r.tests_exist
        ]

    def get_stale_files(self) -> list[FileRecord]:
        """Get files with stale tests."""
        return [r for r in self._records.values() if r.is_stale]

    def get_files_needing_attention(self) -> list[FileRecord]:
        """Get files that need attention."""
        return sorted(
            [r for r in self._records.values() if r.needs_attention],
            key=lambda r: -r.impact_score,
        )

    def get_high_impact_files(self) -> list[FileRecord]:
        """Get high-impact files sorted by impact score."""
        return sorted(
            [
                r
                for r in self._records.values()
                if r.impact_score >= self.config.high_impact_threshold
            ],
            key=lambda r: -r.impact_score,
        )

    def get_files_by_category(self, category: str) -> list[FileRecord]:
        """Get files by category."""
        return [r for r in self._records.values() if r.category.value == category]

    def get_files_by_language(self, language: str) -> list[FileRecord]:
        """Get files by programming language."""
        return [r for r in self._records.values() if r.language == language]

    def search_files(self, pattern: str) -> list[FileRecord]:
        """Search files by path pattern."""
        import fnmatch

        return [r for r in self._records.values() if fnmatch.fnmatch(r.path, pattern)]

    def get_dependents(self, path: str) -> list[FileRecord]:
        """Get files that depend on the given file."""
        record = self._records.get(path)
        if not record:
            return []
        return [self._records[p] for p in record.imported_by if p in self._records]

    def get_dependencies(self, path: str) -> list[FileRecord]:
        """Get files that the given file depends on."""
        record = self._records.get(path)
        if not record:
            return []
        # Match imports to paths
        results = []
        for imp in record.imports:
            for other_path, other_record in self._records.items():
                if imp in other_path.replace("/", ".").replace("\\", "."):
                    results.append(other_record)
                    break
        return results

    # ===== Statistics =====

    def get_test_gap_stats(self) -> dict[str, Any]:
        """Get statistics about test gaps."""
        files_needing_tests = self.get_files_needing_tests()

        return {
            "files_without_tests": len(files_needing_tests),
            "high_impact_untested": len(
                [
                    f
                    for f in files_needing_tests
                    if f.impact_score >= self.config.high_impact_threshold
                ],
            ),
            "total_loc_untested": sum(f.lines_of_code for f in files_needing_tests),
            "by_directory": self._group_by_directory(files_needing_tests),
        }

    def get_staleness_stats(self) -> dict[str, Any]:
        """Get statistics about stale tests."""
        stale = self.get_stale_files()

        return {
            "stale_count": len(stale),
            "avg_staleness_days": sum(f.staleness_days for f in stale) / len(stale) if stale else 0,
            "max_staleness_days": max((f.staleness_days for f in stale), default=0),
            "by_directory": self._group_by_directory(stale),
        }

    def _group_by_directory(self, records: list[FileRecord]) -> dict[str, int]:
        """Group records by top-level directory."""
        counts: dict[str, int] = {}
        for r in records:
            parts = r.path.split("/")
            if len(parts) > 1:
                dir_name = parts[0]
            else:
                dir_name = "."
            counts[dir_name] = counts.get(dir_name, 0) + 1
        return counts

    # ===== Context for Workflows =====

    def get_context_for_workflow(self, workflow_type: str) -> dict[str, Any]:
        """Get relevant context for a specific workflow type.

        This provides a filtered view of the index tailored to workflow needs.
        """
        if workflow_type == "test_gen":
            files = self.get_files_needing_tests()
            return {
                "files_needing_tests": [f.to_dict() for f in files[:20]],
                "summary": self.get_test_gap_stats(),
                "priority_files": [
                    f.path for f in files if f.impact_score >= self.config.high_impact_threshold
                ][:10],
            }

        if workflow_type == "code_review":
            return {
                "high_impact_files": [f.to_dict() for f in self.get_high_impact_files()[:10]],
                "stale_files": [f.to_dict() for f in self.get_stale_files()[:10]],
                "summary": self._summary.to_dict(),
            }

        if workflow_type == "security_audit":
            return {
                "all_source_files": [f.to_dict() for f in self.get_files_by_category("source")],
                "untested_files": [f.to_dict() for f in self.get_files_needing_tests()],
                "summary": self._summary.to_dict(),
            }

        return {
            "summary": self._summary.to_dict(),
            "files_needing_attention": [
                f.to_dict() for f in self.get_files_needing_attention()[:20]
            ],
        }
