# Empathy Framework

**The Claude-optimized AI collaboration framework with breakthrough meta-orchestration - agents that compose themselves.**

🎯 **v4.6.4: Optimized for Claude Code** - Built and tested extensively with Claude Code for the best experience. 10+ slash commands, automatic pattern learning, prompt caching (90% savings), true async I/O. **Full multi-LLM support** - works seamlessly with OpenAI, Gemini, and local models.

[![PyPI](https://img.shields.io/pypi/v/empathy-framework)](https://pypi.org/project/empathy-framework/)
[![Tests](https://img.shields.io/badge/tests-4%2C000%2B%20passing-brightgreen)](https://github.com/Smart-AI-Memory/empathy-framework/actions)
[![Coverage](https://img.shields.io/badge/coverage-68%25-yellow)](https://github.com/Smart-AI-Memory/empathy-framework)
[![License](https://img.shields.io/badge/license-Fair%20Source%200.9-blue)](https://github.com/Smart-AI-Memory/empathy-framework/blob/main/LICENSE)
[![Python](https://img.shields.io/badge/python-3.10+-blue)](https://www.python.org)
[![Security](https://img.shields.io/badge/security-hardened-green)](https://github.com/Smart-AI-Memory/empathy-framework/blob/main/SECURITY.md)

```bash
pip install empathy-framework[developer]  # Lightweight for individual developers
```

## What's New in v4.6.4 🎯 **OPTIMIZED FOR CLAUDE CODE**

### **Built for Claude Code, Works Everywhere**

**v4.6.4** is optimized and extensively tested with Claude Code for the best development experience, while maintaining full compatibility with OpenAI, Gemini, and local models.

**Cost-Saving Features:**

- 📉 **Prompt Caching** - 90% reduction on repeated operations (enabled by default)
- ⚡ **True Async I/O** - `AsyncAnthropic` for parallel efficiency
- 🎯 **Slash Commands** - 10+ structured workflows that reduce token waste
- 🧠 **Auto Pattern Learning** - Stop re-explaining the same codebase

**New Slash Commands:**

| Command | What It Does |
|---------|--------------|
| `/debug` | Bug investigation with pattern matching |
| `/refactor` | Safe refactoring with test verification |
| `/review` | Code review against project standards |
| `/review-pr` | PR review with APPROVE/REJECT verdict |
| `/deps` | Dependency audit (CVE, licenses, outdated) |
| `/profile` | Performance profiling and bottlenecks |
| `/benchmark` | Performance regression tracking |
| `/explain` | Code architecture explanation |
| `/commit` | Well-formatted git commits |
| `/pr` | Structured PR creation |

**Multi-LLM Support:**

```python
# All providers supported with async clients
from empathy_llm_toolkit.providers import (
    AnthropicProvider,  # Claude (primary, optimized)
    OpenAIProvider,     # GPT-4, GPT-3.5
    GeminiProvider,     # Gemini 1.5, 2.0
    LocalProvider,      # Ollama, LM Studio
)
```

---

## What's New in v4.6.0 💰 **$0 COST AI WORKFLOWS**

### **Run Agent Teams Free with Any Claude Code Subscription**

**v4.6** revolutionizes how you use Empathy Framework - all multi-agent workflows now run **at no additional cost** when you have any Claude Code subscription.

**Key Features:**

- 💰 **$0 Execution** - Agent teams use Claude Code's Task tool instead of API calls
- 🎓 **Socratic Agent Creation** - `/create-agent` and `/create-team` guide you through building custom agents
- 🧠 **Memory Enhancement** - Optional short-term and long-term memory for agents that learn
- 🧹 **Streamlined Skills** - 13 clean skills that work without API keys

**Quick Start (Claude Code):**

```
/create-agent     # Walk through creating a custom AI agent
/create-team      # Build a multi-agent team with guided questions
/release-prep     # Run 4-agent release readiness check ($0)
/test-coverage    # 3-agent coverage analysis ($0)
```

**Available Skills (13 total):**

| Skill | Description | Cost |
|-------|-------------|------|
| `/create-agent` | Socratic guide to build custom agents | $0 |
| `/create-team` | Build multi-agent teams interactively | $0 |
| `/release-prep` | Security, coverage, quality, docs check | $0 |
| `/test-coverage` | Coverage gap analysis + suggestions | $0 |
| `/test-maintenance` | Find stale/flaky tests | $0 |
| `/manage-docs` | Keep docs in sync with code | $0 |
| `/feature-overview` | Generate technical documentation | $0 |
| `/security-scan` | Run pytest, ruff, black checks | $0 |
| `/test` | Run test suite with summary | $0 |
| `/status` | Show project dashboard | $0 |
| `/publish` | PyPI publishing guide | $0 |
| `/init` | Initialize new Empathy project | $0 |
| `/memory` | Memory system management | $0 |

**Enterprise API Mode** (optional):

```bash
# For CI/CD, cron jobs, or programmatic control
empathy meta-workflow run release-prep --real --use-defaults
```

---

## What's New in v4.5.0 🖥️ **VS CODE INTEGRATION**

### **Rich HTML Reports for Agent Team Execution**

**v4.5** adds VS Code webview integration with rich HTML reports, Quick Run mode, and JSON output for programmatic workflows.

**Key Features:**

- 📊 **MetaWorkflowReportPanel** - Rich HTML webview displaying agent results with collapsible sections
- ⚡ **Quick Run Mode** - Execute with defaults, see results in beautiful reports
- 🔧 **CLI JSON Output** - `--json` flag for programmatic consumption
- 🎨 **Agent Cards** - Tier badges, status indicators, cost breakdowns

**Quick Start (VS Code):**

1. Open Command Palette (`Cmd+Shift+P`)
2. Run "Empathy: Run Meta-Workflow"
3. Select "Quick Run (Webview Report)"
4. View rich HTML report with agent results

---

## What's New in v4.4.0 🚀 **PRODUCTION-READY AGENT TEAMS**

### **Real LLM Execution with Cost Tracking**

**v4.4** brings production-ready agent teams with real Claude model execution, accurate cost tracking, and skill-based invocation.

**Breakthrough Features:**

- 🤖 **Real LLM Execution** - Agents execute with actual Claude API calls
- 💰 **Accurate Cost Tracking** - Token counting from real API usage
- 📈 **Progressive Tier Escalation** - CHEAP → CAPABLE → PREMIUM with actual execution
- 🎯 **Skill-based Invocation** - Use `/release-prep`, `/test-coverage`, `/manage-docs` in Claude Code

**Quick Start (CLI):**

```bash
# Run release preparation agent team
empathy meta-workflow run release-prep --real

# Natural language - describe what you need
empathy meta-workflow ask "prepare my code for release" --auto
```

---

## Meta-Workflow System 🤖 (v4.2+)

### **Intelligent Workflow Orchestration Through Forms + Dynamic Agents**

**The breakthrough:** The meta-workflow system combines Socratic forms (interactive questions), dynamic agent team creation, and pattern learning for self-improving workflows.

**How it works:**

1. 🎯 **Template Selection** - Choose from pre-built workflow templates (e.g., `python_package_publish`)
2. 📝 **Socratic Forms** - Answer interactive questions about your workflow requirements
3. 🤖 **Dynamic Agent Creation** - System generates optimized agent team based on your responses
4. ⚡ **Progressive Execution** - Agents execute with tier escalation (cheap → capable → premium)
5. 🧠 **Pattern Learning** - System learns from outcomes to optimize future workflows

**Quick Start:**

```bash
# Run meta-workflow with interactive form
empathy meta-workflow run python_package_publish

# View pattern learning insights
empathy meta-workflow analytics python_package_publish

# List historical executions
empathy meta-workflow list-runs
```

**Example workflow:**

```python
from empathy_os.meta_workflows import TemplateRegistry, MetaWorkflow, FormResponse

# Load template
registry = TemplateRegistry()
template = registry.load_template("python_package_publish")

# Create workflow
workflow = MetaWorkflow(template=template)

# Execute with form responses
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

print(f"✅ Created {len(result.agents_created)} agents")
print(f"💰 Total cost: ${result.total_cost:.2f}")
```

**Key Features:**

- ✅ **Interactive forms** via `AskUserQuestion` (batched, max 4 at a time)
- ✅ **Dynamic agent generation** from templates based on responses
- ✅ **Hybrid storage** - files (persistent) + memory (semantic queries)
- ✅ **Pattern learning** - analyzes historical executions for optimization
- ✅ **7 CLI commands** - list, run, analytics, show, export, validate
- ✅ **Security hardened** - OWASP Top 10 compliant, AST-verified

---

## What's in v4.0.0 🎭 **META-ORCHESTRATION**

### **AI Agents That Compose Themselves**

**The concept:** Instead of manually wiring agent workflows, v4.0 introduces a meta-orchestration system that analyzes tasks, selects optimal agent teams, chooses composition patterns, and learns from outcomes.

**What this means:**

- 🧠 **Automatic task analysis** → Determines complexity, domain, required capabilities
- 🤝 **Dynamic team composition** → Selects optimal agents from 7 pre-built templates
- 📐 **Intelligent strategy selection** → Chooses from 6 composition patterns (Sequential, Parallel, Debate, Teaching, Refinement, Adaptive)
- 📚 **Self-learning** → Saves successful compositions and improves over time
- ⚡ **Production-ready workflows** → Release Prep (parallel validation), Test Coverage Boost (sequential improvement)

### Quick Start

**Release preparation with 4 parallel agents:**

```bash
empathy orchestrate release-prep
```

Automatically runs:

- **Security Auditor** (vulnerability scan)
- **Test Coverage Analyzer** (gap analysis)
- **Code Quality Reviewer** (best practices)
- **Documentation Writer** (completeness check)

**Boost test coverage to 90%:**

```bash
empathy orchestrate test-coverage --target 90
```

Sequential workflow:

1. **Coverage Analyzer** → Identify gaps
2. **Test Generator** → Create tests
3. **Test Validator** → Verify coverage

### Python API

```python
from empathy_os.workflows.orchestrated_release_prep import (
    OrchestratedReleasePrepWorkflow
)

# Create workflow with custom quality gates
workflow = OrchestratedReleasePrepWorkflow(
    quality_gates={
        "min_coverage": 90.0,
        "max_critical_issues": 0,
    }
)

# Execute
report = await workflow.execute(path=".")

if report.approved:
    print(f"✅ Release approved! (confidence: {report.confidence})")
else:
    for blocker in report.blockers:
        print(f"❌ {blocker}")
```

### 6 Composition Patterns

The meta-orchestrator automatically selects the best pattern:

1. **Sequential** (A → B → C) - Pipeline processing
2. **Parallel** (A ‖ B ‖ C) - Independent validation
3. **Debate** (A ⇄ B ⇄ C → Synthesis) - Consensus building
4. **Teaching** (Junior → Expert) - Cost optimization
5. **Refinement** (Draft → Review → Polish) - Iterative improvement
6. **Adaptive** (Classifier → Specialist) - Right-sizing

### Learning System

Successful compositions are saved and improved over time:

```python
from empathy_os.orchestration.config_store import ConfigurationStore

store = ConfigurationStore()

# Find best composition for task
best = store.get_best_for_task("release_prep")
print(f"Success rate: {best.success_rate:.1%}")

# Reuse proven composition
agents = [get_template(a["role"]) for a in best.agents]
```

**Documentation:**

- [Meta-Orchestration User Guide](https://github.com/Smart-AI-Memory/empathy-framework/blob/main/docs/ORCHESTRATION_USER_GUIDE.md) - Complete guide with examples
- [API Reference](https://github.com/Smart-AI-Memory/empathy-framework/blob/main/docs/ORCHESTRATION_API.md) - All classes and methods
- [Examples](https://github.com/Smart-AI-Memory/empathy-framework/tree/main/examples/orchestration/) - Working code samples

**Features:**

- ✅ **7 pre-built agent templates** (security, testing, docs, etc.)
- ✅ **Automatic strategy selection** based on task analysis
- ✅ **Quality gates enforcement** with detailed reporting
- ✅ **Configuration store** learns from outcomes
- ✅ **Cost optimization** via tier selection (CHEAP → CAPABLE → PREMIUM)

---

### Previous Releases

#### v3.9.0

### 🔒 **Security Hardening: 174 Security Tests (Up from 14)**

**Production-ready security with comprehensive file path validation across the entire framework.**

- ✅ **6 modules secured** with Pattern 6 (File Path Validation)
- ✅ **13 file write operations** validated to prevent path traversal (CWE-22)
- ✅ **174 security tests** (100% passing) - up from 14 tests (+1143% increase)
- ✅ **Zero blind exception handlers** - all errors now properly typed and logged

```python
# All file writes now validated for security
from empathy_os.config import EmpathyConfig

config = EmpathyConfig(user_id="alice")
config.to_yaml("/etc/passwd")  # ❌ ValueError: Cannot write to system directory
config.to_yaml("./empathy.yml")  # ✅ Safe write
```

**Attack vectors blocked:**

- Path traversal: `../../../etc/passwd` → `ValueError`
- Null byte injection: `config\x00.json` → `ValueError`
- System directory writes: `/etc`, `/sys`, `/proc`, `/dev` → All blocked

See [SECURITY.md](https://github.com/Smart-AI-Memory/empathy-framework/blob/main/SECURITY.md) for complete security documentation.

### 🛡️ **Exception Handling Improvements**

**Better error messages with graceful degradation.**

- Fixed 8 blind `except Exception:` handlers in workflow base
- Specific exception types for better debugging
- Enhanced error logging while maintaining graceful degradation
- All intentional broad catches documented with design rationale

---

#### v3.8.3

### 🎯 **Transparent Cost Claims: Honest Role-Based Savings (34-86%)**

**Real savings depend on your work role.** Architects using 60% PREMIUM tasks see 34% savings, while junior devs see 86%. See [role-based analysis](https://github.com/Smart-AI-Memory/empathy-framework/blob/main/docs/cost-analysis/COST_SAVINGS_BY_ROLE_AND_PROVIDER.md) for your specific case.

### 🚀 **Intelligent Response Caching: Up to 57% Hit Rate (Benchmarked)**

**Hash-only cache**: 100% hit rate on identical prompts, ~5μs lookups
**Hybrid cache**: Up to 57% hit rate on semantically similar prompts (measured on security audit workflow)

```python
from empathy_os.cache import create_cache

# Hash-only mode (fast, exact matches)
cache = create_cache(cache_type="hash")

# Hybrid mode (semantic similarity)
cache = create_cache(cache_type="hybrid", similarity_threshold=0.95)
```

See [caching docs](https://github.com/Smart-AI-Memory/empathy-framework/blob/main/docs/caching/) for benchmarks and configuration.

### 📊 **Local Usage Telemetry: Track Your Real Savings**

Track your actual cost savings vs baseline without sending data to external servers.

```bash
# View recent usage
empathy telemetry show

# Calculate your savings vs all-PREMIUM baseline
empathy telemetry savings --days 30

# Compare time periods
empathy telemetry compare --period1 7 --period2 30

# Export for analysis
empathy telemetry export --format csv --output usage.csv
```

**Privacy**: All data stored locally in `~/.empathy/telemetry/`. No data sent to external servers.

---

#### v3.7.0

#### 🚀 **XML-Enhanced Prompting: 15-35% Token Reduction + Graceful Validation**

**Slash your API costs and eliminate response parsing errors with production-ready XML enhancements.**

#### Context Window Optimization — **Save 15-35% on Every Request**

```python
from empathy_os.optimization import ContextOptimizer, CompressionLevel

optimizer = ContextOptimizer(CompressionLevel.MODERATE)
optimized_prompt = optimizer.optimize(your_xml_prompt)
# Achieves 15-25% token reduction automatically
```

- **Tag compression**: `<thinking>` → `<t>`, `<answer>` → `<a>` (15+ common tags)
- **Whitespace optimization**: Removes excess whitespace while preserving structure
- **Redundancy elimination**: Strips "Please note that", "Make sure to", etc.
- **Real-world impact**: Integration tests achieved **49.7% reduction** on typical prompts
- **Bidirectional**: Full decompression to restore original tag names

#### XML Validation — **Never Crash on Malformed Responses Again**

```python
from empathy_os.validation import validate_xml_response

result = validate_xml_response(llm_response)
if result.is_valid:
    data = result.parsed_data
else:
    # Fallback extraction worked - you still get partial data
    data = result.parsed_data or {}
```

- **Graceful fallback parsing**: Regex extraction when XML is malformed
- **Optional XSD validation**: Full schema validation with lxml
- **Schema caching**: Performance optimization for repeated validations
- **25 comprehensive tests**: Covers edge cases, malformed input, and XSD validation

#### Migration Made Easy

See [XML_WORKFLOW_MIGRATION_GUIDE.md](XML_WORKFLOW_MIGRATION_GUIDE.md) for complete migration guide with:

- XMLAgent/XMLTask patterns with before/after examples
- Configuration options (`config.xml.use_xml_structure`)
- Benefits: **40-60% fewer misinterpretations**, **20-30% fewer retries**

**Test Coverage**: **229 new tests** (86 XML enhancement + 143 robustness) — **100% passing**

---

## What's New in v3.6.0

### 💡 **Finally! Error Messages That Actually Help You**

**No more cryptic `NotImplementedError` when extending the framework!**

We completely rewrote error messages across **5 base classes**. Now when you're building plugins or extensions, you get:

✅ **Exactly which method** you need to implement
✅ **Which base class** to extend
✅ **Real working examples** from the codebase to copy
✅ **Clear explanations** of what each method should return

**Before** (frustrating 😤):

```python
NotImplementedError
# ...now what? Time to dig through source code for 30 minutes
```

**After** (helpful 🎯):

```python
NotImplementedError: BaseLinterParser.parse() must be implemented.
Create a subclass of BaseLinterParser and implement the parse() method.
See ESLintParser, PylintParser, or MyPyParser for examples.
# Perfect! Now I know exactly what to do
```

#### Plus: 9 Integration TODOs Now Link to Working Code

- **Want to add compliance tracking?** → See `ComplianceDatabase` class (agents/compliance_db.py)
- **Need multi-channel notifications?** → See `NotificationService` class (agents/notifications.py)
- **Wondering about MemDocs integration?** → We documented why local cache works better (with rationale)
- **Need secure document storage?** → S3/Azure/SharePoint recommendations with HIPAA requirements

**Impact**: Onboard new contributors in **minutes instead of hours**. Build your first plugin in **one sitting**.

---

### 🔐 Production-Grade Security & Compliance

#### Secure Authentication System ✅ *Deployed in Backend API*

- **Bcrypt password hashing** with cost factor 12 (industry standard 2026)
- **JWT tokens** with 30-minute expiration and automatic refresh
- **Rate limiting**: 5 failed attempts = 15-minute lockout (prevents brute force)
- **18 comprehensive security tests** covering all attack vectors
- **Status**: Fully integrated into `backend/api/wizard_api.py`

#### HIPAA/GDPR Compliance Database 🛠️ *Infrastructure Ready*

- **Append-only architecture** (INSERT only, no UPDATE/DELETE) - satisfies regulators
- **Immutable audit trail** for healthcare and enterprise compliance
- **Compliance gap detection** with severity classification
- **12 tests** ensuring regulatory compliance
- **Status**: Production-ready code with [integration points documented](agents/compliance_db.py). See [compliance_anticipation_agent.py](agents/compliance_anticipation_agent.py) for usage examples.

#### Multi-Channel Notification System 🛠️ *Infrastructure Ready*

- **Email** (SMTP), **Slack** (webhooks), **SMS** (Twilio)
- **Graceful fallback** when channels unavailable
- **Smart routing**: SMS only for critical alerts (cost optimization)
- **10 tests** covering all notification scenarios
- **Status**: Production-ready code with [integration points documented](agents/notifications.py). See TODOs in compliance agent for usage examples.

---

### Previous: Project Indexing & Test Suite Expansion (v3.5.4)

- **Project Indexing System** — JSON-based file tracking with automatic structure scanning, metadata tracking, and CrewAI integration
- **5,603 Tests** — Comprehensive test coverage at 64% with 30+ new test modules
- **BaselineManager Fix** — Resolved test isolation bug affecting suppression system

### Memory API Security Hardening (v3.5.0)

- **Input Validation** — Pattern IDs, agent IDs, and classifications validated to prevent path traversal and injection attacks
- **API Key Authentication** — Bearer token and X-API-Key header support with SHA-256 hash comparison
- **Rate Limiting** — Per-IP sliding window rate limiting (100 req/min default)
- **HTTPS/TLS Support** — Optional SSL certificate configuration for encrypted connections
- **CORS Restrictions** — Configurable allowed origins (localhost-only by default)
- **Request Size Limits** — 1MB body limit to prevent DoS attacks

### Previous (v3.4.x)

- **Trust Circuit Breaker** — Automatic degradation when model reliability drops
- **Pattern Catalog System** — Searchable pattern library with similarity matching
- **Memory Control Panel** — VSCode sidebar for Redis and pattern management

### Previous (v3.3.x)

- **Formatted Reports** — Every workflow includes `formatted_report` with consistent structure
- **Enterprise-Safe Doc-Gen** — Auto-scaling tokens, cost guardrails, file export
- **Unified Typer CLI** — One `empathy` command with Rich output
- **Python 3.13 Support** — Test matrix covers 3.10-3.13 across all platforms

### Previous (v3.1.x)

- **Smart Router** — Natural language wizard dispatch: "Fix security in auth.py" → SecurityWizard
- **Memory Graph** — Cross-wizard knowledge sharing across sessions
- **Auto-Chaining** — Wizards automatically trigger related wizards
- **Resilience Patterns** — Retry, Circuit Breaker, Timeout, Health Checks

### Previous (v3.0.x)

- **Multi-Model Provider System** — Anthropic, OpenAI, Google Gemini, Ollama, or Hybrid mode
- **34-86% Cost Savings** — Smart tier routing varies by role: architects 34%, senior devs 65%, junior devs 86%*
- **VSCode Dashboard** — 10 integrated workflows with input history persistence

*See [Cost Savings Analysis](https://github.com/Smart-AI-Memory/empathy-framework/blob/main/docs/cost-analysis/COST_SAVINGS_BY_ROLE_AND_PROVIDER.md) for your specific use case

---

## Quick Start (2 Minutes)

### 1. Install

**Individual Developers (Recommended):**

```bash
pip install empathy-framework[developer]
```

**Teams/Enterprises (Backend + Auth):**

```bash
pip install empathy-framework[enterprise]
```

**Healthcare Organizations (HIPAA/GDPR Compliance):**

```bash
pip install empathy-framework[healthcare]
```

<details>
<summary><b>What's the difference?</b></summary>

- **`[developer]`** - Lightweight install for individual developers. Includes CLI tools, VSCode extension, LLM providers, agents. **No backend server needed.**

- **`[enterprise]`** - Everything in `[developer]` plus backend API server with authentication (bcrypt, JWT, rate limiting). For teams deploying to production.

- **`[healthcare]`** - Everything in `[enterprise]` plus HIPAA/GDPR compliance database, redis, and healthcare-specific plugins. Only needed for regulated industries.

**Most developers should use `[developer]`** - it's fast to install and has everything you need for software development.

</details>

### 2. Configure Provider

```bash
# Auto-detect your API keys and configure
python -m empathy_os.models.cli provider

# Or set explicitly
python -m empathy_os.models.cli provider --set anthropic
python -m empathy_os.models.cli provider --set hybrid  # Best of all providers
```

### 3. Use It

```python
from empathy_os import EmpathyOS

async with EmpathyOS() as empathy:
    # Level 2: Guided - asks clarifying questions
    result = await empathy.level_2_guided(
        "Review this code for security issues"
    )

    print(result["questions"])        # Clarifying questions asked
    print(result["response"])         # Analysis response
    print(result["next_steps"])       # Recommended actions
```

### 4. Track Your Savings

```bash
# View recent usage
empathy telemetry show

# Calculate your savings vs all-PREMIUM baseline
empathy telemetry savings --days 30

# Compare time periods
empathy telemetry compare --period1 7 --period2 30

# Export for analysis
empathy telemetry export --format csv --output usage.csv
```

**Privacy**: All data stored locally in `~/.empathy/telemetry/`. No data sent to external servers.

---

## Why Empathy?

| Feature | Empathy | SonarQube | GitHub Copilot |
|---------|---------|-----------|----------------|
| **Predicts future issues** | 30-90 days ahead | No | No |
| **Persistent memory** | Redis + patterns | No | No |
| **Multi-provider support** | Claude, GPT-4, Gemini, Ollama | N/A | GPT only |
| **Cost optimization** | 34-86% savings* | N/A | No |
| **Your data stays local** | Yes | Cloud | Cloud |
| **Free for small teams** | ≤5 employees | No | No |

---

## What's New in v3.8.0

### 🚀 **Intelligent Response Caching: Benchmarked Performance**

**Stop paying full price for repeated LLM calls. Measured results: up to 99.8% faster, 40% cost reduction on test generation, 57% cache hit rate on security audits.**

#### Hybrid Cache: Hash + Semantic Matching

```python
from empathy_os.workflows import SecurityAuditWorkflow

# That's it - caching auto-configured!
workflow = SecurityAuditWorkflow(enable_cache=True)
result = await workflow.execute(target_path="./src")

# Check savings
print(f"Cost: ${result.cost_report.total_cost:.4f}")
print(f"Cache hit rate: {result.cost_report.cache_hit_rate:.1f}%")
print(f"Savings: ${result.cost_report.savings_from_cache:.4f}")
```

**Real Results** (v3.8.0 benchmark - see [CACHING_BENCHMARK_REPORT.md](CACHING_BENCHMARK_REPORT.md)):

- **Hash-only cache**: 30.3% average hit rate across 12 workflows, up to 99.8% faster (code review: 17.8s → 0.03s)
- **Hybrid cache**: Up to 57% hit rate on similar prompts (security audit - benchmarked)
- **Cost reduction**: 40% on test-generation workflow (measured)

#### Two Cache Strategies

**Hash-Only Cache** (Default - Zero Dependencies):
- Perfect for CI/CD and testing
- 100% hit rate on identical prompts
- ~5μs lookup time
- No ML dependencies needed

**Hybrid Cache** (Semantic Matching):

- Up to 57% hit rate on similar prompts (benchmarked)
- Understands intent, not just text
- Install: `pip install empathy-framework[cache]`
- Best for development and production

#### Automatic Setup

Framework detects your environment and configures optimal caching:

```python
# First run: Framework checks for sentence-transformers
# - Found? Uses hybrid cache (semantic matching, up to 57% hit rate)
# - Missing? Prompts: "Install for semantic matching? (y/n)"
# - Declined? Falls back to hash-only (100% hit rate on identical prompts)
# - Any errors? Disables gracefully, workflow continues

# Subsequent runs: Cache just works
```

#### The Caching Paradox: Adaptive Workflows

**Discovered during v3.8.0 development**: Some workflows (Security Audit, Bug Prediction) cost MORE on Run 2 with cache enabled - and that's a FEATURE.

**Why?** Adaptive workflows use cache to free up time for deeper analysis:

```
Security Audit without cache:
Run 1: $0.11, 45 seconds - surface scan finds 3 issues

Security Audit with cache:
Run 2: $0.13, 15 seconds - cache frees 30s for deep analysis
       → Uses saved time for PREMIUM tier vulnerability research
       → Finds 7 issues including critical SQLi we missed
       → Extra $0.02 cost = prevented security breach
```

**Result**: Cache makes workflows SMARTER, not just cheaper.

See [Adaptive Workflows Documentation](https://github.com/Smart-AI-Memory/empathy-framework/blob/main/docs/caching/ADAPTIVE_WORKFLOWS.md) for full explanation.

#### Complete Documentation

- **[Quick Reference](https://github.com/Smart-AI-Memory/empathy-framework/blob/main/docs/caching/QUICK_REFERENCE.md)** - Common scenarios, 1-page cheat sheet
- **[Configuration Guide](https://github.com/Smart-AI-Memory/empathy-framework/blob/main/docs/caching/CONFIGURATION_GUIDE.md)** - All options, when to use each
- **[Adaptive Workflows](https://github.com/Smart-AI-Memory/empathy-framework/blob/main/docs/caching/ADAPTIVE_WORKFLOWS.md)** - Why Run 2 can cost more (it's good!)

**Test it yourself**:
```bash
# Quick test (2-3 minutes)
python benchmark_caching_simple.py

# Full benchmark (15-20 minutes, all 12 workflows)
python benchmark_caching.py
```

---

## Become a Power User

### Level 1: Basic Usage

```bash
pip install empathy-framework[developer]
```

- Lightweight install with CLI tools, LLM providers, and agents
- Works out of the box with sensible defaults
- Auto-detects your API keys

### Level 2: Cost Optimization (Role-Based Savings)

**Tier routing automatically routes tasks to appropriate models, saving 34-86% depending on your work role.**

```bash
# Enable hybrid mode
python -m empathy_os.models.cli provider --set hybrid
```

#### Tier Pricing

| Tier | Model | Use Case | Cost per Task* |
|------|-------|----------|----------------|
| CHEAP | GPT-4o-mini / Haiku | Summarization, formatting, simple tasks | $0.0045-0.0075 |
| CAPABLE | GPT-4o / Sonnet | Bug fixing, code review, analysis | $0.0725-0.090 |
| PREMIUM | o1 / Opus | Architecture, complex decisions, design | $0.435-0.450 |

*Typical task: 5,000 input tokens, 1,000 output tokens

#### Actual Savings by Role

| Your Role | PREMIUM % | CAPABLE % | CHEAP % | Actual Savings | Notes |
|-----------|-----------|-----------|---------|----------------|-------|
| **Architect / Designer** | 60% | 30% | 10% | **34%** | Design work requires complex reasoning |
| **Senior Developer** | 25% | 50% | 25% | **65%** | Mix of architecture and implementation |
| **Mid-Level Developer** | 15% | 60% | 25% | **73%** | Mostly implementation and bug fixes |
| **Junior Developer** | 5% | 40% | 55% | **86%** | Simple features, tests, documentation |
| **QA Engineer** | 10% | 35% | 55% | **80%** | Test generation, reports, automation |
| **DevOps Engineer** | 20% | 50% | 30% | **69%** | Infrastructure planning + automation |

**See [Complete Cost Analysis](https://github.com/Smart-AI-Memory/empathy-framework/blob/main/docs/cost-analysis/COST_SAVINGS_BY_ROLE_AND_PROVIDER.md) for provider comparisons (Anthropic vs OpenAI vs Ollama) and detailed calculations.**

### Level 3: Multi-Model Workflows

```python
from empathy_llm_toolkit import EmpathyLLM

llm = EmpathyLLM(provider="anthropic", enable_model_routing=True)

# Automatically routes to appropriate tier
await llm.interact(user_id="dev", user_input="Summarize this", task_type="summarize")     # → Haiku
await llm.interact(user_id="dev", user_input="Fix this bug", task_type="fix_bug")         # → Sonnet
await llm.interact(user_id="dev", user_input="Design system", task_type="coordinate")     # → Opus
```

### Level 4: VSCode Integration

Install the Empathy VSCode extension for:

- **Real-time Dashboard** — Health score, costs, patterns
- **One-Click Workflows** — Research, code review, debugging
- **Visual Cost Tracking** — See savings in real-time
  - See also: `docs/dashboard-costs-by-tier.md` for interpreting the **By tier (7 days)** cost breakdown.
- **Memory Control Panel (Beta)** — Manage Redis and pattern storage
  - View Redis status and memory usage
  - Browse and export stored patterns
  - Run system health checks
  - Configure auto-start in `empathy.config.yml`

```yaml
memory:
  enabled: true
  auto_start_redis: true
```

### Level 5: Custom Agents

```python
from empathy_os.agents import AgentFactory

# Create domain-specific agents with inherited memory
security_agent = AgentFactory.create(
    domain="security",
    memory_enabled=True,
    anticipation_level=4
)
```

---

## CLI Reference

### Provider Configuration

```bash
python -m empathy_os.models.cli provider                    # Show current config
python -m empathy_os.models.cli provider --set anthropic    # Single provider
python -m empathy_os.models.cli provider --set hybrid       # Best-of-breed
python -m empathy_os.models.cli provider --interactive      # Setup wizard
python -m empathy_os.models.cli provider -f json            # JSON output
```

### Model Registry

```bash
python -m empathy_os.models.cli registry                    # Show all models
python -m empathy_os.models.cli registry --provider openai  # Filter by provider
python -m empathy_os.models.cli costs --input-tokens 50000  # Estimate costs
```

### Telemetry & Analytics

```bash
python -m empathy_os.models.cli telemetry                   # Summary
python -m empathy_os.models.cli telemetry --costs           # Cost savings report
python -m empathy_os.models.cli telemetry --providers       # Provider usage
python -m empathy_os.models.cli telemetry --fallbacks       # Fallback stats
```

### Memory Control

```bash
empathy-memory serve    # Start Redis + API server
empathy-memory status   # Check system status
empathy-memory stats    # View statistics
empathy-memory patterns # List stored patterns
```

### Code Inspection

```bash
empathy-inspect .                     # Run full inspection
empathy-inspect . --format sarif      # GitHub Actions format
empathy-inspect . --fix               # Auto-fix safe issues
empathy-inspect . --staged            # Only staged changes
```

---

## XML-Enhanced Prompts

Enable structured XML prompts for consistent, parseable LLM responses:

```yaml
# .empathy/workflows.yaml
xml_prompt_defaults:
  enabled: false  # Set true to enable globally

workflow_xml_configs:
  security-audit:
    enabled: true
    enforce_response_xml: true
    template_name: "security-audit"
  code-review:
    enabled: true
    template_name: "code-review"
```

Built-in templates: `security-audit`, `code-review`, `research`, `bug-analysis`, `perf-audit`, `refactor-plan`, `test-gen`, `doc-gen`, `release-prep`, `dependency-check`

```python
from empathy_os.prompts import get_template, XmlResponseParser, PromptContext

# Use a built-in template
template = get_template("security-audit")
context = PromptContext.for_security_audit(code="def foo(): pass")
prompt = template.render(context)

# Parse XML responses
parser = XmlResponseParser(fallback_on_error=True)
result = parser.parse(llm_response)
print(result.summary, result.findings, result.checklist)
```

---

## Enterprise Doc-Gen

Generate comprehensive documentation for large projects with enterprise-safe defaults:

```python
from empathy_os.workflows import DocumentGenerationWorkflow

# Enterprise-safe configuration
workflow = DocumentGenerationWorkflow(
    export_path="docs/generated",     # Auto-save to disk
    max_cost=5.0,                     # Cost guardrail ($5 default)
    chunked_generation=True,          # Handle large projects
    graceful_degradation=True,        # Partial results on errors
)

result = await workflow.execute(
    source_code=your_code,
    doc_type="api_reference",
    audience="developers"
)

# Access the formatted report
print(result.final_output["formatted_report"])

# Large outputs are chunked for display
if "output_chunks" in result.final_output:
    for chunk in result.final_output["output_chunks"]:
        print(chunk)

# Full docs saved to disk
print(f"Saved to: {result.final_output.get('export_path')}")
```

---

## Smart Router

Route natural language requests to the right wizard automatically:

```python
from empathy_os.routing import SmartRouter

router = SmartRouter()

# Natural language routing
decision = router.route_sync("Fix the security vulnerability in auth.py")
print(f"Primary: {decision.primary_wizard}")      # → security-audit
print(f"Also consider: {decision.secondary_wizards}")  # → [code-review]
print(f"Confidence: {decision.confidence}")

# File-based suggestions
suggestions = router.suggest_for_file("requirements.txt")  # → [dependency-check]

# Error-based suggestions
suggestions = router.suggest_for_error("NullReferenceException")  # → [bug-predict, test-gen]
```

---

## Memory Graph

Cross-wizard knowledge sharing - wizards learn from each other:

```python
from empathy_os.memory import MemoryGraph, EdgeType

graph = MemoryGraph()

# Add findings from any wizard
bug_id = graph.add_finding(
    wizard="bug-predict",
    finding={
        "type": "bug",
        "name": "Null reference in auth.py:42",
        "severity": "high"
    }
)

# Connect related findings
fix_id = graph.add_finding(wizard="code-review", finding={"type": "fix", "name": "Add null check"})
graph.add_edge(bug_id, fix_id, EdgeType.FIXED_BY)

# Find similar past issues
similar = graph.find_similar({"name": "Null reference error"})

# Traverse relationships
related_fixes = graph.find_related(bug_id, edge_types=[EdgeType.FIXED_BY])
```

---

## Auto-Chaining

Wizards automatically trigger related wizards based on findings:

```yaml
# .empathy/wizard_chains.yaml
chains:
  security-audit:
    auto_chain: true
    triggers:
      - condition: "high_severity_count > 0"
        next: dependency-check
        approval_required: false
      - condition: "vulnerability_type == 'injection'"
        next: code-review
        approval_required: true

  bug-predict:
    triggers:
      - condition: "risk_score > 0.7"
        next: test-gen

templates:
  full-security-review:
    steps: [security-audit, dependency-check, code-review]
  pre-release:
    steps: [test-gen, security-audit, release-prep]
```

```python
from empathy_os.routing import ChainExecutor

executor = ChainExecutor()

# Check what chains would trigger
result = {"high_severity_count": 5}
triggers = executor.get_triggered_chains("security-audit", result)
# → [ChainTrigger(next="dependency-check"), ...]

# Execute a template
template = executor.get_template("full-security-review")
# → ["security-audit", "dependency-check", "code-review"]
```

---

## Prompt Engineering Wizard

Analyze, generate, and optimize prompts:

```python
from coach_wizards import PromptEngineeringWizard

wizard = PromptEngineeringWizard()

# Analyze existing prompts
analysis = wizard.analyze_prompt("Fix this bug")
print(f"Score: {analysis.overall_score}")  # → 0.13 (poor)
print(f"Issues: {analysis.issues}")        # → ["Missing role", "No output format"]

# Generate optimized prompts
prompt = wizard.generate_prompt(
    task="Review code for security vulnerabilities",
    role="a senior security engineer",
    constraints=["Focus on OWASP top 10"],
    output_format="JSON with severity and recommendation"
)

# Optimize tokens (reduce costs)
result = wizard.optimize_tokens(verbose_prompt)
print(f"Reduced: {result.token_reduction:.0%}")  # → 20% reduction

# Add chain-of-thought scaffolding
enhanced = wizard.add_chain_of_thought(prompt, "debug")
```

---

## Install Options

```bash
# Recommended (all features)
pip install empathy-framework[full]

# Minimal
pip install empathy-framework

# Specific providers
pip install empathy-framework[anthropic]  # Claude
pip install empathy-framework[openai]     # GPT-4, Ollama (OpenAI-compatible)
pip install empathy-framework[google]     # Gemini
pip install empathy-framework[llm]        # All providers

# Development
git clone https://github.com/Smart-AI-Memory/empathy-framework.git
cd empathy-framework && pip install -e .[dev]
```

---

## What's Included

| Component | Description |
|-----------|-------------|
| **Empathy OS** | Core engine for human↔AI and AI↔AI collaboration |
| **Smart Router** | Natural language wizard dispatch with LLM classification |
| **Memory Graph** | Cross-wizard knowledge sharing (bugs, fixes, patterns) |
| **Auto-Chaining** | Wizards trigger related wizards based on findings |
| **Multi-Model Router** | Smart routing across providers and tiers |
| **Memory System** | Redis short-term + encrypted long-term patterns |
| **17 Coach Wizards** | Security, performance, testing, docs, prompt engineering |
| **10 Cost-Optimized Workflows** | Multi-tier pipelines with formatted reports & XML prompts |
| **Healthcare Suite** | SBAR, SOAP notes, clinical protocols (HIPAA) |
| **Code Inspection** | Unified pipeline with SARIF/GitHub Actions support |
| **VSCode Extension** | Visual dashboard for memory and workflows |
| **Telemetry & Analytics** | Cost tracking, usage stats, optimization insights |

---

## The 5 Levels of AI Empathy

| Level | Name | Behavior | Example |
|-------|------|----------|---------|
| 1 | Reactive | Responds when asked | "Here's the data you requested" |
| 2 | Guided | Asks clarifying questions | "What format do you need?" |
| 3 | Proactive | Notices patterns | "I pre-fetched what you usually need" |
| **4** | **Anticipatory** | **Predicts future needs** | **"This query will timeout at 10k users"** |
| 5 | Transformative | Builds preventing structures | "Here's a framework for all future cases" |

**Empathy operates at Level 4** — predicting problems before they manifest.

---

## Environment Setup

```bash
# Required: At least one provider
export ANTHROPIC_API_KEY="sk-ant-..."   # For Claude models  # pragma: allowlist secret
export OPENAI_API_KEY="sk-..."          # For GPT models  # pragma: allowlist secret
export GOOGLE_API_KEY="..."             # For Gemini models  # pragma: allowlist secret

# Optional: Redis for memory
export REDIS_URL="redis://localhost:6379"

# Or use a .env file (auto-detected)
echo 'ANTHROPIC_API_KEY=sk-ant-...' >> .env
```

---

## Get Involved

- **[Star this repo](https://github.com/Smart-AI-Memory/empathy-framework)** if you find it useful
- **[Join Discussions](https://github.com/Smart-AI-Memory/empathy-framework/discussions)** — Questions, ideas, show what you built
- **[Read the Book](https://smartaimemory.com/book)** — Deep dive into the philosophy
- **[Full Documentation](https://smartaimemory.com/framework-docs/)** — API reference, examples, guides

---

## Project Evolution

For those interested in the development history and architectural decisions:

- **[Development Logs](https://github.com/Smart-AI-Memory/empathy-framework/tree/main/docs/development-logs/)** — Execution plans, phase completions, and progress tracking
- **[Architecture Docs](https://github.com/Smart-AI-Memory/empathy-framework/tree/main/docs/architecture/)** — System design, memory architecture, and integration plans
- **[Claude Code Skills](https://github.com/Smart-AI-Memory/empathy-framework/tree/main/.claude/commands/)** — AI-powered workflows and custom agent creation
- **[Guides](https://github.com/Smart-AI-Memory/empathy-framework/tree/main/docs/guides/)** — Publishing tutorials, MkDocs setup, and distribution policies

---

## License

**Fair Source License 0.9** — Free for students, educators, and teams ≤5 employees. Commercial license ($99/dev/year) for larger organizations. [Details →](https://github.com/Smart-AI-Memory/empathy-framework/blob/main/LICENSE)

---

**Built by [Smart AI Memory](https://smartaimemory.com)** · [Documentation](https://smartaimemory.com/framework-docs/) · [Examples](https://github.com/Smart-AI-Memory/empathy-framework/tree/main/examples) · [Issues](https://github.com/Smart-AI-Memory/empathy-framework/issues)
