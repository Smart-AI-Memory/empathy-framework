# Workflows API Reference

The workflows module provides a framework for creating cost-optimized, multi-tier AI pipelines.

## Overview

Workflows enable:
- **Tier routing**: Route tasks to appropriate model tiers (cheap/capable/premium)
- **Cost optimization**: 34-86% cost savings through intelligent routing
- **Multi-stage pipelines**: Chain multiple processing stages
- **Progress tracking**: Monitor workflow execution

## ModelTier

Define which model tier to use for each stage.

```python
from empathy_os.workflows.base import ModelTier

class ModelTier(Enum):
    CHEAP = "cheap"      # Haiku/GPT-4o-mini - $0.25-1.25/M tokens
    CAPABLE = "capable"  # Sonnet/GPT-4o - $3-15/M tokens
    PREMIUM = "premium"  # Opus/o1 - $15-75/M tokens
```

## BaseWorkflow

Abstract base class for all workflows.

```python
from empathy_os.workflows.base import BaseWorkflow, ModelTier

class MyWorkflow(BaseWorkflow):
    name = "my-workflow"
    description = "My custom workflow"
    stages = ["analyze", "process", "report"]
    tier_map = {
        "analyze": ModelTier.CHEAP,
        "process": ModelTier.CAPABLE,
        "report": ModelTier.CHEAP,
    }

    async def run_stage(
        self,
        stage_name: str,
        tier: ModelTier,
        input_data: Any,
    ) -> tuple[Any, int, int]:
        """Execute a workflow stage.

        Returns:
            Tuple of (result, input_tokens, output_tokens)
        """
        if stage_name == "analyze":
            return await self._analyze(input_data, tier)
        elif stage_name == "process":
            return await self._process(input_data, tier)
        elif stage_name == "report":
            return await self._report(input_data, tier)
        raise ValueError(f"Unknown stage: {stage_name}")
```

## Workflow Execution

Execute workflows with the `execute()` method.

```python
workflow = MyWorkflow()

# Async execution
result = await workflow.execute(input_data)

# Access results
print(f"Success: {result.success}")
print(f"Total cost: ${result.total_cost:.4f}")
print(f"Stages completed: {result.stages_completed}")
```

## WorkflowResult

Result object returned from workflow execution.

```python
@dataclass
class WorkflowResult:
    success: bool
    output: Any
    stages_completed: list[str]
    total_cost: float
    total_input_tokens: int
    total_output_tokens: int
    execution_time: float
    errors: list[str]
```

## Built-in Workflows

| Workflow | Description |
|----------|-------------|
| `bug-predict` | Scan code for potential bugs |
| `code-review` | Automated code review |
| `test-gen` | Generate test cases |
| `doc-gen` | Generate documentation |
| `security-audit` | Security vulnerability scan |
| `document-manager` | Manage documentation files |
| `manage-docs` | Documentation management |

## CLI Usage

```bash
# List available workflows
empathy workflow list

# Run a workflow
empathy workflow run bug-predict --input '{"path": "./src"}'

# Run with JSON output
empathy workflow run code-review --json

# Run with custom tier
empathy workflow run test-gen --tier capable
```

## Progress Tracking

Monitor workflow progress with callbacks.

```python
from empathy_os.workflows.progress import ProgressCallback

def on_progress(stage: str, progress: float, message: str):
    print(f"[{stage}] {progress:.0%}: {message}")

workflow = MyWorkflow(progress_callback=on_progress)
await workflow.execute(input_data)
```

## LLM Integration

Workflows can use the built-in `_call_llm` method.

```python
class MyWorkflow(BaseWorkflow):
    async def _analyze(self, input_data: Any, tier: ModelTier):
        response, in_tokens, out_tokens = await self._call_llm(
            tier=tier,
            system="You are an expert analyst.",
            user_message=f"Analyze: {input_data}",
            max_tokens=2000,
        )
        return response, in_tokens, out_tokens
```

## Cost Tracking

Workflows automatically track costs.

```python
from empathy_os.cost_tracker import CostTracker

# Global cost tracker
tracker = CostTracker()

# After workflow execution
print(f"Session cost: ${tracker.session_cost:.4f}")
print(f"Total tokens: {tracker.total_tokens:,}")
```

## Configuration

Configure workflows via `empathy.config.yml`:

```yaml
workflows:
  default_tier: capable
  cache_enabled: true
  cache_ttl: 1800

  # Tier overrides per workflow
  bug-predict:
    analyze: cheap
    report: cheap

  code-review:
    review: capable
    summarize: cheap
```

## Creating Custom Workflows

1. Inherit from `BaseWorkflow`
2. Define `name`, `description`, `stages`, `tier_map`
3. Implement `run_stage()` method
4. Register with workflow factory (optional)

```python
from empathy_os.workflows.base import BaseWorkflow, ModelTier

class CustomWorkflow(BaseWorkflow):
    name = "custom"
    description = "My custom workflow"
    stages = ["step1", "step2"]
    tier_map = {
        "step1": ModelTier.CHEAP,
        "step2": ModelTier.CAPABLE,
    }

    async def run_stage(self, stage_name, tier, input_data):
        if stage_name == "step1":
            # Implement step1
            return {"analyzed": True}, 100, 50
        elif stage_name == "step2":
            # Implement step2
            return {"processed": True}, 200, 100
        raise ValueError(f"Unknown stage: {stage_name}")
```
