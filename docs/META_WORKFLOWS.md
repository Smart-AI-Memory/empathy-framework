# Meta-Workflow System User Guide

**Version:** 4.6.2
**Last Updated:** 2026-01-21

---

## Table of Contents

1. [Overview](#overview)
2. [Quick Start](#quick-start)
3. [Core Concepts](#core-concepts)
4. [Using the CLI](#using-the-cli)
5. [Python API](#python-api)
6. [Creating Workflow Templates](#creating-workflow-templates)
7. [Memory Integration](#memory-integration)
8. [Pattern Learning & Analytics](#pattern-learning--analytics)
9. [Advanced Usage](#advanced-usage)
10. [Troubleshooting](#troubleshooting)
11. [Claude Code Skills Integration](#claude-code-skills-integration-v46)

---

## Overview

The Meta-Workflow System is an intelligent workflow orchestration framework that combines:

- **Socratic Forms** - Interactive requirements gathering
- **Dynamic Agent Creation** - Generates agent teams from templates
- **Progressive Tier Escalation** - Optimizes costs through smart model selection
- **Pattern Learning** - Learns from historical executions
- **Hybrid Storage** - Files (persistent) + Memory (semantic queries)

### Key Benefits

✅ **Reduce manual configuration** - Answer questions instead of writing code
✅ **Optimize costs** - Agents use appropriate model tiers (cheap → capable → premium)
✅ **Learn from history** - System recommends optimizations based on past runs
✅ **Reusable templates** - Share proven workflows across teams
✅ **Security hardened** - OWASP Top 10 compliant, no code injection risks

---

## Quick Start

### 1. Install Empathy Framework

```bash
pip install empathy-framework[developer]
```

### 2. Run Your First Meta-Workflow

```bash
# List available templates
empathy meta-workflow list-templates

# Run the Python package publishing workflow
empathy meta-workflow run python_package_publish
```

You'll be prompted with interactive questions like:

```
❓ Question 1 of 8: Does your package have tests?
   [1] Yes
   [2] No

Enter your choice (1-2): 1

❓ Question 2 of 8: What test coverage do you require?
   [1] 80%
   [2] 90%
   [3] 95%

Enter your choice (1-3): 2
```

### 3. View Results

After execution, the system will:

1. Create optimized agent team based on your responses
2. Execute agents with progressive tier escalation
3. Save results to `.empathy/meta_workflows/executions/<run_id>/`
4. Optionally store in memory for semantic queries

```bash
# View execution results
empathy meta-workflow show-run <run_id>

# View analytics
empathy meta-workflow analytics python_package_publish
```

---

## Core Concepts

### 1. Workflow Templates

Templates define reusable workflows with:

- **Form Schema** - Questions to ask users
- **Agent Composition Rules** - How to create agents from responses
- **Tier Strategies** - Cost optimization strategies per agent

**Example template structure:**

```json
{
  "template_id": "python_package_publish",
  "name": "Python Package Publishing",
  "description": "Comprehensive workflow for publishing Python packages to PyPI",
  "form_schema": {
    "questions": [
      {
        "id": "has_tests",
        "question": "Does your package have tests?",
        "type": "SINGLE_SELECT",
        "options": ["Yes", "No"],
        "required": true
      }
    ]
  },
  "agent_composition_rules": [
    {
      "role": "test_runner",
      "base_template": "testing_specialist",
      "tier_strategy": "PROGRESSIVE",
      "required_responses": {
        "has_tests": "Yes"
      },
      "config": {
        "coverage_threshold": "{{test_coverage_required}}"
      }
    }
  ]
}
```

### 2. Tier Strategies

Agents can use different tier strategies:

| Strategy | Description | Use Case |
|----------|-------------|----------|
| `CHEAP_ONLY` | Always uses cheap models | Simple, deterministic tasks |
| `PROGRESSIVE` | cheap → capable → premium | Quality-sensitive tasks |
| `CAPABLE_FIRST` | Start at capable tier | Complex tasks, skip cheap |

### 3. Form Response Flow

```
User answers questions
    ↓
FormResponse created with answers
    ↓
Agent Creator evaluates rules
    ↓
Agents created if required_responses match
    ↓
Config values populated from form responses (e.g., {{test_coverage_required}})
```

### 4. Execution Stages

Every meta-workflow follows 5 stages:

1. **Form Collection** - Gather requirements from user
2. **Agent Creation** - Generate agent team from template rules
3. **Agent Execution** - Execute agents (with tier escalation)
4. **Result Aggregation** - Combine outputs and calculate costs
5. **Storage** - Save to files (+ optional memory storage)

---

## Using the CLI

### List Templates

```bash
empathy meta-workflow list-templates
```

**Output:**

```
Available Meta-Workflow Templates:

1. python_package_publish
   Python Package Publishing
   Comprehensive workflow for publishing Python packages to PyPI
   Questions: 8 | Agent Rules: 8

Use: empathy meta-workflow run <template_id>
```

### Run Workflow

```bash
# Interactive mode (will prompt for responses)
empathy meta-workflow run python_package_publish

# Programmatic mode (provide responses file)
empathy meta-workflow run python_package_publish --responses responses.json
```

**Example responses.json:**

```json
{
  "template_id": "python_package_publish",
  "responses": {
    "has_tests": "Yes",
    "test_coverage_required": "90%",
    "quality_checks": ["Linting (ruff)", "Type checking (mypy)"],
    "version_bump": "minor",
    "publish_to": "PyPI (production)",
    "create_git_tag": "Yes",
    "update_changelog": "Yes"
  }
}
```

### View Execution Results

```bash
# Show detailed execution report
empathy meta-workflow show-run <run_id>
```

**Output:**

```
Meta-Workflow Execution Report
==============================

Run ID: python_package_publish-20260117-052959
Template: python_package_publish
Status: ✅ SUCCESS
Duration: 2.5s
Total Cost: $0.80

Agents Created: 8
├─ test_runner (PROGRESSIVE) - ✅ SUCCESS - $0.05 (cheap)
├─ type_checker (CAPABLE_FIRST) - ✅ SUCCESS - $0.25 (capable)
├─ linter (CHEAP_ONLY) - ✅ SUCCESS - $0.02 (cheap)
├─ security_auditor (PROGRESSIVE) - ✅ SUCCESS - $0.15 (capable)
├─ version_manager (CHEAP_ONLY) - ✅ SUCCESS - $0.02 (cheap)
├─ changelog_updater (CHEAP_ONLY) - ✅ SUCCESS - $0.02 (cheap)
├─ package_builder (PROGRESSIVE) - ✅ SUCCESS - $0.10 (cheap)
└─ publisher (CAPABLE_FIRST) - ✅ SUCCESS - $0.19 (capable)

Form Responses:
  has_tests: Yes
  test_coverage_required: 90%
  quality_checks: ["Linting (ruff)", "Type checking (mypy)"]
  version_bump: minor
  ...
```

### List Historical Executions

```bash
# All executions
empathy meta-workflow list-runs

# Filter by template
empathy meta-workflow list-runs --template-id python_package_publish

# Last N runs
empathy meta-workflow list-runs --limit 10
```

### View Analytics

```bash
# All templates
empathy meta-workflow analytics

# Specific template
empathy meta-workflow analytics python_package_publish
```

**Output:**

```
Pattern Learning Analytics: python_package_publish
==================================================

Summary:
  Total Runs: 15
  Successful: 14 (93.3%)
  Average Cost: $0.72 per run
  Average Agents: 6.8 per run
  Total Cost: $10.80

Insights:

📊 Agent Count Analysis
   Average agents created: 6.8
   Min: 2 agents (minimal quality config)
   Max: 8 agents (high quality config)

💰 Cost Analysis
   Average cost per run: $0.72
   Min: $0.15 (cheap-only strategy)
   Max: $1.20 (premium escalation)

   Tier breakdown:
   - cheap: 62% of executions ($0.05 avg)
   - capable: 28% of executions ($0.25 avg)
   - premium: 10% of executions ($0.80 avg)

🎯 Tier Performance
   test_runner (PROGRESSIVE):
     Success rate: 95% at cheap tier
     Escalation rate: 5%

   type_checker (CAPABLE_FIRST):
     Success rate: 100% at capable tier

Recommendations:
  1. Consider CHEAP_ONLY for linter (100% success at cheap)
  2. Keep PROGRESSIVE for test_runner (good escalation balance)
  3. Version management can use CHEAP_ONLY (no failures observed)
```

### Export Template

```bash
empathy meta-workflow export-template python_package_publish > my_template.json
```

### Validate Template

```bash
empathy meta-workflow validate-template my_template.json
```

**Output:**

```
✅ Template validation successful

Template: python_package_publish
Questions: 8
Agent Rules: 8
Estimated Cost Range: $0.10 - $1.50

Validation checks:
  ✅ template_id is valid
  ✅ All questions have unique IDs
  ✅ All agent rules reference valid base templates
  ✅ All config placeholders match question IDs
  ✅ No circular dependencies
```

---

## Python API

### Basic Usage

```python
from empathy_os.meta_workflows import (
    TemplateRegistry,
    MetaWorkflow,
    FormResponse,
)

# 1. Load template
registry = TemplateRegistry()
template = registry.load_template("python_package_publish")

# 2. Create workflow
workflow = MetaWorkflow(template=template)

# 3. Execute (interactive - will show AskUserQuestion prompts)
result = workflow.execute()

# Or provide responses programmatically
response = FormResponse(
    template_id="python_package_publish",
    responses={
        "has_tests": "Yes",
        "test_coverage_required": "90%",
        "quality_checks": ["Linting (ruff)", "Type checking (mypy)"],
        "version_bump": "minor",
    },
)

result = workflow.execute(form_response=response, mock_execution=True)

# 4. Inspect results
print(f"Created {len(result.agents_created)} agents")
print(f"Total cost: ${result.total_cost:.2f}")
print(f"Success: {result.success}")

for agent_result in result.agent_results:
    print(f"  {agent_result.role}: {agent_result.tier_used} - ${agent_result.cost:.2f}")
```

### Pattern Learning API

```python
from empathy_os.meta_workflows import PatternLearner

# Initialize learner
learner = PatternLearner()

# Analyze patterns
insights = learner.analyze_patterns(
    template_id="python_package_publish",
    min_confidence=0.7,
)

for insight in insights:
    print(f"{insight.insight_type}: {insight.description}")
    print(f"  Confidence: {insight.confidence:.1%}")
    print(f"  Data: {insight.data}")

# Get recommendations
recommendations = learner.get_recommendations(
    template_id="python_package_publish",
    min_confidence=0.6,
)

for rec in recommendations:
    print(f"💡 {rec}")

# Generate analytics report
report = learner.generate_analytics_report(
    template_id="python_package_publish"
)

print(f"Total runs: {report['summary']['total_runs']}")
print(f"Success rate: {report['summary']['success_rate']:.1%}")
print(f"Avg cost: ${report['summary']['avg_cost_per_run']:.2f}")
```

### Custom Storage Directory

```python
workflow = MetaWorkflow(
    template=template,
    storage_dir="/custom/path/to/executions",
)
```

---

## Creating Workflow Templates

### Template Structure

A workflow template consists of:

1. **Metadata** - ID, name, description, cost estimates
2. **Form Schema** - Questions to collect requirements
3. **Agent Composition Rules** - Logic for creating agents

### Step 1: Define Form Schema

```python
from empathy_os.meta_workflows import FormSchema, FormQuestion, QuestionType

schema = FormSchema(
    questions=[
        FormQuestion(
            id="project_type",
            question="What type of project is this?",
            question_type=QuestionType.SINGLE_SELECT,
            options=["Web Application", "CLI Tool", "Library", "Data Pipeline"],
            required=True,
            help_text="This determines which validation checks to run",
        ),
        FormQuestion(
            id="has_tests",
            question="Does your project have tests?",
            question_type=QuestionType.BOOLEAN,
            required=True,
        ),
        FormQuestion(
            id="test_frameworks",
            question="Which test frameworks do you use?",
            question_type=QuestionType.MULTI_SELECT,
            options=["pytest", "unittest", "nose2", "hypothesis"],
            required=False,
            dependencies={"has_tests": True},  # Only ask if has_tests is True
        ),
    ]
)
```

### Step 2: Define Agent Composition Rules

```python
from empathy_os.meta_workflows import AgentCompositionRule, TierStrategy

rules = [
    AgentCompositionRule(
        role="test_runner",
        base_template="testing_specialist",
        tier_strategy=TierStrategy.PROGRESSIVE,
        required_responses={"has_tests": True},  # Only create if has_tests=True
        config={
            "frameworks": "{{test_frameworks}}",  # Populate from form response
            "min_coverage": "{{min_coverage}}",
        },
        success_criteria={
            "tests_pass": True,
            "coverage_met": True,
        },
    ),
    AgentCompositionRule(
        role="code_quality",
        base_template="code_reviewer",
        tier_strategy=TierStrategy.CHEAP_ONLY,
        required_responses={},  # Always create (no requirements)
        config={
            "project_type": "{{project_type}}",
            "strict_mode": "{{strict_mode}}",
        },
    ),
]
```

### Step 3: Create Template

```python
from empathy_os.meta_workflows import MetaWorkflowTemplate

template = MetaWorkflowTemplate(
    template_id="my_custom_workflow",
    name="My Custom Workflow",
    description="Custom workflow for my use case",
    form_schema=schema,
    agent_composition_rules=rules,
    estimated_cost_range=(0.10, 2.00),  # Min/max cost estimates
)

# Save template
from empathy_os.meta_workflows import TemplateRegistry

registry = TemplateRegistry()
registry.save_template(template)
```

### Best Practices

1. **Question IDs**: Use descriptive, snake_case IDs
2. **Dependencies**: Use `dependencies` field to show/hide questions based on answers
3. **Config Placeholders**: Use `{{question_id}}` to inject form responses into agent configs
4. **Tier Strategies**:
   - Use `CHEAP_ONLY` for deterministic tasks (linting, formatting)
   - Use `PROGRESSIVE` for quality-sensitive tasks (testing, validation)
   - Use `CAPABLE_FIRST` for complex tasks (code generation, refactoring)
5. **Success Criteria**: Define clear success metrics for agents

---

## Memory Integration

### Why Memory Integration?

Memory integration enables:

- **Semantic search** - "Find workflows with high test coverage"
- **Context-aware recommendations** - Suggest optimizations based on similar past runs
- **Natural language queries** - No need to remember run IDs or filters
- **Relationship modeling** - Understand patterns across workflows

### Setup

```python
from empathy_os.memory.unified import UnifiedMemory
from empathy_os.meta_workflows import PatternLearner, MetaWorkflow

# 1. Initialize memory system
memory = UnifiedMemory(user_id="agent@company.com")

# 2. Create pattern learner with memory
learner = PatternLearner(memory=memory)

# 3. Create workflow with pattern learner
workflow = MetaWorkflow(
    template=template,
    pattern_learner=learner,  # Enables hybrid storage
)

# 4. Execute - automatically stores in files + memory
result = workflow.execute(form_response=response)
```

### Memory-Enhanced Queries

```python
# Semantic search for similar executions
similar = learner.search_executions_by_context(
    query="successful workflows with progressive tier escalation",
    template_id="python_package_publish",
    limit=10,
)

for result in similar:
    print(f"Run: {result.run_id}")
    print(f"  Success: {result.success}")
    print(f"  Cost: ${result.total_cost:.2f}")
    print(f"  Agents: {len(result.agents_created)}")
```

### Smart Recommendations

```python
# Get memory-enhanced recommendations
recommendations = learner.get_smart_recommendations(
    template_id="python_package_publish",
    form_response=new_response,
    min_confidence=0.7,
)

for rec in recommendations:
    print(f"💡 {rec}")
```

**Example output:**

```
💡 Similar workflows with test_coverage_required=90% had 15% lower costs using CHEAP_ONLY for linter
💡 Workflows with quality_checks=["Linting","Type checking"] succeeded 98% of the time at capable tier
💡 Consider PROGRESSIVE strategy for security_auditor based on 3 similar successful runs
```

### Graceful Fallback

If memory is unavailable, the system automatically falls back to file-based operations:

```python
# Works without memory (files only)
learner = PatternLearner()  # No memory parameter

# Still works - uses file-based keyword search
similar = learner.search_executions_by_context(
    query="successful workflows",
    limit=5,
)
```

---

## Pattern Learning & Analytics

### How Pattern Learning Works

1. **Data Collection** - Every execution is saved with rich metadata:
   - Form responses
   - Agents created (roles, tier strategies, configs)
   - Agent results (success/failure, tier used, cost, duration)
   - Total cost and duration
   - Timestamp

2. **Pattern Analysis** - System analyzes historical data for:
   - **Agent count patterns** - How many agents are typically needed?
   - **Tier performance** - Which tiers succeed for which agent roles?
   - **Cost distribution** - What's the typical cost range?
   - **Failure patterns** - Which configurations fail more often?

3. **Insight Generation** - Creates actionable insights:
   - "Consider CHEAP_ONLY for linter (100% success at cheap tier)"
   - "test_runner escalates to capable 15% of the time"
   - "Average cost: $0.72 per run"

4. **Recommendations** - Suggests optimizations:
   - Tier strategy adjustments
   - Configuration changes
   - Cost optimization opportunities

### Confidence Scores

Every insight has a confidence score (0.0-1.0) based on:

- Sample size (more data = higher confidence)
- Consistency (consistent patterns = higher confidence)
- Recency (recent data weighted higher)

**Filtering by confidence:**

```python
# Only high-confidence insights (70%+)
insights = learner.analyze_patterns(min_confidence=0.7)

# All insights (including low-confidence)
insights = learner.analyze_patterns(min_confidence=0.0)
```

### Analytics Report Structure

```python
report = learner.generate_analytics_report("python_package_publish")

# Report structure:
{
    "summary": {
        "total_runs": 15,
        "successful_runs": 14,
        "failed_runs": 1,
        "success_rate": 0.933,
        "total_cost": 10.80,
        "avg_cost_per_run": 0.72,
        "total_agents_created": 102,
        "avg_agents_per_run": 6.8,
    },
    "insights": {
        "agent_count": [...],
        "tier_performance": [...],
        "cost_analysis": [...],
        "failure_patterns": [...],
    },
    "recommendations": [
        "Consider CHEAP_ONLY for linter",
        "Keep PROGRESSIVE for test_runner",
        ...
    ],
}
```

---

## Advanced Usage

### Custom Base Templates

Create custom base templates for agents:

```python
from empathy_os.orchestration.agent_templates import AgentTemplate

custom_template = AgentTemplate(
    role="custom_validator",
    description="Custom validation logic",
    system_prompt="You are a validation expert...",
    model_tier="cheap",
)

# Use in agent composition rule
rule = AgentCompositionRule(
    role="validator",
    base_template="custom_validator",  # Reference your custom template
    tier_strategy=TierStrategy.PROGRESSIVE,
    ...
)
```

### Programmatic Template Creation

```python
from pathlib import Path
import json

# Load template from file
template_path = Path("templates/my_template.json")
template_data = json.loads(template_path.read_text())

template = MetaWorkflowTemplate.from_dict(template_data)

# Or create from scratch
template = MetaWorkflowTemplate(
    template_id="dynamic_workflow",
    name="Dynamically Created Workflow",
    ...
)
```

### Batch Execution

```python
# Execute multiple configurations
configs = [
    {"has_tests": "No", "version_bump": "patch"},
    {"has_tests": "Yes", "test_coverage_required": "80%"},
    {"has_tests": "Yes", "test_coverage_required": "90%"},
]

results = []
for config in configs:
    response = FormResponse(
        template_id="python_package_publish",
        responses=config,
    )
    result = workflow.execute(form_response=response, mock_execution=True)
    results.append(result)

# Analyze batch results
total_cost = sum(r.total_cost for r in results)
avg_agents = sum(len(r.agents_created) for r in results) / len(results)

print(f"Batch execution complete: {len(results)} runs")
print(f"Total cost: ${total_cost:.2f}")
print(f"Avg agents: {avg_agents:.1f}")
```

### Custom Execution Logic

Override execution for real LLM integration (v4.3.0+):

```python
class CustomMetaWorkflow(MetaWorkflow):
    def _execute_agents(self, agents):
        """Override to use real LLM execution."""
        results = []
        for agent in agents:
            # Real LLM execution logic here
            result = self._execute_single_agent_real(agent)
            results.append(result)
        return results
```

---

## Troubleshooting

### Issue: Questions not showing

**Symptom:** `workflow.execute()` runs without showing questions

**Cause:** Form responses were provided programmatically

**Solution:**

```python
# Don't pass form_response to see interactive questions
result = workflow.execute()  # Shows questions

# Or check if you accidentally passed responses
result = workflow.execute(form_response=None)  # Also shows questions
```

### Issue: Agent not created

**Symptom:** Expected agent missing from execution

**Cause:** `required_responses` not matching form responses

**Debug:**

```python
# Print agent rules
for rule in template.agent_composition_rules:
    print(f"{rule.role}: {rule.required_responses}")

# Print form responses
print(f"Responses: {response.responses}")

# Check for mismatches
```

**Common issues:**

- String vs boolean mismatch (`"True"` vs `True`)
- Case sensitivity (`"yes"` vs `"Yes"`)
- Multi-select format (must be list: `["option1", "option2"]`)

### Issue: Low coverage in analytics

**Symptom:** Analytics show "not enough data"

**Cause:** Fewer than 3 executions for template

**Solution:** Run more executions:

```bash
# Run workflow multiple times with different configs
empathy meta-workflow run python_package_publish
```

Pattern learning requires 3+ executions for meaningful insights.

### Issue: Memory integration not working

**Symptom:** `learner.search_executions_by_context()` returns empty

**Cause:** Memory not initialized or search not implemented

**Debug:**

```python
# Check if memory is available
if learner.memory:
    print("Memory available")
else:
    print("Memory not available - using file fallback")

# Check memory backend status
if learner.memory:
    status = learner.memory.get_backend_status()
    print(f"Short-term: {status['short_term']['available']}")
    print(f"Long-term: {status['long_term']['available']}")
```

**Note:** Memory search implementation is deferred to v4.3.0. Currently uses file-based fallback.

### Issue: Template validation fails

**Symptom:** `validate-template` command reports errors

**Common errors:**

1. **Missing required fields:**
   ```json
   Error: template_id is required
   Error: form_schema.questions is empty
   ```

2. **Invalid question IDs:**
   ```json
   Error: Duplicate question ID 'has_tests'
   Error: Question ID contains spaces
   ```

3. **Invalid config placeholders:**
   ```json
   Error: Config placeholder '{{unknown_question}}' does not match any question ID
   ```

4. **Invalid base template:**
   ```json
   Error: base_template 'unknown_agent' not found in agent registry
   ```

**Fix:** Review template JSON against the [template structure](#template-structure) specification.

---

## Claude Code Skills Integration (v4.6+)

Starting with v4.6, Empathy Framework integrates directly with Claude Code through slash command skills. These skills provide $0 cost execution using your Claude Max subscription.

### Available Skills

| Skill | Command | Description |
|-------|---------|-------------|
| Create Agent | `/create-agent` | Socratic guide for creating custom agents |
| Create Team | `/create-team` | Create multi-agent teams collaboratively |
| Release Prep | `/release-prep` | Run release preparation workflow |
| Test Coverage | `/test-coverage` | Boost test coverage in targeted modules |
| Test Maintenance | `/test-maintenance` | Fix failing tests and align with code changes |
| Manage Docs | `/manage-docs` | Analyze documentation health and sync |
| Feature Overview | `/feature-overview` | Generate feature documentation |
| Security Scan | `/security-scan` | Run comprehensive security checks |
| Test | `/test` | Run test suite and report results |
| Status | `/status` | Show project status summary |
| Publish | `/publish` | Guide package publishing to PyPI |
| Init | `/init` | Initialize new Empathy Framework project |
| Memory | `/memory` | Manage the memory system |

### Using Skills in Claude Code

Skills run entirely within Claude Code using exploratory agents:

```bash
# In Claude Code, simply type:
/release-prep

# Claude will:
# 1. Run pre-release checks (tests, coverage, CHANGELOG)
# 2. Validate semantic versioning
# 3. Generate release report
```

### Skill Configuration

Skills are defined in `.claude/commands/` directory:

```text
.claude/commands/
├── create-agent.md      # Agent creation wizard
├── create-team.md       # Team creation wizard
├── release-prep.md      # Release preparation
├── test-coverage.md     # Coverage boosting
├── manage-docs.md       # Documentation management
├── security-scan.md     # Security auditing
└── ...
```

### Cost Comparison

| Execution Mode | Cost | Speed | Use Case |
|---------------|------|-------|----------|
| Claude Code Skills | $0 (Max subscription) | Fast | Development workflow |
| Meta-workflow (simulated) | $0 | Fast | Testing/validation |
| Meta-workflow (real) | $0.08-$0.50 | Medium | Production execution |

### Extending Skills

To create a custom skill:

1. Create a markdown file in `.claude/commands/your-skill.md`
2. Define the skill prompt and instructions
3. The skill will appear as `/your-skill` in Claude Code

Example skill template:

```markdown
# /your-skill - Your Skill Name

Brief description of what the skill does.

## Instructions for Claude

When the user invokes /your-skill:

1. First step...
2. Second step...
3. Generate report...
```

### Skill vs Meta-Workflow

| Feature | Claude Code Skills | Meta-Workflows |
|---------|-------------------|----------------|
| Cost | $0 | $0-$0.50 |
| Interactive forms | No | Yes |
| Pattern learning | Limited | Full |
| Execution tracking | No | Yes |
| Best for | Quick dev tasks | Production workflows |

Use skills for rapid development tasks; use meta-workflows for production pipelines that need tracking and analytics.

---

## Appendix

### Question Types Reference

| Type | Description | Example |
|------|-------------|---------|
| `TEXT_INPUT` | Free-form text | "What is the package name?" |
| `SINGLE_SELECT` | Choose one option | "Which tier?" → ["cheap", "capable"] |
| `MULTI_SELECT` | Choose multiple | "Quality checks?" → ["Lint", "Type", "Test"] |
| `BOOLEAN` | Yes/No question | "Has tests?" → Yes/No |

### Tier Strategy Reference

| Strategy | Behavior | Cost Profile | Use Case |
|----------|----------|--------------|----------|
| `CHEAP_ONLY` | Always cheap | $ | Deterministic tasks (lint, format) |
| `PROGRESSIVE` | cheap → capable → premium | $-$$$ | Quality-sensitive (test, validate) |
| `CAPABLE_FIRST` | capable → premium | $$-$$$ | Complex tasks (refactor, generate) |

### File Locations

| Path | Description |
|------|-------------|
| `.empathy/meta_workflows/templates/` | Workflow templates (JSON) |
| `.empathy/meta_workflows/executions/<run_id>/` | Execution results |
| `.empathy/meta_workflows/executions/<run_id>/config.json` | Template used |
| `.empathy/meta_workflows/executions/<run_id>/form_responses.json` | User responses |
| `.empathy/meta_workflows/executions/<run_id>/agents.json` | Agents created |
| `.empathy/meta_workflows/executions/<run_id>/result.json` | Execution result |
| `.empathy/meta_workflows/executions/<run_id>/report.txt` | Human-readable report |

### Related Documentation

- [CHANGELOG.md](../CHANGELOG.md) - Version history
- [META_WORKFLOW_SECURITY_REVIEW.md](../META_WORKFLOW_SECURITY_REVIEW.md) - Security audit
- [MEMORY_INTEGRATION_SUMMARY.md](../MEMORY_INTEGRATION_SUMMARY.md) - Memory architecture
- [DAY_5_COMPLETION_SUMMARY.md](../DAY_5_COMPLETION_SUMMARY.md) - Implementation summary

---

**Questions or Issues?**

- GitHub Issues: https://github.com/Smart-AI-Memory/empathy-framework/issues
- GitHub Discussions: https://github.com/Smart-AI-Memory/empathy-framework/discussions
- Documentation: https://empathyframework.com/framework-docs/

**Contributing:**

We welcome contributions! See [CONTRIBUTING.md](../CONTRIBUTING.md) for guidelines.

---

**Version:** 4.6.2
**Last Updated:** 2026-01-21
**Maintained By:** Empathy Framework Team
