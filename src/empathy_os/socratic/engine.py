"""Socratic Workflow Builder - Main Engine

The core engine that orchestrates Socratic questioning for agent generation.

Flow:
1. User provides initial goal (free text)
2. Engine analyzes goal and generates clarifying questions
3. User answers questions (forms)
4. Engine determines if more clarification needed
5. When ready, generates optimized workflow with agents
6. Defines success criteria for measuring completion

Copyright 2026 Smart-AI-Memory
Licensed under Fair Source License 0.9
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from .blueprint import WorkflowBlueprint
from .forms import (
    FieldOption,
    FieldType,
    FieldValidation,
    Form,
    FormField,
    FormResponse,
    create_additional_context_field,
    create_automation_level_field,
    create_goal_text_field,
    create_language_field,
    create_quality_focus_field,
    create_team_size_field,
)
from .generator import AgentGenerator, GeneratedWorkflow
from .session import GoalAnalysis, RequirementSet, SessionState, SocraticSession
from .success import (
    MetricType,
    SuccessCriteria,
    SuccessMetric,
    code_review_criteria,
    security_audit_criteria,
    test_generation_criteria,
)

logger = logging.getLogger(__name__)


# =============================================================================
# DOMAIN DETECTION
# =============================================================================


@dataclass
class DomainPattern:
    """Pattern for detecting user intent domain."""

    domain: str
    keywords: list[str]
    phrases: list[str]
    weight: float = 1.0


DOMAIN_PATTERNS = [
    DomainPattern(
        domain="code_review",
        keywords=["review", "pr", "pull request", "merge", "diff", "changes"],
        phrases=["code review", "review code", "check my code", "review my"],
        weight=1.0,
    ),
    DomainPattern(
        domain="security",
        keywords=["security", "vulnerability", "secure", "exploit", "attack", "owasp"],
        phrases=["security audit", "find vulnerabilities", "security check", "penetration"],
        weight=1.2,
    ),
    DomainPattern(
        domain="testing",
        keywords=["test", "coverage", "unit test", "integration", "pytest", "jest"],
        phrases=["write tests", "generate tests", "test coverage", "increase coverage"],
        weight=1.0,
    ),
    DomainPattern(
        domain="documentation",
        keywords=["document", "docstring", "readme", "api docs", "comment"],
        phrases=["write documentation", "generate docs", "add docstrings"],
        weight=0.9,
    ),
    DomainPattern(
        domain="performance",
        keywords=["performance", "optimize", "speed", "slow", "memory", "efficient"],
        phrases=["improve performance", "optimize code", "make faster", "reduce memory"],
        weight=1.0,
    ),
    DomainPattern(
        domain="refactoring",
        keywords=["refactor", "clean", "restructure", "simplify", "modular"],
        phrases=["refactor code", "clean up", "improve structure"],
        weight=0.9,
    ),
]


def detect_domain(goal: str) -> tuple[str, float]:
    """Detect the domain from goal text.

    Returns:
        Tuple of (domain, confidence)
    """
    goal_lower = goal.lower()
    scores: dict[str, float] = {}

    for pattern in DOMAIN_PATTERNS:
        score = 0.0

        # Check keywords
        for keyword in pattern.keywords:
            if keyword in goal_lower:
                score += 1.0 * pattern.weight

        # Check phrases (higher weight)
        for phrase in pattern.phrases:
            if phrase in goal_lower:
                score += 2.0 * pattern.weight

        if score > 0:
            scores[pattern.domain] = score

    if not scores:
        return "general", 0.5

    best_domain = max(scores, key=lambda k: scores[k])
    max_score = scores[best_domain]

    # Normalize confidence (cap at 1.0)
    confidence = min(max_score / 5.0, 1.0)

    return best_domain, confidence


def extract_keywords(goal: str) -> list[str]:
    """Extract important keywords from goal."""
    # Remove common words
    stop_words = {
        "i", "want", "to", "the", "a", "an", "my", "our", "for", "with",
        "that", "this", "is", "are", "be", "will", "would", "could",
        "should", "can", "help", "me", "us", "please", "need", "like",
    }

    # Extract words
    words = re.findall(r"\b\w+\b", goal.lower())
    keywords = [w for w in words if w not in stop_words and len(w) > 2]

    # Return unique keywords preserving order
    return list(dict.fromkeys(keywords))


def identify_ambiguities(goal: str, domain: str) -> list[str]:
    """Identify ambiguities in the goal that need clarification."""
    ambiguities = []

    # Check for missing specifics
    if not any(lang in goal.lower() for lang in ["python", "javascript", "typescript", "java", "go", "rust"]):
        ambiguities.append("Programming language not specified")

    # Check for vague scope
    vague_terms = ["some", "various", "different", "several", "multiple"]
    for term in vague_terms:
        if term in goal.lower():
            ambiguities.append(f"Vague scope indicator: '{term}'")
            break

    # Domain-specific ambiguities
    if domain == "code_review":
        if "security" not in goal.lower() and "style" not in goal.lower():
            ambiguities.append("Review focus areas not specified")

    if domain == "testing":
        if "unit" not in goal.lower() and "integration" not in goal.lower():
            ambiguities.append("Test type not specified")

    return ambiguities


def identify_assumptions(goal: str, domain: str) -> list[str]:
    """Identify assumptions we're making from the goal."""
    assumptions = []

    # Common assumptions
    if domain == "code_review":
        assumptions.append("Assuming code is version-controlled (git)")
        assumptions.append("Assuming PR/diff-based review workflow")

    if domain == "testing":
        assumptions.append("Assuming existing test framework in project")

    if domain == "security":
        assumptions.append("Assuming standard web application security model")

    return assumptions


# =============================================================================
# QUESTION GENERATION
# =============================================================================


def generate_initial_questions(
    goal_analysis: GoalAnalysis,
    session: SocraticSession,
) -> Form:
    """Generate the first round of questions based on goal analysis."""
    fields: list[FormField] = []

    # Always ask about languages if not detected
    if "Programming language not specified" in goal_analysis.ambiguities:
        fields.append(create_language_field(required=True))

    # Ask about quality focus
    fields.append(create_quality_focus_field(required=True))

    # Domain-specific questions
    if goal_analysis.domain == "code_review":
        fields.append(FormField(
            id="review_scope",
            field_type=FieldType.SINGLE_SELECT,
            label="What scope of review do you need?",
            options=[
                FieldOption("pr", "Pull Request/Diff", description="Review specific changes", recommended=True),
                FieldOption("file", "Single File", description="Deep review of one file"),
                FieldOption("directory", "Directory/Module", description="Review entire module"),
                FieldOption("project", "Full Project", description="Comprehensive codebase review"),
            ],
            validation=FieldValidation(required=True),
            category="scope",
        ))

    if goal_analysis.domain == "security":
        fields.append(FormField(
            id="security_focus",
            field_type=FieldType.MULTI_SELECT,
            label="What security aspects are most important?",
            options=[
                FieldOption("owasp", "OWASP Top 10", description="Common web vulnerabilities"),
                FieldOption("injection", "Injection Attacks", description="SQL, command, XSS"),
                FieldOption("auth", "Authentication/Authorization", description="Access control issues"),
                FieldOption("crypto", "Cryptography", description="Encryption, hashing, secrets"),
                FieldOption("deps", "Dependencies", description="Vulnerable dependencies"),
            ],
            validation=FieldValidation(required=True),
            category="security",
        ))

    if goal_analysis.domain == "testing":
        fields.append(FormField(
            id="test_type",
            field_type=FieldType.MULTI_SELECT,
            label="What types of tests do you need?",
            options=[
                FieldOption("unit", "Unit Tests", description="Test individual functions", recommended=True),
                FieldOption("integration", "Integration Tests", description="Test component interactions"),
                FieldOption("e2e", "End-to-End Tests", description="Test full user flows"),
                FieldOption("edge", "Edge Cases", description="Test boundary conditions"),
            ],
            validation=FieldValidation(required=True),
            category="testing",
        ))

    # Automation level (always relevant)
    fields.append(create_automation_level_field())

    # Team context (helps calibration)
    fields.append(create_team_size_field())

    # Additional context (optional)
    fields.append(create_additional_context_field())

    return Form(
        id=f"round_{session.current_round + 1}",
        title="Help Us Understand Your Needs",
        description=f"Based on your goal: \"{goal_analysis.raw_goal[:100]}...\"",
        fields=fields,
        round_number=session.current_round + 1,
        progress=0.3,
    )


def generate_followup_questions(
    session: SocraticSession,
) -> Form | None:
    """Generate follow-up questions based on previous answers."""
    # Check if we need more clarification
    if session.requirements.completeness_score() >= 0.8:
        return None  # Ready to generate

    if session.current_round >= session.max_rounds:
        return None  # Max rounds reached

    fields: list[FormField] = []

    # Check what's still missing
    reqs = session.requirements

    # If no must-haves, ask for priorities
    if not reqs.must_have:
        fields.append(FormField(
            id="priorities",
            field_type=FieldType.TEXT_AREA,
            label="What are your top 3 priorities for this workflow?",
            help_text="Be as specific as possible about what success looks like.",
            validation=FieldValidation(required=True, min_length=20),
            category="priorities",
        ))

    # If technical constraints missing
    if not reqs.technical_constraints.get("languages"):
        fields.append(create_language_field(required=True))

    # Domain-specific follow-ups
    if session.goal_analysis and session.goal_analysis.domain == "code_review":
        if "review_depth" not in [r.get("id") for r in session.question_rounds[-1]["questions"]] if session.question_rounds else True:
            fields.append(FormField(
                id="review_depth",
                field_type=FieldType.SINGLE_SELECT,
                label="How thorough should the review be?",
                options=[
                    FieldOption("quick", "Quick Scan", description="Fast, surface-level review"),
                    FieldOption("standard", "Standard", description="Balanced depth", recommended=True),
                    FieldOption("deep", "Deep Dive", description="Thorough, detailed analysis"),
                ],
                category="depth",
            ))

    if not fields:
        return None

    return Form(
        id=f"round_{session.current_round + 1}",
        title="A Few More Questions",
        description="Help us fine-tune your workflow.",
        fields=fields,
        round_number=session.current_round + 1,
        progress=0.3 + (session.current_round * 0.2),
    )


# =============================================================================
# MAIN ENGINE
# =============================================================================


class SocraticWorkflowBuilder:
    """Main engine for Socratic agent/workflow generation.

    Example:
        >>> builder = SocraticWorkflowBuilder()
        >>>
        >>> # Start with a goal
        >>> session = builder.start_session("I want to automate security reviews")
        >>>
        >>> # Get questions
        >>> form = builder.get_next_questions(session)
        >>> print(form.title)
        >>>
        >>> # Submit answers
        >>> session = builder.submit_answers(session, {
        ...     "languages": ["python"],
        ...     "quality_focus": ["security"],
        ...     "automation_level": "semi_auto"
        ... })
        >>>
        >>> # Check if ready
        >>> if builder.is_ready_to_generate(session):
        ...     workflow = builder.generate_workflow(session)
        ...     print(workflow.describe())
    """

    def __init__(self):
        """Initialize the builder."""
        self.generator = AgentGenerator()
        self._sessions: dict[str, SocraticSession] = {}

    def start_session(self, goal: str = "") -> SocraticSession:
        """Start a new Socratic session.

        Args:
            goal: Optional initial goal (can be set later)

        Returns:
            New SocraticSession
        """
        session = SocraticSession()

        if goal:
            session = self.set_goal(session, goal)

        self._sessions[session.session_id] = session
        return session

    def get_session(self, session_id: str) -> SocraticSession | None:
        """Retrieve a session by ID."""
        return self._sessions.get(session_id)

    def set_goal(self, session: SocraticSession, goal: str) -> SocraticSession:
        """Set or update the session goal.

        Args:
            session: The session to update
            goal: The user's goal statement

        Returns:
            Updated session with goal analysis
        """
        session.goal = goal
        session.state = SessionState.ANALYZING_GOAL
        session.touch()

        # Analyze the goal
        domain, confidence = detect_domain(goal)
        keywords = extract_keywords(goal)
        ambiguities = identify_ambiguities(goal, domain)
        assumptions = identify_assumptions(goal, domain)

        session.goal_analysis = GoalAnalysis(
            raw_goal=goal,
            intent=self._extract_intent(goal, domain),
            domain=domain,
            confidence=confidence,
            ambiguities=ambiguities,
            assumptions=assumptions,
            keywords=keywords,
        )

        # Transition to awaiting answers
        session.state = SessionState.AWAITING_ANSWERS
        return session

    def _extract_intent(self, goal: str, domain: str) -> str:
        """Extract the core intent from the goal."""
        intent_patterns = {
            "code_review": "Automated code review",
            "security": "Security vulnerability analysis",
            "testing": "Automated test generation",
            "documentation": "Documentation generation",
            "performance": "Performance optimization",
            "refactoring": "Code refactoring",
            "general": "Code analysis and improvement",
        }
        return intent_patterns.get(domain, "Code analysis")

    def get_initial_form(self) -> Form:
        """Get the initial goal capture form."""
        return Form(
            id="initial_goal",
            title="What would you like to accomplish?",
            description=(
                "Describe your goal in your own words. Be as specific as you like - "
                "we'll ask clarifying questions to understand exactly what you need."
            ),
            fields=[create_goal_text_field()],
            round_number=0,
            progress=0.1,
        )

    def get_next_questions(self, session: SocraticSession) -> Form | None:
        """Get the next set of questions for a session.

        Args:
            session: The current session

        Returns:
            Form with questions, or None if ready to generate
        """
        if session.state == SessionState.AWAITING_GOAL:
            return self.get_initial_form()

        if session.state == SessionState.READY_TO_GENERATE:
            return None

        if session.state == SessionState.COMPLETED:
            return None

        if session.goal_analysis is None:
            return self.get_initial_form()

        # First round of questions
        if session.current_round == 0:
            return generate_initial_questions(session.goal_analysis, session)

        # Follow-up questions
        return generate_followup_questions(session)

    def submit_answers(
        self,
        session: SocraticSession,
        answers: dict[str, Any],
    ) -> SocraticSession:
        """Submit answers to the current questions.

        Args:
            session: The current session
            answers: Dictionary mapping field IDs to values

        Returns:
            Updated session
        """
        session.state = SessionState.PROCESSING_ANSWERS
        session.touch()

        # Record this round
        current_form = self.get_next_questions(session)
        questions_data = []
        if current_form:
            questions_data = [
                {"id": f.id, "label": f.label}
                for f in current_form.fields
            ]

        session.add_question_round(questions_data, answers)

        # Update requirements from answers
        self._update_requirements(session, answers)

        # Check if we can generate
        if session.can_generate():
            session.state = SessionState.READY_TO_GENERATE
        else:
            session.state = SessionState.AWAITING_ANSWERS

        return session

    def _update_requirements(
        self,
        session: SocraticSession,
        answers: dict[str, Any],
    ) -> None:
        """Update session requirements from answers."""
        reqs = session.requirements

        # Languages
        if "languages" in answers:
            reqs.technical_constraints["languages"] = answers["languages"]

        # Quality focus
        if "quality_focus" in answers:
            reqs.quality_attributes = {q: 1.0 for q in answers["quality_focus"]}
            # Add to must-haves
            for quality in answers["quality_focus"]:
                req = f"Optimize for {quality}"
                if req not in reqs.must_have:
                    reqs.must_have.append(req)

        # Automation level
        if "automation_level" in answers:
            reqs.preferences["automation_level"] = answers["automation_level"]

        # Team size
        if "team_size" in answers:
            reqs.preferences["team_size"] = answers["team_size"]

        # Domain-specific
        if "review_scope" in answers:
            reqs.domain_specific["review_scope"] = answers["review_scope"]

        if "security_focus" in answers:
            reqs.domain_specific["security_focus"] = answers["security_focus"]

        if "test_type" in answers:
            reqs.domain_specific["test_type"] = answers["test_type"]

        # Additional context
        if "additional_context" in answers and answers["additional_context"]:
            reqs.domain_specific["additional_context"] = answers["additional_context"]

        # Priorities
        if "priorities" in answers:
            priorities = answers["priorities"]
            if isinstance(priorities, str):
                # Parse priorities from text
                for line in priorities.split("\n"):
                    line = line.strip()
                    if line and line not in reqs.must_have:
                        reqs.must_have.append(line)

    def is_ready_to_generate(self, session: SocraticSession) -> bool:
        """Check if session is ready for workflow generation."""
        return session.state == SessionState.READY_TO_GENERATE or session.can_generate()

    def generate_workflow(
        self,
        session: SocraticSession,
    ) -> GeneratedWorkflow:
        """Generate workflow from the session.

        Args:
            session: Session with complete requirements

        Returns:
            Generated workflow ready for execution

        Raises:
            ValueError: If session not ready for generation
        """
        if not self.is_ready_to_generate(session):
            raise ValueError("Session not ready for generation. Answer more questions.")

        session.state = SessionState.GENERATING
        session.touch()

        # Build requirements dict for generator
        reqs = session.requirements
        requirements = {
            "quality_focus": list(reqs.quality_attributes.keys()),
            "languages": reqs.technical_constraints.get("languages", []),
            "automation_level": reqs.preferences.get("automation_level", "semi_auto"),
            "domain": session.goal_analysis.domain if session.goal_analysis else "general",
        }

        # Generate agents
        agents = self.generator.generate_agents_for_requirements(requirements)

        # Determine workflow name
        domain = session.goal_analysis.domain if session.goal_analysis else "general"
        name = self._generate_workflow_name(domain, requirements)

        # Generate success criteria
        success_criteria = self._generate_success_criteria(domain, requirements)

        # Create blueprint
        blueprint = self.generator.create_workflow_blueprint(
            name=name,
            description=session.goal or "Generated workflow",
            agents=agents,
            quality_focus=requirements["quality_focus"],
            automation_level=requirements["automation_level"],
            success_criteria=success_criteria,
        )

        blueprint.source_session_id = session.session_id
        blueprint.supported_languages = requirements["languages"]

        # Generate workflow
        workflow = self.generator.generate_workflow(blueprint)

        # Update session
        session.blueprint = blueprint
        session.workflow = workflow
        session.state = SessionState.COMPLETED
        session.touch()

        return workflow

    def _generate_workflow_name(
        self,
        domain: str,
        requirements: dict[str, Any],
    ) -> str:
        """Generate a descriptive workflow name."""
        domain_names = {
            "code_review": "Code Review",
            "security": "Security Audit",
            "testing": "Test Generation",
            "documentation": "Documentation",
            "performance": "Performance Analysis",
            "refactoring": "Refactoring",
            "general": "Code Analysis",
        }

        base_name = domain_names.get(domain, "Custom Workflow")

        # Add qualifier
        qualities = requirements.get("quality_focus", [])
        if qualities:
            qualifier = qualities[0].title()
            return f"{qualifier}-Focused {base_name}"

        return f"Automated {base_name}"

    def _generate_success_criteria(
        self,
        domain: str,
        requirements: dict[str, Any],
    ) -> SuccessCriteria:
        """Generate appropriate success criteria for the workflow."""
        # Use predefined criteria based on domain
        if domain == "code_review":
            return code_review_criteria()
        elif domain == "security":
            return security_audit_criteria()
        elif domain == "testing":
            return test_generation_criteria()
        else:
            # Generic criteria
            return SuccessCriteria(
                id=f"{domain}_success",
                name=f"{domain.title()} Success Criteria",
                metrics=[
                    SuccessMetric(
                        id="task_completed",
                        name="Task Completed",
                        metric_type=MetricType.BOOLEAN,
                        is_primary=True,
                        extraction_path="success",
                    ),
                    SuccessMetric(
                        id="findings_count",
                        name="Findings",
                        metric_type=MetricType.COUNT,
                        extraction_path="findings_count",
                    ),
                ],
                success_threshold=0.7,
            )

    def get_session_summary(self, session: SocraticSession) -> dict[str, Any]:
        """Get a summary of the session state for display."""
        return {
            "session_id": session.session_id,
            "state": session.state.value,
            "goal": session.goal,
            "domain": session.goal_analysis.domain if session.goal_analysis else None,
            "confidence": session.goal_analysis.confidence if session.goal_analysis else 0,
            "rounds_completed": session.current_round,
            "requirements_completeness": session.requirements.completeness_score(),
            "ready_to_generate": self.is_ready_to_generate(session),
            "ambiguities_remaining": len(session.goal_analysis.ambiguities) if session.goal_analysis else 0,
        }
