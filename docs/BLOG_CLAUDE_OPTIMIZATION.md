# Why I Made Empathy Framework Claude-First (And How It Cuts Your Costs)

**January 2026**

---

## TL;DR

I rebuilt Empathy Framework v4.6.3 around Claude Code with 10+ slash commands, automatic pattern learning, and true async I/O. The result? Better workflows AND lower API costs. OpenAI, Gemini, and local models still work perfectly.

---

## The Realization

When I started building Empathy Framework, I wanted it to work with any LLM. And it still does. But as I used it day after day, I noticed something: I was getting dramatically better results with Claude Code.

The conversation persistence, tool use, and extended context windows are a perfect match for the kind of work Empathy does: multi-step workflows, codebase analysis, and pattern learning across sessions.

So I leaned in hard.

## How This Cuts Your Costs

If you're paying for a Claude subscription or API access, here's how these optimizations save you money:

### 1. Prompt Caching (Up to 90% Savings)

I enabled Claude's prompt caching by default:

```python
api_kwargs["system"] = [{
    "type": "text",
    "text": system_prompt,
    "cache_control": {"type": "ephemeral"},  # 5-minute cache
}]
```

When you run multiple operations against the same codebase (which you do constantly), the system prompt gets cached. Anthropic charges 90% less for cached tokens. For a typical debugging session that makes 10+ API calls, this adds up fast.

### 2. Slash Commands = Fewer Round Trips

Instead of explaining what you want in natural language and going back-and-forth, you type:

```
/debug
```

The skill file contains structured instructions. Claude knows exactly what to do. Fewer tokens explaining, more tokens solving.

### 3. Pattern Learning = Don't Solve Twice

After `/debug`, `/refactor`, or `/review` workflows complete, Empathy automatically saves what was learned:

```bash
python -m empathy_os.cli learn --quiet &
```

Next time you hit a similar issue, Claude has context. You're not burning tokens re-explaining the same codebase patterns every session.

### 4. True Async = Parallel Efficiency

I migrated to `AsyncAnthropic`:

```python
# v4.6.3
self.client = anthropic.AsyncAnthropic(api_key=api_key)
```

This lets multiple API calls run in parallel. When a workflow needs to analyze 5 files, it does them concurrently instead of sequentially. Same tokens, faster results.

## What "Claude-First" Actually Means

### Native Slash Commands

Type these directly in Claude Code:

| Command | What It Does |
|---------|--------------|
| `/debug` | Bug investigation with historical pattern matching |
| `/refactor` | Safe refactoring with test verification |
| `/review` | Code review against project standards |
| `/deps` | Dependency audit (CVE, outdated, licenses) |
| `/profile` | Performance profiling |
| `/commit` | Well-formatted git commits |
| `/pr` | Structured PR creation |

### VSCode Dashboard

Every button in the Empathy Dashboard now shows its slash command. Click "Debug" and see `/debug`. I built this so you learn the shortcuts as you work.

### Automatic Pattern Learning

This is the part I'm most excited about. After completing debug, refactor, or review workflows, the framework captures what happened:

- What type of bug was it?
- How did you fix it?
- What patterns emerged?

This goes into `patterns/debugging.json` and `patterns/refactoring_memory.json`. Over time, Empathy gets smarter about YOUR codebase.

## Other LLMs Still Work

I didn't break anything. Empathy Framework supports:

| Provider | Status |
|----------|--------|
| **Anthropic (Claude)** | Primary, optimized |
| **OpenAI (GPT-4, GPT-3.5)** | Full support, async |
| **Google (Gemini)** | Full support |
| **Local (Ollama, LM Studio)** | Full support |

All providers use async clients. All providers work with workflows. The difference: Claude-specific features (slash commands, conversation persistence) unlock capabilities the others don't have.

```python
# Still works fine
from empathy_llm_toolkit.providers import OpenAIProvider, GeminiProvider, LocalProvider
```

## The Skills System

I put all the workflow logic in markdown files:

```
.claude/commands/
├── debug.md        # Bug investigation
├── refactor.md     # Safe refactoring
├── review.md       # Code review
├── deps.md         # Dependency audit
├── profile.md      # Performance profiling
├── commit.md       # Git commits
└── pr.md           # PR creation
```

You can read these. You can customize them. They're just markdown files that Claude Code executes. No black box.

## Getting Started

```bash
pip install empathy-framework --upgrade

# In Claude Code
/debug
```

Or click any button in the VSCode dashboard - it'll route to the right skill.

## What's Next

- **Cross-session memory**: Pattern learning that persists across conversations
- **Team patterns**: Share learned patterns with your organization
- **Custom skill builder**: Create slash commands without code

---

The goal was simple: make Empathy Framework work better where I use it most (Claude Code) while keeping everything else working. The bonus: it costs less to run.

**Try it:** `pip install empathy-framework --upgrade`

**Source:** [github.com/Smart-AI-Memory/empathy-framework](https://github.com/Smart-AI-Memory/empathy-framework)

*Claude-first, but never Claude-only.*
