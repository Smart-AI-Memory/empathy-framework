Run CrewAI-powered multi-agent tasks for complex workflows.

## Available Crews

The Empathy Framework integrates with CrewAI for multi-agent orchestration:

### 1. Code Review Crew
Three-agent pipeline for thorough code review:
- **Scanner Agent**: Initial code scan, identifies areas of concern
- **Analyzer Agent**: Deep analysis of flagged issues
- **Reporter Agent**: Synthesizes findings into actionable report

```bash
empathy crew run code-review --path ./src
```

### 2. Test Maintenance Crew
Keeps your test suite healthy:
- **Coverage Agent**: Identifies coverage gaps
- **Generator Agent**: Creates missing tests
- **Validator Agent**: Ensures tests pass and are meaningful

```bash
empathy crew run test-maintenance --path ./tests
```

### 3. Documentation Crew
Comprehensive documentation generation:
- **Outliner Agent**: Plans documentation structure
- **Writer Agent**: Generates content for each section
- **Editor Agent**: Polishes for consistency and clarity

```bash
empathy crew run documentation --source ./src --output ./docs
```

### 4. Security Audit Crew
Multi-layer security analysis:
- **Scanner Agent**: Static analysis, pattern matching
- **Analyzer Agent**: Deep vulnerability assessment
- **Remediator Agent**: Suggests fixes with code examples

```bash
empathy crew run security-audit --path ./src
```

## Commands

### List Available Crews
```bash
empathy crew list
```

### Run a Crew
```bash
empathy crew run <crew-name> [options]
```

### Check Crew Status
```bash
empathy crew status
```

### View Crew Execution Log
```bash
empathy crew log --last
```

## Execution Monitoring

When running a crew, show:
- Current agent and task
- Progress through pipeline
- Inter-agent handoffs
- Token usage per agent
- Total cost estimate

## Output Format

```
Crew: code-review
Status: Running

[1/3] Scanner Agent ✓ (2.3s, $0.002)
      Found: 12 areas of concern

[2/3] Analyzer Agent ⟳ (running...)
      Analyzing: src/auth/login.py

[3/3] Reporter Agent ○ (pending)

Progress: ████████░░ 67%
Est. Total Cost: $0.15
```

## Configuration

In `empathy.config.yml`:
```yaml
crews:
  max_iterations: 10
  verbose: true
  cost_limit: 1.00  # Max spend per crew run
```
