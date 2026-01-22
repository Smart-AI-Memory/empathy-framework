"""EmpathyOS - Core Implementation

The main entry point for the Empathy Framework, providing access to all
5 empathy levels and system thinking integrations.

Copyright 2025 Smart AI Memory, LLC
Licensed under Fair Source 0.9
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any

from .emergence import EmergenceDetector
from .exceptions import ValidationError
from .feedback_loops import FeedbackLoopDetector
from .leverage_points import LeveragePoint, LeveragePointAnalyzer
from .memory import Classification, UnifiedMemory
from .redis_memory import AccessTier, AgentCredentials, RedisShortTermMemory, StagedPattern

if TYPE_CHECKING:
    from .pattern_library import PatternLibrary


@dataclass
class CollaborationState:
    """Stock & Flow model of AI-human collaboration

    Tracks:
    - Trust level (stock that accumulates/erodes)
    - Shared context (accumulated understanding)
    - Success/failure rates (quality metrics)
    - Flow rates (how fast trust builds/erodes)
    """

    # Stocks (accumulate over time)
    trust_level: float = 0.5  # 0.0 to 1.0, start neutral
    shared_context: dict = field(default_factory=dict)
    successful_interventions: int = 0
    failed_interventions: int = 0

    # Flow rates (change stocks per interaction)
    trust_building_rate: float = 0.05  # Per successful interaction
    trust_erosion_rate: float = 0.10  # Per failed interaction (erosion faster)
    context_accumulation_rate: float = 0.1

    # Metadata
    session_start: datetime = field(default_factory=datetime.now)
    total_interactions: int = 0
    trust_trajectory: list[float] = field(default_factory=list)  # Historical trust levels

    def update_trust(self, outcome: str):
        """Update trust stock based on interaction outcome"""
        if outcome == "success":
            self.trust_level += self.trust_building_rate
            self.successful_interventions += 1
        elif outcome == "failure":
            self.trust_level -= self.trust_erosion_rate
            self.failed_interventions += 1

        # Clamp to [0, 1]
        self.trust_level = max(0.0, min(1.0, self.trust_level))
        self.total_interactions += 1

        # Track trajectory
        self.trust_trajectory.append(self.trust_level)


class EmpathyOS:
    """Empathy Operating System for AI-Human Collaboration.

    Integrates:
    - 5-level Empathy Maturity Model
    - Systems Thinking (feedback loops, emergence, leverage points)
    - Tactical Empathy (Voss)
    - Emotional Intelligence (Goleman)
    - Clear Thinking (Naval)

    Goal: Enable AI to operate at Levels 3-4 (Proactive/Anticipatory)

    Example:
        Basic usage with empathy levels::

            from empathy_os import EmpathyOS

            # Create instance targeting Level 4 (Anticipatory)
            empathy = EmpathyOS(user_id="developer_123", target_level=4)

            # Level 1 - Reactive response
            response = empathy.level_1_reactive(
                user_input="How do I optimize database queries?",
                context={"domain": "software"}
            )

            # Level 2 - Guided with follow-up questions
            response = empathy.level_2_guided(
                user_input="I need help with my code",
                context={"task": "debugging"},
                history=[]
            )

        Memory operations::

            # Stash working data (short-term)
            empathy.stash("current_task", {"status": "debugging"})

            # Retrieve later
            task = empathy.retrieve("current_task")

            # Persist patterns (long-term)
            result = empathy.persist_pattern(
                content="Query optimization technique",
                pattern_type="technique"
            )

            # Recall patterns
            pattern = empathy.recall_pattern(result["pattern_id"])

    """

    def __init__(
        self,
        user_id: str,
        target_level: int = 3,
        confidence_threshold: float = 0.75,
        logger: logging.Logger | None = None,
        shared_library: PatternLibrary | None = None,
        short_term_memory: RedisShortTermMemory | None = None,
        access_tier: AccessTier = AccessTier.CONTRIBUTOR,
    ):
        """Initialize EmpathyOS

        Args:
            user_id: Unique identifier for user/team
            target_level: Target empathy level (1-5), default 3 (Proactive)
            confidence_threshold: Minimum confidence for anticipatory actions (0.0-1.0)
            logger: Optional logger instance for structured logging
            shared_library: Optional shared PatternLibrary for multi-agent collaboration.
                           When provided, enables agents to share discovered patterns,
                           supporting Level 5 (Systems Empathy) distributed memory networks.
            short_term_memory: Optional RedisShortTermMemory for fast, TTL-based working
                              memory. Enables real-time multi-agent coordination, pattern
                              staging, and conflict resolution.
            access_tier: Access tier for this agent (Observer, Contributor, Validator, Steward).
                        Determines what operations the agent can perform on shared memory.

        """
        self.user_id = user_id
        self.target_level = target_level
        self.confidence_threshold = confidence_threshold
        self.logger = logger or logging.getLogger(__name__)
        self.shared_library = shared_library

        # Short-term memory for multi-agent coordination
        self.short_term_memory = short_term_memory
        self.credentials = AgentCredentials(agent_id=user_id, tier=access_tier)

        # Collaboration state tracking
        self.collaboration_state = CollaborationState()

        # System thinking components
        self.feedback_detector = FeedbackLoopDetector()
        self.emergence_detector = EmergenceDetector()
        self.leverage_analyzer = LeveragePointAnalyzer()

        # Pattern storage for Level 3+
        self.user_patterns: list[dict] = []
        self.system_trajectory: list[dict] = []

        # Current empathy level
        self.current_empathy_level = 1

        # Session ID for tracking (generated on first use)
        self._session_id: str | None = None

        # Unified memory (lazily initialized)
        self._unified_memory: UnifiedMemory | None = None

    @property
    def memory(self) -> UnifiedMemory:
        """Unified memory interface for both short-term and long-term storage.

        Lazily initializes on first access with environment auto-detection.

        Usage:
            empathy = EmpathyOS(user_id="agent_1")

            # Store working data (short-term)
            empathy.memory.stash("analysis", {"results": [...]})

            # Persist pattern (long-term)
            result = empathy.memory.persist_pattern(
                content="Algorithm for X",
                pattern_type="algorithm",
            )

            # Retrieve pattern
            pattern = empathy.memory.recall_pattern(result["pattern_id"])
        """
        if self._unified_memory is None:
            self._unified_memory = UnifiedMemory(
                user_id=self.user_id,
                access_tier=self.credentials.tier,
            )
        return self._unified_memory

    # =========================================================================
    # UNIFIED MEMORY CONVENIENCE METHODS
    # =========================================================================

    def persist_pattern(
        self,
        content: str,
        pattern_type: str,
        classification: Classification | str | None = None,
        auto_classify: bool = True,
    ) -> dict | None:
        """Store a pattern in long-term memory with security controls.

        This is a convenience method that delegates to memory.persist_pattern().

        Args:
            content: Pattern content
            pattern_type: Type (algorithm, protocol, config, etc.)
            classification: Security classification (or auto-detect)
            auto_classify: Auto-detect classification from content

        Returns:
            Storage result with pattern_id and classification

        Example:
            >>> empathy = EmpathyOS(user_id="dev@company.com")
            >>> result = empathy.persist_pattern(
            ...     content="Our proprietary algorithm for...",
            ...     pattern_type="algorithm",
            ... )
            >>> print(result["classification"])  # "INTERNAL"

        """
        return self.memory.persist_pattern(
            content=content,
            pattern_type=pattern_type,
            classification=classification,
            auto_classify=auto_classify,
        )

    def recall_pattern(self, pattern_id: str) -> dict | None:
        """Retrieve a pattern from long-term memory.

        This is a convenience method that delegates to memory.recall_pattern().

        Args:
            pattern_id: ID of pattern to retrieve

        Returns:
            Pattern data with content and metadata

        Example:
            >>> pattern = empathy.recall_pattern("pat_123")
            >>> print(pattern["content"])

        """
        return self.memory.recall_pattern(pattern_id)

    def stash(self, key: str, value: Any, ttl_seconds: int = 3600) -> bool:
        """Store data in short-term memory with TTL.

        This is a convenience method that delegates to memory.stash().

        Args:
            key: Storage key
            value: Data to store
            ttl_seconds: Time-to-live (default 1 hour)

        Returns:
            True if stored successfully

        """
        return self.memory.stash(key, value, ttl_seconds)

    def retrieve(self, key: str) -> Any:
        """Retrieve data from short-term memory.

        This is a convenience method that delegates to memory.retrieve().

        Args:
            key: Storage key

        Returns:
            Stored data or None

        """
        return self.memory.retrieve(key)

    async def __aenter__(self):
        """Enter async context manager

        Enables usage: async with EmpathyOS(...) as empathy:

        Returns:
            self: The EmpathyOS instance

        """
        # Initialize any async resources here if needed
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit async context manager

        Performs cleanup when exiting the context:
        - Saves patterns if persistence is enabled
        - Closes any open connections
        - Logs final collaboration state

        Args:
            exc_type: Exception type if an exception occurred
            exc_val: Exception value if an exception occurred
            exc_tb: Exception traceback if an exception occurred

        Returns:
            False to propagate exceptions (standard behavior)

        """
        await self._cleanup()
        return False  # Don't suppress exceptions

    async def _cleanup(self):
        """Cleanup resources on context exit

        **Extension Point**: Override to add custom cleanup logic
        (e.g., save state to database, close connections, send metrics)
        """
        # Future: Save patterns to disk
        # Future: Send final metrics
        # Future: Close async connections

    # =========================================================================
    # SHARED PATTERN LIBRARY (Multi-Agent Collaboration)
    # =========================================================================

    def contribute_pattern(self, pattern) -> None:
        """Contribute a discovered pattern to the shared library.

        Enables Level 5 Systems Empathy: patterns discovered by this agent
        become available to all other agents sharing the same library.

        Args:
            pattern: Pattern object to contribute

        Raises:
            RuntimeError: If no shared library is configured

        Example:
            >>> from empathy_os import Pattern, PatternLibrary
            >>> library = PatternLibrary()
            >>> agent = EmpathyOS(user_id="code_reviewer", shared_library=library)
            >>> pattern = Pattern(
            ...     id="pat_001",
            ...     agent_id="code_reviewer",
            ...     pattern_type="best_practice",
            ...     name="Test pattern",
            ...     description="A discovered pattern",
            ... )
            >>> agent.contribute_pattern(pattern)

        """
        if self.shared_library is None:
            raise RuntimeError(
                "No shared library configured. Pass shared_library to __init__ "
                "to enable multi-agent pattern sharing.",
            )
        self.shared_library.contribute_pattern(self.user_id, pattern)

    def query_patterns(self, context: dict, **kwargs):
        """Query the shared library for patterns relevant to the current context.

        Enables agents to benefit from patterns discovered by other agents
        in the distributed memory network.

        Args:
            context: Dictionary describing the current context
            **kwargs: Additional arguments passed to PatternLibrary.query_patterns()
                     (e.g., pattern_type, min_confidence, limit)

        Returns:
            List of PatternMatch objects sorted by relevance

        Raises:
            RuntimeError: If no shared library is configured

        Example:
            >>> matches = agent.query_patterns(
            ...     context={"language": "python", "task": "code_review"},
            ...     min_confidence=0.7
            ... )
            >>> for match in matches:
            ...     print(f"{match.pattern.name}: {match.relevance_score:.0%}")

        """
        if self.shared_library is None:
            raise RuntimeError(
                "No shared library configured. Pass shared_library to __init__ "
                "to enable multi-agent pattern sharing.",
            )
        return self.shared_library.query_patterns(self.user_id, context, **kwargs)

    def has_shared_library(self) -> bool:
        """Check if this agent has a shared pattern library configured."""
        return self.shared_library is not None

    # =========================================================================
    # LEVEL 1: REACTIVE EMPATHY
    # =========================================================================

    async def level_1_reactive(self, user_request: str) -> dict:
        """Level 1: Reactive Empathy

        Respond to explicit request accurately and helpfully.
        No anticipation, no proactive action.

        Args:
            user_request: User's explicit request

        Returns:
            Dict with result and reasoning

        Raises:
            ValueError: If user_request is empty or not a string

        """
        # Input validation
        if not isinstance(user_request, str):
            raise ValidationError(
                f"user_request must be a string, got {type(user_request).__name__}",
            )
        if not user_request.strip():
            raise ValidationError("user_request cannot be empty")

        self.logger.info(
            "Level 1 reactive request started",
            extra={
                "user_id": self.user_id,
                "empathy_level": 1,
                "request_length": len(user_request),
            },
        )

        self.current_empathy_level = 1

        # Process request (implement your domain logic here)
        result = await self._process_request(user_request)

        self.logger.info(
            "Level 1 reactive request completed",
            extra={"user_id": self.user_id, "success": result.get("status") == "success"},
        )

        # Update collaboration state
        self.collaboration_state.total_interactions += 1

        return {
            "level": 1,
            "type": "reactive",
            "result": result,
            "reasoning": "Responding to explicit request",
            "empathy_level": "Reactive: Help after being asked",
        }

    # =========================================================================
    # LEVEL 2: GUIDED EMPATHY
    # =========================================================================

    async def level_2_guided(self, user_request: str) -> dict:
        """Level 2: Guided Empathy

        Use calibrated questions (Voss) to clarify intent before acting.
        Collaborative exploration to uncover hidden needs.

        Args:
            user_request: User's request (potentially ambiguous)

        Returns:
            Dict with clarification questions or refined result

        Raises:
            ValueError: If user_request is empty or not a string

        """
        # Input validation
        if not isinstance(user_request, str):
            raise ValidationError(
                f"user_request must be a string, got {type(user_request).__name__}",
            )
        if not user_request.strip():
            raise ValidationError("user_request cannot be empty")

        self.current_empathy_level = 2

        self.logger.info(
            "Level 2 guided request started",
            extra={
                "user_id": self.user_id,
                "empathy_level": 2,
                "request_length": len(user_request),
            },
        )

        # Use Voss's calibrated questions
        clarification = await self._ask_calibrated_questions(user_request)

        if clarification["needs_clarification"]:
            return {
                "level": 2,
                "type": "guided",
                "action": "clarify_first",
                "questions": clarification["questions"],
                "reasoning": "Asking clarifying questions to understand true intent",
                "empathy_level": "Guided: Collaborative exploration",
            }

        # Refine request based on clarification
        refined_request = self._refine_request(user_request, clarification)

        # Process refined request
        result = await self._process_request(refined_request)

        # Update collaboration state
        self.collaboration_state.total_interactions += 1
        self.collaboration_state.shared_context.update(clarification)

        self.logger.info(
            "Level 2 guided request completed",
            extra={
                "user_id": self.user_id,
                "empathy_level": 2,
                "action": "proceed",
                "clarification_applied": True,
            },
        )

        return {
            "level": 2,
            "type": "guided",
            "action": "proceed",
            "result": result,
            "clarification": clarification,
            "reasoning": "Collaborated to refine understanding before execution",
            "empathy_level": "Guided: Clarified through questions",
        }

    # =========================================================================
    # LEVEL 3: PROACTIVE EMPATHY
    # =========================================================================

    async def level_3_proactive(self, context: dict) -> dict:
        """Level 3: Proactive Empathy

        Detect patterns, act on leading indicators.
        Take initiative without being asked.

        Args:
            context: Current context (user activity, system state, etc.)

        Returns:
            Dict with proactive actions taken

        Raises:
            ValueError: If context is not a dict or is empty

        """
        # Input validation
        if not isinstance(context, dict):
            raise ValidationError(f"context must be a dict, got {type(context).__name__}")
        if not context:
            raise ValidationError("context cannot be empty")

        self.current_empathy_level = 3

        self.logger.info(
            "Level 3 proactive analysis started",
            extra={
                "user_id": self.user_id,
                "empathy_level": 3,
                "context_keys": list(context.keys()),
            },
        )

        # Detect current patterns
        active_patterns = self._detect_active_patterns(context)

        # Select proactive actions based on patterns
        proactive_actions = []

        for pattern in active_patterns:
            if pattern["confidence"] > 0.8:  # High confidence required
                action = self._design_proactive_action(pattern)

                # Safety check
                if self._is_safe_to_execute(action):
                    proactive_actions.append(action)

        # Execute proactive actions
        results = await self._execute_proactive_actions(proactive_actions)

        # Update collaboration state
        for result in results:
            outcome = "success" if result["success"] else "failure"
            self.collaboration_state.update_trust(outcome)

        self.logger.info(
            "Level 3 proactive actions completed",
            extra={
                "user_id": self.user_id,
                "empathy_level": 3,
                "patterns_detected": len(active_patterns),
                "actions_taken": len(proactive_actions),
                "success_rate": (
                    sum(1 for r in results if r["success"]) / len(results) if results else 0
                ),
            },
        )

        return {
            "level": 3,
            "type": "proactive",
            "patterns_detected": len(active_patterns),
            "actions_taken": len(proactive_actions),
            "results": results,
            "reasoning": "Acting on detected patterns without being asked",
            "empathy_level": "Proactive: Act before being asked",
        }

    # =========================================================================
    # LEVEL 4: ANTICIPATORY EMPATHY
    # =========================================================================

    async def level_4_anticipatory(self, system_trajectory: dict) -> dict:
        """Level 4: Anticipatory Empathy (THE INNOVATION)

        Predict future bottlenecks, design relief in advance.

        This is STRATEGIC CARE:
        - Timing + Prediction + Initiative
        - Solve tomorrow's pain today
        - Act without being told (but without overstepping)

        Args:
            system_trajectory: System state + growth trends + constraints

        Returns:
            Dict with predicted bottlenecks and interventions

        Raises:
            ValueError: If system_trajectory is not a dict or is empty

        """
        # Input validation
        if not isinstance(system_trajectory, dict):
            raise ValidationError(
                f"system_trajectory must be a dict, got {type(system_trajectory).__name__}",
            )
        if not system_trajectory:
            raise ValidationError("system_trajectory cannot be empty")

        self.current_empathy_level = 4

        self.logger.info(
            "Level 4 anticipatory prediction started",
            extra={
                "user_id": self.user_id,
                "empathy_level": 4,
                "trajectory_keys": list(system_trajectory.keys()),
            },
        )

        # Analyze system trajectory
        predicted_bottlenecks = self._predict_future_bottlenecks(system_trajectory)

        # Design structural relief for each bottleneck
        interventions = []

        for bottleneck in predicted_bottlenecks:
            # Only intervene if:
            # 1. High confidence (>75%)
            # 2. Appropriate time horizon (30-120 days)
            # 3. Reversible action
            if self._should_anticipate(bottleneck):
                intervention = self._design_anticipatory_intervention(bottleneck)
                interventions.append(intervention)

        # Execute anticipatory interventions
        results = await self._execute_anticipatory_interventions(interventions)

        # Update collaboration state
        for result in results:
            outcome = "success" if result["success"] else "failure"
            self.collaboration_state.update_trust(outcome)

        self.logger.info(
            "Level 4 anticipatory interventions completed",
            extra={
                "user_id": self.user_id,
                "empathy_level": 4,
                "bottlenecks_predicted": len(predicted_bottlenecks),
                "interventions_executed": len(interventions),
                "success_rate": (
                    sum(1 for r in results if r["success"]) / len(results) if results else 0
                ),
            },
        )

        return {
            "level": 4,
            "type": "anticipatory",
            "bottlenecks_predicted": predicted_bottlenecks,
            "interventions_designed": len(interventions),
            "results": results,
            "reasoning": "Predicting future bottlenecks and designing relief in advance",
            "empathy_level": "Anticipatory: Predict and prevent problems",
            "formula": "Timing + Prediction + Initiative = Anticipatory Empathy",
        }

    # =========================================================================
    # LEVEL 5: SYSTEMS EMPATHY
    # =========================================================================

    async def level_5_systems(self, domain_context: dict) -> dict:
        """Level 5: Systems Empathy

        Build structures that help at scale.
        Design leverage points, frameworks, self-sustaining systems.

        This is ARCHITECTURAL CARE:
        - One framework → infinite applications
        - Solve entire problem class, not individual instances
        - Design for emergence of desired properties

        Args:
            domain_context: Domain information, recurring problems, patterns

        Returns:
            Dict with designed frameworks and leverage points

        Raises:
            ValueError: If domain_context is not a dict or is empty

        """
        # Input validation
        if not isinstance(domain_context, dict):
            raise ValidationError(
                f"domain_context must be a dict, got {type(domain_context).__name__}",
            )
        if not domain_context:
            raise ValidationError("domain_context cannot be empty")

        self.current_empathy_level = 5

        self.logger.info(
            "Level 5 systems framework design started",
            extra={
                "user_id": self.user_id,
                "empathy_level": 5,
                "domain_keys": list(domain_context.keys()),
            },
        )

        # Identify problem class (not individual problem)
        problem_classes = self._identify_problem_classes(domain_context)

        # Find leverage points (Meadows's framework)
        leverage_points = []
        for problem_class in problem_classes:
            points = self.leverage_analyzer.find_leverage_points(problem_class)
            leverage_points.extend(points)

        # Design structural interventions at highest leverage points
        frameworks = []
        for lp in leverage_points:
            if lp.level.value >= 8:  # High leverage points only (Rules and above)
                framework = self._design_framework(lp)
                frameworks.append(framework)

        # Implement frameworks
        results = await self._implement_frameworks(frameworks)

        self.logger.info(
            "Level 5 systems frameworks implemented",
            extra={
                "user_id": self.user_id,
                "empathy_level": 5,
                "problem_classes": len(problem_classes),
                "leverage_points_found": len(leverage_points),
                "frameworks_deployed": len(frameworks),
            },
        )

        return {
            "level": 5,
            "type": "systems",
            "problem_classes": len(problem_classes),
            "leverage_points": leverage_points,
            "frameworks_designed": len(frameworks),
            "results": results,
            "reasoning": "Building structural solutions that scale to entire problem class",
            "empathy_level": "Systems: Build structures that help at scale",
        }

    # =========================================================================
    # HELPER METHODS (implement based on your domain)
    # =========================================================================

    async def _process_request(self, request: str) -> dict:
        """Process user request (implement domain logic)

        **Extension Point**: Override this method in subclasses to implement
        your specific domain logic for processing user requests.

        Args:
            request: The user's request string

        Returns:
            Dict with processed result and status

        """
        # Placeholder - implement your actual request processing
        return {"processed": request, "status": "success"}

    async def _ask_calibrated_questions(self, request: str) -> dict:
        """Voss's tactical empathy: Ask calibrated questions

        **Extension Point**: Override to implement sophisticated clarification
        logic using NLP, LLMs, or domain-specific heuristics.

        Args:
            request: The user's request string

        Returns:
            Dict with needs_clarification flag and optional questions list

        """
        # Simple heuristic - in production, use NLP/LLM
        needs_clarification = any(
            word in request.lower() for word in ["some", "a few", "many", "soon"]
        )

        if needs_clarification:
            return {
                "needs_clarification": True,
                "questions": [
                    "What are you hoping to accomplish?",
                    "How does this fit into your workflow?",
                    "What would make this most helpful right now?",
                ],
            }
        return {"needs_clarification": False}

    def _refine_request(self, original: str, clarification: dict) -> str:
        """Refine request based on clarification responses

        **Extension Point**: Override to implement domain-specific request refinement
        based on clarification questions and user responses.

        Args:
            original: Original request string
            clarification: Dict containing clarification questions and responses

        Returns:
            Refined request string with added context

        """
        # If no clarification was needed, return original
        if not clarification.get("needs_clarification", False):
            return original

        # If clarification responses exist, incorporate them
        if "responses" in clarification:
            refinements = []
            for question, response in clarification["responses"].items():
                refinements.append(f"{question}: {response}")

            refined = f"{original}\n\nClarifications:\n" + "\n".join(f"- {r}" for r in refinements)
            return refined

        # Default: return original
        return original

    def _detect_active_patterns(self, context: dict) -> list[dict]:
        """Detect patterns in user behavior"""
        patterns = []

        # Example pattern detection logic
        if context.get("repeated_action"):
            patterns.append(
                {
                    "type": "sequential",
                    "pattern": "user_always_does_X_before_Y",
                    "confidence": 0.85,
                },
            )

        return patterns

    def _design_proactive_action(self, pattern: dict) -> dict:
        """Design proactive action based on pattern"""
        return {
            "action": "prefetch_data",
            "reasoning": f"Pattern detected: {pattern['pattern']}",
            "confidence": pattern["confidence"],
        }

    def _is_safe_to_execute(self, action: dict[str, Any]) -> bool:
        """Safety check for proactive actions"""
        confidence: float = action.get("confidence", 0)
        return confidence > 0.8

    async def _execute_proactive_actions(self, actions: list[dict]) -> list[dict]:
        """Execute proactive actions

        **Extension Point**: Override to implement actual execution of proactive
        actions in your domain (e.g., file operations, API calls, UI updates).

        This default implementation simulates execution with basic validation.
        Override this method to add real action execution logic.

        Args:
            actions: List of action dicts to execute

        Returns:
            List of result dicts with action and success status

        """
        results = []
        for action in actions:
            # Validate action has required fields
            if not action.get("action"):
                results.append(
                    {"action": action, "success": False, "error": "Missing 'action' field"},
                )
                continue

            # Log the action (in production, this would execute real logic)
            self.logger.debug(
                f"Executing proactive action: {action.get('action')}",
                extra={
                    "user_id": self.user_id,
                    "action_type": action.get("action"),
                    "confidence": action.get("confidence", 0),
                },
            )

            # Simulate successful execution
            results.append(
                {"action": action, "success": True, "executed_at": datetime.now().isoformat()},
            )

        return results

    def _predict_future_bottlenecks(self, trajectory: dict) -> list[dict]:
        """Predict where system will hit friction/overload

        Uses trajectory analysis, domain knowledge, historical patterns
        """
        bottlenecks = []

        # Example: Scaling bottleneck
        if trajectory.get("feature_count_increasing"):
            current = trajectory["current_feature_count"]
            growth_rate = trajectory.get("growth_rate", 0)
            projected_3mo = current + (growth_rate * 3)

            if projected_3mo > trajectory.get("threshold", 25):
                bottlenecks.append(
                    {
                        "type": "scaling_bottleneck",
                        "area": "testing",
                        "description": "Testing burden will become unsustainable",
                        "timeframe": "2-3 months",
                        "confidence": 0.75,
                        "current_state": f"{current} features",
                        "predicted_state": f"{projected_3mo} features",
                        "impact": trajectory.get("impact", "low"),
                    },
                )

        return bottlenecks

    def _should_anticipate(self, bottleneck: dict) -> bool:
        """Safety checks for Level 4 anticipatory actions

        Validates:
        1. Confidence is above threshold
        2. Time horizon is appropriate (30-120 days)
        3. Impact justifies the intervention effort
        """
        # Check 1: Confidence threshold
        if bottleneck["confidence"] < self.confidence_threshold:
            return False

        # Check 2: Time horizon (30-120 days ideal)
        timeframe = bottleneck.get("timeframe", "")
        days = self._parse_timeframe_to_days(timeframe)

        # Too soon (<30 days) = reactive, not anticipatory
        # Too far (>120 days) = too uncertain to act on
        if days is not None and (days < 30 or days > 120):
            return False

        # Check 3: Impact justifies effort
        if bottleneck.get("impact", "low") not in ["high", "critical"]:
            return False

        return True

    def _parse_timeframe_to_days(self, timeframe: str) -> int | None:
        """Parse timeframe string to days

        Examples:
            "2-3 months" -> 75 (midpoint)
            "60 days" -> 60
            "3 weeks" -> 21

        Returns:
            Number of days, or None if unparseable

        """
        import re

        if not timeframe:
            return None

        timeframe_lower = timeframe.lower()

        # Pattern: "X days"
        match = re.search(r"(\d+)\s*days?", timeframe_lower)
        if match:
            return int(match.group(1))

        # Pattern: "X weeks"
        match = re.search(r"(\d+)\s*weeks?", timeframe_lower)
        if match:
            return int(match.group(1)) * 7

        # Pattern: "X months" or "X-Y months"
        match = re.search(r"(\d+)(?:-(\d+))?\s*months?", timeframe_lower)
        if match:
            start = int(match.group(1))
            end = int(match.group(2)) if match.group(2) else start
            midpoint = (start + end) / 2
            return int(midpoint * 30)  # Approximate 30 days/month

        # Couldn't parse - return None (will skip time validation)
        return None

    def _design_anticipatory_intervention(self, bottleneck: dict) -> dict:
        """Design structural relief for predicted bottleneck"""
        return {
            "type": "framework_design",
            "target": bottleneck["area"],
            "deliverables": ["design_doc", "implementation_plan"],
            "timeline": "Implement before threshold",
        }

    async def _execute_anticipatory_interventions(self, interventions: list[dict]) -> list[dict]:
        """Execute anticipatory interventions

        **Extension Point**: Override to implement actual execution of
        anticipatory interventions (e.g., scaling resources, provisioning
        infrastructure, preparing documentation).

        This default implementation simulates intervention execution with
        validation and logging. Override for real infrastructure changes.

        Args:
            interventions: List of intervention dicts to execute

        Returns:
            List of result dicts with intervention and success status

        """
        results = []
        for intervention in interventions:
            # Validate intervention has required fields
            if not intervention.get("type"):
                results.append(
                    {
                        "intervention": intervention,
                        "success": False,
                        "error": "Missing 'type' field",
                    },
                )
                continue

            # Log the intervention (in production, this would trigger real infrastructure changes)
            self.logger.info(
                f"Executing anticipatory intervention: {intervention.get('type')}",
                extra={
                    "user_id": self.user_id,
                    "intervention_type": intervention.get("type"),
                    "target": intervention.get("target"),
                    "timeline": intervention.get("timeline"),
                },
            )

            # Simulate successful intervention
            results.append(
                {
                    "intervention": intervention,
                    "success": True,
                    "executed_at": datetime.now().isoformat(),
                    "status": "intervention_deployed",
                },
            )

        return results

    def _identify_problem_classes(self, domain_context: dict) -> list[dict]:
        """Identify recurring problem classes (not individual instances)

        Use "Rule of Three":
        - Occurred at least 3 times
        - Will occur at least 3 more times
        - Affects at least 3 users/workflows
        """
        problem_classes = []

        # Example detection logic
        if domain_context.get("recurring_documentation_burden"):
            problem_classes.append(
                {
                    "class": "documentation_burden",
                    "instances": domain_context["instances"],
                    "frequency": "every_new_feature",
                },
            )

        return problem_classes

    def _design_framework(self, leverage_point: LeveragePoint) -> dict:
        """Design framework at leverage point"""
        return {
            "name": f"{leverage_point.problem_domain}_framework",
            "type": "architectural_pattern",
            "leverage_point": leverage_point.description,
            "leverage_level": leverage_point.level.value,
            "impact": "Scales to all current + future instances",
        }

    async def _implement_frameworks(self, frameworks: list[dict]) -> list[dict]:
        """Implement designed frameworks

        **Extension Point**: Override to implement actual framework deployment
        (e.g., generating code templates, creating CI/CD pipelines, deploying
        infrastructure, setting up monitoring).

        This default implementation simulates framework deployment with validation
        and logging. Override for real framework deployment logic.

        Args:
            frameworks: List of framework dicts to implement

        Returns:
            List of result dicts with framework and deployed status

        """
        results = []
        for framework in frameworks:
            # Validate framework has required fields
            if not framework.get("name"):
                results.append(
                    {"framework": framework, "deployed": False, "error": "Missing 'name' field"},
                )
                continue

            # Log the framework deployment (in production, this would deploy real infrastructure)
            self.logger.info(
                f"Deploying systems framework: {framework.get('name')}",
                extra={
                    "user_id": self.user_id,
                    "framework_name": framework.get("name"),
                    "framework_type": framework.get("type"),
                    "leverage_level": framework.get("leverage_level"),
                },
            )

            # Simulate successful deployment
            results.append(
                {
                    "framework": framework,
                    "deployed": True,
                    "deployed_at": datetime.now().isoformat(),
                    "status": "framework_active",
                    "impact_scope": "system_wide",
                },
            )

        return results

    # =========================================================================
    # FEEDBACK LOOP MANAGEMENT
    # =========================================================================

    def monitor_feedback_loops(self, session_history: list) -> dict:
        """Detect and manage feedback loops in collaboration"""
        active_loops = self.feedback_detector.detect_active_loop(session_history)

        # Take action based on loop type
        if active_loops.get("dominant_loop") == "R2_trust_erosion":
            # URGENT: Break vicious cycle
            return self._break_trust_erosion_loop()

        if active_loops.get("dominant_loop") == "R1_trust_building":
            # MAINTAIN: Keep virtuous cycle going
            return self._maintain_trust_building_loop()

        return active_loops

    def _break_trust_erosion_loop(self) -> dict:
        """Intervention to break vicious cycle of trust erosion"""
        return {
            "action": "transparency_intervention",
            "steps": [
                "Acknowledge misalignment explicitly",
                "Ask calibrated questions (Level 2)",
                "Reduce initiative temporarily (drop to Level 1-2)",
                "Rebuild trust through consistent small wins",
            ],
        }

    def _maintain_trust_building_loop(self) -> dict:
        """Maintain virtuous cycle of trust building"""
        return {
            "action": "maintain_momentum",
            "steps": [
                "Continue current approach",
                "Gradually increase initiative (Level 3 → 4)",
                "Document successful patterns",
            ],
        }

    # =========================================================================
    # STATE MANAGEMENT
    # =========================================================================

    def get_collaboration_state(self) -> dict:
        """Get current collaboration state"""
        return {
            "trust_level": self.collaboration_state.trust_level,
            "total_interactions": self.collaboration_state.total_interactions,
            "success_rate": (
                self.collaboration_state.successful_interventions
                / self.collaboration_state.total_interactions
                if self.collaboration_state.total_interactions > 0
                else 0
            ),
            "current_empathy_level": self.current_empathy_level,
            "target_empathy_level": self.target_level,
        }

    def reset_collaboration_state(self):
        """Reset collaboration state (new session)"""
        self.collaboration_state = CollaborationState()

    # =========================================================================
    # SHORT-TERM MEMORY (Redis-backed Multi-Agent Coordination)
    # =========================================================================

    def has_short_term_memory(self) -> bool:
        """Check if this agent has short-term memory configured."""
        return self.short_term_memory is not None

    @property
    def session_id(self) -> str:
        """Get or generate a unique session ID for this agent instance."""
        if self._session_id is None:
            import uuid

            self._session_id = f"{self.user_id}_{uuid.uuid4().hex[:8]}"
        return self._session_id

    def stage_pattern(self, pattern: StagedPattern) -> bool:
        """Stage a discovered pattern for validation.

        Patterns are held in a staging area until a Validator promotes them
        to the active pattern library. This implements the trust-but-verify
        approach to multi-agent knowledge building.

        Args:
            pattern: StagedPattern with discovery details

        Returns:
            True if staged successfully

        Raises:
            RuntimeError: If no short-term memory configured
            PermissionError: If agent lacks Contributor+ access

        Example:
            >>> from empathy_os import StagedPattern
            >>> pattern = StagedPattern(
            ...     pattern_id="pat_auth_001",
            ...     agent_id=empathy.user_id,
            ...     pattern_type="security",
            ...     name="JWT Token Refresh Pattern",
            ...     description="Refresh tokens before expiry to prevent auth failures",
            ...     confidence=0.85,
            ... )
            >>> empathy.stage_pattern(pattern)

        """
        if self.short_term_memory is None:
            raise RuntimeError(
                "No short-term memory configured. Pass short_term_memory to __init__ "
                "to enable pattern staging.",
            )
        return self.short_term_memory.stage_pattern(pattern, self.credentials)

    def get_staged_patterns(self) -> list[StagedPattern]:
        """Get all patterns currently in staging.

        Returns patterns staged by any agent that are awaiting validation.
        Validators use this to review and promote/reject patterns.

        Returns:
            List of StagedPattern objects

        Raises:
            RuntimeError: If no short-term memory configured

        """
        if self.short_term_memory is None:
            raise RuntimeError(
                "No short-term memory configured. Pass short_term_memory to __init__ "
                "to enable pattern staging.",
            )
        return self.short_term_memory.list_staged_patterns(self.credentials)

    def send_signal(
        self,
        signal_type: str,
        data: dict,
        target_agent: str | None = None,
    ) -> bool:
        """Send a coordination signal to other agents.

        Use signals for real-time coordination:
        - Notify completion of tasks
        - Request assistance
        - Broadcast status updates

        Args:
            signal_type: Type of signal (e.g., "task_complete", "need_review")
            data: Signal payload
            target_agent: Specific agent to target, or None for broadcast

        Returns:
            True if sent successfully

        Raises:
            RuntimeError: If no short-term memory configured

        Example:
            >>> # Notify specific agent
            >>> empathy.send_signal(
            ...     "analysis_complete",
            ...     {"files": 10, "issues_found": 3},
            ...     target_agent="lead_reviewer"
            ... )
            >>> # Broadcast to all
            >>> empathy.send_signal("status_update", {"phase": "testing"})

        """
        if self.short_term_memory is None:
            raise RuntimeError(
                "No short-term memory configured. Pass short_term_memory to __init__ "
                "to enable coordination signals.",
            )
        return self.short_term_memory.send_signal(
            signal_type=signal_type,
            data=data,
            credentials=self.credentials,
            target_agent=target_agent,
        )

    def receive_signals(self, signal_type: str | None = None) -> list[dict]:
        """Receive coordination signals from other agents.

        Returns signals targeted at this agent or broadcast signals.
        Signals expire after 5 minutes (TTL).

        Args:
            signal_type: Filter by signal type, or None for all

        Returns:
            List of signal dicts with sender, type, data, timestamp

        Raises:
            RuntimeError: If no short-term memory configured

        Example:
            >>> signals = empathy.receive_signals("analysis_complete")
            >>> for sig in signals:
            ...     print(f"From {sig['sender']}: {sig['data']}")

        """
        if self.short_term_memory is None:
            raise RuntimeError(
                "No short-term memory configured. Pass short_term_memory to __init__ "
                "to enable coordination signals.",
            )
        return self.short_term_memory.receive_signals(self.credentials, signal_type=signal_type)

    def persist_collaboration_state(self) -> bool:
        """Persist current collaboration state to short-term memory.

        Call periodically to save state that can be recovered if the agent
        restarts. State expires after 30 minutes by default.

        Returns:
            True if persisted successfully

        Raises:
            RuntimeError: If no short-term memory configured

        """
        if self.short_term_memory is None:
            raise RuntimeError(
                "No short-term memory configured. Pass short_term_memory to __init__ "
                "to enable state persistence.",
            )

        state_data = {
            "trust_level": self.collaboration_state.trust_level,
            "successful_interventions": self.collaboration_state.successful_interventions,
            "failed_interventions": self.collaboration_state.failed_interventions,
            "total_interactions": self.collaboration_state.total_interactions,
            "current_empathy_level": self.current_empathy_level,
            "session_start": self.collaboration_state.session_start.isoformat(),
            "trust_trajectory": self.collaboration_state.trust_trajectory[-100:],  # Last 100
        }
        return self.short_term_memory.stash(
            f"collaboration_state_{self.session_id}",
            state_data,
            self.credentials,
        )

    def restore_collaboration_state(self, session_id: str | None = None) -> bool:
        """Restore collaboration state from short-term memory.

        Use to recover state after agent restart or to continue a previous
        session.

        Args:
            session_id: Session to restore, or None for current session

        Returns:
            True if state was found and restored

        Raises:
            RuntimeError: If no short-term memory configured

        """
        if self.short_term_memory is None:
            raise RuntimeError(
                "No short-term memory configured. Pass short_term_memory to __init__ "
                "to enable state persistence.",
            )

        sid = session_id or self.session_id
        state_data = self.short_term_memory.retrieve(
            f"collaboration_state_{sid}",
            self.credentials,
        )

        if state_data is None:
            return False

        # Restore state
        self.collaboration_state.trust_level = state_data.get("trust_level", 0.5)
        self.collaboration_state.successful_interventions = state_data.get(
            "successful_interventions",
            0,
        )
        self.collaboration_state.failed_interventions = state_data.get("failed_interventions", 0)
        self.collaboration_state.total_interactions = state_data.get("total_interactions", 0)
        self.current_empathy_level = state_data.get("current_empathy_level", 1)
        self.collaboration_state.trust_trajectory = state_data.get("trust_trajectory", [])

        self.logger.info(
            f"Restored collaboration state from session {sid}",
            extra={
                "user_id": self.user_id,
                "restored_trust_level": self.collaboration_state.trust_level,
                "restored_interactions": self.collaboration_state.total_interactions,
            },
        )

        return True

    def get_memory_stats(self) -> dict | None:
        """Get statistics about the short-term memory system.

        Returns:
            Dict with memory usage, key counts, mode, or None if not configured

        """
        if self.short_term_memory is None:
            return None
        return self.short_term_memory.get_stats()
