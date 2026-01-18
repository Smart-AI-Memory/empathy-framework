"""Tests for the Socratic forms module.

Copyright 2026 Smart-AI-Memory
Licensed under Fair Source License 0.9
"""

import pytest


class TestFormField:
    """Tests for FormField class."""

    def test_create_text_field(self):
        """Test creating a text field."""
        from empathy_os.socratic.forms import FormField, FieldType

        field = FormField(
            field_id="name",
            field_type=FieldType.TEXT,
            label="Your Name",
            required=True,
        )

        assert field.field_id == "name"
        assert field.field_type == FieldType.TEXT
        assert field.required is True

    def test_create_select_field_with_options(self):
        """Test creating a select field with options."""
        from empathy_os.socratic.forms import FormField, FieldType, FieldOption

        field = FormField(
            field_id="language",
            field_type=FieldType.SINGLE_SELECT,
            label="Programming Language",
            options=[
                FieldOption(value="python", label="Python"),
                FieldOption(value="javascript", label="JavaScript"),
            ],
        )

        assert len(field.options) == 2
        assert field.options[0].value == "python"

    def test_field_with_validation(self):
        """Test field with validation rules."""
        from empathy_os.socratic.forms import FormField, FieldType, FieldValidation

        field = FormField(
            field_id="email",
            field_type=FieldType.TEXT,
            label="Email",
            validation=FieldValidation(
                required=True,
                min_length=5,
                pattern=r"^[\w.-]+@[\w.-]+\.\w+$",
            ),
        )

        assert field.validation.required is True
        assert field.validation.min_length == 5

    def test_field_with_show_when(self):
        """Test conditional field visibility."""
        from empathy_os.socratic.forms import FormField, FieldType, ShowWhen

        field = FormField(
            field_id="security_level",
            field_type=FieldType.SINGLE_SELECT,
            label="Security Level",
            show_when=ShowWhen(
                field_id="enable_security",
                operator="equals",
                value=True,
            ),
        )

        assert field.show_when is not None
        assert field.show_when.field_id == "enable_security"


class TestForm:
    """Tests for Form class."""

    def test_create_form(self, sample_form):
        """Test creating a form."""
        assert sample_form.form_id == "test-form-001"
        assert len(sample_form.fields) == 3
        assert sample_form.round_number == 1

    def test_form_serialization(self, sample_form):
        """Test form serialization to dict."""
        from empathy_os.socratic.forms import Form

        data = sample_form.to_dict()

        assert data["form_id"] == sample_form.form_id
        assert data["title"] == sample_form.title
        assert len(data["fields"]) == 3

    def test_form_deserialization(self, sample_form):
        """Test form deserialization from dict."""
        from empathy_os.socratic.forms import Form

        data = sample_form.to_dict()
        restored = Form.from_dict(data)

        assert restored.form_id == sample_form.form_id
        assert len(restored.fields) == len(sample_form.fields)


class TestFormResponse:
    """Tests for FormResponse class."""

    def test_create_form_response(self, sample_form):
        """Test creating a form response."""
        from empathy_os.socratic.forms import FormResponse

        response = FormResponse(
            form_id=sample_form.form_id,
            answers={
                "languages": ["python", "javascript"],
                "quality_focus": ["security"],
                "notes": "Focus on API endpoints",
            },
        )

        assert response.form_id == sample_form.form_id
        assert len(response.answers) == 3


class TestValidationResult:
    """Tests for ValidationResult class."""

    def test_valid_result(self):
        """Test valid validation result."""
        from empathy_os.socratic.forms import ValidationResult

        result = ValidationResult(is_valid=True)

        assert result.is_valid is True
        assert result.errors == []

    def test_invalid_result_with_errors(self):
        """Test invalid validation result with errors."""
        from empathy_os.socratic.forms import ValidationResult

        result = ValidationResult(
            is_valid=False,
            errors=["Field 'name' is required", "Invalid email format"],
        )

        assert result.is_valid is False
        assert len(result.errors) == 2


class TestFieldType:
    """Tests for FieldType enum."""

    def test_all_field_types(self):
        """Test all field types exist."""
        from empathy_os.socratic.forms import FieldType

        assert FieldType.TEXT.value == "text"
        assert FieldType.TEXT_AREA.value == "text_area"
        assert FieldType.SINGLE_SELECT.value == "single_select"
        assert FieldType.MULTI_SELECT.value == "multi_select"
        assert FieldType.BOOLEAN.value == "boolean"
        assert FieldType.NUMBER.value == "number"
        assert FieldType.SLIDER.value == "slider"
