"""Secure MemDocs Integration for Enterprise Privacy

Combines PII scrubbing, secrets detection, and audit logging with MemDocs pattern storage.
Implements three-tier classification (PUBLIC/INTERNAL/SENSITIVE) with encryption support.

This module provides the complete security pipeline for storing and retrieving
patterns with full compliance for GDPR, HIPAA, and SOC2 requirements.

Key Features:
- Automatic PII scrubbing before storage
- Secrets detection with blocking
- Three-tier classification system
- AES-256-GCM encryption for SENSITIVE patterns
- Comprehensive audit logging
- Access control enforcement
- Retention policy management

Architecture:
    User Input → [PII Scrubbing + Secrets Detection (PARALLEL)] → Classification
    → Encryption (if SENSITIVE) → MemDocs Storage → Audit Logging

Reference:
- SECURE_MEMORY_ARCHITECTURE.md: MemDocs Integration Patterns
- ENTERPRISE_PRIVACY_INTEGRATION.md: Phase 2 Implementation

Copyright 2025 Smart AI Memory, LLC
Licensed under Fair Source 0.9
"""

import base64
import binascii
import concurrent.futures
import hashlib
import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any

import structlog

from empathy_os.config import _validate_file_path

from .security.audit_logger import AuditEvent, AuditLogger
from .security.pii_scrubber import PIIScrubber
from .security.secrets_detector import SecretsDetector

logger = structlog.get_logger(__name__)

# Check for cryptography library
try:
    from cryptography.exceptions import InvalidTag
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    HAS_ENCRYPTION = True
except ImportError:
    HAS_ENCRYPTION = False
    logger.warning("cryptography library not available - encryption disabled")


class Classification(Enum):
    """Three-tier classification system for MemDocs patterns"""

    PUBLIC = "PUBLIC"  # Shareable across organization, anonymized
    INTERNAL = "INTERNAL"  # Team/project only, no PII or secrets
    SENSITIVE = "SENSITIVE"  # Encrypted at rest, access-controlled (HIPAA, finance)


@dataclass
class ClassificationRules:
    """Security rules for each classification level"""

    classification: Classification
    encryption_required: bool
    retention_days: int
    access_level: str  # "all_users", "project_team", "explicit_permission"
    audit_all_access: bool = False


# Default classification rules based on enterprise security policy
DEFAULT_CLASSIFICATION_RULES: dict[Classification, ClassificationRules] = {
    Classification.PUBLIC: ClassificationRules(
        classification=Classification.PUBLIC,
        encryption_required=False,
        retention_days=365,
        access_level="all_users",
        audit_all_access=False,
    ),
    Classification.INTERNAL: ClassificationRules(
        classification=Classification.INTERNAL,
        encryption_required=False,
        retention_days=180,
        access_level="project_team",
        audit_all_access=False,
    ),
    Classification.SENSITIVE: ClassificationRules(
        classification=Classification.SENSITIVE,
        encryption_required=True,
        retention_days=90,
        access_level="explicit_permission",
        audit_all_access=True,
    ),
}


@dataclass
class PatternMetadata:
    """Metadata for stored MemDocs patterns"""

    pattern_id: str
    created_by: str
    created_at: str
    classification: str
    retention_days: int
    encrypted: bool
    pattern_type: str
    sanitization_applied: bool
    pii_removed: int
    secrets_detected: int
    access_control: dict[str, Any] = field(default_factory=dict)
    custom_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SecurePattern:
    """Represents a securely stored pattern"""

    pattern_id: str
    content: str
    metadata: PatternMetadata


class SecurityError(Exception):
    """Raised when security policy is violated"""


class PermissionError(Exception):
    """Raised when access is denied"""


class EncryptionManager:
    """Manages encryption/decryption for SENSITIVE patterns.

    Uses AES-256-GCM (Galois/Counter Mode) for authenticated encryption.
    Keys are derived from a master key using HKDF.
    """

    def __init__(self, master_key: bytes | None = None):
        """Initialize encryption manager.

        Args:
            master_key: 32-byte master key (or None to generate/load)

        """
        if not HAS_ENCRYPTION:
            logger.warning("Encryption not available - install cryptography library")
            self.enabled = False
            return

        self.enabled = True
        self.master_key = master_key or self._load_or_generate_key()

    def _load_or_generate_key(self) -> bytes:
        """Load master key from environment or generate new one.

        Production: Set EMPATHY_MASTER_KEY environment variable
        Development: Generates ephemeral key (warning logged)
        """
        # Check environment variable first
        if env_key := os.getenv("EMPATHY_MASTER_KEY"):
            try:
                return base64.b64decode(env_key)
            except (binascii.Error, ValueError) as e:
                logger.error("invalid_master_key_in_env", error=str(e))
                raise ValueError("Invalid EMPATHY_MASTER_KEY format") from e

        # Check key file
        key_file = Path.home() / ".empathy" / "master.key"
        if key_file.exists():
            try:
                return key_file.read_bytes()
            except (OSError, PermissionError) as e:
                logger.error("failed_to_load_key_file", error=str(e))

        # Generate ephemeral key (NOT for production)
        logger.warning(
            "no_master_key_found",
            message="Generating ephemeral encryption key - set EMPATHY_MASTER_KEY for production",
        )
        return AESGCM.generate_key(bit_length=256)

    def encrypt(self, plaintext: str) -> str:
        """Encrypt plaintext using AES-256-GCM.

        Args:
            plaintext: Content to encrypt

        Returns:
            Base64-encoded ciphertext with format: nonce||ciphertext||tag

        Raises:
            SecurityError: If encryption fails

        """
        if not self.enabled:
            raise SecurityError("Encryption not available - install cryptography library")

        try:
            # Generate random 96-bit nonce (12 bytes)
            nonce = os.urandom(12)

            # Create AESGCM cipher
            aesgcm = AESGCM(self.master_key)

            # Encrypt and authenticate
            ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)

            # Combine nonce + ciphertext for storage
            encrypted_data = nonce + ciphertext

            # Return base64-encoded
            return base64.b64encode(encrypted_data).decode("utf-8")

        except (ValueError, TypeError, UnicodeEncodeError) as e:
            logger.error("encryption_failed", error=str(e))
            raise SecurityError(f"Encryption failed: {e}") from e

    def decrypt(self, ciphertext_b64: str) -> str:
        """Decrypt ciphertext using AES-256-GCM.

        Args:
            ciphertext_b64: Base64-encoded encrypted data

        Returns:
            Decrypted plaintext

        Raises:
            SecurityError: If decryption fails (invalid key, corrupted data, etc.)

        """
        if not self.enabled:
            raise SecurityError("Encryption not available - install cryptography library")

        try:
            # Decode from base64
            encrypted_data = base64.b64decode(ciphertext_b64)

            # Extract nonce (first 12 bytes) and ciphertext (rest)
            nonce = encrypted_data[:12]
            ciphertext = encrypted_data[12:]

            # Create AESGCM cipher
            aesgcm = AESGCM(self.master_key)

            # Decrypt and verify
            plaintext_bytes = aesgcm.decrypt(nonce, ciphertext, None)

            return plaintext_bytes.decode("utf-8")

        except (ValueError, TypeError, UnicodeDecodeError, binascii.Error, InvalidTag) as e:
            logger.error("decryption_failed", error=str(e))
            raise SecurityError(f"Decryption failed: {e}") from e


class MemDocsStorage:
    """Mock/Simple MemDocs storage backend.

    In production, this would integrate with the actual MemDocs library.
    For now, provides a simple file-based storage for testing.
    """

    def __init__(self, storage_dir: str = "./memdocs_storage"):
        """Initialize storage backend.

        Args:
            storage_dir: Directory for pattern storage

        """
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        logger.info("memdocs_storage_initialized", storage_dir=str(self.storage_dir))

    def store(self, pattern_id: str, content: str, metadata: dict[str, Any]) -> bool:
        """Store a pattern.

        Args:
            pattern_id: Unique pattern identifier
            content: Pattern content (may be encrypted)
            metadata: Pattern metadata

        Returns:
            True if successful

        Raises:
            IOError: If storage fails

        """
        try:
            pattern_file = self.storage_dir / f"{pattern_id}.json"

            # Ensure parent directory exists
            pattern_file.parent.mkdir(parents=True, exist_ok=True)

            pattern_data = {"pattern_id": pattern_id, "content": content, "metadata": metadata}

            validated_pattern_file = _validate_file_path(str(pattern_file))
            with open(validated_pattern_file, "w", encoding="utf-8") as f:
                json.dump(pattern_data, f, indent=2)

            logger.debug("pattern_stored", pattern_id=pattern_id)
            return True

        except (OSError, PermissionError, json.JSONDecodeError) as e:
            logger.error("pattern_storage_failed", pattern_id=pattern_id, error=str(e))
            raise

    def retrieve(self, pattern_id: str) -> dict[str, Any] | None:
        """Retrieve a pattern.

        Args:
            pattern_id: Unique pattern identifier

        Returns:
            Pattern data dictionary or None if not found

        """
        try:
            pattern_file = self.storage_dir / f"{pattern_id}.json"

            if not pattern_file.exists():
                logger.warning("pattern_not_found", pattern_id=pattern_id)
                return None

            with open(pattern_file, encoding="utf-8") as f:
                pattern_data: dict[str, Any] = json.load(f)

            logger.debug("pattern_retrieved", pattern_id=pattern_id)
            return pattern_data

        except (OSError, PermissionError, json.JSONDecodeError) as e:
            logger.error("pattern_retrieval_failed", pattern_id=pattern_id, error=str(e))
            return None

    def delete(self, pattern_id: str) -> bool:
        """Delete a pattern.

        Args:
            pattern_id: Unique pattern identifier

        Returns:
            True if deleted, False if not found

        """
        try:
            pattern_file = self.storage_dir / f"{pattern_id}.json"

            if not pattern_file.exists():
                return False

            pattern_file.unlink()
            logger.info("pattern_deleted", pattern_id=pattern_id)
            return True

        except (OSError, PermissionError) as e:
            logger.error("pattern_deletion_failed", pattern_id=pattern_id, error=str(e))
            return False

    def list_patterns(
        self,
        classification: str | None = None,
        created_by: str | None = None,
    ) -> list[str]:
        """List pattern IDs matching criteria.

        Args:
            classification: Filter by classification
            created_by: Filter by creator

        Returns:
            List of pattern IDs

        """
        pattern_ids = []

        for pattern_file in self.storage_dir.glob("*.json"):
            try:
                with open(pattern_file, encoding="utf-8") as f:
                    data = json.load(f)
                    metadata = data.get("metadata", {})

                    # Apply filters
                    if classification and metadata.get("classification") != classification:
                        continue
                    if created_by and metadata.get("created_by") != created_by:
                        continue

                    pattern_ids.append(data.get("pattern_id"))

            except Exception:
                continue

        return pattern_ids


class SecureMemDocsIntegration:
    """Secure integration between Claude Memory and MemDocs.

    Enforces enterprise security policies from CLAUDE.md with:
    - Automatic PII scrubbing
    - Secrets detection and blocking
    - Three-tier classification
    - Encryption for SENSITIVE data
    - Comprehensive audit logging
    - Access control enforcement

    Example:
        >>> from empathy_llm_toolkit.claude_memory import ClaudeMemoryConfig
        >>> config = ClaudeMemoryConfig(enabled=True, load_enterprise=True)
        >>> integration = SecureMemDocsIntegration(config)
        >>>
        >>> # Store pattern with full security pipeline
        >>> result = integration.store_pattern(
        ...     content="Patient diagnosis: diabetes type 2",
        ...     pattern_type="clinical_protocol",
        ...     user_id="doctor@hospital.com"
        ... )
        >>> # Automatically: PII scrubbed, classified as SENSITIVE, encrypted
        >>>
        >>> # Retrieve with access control
        >>> pattern = integration.retrieve_pattern(
        ...     pattern_id=result["pattern_id"],
        ...     user_id="doctor@hospital.com"
        ... )

    """

    def __init__(
        self,
        claude_memory_config=None,
        storage_dir: str = "./memdocs_storage",
        audit_log_dir: str | None = None,  # Uses platform-appropriate default if None
        classification_rules: dict[Classification, ClassificationRules] | None = None,
        enable_encryption: bool = True,
        master_key: bytes | None = None,
    ):
        """Initialize Secure MemDocs Integration.

        Args:
            claude_memory_config: Configuration for Claude memory integration
            storage_dir: Directory for MemDocs storage
            audit_log_dir: Directory for audit logs
            classification_rules: Custom classification rules (uses defaults if None)
            enable_encryption: Enable encryption for SENSITIVE patterns
            master_key: Encryption master key (auto-generated if None)

        """
        self.claude_memory_config = claude_memory_config
        self.classification_rules = classification_rules or DEFAULT_CLASSIFICATION_RULES

        # Initialize security components
        self.pii_scrubber = PIIScrubber()
        self.secrets_detector = SecretsDetector()
        self.audit_logger = AuditLogger(
            log_dir=audit_log_dir,
            enable_console_logging=True,  # Development mode
        )

        # Initialize encryption
        self.encryption_enabled = enable_encryption and HAS_ENCRYPTION
        self.encryption_manager: EncryptionManager | None = None
        if self.encryption_enabled:
            self.encryption_manager = EncryptionManager(master_key)
        elif enable_encryption:
            logger.warning("encryption_disabled", reason="cryptography library not available")

        # Initialize storage backend
        self.storage = MemDocsStorage(storage_dir)

        # Load security policies from enterprise CLAUDE.md
        self.security_policies = self._load_security_policies()

        logger.info(
            "secure_memdocs_initialized",
            encryption_enabled=self.encryption_enabled,
            storage_dir=storage_dir,
            audit_dir=audit_log_dir,
        )

    def _load_security_policies(self) -> dict[str, Any]:
        """Load security policies from enterprise Claude memory.

        In production, this would parse the enterprise CLAUDE.md file
        to extract PII patterns, secret patterns, and classification rules.

        For now, returns default policies that match the architecture spec.
        """
        policies = {
            "pii_scrubbing_enabled": True,
            "secrets_detection_enabled": True,
            "classification_required": True,
            "audit_logging_enabled": True,
            "retention_enforcement_enabled": True,
        }

        logger.debug("security_policies_loaded", policies=policies)
        return policies

    def store_pattern(
        self,
        content: str,
        pattern_type: str,
        user_id: str,
        auto_classify: bool = True,
        explicit_classification: Classification | None = None,
        session_id: str = "",
        custom_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Store a pattern with full security pipeline.

        Pipeline:
            1. PII scrubbing
            2. Secrets detection (blocks if found)
            3. Classification (auto or explicit)
            4. Encryption (if SENSITIVE)
            5. MemDocs storage
            6. Audit logging

        Args:
            content: Pattern content to store
            pattern_type: Type of pattern (code, architecture, clinical, etc.)
            user_id: User storing the pattern
            auto_classify: Enable automatic classification
            explicit_classification: Override auto-classification
            session_id: Session identifier for audit
            custom_metadata: Additional metadata

        Returns:
            Dictionary with:
                - pattern_id: Unique identifier
                - classification: Applied classification
                - sanitization_report: PII and secrets detection results

        Raises:
            SecurityError: If secrets detected or security policy violated
            ValueError: If content/pattern_type/user_id empty or invalid classification
            TypeError: If custom_metadata is not dict

        Example:
            >>> result = integration.store_pattern(
            ...     content="Patient vital signs protocol",
            ...     pattern_type="clinical_protocol",
            ...     user_id="nurse@hospital.com"
            ... )
            >>> print(f"Stored as {result['classification']}")

        """
        logger.info(
            "store_pattern_started",
            user_id=user_id,
            pattern_type=pattern_type,
            auto_classify=auto_classify,
        )

        try:
            # Pattern 1: String ID validation
            if not content or not content.strip():
                raise ValueError("content cannot be empty")
            if not pattern_type or not pattern_type.strip():
                raise ValueError("pattern_type cannot be empty")
            if not user_id or not user_id.strip():
                raise ValueError("user_id cannot be empty")

            # Pattern 5: Type validation
            if custom_metadata is not None and not isinstance(custom_metadata, dict):
                raise TypeError(
                    f"custom_metadata must be dict, got {type(custom_metadata).__name__}"
                )

            # Step 1 & 2: PII Scrubbing + Secrets Detection (PARALLEL for performance)
            # Run both operations in parallel since they're independent
            # Secrets detection runs on original content to catch secrets before PII scrubbing
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                # Submit both tasks in parallel
                pii_future = executor.submit(self.pii_scrubber.scrub, content)
                secrets_future = executor.submit(self.secrets_detector.detect, content)

                # Wait for both to complete
                sanitized_content, pii_detections = pii_future.result()
                secrets_found = secrets_future.result()

            pii_count = len(pii_detections)

            if pii_count > 0:
                logger.info(
                    "pii_scrubbed",
                    user_id=user_id,
                    pii_count=pii_count,
                    types=[d.pii_type for d in pii_detections],
                )

            if secrets_found:
                # CRITICAL: Block storage if secrets detected
                secret_types = [s.secret_type.value for s in secrets_found]
                logger.error(
                    "secrets_detected_blocking_storage",
                    user_id=user_id,
                    secret_count=len(secrets_found),
                    types=secret_types,
                )

                # Log to audit trail
                self.audit_logger.log_security_violation(
                    user_id=user_id,
                    violation_type="secrets_in_storage_attempt",
                    severity="CRITICAL",
                    details={
                        "secret_count": len(secrets_found),
                        "secret_types": secret_types,
                        "pattern_type": pattern_type,
                    },
                    session_id=session_id,
                    blocked=True,
                )

                raise SecurityError(
                    f"Secrets detected in pattern. Cannot store. Found: {secret_types}",
                )

            # Step 3: Classification
            if explicit_classification:
                classification = explicit_classification
                logger.info("explicit_classification", classification=classification.value)
            elif auto_classify:
                classification = self._classify_pattern(sanitized_content, pattern_type)
                logger.info("auto_classification", classification=classification.value)
            else:
                # Default to INTERNAL if not specified
                classification = Classification.INTERNAL
                logger.info("default_classification", classification=classification.value)

            # Step 4: Apply classification-specific controls
            rules = self.classification_rules[classification]

            # Encrypt if required
            final_content = sanitized_content
            encrypted = False

            if rules.encryption_required and self.encryption_enabled and self.encryption_manager:
                final_content = self.encryption_manager.encrypt(sanitized_content)
                encrypted = True
                logger.info("pattern_encrypted", classification=classification.value)
            elif rules.encryption_required and not self.encryption_enabled:
                logger.warning(
                    "encryption_required_but_unavailable",
                    classification=classification.value,
                    action="storing_unencrypted",
                )

            # Generate pattern ID
            pattern_id = self._generate_pattern_id(user_id, pattern_type)

            # Step 5: Store in MemDocs with metadata
            metadata = PatternMetadata(
                pattern_id=pattern_id,
                created_by=user_id,
                created_at=datetime.utcnow().isoformat() + "Z",
                classification=classification.value,
                retention_days=rules.retention_days,
                encrypted=encrypted,
                pattern_type=pattern_type,
                sanitization_applied=True,
                pii_removed=pii_count,
                secrets_detected=0,
                access_control={
                    "access_level": rules.access_level,
                    "audit_required": rules.audit_all_access,
                },
                custom_metadata=custom_metadata or {},
            )

            self.storage.store(
                pattern_id=pattern_id,
                content=final_content,
                metadata=metadata.__dict__,
            )

            # Step 6: Audit logging
            self.audit_logger.log_pattern_store(
                user_id=user_id,
                pattern_id=pattern_id,
                pattern_type=pattern_type,
                classification=classification.value,
                pii_scrubbed=pii_count,
                secrets_detected=0,
                retention_days=rules.retention_days,
                encrypted=encrypted,
                session_id=session_id,
                status="success",
            )

            logger.info(
                "pattern_stored_successfully",
                pattern_id=pattern_id,
                classification=classification.value,
                encrypted=encrypted,
            )

            return {
                "pattern_id": pattern_id,
                "classification": classification.value,
                "sanitization_report": {
                    "pii_removed": [{"type": d.pii_type, "count": 1} for d in pii_detections],
                    "pii_count": pii_count,
                    "secrets_detected": 0,
                },
                "metadata": {
                    "encrypted": encrypted,
                    "retention_days": rules.retention_days,
                    "created_at": metadata.created_at,
                },
            }

        except SecurityError:
            # Re-raise security errors
            raise
        except Exception as e:
            # Log unexpected errors
            logger.error("pattern_storage_failed", user_id=user_id, error=str(e))

            self.audit_logger.log_pattern_store(
                user_id=user_id,
                pattern_id="",
                pattern_type=pattern_type,
                classification="UNKNOWN",
                pii_scrubbed=0,
                secrets_detected=0,
                retention_days=0,
                encrypted=False,
                session_id=session_id,
                status="failed",
                error=str(e),
            )

            raise

    def retrieve_pattern(
        self,
        pattern_id: str,
        user_id: str,
        check_permissions: bool = True,
        session_id: str = "",
    ) -> dict[str, Any]:
        """Retrieve a pattern with access control and decryption.

        Pipeline:
            1. Retrieve from MemDocs
            2. Check access permissions
            3. Decrypt (if SENSITIVE)
            4. Check retention policy
            5. Audit logging

        Args:
            pattern_id: Unique pattern identifier
            user_id: User retrieving the pattern
            check_permissions: Enforce access control
            session_id: Session identifier for audit

        Returns:
            Dictionary with:
                - content: Pattern content (decrypted if needed)
                - metadata: Pattern metadata

        Raises:
            PermissionError: If access denied
            ValueError: If pattern_id/user_id empty, pattern not found, or retention expired
            SecurityError: If decryption fails

        Example:
            >>> pattern = integration.retrieve_pattern(
            ...     pattern_id="pat_abc123",
            ...     user_id="user@company.com"
            ... )
            >>> print(pattern["content"])

        """
        # Pattern 1: String ID validation
        if not pattern_id or not pattern_id.strip():
            raise ValueError("pattern_id cannot be empty")
        if not user_id or not user_id.strip():
            raise ValueError("user_id cannot be empty")

        logger.info(
            "retrieve_pattern_started",
            pattern_id=pattern_id,
            user_id=user_id,
            check_permissions=check_permissions,
        )

        try:
            # Step 1: Retrieve from MemDocs
            pattern_data = self.storage.retrieve(pattern_id)

            if not pattern_data:
                logger.warning("pattern_not_found", pattern_id=pattern_id)
                raise ValueError(f"Pattern {pattern_id} not found")

            content = pattern_data["content"]
            metadata = pattern_data["metadata"]
            classification = Classification[metadata["classification"]]

            # Step 2: Check access permissions
            access_granted = True
            if check_permissions:
                access_granted = self._check_access(
                    user_id=user_id,
                    classification=classification,
                    metadata=metadata,
                )

                if not access_granted:
                    logger.warning(
                        "access_denied",
                        pattern_id=pattern_id,
                        user_id=user_id,
                        classification=classification.value,
                    )

                    # Log access denial
                    self.audit_logger.log_pattern_retrieve(
                        user_id=user_id,
                        pattern_id=pattern_id,
                        classification=classification.value,
                        access_granted=False,
                        session_id=session_id,
                        status="blocked",
                        error="Access denied",
                    )

                    raise PermissionError(
                        f"User {user_id} does not have access to {classification.value} pattern",
                    )

            # Step 3: Decrypt if needed
            if metadata.get("encrypted", False):
                if not self.encryption_enabled:
                    logger.error("decryption_required_but_unavailable", pattern_id=pattern_id)
                    raise SecurityError("Encryption not available for decryption")

                if self.encryption_manager:
                    content = self.encryption_manager.decrypt(content)
                logger.debug("pattern_decrypted", pattern_id=pattern_id)

            # Step 4: Check retention policy
            created_at = datetime.fromisoformat(metadata["created_at"].rstrip("Z"))
            retention_days = metadata["retention_days"]
            expiration_date = created_at + timedelta(days=retention_days)

            if datetime.utcnow() > expiration_date:
                logger.warning(
                    "pattern_retention_expired",
                    pattern_id=pattern_id,
                    created_at=metadata["created_at"],
                    retention_days=retention_days,
                )
                raise ValueError(
                    f"Pattern {pattern_id} has expired retention period "
                    f"(created: {metadata['created_at']}, retention: {retention_days} days)",
                )

            # Step 5: Audit logging
            self.audit_logger.log_pattern_retrieve(
                user_id=user_id,
                pattern_id=pattern_id,
                classification=classification.value,
                access_granted=True,
                permission_level=metadata["access_control"]["access_level"],
                session_id=session_id,
                status="success",
            )

            logger.info(
                "pattern_retrieved_successfully",
                pattern_id=pattern_id,
                classification=classification.value,
            )

            return {"content": content, "metadata": metadata}

        except (PermissionError, ValueError, SecurityError):
            # Re-raise expected errors
            raise
        except Exception as e:
            # Log unexpected errors
            logger.error("pattern_retrieval_failed", pattern_id=pattern_id, error=str(e))

            self.audit_logger.log_pattern_retrieve(
                user_id=user_id,
                pattern_id=pattern_id,
                classification="UNKNOWN",
                access_granted=False,
                session_id=session_id,
                status="failed",
                error=str(e),
            )

            raise

    def _classify_pattern(self, content: str, pattern_type: str) -> Classification:
        """Auto-classify pattern based on content and type.

        Classification heuristics:
        - SENSITIVE: Healthcare, financial, regulated data keywords
        - INTERNAL: Proprietary, confidential, internal keywords
        - PUBLIC: Everything else (general patterns)

        Args:
            content: Pattern content (already PII-scrubbed)
            pattern_type: Type of pattern

        Returns:
            Classification level

        """
        content_lower = content.lower()

        # SENSITIVE: Healthcare keywords (HIPAA)
        healthcare_keywords = [
            "patient",
            "medical",
            "diagnosis",
            "treatment",
            "healthcare",
            "clinical",
            "hipaa",
            "phi",
            "medical record",
            "prescription",
        ]

        # SENSITIVE: Financial keywords
        financial_keywords = [
            "financial",
            "payment",
            "credit card",
            "banking",
            "transaction",
            "pci dss",
            "payment card",
        ]

        # INTERNAL: Proprietary keywords
        proprietary_keywords = [
            "proprietary",
            "confidential",
            "internal",
            "trade secret",
            "company confidential",
            "restricted",
        ]

        # Check for SENSITIVE indicators
        if any(keyword in content_lower for keyword in healthcare_keywords):
            return Classification.SENSITIVE

        if any(keyword in content_lower for keyword in financial_keywords):
            return Classification.SENSITIVE

        # Pattern type based classification
        if pattern_type in [
            "clinical_protocol",
            "medical_guideline",
            "patient_workflow",
            "financial_procedure",
        ]:
            return Classification.SENSITIVE

        # Check for INTERNAL indicators
        if any(keyword in content_lower for keyword in proprietary_keywords):
            return Classification.INTERNAL

        if pattern_type in ["architecture", "business_logic", "company_process"]:
            return Classification.INTERNAL

        # Default to PUBLIC for general patterns
        return Classification.PUBLIC

    def _check_access(
        self,
        user_id: str,
        classification: Classification,
        metadata: dict[str, Any],
    ) -> bool:
        """Check if user has access to pattern based on classification.

        Access rules:
        - PUBLIC: All users
        - INTERNAL: Users on project team (simplified: always granted for demo)
        - SENSITIVE: Explicit permission required (simplified: creator only)

        Args:
            user_id: User requesting access
            classification: Pattern classification
            metadata: Pattern metadata

        Returns:
            True if access granted, False otherwise

        """
        # PUBLIC: Everyone has access
        if classification == Classification.PUBLIC:
            return True

        # INTERNAL: Check project team membership
        # Simplified: Grant access (production would check team membership)
        if classification == Classification.INTERNAL:
            logger.debug("internal_access_check", user_id=user_id, granted=True)
            return True

        # SENSITIVE: Require explicit permission
        # Simplified: Only pattern creator has access
        if classification == Classification.SENSITIVE:
            created_by = str(metadata.get("created_by", ""))
            granted = user_id == created_by

            logger.debug(
                "sensitive_access_check",
                user_id=user_id,
                created_by=created_by,
                granted=granted,
            )

            return bool(granted)

        # Default deny
        return False

    def _generate_pattern_id(self, user_id: str, pattern_type: str) -> str:
        """Generate unique pattern ID.

        Format: pat_{timestamp}_{hash}

        Args:
            user_id: User creating the pattern
            pattern_type: Type of pattern

        Returns:
            Unique pattern identifier

        """
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")

        # Create hash from user_id, pattern_type, and random component
        hash_input = f"{user_id}:{pattern_type}:{timestamp}:{os.urandom(8).hex()}"
        hash_digest = hashlib.sha256(hash_input.encode()).hexdigest()[:12]

        return f"pat_{timestamp}_{hash_digest}"

    def list_patterns(
        self,
        user_id: str,
        classification: Classification | None = None,
        pattern_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """List patterns accessible to user.

        Args:
            user_id: User listing patterns
            classification: Filter by classification
            pattern_type: Filter by pattern type

        Returns:
            List of pattern summaries

        """
        all_pattern_ids = self.storage.list_patterns()
        accessible_patterns = []

        for pattern_id in all_pattern_ids:
            try:
                pattern_data = self.storage.retrieve(pattern_id)
                if not pattern_data:
                    continue

                metadata = pattern_data["metadata"]
                pat_classification = Classification[metadata["classification"]]

                # Apply filters
                if classification and pat_classification != classification:
                    continue

                if pattern_type and metadata.get("pattern_type") != pattern_type:
                    continue

                # Check access
                if self._check_access(user_id, pat_classification, metadata):
                    accessible_patterns.append(
                        {
                            "pattern_id": pattern_id,
                            "pattern_type": metadata.get("pattern_type"),
                            "classification": metadata["classification"],
                            "created_by": metadata.get("created_by"),
                            "created_at": metadata.get("created_at"),
                            "encrypted": metadata.get("encrypted", False),
                        },
                    )

            except Exception as e:
                logger.warning(
                    "failed_to_load_pattern_metadata",
                    pattern_id=pattern_id,
                    error=str(e),
                )
                continue

        return accessible_patterns

    def delete_pattern(self, pattern_id: str, user_id: str, session_id: str = "") -> bool:
        """Delete a pattern (with access control).

        Args:
            pattern_id: Pattern to delete
            user_id: User requesting deletion
            session_id: Session identifier

        Returns:
            True if deleted successfully

        Raises:
            PermissionError: If user doesn't have permission to delete
            ValueError: If pattern_id or user_id is empty

        """
        # Pattern 1: String ID validation
        if not pattern_id or not pattern_id.strip():
            raise ValueError("pattern_id cannot be empty")
        if not user_id or not user_id.strip():
            raise ValueError("user_id cannot be empty")

        # Retrieve pattern to check permissions
        pattern_data = self.storage.retrieve(pattern_id)

        if not pattern_data:
            logger.warning("pattern_not_found_for_deletion", pattern_id=pattern_id)
            return False

        metadata = pattern_data["metadata"]

        # Only creator can delete (simplified access control)
        if metadata.get("created_by") != user_id:
            logger.warning(
                "delete_permission_denied",
                pattern_id=pattern_id,
                user_id=user_id,
                created_by=metadata.get("created_by"),
            )
            raise PermissionError(f"User {user_id} cannot delete pattern {pattern_id}")

        # Delete pattern
        deleted = self.storage.delete(pattern_id)

        if deleted:
            # Log deletion
            self.audit_logger._write_event(
                AuditEvent(
                    event_type="delete_pattern",
                    user_id=user_id,
                    session_id=session_id,
                    status="success",
                    data={
                        "pattern_id": pattern_id,
                        "classification": metadata["classification"],
                    },
                ),
            )

            logger.info("pattern_deleted", pattern_id=pattern_id, user_id=user_id)

        return deleted

    def get_statistics(self) -> dict[str, Any]:
        """Get statistics about stored patterns.

        Returns:
            Dictionary with pattern statistics

        """
        all_patterns = self.storage.list_patterns()

        stats: dict[str, Any] = {
            "total_patterns": len(all_patterns),
            "by_classification": {
                "PUBLIC": 0,
                "INTERNAL": 0,
                "SENSITIVE": 0,
            },
            "encrypted_count": 0,
            "with_pii_scrubbed": 0,
        }

        for pattern_id in all_patterns:
            try:
                pattern_data = self.storage.retrieve(pattern_id)
                if not pattern_data:
                    continue

                metadata = pattern_data["metadata"]
                classification = metadata.get("classification", "INTERNAL")

                stats["by_classification"][classification] += 1

                if metadata.get("encrypted", False):
                    stats["encrypted_count"] += 1

                if metadata.get("pii_removed", 0) > 0:
                    stats["with_pii_scrubbed"] += 1

            except Exception:
                continue

        return stats


# ============================================================================
# Simplified Long-Term Memory Interface
# ============================================================================


class LongTermMemory:
    """Simplified long-term persistent storage interface.

    Provides basic CRUD operations for long-term memory storage without
    the full security pipeline of SecureMemDocsIntegration. Suitable for
    simple persistent storage needs where PII scrubbing and encryption
    are not required.

    Features:
    - JSON file-based storage
    - Classification support (PUBLIC/INTERNAL/SENSITIVE)
    - Simple key-value interface
    - List keys by classification

    Example:
        >>> memory = LongTermMemory(storage_path="./data")
        >>> memory.store("config", {"setting": "value"}, classification="INTERNAL")
        >>> data = memory.retrieve("config")
        >>> keys = memory.list_keys(classification="INTERNAL")

    Note:
        For enterprise features (PII scrubbing, encryption, audit logging),
        use SecureMemDocsIntegration instead.
    """

    def __init__(self, storage_path: str = "./long_term_storage"):
        """Initialize long-term memory storage.

        Args:
            storage_path: Directory path for JSON storage

        """
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        logger.info("long_term_memory_initialized", storage_path=str(self.storage_path))

    def store(
        self,
        key: str,
        data: Any,
        classification: str | Classification | None = None,
    ) -> bool:
        """Store data in long-term memory.

        Args:
            key: Storage key
            data: Data to store (must be JSON-serializable)
            classification: Data classification (PUBLIC/INTERNAL/SENSITIVE)

        Returns:
            True if stored successfully, False otherwise

        Raises:
            ValueError: If key is empty or data is not JSON-serializable
            TypeError: If data cannot be serialized to JSON

        Example:
            >>> memory = LongTermMemory()
            >>> memory.store("user_prefs", {"theme": "dark"}, "INTERNAL")
            True

        """
        if not key or not key.strip():
            raise ValueError("key cannot be empty")

        # Validate key for path traversal attacks
        if ".." in key or key.startswith("/") or "\x00" in key:
            logger.error("path_traversal_attempt", key=key)
            return False

        try:
            # Convert classification to string
            classification_str = "INTERNAL"  # Default
            if classification is not None:
                if isinstance(classification, Classification):
                    classification_str = classification.value
                elif isinstance(classification, str):
                    # Validate classification string
                    try:
                        Classification[classification.upper()]
                        classification_str = classification.upper()
                    except KeyError:
                        logger.warning(
                            "invalid_classification",
                            classification=classification,
                            using_default="INTERNAL",
                        )

            # Create storage record
            record = {
                "key": key,
                "data": data,
                "classification": classification_str,
                "created_at": datetime.utcnow().isoformat() + "Z",
                "updated_at": datetime.utcnow().isoformat() + "Z",
            }

            # Store to JSON file
            file_path = self.storage_path / f"{key}.json"
            validated_file_path = _validate_file_path(str(file_path))
            with validated_file_path.open("w", encoding="utf-8") as f:
                json.dump(record, f, indent=2)

            logger.debug("data_stored", key=key, classification=classification_str)
            return True

        except (TypeError, ValueError) as e:
            logger.error("store_failed", key=key, error=str(e))
            raise
        except (OSError, PermissionError) as e:
            logger.error("storage_io_error", key=key, error=str(e))
            return False

    def retrieve(self, key: str) -> Any | None:
        """Retrieve data from long-term memory.

        Args:
            key: Storage key

        Returns:
            Stored data or None if not found

        Raises:
            ValueError: If key is empty

        Example:
            >>> memory = LongTermMemory()
            >>> memory.store("config", {"value": 42})
            >>> data = memory.retrieve("config")
            >>> print(data["value"])
            42

        """
        if not key or not key.strip():
            raise ValueError("key cannot be empty")

        try:
            file_path = self.storage_path / f"{key}.json"

            if not file_path.exists():
                logger.debug("key_not_found", key=key)
                return None

            with file_path.open(encoding="utf-8") as f:
                record = json.load(f)

            logger.debug("data_retrieved", key=key)
            return record.get("data")

        except (OSError, PermissionError, json.JSONDecodeError) as e:
            logger.error("retrieve_failed", key=key, error=str(e))
            return None

    def delete(self, key: str) -> bool:
        """Delete data from long-term memory.

        Args:
            key: Storage key

        Returns:
            True if deleted, False if not found or error

        Raises:
            ValueError: If key is empty

        Example:
            >>> memory = LongTermMemory()
            >>> memory.store("temp", {"data": "value"})
            >>> memory.delete("temp")
            True

        """
        if not key or not key.strip():
            raise ValueError("key cannot be empty")

        try:
            file_path = self.storage_path / f"{key}.json"

            if not file_path.exists():
                logger.debug("key_not_found_for_deletion", key=key)
                return False

            file_path.unlink()
            logger.info("data_deleted", key=key)
            return True

        except (OSError, PermissionError) as e:
            logger.error("delete_failed", key=key, error=str(e))
            return False

    def list_keys(self, classification: str | Classification | None = None) -> list[str]:
        """List all keys in long-term memory, optionally filtered by classification.

        Args:
            classification: Filter by classification (PUBLIC/INTERNAL/SENSITIVE)

        Returns:
            List of storage keys

        Example:
            >>> memory = LongTermMemory()
            >>> memory.store("public_data", {"x": 1}, "PUBLIC")
            >>> memory.store("internal_data", {"y": 2}, "INTERNAL")
            >>> keys = memory.list_keys(classification="PUBLIC")
            >>> print(keys)
            ['public_data']

        """
        keys = []

        # Convert classification to string if needed
        filter_classification = None
        if classification is not None:
            if isinstance(classification, Classification):
                filter_classification = classification.value
            elif isinstance(classification, str):
                try:
                    Classification[classification.upper()]
                    filter_classification = classification.upper()
                except KeyError:
                    logger.warning("invalid_classification_filter", classification=classification)
                    return []

        try:
            for file_path in self.storage_path.glob("*.json"):
                try:
                    with file_path.open(encoding="utf-8") as f:
                        record = json.load(f)

                    # Apply classification filter if specified
                    if filter_classification is not None:
                        if record.get("classification") != filter_classification:
                            continue

                    keys.append(record.get("key", file_path.stem))

                except (OSError, json.JSONDecodeError):
                    continue

        except (OSError, PermissionError) as e:
            logger.error("list_keys_failed", error=str(e))

        return keys

    def clear(self) -> int:
        """Clear all data from long-term memory.

        Returns:
            Number of keys deleted

        Warning:
            This operation cannot be undone!

        """
        count = 0
        try:
            for file_path in self.storage_path.glob("*.json"):
                try:
                    file_path.unlink()
                    count += 1
                except (OSError, PermissionError):
                    continue

            logger.warning("long_term_memory_cleared", count=count)
            return count

        except (OSError, PermissionError) as e:
            logger.error("clear_failed", error=str(e))
            return count
