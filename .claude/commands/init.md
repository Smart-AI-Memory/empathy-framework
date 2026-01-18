Initialize a new Empathy Framework project with best practices.

## Steps

### 1. Check Prerequisites
```bash
# Verify empathy-framework is installed
python -c "import empathy_os; print(f'Empathy Framework v{empathy_os.__version__}')"

# Check for existing config
ls -la empathy.config.yml .empathy/ 2>/dev/null || echo "No existing config found"
```

### 2. Create Configuration File
If `empathy.config.yml` doesn't exist, create it with sensible defaults:

```yaml
# empathy.config.yml
version: "1.0"

# Model tier routing - optimize cost vs capability
tiers:
  cheap: "claude-3-haiku-20240307"      # Fast, cheap: outlines, summaries
  capable: "claude-3-5-sonnet-20241022" # Balanced: code review, generation
  premium: "claude-opus-4-5-20251101"   # Best: complex analysis, final review

# Caching configuration
cache:
  enabled: true
  type: "hybrid"  # semantic + hash matching
  max_size_mb: 100
  ttl_hours: 24

# Memory configuration
memory:
  short_term:
    backend: "redis"  # or "memory" for no persistence
    ttl_minutes: 60
  long_term:
    backend: "sqlite"
    path: ".empathy/memory.db"

# Security settings
security:
  pii_scrubbing: true
  secrets_detection: true
  audit_logging: true

# Cost guardrails
cost:
  max_daily_spend: 10.00
  warn_threshold: 5.00
```

### 3. Create Environment Template
Create `.env.example` with required variables:

```bash
# API Keys (at least one required)
ANTHROPIC_API_KEY=your-key-here
# OPENAI_API_KEY=your-key-here

# Optional: Redis for short-term memory
# REDIS_URL=redis://localhost:6379

# Optional: Telemetry
# EMPATHY_TELEMETRY=true
```

### 4. Initialize Storage Directory
```bash
mkdir -p .empathy/cache .empathy/memory .empathy/telemetry
echo ".empathy/" >> .gitignore 2>/dev/null || true
echo ".env" >> .gitignore 2>/dev/null || true
```

### 5. Verify Installation
```bash
empathy --version
empathy health 2>/dev/null || echo "Run 'empathy health' to check system status"
```

## Output

Provide a summary:
- Configuration file created/updated
- Environment template created
- Storage directories initialized
- Next steps for the user (copy .env.example to .env, add API keys)
