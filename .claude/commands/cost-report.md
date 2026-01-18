Analyze LLM API costs and show savings from intelligent tier routing.

## Leverages Existing Features

The Empathy Framework has powerful cost tracking built-in:
- `empathy telemetry show` - Recent API calls with costs
- `empathy telemetry savings` - Savings analysis vs premium baseline
- `CostTracker` - Automatic cost logging per request

## Execution Steps

### 1. Show Recent Usage
```bash
empathy telemetry show --limit 50
```

### 2. Calculate Savings
```bash
empathy telemetry savings --days 30
```

### 3. Analyze by Workflow
```bash
# If available, show cost breakdown by workflow type
empathy telemetry breakdown 2>/dev/null || echo "Breakdown not available"
```

### 4. Check Cache Effectiveness
```bash
empathy cache stats 2>/dev/null || echo "Cache stats: check .empathy/cache/"
```

## Analysis to Provide

After running the commands, analyze and report:

### Cost Summary
| Metric | Value |
|--------|-------|
| Total Spend (30d) | $X.XX |
| Baseline (if all premium) | $X.XX |
| **Your Savings** | $X.XX (XX%) |
| Cache Savings | $X.XX |

### Tier Distribution
Show percentage of calls by tier:
- CHEAP (Haiku): XX% - outlines, summaries
- CAPABLE (Sonnet): XX% - code review, generation
- PREMIUM (Opus): XX% - complex analysis

### Optimization Recommendations

Based on the data, suggest:
1. **Under-utilizing cheap tier?** - Some tasks could use Haiku
2. **High cache miss rate?** - Adjust cache TTL or size
3. **Expensive workflows?** - Identify cost hotspots
4. **Cost trending up?** - Alert on unusual patterns

### Cost Projection
- Daily average: $X.XX
- Projected monthly: $X.XX
- At current rate, daily limit ($10) reached in: X days

Keep output concise with actionable insights.
