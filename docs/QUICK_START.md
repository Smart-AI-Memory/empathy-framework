# Quick Start - Empathy Framework

**Get started with Empathy Framework in 5 minutes**

**Version:** 4.6.2
**Last Updated:** January 21, 2026

---

## Installation (1 minute)

```bash
# Recommended: Install with developer tools
pip install empathy-framework[developer]

# Or minimal install
pip install empathy-framework
```

**What you get:**
- ✅ CLI tools
- ✅ VSCode extension support
- ✅ Multi-provider LLM routing
- ✅ Meta-orchestration (v4.0)
- ✅ 10 built-in workflows
- ✅ Local telemetry tracking

---

## Setup (2 minutes)

### 1. Add API Key

Set up at least one LLM provider:

```bash
# Option 1: Environment variable
export ANTHROPIC_API_KEY="sk-ant-..."

# Option 2: .env file (auto-detected)
echo 'ANTHROPIC_API_KEY=sk-ant-...' > .env

# Option 3: Interactive setup
python -m empathy_os.models.cli provider --interactive
```

**Supported providers:**
- **Anthropic** (Claude) - Recommended
- **OpenAI** (GPT-4, GPT-4o-mini)
- **Google** (Gemini)
- **Ollama** (Local models)

### 2. Verify Installation

```bash
# Check provider configuration
python -m empathy_os.models.cli provider

# Should show:
# Current provider: anthropic
# Available models: claude-opus-4, claude-sonnet-4, claude-haiku-4
# ✓ API key configured
```

---

## Your First Task (2 minutes)

### Option 1: Meta-Orchestration (v4.0 - Recommended)

Let the framework automatically compose agent teams:

```python
from empathy_os.orchestration import MetaOrchestrator

# Create orchestrator
orchestrator = MetaOrchestrator()

# Analyze your task
plan = orchestrator.analyze_and_compose(
    task="Review my code for security issues",
    context={"path": "./src"}
)

# See the plan
print(f"Strategy: {plan.strategy.value}")
print(f"Agents: {[a.role for a in plan.agents]}")
print(f"Estimated cost: ${plan.estimated_cost:.2f}")
```

**Output:**
```
Strategy: sequential
Agents: ['Security Auditor', 'Code Quality Reviewer']
Estimated cost: $1.20
```

### Option 2: Direct Workflow

Run a specific workflow directly:

```python
from empathy_os.workflows import SecurityAuditWorkflow

# Create workflow
workflow = SecurityAuditWorkflow(enable_cache=True)

# Execute (async)
import asyncio

async def audit():
    result = await workflow.execute(target_path="./src")

    print(f"Status: {result.status}")
    print(f"Found {len(result.findings)} issues:")

    for finding in result.findings[:5]:  # Show first 5
        print(f"  - [{finding.severity}] {finding.description}")

    print(f"\nCost: ${result.cost_report.total_cost:.4f}")
    print(f"Cache hit rate: {result.cost_report.cache_hit_rate:.1f}%")

asyncio.run(audit())
```

**Output:**
```
Status: success
Found 3 issues:
  - [HIGH] SQL query vulnerable to injection
  - [MEDIUM] Hardcoded API key in config.py
  - [LOW] Missing input validation in user_handler.py

Cost: $0.0850
Cache hit rate: 0.0%
```

### Option 3: CLI (Fastest)

```bash
# Meta-orchestration
empathy orchestrate release-prep

# Specific workflow
empathy workflow run security-audit --path ./src

# Check telemetry
empathy telemetry show
```

---

## What's Next?

### Learn More

- **[Meta-Orchestration Guide](./api-reference/meta-orchestration.md)** - v4.0 automatic agent composition
- **[Workflow Guide](./api-reference/workflows.md)** - 10 built-in workflows
- **[Developer Guide](./DEVELOPER_GUIDE.md)** - Building custom plugins
- **[Architecture Overview](./ARCHITECTURE.md)** - System design

### Common Next Steps

#### 1. Enable Multi-Provider (Cost Optimization)

```bash
# Use best model from all providers
python -m empathy_os.models.cli provider --set hybrid

# Save 34-86% on API costs (role-dependent)
```

[See Cost Analysis](./cost-analysis/COST_SAVINGS_BY_ROLE_AND_PROVIDER.md)

#### 2. Enable Response Caching

```bash
# Install semantic caching (optional, improves hit rate)
pip install empathy-framework[cache]

# Or use hash-only cache (no extra dependencies)
# Already enabled by default!
```

Caching provides:
- Up to 57% cache hit rate (semantic matching)
- 40% cost reduction on repeated tasks
- 99.8% faster on cache hits

[See Caching Guide](./caching/README.md)

#### 3. Track Your Savings

```bash
# View recent usage
empathy telemetry show

# Calculate savings vs all-PREMIUM baseline
empathy telemetry savings --days 30

# Export for analysis
empathy telemetry export --format csv --output usage.csv
```

All data stays local in `~/.empathy/telemetry/` (privacy-first)

#### 4. Install VSCode Extension

- Real-time dashboard
- One-click workflows
- Visual cost tracking
- Memory control panel

[Installation Guide](./guides/vscode-extension.md)

---

## Troubleshooting

### Issue: "No API key configured"

```bash
# Check environment
env | grep API_KEY

# Set key
export ANTHROPIC_API_KEY="sk-ant-..."

# Verify
python -m empathy_os.models.cli provider --check
```

### Issue: "ModuleNotFoundError: empathy_os"

```bash
# Install in development mode
pip install -e .[dev]

# Or regular install
pip install empathy-framework
```

### Issue: "All providers unavailable"

```bash
# Check provider status
python -m empathy_os.models.cli provider --check

# Try different provider
python -m empathy_os.models.cli provider --set openai
```

### Issue: Import warnings about deprecated wizards

```python
# DeprecationWarning: HealthcareWizard is deprecated...

# Fix: Use specialized plugin
pip install empathy-healthcare-wizards

# Or use empathy_software_plugin (built-in)
from empathy_software_plugin.wizards import SecurityAnalysisWizard
```

---

## Examples

### Example 1: Release Preparation

```python
from empathy_os.workflows.orchestrated_release_prep import (
    OrchestratedReleasePrepWorkflow
)

workflow = OrchestratedReleasePrepWorkflow(
    quality_gates={
        "min_coverage": 90.0,
        "max_critical_issues": 0,
    }
)

report = await workflow.execute(path=".")

if report.approved:
    print(f"✅ Release approved!")
else:
    print("❌ Blockers:")
    for blocker in report.blockers:
        print(f"  - {blocker}")
```

### Example 2: Boost Test Coverage

```python
from empathy_os.workflows.orchestrated_test_coverage import (
    OrchestratedTestCoverageWorkflow
)

workflow = OrchestratedTestCoverageWorkflow(target_coverage=90.0)
report = await workflow.execute(path="./src")

print(f"Coverage: {report.initial_coverage}% → {report.final_coverage}%")
print(f"Tests added: {report.tests_added}")
```

### Example 3: Custom Agent Composition

```python
from empathy_os.orchestration import MetaOrchestrator

orchestrator = MetaOrchestrator()

# Analyze with context
plan = orchestrator.analyze_and_compose(
    task="Prepare codebase for production deployment",
    context={
        "environment": "production",
        "deadline": "urgent",
        "priority_areas": ["security", "performance"],
    }
)

# Inspect plan
print(f"Strategy: {plan.strategy.value}")
for agent in plan.agents:
    print(f"  - {agent.role} ({agent.tier})")
```

---

## Next Steps

**Choose Your Path:**

### Path 1: Software Developer
→ [Software Development Workflows](./guides/software-development.md)
→ [Code Review & Testing](./api-reference/workflows.md)

### Path 2: Security Engineer
→ [Security Auditing](./guides/security-auditing.md)
→ [Vulnerability Scanning](./api-reference/workflows.md#securityauditworkflow)

### Path 3: DevOps Engineer
→ [Release Automation](./guides/release-automation.md)
→ [Dependency Management](./api-reference/workflows.md#dependencycheckworkflow)

### Path 4: Framework Contributor
→ [Developer Guide](./DEVELOPER_GUIDE.md)
→ [Architecture Overview](./ARCHITECTURE.md)

---

## Community & Support

- **Documentation:** https://smartaimemory.com/framework-docs/
- **GitHub:** https://github.com/Smart-AI-Memory/empathy-framework
- **Issues:** https://github.com/Smart-AI-Memory/empathy-framework/issues
- **Discussions:** https://github.com/Smart-AI-Memory/empathy-framework/discussions

---

**Welcome to Empathy Framework v4.6 - Claude Code Integration Era! 🎉**

**Last Updated:** January 21, 2026
**License:** Fair Source 0.9
