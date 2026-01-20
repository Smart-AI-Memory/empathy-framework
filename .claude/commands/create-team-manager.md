# Create Team Management Agent - Socratic Guide

You are helping the user create a Team Management Agent (orchestrator) that coordinates sub-agents to accomplish complex tasks. Use the AskUserQuestion tool to gather requirements through a guided Socratic conversation.

**Cost: $0** - Runs within Claude Code using your Max subscription.

## What is a Team Manager Agent?

Unlike static teams, a Team Manager Agent:
- Dynamically spawns and coordinates sub-agents based on task requirements
- Decomposes complex tasks into subtasks for delegation
- Aggregates results from multiple agents into coherent outputs
- Handles failures, retries, and escalation
- Learns from past executions (optional)

## Step 1: Team Mission

First, understand what this team will accomplish.

Use AskUserQuestion with:

- Question: "What is the primary mission of this managed team?"
- Header: "Mission"
- Options:
  - "Code Quality Pipeline" - Review, test, and improve code quality
  - "Feature Development" - Implement new features with multiple specialists
  - "Incident Response" - Diagnose and fix production issues
  - "Knowledge Work" - Research, document, and synthesize information

## Step 2: Sub-Agent Pool

Determine which types of agents the manager can spawn.

Use AskUserQuestion with multiSelect: true:

- Question: "Which agent types should the manager be able to deploy? (Select all that apply)"
- Header: "Agent Pool"
- Options:
  - "Analyzer" - Examines code/data and identifies patterns or issues
  - "Generator" - Creates content, code, tests, or documentation
  - "Reviewer" - Validates quality, security, or correctness
  - "Specialist" - Domain expert (security, performance, architecture)

## Step 3: Coordination Strategy

Determine how the manager delegates and coordinates work.

Use AskUserQuestion with:

- Question: "How should the manager coordinate sub-agents?"
- Header: "Strategy"
- Options:
  - "Sequential Pipeline (Recommended)" - Each agent's output feeds the next
  - "Parallel Fan-Out" - Run multiple agents simultaneously, merge results
  - "Adaptive" - Manager decides based on task complexity
  - "Hierarchical" - Manager spawns sub-managers for complex subtasks

## Step 4: Communication Pattern

Determine how agents share context and results.

Use AskUserQuestion with:

- Question: "How should agents communicate with each other?"
- Header: "Communication"
- Options:
  - "Shared Context (Recommended)" - All agents can read shared context
  - "Message Passing" - Agents explicitly send messages to each other
  - "Blackboard" - Central knowledge store all agents can read/write
  - "Direct Handoff" - Output of one agent becomes input of next

## Step 5: Failure Handling

Determine what happens when things go wrong.

Use AskUserQuestion with:

- Question: "How should the manager handle agent failures?"
- Header: "Failures"
- Options:
  - "Retry with same agent (Recommended)" - Retry up to 3 times
  - "Fallback to different agent" - Try an alternative agent type
  - "Escalate to human" - Pause and ask user for guidance
  - "Skip and continue" - Log failure and continue with remaining agents

## Step 6: Output Format

Determine how results are delivered.

Use AskUserQuestion with:

- Question: "What format should the team's final output be in?"
- Header: "Output"
- Options:
  - "Structured JSON (Recommended)" - Machine-readable structured data
  - "Markdown Report" - Human-readable formatted report
  - "Code Changes" - Direct modifications to the codebase
  - "Mixed" - JSON data with Markdown summary

## Step 7: Memory & Learning (Optional)

Determine if the manager should learn from executions.

Use AskUserQuestion with:

- Question: "Should this manager learn from past executions?"
- Header: "Memory"
- Options:
  - "No memory (Recommended)" - Stateless, simpler setup
  - "Session memory" - Remember patterns within current session
  - "Persistent learning" - Store successful strategies for future use
  - "Full memory" - Both session and persistent memory

## Step 8: Generate the Team Manager

After gathering all answers, generate a Team Manager specification. Create two outputs:

### Output 1: Team Manager Blueprint (JSON)

```json
{
  "id": "[team-manager-id]",
  "name": "[Team Manager Name]",
  "version": "1.0.0",
  "mission": "[Selected mission]",
  "manager": {
    "role": "orchestrator",
    "model_tier": "capable",
    "goal": "[Derived from mission]",
    "backstory": "Expert team coordinator skilled in task decomposition, delegation, and result synthesis.",
    "capabilities": [
      "task_decomposition",
      "agent_spawning",
      "result_aggregation",
      "failure_handling"
    ]
  },
  "agent_pool": {
    "available_types": ["[Selected agent types]"],
    "spawn_strategy": "[coordination strategy]",
    "max_concurrent": 3
  },
  "coordination": {
    "strategy": "[Selected strategy]",
    "communication": "[Selected pattern]",
    "failure_handling": "[Selected failure handling]"
  },
  "output": {
    "format": "[Selected format]",
    "include_metadata": true,
    "include_agent_logs": false
  },
  "memory": {
    "enabled": "[true/false based on selection]",
    "type": "[session/persistent/full]"
  }
}
```

### Output 2: Claude Code Skill File

Create file at `.claude/commands/[team-manager-name].md`:

```markdown
# [Team Manager Name]

[Description based on mission and configuration]

## What This Does

Orchestrates a team of specialized agents to [mission description]:

- **Manager**: Coordinates all sub-agents and synthesizes results
- **Agent Pool**: [List of available agent types]
- **Strategy**: [Coordination strategy description]

## Usage

/[team-manager-name] [task description]

## Instructions for Claude

When the user invokes /[team-manager-name], act as the Team Manager agent:

### Phase 1: Task Analysis

Analyze the user's request and decompose it into subtasks:

1. Read the task description carefully
2. Identify which agent types are needed from the pool: [agent types]
3. Determine the execution order based on strategy: [strategy]
4. Create a task plan

Output a JSON task plan:
```json
{
  "task": "[user's task]",
  "subtasks": [
    {"id": 1, "type": "[agent type]", "description": "[subtask]", "depends_on": []},
    {"id": 2, "type": "[agent type]", "description": "[subtask]", "depends_on": [1]}
  ]
}
```

### Phase 2: Agent Execution

For each subtask, spawn the appropriate agent using the Task tool:

**Strategy: [Selected strategy]**

[If Sequential Pipeline]:
Execute each subtask in order. Pass the output of each agent to the next:
- Use Task tool with subagent_type matching the agent type
- Include previous agent's output in the prompt
- Collect results before proceeding

[If Parallel Fan-Out]:
Execute independent subtasks in parallel:
- Use multiple Task tool calls in a single message
- Wait for all to complete
- Merge results using [communication pattern]

[If Adaptive]:
Evaluate task complexity first:
- Simple tasks: Execute sequentially
- Complex tasks: Spawn sub-manager or parallelize
- Track execution and adjust strategy

[If Hierarchical]:
For complex subtasks, create sub-managers:
- Each sub-manager handles a subset of the work
- Aggregate results from all sub-managers

### Phase 3: Result Aggregation

Collect all agent outputs and synthesize:

1. Gather all subtask results
2. Check for failures (handle per: [failure handling])
3. Merge/synthesize into final output
4. Format as: [output format]

### Phase 4: Final Output

[If Structured JSON]:
```json
{
  "task": "[original task]",
  "status": "completed",
  "results": {
    "summary": "[high-level summary]",
    "details": "[detailed findings from each agent]",
    "recommendations": "[actionable items]"
  },
  "execution": {
    "agents_used": ["[list of agents]"],
    "duration_estimate": "[time taken]",
    "success_rate": "[% of subtasks completed]"
  }
}
```

[If Markdown Report]:
## Team Execution Report

### Summary
[High-level summary of findings]

### Agent Reports
[Section for each agent's output]

### Recommendations
[Actionable items]

[If Code Changes]:
Apply changes to the codebase using Edit tool, then summarize what was changed.

[If Mixed]:
Provide both JSON data and Markdown summary.

## Memory Integration

[Include only if memory enabled]

### Session Memory
Pass context between agents within this execution:
- Store intermediate results in context
- Reference earlier findings in later agent prompts

### Persistent Learning
After successful execution:
```bash
empathy memory store --type "team_execution" --content "[execution summary]"
```

Before execution, check for relevant patterns:
```bash
empathy memory search "[task keywords]"
```

## Model Tiers

- **Manager**: [capable/sonnet] - Handles orchestration
- **Analyzers**: haiku - Fast analysis
- **Generators**: capable - Quality output
- **Reviewers**: capable - Thorough validation
- **Specialists**: capable/opus - Deep expertise

## Cost

**$0** - Runs entirely within Claude Code using your Max subscription.

## Example Usage

User: /[team-manager-name] Review the authentication module for security issues

Manager Response:
1. Decomposes into: code analysis, security scan, vulnerability report
2. Spawns: Analyzer -> Security Specialist -> Reporter
3. Aggregates findings into structured security report
```

### Step 9: Save and Explain

After generating both outputs:

1. **Show the JSON Blueprint** - Display the full JSON specification
2. **Save the Skill File** - Write to `.claude/commands/[team-manager-name].md`
3. **Explain Usage**:
   - How to invoke: `/[team-manager-name] [task]`
   - How to customize: Edit the skill file
   - How to add agents: Extend the agent pool
4. **Optionally Save Blueprint** - Offer to save JSON to `.empathy/team-managers/[id].json`

## Important Guidelines

- Use AskUserQuestion for EACH step - don't ask multiple questions at once
- Wait for user response before proceeding to next step
- Generate meaningful names based on their mission choice
- Always create the `.claude/commands/` skill file for $0 execution
- The JSON blueprint enables programmatic access and future extensions
- Keep the Socratic conversation focused and efficient (7-8 questions max)

## Advanced: JSON Schema for Inter-Agent Communication

When agents communicate, they should use this standardized message format:

```json
{
  "from_agent": "[sender agent id]",
  "to_agent": "[recipient agent id or 'manager']",
  "message_type": "result|request|error|status",
  "content": {
    "summary": "[brief summary]",
    "data": {},
    "confidence": 0.95
  },
  "metadata": {
    "timestamp": "[ISO timestamp]",
    "execution_id": "[unique execution id]"
  }
}
```

This enables structured communication that the manager can parse and route appropriately.
