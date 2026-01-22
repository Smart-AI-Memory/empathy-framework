"""Persistent disk storage for cache with TTL support.

Provides hybrid in-memory + disk persistence for cache entries.

Copyright 2025 Smart-AI-Memory
Licensed under Fair Source License 0.9
"""

import json
import logging
import time
from pathlib import Path
from typing import Any

from empathy_os.config import _validate_file_path

from .base import CacheEntry

logger = logging.getLogger(__name__)


class CacheStorage:
    """Hybrid in-memory + disk cache storage with TTL.

    Provides:
    - In-memory LRU cache for fast access
    - Persistent disk storage for cache survival across restarts
    - TTL-based expiration
    - Automatic cleanup of expired entries

    Example:
        storage = CacheStorage()
        storage.put(entry)
        entry = storage.get(cache_key)

    """

    def __init__(
        self,
        cache_dir: Path | None = None,
        max_disk_mb: int = 500,
        auto_save: bool = True,
    ):
        """Initialize cache storage.

        Args:
            cache_dir: Directory for cache files (default: ~/.empathy/cache/).
            max_disk_mb: Maximum disk cache size in MB.
            auto_save: Automatically save to disk on put (default: True).

        """
        self.cache_dir = cache_dir or Path.home() / ".empathy" / "cache"
        self.cache_file = self.cache_dir / "responses.json"
        self.max_disk_mb = max_disk_mb
        self.auto_save = auto_save

        # Ensure cache directory exists
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Load cache from disk
        self._entries: dict[str, CacheEntry] = {}
        self.load()

        logger.debug(
            f"CacheStorage initialized (dir: {self.cache_dir}, "
            f"max: {max_disk_mb}MB, entries: {len(self._entries)})"
        )

    def load(self) -> int:
        """Load cache from disk into memory.

        Returns:
            Number of entries loaded.

        """
        if not self.cache_file.exists():
            logger.debug("No cache file found, starting fresh")
            return 0

        try:
            with open(self.cache_file) as f:
                data = json.load(f)

            version = data.get("version", "unknown")
            entries_data = data.get("entries", [])

            # Load entries
            loaded = 0
            current_time = time.time()

            for entry_data in entries_data:
                entry = CacheEntry(
                    key=entry_data["key"],
                    response=entry_data["response"],
                    workflow=entry_data["workflow"],
                    stage=entry_data["stage"],
                    model=entry_data["model"],
                    prompt_hash=entry_data["prompt_hash"],
                    timestamp=entry_data["timestamp"],
                    ttl=entry_data.get("ttl"),
                )

                # Skip expired entries
                if entry.is_expired(current_time):
                    continue

                self._entries[entry.key] = entry
                loaded += 1

            logger.info(
                f"Loaded {loaded} cache entries from disk (version: {version}, "
                f"skipped {len(entries_data) - loaded} expired)"
            )
            return loaded

        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Failed to load cache from disk: {e}")
            return 0

    def save(self) -> bool:
        """Save cache to disk.

        Returns:
            True if saved successfully, False otherwise.

        """
        try:
            # Prepare data
            data = {
                "version": "3.8.0",
                "timestamp": time.time(),
                "entries": [
                    {
                        "key": entry.key,
                        "response": entry.response,
                        "workflow": entry.workflow,
                        "stage": entry.stage,
                        "model": entry.model,
                        "prompt_hash": entry.prompt_hash,
                        "timestamp": entry.timestamp,
                        "ttl": entry.ttl,
                    }
                    for entry in self._entries.values()
                ],
            }

            # Write to disk
            validated_path = _validate_file_path(str(self.cache_file))
            with open(validated_path, "w") as f:
                json.dump(data, f, indent=2)

            logger.debug(f"Saved {len(self._entries)} cache entries to disk")
            return True

        except (OSError, TypeError, ValueError) as e:
            logger.error(f"Failed to save cache to disk: {e}")
            return False

    def get(self, cache_key: str) -> CacheEntry | None:
        """Get entry from storage.

        Args:
            cache_key: Cache key to lookup.

        Returns:
            CacheEntry if found and not expired, None otherwise.

        """
        if cache_key not in self._entries:
            return None

        entry = self._entries[cache_key]

        # Check expiration
        if entry.is_expired(time.time()):
            del self._entries[cache_key]
            return None

        return entry

    def put(self, entry: CacheEntry) -> None:
        """Store entry in storage.

        Args:
            entry: CacheEntry to store.

        """
        self._entries[entry.key] = entry

        # Auto-save to disk if enabled
        if self.auto_save:
            self.save()

    def delete(self, cache_key: str) -> bool:
        """Delete entry from storage.

        Args:
            cache_key: Key to delete.

        Returns:
            True if entry was deleted, False if not found.

        """
        if cache_key in self._entries:
            del self._entries[cache_key]
            if self.auto_save:
                self.save()
            return True
        return False

    def clear(self) -> int:
        """Clear all entries.

        Returns:
            Number of entries cleared.

        """
        count = len(self._entries)
        self._entries.clear()

        if self.auto_save:
            self.save()

        return count

    def evict_expired(self) -> int:
        """Remove all expired entries.

        Returns:
            Number of entries evicted.

        """
        current_time = time.time()
        expired_keys = [
            key for key, entry in self._entries.items() if entry.is_expired(current_time)
        ]

        for key in expired_keys:
            del self._entries[key]

        if expired_keys and self.auto_save:
            self.save()

        return len(expired_keys)

    def get_all(self) -> list[CacheEntry]:
        """Get all non-expired entries.

        Returns:
            List of CacheEntry objects.

        """
        current_time = time.time()
        return [entry for entry in self._entries.values() if not entry.is_expired(current_time)]

    def size_mb(self) -> float:
        """Estimate cache size in MB.

        Returns:
            Estimated size in megabytes.

        """
        if not self.cache_file.exists():
            return 0.0

        return self.cache_file.stat().st_size / (1024 * 1024)

    def stats(self) -> dict[str, Any]:
        """Get storage statistics.

        Returns:
            Dictionary with storage metrics.

        """
        current_time = time.time()
        expired = sum(1 for entry in self._entries.values() if entry.is_expired(current_time))

        return {
            "total_entries": len(self._entries),
            "expired_entries": expired,
            "active_entries": len(self._entries) - expired,
            "disk_size_mb": round(self.size_mb(), 2),
            "max_disk_mb": self.max_disk_mb,
            "cache_dir": str(self.cache_dir),
        }
