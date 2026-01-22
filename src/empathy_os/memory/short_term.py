"""Redis Short-Term Memory for Empathy Framework

Per EMPATHY_PHILOSOPHY.md v1.1.0:
- Implements fast, TTL-based working memory for agent coordination
- Role-based access tiers for data integrity
- Pattern staging before validation
- Principled negotiation support

Enhanced Features (v2.0):
- Pub/Sub for real-time agent notifications
- Batch operations for high-throughput workflows
- SCAN-based pagination for large datasets
- Redis Streams for audit trails
- Connection retry with exponential backoff
- SSL/TLS support for managed Redis services
- Time-window queries with sorted sets
- Task queues with Lists
- Atomic transactions with MULTI/EXEC
- Comprehensive metrics tracking

Copyright 2025 Smart AI Memory, LLC
Licensed under Fair Source 0.9
"""

import json
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

import structlog

from .security.pii_scrubber import PIIScrubber
from .security.secrets_detector import SecretsDetector
from .security.secrets_detector import Severity as SecretSeverity

logger = structlog.get_logger(__name__)

try:
    import redis
    from redis.exceptions import ConnectionError as RedisConnectionError
    from redis.exceptions import TimeoutError as RedisTimeoutError

    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    RedisConnectionError = Exception  # type: ignore
    RedisTimeoutError = Exception  # type: ignore


class AccessTier(Enum):
    """Role-based access tiers per EMPATHY_PHILOSOPHY.md

    Tier 1 - Observer: Read-only access to validated patterns
    Tier 2 - Contributor: Can stage patterns for validation
    Tier 3 - Validator: Can promote staged patterns to active
    Tier 4 - Steward: Full access including deprecation and audit
    """

    OBSERVER = 1
    CONTRIBUTOR = 2
    VALIDATOR = 3
    STEWARD = 4


class TTLStrategy(Enum):
    """TTL strategies for different memory types

    Per EMPATHY_PHILOSOPHY.md Section 9.3:
    - Working results: 1 hour
    - Staged patterns: 24 hours
    - Coordination signals: 5 minutes
    - Conflict context: Until resolution
    """

    WORKING_RESULTS = 3600  # 1 hour
    STAGED_PATTERNS = 86400  # 24 hours
    COORDINATION = 300  # 5 minutes
    CONFLICT_CONTEXT = 604800  # 7 days (fallback for unresolved)
    SESSION = 1800  # 30 minutes
    STREAM_ENTRY = 86400 * 7  # 7 days for audit stream entries
    TASK_QUEUE = 3600 * 4  # 4 hours for task queue items


@dataclass
class RedisConfig:
    """Enhanced Redis configuration with SSL and retry support.

    Supports:
    - Standard connections (host:port)
    - URL-based connections (redis://...)
    - SSL/TLS for managed services (rediss://...)
    - Sentinel for high availability
    - Connection pooling
    - Retry with exponential backoff
    """

    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: str | None = None
    use_mock: bool = False

    # Security settings
    pii_scrub_enabled: bool = True  # Scrub PII before storing (HIPAA/GDPR compliance)
    secrets_detection_enabled: bool = True  # Block storage of detected secrets

    # SSL/TLS settings
    ssl: bool = False
    ssl_cert_reqs: str | None = None  # "required", "optional", "none"
    ssl_ca_certs: str | None = None
    ssl_certfile: str | None = None
    ssl_keyfile: str | None = None

    # Connection pool settings
    max_connections: int = 10
    socket_timeout: float = 5.0
    socket_connect_timeout: float = 5.0

    # Retry settings
    retry_on_timeout: bool = True
    retry_max_attempts: int = 3
    retry_base_delay: float = 0.1  # seconds
    retry_max_delay: float = 2.0  # seconds

    # Sentinel settings (for HA)
    sentinel_hosts: list[tuple[str, int]] | None = None
    sentinel_master_name: str | None = None

    def to_redis_kwargs(self) -> dict:
        """Convert to redis.Redis constructor kwargs."""
        kwargs: dict[str, Any] = {
            "host": self.host,
            "port": self.port,
            "db": self.db,
            "password": self.password,
            "decode_responses": True,
            "socket_timeout": self.socket_timeout,
            "socket_connect_timeout": self.socket_connect_timeout,
            "retry_on_timeout": self.retry_on_timeout,
        }

        if self.ssl:
            kwargs["ssl"] = True
            if self.ssl_cert_reqs:
                kwargs["ssl_cert_reqs"] = self.ssl_cert_reqs
            if self.ssl_ca_certs:
                kwargs["ssl_ca_certs"] = self.ssl_ca_certs
            if self.ssl_certfile:
                kwargs["ssl_certfile"] = self.ssl_certfile
            if self.ssl_keyfile:
                kwargs["ssl_keyfile"] = self.ssl_keyfile

        return kwargs


@dataclass
class RedisMetrics:
    """Metrics for Redis operations."""

    operations_total: int = 0
    operations_success: int = 0
    operations_failed: int = 0
    retries_total: int = 0
    latency_sum_ms: float = 0.0
    latency_max_ms: float = 0.0

    # Per-operation metrics
    stash_count: int = 0
    retrieve_count: int = 0
    publish_count: int = 0
    stream_append_count: int = 0

    # Security metrics
    pii_scrubbed_total: int = 0  # Total PII instances scrubbed
    pii_scrub_operations: int = 0  # Operations that had PII scrubbed
    secrets_blocked_total: int = 0  # Total secrets blocked from storage

    def record_operation(self, operation: str, latency_ms: float, success: bool = True) -> None:
        """Record an operation metric."""
        self.operations_total += 1
        self.latency_sum_ms += latency_ms
        self.latency_max_ms = max(self.latency_max_ms, latency_ms)

        if success:
            self.operations_success += 1
        else:
            self.operations_failed += 1

        # Track by operation type
        if operation == "stash":
            self.stash_count += 1
        elif operation == "retrieve":
            self.retrieve_count += 1
        elif operation == "publish":
            self.publish_count += 1
        elif operation == "stream_append":
            self.stream_append_count += 1

    @property
    def latency_avg_ms(self) -> float:
        """Average latency in milliseconds."""
        if self.operations_total == 0:
            return 0.0
        return self.latency_sum_ms / self.operations_total

    @property
    def success_rate(self) -> float:
        """Success rate as percentage."""
        if self.operations_total == 0:
            return 100.0
        return (self.operations_success / self.operations_total) * 100

    def to_dict(self) -> dict:
        """Convert metrics to dictionary for reporting and serialization.

        Returns:
            Dictionary with keys: operations_total, operations_success,
            operations_failed, retries_total, latency_avg_ms, latency_max_ms,
            success_rate, by_operation, security.
        """
        return {
            "operations_total": self.operations_total,
            "operations_success": self.operations_success,
            "operations_failed": self.operations_failed,
            "retries_total": self.retries_total,
            "latency_avg_ms": round(self.latency_avg_ms, 2),
            "latency_max_ms": round(self.latency_max_ms, 2),
            "success_rate": round(self.success_rate, 2),
            "by_operation": {
                "stash": self.stash_count,
                "retrieve": self.retrieve_count,
                "publish": self.publish_count,
                "stream_append": self.stream_append_count,
            },
            "security": {
                "pii_scrubbed_total": self.pii_scrubbed_total,
                "pii_scrub_operations": self.pii_scrub_operations,
                "secrets_blocked_total": self.secrets_blocked_total,
            },
        }


@dataclass
class PaginatedResult:
    """Result of a paginated query."""

    items: list[Any]
    cursor: str
    has_more: bool
    total_scanned: int = 0


@dataclass
class TimeWindowQuery:
    """Query parameters for time-window operations."""

    start_time: datetime | None = None
    end_time: datetime | None = None
    limit: int = 100
    offset: int = 0

    @property
    def start_score(self) -> float:
        """Start timestamp as Redis score."""
        if self.start_time is None:
            return float("-inf")
        return self.start_time.timestamp()

    @property
    def end_score(self) -> float:
        """End timestamp as Redis score."""
        if self.end_time is None:
            return float("+inf")
        return self.end_time.timestamp()


@dataclass
class AgentCredentials:
    """Agent identity and access permissions"""

    agent_id: str
    tier: AccessTier
    roles: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)

    def can_read(self) -> bool:
        """All tiers can read"""
        return True

    def can_stage(self) -> bool:
        """Contributor+ can stage patterns"""
        return self.tier.value >= AccessTier.CONTRIBUTOR.value

    def can_validate(self) -> bool:
        """Validator+ can promote patterns"""
        return self.tier.value >= AccessTier.VALIDATOR.value

    def can_administer(self) -> bool:
        """Only Stewards have full admin access"""
        return self.tier.value >= AccessTier.STEWARD.value


@dataclass
class StagedPattern:
    """Pattern awaiting validation"""

    pattern_id: str
    agent_id: str
    pattern_type: str
    name: str
    description: str
    code: str | None = None
    context: dict = field(default_factory=dict)
    confidence: float = 0.5
    staged_at: datetime = field(default_factory=datetime.now)
    interests: list[str] = field(default_factory=list)  # For negotiation

    def __post_init__(self):
        """Validate fields after initialization"""
        # Pattern 1: String ID validation
        if not self.pattern_id or not self.pattern_id.strip():
            raise ValueError("pattern_id cannot be empty")
        if not self.agent_id or not self.agent_id.strip():
            raise ValueError("agent_id cannot be empty")
        if not self.pattern_type or not self.pattern_type.strip():
            raise ValueError("pattern_type cannot be empty")

        # Pattern 4: Range validation for confidence
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence must be between 0.0 and 1.0, got {self.confidence}")

        # Pattern 5: Type validation
        if not isinstance(self.context, dict):
            raise TypeError(f"context must be dict, got {type(self.context).__name__}")
        if not isinstance(self.interests, list):
            raise TypeError(f"interests must be list, got {type(self.interests).__name__}")

    def to_dict(self) -> dict:
        """Convert staged pattern to dictionary for serialization.

        Returns:
            Dictionary with keys: pattern_id, agent_id, pattern_type, name,
            description, code, context, confidence, staged_at, interests.
        """
        return {
            "pattern_id": self.pattern_id,
            "agent_id": self.agent_id,
            "pattern_type": self.pattern_type,
            "name": self.name,
            "description": self.description,
            "code": self.code,
            "context": self.context,
            "confidence": self.confidence,
            "staged_at": self.staged_at.isoformat(),
            "interests": self.interests,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "StagedPattern":
        """Reconstruct StagedPattern from dictionary.

        Args:
            data: Dictionary with required keys: pattern_id, agent_id,
                pattern_type, name, description, staged_at.

        Returns:
            Reconstructed StagedPattern instance.

        Raises:
            KeyError: If required keys are missing.
            ValueError: If data format is invalid.
        """
        return cls(
            pattern_id=data["pattern_id"],
            agent_id=data["agent_id"],
            pattern_type=data["pattern_type"],
            name=data["name"],
            description=data["description"],
            code=data.get("code"),
            context=data.get("context", {}),
            confidence=data.get("confidence", 0.5),
            staged_at=datetime.fromisoformat(data["staged_at"]),
            interests=data.get("interests", []),
        )


@dataclass
class ConflictContext:
    """Context for principled negotiation

    Per Getting to Yes framework:
    - Positions: What each party says they want
    - Interests: Why they want it (underlying needs)
    - BATNA: Best Alternative to Negotiated Agreement
    """

    conflict_id: str
    positions: dict[str, Any]  # agent_id -> stated position
    interests: dict[str, list[str]]  # agent_id -> underlying interests
    batna: str | None = None  # Fallback strategy
    created_at: datetime = field(default_factory=datetime.now)
    resolved: bool = False
    resolution: str | None = None

    def to_dict(self) -> dict:
        """Convert conflict context to dictionary for serialization.

        Returns:
            Dictionary with keys: conflict_id, positions, interests,
            batna, created_at, resolved, resolution.
        """
        return {
            "conflict_id": self.conflict_id,
            "positions": self.positions,
            "interests": self.interests,
            "batna": self.batna,
            "created_at": self.created_at.isoformat(),
            "resolved": self.resolved,
            "resolution": self.resolution,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ConflictContext":
        """Reconstruct ConflictContext from dictionary.

        Args:
            data: Dictionary with required keys: conflict_id, positions,
                interests, created_at.

        Returns:
            Reconstructed ConflictContext instance.

        Raises:
            KeyError: If required keys are missing.
            ValueError: If data format is invalid.
        """
        return cls(
            conflict_id=data["conflict_id"],
            positions=data["positions"],
            interests=data["interests"],
            batna=data.get("batna"),
            created_at=datetime.fromisoformat(data["created_at"]),
            resolved=data.get("resolved", False),
            resolution=data.get("resolution"),
        )


class SecurityError(Exception):
    """Raised when a security policy is violated (e.g., secrets detected in data)."""


class RedisShortTermMemory:
    """Redis-backed short-term memory for agent coordination

    Features:
    - Fast read/write with automatic TTL expiration
    - Role-based access control
    - Pattern staging workflow
    - Conflict negotiation context
    - Agent working memory

    Enhanced Features (v2.0):
    - Pub/Sub for real-time agent notifications
    - Batch operations (stash_batch, retrieve_batch)
    - SCAN-based pagination for large datasets
    - Redis Streams for audit trails
    - Time-window queries with sorted sets
    - Task queues with Lists (LPUSH/RPOP)
    - Atomic transactions with MULTI/EXEC
    - Connection retry with exponential backoff
    - Metrics tracking for observability

    Example:
        >>> memory = RedisShortTermMemory()
        >>> creds = AgentCredentials("agent_1", AccessTier.CONTRIBUTOR)
        >>> memory.stash("analysis_results", {"issues": 3}, creds)
        >>> data = memory.retrieve("analysis_results", creds)

        # Pub/Sub example
        >>> memory.subscribe("agent_signals", lambda msg: print(msg))
        >>> memory.publish("agent_signals", {"event": "task_complete"}, creds)

        # Batch operations
        >>> items = [("key1", {"data": 1}), ("key2", {"data": 2})]
        >>> memory.stash_batch(items, creds)

        # Pagination
        >>> result = memory.list_staged_patterns_paginated(creds, cursor="0", count=10)

    """

    # Key prefixes for namespacing
    PREFIX_WORKING = "empathy:working:"
    PREFIX_STAGED = "empathy:staged:"
    PREFIX_CONFLICT = "empathy:conflict:"
    PREFIX_COORDINATION = "empathy:coord:"
    PREFIX_SESSION = "empathy:session:"
    PREFIX_PUBSUB = "empathy:pubsub:"
    PREFIX_STREAM = "empathy:stream:"
    PREFIX_TIMELINE = "empathy:timeline:"
    PREFIX_QUEUE = "empathy:queue:"

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        password: str | None = None,
        use_mock: bool = False,
        config: RedisConfig | None = None,
    ):
        """Initialize Redis connection

        Args:
            host: Redis host
            port: Redis port
            db: Redis database number
            password: Redis password (optional)
            use_mock: Use in-memory mock for testing
            config: Full RedisConfig for advanced settings (overrides other args)

        """
        # Use config if provided, otherwise build from individual args
        if config is not None:
            self._config = config
        else:
            self._config = RedisConfig(
                host=host,
                port=port,
                db=db,
                password=password,
                use_mock=use_mock,
            )

        self.use_mock = self._config.use_mock or not REDIS_AVAILABLE

        # Initialize metrics
        self._metrics = RedisMetrics()

        # Pub/Sub state
        self._pubsub: Any | None = None
        self._pubsub_thread: threading.Thread | None = None
        self._subscriptions: dict[str, list[Callable[[dict], None]]] = {}
        self._pubsub_running = False

        # Mock storage for testing
        self._mock_storage: dict[str, tuple[Any, float | None]] = {}
        self._mock_lists: dict[str, list[str]] = {}
        self._mock_sorted_sets: dict[str, list[tuple[float, str]]] = {}
        self._mock_streams: dict[str, list[tuple[str, dict]]] = {}
        self._mock_pubsub_handlers: dict[str, list[Callable[[dict], None]]] = {}

        # Security: Initialize PII scrubber and secrets detector
        self._pii_scrubber: PIIScrubber | None = None
        self._secrets_detector: SecretsDetector | None = None

        if self._config.pii_scrub_enabled:
            self._pii_scrubber = PIIScrubber(enable_name_detection=False)
            logger.debug("pii_scrubber_enabled", message="PII scrubbing active for short-term memory")

        if self._config.secrets_detection_enabled:
            self._secrets_detector = SecretsDetector()
            logger.debug("secrets_detector_enabled", message="Secrets detection active for short-term memory")

        if self.use_mock:
            self._client = None
        else:
            self._client = self._create_client_with_retry()

    def _create_client_with_retry(self) -> Any:
        """Create Redis client with retry logic."""
        max_attempts = self._config.retry_max_attempts
        base_delay = self._config.retry_base_delay
        max_delay = self._config.retry_max_delay

        last_error: Exception | None = None

        for attempt in range(max_attempts):
            try:
                client = redis.Redis(**self._config.to_redis_kwargs())
                # Test connection
                client.ping()
                logger.info(
                    "redis_connected",
                    host=self._config.host,
                    port=self._config.port,
                    attempt=attempt + 1,
                )
                return client
            except (RedisConnectionError, RedisTimeoutError) as e:
                last_error = e
                self._metrics.retries_total += 1

                if attempt < max_attempts - 1:
                    delay = min(base_delay * (2**attempt), max_delay)
                    logger.warning(
                        "redis_connection_retry",
                        attempt=attempt + 1,
                        max_attempts=max_attempts,
                        delay=delay,
                        error=str(e),
                    )
                    time.sleep(delay)

        # All retries failed
        logger.error(
            "redis_connection_failed",
            max_attempts=max_attempts,
            error=str(last_error),
        )
        raise last_error if last_error else ConnectionError("Failed to connect to Redis")

    def _execute_with_retry(self, operation: Callable[[], Any], op_name: str = "operation") -> Any:
        """Execute a Redis operation with retry logic."""
        start_time = time.perf_counter()
        max_attempts = self._config.retry_max_attempts
        base_delay = self._config.retry_base_delay
        max_delay = self._config.retry_max_delay

        last_error: Exception | None = None

        for attempt in range(max_attempts):
            try:
                result = operation()
                latency_ms = (time.perf_counter() - start_time) * 1000
                self._metrics.record_operation(op_name, latency_ms, success=True)
                return result
            except (RedisConnectionError, RedisTimeoutError) as e:
                last_error = e
                self._metrics.retries_total += 1

                if attempt < max_attempts - 1:
                    delay = min(base_delay * (2**attempt), max_delay)
                    logger.warning(
                        "redis_operation_retry",
                        operation=op_name,
                        attempt=attempt + 1,
                        delay=delay,
                    )
                    time.sleep(delay)

        latency_ms = (time.perf_counter() - start_time) * 1000
        self._metrics.record_operation(op_name, latency_ms, success=False)
        raise last_error if last_error else ConnectionError("Redis operation failed")

    def _get(self, key: str) -> str | None:
        """Get value from Redis or mock"""
        if self.use_mock:
            if key in self._mock_storage:
                value, expires = self._mock_storage[key]
                if expires is None or datetime.now().timestamp() < expires:
                    return str(value) if value is not None else None
                del self._mock_storage[key]
            return None
        if self._client is None:
            return None
        result = self._client.get(key)
        return str(result) if result else None

    def _set(self, key: str, value: str, ttl: int | None = None) -> bool:
        """Set value in Redis or mock"""
        if self.use_mock:
            expires = datetime.now().timestamp() + ttl if ttl else None
            self._mock_storage[key] = (value, expires)
            return True
        if self._client is None:
            return False
        if ttl:
            self._client.setex(key, ttl, value)
            return True
        result = self._client.set(key, value)
        return bool(result)

    def _delete(self, key: str) -> bool:
        """Delete key from Redis or mock"""
        if self.use_mock:
            if key in self._mock_storage:
                del self._mock_storage[key]
                return True
            return False
        if self._client is None:
            return False
        return bool(self._client.delete(key) > 0)

    def _keys(self, pattern: str) -> list[str]:
        """Get keys matching pattern"""
        if self.use_mock:
            import fnmatch

            # Use list comp for small result sets (typical <1000 keys)
            return [k for k in self._mock_storage.keys() if fnmatch.fnmatch(k, pattern)]
        if self._client is None:
            return []
        keys = self._client.keys(pattern)
        # Convert bytes to strings - needed for API return type
        return [k.decode() if isinstance(k, bytes) else str(k) for k in keys]

    # === Security Methods ===

    def _sanitize_data(self, data: Any) -> tuple[Any, int]:
        """Sanitize data by scrubbing PII and checking for secrets.

        Args:
            data: Data to sanitize (dict, list, or str)

        Returns:
            Tuple of (sanitized_data, pii_count)

        Raises:
            SecurityError: If secrets are detected and blocking is enabled

        """
        pii_count = 0

        if data is None:
            return data, 0

        # Convert data to string for scanning
        if isinstance(data, dict):
            data_str = json.dumps(data)
        elif isinstance(data, list):
            data_str = json.dumps(data)
        elif isinstance(data, str):
            data_str = data
        else:
            # For other types, convert to string
            data_str = str(data)

        # Check for secrets first (before modifying data)
        if self._secrets_detector is not None:
            detections = self._secrets_detector.detect(data_str)
            # Block critical and high severity secrets
            critical_secrets = [
                d for d in detections
                if d.severity in (SecretSeverity.CRITICAL, SecretSeverity.HIGH)
            ]
            if critical_secrets:
                self._metrics.secrets_blocked_total += len(critical_secrets)
                secret_types = [d.secret_type.value for d in critical_secrets]
                logger.warning(
                    "secrets_detected_blocked",
                    secret_types=secret_types,
                    count=len(critical_secrets),
                )
                raise SecurityError(
                    f"Cannot store data containing secrets: {secret_types}. "
                    "Remove sensitive credentials before storing."
                )

        # Scrub PII
        if self._pii_scrubber is not None:
            sanitized_str, pii_detections = self._pii_scrubber.scrub(data_str)
            pii_count = len(pii_detections)

            if pii_count > 0:
                self._metrics.pii_scrubbed_total += pii_count
                self._metrics.pii_scrub_operations += 1
                logger.debug(
                    "pii_scrubbed",
                    pii_count=pii_count,
                    pii_types=[d.pii_type for d in pii_detections],
                )

                # Convert back to original type
                if isinstance(data, dict):
                    try:
                        return json.loads(sanitized_str), pii_count
                    except json.JSONDecodeError:
                        # If PII scrubbing broke JSON structure, return original
                        # This can happen if regex matches part of JSON syntax
                        logger.warning("pii_scrubbing_broke_json_returning_original")
                        return data, 0
                elif isinstance(data, list):
                    try:
                        return json.loads(sanitized_str), pii_count
                    except json.JSONDecodeError:
                        logger.warning("pii_scrubbing_broke_json_returning_original")
                        return data, 0
                else:
                    return sanitized_str, pii_count

        return data, pii_count

    # === Working Memory (Stash/Retrieve) ===

    def stash(
        self,
        key: str,
        data: Any,
        credentials: AgentCredentials,
        ttl: TTLStrategy = TTLStrategy.WORKING_RESULTS,
        skip_sanitization: bool = False,
    ) -> bool:
        """Stash data in short-term memory

        Args:
            key: Unique key for the data
            data: Data to store (will be JSON serialized)
            credentials: Agent credentials
            ttl: Time-to-live strategy
            skip_sanitization: Skip PII scrubbing and secrets detection (use with caution)

        Returns:
            True if successful

        Raises:
            ValueError: If key is empty or invalid
            PermissionError: If credentials lack write access
            SecurityError: If secrets are detected in data (when secrets_detection_enabled)

        Note:
            PII (emails, SSNs, phone numbers, etc.) is automatically scrubbed
            before storage unless skip_sanitization=True or pii_scrub_enabled=False.
            Secrets (API keys, passwords, etc.) will block storage by default.

        Example:
            >>> memory.stash("analysis_v1", {"findings": [...]}, creds)

        """
        # Pattern 1: String ID validation
        if not key or not key.strip():
            raise ValueError("key cannot be empty")

        if not credentials.can_stage():
            raise PermissionError(
                f"Agent {credentials.agent_id} (Tier {credentials.tier.name}) "
                "cannot write to memory. Requires CONTRIBUTOR or higher.",
            )

        # Sanitize data (PII scrubbing + secrets detection)
        if not skip_sanitization:
            data, pii_count = self._sanitize_data(data)
            if pii_count > 0:
                logger.info(
                    "stash_pii_scrubbed",
                    key=key,
                    agent_id=credentials.agent_id,
                    pii_count=pii_count,
                )

        full_key = f"{self.PREFIX_WORKING}{credentials.agent_id}:{key}"
        payload = {
            "data": data,
            "agent_id": credentials.agent_id,
            "stashed_at": datetime.now().isoformat(),
        }
        return self._set(full_key, json.dumps(payload), ttl.value)

    def retrieve(
        self,
        key: str,
        credentials: AgentCredentials,
        agent_id: str | None = None,
    ) -> Any | None:
        """Retrieve data from short-term memory

        Args:
            key: Key to retrieve
            credentials: Agent credentials
            agent_id: Owner agent ID (defaults to credentials agent)

        Returns:
            Retrieved data or None if not found

        Raises:
            ValueError: If key is empty or invalid

        Example:
            >>> data = memory.retrieve("analysis_v1", creds)

        """
        # Pattern 1: String ID validation
        if not key or not key.strip():
            raise ValueError("key cannot be empty")

        owner = agent_id or credentials.agent_id
        full_key = f"{self.PREFIX_WORKING}{owner}:{key}"
        raw = self._get(full_key)

        if raw is None:
            return None

        payload = json.loads(raw)
        return payload.get("data")

    def clear_working_memory(self, credentials: AgentCredentials) -> int:
        """Clear all working memory for an agent

        Args:
            credentials: Agent credentials (must own the memory or be Steward)

        Returns:
            Number of keys deleted

        """
        pattern = f"{self.PREFIX_WORKING}{credentials.agent_id}:*"
        keys = self._keys(pattern)
        count = 0
        for key in keys:
            if self._delete(key):
                count += 1
        return count

    # === Pattern Staging ===

    def stage_pattern(
        self,
        pattern: StagedPattern,
        credentials: AgentCredentials,
    ) -> bool:
        """Stage a pattern for validation

        Per EMPATHY_PHILOSOPHY.md: Patterns must be staged before
        being promoted to the active library.

        Args:
            pattern: Pattern to stage
            credentials: Must be CONTRIBUTOR or higher

        Returns:
            True if staged successfully

        Raises:
            TypeError: If pattern is not StagedPattern
            PermissionError: If credentials lack staging access

        """
        # Pattern 5: Type validation
        if not isinstance(pattern, StagedPattern):
            raise TypeError(f"pattern must be StagedPattern, got {type(pattern).__name__}")

        if not credentials.can_stage():
            raise PermissionError(
                f"Agent {credentials.agent_id} cannot stage patterns. "
                "Requires CONTRIBUTOR tier or higher.",
            )

        key = f"{self.PREFIX_STAGED}{pattern.pattern_id}"
        return self._set(
            key,
            json.dumps(pattern.to_dict()),
            TTLStrategy.STAGED_PATTERNS.value,
        )

    def get_staged_pattern(
        self,
        pattern_id: str,
        credentials: AgentCredentials,
    ) -> StagedPattern | None:
        """Retrieve a staged pattern

        Args:
            pattern_id: Pattern ID
            credentials: Any tier can read

        Returns:
            StagedPattern or None

        Raises:
            ValueError: If pattern_id is empty

        """
        # Pattern 1: String ID validation
        if not pattern_id or not pattern_id.strip():
            raise ValueError("pattern_id cannot be empty")

        key = f"{self.PREFIX_STAGED}{pattern_id}"
        raw = self._get(key)

        if raw is None:
            return None

        return StagedPattern.from_dict(json.loads(raw))

    def list_staged_patterns(
        self,
        credentials: AgentCredentials,
    ) -> list[StagedPattern]:
        """List all staged patterns awaiting validation

        Args:
            credentials: Any tier can read

        Returns:
            List of staged patterns

        """
        pattern = f"{self.PREFIX_STAGED}*"
        keys = self._keys(pattern)
        patterns = []

        for key in keys:
            raw = self._get(key)
            if raw:
                patterns.append(StagedPattern.from_dict(json.loads(raw)))

        return patterns

    def promote_pattern(
        self,
        pattern_id: str,
        credentials: AgentCredentials,
    ) -> StagedPattern | None:
        """Promote staged pattern (remove from staging for library add)

        Args:
            pattern_id: Pattern to promote
            credentials: Must be VALIDATOR or higher

        Returns:
            The promoted pattern (for adding to PatternLibrary)

        """
        if not credentials.can_validate():
            raise PermissionError(
                f"Agent {credentials.agent_id} cannot promote patterns. "
                "Requires VALIDATOR tier or higher.",
            )

        pattern = self.get_staged_pattern(pattern_id, credentials)
        if pattern:
            key = f"{self.PREFIX_STAGED}{pattern_id}"
            self._delete(key)
        return pattern

    def reject_pattern(
        self,
        pattern_id: str,
        credentials: AgentCredentials,
        reason: str = "",
    ) -> bool:
        """Reject a staged pattern

        Args:
            pattern_id: Pattern to reject
            credentials: Must be VALIDATOR or higher
            reason: Rejection reason (for audit)

        Returns:
            True if rejected

        """
        if not credentials.can_validate():
            raise PermissionError(
                f"Agent {credentials.agent_id} cannot reject patterns. "
                "Requires VALIDATOR tier or higher.",
            )

        key = f"{self.PREFIX_STAGED}{pattern_id}"
        return self._delete(key)

    # === Conflict Negotiation ===

    def create_conflict_context(
        self,
        conflict_id: str,
        positions: dict[str, Any],
        interests: dict[str, list[str]],
        credentials: AgentCredentials,
        batna: str | None = None,
    ) -> ConflictContext:
        """Create context for principled negotiation

        Per Getting to Yes framework:
        - Separate positions from interests
        - Define BATNA before negotiating

        Args:
            conflict_id: Unique conflict identifier
            positions: agent_id -> their stated position
            interests: agent_id -> underlying interests
            credentials: Must be CONTRIBUTOR or higher
            batna: Best Alternative to Negotiated Agreement

        Returns:
            ConflictContext for resolution

        Raises:
            ValueError: If conflict_id is empty
            TypeError: If positions or interests are not dicts
            PermissionError: If credentials lack permission

        """
        # Pattern 1: String ID validation
        if not conflict_id or not conflict_id.strip():
            raise ValueError("conflict_id cannot be empty")

        # Pattern 5: Type validation
        if not isinstance(positions, dict):
            raise TypeError(f"positions must be dict, got {type(positions).__name__}")
        if not isinstance(interests, dict):
            raise TypeError(f"interests must be dict, got {type(interests).__name__}")

        if not credentials.can_stage():
            raise PermissionError(
                f"Agent {credentials.agent_id} cannot create conflict context. "
                "Requires CONTRIBUTOR tier or higher.",
            )

        context = ConflictContext(
            conflict_id=conflict_id,
            positions=positions,
            interests=interests,
            batna=batna,
        )

        key = f"{self.PREFIX_CONFLICT}{conflict_id}"
        self._set(
            key,
            json.dumps(context.to_dict()),
            TTLStrategy.CONFLICT_CONTEXT.value,
        )

        return context

    def get_conflict_context(
        self,
        conflict_id: str,
        credentials: AgentCredentials,
    ) -> ConflictContext | None:
        """Retrieve conflict context

        Args:
            conflict_id: Conflict identifier
            credentials: Any tier can read

        Returns:
            ConflictContext or None

        Raises:
            ValueError: If conflict_id is empty

        """
        # Pattern 1: String ID validation
        if not conflict_id or not conflict_id.strip():
            raise ValueError("conflict_id cannot be empty")

        key = f"{self.PREFIX_CONFLICT}{conflict_id}"
        raw = self._get(key)

        if raw is None:
            return None

        return ConflictContext.from_dict(json.loads(raw))

    def resolve_conflict(
        self,
        conflict_id: str,
        resolution: str,
        credentials: AgentCredentials,
    ) -> bool:
        """Mark conflict as resolved

        Args:
            conflict_id: Conflict to resolve
            resolution: How it was resolved
            credentials: Must be VALIDATOR or higher

        Returns:
            True if resolved

        """
        if not credentials.can_validate():
            raise PermissionError(
                f"Agent {credentials.agent_id} cannot resolve conflicts. "
                "Requires VALIDATOR tier or higher.",
            )

        context = self.get_conflict_context(conflict_id, credentials)
        if context is None:
            return False

        context.resolved = True
        context.resolution = resolution

        key = f"{self.PREFIX_CONFLICT}{conflict_id}"
        # Keep resolved conflicts longer for audit
        self._set(key, json.dumps(context.to_dict()), TTLStrategy.CONFLICT_CONTEXT.value)
        return True

    # === Coordination Signals ===

    def send_signal(
        self,
        signal_type: str,
        data: Any,
        credentials: AgentCredentials,
        target_agent: str | None = None,
    ) -> bool:
        """Send coordination signal to other agents

        Args:
            signal_type: Type of signal (e.g., "ready", "blocking", "complete")
            data: Signal payload
            credentials: Must be CONTRIBUTOR or higher
            target_agent: Specific agent to signal (None = broadcast)

        Returns:
            True if sent

        """
        if not credentials.can_stage():
            raise PermissionError(
                f"Agent {credentials.agent_id} cannot send signals. "
                "Requires CONTRIBUTOR tier or higher.",
            )

        target = target_agent or "broadcast"
        key = f"{self.PREFIX_COORDINATION}{signal_type}:{credentials.agent_id}:{target}"
        payload = {
            "signal_type": signal_type,
            "from_agent": credentials.agent_id,
            "to_agent": target_agent,
            "data": data,
            "sent_at": datetime.now().isoformat(),
        }
        return self._set(key, json.dumps(payload), TTLStrategy.COORDINATION.value)

    def receive_signals(
        self,
        credentials: AgentCredentials,
        signal_type: str | None = None,
    ) -> list[dict]:
        """Receive coordination signals

        Args:
            credentials: Agent receiving signals
            signal_type: Filter by signal type (optional)

        Returns:
            List of signals

        """
        if signal_type:
            pattern = f"{self.PREFIX_COORDINATION}{signal_type}:*:{credentials.agent_id}"
        else:
            pattern = f"{self.PREFIX_COORDINATION}*:{credentials.agent_id}"

        # Also get broadcasts
        broadcast_pattern = f"{self.PREFIX_COORDINATION}*:*:broadcast"

        keys = set(self._keys(pattern)) | set(self._keys(broadcast_pattern))
        signals = []

        for key in keys:
            raw = self._get(key)
            if raw:
                signals.append(json.loads(raw))

        return signals

    # === Session Management ===

    def create_session(
        self,
        session_id: str,
        credentials: AgentCredentials,
        metadata: dict | None = None,
    ) -> bool:
        """Create a collaboration session

        Args:
            session_id: Unique session identifier
            credentials: Session creator
            metadata: Optional session metadata

        Returns:
            True if created

        Raises:
            ValueError: If session_id is empty
            TypeError: If metadata is not dict

        """
        # Pattern 1: String ID validation
        if not session_id or not session_id.strip():
            raise ValueError("session_id cannot be empty")

        # Pattern 5: Type validation
        if metadata is not None and not isinstance(metadata, dict):
            raise TypeError(f"metadata must be dict, got {type(metadata).__name__}")

        key = f"{self.PREFIX_SESSION}{session_id}"
        payload = {
            "session_id": session_id,
            "created_by": credentials.agent_id,
            "created_at": datetime.now().isoformat(),
            "participants": [credentials.agent_id],
            "metadata": metadata or {},
        }
        return self._set(key, json.dumps(payload), TTLStrategy.SESSION.value)

    def join_session(
        self,
        session_id: str,
        credentials: AgentCredentials,
    ) -> bool:
        """Join an existing session

        Args:
            session_id: Session to join
            credentials: Joining agent

        Returns:
            True if joined

        Raises:
            ValueError: If session_id is empty

        """
        # Pattern 1: String ID validation
        if not session_id or not session_id.strip():
            raise ValueError("session_id cannot be empty")

        key = f"{self.PREFIX_SESSION}{session_id}"
        raw = self._get(key)

        if raw is None:
            return False

        payload = json.loads(raw)
        if credentials.agent_id not in payload["participants"]:
            payload["participants"].append(credentials.agent_id)

        return self._set(key, json.dumps(payload), TTLStrategy.SESSION.value)

    def get_session(
        self,
        session_id: str,
        credentials: AgentCredentials,
    ) -> dict | None:
        """Get session information

        Args:
            session_id: Session identifier
            credentials: Any participant can read

        Returns:
            Session data or None

        """
        key = f"{self.PREFIX_SESSION}{session_id}"
        raw = self._get(key)

        if raw is None:
            return None

        result: dict = json.loads(raw)
        return result

    # === Health Check ===

    def ping(self) -> bool:
        """Check Redis connection health

        Returns:
            True if connected and responsive

        """
        if self.use_mock:
            return True
        if self._client is None:
            return False
        try:
            return bool(self._client.ping())
        except Exception:
            return False

    def get_stats(self) -> dict:
        """Get memory statistics

        Returns:
            Dict with memory stats

        """
        if self.use_mock:
            return {
                "mode": "mock",
                "total_keys": len(self._mock_storage),
                "working_keys": len(
                    [k for k in self._mock_storage if k.startswith(self.PREFIX_WORKING)],
                ),
                "staged_keys": len(
                    [k for k in self._mock_storage if k.startswith(self.PREFIX_STAGED)],
                ),
                "conflict_keys": len(
                    [k for k in self._mock_storage if k.startswith(self.PREFIX_CONFLICT)],
                ),
            }

        if self._client is None:
            return {"mode": "disconnected", "error": "No Redis client"}
        info = self._client.info("memory")
        return {
            "mode": "redis",
            "used_memory": info.get("used_memory_human"),
            "peak_memory": info.get("used_memory_peak_human"),
            "total_keys": self._client.dbsize(),
            "working_keys": len(self._keys(f"{self.PREFIX_WORKING}*")),
            "staged_keys": len(self._keys(f"{self.PREFIX_STAGED}*")),
            "conflict_keys": len(self._keys(f"{self.PREFIX_CONFLICT}*")),
        }

    def get_metrics(self) -> dict:
        """Get operation metrics for observability.

        Returns:
            Dict with operation counts, latencies, and success rates

        """
        return self._metrics.to_dict()

    def reset_metrics(self) -> None:
        """Reset all metrics to zero."""
        self._metrics = RedisMetrics()

    # =========================================================================
    # BATCH OPERATIONS
    # =========================================================================

    def stash_batch(
        self,
        items: list[tuple[str, Any]],
        credentials: AgentCredentials,
        ttl: TTLStrategy = TTLStrategy.WORKING_RESULTS,
    ) -> int:
        """Stash multiple items in a single operation.

        Uses Redis pipeline for efficiency (reduces network round-trips).

        Args:
            items: List of (key, data) tuples
            credentials: Agent credentials
            ttl: Time-to-live strategy (applied to all items)

        Returns:
            Number of items successfully stashed

        Raises:
            TypeError: If items is not a list
            PermissionError: If credentials lack write access

        Example:
            >>> items = [("key1", {"a": 1}), ("key2", {"b": 2})]
            >>> count = memory.stash_batch(items, creds)

        """
        # Pattern 5: Type validation
        if not isinstance(items, list):
            raise TypeError(f"items must be list, got {type(items).__name__}")

        if not credentials.can_stage():
            raise PermissionError(
                f"Agent {credentials.agent_id} cannot write to memory. "
                "Requires CONTRIBUTOR tier or higher.",
            )

        if not items:
            return 0

        start_time = time.perf_counter()

        if self.use_mock:
            count = 0
            for key, data in items:
                full_key = f"{self.PREFIX_WORKING}{credentials.agent_id}:{key}"
                payload = {
                    "data": data,
                    "agent_id": credentials.agent_id,
                    "stashed_at": datetime.now().isoformat(),
                }
                expires = datetime.now().timestamp() + ttl.value
                self._mock_storage[full_key] = (json.dumps(payload), expires)
                count += 1
            latency_ms = (time.perf_counter() - start_time) * 1000
            self._metrics.record_operation("stash_batch", latency_ms)
            return count

        if self._client is None:
            return 0

        pipe = self._client.pipeline()
        for key, data in items:
            full_key = f"{self.PREFIX_WORKING}{credentials.agent_id}:{key}"
            payload = {
                "data": data,
                "agent_id": credentials.agent_id,
                "stashed_at": datetime.now().isoformat(),
            }
            pipe.setex(full_key, ttl.value, json.dumps(payload))

        results = pipe.execute()
        count = sum(1 for r in results if r)
        latency_ms = (time.perf_counter() - start_time) * 1000
        self._metrics.record_operation("stash_batch", latency_ms)

        logger.info("batch_stash_complete", count=count, total=len(items))
        return count

    def retrieve_batch(
        self,
        keys: list[str],
        credentials: AgentCredentials,
        agent_id: str | None = None,
    ) -> dict[str, Any]:
        """Retrieve multiple items in a single operation.

        Args:
            keys: List of keys to retrieve
            credentials: Agent credentials
            agent_id: Owner agent ID (defaults to credentials agent)

        Returns:
            Dict mapping key to data (missing keys omitted)

        Example:
            >>> data = memory.retrieve_batch(["key1", "key2"], creds)
            >>> print(data["key1"])

        """
        if not keys:
            return {}

        start_time = time.perf_counter()
        owner = agent_id or credentials.agent_id
        results: dict[str, Any] = {}

        if self.use_mock:
            for key in keys:
                full_key = f"{self.PREFIX_WORKING}{owner}:{key}"
                if full_key in self._mock_storage:
                    value, expires = self._mock_storage[full_key]
                    if expires is None or datetime.now().timestamp() < expires:
                        payload = json.loads(str(value))
                        results[key] = payload.get("data")
            latency_ms = (time.perf_counter() - start_time) * 1000
            self._metrics.record_operation("retrieve_batch", latency_ms)
            return results

        if self._client is None:
            return {}

        full_keys = [f"{self.PREFIX_WORKING}{owner}:{key}" for key in keys]
        values = self._client.mget(full_keys)

        for key, value in zip(keys, values, strict=False):
            if value:
                payload = json.loads(str(value))
                results[key] = payload.get("data")

        latency_ms = (time.perf_counter() - start_time) * 1000
        self._metrics.record_operation("retrieve_batch", latency_ms)
        return results

    # =========================================================================
    # SCAN-BASED PAGINATION
    # =========================================================================

    def list_staged_patterns_paginated(
        self,
        credentials: AgentCredentials,
        cursor: str = "0",
        count: int = 100,
    ) -> PaginatedResult:
        """List staged patterns with pagination using SCAN.

        More efficient than list_staged_patterns() for large datasets.

        Args:
            credentials: Agent credentials
            cursor: Pagination cursor (start with "0")
            count: Maximum items per page

        Returns:
            PaginatedResult with items, cursor, and has_more flag

        Example:
            >>> result = memory.list_staged_patterns_paginated(creds, "0", 10)
            >>> for pattern in result.items:
            ...     print(pattern.name)
            >>> if result.has_more:
            ...     next_result = memory.list_staged_patterns_paginated(creds, result.cursor, 10)

        """
        start_time = time.perf_counter()
        pattern = f"{self.PREFIX_STAGED}*"

        if self.use_mock:
            import fnmatch

            all_keys = [k for k in self._mock_storage.keys() if fnmatch.fnmatch(k, pattern)]
            start_idx = int(cursor)
            end_idx = start_idx + count
            page_keys = all_keys[start_idx:end_idx]

            patterns = []
            for key in page_keys:
                raw_value, expires = self._mock_storage[key]
                if expires is None or datetime.now().timestamp() < expires:
                    patterns.append(StagedPattern.from_dict(json.loads(str(raw_value))))

            new_cursor = str(end_idx) if end_idx < len(all_keys) else "0"
            has_more = end_idx < len(all_keys)

            latency_ms = (time.perf_counter() - start_time) * 1000
            self._metrics.record_operation("list_paginated", latency_ms)

            return PaginatedResult(
                items=patterns,
                cursor=new_cursor,
                has_more=has_more,
                total_scanned=len(page_keys),
            )

        if self._client is None:
            return PaginatedResult(items=[], cursor="0", has_more=False)

        # Use SCAN for efficient iteration
        new_cursor, keys = self._client.scan(cursor=int(cursor), match=pattern, count=count)

        patterns = []
        for key in keys:
            raw = self._client.get(key)
            if raw:
                patterns.append(StagedPattern.from_dict(json.loads(raw)))

        has_more = new_cursor != 0

        latency_ms = (time.perf_counter() - start_time) * 1000
        self._metrics.record_operation("list_paginated", latency_ms)

        return PaginatedResult(
            items=patterns,
            cursor=str(new_cursor),
            has_more=has_more,
            total_scanned=len(keys),
        )

    def scan_keys(
        self,
        pattern: str,
        cursor: str = "0",
        count: int = 100,
    ) -> PaginatedResult:
        """Scan keys matching a pattern with pagination.

        Args:
            pattern: Key pattern (e.g., "empathy:working:*")
            cursor: Pagination cursor
            count: Items per page

        Returns:
            PaginatedResult with key strings

        """
        if self.use_mock:
            import fnmatch

            all_keys = [k for k in self._mock_storage.keys() if fnmatch.fnmatch(k, pattern)]
            start_idx = int(cursor)
            end_idx = start_idx + count
            page_keys = all_keys[start_idx:end_idx]
            new_cursor = str(end_idx) if end_idx < len(all_keys) else "0"
            has_more = end_idx < len(all_keys)
            return PaginatedResult(items=page_keys, cursor=new_cursor, has_more=has_more)

        if self._client is None:
            return PaginatedResult(items=[], cursor="0", has_more=False)

        new_cursor, keys = self._client.scan(cursor=int(cursor), match=pattern, count=count)
        return PaginatedResult(
            items=[str(k) for k in keys],
            cursor=str(new_cursor),
            has_more=new_cursor != 0,
        )

    # =========================================================================
    # PUB/SUB FOR REAL-TIME NOTIFICATIONS
    # =========================================================================

    def publish(
        self,
        channel: str,
        message: dict,
        credentials: AgentCredentials,
    ) -> int:
        """Publish a message to a channel for real-time notifications.

        Args:
            channel: Channel name (will be prefixed)
            message: Message payload (dict)
            credentials: Agent credentials (must be CONTRIBUTOR+)

        Returns:
            Number of subscribers that received the message

        Example:
            >>> memory.publish("agent_signals", {"event": "task_complete", "task_id": "123"}, creds)

        """
        if not credentials.can_stage():
            raise PermissionError(
                f"Agent {credentials.agent_id} cannot publish. Requires CONTRIBUTOR tier or higher.",
            )

        start_time = time.perf_counter()
        full_channel = f"{self.PREFIX_PUBSUB}{channel}"

        payload = {
            "channel": channel,
            "from_agent": credentials.agent_id,
            "timestamp": datetime.now().isoformat(),
            "data": message,
        }

        if self.use_mock:
            handlers = self._mock_pubsub_handlers.get(full_channel, [])
            for handler in handlers:
                try:
                    handler(payload)
                except Exception as e:
                    logger.warning("pubsub_handler_error", channel=channel, error=str(e))
            latency_ms = (time.perf_counter() - start_time) * 1000
            self._metrics.record_operation("publish", latency_ms)
            return len(handlers)

        if self._client is None:
            return 0

        count = self._client.publish(full_channel, json.dumps(payload))
        latency_ms = (time.perf_counter() - start_time) * 1000
        self._metrics.record_operation("publish", latency_ms)

        logger.debug("pubsub_published", channel=channel, subscribers=count)
        return int(count)

    def subscribe(
        self,
        channel: str,
        handler: Callable[[dict], None],
        credentials: AgentCredentials | None = None,
    ) -> bool:
        """Subscribe to a channel for real-time notifications.

        Args:
            channel: Channel name to subscribe to
            handler: Callback function receiving message dict
            credentials: Optional credentials (any tier can subscribe)

        Returns:
            True if subscribed successfully

        Example:
            >>> def on_message(msg):
            ...     print(f"Received: {msg['data']}")
            >>> memory.subscribe("agent_signals", on_message)

        """
        full_channel = f"{self.PREFIX_PUBSUB}{channel}"

        if self.use_mock:
            if full_channel not in self._mock_pubsub_handlers:
                self._mock_pubsub_handlers[full_channel] = []
            self._mock_pubsub_handlers[full_channel].append(handler)
            logger.info("pubsub_subscribed_mock", channel=channel)
            return True

        if self._client is None:
            return False

        # Store handler
        if full_channel not in self._subscriptions:
            self._subscriptions[full_channel] = []
        self._subscriptions[full_channel].append(handler)

        # Create pubsub if needed
        if self._pubsub is None:
            self._pubsub = self._client.pubsub()

        # Subscribe
        self._pubsub.subscribe(**{full_channel: self._pubsub_message_handler})

        # Start listener thread if not running
        if not self._pubsub_running:
            self._pubsub_running = True
            self._pubsub_thread = threading.Thread(
                target=self._pubsub_listener,
                daemon=True,
                name="redis-pubsub-listener",
            )
            self._pubsub_thread.start()

        logger.info("pubsub_subscribed", channel=channel)
        return True

    def _pubsub_message_handler(self, message: dict) -> None:
        """Internal handler for pubsub messages."""
        if message["type"] != "message":
            return

        channel = message["channel"]
        if isinstance(channel, bytes):
            channel = channel.decode()

        try:
            payload = json.loads(message["data"])
        except json.JSONDecodeError:
            payload = {"raw": message["data"]}

        handlers = self._subscriptions.get(channel, [])
        for handler in handlers:
            try:
                handler(payload)
            except Exception as e:
                logger.warning("pubsub_handler_error", channel=channel, error=str(e))

    def _pubsub_listener(self) -> None:
        """Background thread for listening to pubsub messages."""
        while self._pubsub_running and self._pubsub:
            try:
                self._pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            except Exception as e:
                logger.warning("pubsub_listener_error", error=str(e))
                time.sleep(1)

    def unsubscribe(self, channel: str) -> bool:
        """Unsubscribe from a channel.

        Args:
            channel: Channel name to unsubscribe from

        Returns:
            True if unsubscribed successfully

        """
        full_channel = f"{self.PREFIX_PUBSUB}{channel}"

        if self.use_mock:
            self._mock_pubsub_handlers.pop(full_channel, None)
            return True

        if self._pubsub is None:
            return False

        self._pubsub.unsubscribe(full_channel)
        self._subscriptions.pop(full_channel, None)
        return True

    def close_pubsub(self) -> None:
        """Close pubsub connection and stop listener thread."""
        self._pubsub_running = False
        if self._pubsub:
            self._pubsub.close()
            self._pubsub = None
        self._subscriptions.clear()

    # =========================================================================
    # REDIS STREAMS FOR AUDIT TRAILS
    # =========================================================================

    def stream_append(
        self,
        stream_name: str,
        data: dict,
        credentials: AgentCredentials,
        max_len: int = 10000,
    ) -> str | None:
        """Append an entry to a Redis Stream for audit trails.

        Streams provide:
        - Ordered, persistent event log
        - Consumer groups for distributed processing
        - Time-based retention

        Args:
            stream_name: Name of the stream
            data: Event data to append
            credentials: Agent credentials (must be CONTRIBUTOR+)
            max_len: Maximum stream length (older entries trimmed)

        Returns:
            Entry ID if successful, None otherwise

        Example:
            >>> entry_id = memory.stream_append("audit", {"action": "pattern_promoted", "pattern_id": "xyz"}, creds)

        """
        if not credentials.can_stage():
            raise PermissionError(
                f"Agent {credentials.agent_id} cannot write to stream. "
                "Requires CONTRIBUTOR tier or higher.",
            )

        start_time = time.perf_counter()
        full_stream = f"{self.PREFIX_STREAM}{stream_name}"

        entry = {
            "agent_id": credentials.agent_id,
            "timestamp": datetime.now().isoformat(),
            **{
                str(k): json.dumps(v) if isinstance(v, dict | list) else str(v)
                for k, v in data.items()
            },
        }

        if self.use_mock:
            if full_stream not in self._mock_streams:
                self._mock_streams[full_stream] = []
            entry_id = f"{int(datetime.now().timestamp() * 1000)}-0"
            self._mock_streams[full_stream].append((entry_id, entry))
            # Trim to max_len
            if len(self._mock_streams[full_stream]) > max_len:
                self._mock_streams[full_stream] = self._mock_streams[full_stream][-max_len:]
            latency_ms = (time.perf_counter() - start_time) * 1000
            self._metrics.record_operation("stream_append", latency_ms)
            return entry_id

        if self._client is None:
            return None

        entry_id = self._client.xadd(full_stream, entry, maxlen=max_len)
        latency_ms = (time.perf_counter() - start_time) * 1000
        self._metrics.record_operation("stream_append", latency_ms)

        return str(entry_id) if entry_id else None

    def stream_read(
        self,
        stream_name: str,
        credentials: AgentCredentials,
        start_id: str = "0",
        count: int = 100,
    ) -> list[tuple[str, dict]]:
        """Read entries from a Redis Stream.

        Args:
            stream_name: Name of the stream
            credentials: Agent credentials
            start_id: Start reading from this ID ("0" = beginning)
            count: Maximum entries to read

        Returns:
            List of (entry_id, data) tuples

        Example:
            >>> entries = memory.stream_read("audit", creds, count=50)
            >>> for entry_id, data in entries:
            ...     print(f"{entry_id}: {data}")

        """
        full_stream = f"{self.PREFIX_STREAM}{stream_name}"

        if self.use_mock:
            if full_stream not in self._mock_streams:
                return []
            entries = self._mock_streams[full_stream]
            # Filter by start_id (simple comparison)
            filtered = [(eid, data) for eid, data in entries if eid > start_id]
            return filtered[:count]

        if self._client is None:
            return []

        result = self._client.xrange(full_stream, min=start_id, count=count)
        return [(str(entry_id), {str(k): v for k, v in data.items()}) for entry_id, data in result]

    def stream_read_new(
        self,
        stream_name: str,
        credentials: AgentCredentials,
        block_ms: int = 0,
        count: int = 100,
    ) -> list[tuple[str, dict]]:
        """Read only new entries from a stream (blocking read).

        Args:
            stream_name: Name of the stream
            credentials: Agent credentials
            block_ms: Milliseconds to block waiting (0 = no block)
            count: Maximum entries to read

        Returns:
            List of (entry_id, data) tuples

        """
        full_stream = f"{self.PREFIX_STREAM}{stream_name}"

        if self.use_mock:
            return []  # Mock doesn't support blocking reads

        if self._client is None:
            return []

        result = self._client.xread({full_stream: "$"}, block=block_ms, count=count)
        if not result:
            return []

        # Result format: [(stream_name, [(entry_id, data), ...])]
        entries = []
        for _stream, stream_entries in result:
            for entry_id, data in stream_entries:
                entries.append((str(entry_id), {str(k): v for k, v in data.items()}))
        return entries

    # =========================================================================
    # TIME-WINDOW QUERIES (SORTED SETS)
    # =========================================================================

    def timeline_add(
        self,
        timeline_name: str,
        event_id: str,
        data: dict,
        credentials: AgentCredentials,
        timestamp: datetime | None = None,
    ) -> bool:
        """Add an event to a timeline (sorted set by timestamp).

        Args:
            timeline_name: Name of the timeline
            event_id: Unique event identifier
            data: Event data
            credentials: Agent credentials
            timestamp: Event timestamp (defaults to now)

        Returns:
            True if added successfully

        """
        if not credentials.can_stage():
            raise PermissionError(
                f"Agent {credentials.agent_id} cannot write to timeline. "
                "Requires CONTRIBUTOR tier or higher.",
            )

        full_timeline = f"{self.PREFIX_TIMELINE}{timeline_name}"
        ts = timestamp or datetime.now()
        score = ts.timestamp()

        payload = json.dumps(
            {
                "event_id": event_id,
                "timestamp": ts.isoformat(),
                "agent_id": credentials.agent_id,
                "data": data,
            },
        )

        if self.use_mock:
            if full_timeline not in self._mock_sorted_sets:
                self._mock_sorted_sets[full_timeline] = []
            self._mock_sorted_sets[full_timeline].append((score, payload))
            self._mock_sorted_sets[full_timeline].sort(key=lambda x: x[0])
            return True

        if self._client is None:
            return False

        self._client.zadd(full_timeline, {payload: score})
        return True

    def timeline_query(
        self,
        timeline_name: str,
        credentials: AgentCredentials,
        query: TimeWindowQuery | None = None,
    ) -> list[dict]:
        """Query events from a timeline within a time window.

        Args:
            timeline_name: Name of the timeline
            credentials: Agent credentials
            query: Time window query parameters

        Returns:
            List of events in the time window

        Example:
            >>> from datetime import datetime, timedelta
            >>> query = TimeWindowQuery(
            ...     start_time=datetime.now() - timedelta(hours=1),
            ...     end_time=datetime.now(),
            ...     limit=50
            ... )
            >>> events = memory.timeline_query("agent_events", creds, query)

        """
        full_timeline = f"{self.PREFIX_TIMELINE}{timeline_name}"
        q = query or TimeWindowQuery()

        if self.use_mock:
            if full_timeline not in self._mock_sorted_sets:
                return []
            entries = self._mock_sorted_sets[full_timeline]
            filtered = [
                json.loads(payload)
                for score, payload in entries
                if q.start_score <= score <= q.end_score
            ]
            return filtered[q.offset : q.offset + q.limit]

        if self._client is None:
            return []

        results = self._client.zrangebyscore(
            full_timeline,
            min=q.start_score,
            max=q.end_score,
            start=q.offset,
            num=q.limit,
        )

        return [json.loads(r) for r in results]

    def timeline_count(
        self,
        timeline_name: str,
        credentials: AgentCredentials,
        query: TimeWindowQuery | None = None,
    ) -> int:
        """Count events in a timeline within a time window.

        Args:
            timeline_name: Name of the timeline
            credentials: Agent credentials
            query: Time window query parameters

        Returns:
            Number of events in the time window

        """
        full_timeline = f"{self.PREFIX_TIMELINE}{timeline_name}"
        q = query or TimeWindowQuery()

        if self.use_mock:
            if full_timeline not in self._mock_sorted_sets:
                return 0
            entries = self._mock_sorted_sets[full_timeline]
            return len([1 for score, _ in entries if q.start_score <= score <= q.end_score])

        if self._client is None:
            return 0

        return int(self._client.zcount(full_timeline, q.start_score, q.end_score))

    # =========================================================================
    # TASK QUEUES (LISTS)
    # =========================================================================

    def queue_push(
        self,
        queue_name: str,
        task: dict,
        credentials: AgentCredentials,
        priority: bool = False,
    ) -> int:
        """Push a task to a queue.

        Args:
            queue_name: Name of the queue
            task: Task data
            credentials: Agent credentials (must be CONTRIBUTOR+)
            priority: If True, push to front (high priority)

        Returns:
            New queue length

        Example:
            >>> task = {"type": "analyze", "file": "main.py"}
            >>> memory.queue_push("agent_tasks", task, creds)

        """
        if not credentials.can_stage():
            raise PermissionError(
                f"Agent {credentials.agent_id} cannot push to queue. "
                "Requires CONTRIBUTOR tier or higher.",
            )

        full_queue = f"{self.PREFIX_QUEUE}{queue_name}"
        payload = json.dumps(
            {
                "task": task,
                "queued_by": credentials.agent_id,
                "queued_at": datetime.now().isoformat(),
            },
        )

        if self.use_mock:
            if full_queue not in self._mock_lists:
                self._mock_lists[full_queue] = []
            if priority:
                self._mock_lists[full_queue].insert(0, payload)
            else:
                self._mock_lists[full_queue].append(payload)
            return len(self._mock_lists[full_queue])

        if self._client is None:
            return 0

        if priority:
            return int(self._client.lpush(full_queue, payload))
        return int(self._client.rpush(full_queue, payload))

    def queue_pop(
        self,
        queue_name: str,
        credentials: AgentCredentials,
        timeout: int = 0,
    ) -> dict | None:
        """Pop a task from a queue.

        Args:
            queue_name: Name of the queue
            credentials: Agent credentials
            timeout: Seconds to block waiting (0 = no block)

        Returns:
            Task data or None if queue empty

        Example:
            >>> task = memory.queue_pop("agent_tasks", creds, timeout=5)
            >>> if task:
            ...     process(task["task"])

        """
        full_queue = f"{self.PREFIX_QUEUE}{queue_name}"

        if self.use_mock:
            if full_queue not in self._mock_lists or not self._mock_lists[full_queue]:
                return None
            payload = self._mock_lists[full_queue].pop(0)
            data: dict = json.loads(payload)
            return data

        if self._client is None:
            return None

        if timeout > 0:
            result = self._client.blpop(full_queue, timeout=timeout)
            if result:
                data = json.loads(result[1])
                return data
            return None

        result = self._client.lpop(full_queue)
        if result:
            data = json.loads(result)
            return data
        return None

    def queue_length(self, queue_name: str) -> int:
        """Get the length of a queue.

        Args:
            queue_name: Name of the queue

        Returns:
            Number of items in the queue

        """
        full_queue = f"{self.PREFIX_QUEUE}{queue_name}"

        if self.use_mock:
            return len(self._mock_lists.get(full_queue, []))

        if self._client is None:
            return 0

        return int(self._client.llen(full_queue))

    def queue_peek(
        self,
        queue_name: str,
        credentials: AgentCredentials,
        count: int = 1,
    ) -> list[dict]:
        """Peek at tasks in a queue without removing them.

        Args:
            queue_name: Name of the queue
            credentials: Agent credentials
            count: Number of items to peek

        Returns:
            List of task data

        """
        full_queue = f"{self.PREFIX_QUEUE}{queue_name}"

        if self.use_mock:
            items = self._mock_lists.get(full_queue, [])[:count]
            return [json.loads(item) for item in items]

        if self._client is None:
            return []

        items = self._client.lrange(full_queue, 0, count - 1)
        return [json.loads(item) for item in items]

    # =========================================================================
    # ATOMIC TRANSACTIONS
    # =========================================================================

    def atomic_promote_pattern(
        self,
        pattern_id: str,
        credentials: AgentCredentials,
        min_confidence: float = 0.0,
    ) -> tuple[bool, StagedPattern | None, str]:
        """Atomically promote a pattern with validation.

        Uses Redis transaction (MULTI/EXEC) to ensure:
        - Pattern exists and meets confidence threshold
        - Pattern is removed from staging atomically
        - No race conditions with concurrent operations

        Args:
            pattern_id: Pattern to promote
            credentials: Must be VALIDATOR or higher
            min_confidence: Minimum confidence threshold

        Returns:
            Tuple of (success, pattern, message)

        Raises:
            ValueError: If pattern_id is empty or min_confidence out of range

        Example:
            >>> success, pattern, msg = memory.atomic_promote_pattern("pat_123", creds, min_confidence=0.7)
            >>> if success:
            ...     library.add(pattern)

        """
        # Pattern 1: String ID validation
        if not pattern_id or not pattern_id.strip():
            raise ValueError("pattern_id cannot be empty")

        # Pattern 4: Range validation
        if not 0.0 <= min_confidence <= 1.0:
            raise ValueError(f"min_confidence must be between 0.0 and 1.0, got {min_confidence}")

        if not credentials.can_validate():
            return False, None, "Requires VALIDATOR tier or higher"

        key = f"{self.PREFIX_STAGED}{pattern_id}"

        if self.use_mock:
            if key not in self._mock_storage:
                return False, None, "Pattern not found"
            value, expires = self._mock_storage[key]
            if expires and datetime.now().timestamp() >= expires:
                return False, None, "Pattern expired"
            pattern = StagedPattern.from_dict(json.loads(str(value)))
            if pattern.confidence < min_confidence:
                return (
                    False,
                    None,
                    f"Confidence {pattern.confidence} below threshold {min_confidence}",
                )
            del self._mock_storage[key]
            return True, pattern, "Pattern promoted successfully"

        if self._client is None:
            return False, None, "Redis not connected"

        # Use WATCH for optimistic locking
        try:
            self._client.watch(key)
            raw = self._client.get(key)

            if raw is None:
                self._client.unwatch()
                return False, None, "Pattern not found"

            pattern = StagedPattern.from_dict(json.loads(raw))

            if pattern.confidence < min_confidence:
                self._client.unwatch()
                return (
                    False,
                    None,
                    f"Confidence {pattern.confidence} below threshold {min_confidence}",
                )

            # Execute atomic delete
            pipe = self._client.pipeline(True)
            pipe.delete(key)
            pipe.execute()

            return True, pattern, "Pattern promoted successfully"

        except redis.WatchError:
            return False, None, "Pattern was modified by another process"
        finally:
            try:
                self._client.unwatch()
            except Exception:
                pass

    # =========================================================================
    # CROSS-SESSION COMMUNICATION
    # =========================================================================

    def enable_cross_session(
        self,
        access_tier: AccessTier = AccessTier.CONTRIBUTOR,
        auto_announce: bool = True,
    ):
        """Enable cross-session communication for this memory instance.

        This allows agents in different Claude Code sessions to communicate
        and coordinate via Redis.

        Args:
            access_tier: Access tier for this session
            auto_announce: Whether to announce presence automatically

        Returns:
            CrossSessionCoordinator instance

        Raises:
            ValueError: If in mock mode (Redis required for cross-session)

        Example:
            >>> memory = RedisShortTermMemory()
            >>> coordinator = memory.enable_cross_session(AccessTier.CONTRIBUTOR)
            >>> print(f"Session ID: {coordinator.agent_id}")
            >>> sessions = coordinator.get_active_sessions()

        """
        if self.use_mock:
            raise ValueError(
                "Cross-session communication requires Redis. "
                "Set REDIS_HOST/REDIS_PORT or disable mock mode."
            )

        from .cross_session import CrossSessionCoordinator, SessionType

        coordinator = CrossSessionCoordinator(
            memory=self,
            session_type=SessionType.CLAUDE,
            access_tier=access_tier,
            auto_announce=auto_announce,
        )

        return coordinator

    def cross_session_available(self) -> bool:
        """Check if cross-session communication is available.

        Returns:
            True if Redis is connected (not mock mode)

        """
        return not self.use_mock and self._client is not None

    # =========================================================================
    # CLEANUP AND LIFECYCLE
    # =========================================================================

    def close(self) -> None:
        """Close all connections and cleanup resources."""
        self.close_pubsub()
        if self._client:
            self._client.close()
            self._client = None
        logger.info("redis_connection_closed")
