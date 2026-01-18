"""Socratic Forms System

Structured questionnaires with branching logic for gathering requirements.

Supports multiple field types:
- Single select (radio buttons)
- Multi-select (checkboxes)
- Text input (short answer)
- Text area (long form)
- Slider (numeric range)
- Conditional fields (appear based on previous answers)

Copyright 2026 Smart-AI-Memory
Licensed under Fair Source License 0.9
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable


class FieldType(Enum):
    """Types of form fields."""

    # Single selection from options
    SINGLE_SELECT = "single_select"

    # Multiple selection from options
    MULTI_SELECT = "multi_select"

    # Short text input
    TEXT = "text"

    # Long text input
    TEXT_AREA = "text_area"

    # Numeric slider with range
    SLIDER = "slider"

    # Yes/No toggle
    BOOLEAN = "boolean"

    # Numeric input
    NUMBER = "number"

    # Grouped fields (sub-form)
    GROUP = "group"


@dataclass
class FieldOption:
    """An option for select-type fields."""

    # Option value (stored in response)
    value: str

    # Display label
    label: str

    # Optional description/help text
    description: str = ""

    # Optional icon or emoji
    icon: str = ""

    # Whether this is the recommended option
    recommended: bool = False

    # Conditions that enable/disable this option
    enabled_when: dict[str, Any] | None = None


@dataclass
class FieldValidation:
    """Validation rules for a field."""

    # Whether field is required
    required: bool = False

    # Minimum length (for text fields)
    min_length: int | None = None

    # Maximum length (for text fields)
    max_length: int | None = None

    # Minimum value (for numeric fields)
    min_value: float | None = None

    # Maximum value (for numeric fields)
    max_value: float | None = None

    # Regex pattern (for text fields)
    pattern: str | None = None

    # Custom validation function
    custom_validator: Callable[[Any], tuple[bool, str]] | None = None

    # Error message template
    error_message: str = "Invalid value"


@dataclass
class FormField:
    """A single field in a Socratic form.

    Example:
        >>> field = FormField(
        ...     id="languages",
        ...     field_type=FieldType.MULTI_SELECT,
        ...     label="What programming languages does your team use?",
        ...     help_text="Select all that apply",
        ...     options=[
        ...         FieldOption("python", "Python", recommended=True),
        ...         FieldOption("typescript", "TypeScript"),
        ...         FieldOption("javascript", "JavaScript"),
        ...         FieldOption("go", "Go"),
        ...         FieldOption("rust", "Rust"),
        ...     ],
        ...     validation=FieldValidation(required=True)
        ... )
    """

    # Unique field identifier
    id: str

    # Type of field
    field_type: FieldType

    # Display label (the question)
    label: str

    # Help text explaining the question
    help_text: str = ""

    # Placeholder text for input fields
    placeholder: str = ""

    # Options for select fields
    options: list[FieldOption] = field(default_factory=list)

    # Default value
    default: Any = None

    # Validation rules
    validation: FieldValidation = field(default_factory=FieldValidation)

    # Conditions for showing this field (based on other answers)
    show_when: dict[str, Any] | None = None

    # Category/section this field belongs to
    category: str = "general"

    # Order within category
    order: int = 0

    # Additional metadata
    metadata: dict[str, Any] = field(default_factory=dict)

    def validate(self, value: Any) -> tuple[bool, str]:
        """Validate a value for this field.

        Args:
            value: The value to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        v = self.validation

        # Check required
        if v.required:
            if value is None:
                return False, f"{self.label} is required"
            if isinstance(value, str) and not value.strip():
                return False, f"{self.label} is required"
            if isinstance(value, list) and not value:
                return False, f"Please select at least one option for {self.label}"

        # Skip further validation if empty and not required
        if value is None or (isinstance(value, str) and not value.strip()):
            return True, ""

        # Check string length
        if isinstance(value, str):
            if v.min_length and len(value) < v.min_length:
                return False, f"Minimum {v.min_length} characters required"
            if v.max_length and len(value) > v.max_length:
                return False, f"Maximum {v.max_length} characters allowed"

        # Check numeric range
        if isinstance(value, (int, float)):
            if v.min_value is not None and value < v.min_value:
                return False, f"Value must be at least {v.min_value}"
            if v.max_value is not None and value > v.max_value:
                return False, f"Value must be at most {v.max_value}"

        # Check pattern
        if v.pattern and isinstance(value, str):
            import re
            if not re.match(v.pattern, value):
                return False, v.error_message

        # Custom validation
        if v.custom_validator:
            return v.custom_validator(value)

        return True, ""

    def should_show(self, current_answers: dict[str, Any]) -> bool:
        """Check if this field should be shown based on current answers.

        Args:
            current_answers: Dictionary of field_id -> value

        Returns:
            True if field should be shown
        """
        if self.show_when is None:
            return True

        for field_id, expected in self.show_when.items():
            actual = current_answers.get(field_id)

            # Handle "any of" conditions (list of acceptable values)
            if isinstance(expected, list):
                if actual not in expected:
                    # Also check if actual is a list (multi-select)
                    if isinstance(actual, list):
                        if not any(v in expected for v in actual):
                            return False
                    else:
                        return False
            # Handle exact match
            elif actual != expected:
                return False

        return True


@dataclass
class Form:
    """A Socratic questionnaire form.

    Example:
        >>> form = Form(
        ...     id="code_review_setup",
        ...     title="Code Review Configuration",
        ...     description="Help us understand your code review needs",
        ...     fields=[
        ...         FormField(
        ...             id="languages",
        ...             field_type=FieldType.MULTI_SELECT,
        ...             label="What languages?",
        ...             options=[...]
        ...         ),
        ...         FormField(
        ...             id="team_size",
        ...             field_type=FieldType.SLIDER,
        ...             label="How large is your team?",
        ...             validation=FieldValidation(min_value=1, max_value=100)
        ...         ),
        ...     ]
        ... )
    """

    # Unique form identifier
    id: str

    # Form title
    title: str

    # Form description/instructions
    description: str = ""

    # Fields in this form
    fields: list[FormField] = field(default_factory=list)

    # Round number (for multi-round questioning)
    round_number: int = 1

    # Progress indicator (0-1)
    progress: float = 0.0

    # Whether this is the final form
    is_final: bool = False

    # Category groupings for display
    categories: list[str] = field(default_factory=list)

    def get_visible_fields(self, current_answers: dict[str, Any]) -> list[FormField]:
        """Get fields that should be visible based on current answers.

        Args:
            current_answers: Dictionary of answered field values

        Returns:
            List of visible FormField objects
        """
        return [f for f in self.fields if f.should_show(current_answers)]

    def get_fields_by_category(
        self,
        current_answers: dict[str, Any] | None = None,
    ) -> dict[str, list[FormField]]:
        """Get fields grouped by category.

        Args:
            current_answers: Optional answers for visibility filtering

        Returns:
            Dictionary mapping category name to list of fields
        """
        current_answers = current_answers or {}
        result: dict[str, list[FormField]] = {}

        for f in self.fields:
            if f.should_show(current_answers):
                if f.category not in result:
                    result[f.category] = []
                result[f.category].append(f)

        # Sort fields within each category
        for category in result:
            result[category].sort(key=lambda x: x.order)

        return result

    def to_dict(self) -> dict[str, Any]:
        """Serialize form to dictionary for JSON/API response."""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "round_number": self.round_number,
            "progress": self.progress,
            "is_final": self.is_final,
            "categories": self.categories,
            "fields": [
                {
                    "id": f.id,
                    "type": f.field_type.value,
                    "label": f.label,
                    "help_text": f.help_text,
                    "placeholder": f.placeholder,
                    "default": f.default,
                    "category": f.category,
                    "options": [
                        {
                            "value": o.value,
                            "label": o.label,
                            "description": o.description,
                            "icon": o.icon,
                            "recommended": o.recommended,
                        }
                        for o in f.options
                    ] if f.options else [],
                    "validation": {
                        "required": f.validation.required,
                        "min_length": f.validation.min_length,
                        "max_length": f.validation.max_length,
                        "min_value": f.validation.min_value,
                        "max_value": f.validation.max_value,
                        "pattern": f.validation.pattern,
                    },
                    "show_when": f.show_when,
                }
                for f in self.fields
            ],
        }


@dataclass
class ValidationResult:
    """Result of validating a form response."""

    # Whether validation passed
    is_valid: bool

    # Field-level errors (field_id -> error message)
    field_errors: dict[str, str] = field(default_factory=dict)

    # Form-level errors
    form_errors: list[str] = field(default_factory=list)

    @property
    def all_errors(self) -> list[str]:
        """Get all errors as a flat list."""
        errors = list(self.form_errors)
        errors.extend(f"{k}: {v}" for k, v in self.field_errors.items())
        return errors


@dataclass
class FormResponse:
    """A user's response to a form.

    Example:
        >>> response = FormResponse(
        ...     form_id="code_review_setup",
        ...     answers={
        ...         "languages": ["python", "typescript"],
        ...         "team_size": 8,
        ...         "focus_areas": ["security", "performance"]
        ...     }
        ... )
    """

    # ID of the form being responded to
    form_id: str

    # Answers keyed by field ID
    answers: dict[str, Any] = field(default_factory=dict)

    # When the response was submitted
    submitted_at: str = ""

    # Whether the user skipped optional questions
    skipped_fields: list[str] = field(default_factory=list)

    # Additional notes from user
    notes: str = ""

    def validate(self, form: Form) -> ValidationResult:
        """Validate this response against a form.

        Args:
            form: The Form to validate against

        Returns:
            ValidationResult with any errors
        """
        result = ValidationResult(is_valid=True)

        # Get visible fields based on current answers
        visible_fields = form.get_visible_fields(self.answers)

        for f in visible_fields:
            value = self.answers.get(f.id)
            is_valid, error = f.validate(value)

            if not is_valid:
                result.is_valid = False
                result.field_errors[f.id] = error

        return result


# =============================================================================
# FORM BUILDER HELPERS
# =============================================================================


def create_language_field(
    id: str = "languages",
    required: bool = True,
) -> FormField:
    """Create a standard programming language selection field."""
    return FormField(
        id=id,
        field_type=FieldType.MULTI_SELECT,
        label="What programming languages does your team primarily use?",
        help_text="Select all that apply. This helps us customize analysis tools.",
        options=[
            FieldOption("python", "Python", icon="🐍", recommended=True),
            FieldOption("typescript", "TypeScript", icon="📘"),
            FieldOption("javascript", "JavaScript", icon="📒"),
            FieldOption("java", "Java", icon="☕"),
            FieldOption("go", "Go", icon="🐹"),
            FieldOption("rust", "Rust", icon="🦀"),
            FieldOption("csharp", "C#", icon="🎯"),
            FieldOption("cpp", "C++", icon="⚡"),
            FieldOption("ruby", "Ruby", icon="💎"),
            FieldOption("php", "PHP", icon="🐘"),
            FieldOption("other", "Other", icon="🔧"),
        ],
        validation=FieldValidation(required=required),
        category="technical",
    )


def create_quality_focus_field(
    id: str = "quality_focus",
    required: bool = True,
) -> FormField:
    """Create a quality focus area selection field."""
    return FormField(
        id=id,
        field_type=FieldType.MULTI_SELECT,
        label="What quality attributes are most important?",
        help_text="Select your top priorities. We'll optimize agents for these.",
        options=[
            FieldOption(
                "security",
                "Security",
                description="Vulnerability detection, secure coding practices",
                icon="🔒",
            ),
            FieldOption(
                "performance",
                "Performance",
                description="Speed, memory usage, scalability",
                icon="⚡",
            ),
            FieldOption(
                "maintainability",
                "Maintainability",
                description="Code clarity, documentation, modularity",
                icon="🧩",
            ),
            FieldOption(
                "reliability",
                "Reliability",
                description="Error handling, edge cases, stability",
                icon="🛡️",
            ),
            FieldOption(
                "testability",
                "Testability",
                description="Test coverage, test quality, mocking",
                icon="🧪",
            ),
        ],
        validation=FieldValidation(required=required),
        category="quality",
    )


def create_team_size_field(
    id: str = "team_size",
    required: bool = False,
) -> FormField:
    """Create a team size input field."""
    return FormField(
        id=id,
        field_type=FieldType.SINGLE_SELECT,
        label="How large is your development team?",
        help_text="This helps us calibrate review thoroughness.",
        options=[
            FieldOption("solo", "Solo developer", description="Just me"),
            FieldOption("small", "Small team (2-5)", description="Close collaboration"),
            FieldOption("medium", "Medium team (6-15)", description="Multiple reviewers"),
            FieldOption("large", "Large team (16+)", description="Formal review process"),
        ],
        validation=FieldValidation(required=required),
        category="context",
    )


def create_automation_level_field(
    id: str = "automation_level",
    required: bool = True,
) -> FormField:
    """Create an automation preference field."""
    return FormField(
        id=id,
        field_type=FieldType.SINGLE_SELECT,
        label="How much automation do you want?",
        help_text="Higher automation means less human intervention required.",
        options=[
            FieldOption(
                "advisory",
                "Advisory Only",
                description="Suggestions for humans to review and apply",
                icon="💡",
            ),
            FieldOption(
                "semi_auto",
                "Semi-Automated",
                description="Auto-fix simple issues, flag complex ones",
                icon="⚙️",
                recommended=True,
            ),
            FieldOption(
                "fully_auto",
                "Fully Automated",
                description="Auto-fix everything possible, minimal human review",
                icon="🤖",
            ),
        ],
        validation=FieldValidation(required=required),
        category="preferences",
    )


def create_goal_text_field(
    id: str = "goal",
    required: bool = True,
) -> FormField:
    """Create the initial goal capture field."""
    return FormField(
        id=id,
        field_type=FieldType.TEXT_AREA,
        label="What do you want to accomplish?",
        help_text=(
            "Describe your goal in your own words. Be as specific as you like - "
            "we'll ask clarifying questions if needed."
        ),
        placeholder="e.g., I want to automate code reviews to catch security issues...",
        validation=FieldValidation(
            required=required,
            min_length=10,
            max_length=2000,
        ),
        category="goal",
    )


def create_additional_context_field(
    id: str = "additional_context",
    required: bool = False,
) -> FormField:
    """Create an optional additional context field."""
    return FormField(
        id=id,
        field_type=FieldType.TEXT_AREA,
        label="Anything else we should know?",
        help_text="Optional: Share any additional context, constraints, or preferences.",
        placeholder="e.g., We use a monorepo, have strict SLAs, prefer verbose output...",
        validation=FieldValidation(max_length=1000),
        category="context",
    )
