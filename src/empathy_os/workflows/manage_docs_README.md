# ManageDocsWorkflow

**Manage documentation**

---

## Overview

**Patterns Used:**
- `single-stage` - Simple one-stage workflow with single tier

**Complexity:** SIMPLE

**Stages:**
1. **process** - CAPABLE tier

---

## Usage

```python
from empathy_os.workflows.manage_docs import ManageDocsWorkflow

# Initialize workflow
workflow = ManageDocsWorkflow(
)

# Execute
result = await workflow.execute(
    # Add your input data here
)

# Check result
print(f"Success: {result.success}")
```

---

## CLI Usage

```bash
# Run via empathy CLI
empathy workflow run manage-docs --input '{"key": "value"}'

# With options
```

---

## Configuration

This workflow does not use configuration files.

---

## Stages

### 1. Process

**Tier:** CAPABLE

**Purpose:** Process documentation tasks using LLM capabilities
**Input:** Documentation content, instructions, or context to process
**Output:** Processed documentation or generated content

---

## Testing

```bash
# Run tests
pytest tests/unit/workflows/test_manage_docs.py -v

# Run with coverage
pytest tests/unit/workflows/test_manage_docs.py --cov

# Run specific test
pytest tests/unit/workflows/test_manage_docs.py::TestManageDocsWorkflow::test_workflow_execution_basic -v
```

---

## Cost Optimization

**Tier Distribution:**
- CHEAP: 0 stage(s)
- CAPABLE: 1 stage(s)
- PREMIUM: 0 stage(s)

---

## Examples

### Example 1: Basic Usage

```python
workflow = ManageDocsWorkflow()
result = await workflow.execute(
    content="Update the API documentation for the new endpoint",
    format="markdown"
)
```

### Example 2: With Custom Settings

```python
workflow = ManageDocsWorkflow(
    max_retries=3
)
result = await workflow.execute(
    content="Generate docstrings for the following code",
    style="google"
)
```

---

## Troubleshooting

### Common Issues

**Issue:** Workflow fails with "X not found"
**Solution:** Ensure the workflow is properly registered in pyproject.toml entry points

**Issue:** High costs
**Solution:** Consider adding conditional tier routing
---

## Related Workflows

- `doc-gen` - Document generation workflow
- `code-review` - Code review workflow

---

**Generated:** 2026-01-09
**Patterns:** single-stage
**Complexity:** SIMPLE
