"""Empathy Framework - AI-Human Collaboration Library

A five-level maturity model for building AI systems that progress from
reactive responses to anticipatory problem prevention.

QUICK START:
    from empathy_os import EmpathyOS

    # Create an EmpathyOS instance
    empathy = EmpathyOS(user_id="developer@company.com")

    # Use Level 4 (Anticipatory) for predictions
    response = empathy.level_4_anticipatory(
        user_input="How do I optimize database queries?",
        context={"domain": "software"},
        history=[]
    )

    print(f"Response: {response['response']}")
    print(f"Predictions: {response.get('predictions', [])}")

    # Store patterns in memory
    empathy.stash("session_context", {"topic": "database optimization"})
    empathy.persist_pattern(
        content="Query optimization technique",
        pattern_type="technique"
    )

MEMORY OPERATIONS:
    from empathy_os import UnifiedMemory, Classification

    # Initialize unified memory (auto-detects environment)
    memory = UnifiedMemory(user_id="agent@company.com")

    # Short-term (Redis-backed, TTL-based)
    memory.stash("working_data", {"status": "processing"})
    data = memory.retrieve("working_data")

    # Long-term (persistent, classified)
    result = memory.persist_pattern(
        content="Optimization algorithm for X",
        pattern_type="algorithm",
        classification=Classification.INTERNAL,
    )
    pattern = memory.recall_pattern(result["pattern_id"])

KEY EXPORTS:
    - EmpathyOS: Main orchestration class
    - UnifiedMemory: Two-tier memory (short + long term)
    - MemoryConfig, Environment: Memory configuration
    - Classification, AccessTier: Security/access enums
    - Level1-5 classes: Empathy level implementations

Copyright 2025 Smart AI Memory, LLC
Licensed under Fair Source 0.9
"""

__version__ = "4.6.4"
__author__ = "Patrick Roebuck"
__email__ = "hello@deepstudy.ai"

from .agent_monitoring import AgentMetrics, AgentMonitor, TeamMetrics
from .config import EmpathyConfig, load_config
from .coordination import (
    AgentCoordinator,
    AgentTask,
    ConflictResolver,
    ResolutionResult,
    ResolutionStrategy,
    TeamPriorities,
    TeamSession,
)
from .core import EmpathyOS
from .emergence import EmergenceDetector
from .exceptions import (
    CollaborationStateError,
    ConfidenceThresholdError,
    EmpathyFrameworkError,
    EmpathyLevelError,
    FeedbackLoopError,
    LeveragePointError,
    PatternNotFoundError,
    TrustThresholdError,
    ValidationError,
)
from .feedback_loops import FeedbackLoopDetector
from .levels import Level1Reactive, Level2Guided, Level3Proactive, Level4Anticipatory, Level5Systems
from .leverage_points import LeveragePointAnalyzer
from .logging_config import LoggingConfig, get_logger

# Memory module (unified short-term + long-term + security)
from .memory import (
    AccessTier,
    AgentCredentials,  # Memory module imports
    AuditEvent,
    AuditLogger,
    Classification,
    ClassificationRules,
    ClaudeMemoryConfig,
    ClaudeMemoryLoader,
    ConflictContext,
    EncryptionManager,
    Environment,
    MemDocsStorage,
    MemoryConfig,
    MemoryPermissionError,
    PatternMetadata,
    PIIDetection,
    PIIPattern,
    PIIScrubber,
    RedisShortTermMemory,
    SecretDetection,
    SecretsDetector,
    SecretType,
    SecureMemDocsIntegration,
    SecurePattern,
    SecurityError,
    SecurityViolation,
    Severity,
    StagedPattern,
    TTLStrategy,
    UnifiedMemory,
    check_redis_connection,
    detect_secrets,
    get_railway_redis,
    get_redis_config,
    get_redis_memory,
)
from .pattern_library import Pattern, PatternLibrary, PatternMatch
from .persistence import MetricsCollector, PatternPersistence, StateManager
from .trust_building import TrustBuildingBehaviors

__all__ = [
    "AccessTier",
    "AgentCoordinator",
    "AgentCredentials",
    "AgentMetrics",
    # Monitoring (Multi-Agent)
    "AgentMonitor",
    "AgentTask",
    "AuditEvent",
    # Security - Audit
    "AuditLogger",
    "Classification",
    "ClassificationRules",
    # Claude Memory
    "ClaudeMemoryConfig",
    "ClaudeMemoryLoader",
    "CollaborationStateError",
    "ConfidenceThresholdError",
    "ConflictContext",
    # Coordination (Multi-Agent)
    "ConflictResolver",
    "EmergenceDetector",
    # Configuration
    "EmpathyConfig",
    # Exceptions
    "EmpathyFrameworkError",
    "EmpathyLevelError",
    "EmpathyOS",
    "EncryptionManager",
    "Environment",
    "FeedbackLoopDetector",
    "FeedbackLoopError",
    "Level1Reactive",
    "Level2Guided",
    "Level3Proactive",
    "Level4Anticipatory",
    "Level5Systems",
    "LeveragePointAnalyzer",
    "LeveragePointError",
    "LoggingConfig",
    "MemDocsStorage",
    "MemoryConfig",
    "MemoryPermissionError",
    "MetricsCollector",
    "PIIDetection",
    "PIIPattern",
    # Security - PII
    "PIIScrubber",
    "Pattern",
    # Pattern Library
    "PatternLibrary",
    "PatternMatch",
    "PatternMetadata",
    "PatternNotFoundError",
    # Persistence
    "PatternPersistence",
    # Redis Short-Term Memory
    "RedisShortTermMemory",
    "ResolutionResult",
    "ResolutionStrategy",
    "SecretDetection",
    "SecretType",
    # Security - Secrets
    "SecretsDetector",
    # Long-term Memory
    "SecureMemDocsIntegration",
    "SecurePattern",
    "SecurityError",
    "SecurityViolation",
    "Severity",
    "StagedPattern",
    "StateManager",
    "TTLStrategy",
    "TeamMetrics",
    "TeamPriorities",
    "TeamSession",
    # Trust
    "TrustBuildingBehaviors",
    "TrustThresholdError",
    # Unified Memory Interface
    "UnifiedMemory",
    "ValidationError",
    "check_redis_connection",
    "detect_secrets",
    # Logging
    "get_logger",
    "get_railway_redis",
    "get_redis_config",
    # Redis Configuration
    "get_redis_memory",
    "load_config",
]
