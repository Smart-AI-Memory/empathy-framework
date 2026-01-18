# Socratic Workflow Builder Skill

Use this skill when helping users create agent workflows through guided questioning.

## Overview

The Socratic Agent Generation System (`src/empathy_os/socratic/`) creates optimized multi-agent workflows by:
1. Understanding user goals through free-form input
2. Asking targeted clarifying questions
3. Generating agent blueprints and workflow specifications
4. Defining measurable success criteria

## Core Components

### Session Management (`session.py`)
```python
from empathy_os.socratic import SocraticSession, SessionState

# States: AWAITING_GOAL → ANALYZING_GOAL → AWAITING_ANSWERS → READY_TO_GENERATE → COMPLETED
session = SocraticSession(session_id="unique-id")
session.set_goal("I want to automate security reviews")
```

### Form System (`forms.py`)
```python
from empathy_os.socratic import Form, FormField, FieldType

# Field types: SINGLE_SELECT, MULTI_SELECT, TEXT, TEXT_AREA, SLIDER, BOOLEAN, NUMBER, GROUP
field = FormField(
    field_id="languages",
    field_type=FieldType.MULTI_SELECT,
    label="Programming Languages",
    options=["Python", "TypeScript", "Go", "Rust"],
    required=True
)
```

### Blueprint Generation (`blueprint.py`, `generator.py`)
```python
from empathy_os.socratic import AgentBlueprint, AgentGenerator

generator = AgentGenerator()
agents = generator.generate_agents_for_requirements(requirements)
# Returns: security_reviewer, code_quality_reviewer, test_generator, etc.
```

### Success Metrics (`success.py`)
```python
from empathy_os.socratic import SuccessCriteria, SuccessMetric, MetricType

metric = SuccessMetric(
    metric_id="vulnerabilities_found",
    name="Security Issues Detected",
    description="Number of security vulnerabilities identified",
    metric_type=MetricType.COUNT,
    target_value=0,  # Goal: zero vulnerabilities
    direction=MetricDirection.LOWER_IS_BETTER
)
```

## LLM-Powered Analysis

### Goal Analysis (`llm_analyzer.py`)
```python
from empathy_os.socratic import LLMGoalAnalyzer

analyzer = LLMGoalAnalyzer(api_key=os.environ.get("ANTHROPIC_API_KEY"))
result = await analyzer.analyze_goal("I want to automate code reviews")
# Returns: domains, requirements, ambiguities, suggested_agents
```

### Adaptive Recommendations (`feedback.py`)
```python
from empathy_os.socratic import FeedbackLoop, AdaptiveAgentGenerator

feedback_loop = FeedbackLoop(storage)
adaptive_gen = AdaptiveAgentGenerator(feedback_loop.collector)

# Recommendations improve based on historical success rates
recommendations = adaptive_gen.recommend_agents(context)
```

## Domain Detection Keywords

| Domain | Keywords |
|--------|----------|
| code_review | review, quality, lint, style, clean |
| security | security, vulnerability, audit, penetration, CVE |
| testing | test, coverage, unit, integration, e2e |
| documentation | document, readme, api docs, comment |
| performance | performance, optimize, speed, memory, profile |
| refactoring | refactor, restructure, modernize, migrate |

## Agent Templates

Available agent templates in `generator.py`:

1. **security_reviewer** - Scans for vulnerabilities (OWASP, CVE patterns)
2. **code_quality_reviewer** - Checks style, complexity, maintainability
3. **performance_analyzer** - Profiles and identifies bottlenecks
4. **test_generator** - Creates unit/integration tests
5. **documentation_writer** - Generates docs from code
6. **style_enforcer** - Ensures coding standards compliance
7. **result_synthesizer** - Aggregates multi-agent outputs

## Tool Registry

Available tools for agents:

| Tool | Category | Purpose |
|------|----------|---------|
| grep_code | CODE_ANALYSIS | Search code patterns |
| read_file | CODE_ANALYSIS | Read file contents |
| analyze_ast | CODE_ANALYSIS | Parse and analyze AST |
| security_scan | SECURITY | Run security scanners |
| run_linter | CODE_ANALYSIS | Execute linters |
| run_tests | TESTING | Execute test suite |
| edit_file | MODIFICATION | Modify files |
| write_file | MODIFICATION | Create files |

## Workflow Generation Flow

```
User Goal → LLM Analysis → Domain Detection → Question Generation
    ↓
Form Presentation → Answer Collection → Requirement Refinement
    ↓
Agent Selection → Blueprint Creation → Workflow Assembly
    ↓
Success Criteria → Execution Plan → Ready for Run
```

## Storage Locations

- Sessions: `.empathy/socratic/sessions/{session_id}.json`
- Blueprints: `.empathy/socratic/blueprints/{blueprint_id}.json`
- Feedback: `.empathy/socratic/feedback.db` (SQLite)

## CLI Commands

```bash
# Start new session
python -m empathy_os.socratic.cli start

# Resume session
python -m empathy_os.socratic.cli resume <session_id>

# List sessions
python -m empathy_os.socratic.cli list

# Export blueprint
python -m empathy_os.socratic.cli export <blueprint_id> -o workflow.json
```

## Best Practices

1. **Start Broad, Then Narrow**: Begin with open-ended goal capture, then ask specific questions
2. **Detect Ambiguity**: If goal is unclear, ask clarifying questions before proceeding
3. **Match Agents to Needs**: Don't over-engineer - select only relevant agents
4. **Define Measurable Success**: Every workflow needs quantifiable completion criteria
5. **Iterate Based on Feedback**: Use historical success data to improve recommendations
