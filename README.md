# Empathy Framework

**AI-powered developer workflows with cost optimization and pattern learning.**

Run code review, debugging, testing, and release workflows from your terminal or Claude Code. Smart tier routing saves 34-86% on LLM costs.

[![PyPI](https://img.shields.io/pypi/v/empathy-framework?color=blue)](https://pypi.org/project/empathy-framework/)
[![Tests](https://img.shields.io/badge/tests-7%2C168%20passing%20(99.9%25)-brightgreen)](https://github.com/Smart-AI-Memory/empathy-framework/actions)
[![Python](https://img.shields.io/badge/python-3.10+-blue)](https://www.python.org)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue)](LICENSE)
[![Performance](https://img.shields.io/badge/performance-18x%20faster-success)](https://github.com/Smart-AI-Memory/empathy-framework/blob/main/CHANGELOG.md)

```bash
pip install empathy-framework[developer]
```

---

## 🎯 Transitioning to Claude-Native Architecture

**Empathy Framework is evolving to focus exclusively on Anthropic/Claude** to unlock features impossible with multi-provider abstraction:

- **📦 Prompt Caching:** 90% cost reduction on repeated prompts
- **📖 200K Context:** Largest context window available (vs 128K for competitors)
- **🧠 Extended Thinking:** See Claude's internal reasoning process
- **🔧 Advanced Tool Use:** Optimized for agentic workflows

**Timeline:**

- ✅ **v4.8.0 (Jan 2026):** Deprecation warnings for OpenAI/Google/Ollama providers
- ✅ **v5.0.0 (Jan 26, 2026):** Non-Anthropic providers removed (BREAKING - COMPLETE)
- ✅ **v5.0.2 (Jan 28, 2026):** Cost optimization suite with batch processing and caching monitoring

**Migration Guide:** [docs/CLAUDE_NATIVE.md](docs/CLAUDE_NATIVE.md)

---

## What's New in v5.1.0

**🤖 Multi-Agent Orchestration** - Full support for custom agents and Anthropic LLM agents:

- **Agent Coordination Dashboard** - Real-time monitoring with 6 coordination patterns:
  - Agent heartbeats and status tracking
  - Inter-agent coordination signals
  - Event streaming across agent workflows
  - Approval gates for human-in-the-loop
  - Quality feedback and performance metrics
  - Demo mode with test data generation

- **Custom Agents** - Build specialized agents for your workflow needs
- **LLM Agents from Anthropic** - Leverage Claude's advanced capabilities
- Dashboard accessible at `http://localhost:8000` with `python examples/dashboard_demo.py`

**🔐 Authentication Strategy System** - Intelligent routing between Claude subscriptions and Anthropic API:

```bash
# Interactive setup
python -m empathy_os.models.auth_cli setup

# View current configuration
python -m empathy_os.models.auth_cli status

# Get recommendation for a file
python -m empathy_os.models.auth_cli recommend src/module.py
```

**💰 Automatic Cost Optimization** - Workflows choose the best auth method:

- Small/medium modules (<2000 LOC) → Claude subscription (free)
- Large modules (>2000 LOC) → Anthropic API (pay for what you need)
- 7 workflows integrated: document-gen, test-gen, code-review, bug-predict, security-audit, perf-audit, release-prep
- Auth mode tracking in all workflow outputs for telemetry

**🧪 Comprehensive Testing** - 7 new integration tests for auth strategy:

- All workflows tested with auth enabled/disabled
- API and subscription mode verification
- Cost tracking validation

**📖 Documentation** - 950+ lines across 3 guides:

- [AUTH_STRATEGY_GUIDE.md](docs/AUTH_STRATEGY_GUIDE.md) - User guide for configuration
- [AUTH_CLI_IMPLEMENTATION.md](docs/AUTH_CLI_IMPLEMENTATION.md) - CLI command reference
- [AUTH_WORKFLOW_INTEGRATIONS.md](docs/AUTH_WORKFLOW_INTEGRATIONS.md) - Integration patterns

[See Full Changelog](CHANGELOG.md#510---2026-01-29)

---

## What's New in v5.0.2

**💰 50% Cost Savings with Batch API** - Process non-urgent tasks asynchronously:

```bash
empathy batch submit batch_requests.json  # Submit batch job
empathy batch status msgbatch_abc123      # Check progress
empathy batch results msgbatch_abc123 output.json  # Download results
```

Perfect for: log analysis, report generation, bulk classification, test generation

**📊 Precise Token Counting** - >98% accurate cost tracking:

- Integrated Anthropic's `count_tokens()` API for billing-accurate measurements
- 3-tier fallback: API → tiktoken (local) → heuristic
- Cache-aware cost calculation (25% write markup, 90% read discount)

**📈 Cache Performance Monitoring** - Track your 20-30% caching savings:

```bash
empathy cache stats           # Show hit rates and cost savings
empathy cache stats --verbose # Detailed token metrics
empathy cache stats --format json  # Machine-readable output
```

**🧭 Adaptive Routing Analytics** - Intelligent tier recommendations:

```bash
empathy routing stats <workflow>    # Performance metrics
empathy routing check --all         # Tier upgrade recommendations
empathy routing models --provider anthropic  # Compare models
```

**🔧 Dashboard Fixes** - All 6 agent coordination patterns now operational:
- Agent heartbeats displaying correctly
- Event streaming functional
- Coordination signals working
- Approval gates operational

[See Full Changelog](CHANGELOG.md#502---2026-01-28) | [Batch API Guide](docs/BATCH_API_GUIDE.md) | [User API Docs](docs/USER_API_DOCUMENTATION.md)

---

## What's New in v4.9.0

**⚡ 18x Faster Performance** - Massive performance gains through Phase 2 optimizations:

- **Redis Two-Tier Caching:** 2x faster memory operations (37,000x for cached keys)
- **Generator Expressions:** 99.9% memory reduction across 27 optimizations
- **Parallel Scanning:** Multi-core processing enabled by default (2-4x faster)
- **Incremental Scanning:** Git diff-based updates (10x faster)

**🧭 Natural Language Workflows** - Use plain English instead of workflow names:

```bash
/workflows "find security vulnerabilities"  # → security-audit
/workflows "check code performance"         # → perf-audit
/workflows "predict bugs"                   # → bug-predict
/plan "review my code"                      # → code-review
```

**📊 Real-World Performance:**

- Combined workflow: 3.59s → 0.2s (**18x faster**)
- Full scan: 3,472 files in 0.98s (was 3.59s)
- Redis cached operations: 37ms → 0.001ms

**🎯 Improved Navigation:**

- Split `/workflow` into `/workflows` (automated analysis) and `/plan` (planning/review)
- Clearer hub organization with better categorization
- Natural language routing matches intent to workflow

[See CHANGELOG.md](CHANGELOG.md) | [Performance Docs](docs/REDIS_OPTIMIZATION_SUMMARY.md)

---

## What's New in v4.7.0

**$0 Workflows via Skills** - Multi-agent workflows run through Claude Code's Task tool instead of API calls. No additional cost with your Claude subscription.

**Socratic Workflows** - Interactive discovery through guided questions. Workflows ask what you need rather than requiring upfront configuration.

**Security Hardened** - Fixed critical vulnerabilities (path traversal, JWT, SSRF).

**Hub-Based Commands** - Organized workflows into intuitive command hubs.

---

## Quick Start

### 1. Install

```bash
pip install empathy-framework[developer]
```

### 2. Configure

```bash
# Auto-detect API keys
python -m empathy_os.models.cli provider

# Or set explicitly
python -m empathy_os.models.cli provider --set anthropic
```

### 3. Use

**In Claude Code:**

```bash
/dev           # Developer tools (debug, commit, PR, review)
/testing       # Run tests, coverage, benchmarks
/workflows     # Automated analysis (security, bugs, perf)
/plan          # Planning, TDD, code review
/docs          # Documentation generation
/release       # Release preparation

# Natural language support:
/workflows "find security issues"
/plan "review my code"

# Direct tool access via MCP (v5.1.1+):
# Claude Code automatically discovers Empathy tools through the MCP server
# Just describe what you need in natural language:
"Run a security audit on src/"          → Invokes security_audit tool
"Generate tests for config.py"          → Invokes test_generation tool
"Check my auth configuration"           → Invokes auth_status tool
"Analyze performance bottlenecks"       → Invokes performance_audit tool
```

**MCP Server Integration (v5.1.1+):**

Empathy Framework now includes a Model Context Protocol (MCP) server that exposes all workflows as native Claude Code tools:

- **10 Tools Available:** security_audit, bug_predict, code_review, test_generation, performance_audit, release_prep, auth_status, auth_recommend, telemetry_stats, dashboard_status
- **Automatic Discovery:** No manual configuration needed - Claude Code finds tools via `.claude/mcp.json`
- **Natural Language Access:** Describe your need and Claude invokes the appropriate tool
- **Verification Hooks:** Automatic validation of Python/JSON files and workflow outputs

To verify MCP integration:

```bash
# Check server is running
echo '{"method":"tools/list","params":{}}' | PYTHONPATH=./src python -m empathy_os.mcp.server

# Restart Claude Code to load the MCP server
# Tools will appear in Claude's tool list automatically
```

See [.claude/MCP_TEST_RESULTS.md](.claude/MCP_TEST_RESULTS.md) for full integration details.

**CLI:**

```bash
empathy workflow run security-audit --path ./src
empathy workflow run test-coverage --target 90
empathy telemetry show  # View cost savings
```

**Python:**

```python
from empathy_os import EmpathyOS

async with EmpathyOS() as empathy:
    result = await empathy.level_2_guided(
        "Review this code for security issues"
    )
    print(result["response"])
```

---

## Command Hubs

Workflows are organized into hubs for easy discovery:

| Hub               | Command       | Description                                  |
| ----------------- | ------------- | -------------------------------------------- |
| **Developer**     | `/dev`        | Debug, commit, PR, code review, quality      |
| **Testing**       | `/testing`    | Run tests, coverage analysis, benchmarks     |
| **Documentation** | `/docs`       | Generate and manage documentation            |
| **Release**       | `/release`    | Release prep, security scan, publishing      |
| **Workflows**     | `/workflows`  | Automated analysis (security, bugs, perf)    |
| **Plan**          | `/plan`       | Planning, TDD, code review, refactoring      |
| **Utilities**     | `/utilities`  | Project init, dependencies, profiling        |
| **Learning**      | `/learning`   | Pattern learning and session evaluation      |
| **Context**       | `/context`    | State management and memory                  |
| **Agent**         | `/agent`      | Create and manage custom agents              |

**Natural Language Support:**

```bash
# Use plain English - intelligent routing matches your intent
/workflows "find security vulnerabilities"  # → security-audit
/workflows "check code performance"         # → perf-audit
/workflows "predict bugs"                   # → bug-predict
/plan "review my code"                      # → code-review
/plan "help me plan this feature"           # → planning

# Or use traditional workflow names
/workflows security-audit
/plan code-review
```

**Interactive menus:**

```bash
/dev                    # Show interactive menu
/dev "debug auth error" # Jump directly to debugging
/testing "run coverage" # Run coverage analysis
/release                # Start release preparation
```

---

## Socratic Method

Workflows guide you through discovery instead of requiring upfront configuration:

```text
You: /dev

Claude: What development task do you need?
  1. Debug issue
  2. Create commit
  3. PR workflow
  4. Quality check

You: 1

Claude: What error or unexpected behavior are you seeing?
```

**How it works:**

1. **Discovery** - Workflow asks targeted questions to understand your needs
2. **Context gathering** - Collects relevant code, errors, and constraints
3. **Dynamic agent creation** - Assembles the right team based on your answers
4. **Execution** - Runs with appropriate tier selection

**Create custom agents with Socratic guidance:**

```bash
/agent create    # Guided agent creation
/agent team      # Build multi-agent teams interactively
```

---

## Cost Optimization

### Skills = $0 (Claude Code)

When using Claude Code, workflows run as skills through the Task tool - **no API costs**:

```bash
/dev           # $0 - uses your Claude subscription
/testing       # $0
/release       # $0
/agent create  # $0
```

### API Mode (CI/CD, Automation)

For programmatic use, smart tier routing saves 34-86%:

| Tier    | Model               | Use Case                    | Cost        |
| ------- | ------------------- | --------------------------- | ----------- |
| CHEAP   | Haiku / GPT-4o-mini | Formatting, simple tasks    | ~$0.005     |
| CAPABLE | Sonnet / GPT-4o     | Bug fixes, code review      | ~$0.08      |
| PREMIUM | Opus / o1           | Architecture, complex design | ~$0.45      |

```bash
# Track API usage and savings
empathy telemetry savings --days 30
```

---

## Key Features

### Multi-Agent Workflows

```bash
# 4 parallel agents check release readiness
empathy orchestrate release-prep

# Sequential coverage improvement
empathy orchestrate test-coverage --target 90
```

### Response Caching

Up to 57% cache hit rate on similar prompts. Zero config needed.

```python
from empathy_os.workflows import SecurityAuditWorkflow

workflow = SecurityAuditWorkflow(enable_cache=True)
result = await workflow.execute(target_path="./src")
print(f"Cache hit rate: {result.cost_report.cache_hit_rate:.1f}%")
```

### Pattern Learning

Workflows learn from outcomes and improve over time:

```python
from empathy_os.orchestration.config_store import ConfigurationStore

store = ConfigurationStore()
best = store.get_best_for_task("release_prep")
print(f"Success rate: {best.success_rate:.1%}")
```

### Multi-Provider Support

```python
from empathy_llm_toolkit.providers import (
    AnthropicProvider,  # Claude
    OpenAIProvider,     # GPT-4
    GeminiProvider,     # Gemini
    LocalProvider,      # Ollama, LM Studio
)
```

---

## CLI Reference

```bash
# Provider configuration
python -m empathy_os.models.cli provider
python -m empathy_os.models.cli provider --set hybrid

# Workflows
empathy workflow list
empathy workflow run <workflow-name>

# Cost tracking
empathy telemetry show
empathy telemetry savings --days 30
empathy telemetry export --format csv

# Orchestration
empathy orchestrate release-prep
empathy orchestrate test-coverage --target 90

# Meta-workflows
empathy meta-workflow list
empathy meta-workflow run release-prep --real
```

---

## Install Options

```bash
# Individual developers (recommended)
pip install empathy-framework[developer]

# All LLM providers
pip install empathy-framework[llm]

# With caching (semantic similarity)
pip install empathy-framework[cache]

# Enterprise (auth, rate limiting)
pip install empathy-framework[enterprise]

# Healthcare (HIPAA compliance)
pip install empathy-framework[healthcare]

# Development
git clone https://github.com/Smart-AI-Memory/empathy-framework.git
cd empathy-framework && pip install -e .[dev]
```

---

## Environment Setup

```bash
# At least one provider required
export ANTHROPIC_API_KEY="sk-ant-..."
export OPENAI_API_KEY="sk-..."
export GOOGLE_API_KEY="..."

# Optional: Redis for memory
export REDIS_URL="redis://localhost:6379"
```

---

## VSCode Extension

Install the Empathy VSCode extension for:

- **Dashboard** - Health score, costs, patterns
- **One-Click Workflows** - Run from command palette
- **Memory Panel** - Manage Redis and patterns
- **Cost Tracking** - Real-time savings display

---

## Documentation

- [Quick Start Guide](docs/quickstart.md)
- [CLI Reference](docs/cli-reference.md)
- [Testing Guide](docs/testing-guide.md)
- [Keyboard Shortcuts](docs/keyboard-shortcuts.md)
- [Full Documentation](https://smartaimemory.com/framework-docs/)

---

## Security

- Path traversal protection on all file operations
- JWT authentication with rate limiting
- PII scrubbing in telemetry
- HIPAA/GDPR compliance options
- **Automated security scanning** with 82% accuracy (Phase 3 AST-based detection)

See [SECURITY.md](SECURITY.md) for vulnerability reporting.

### Security Scanning

**Automated security scanning in CI/CD** - 82% accuracy, blocks critical issues:

```bash
# Run security audit locally
empathy workflow run security-audit

# Scan specific directory
empathy workflow run security-audit --input '{"path":"./src"}'
```

**Documentation:**

- **[Developer Workflow Guide](docs/DEVELOPER_SECURITY_WORKFLOW.md)** - Quick reference for handling security findings (all developers)
- **[CI/CD Integration Guide](docs/CI_SECURITY_SCANNING.md)** - Complete setup and troubleshooting (DevOps, developers)
- **[Scanner Architecture](docs/SECURITY_SCANNER_ARCHITECTURE.md)** - Technical implementation details (engineers, architects)
- **[Remediation Process](docs/SECURITY_REMEDIATION_PROCESS.md)** - 3-phase methodology for improving scanners (security teams, leadership)
- **[API Reference](docs/api-reference/security-scanner.md)** - Complete API documentation (developers extending scanner)

**Key achievements:**

- 82.3% reduction in false positives (350 → 62 findings)
- 16x improvement in scanner accuracy
- <15 minute average fix time for critical issues
- Zero critical vulnerabilities in production code

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

---

## License

**Apache License 2.0** - Free and open source for everyone. Use it, modify it, build commercial products with it. [Details →](LICENSE)

---

## Acknowledgements

This project stands on the shoulders of giants. We are deeply grateful to the open source community and all the amazing projects that make this framework possible.

**[View Full Acknowledgements →](ACKNOWLEDGEMENTS.md)**

Special thanks to:

- **[Anthropic](https://www.anthropic.com/)** - For Claude AI and the Model Context Protocol
- **[LangChain](https://github.com/langchain-ai/langchain)** - Agent framework powering our meta-orchestration
- **[FastAPI](https://github.com/tiangolo/fastapi)** - Modern Python web framework
- **[pytest](https://github.com/pytest-dev/pytest)** - Testing framework making quality assurance effortless

And to all 50+ open source projects we depend on. [See the complete list →](ACKNOWLEDGEMENTS.md)

Want to contribute? See [CONTRIBUTORS.md](CONTRIBUTORS.md)

---

**Built by [Smart AI Memory](https://smartaimemory.com)** · [Docs](https://smartaimemory.com/framework-docs/) · [Examples](examples/) · [Issues](https://github.com/Smart-AI-Memory/empathy-framework/issues)
