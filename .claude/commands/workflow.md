Run an Empathy Framework workflow interactively.

## Available Workflows

| Workflow | Description | Tier Usage |
|----------|-------------|------------|
| `code-review` | Review code for quality, bugs, security | Capable |
| `bug-predict` | Predict potential bugs using pattern analysis | Cheap → Capable |
| `test-gen` | Generate test cases for functions | Capable → Premium |
| `doc-gen` | Generate documentation | Cheap → Capable → Premium |
| `security-audit` | Security vulnerability analysis | Premium |
| `perf-audit` | Performance analysis and recommendations | Capable |
| `refactor-plan` | Plan safe refactoring steps | Capable → Premium |
| `dependency-check` | Check dependency health and CVEs | Cheap |
| `health-check` | Project health assessment | Cheap |
| `pr-review` | Pull request review | Capable |

## Usage

### List Available Workflows
```bash
empathy workflow list
```

### Run a Workflow
```bash
# General syntax
empathy workflow run <workflow-name> --input '{"path": "./src"}'

# Examples:
empathy workflow run code-review --input '{"files": ["src/main.py"]}'
empathy workflow run bug-predict --input '{"path": "./src"}'
empathy workflow run test-gen --input '{"file": "src/utils.py", "function": "calculate_total"}'
empathy workflow run doc-gen --input '{"source": "./src", "doc_type": "api_reference"}'
```

### Check Workflow Status
```bash
empathy workflow status
```

## Interactive Mode

Ask the user which workflow they want to run:

1. **What do you want to analyze?**
   - Code quality → `code-review`
   - Potential bugs → `bug-predict`
   - Security issues → `security-audit`
   - Performance → `perf-audit`

2. **What's the target?**
   - Specific file(s)
   - Directory
   - Entire project

3. **Run the workflow** and show progress

## Output

Show:
- Workflow execution progress (stages)
- Cost incurred for each tier
- Final results/recommendations
- Links to detailed output files if generated
