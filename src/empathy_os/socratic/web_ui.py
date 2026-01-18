"""Web UI Components for Socratic Workflow Builder

Provides components for rendering Socratic forms in web interfaces:
- React component schemas
- HTML template rendering
- API endpoint helpers
- WebSocket support for real-time sessions

Copyright 2026 Smart-AI-Memory
Licensed under Fair Source License 0.9
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any

from .forms import Form, FormField, FieldType, FieldOption
from .session import SocraticSession, SessionState
from .blueprint import WorkflowBlueprint


# =============================================================================
# REACT COMPONENT SCHEMAS
# =============================================================================


@dataclass
class ReactFormSchema:
    """Schema for rendering forms in React.

    Can be directly consumed by a React frontend to render
    the Socratic form with appropriate components.
    """

    form_id: str
    title: str
    description: str
    progress: float
    round_number: int
    is_final: bool
    fields: list[dict[str, Any]]
    categories: list[str]

    @classmethod
    def from_form(cls, form: Form) -> ReactFormSchema:
        """Create schema from a Form object."""
        fields = []

        for f in form.fields:
            field_schema = {
                "id": f.id,
                "type": _field_type_to_component(f.field_type),
                "label": f.label,
                "helpText": f.help_text,
                "placeholder": f.placeholder,
                "default": f.default,
                "category": f.category,
                "required": f.validation.required,
                "validation": {
                    "minLength": f.validation.min_length,
                    "maxLength": f.validation.max_length,
                    "minValue": f.validation.min_value,
                    "maxValue": f.validation.max_value,
                    "pattern": f.validation.pattern,
                },
                "showWhen": f.show_when,
                "options": [
                    {
                        "value": o.value,
                        "label": o.label,
                        "description": o.description,
                        "icon": o.icon,
                        "recommended": o.recommended,
                    }
                    for o in f.options
                ] if f.options else None,
            }
            fields.append(field_schema)

        return cls(
            form_id=form.id,
            title=form.title,
            description=form.description,
            progress=form.progress,
            round_number=form.round_number,
            is_final=form.is_final,
            fields=fields,
            categories=form.categories or list(dict.fromkeys(f.category for f in form.fields)),
        )

    def to_json(self) -> str:
        """Serialize to JSON for API response."""
        return json.dumps(asdict(self), indent=2)


def _field_type_to_component(field_type: FieldType) -> str:
    """Map FieldType to React component name."""
    mapping = {
        FieldType.SINGLE_SELECT: "RadioGroup",
        FieldType.MULTI_SELECT: "CheckboxGroup",
        FieldType.TEXT: "TextInput",
        FieldType.TEXT_AREA: "TextArea",
        FieldType.SLIDER: "Slider",
        FieldType.BOOLEAN: "Switch",
        FieldType.NUMBER: "NumberInput",
        FieldType.GROUP: "FieldGroup",
    }
    return mapping.get(field_type, "TextInput")


@dataclass
class ReactSessionSchema:
    """Schema for session state in React."""

    session_id: str
    state: str
    goal: str
    domain: str | None
    confidence: float
    current_round: int
    requirements_completeness: float
    ready_to_generate: bool
    ambiguities: list[str]
    assumptions: list[str]

    @classmethod
    def from_session(cls, session: SocraticSession) -> ReactSessionSchema:
        """Create schema from a SocraticSession."""
        return cls(
            session_id=session.session_id,
            state=session.state.value,
            goal=session.goal,
            domain=session.goal_analysis.domain if session.goal_analysis else None,
            confidence=session.goal_analysis.confidence if session.goal_analysis else 0,
            current_round=session.current_round,
            requirements_completeness=session.requirements.completeness_score(),
            ready_to_generate=session.can_generate(),
            ambiguities=session.goal_analysis.ambiguities if session.goal_analysis else [],
            assumptions=session.goal_analysis.assumptions if session.goal_analysis else [],
        )

    def to_json(self) -> str:
        """Serialize to JSON."""
        return json.dumps(asdict(self), indent=2)


@dataclass
class ReactBlueprintSchema:
    """Schema for blueprint display in React."""

    id: str
    name: str
    description: str
    domain: str
    languages: list[str]
    quality_focus: list[str]
    automation_level: str
    agents: list[dict[str, Any]]
    stages: list[dict[str, Any]]
    success_criteria: dict[str, Any] | None

    @classmethod
    def from_blueprint(cls, blueprint: WorkflowBlueprint) -> ReactBlueprintSchema:
        """Create schema from a WorkflowBlueprint."""
        agents = []
        for agent in blueprint.agents:
            agents.append({
                "id": agent.spec.id,
                "name": agent.spec.name,
                "role": agent.spec.role.value,
                "goal": agent.spec.goal,
                "backstory": agent.spec.backstory[:200] + "..." if len(agent.spec.backstory) > 200 else agent.spec.backstory,
                "modelTier": agent.spec.model_tier,
                "tools": [t.name for t in agent.spec.tools],
            })

        stages = []
        for stage in blueprint.stages:
            stages.append({
                "id": stage.id,
                "name": stage.name,
                "description": stage.description,
                "agents": stage.agent_ids,
                "parallel": stage.parallel,
                "dependsOn": stage.depends_on,
            })

        success_criteria = None
        if blueprint.success_criteria:
            success_criteria = blueprint.success_criteria.to_dict()

        return cls(
            id=blueprint.id,
            name=blueprint.name,
            description=blueprint.description,
            domain=blueprint.domain,
            languages=blueprint.supported_languages,
            quality_focus=blueprint.quality_focus,
            automation_level=blueprint.automation_level,
            agents=agents,
            stages=stages,
            success_criteria=success_criteria,
        )

    def to_json(self) -> str:
        """Serialize to JSON."""
        return json.dumps(asdict(self), indent=2)


# =============================================================================
# HTML TEMPLATE RENDERING
# =============================================================================


def render_form_html(form: Form, action_url: str = "/api/socratic/submit") -> str:
    """Render a form as HTML.

    Args:
        form: Form to render
        action_url: Form submission URL

    Returns:
        HTML string
    """
    html_parts = [
        f'<form id="{form.id}" action="{action_url}" method="POST" class="socratic-form">',
        f'  <div class="form-header">',
        f'    <h2>{_escape_html(form.title)}</h2>',
        f'    <p class="form-description">{_escape_html(form.description)}</p>',
        f'    <div class="progress-bar">',
        f'      <div class="progress-fill" style="width: {form.progress * 100}%"></div>',
        f'      <span class="progress-text">{form.progress:.0%}</span>',
        f'    </div>',
        f'  </div>',
        f'  <div class="form-fields">',
    ]

    # Group fields by category
    fields_by_category = form.get_fields_by_category()

    for category, fields in fields_by_category.items():
        if len(fields_by_category) > 1:
            html_parts.append(f'    <fieldset class="field-category" data-category="{category}">')
            html_parts.append(f'      <legend>{category.title()}</legend>')

        for field in fields:
            html_parts.append(_render_field_html(field))

        if len(fields_by_category) > 1:
            html_parts.append('    </fieldset>')

    html_parts.extend([
        '  </div>',
        '  <div class="form-actions">',
        '    <button type="submit" class="btn-primary">Continue</button>',
        '  </div>',
        '</form>',
    ])

    return "\n".join(html_parts)


def _render_field_html(field: FormField) -> str:
    """Render a single field as HTML."""
    required = 'required' if field.validation.required else ''
    required_indicator = '<span class="required">*</span>' if field.validation.required else ''

    # Show when data attribute
    show_when = ""
    if field.show_when:
        show_when = f' data-show-when=\'{json.dumps(field.show_when)}\''

    parts = [
        f'    <div class="form-field" data-field-id="{field.id}"{show_when}>',
        f'      <label for="{field.id}">{_escape_html(field.label)}{required_indicator}</label>',
    ]

    if field.help_text:
        parts.append(f'      <p class="help-text">{_escape_html(field.help_text)}</p>')

    # Render input based on type
    if field.field_type == FieldType.SINGLE_SELECT:
        parts.append(f'      <div class="radio-group">')
        for opt in field.options:
            rec_class = ' recommended' if opt.recommended else ''
            parts.append(f'        <label class="radio-option{rec_class}">')
            parts.append(f'          <input type="radio" name="{field.id}" value="{opt.value}" {required}>')
            parts.append(f'          <span class="option-label">{_escape_html(opt.label)}</span>')
            if opt.description:
                parts.append(f'          <span class="option-desc">{_escape_html(opt.description)}</span>')
            parts.append(f'        </label>')
        parts.append(f'      </div>')

    elif field.field_type == FieldType.MULTI_SELECT:
        parts.append(f'      <div class="checkbox-group">')
        for opt in field.options:
            rec_class = ' recommended' if opt.recommended else ''
            parts.append(f'        <label class="checkbox-option{rec_class}">')
            parts.append(f'          <input type="checkbox" name="{field.id}" value="{opt.value}">')
            parts.append(f'          <span class="option-label">{_escape_html(opt.label)}</span>')
            if opt.description:
                parts.append(f'          <span class="option-desc">{_escape_html(opt.description)}</span>')
            parts.append(f'        </label>')
        parts.append(f'      </div>')

    elif field.field_type == FieldType.TEXT_AREA:
        max_len = f' maxlength="{field.validation.max_length}"' if field.validation.max_length else ''
        parts.append(f'      <textarea id="{field.id}" name="{field.id}" placeholder="{_escape_html(field.placeholder)}"{max_len} {required}></textarea>')

    elif field.field_type == FieldType.BOOLEAN:
        parts.append(f'      <div class="switch-container">')
        parts.append(f'        <label class="switch">')
        parts.append(f'          <input type="checkbox" id="{field.id}" name="{field.id}" value="true">')
        parts.append(f'          <span class="slider"></span>')
        parts.append(f'        </label>')
        parts.append(f'      </div>')

    elif field.field_type == FieldType.SLIDER:
        min_val = field.validation.min_value or 0
        max_val = field.validation.max_value or 100
        parts.append(f'      <div class="slider-container">')
        parts.append(f'        <input type="range" id="{field.id}" name="{field.id}" min="{min_val}" max="{max_val}">')
        parts.append(f'        <output for="{field.id}"></output>')
        parts.append(f'      </div>')

    else:  # TEXT, NUMBER
        input_type = "number" if field.field_type == FieldType.NUMBER else "text"
        max_len = f' maxlength="{field.validation.max_length}"' if field.validation.max_length else ''
        parts.append(f'      <input type="{input_type}" id="{field.id}" name="{field.id}" placeholder="{_escape_html(field.placeholder)}"{max_len} {required}>')

    parts.append('    </div>')

    return "\n".join(parts)


def _escape_html(text: str) -> str:
    """Escape HTML special characters."""
    return (text
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#x27;"))


# =============================================================================
# CSS STYLES
# =============================================================================


FORM_CSS = """
/* Socratic Form Styles */

.socratic-form {
  max-width: 800px;
  margin: 0 auto;
  padding: 2rem;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}

.form-header {
  margin-bottom: 2rem;
}

.form-header h2 {
  margin: 0 0 0.5rem 0;
  font-size: 1.75rem;
  color: #1a1a2e;
}

.form-description {
  color: #666;
  margin: 0 0 1rem 0;
}

.progress-bar {
  background: #e0e0e0;
  border-radius: 10px;
  height: 20px;
  position: relative;
  overflow: hidden;
}

.progress-fill {
  background: linear-gradient(90deg, #4CAF50, #8BC34A);
  height: 100%;
  border-radius: 10px;
  transition: width 0.3s ease;
}

.progress-text {
  position: absolute;
  right: 10px;
  top: 50%;
  transform: translateY(-50%);
  font-size: 0.75rem;
  font-weight: 600;
  color: #333;
}

.form-fields {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.form-field {
  background: #f8f9fa;
  padding: 1.25rem;
  border-radius: 8px;
  border: 1px solid #e0e0e0;
}

.form-field label {
  display: block;
  font-weight: 600;
  margin-bottom: 0.5rem;
  color: #1a1a2e;
}

.form-field .required {
  color: #e53935;
  margin-left: 0.25rem;
}

.help-text {
  font-size: 0.875rem;
  color: #666;
  margin: 0 0 0.75rem 0;
}

/* Text inputs */
input[type="text"],
input[type="number"],
textarea {
  width: 100%;
  padding: 0.75rem;
  border: 1px solid #ccc;
  border-radius: 6px;
  font-size: 1rem;
  transition: border-color 0.2s, box-shadow 0.2s;
}

input[type="text"]:focus,
input[type="number"]:focus,
textarea:focus {
  outline: none;
  border-color: #4CAF50;
  box-shadow: 0 0 0 3px rgba(76, 175, 80, 0.1);
}

textarea {
  min-height: 100px;
  resize: vertical;
}

/* Radio and checkbox groups */
.radio-group,
.checkbox-group {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.radio-option,
.checkbox-option {
  display: flex;
  align-items: flex-start;
  gap: 0.75rem;
  padding: 0.75rem;
  background: white;
  border: 1px solid #e0e0e0;
  border-radius: 6px;
  cursor: pointer;
  transition: border-color 0.2s, background 0.2s;
}

.radio-option:hover,
.checkbox-option:hover {
  border-color: #4CAF50;
  background: #f0f7f0;
}

.radio-option.recommended,
.checkbox-option.recommended {
  border-color: #4CAF50;
}

.radio-option input,
.checkbox-option input {
  margin-top: 0.25rem;
}

.option-label {
  font-weight: 500;
  color: #1a1a2e;
}

.option-desc {
  display: block;
  font-size: 0.875rem;
  color: #666;
  margin-top: 0.25rem;
}

/* Switch/toggle */
.switch-container {
  display: flex;
  align-items: center;
}

.switch {
  position: relative;
  width: 50px;
  height: 28px;
}

.switch input {
  opacity: 0;
  width: 0;
  height: 0;
}

.switch .slider {
  position: absolute;
  cursor: pointer;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: #ccc;
  border-radius: 28px;
  transition: 0.3s;
}

.switch .slider:before {
  position: absolute;
  content: "";
  height: 22px;
  width: 22px;
  left: 3px;
  bottom: 3px;
  background-color: white;
  border-radius: 50%;
  transition: 0.3s;
}

.switch input:checked + .slider {
  background-color: #4CAF50;
}

.switch input:checked + .slider:before {
  transform: translateX(22px);
}

/* Slider/range */
.slider-container {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.slider-container input[type="range"] {
  flex: 1;
  height: 6px;
  -webkit-appearance: none;
  background: #e0e0e0;
  border-radius: 3px;
}

.slider-container input[type="range"]::-webkit-slider-thumb {
  -webkit-appearance: none;
  width: 20px;
  height: 20px;
  background: #4CAF50;
  border-radius: 50%;
  cursor: pointer;
}

/* Category fieldsets */
.field-category {
  border: none;
  padding: 0;
  margin: 0;
}

.field-category legend {
  font-size: 1.25rem;
  font-weight: 600;
  color: #1a1a2e;
  padding: 0;
  margin-bottom: 1rem;
}

/* Form actions */
.form-actions {
  margin-top: 2rem;
  display: flex;
  justify-content: flex-end;
  gap: 1rem;
}

.btn-primary {
  background: linear-gradient(90deg, #4CAF50, #45a049);
  color: white;
  border: none;
  padding: 0.875rem 2rem;
  font-size: 1rem;
  font-weight: 600;
  border-radius: 6px;
  cursor: pointer;
  transition: transform 0.2s, box-shadow 0.2s;
}

.btn-primary:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(76, 175, 80, 0.3);
}

.btn-primary:active {
  transform: translateY(0);
}

/* Conditional field visibility */
.form-field[data-show-when] {
  display: none;
}

.form-field[data-show-when].visible {
  display: block;
}
"""


# =============================================================================
# JAVASCRIPT FOR FORM INTERACTIVITY
# =============================================================================


FORM_JS = """
// Socratic Form Interactivity

class SocraticForm {
  constructor(formElement) {
    this.form = formElement;
    this.fields = {};
    this.init();
  }

  init() {
    // Index all fields
    this.form.querySelectorAll('.form-field').forEach(field => {
      const fieldId = field.dataset.fieldId;
      this.fields[fieldId] = {
        element: field,
        showWhen: field.dataset.showWhen ? JSON.parse(field.dataset.showWhen) : null,
      };
    });

    // Add change listeners
    this.form.addEventListener('change', (e) => this.handleChange(e));

    // Initial visibility check
    this.updateVisibility();

    // Slider output sync
    this.form.querySelectorAll('input[type="range"]').forEach(slider => {
      const output = slider.nextElementSibling;
      if (output && output.tagName === 'OUTPUT') {
        output.textContent = slider.value;
        slider.addEventListener('input', () => {
          output.textContent = slider.value;
        });
      }
    });
  }

  handleChange(event) {
    this.updateVisibility();
  }

  getValues() {
    const values = {};
    const formData = new FormData(this.form);

    for (const [key, value] of formData.entries()) {
      if (values[key]) {
        // Multi-select: convert to array
        if (!Array.isArray(values[key])) {
          values[key] = [values[key]];
        }
        values[key].push(value);
      } else {
        values[key] = value;
      }
    }

    return values;
  }

  updateVisibility() {
    const values = this.getValues();

    Object.entries(this.fields).forEach(([fieldId, field]) => {
      if (!field.showWhen) {
        field.element.classList.add('visible');
        return;
      }

      const shouldShow = this.evaluateCondition(field.showWhen, values);
      field.element.classList.toggle('visible', shouldShow);

      // Disable hidden inputs to exclude from submission
      const inputs = field.element.querySelectorAll('input, textarea, select');
      inputs.forEach(input => {
        input.disabled = !shouldShow;
      });
    });
  }

  evaluateCondition(condition, values) {
    for (const [fieldId, expected] of Object.entries(condition)) {
      const actual = values[fieldId];

      if (Array.isArray(expected)) {
        // Any of condition
        if (Array.isArray(actual)) {
          if (!actual.some(v => expected.includes(v))) return false;
        } else {
          if (!expected.includes(actual)) return false;
        }
      } else {
        // Exact match
        if (Array.isArray(actual)) {
          if (!actual.includes(expected)) return false;
        } else {
          if (actual !== expected) return false;
        }
      }
    }
    return true;
  }
}

// Auto-initialize forms
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.socratic-form').forEach(form => {
    new SocraticForm(form);
  });
});

// Async form submission
async function submitSocraticForm(form, url) {
  const socraticForm = form._socraticForm || new SocraticForm(form);
  const values = socraticForm.getValues();

  try {
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(values),
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    return await response.json();
  } catch (error) {
    console.error('Form submission failed:', error);
    throw error;
  }
}
"""


# =============================================================================
# API HELPERS
# =============================================================================


@dataclass
class APIResponse:
    """Standard API response format."""

    success: bool
    data: dict[str, Any] | None = None
    error: str | None = None
    next_action: str | None = None  # "continue", "generate", "complete"

    def to_json(self) -> str:
        """Serialize to JSON."""
        return json.dumps(asdict(self), indent=2)


def create_form_response(
    session: SocraticSession,
    form: Form | None,
    builder: Any,  # SocraticWorkflowBuilder
) -> APIResponse:
    """Create API response for form request.

    Args:
        session: Current session
        form: Form to display (or None if ready to generate)
        builder: SocraticWorkflowBuilder instance

    Returns:
        APIResponse with form data or generation prompt
    """
    session_schema = ReactSessionSchema.from_session(session)

    if form:
        form_schema = ReactFormSchema.from_form(form)
        return APIResponse(
            success=True,
            data={
                "session": asdict(session_schema),
                "form": asdict(form_schema),
            },
            next_action="continue",
        )
    elif builder.is_ready_to_generate(session):
        return APIResponse(
            success=True,
            data={
                "session": asdict(session_schema),
                "message": "Ready to generate workflow",
            },
            next_action="generate",
        )
    else:
        return APIResponse(
            success=False,
            error="Unable to determine next step",
        )


def create_blueprint_response(
    blueprint: WorkflowBlueprint,
    session: SocraticSession,
) -> APIResponse:
    """Create API response for generated blueprint.

    Args:
        blueprint: Generated blueprint
        session: Source session

    Returns:
        APIResponse with blueprint data
    """
    blueprint_schema = ReactBlueprintSchema.from_blueprint(blueprint)
    session_schema = ReactSessionSchema.from_session(session)

    return APIResponse(
        success=True,
        data={
            "session": asdict(session_schema),
            "blueprint": asdict(blueprint_schema),
        },
        next_action="complete",
    )


# =============================================================================
# EXPORT FUNCTIONS
# =============================================================================


def get_form_assets() -> dict[str, str]:
    """Get CSS and JS assets for forms.

    Returns:
        Dictionary with 'css' and 'js' keys
    """
    return {
        "css": FORM_CSS,
        "js": FORM_JS,
    }


def render_complete_page(form: Form, session: SocraticSession) -> str:
    """Render a complete HTML page with form.

    Args:
        form: Form to render
        session: Current session

    Returns:
        Complete HTML page
    """
    form_html = render_form_html(form)
    session_data = ReactSessionSchema.from_session(session)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Socratic Workflow Builder</title>
    <style>
{FORM_CSS}
    </style>
</head>
<body>
    <div class="container">
        <div class="session-info">
            <span class="domain-badge">{session_data.domain or 'General'}</span>
            <span class="confidence">Confidence: {session_data.confidence:.0%}</span>
        </div>

        {form_html}
    </div>

    <script>
{FORM_JS}

// Session data for client-side use
window.socraticSession = {session_data.to_json()};
    </script>
</body>
</html>"""
