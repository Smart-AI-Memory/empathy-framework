# Code Quality Manager

Orchestrate a team of specialized agents to ensure comprehensive code quality through coordinated analysis, generation, review, and specialized assessment.

**Generated:** 2026-01-20
**Version:** 1.0.0
**Cost:** $0 - Runs entirely within Claude Code

## What This Does

Orchestrates a **Code Quality Pipeline** with these capabilities:

- **Manager**: Coordinates all sub-agents and synthesizes results
- **Agent Pool**: Analyzer, Generator, Reviewer, Specialist
- **Strategy**: Sequential Pipeline - each agent's output feeds the next
- **Communication**: Shared Context - accumulated findings visible to all
- **Failures**: Fallback to different agent type if one fails
- **Memory**: Persistent learning - stores successful patterns for future use

## Usage

```
/code-quality-manager [task description]
```

### Examples

```
/code-quality-manager Review the authentication module for security and quality issues
/code-quality-manager Analyze src/api/ for performance bottlenecks and suggest improvements
/code-quality-manager Check test coverage and generate missing tests for core modules
```

## Instructions for Claude

When the user invokes `/code-quality-manager`, act as the Team Manager agent following this workflow:

### Phase 1: Task Analysis

Analyze the user's request and decompose it into subtasks:

1. Parse the task description to understand scope
2. Identify which agent types are needed from: `analyzer`, `generator`, `reviewer`, `specialist`
3. Plan execution order (sequential pipeline)
4. Create a task plan

**Output a JSON task plan:**

```json
{
  "task": "[user's task]",
  "scope": "[files/modules being analyzed]",
  "subtasks": [
    {"id": 1, "type": "analyzer", "description": "[analysis task]", "depends_on": []},
    {"id": 2, "type": "specialist", "description": "[specialized review]", "depends_on": [1]},
    {"id": 3, "type": "generator", "description": "[generate fixes/tests]", "depends_on": [2]},
    {"id": 4, "type": "reviewer", "description": "[validate changes]", "depends_on": [3]}
  ],
  "shared_context": {
    "quality_focus": ["security", "performance", "maintainability"],
    "findings": []
  }
}
```

### Phase 2: Agent Execution

Execute each subtask using the Task tool in **sequential order**:

#### Step 2.1: Analyzer Agent

```
Use Task tool with:
- subagent_type: "Explore" (for code analysis)
- model: "haiku" (fast analysis)
- prompt: Analyze [scope] for [quality aspects]. Look for:
  - Code patterns and anti-patterns
  - Potential issues (bugs, security, performance)
  - Areas needing improvement
  Return findings as structured JSON.
```

**Add analyzer findings to shared context.**

#### Step 2.2: Specialist Agent

```
Use Task tool with:
- subagent_type: "Explore" or "general-purpose"
- model: "sonnet" (deeper expertise)
- prompt: Based on analyzer findings: [shared_context.findings]
  Provide specialized assessment for [domain: security/performance/architecture].
  Prioritize issues by severity and impact.
```

**Add specialist assessment to shared context.**

#### Step 2.3: Generator Agent

```
Use Task tool with:
- subagent_type: "general-purpose"
- model: "sonnet" (quality output)
- prompt: Based on findings: [shared_context.findings]
  Generate [fixes/tests/documentation] to address identified issues.
  Follow project coding standards.
```

**Add generated content to shared context.**

#### Step 2.4: Reviewer Agent

```
Use Task tool with:
- subagent_type: "general-purpose"
- model: "sonnet" (thorough validation)
- prompt: Review the generated changes against:
  - Original findings
  - Project coding standards
  - Best practices
  Validate completeness and correctness.
```

### Phase 2.5: Failure Handling

If any agent fails:

1. Log the failure with context
2. Attempt fallback to alternative agent type:
   - Analyzer fails -> Try Specialist for initial analysis
   - Generator fails -> Try Analyzer with generation prompt
   - Specialist fails -> Try Reviewer with domain focus
   - Reviewer fails -> Try Analyzer for validation
3. If fallback fails, continue with remaining agents and note the gap

### Phase 3: Result Aggregation

Collect all agent outputs and synthesize:

1. Gather all subtask results from shared context
2. Merge findings by category (security, performance, maintainability)
3. Deduplicate overlapping findings
4. Prioritize by severity: CRITICAL > HIGH > MEDIUM > LOW
5. Generate actionable recommendations

### Phase 4: Final Output

Output structured JSON result:

```json
{
  "task": "[original task]",
  "status": "completed",
  "results": {
    "summary": "[1-2 sentence high-level summary]",
    "findings": {
      "critical": [{"issue": "...", "location": "...", "recommendation": "..."}],
      "high": [...],
      "medium": [...],
      "low": [...]
    },
    "generated_content": {
      "fixes": ["[list of fixes applied or suggested]"],
      "tests": ["[list of tests generated]"],
      "documentation": ["[documentation updates]"]
    },
    "recommendations": [
      {"priority": 1, "action": "...", "impact": "..."},
      {"priority": 2, "action": "...", "impact": "..."}
    ]
  },
  "execution": {
    "agents_used": ["analyzer", "specialist", "generator", "reviewer"],
    "subtasks_completed": 4,
    "subtasks_failed": 0,
    "fallbacks_used": 0
  }
}
```

## Memory Integration

### Before Execution

Search for relevant patterns from past executions:

```bash
empathy memory search "code_quality [relevant keywords from task]"
```

Use past successful strategies to inform task decomposition.

### After Successful Execution

Store the execution pattern:

```bash
empathy memory store --type "team_execution" --tags "code_quality,success" --content "[execution summary with what worked well]"
```

### After Failures

Store failure patterns to avoid:

```bash
empathy memory store --type "team_execution" --tags "code_quality,failure" --content "[what failed and why]"
```

## Model Tiers

| Agent Type | Model | Rationale |
|------------|-------|-----------|
| Manager | capable (Sonnet) | Orchestration requires good reasoning |
| Analyzer | haiku | Fast pattern detection |
| Generator | capable (Sonnet) | Quality code generation |
| Reviewer | capable (Sonnet) | Thorough validation |
| Specialist | capable (Sonnet) | Deep domain expertise |

## Customization

### Adding Agent Types

Edit the `agent_pool.available_types` in this file to add:
- `fixer` - Automatically applies fixes
- `documenter` - Generates documentation
- `tester` - Specialized test generation

### Changing Strategy

Modify Phase 2 to change coordination:
- **Parallel**: Launch analyzer + specialist simultaneously, merge before generator
- **Adaptive**: Check task complexity first, parallelize for simple tasks

### Adjusting Output

Modify Phase 4 to change output format:
- Add `include_agent_logs: true` for debugging
- Switch to Markdown for human-readable reports
