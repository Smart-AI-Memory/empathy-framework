# Monitoring API Reference

The monitoring module provides telemetry alerts and observability for LLM usage.

## Alert System

### AlertMetric

Supported metrics for alerting.

```python
from empathy_os.monitoring.alerts import AlertMetric

class AlertMetric(str, Enum):
    DAILY_COST = "daily_cost"      # Total daily spend in USD
    ERROR_RATE = "error_rate"      # Error percentage
    AVG_LATENCY = "avg_latency"    # Average response time (ms)
    TOKEN_USAGE = "token_usage"    # Total tokens consumed
```

### AlertChannel

Notification delivery channels.

```python
from empathy_os.monitoring.alerts import AlertChannel

class AlertChannel(str, Enum):
    WEBHOOK = "webhook"           # Slack, Discord, etc.
    EMAIL = "email"               # Email notifications
    STDOUT = "stdout"             # Console output
    VSCODE_OUTPUT = "vscode_output"  # VSCode output panel
```

### Alert

Alert configuration dataclass.

```python
from empathy_os.monitoring.alerts import Alert, AlertMetric, AlertChannel

alert = Alert(
    id="cost-alert-001",
    name="Daily Cost Alert",
    metric=AlertMetric.DAILY_COST,
    threshold=10.0,              # Trigger when daily cost > $10
    channel=AlertChannel.WEBHOOK,
    webhook_url="https://hooks.slack.com/...",
    enabled=True,
    cooldown_seconds=3600,       # 1 hour cooldown
)
```

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `id` | `str` | Unique identifier for the alert |
| `name` | `str` | Human-readable name |
| `metric` | `AlertMetric` | Metric to monitor |
| `threshold` | `float` | Trigger threshold |
| `channel` | `AlertChannel` | Notification channel |
| `webhook_url` | `str \| None` | Webhook URL (for WEBHOOK channel) |
| `email` | `str \| None` | Email address (for EMAIL channel) |
| `enabled` | `bool` | Whether alert is active (default: True) |
| `cooldown_seconds` | `int` | Minimum time between notifications (default: 3600) |

### AlertEngine

Core alert engine with SQLite storage.

```python
from empathy_os.monitoring.alerts import AlertEngine, Alert

# Initialize
engine = AlertEngine(db_path=".empathy/alerts.db")

# Add alert
engine.add_alert(alert)

# Get all enabled alerts
alerts = engine.get_alerts(enabled_only=True)

# Check metrics and notify
metrics = {"daily_cost": 15.50, "error_rate": 2.5}
triggered = engine.check_and_notify(metrics)

# Delete alert
engine.delete_alert("cost-alert-001")

# Get alert history
history = engine.get_history(limit=100)
```

**Methods:**

| Method | Description |
|--------|-------------|
| `add_alert(alert)` | Add or update an alert configuration |
| `get_alerts(enabled_only=True)` | Get all configured alerts |
| `delete_alert(alert_id)` | Delete an alert by ID |
| `check_and_notify(metrics)` | Check metrics and send notifications |
| `get_history(alert_id=None, limit=100)` | Get alert trigger history |

### Notifiers

Built-in notification handlers:

- **WebhookNotifier**: Sends JSON payloads to webhook URLs (Slack, Discord compatible)
- **EmailNotifier**: Placeholder for email notifications (requires SMTP config)
- **StdoutNotifier**: Prints alerts to console

### CLI Commands

```bash
# Interactive setup wizard
empathy alerts init

# List configured alerts
empathy alerts list

# Start monitoring
empathy alerts watch --interval 60

# Delete an alert
empathy alerts delete <alert-id>
```

## Usage Example

```python
from empathy_os.monitoring.alerts import (
    AlertEngine,
    Alert,
    AlertMetric,
    AlertChannel,
    get_current_metrics,
)

# Create engine
engine = AlertEngine()

# Configure cost alert
cost_alert = Alert(
    id="high-cost",
    name="High Daily Cost",
    metric=AlertMetric.DAILY_COST,
    threshold=25.0,
    channel=AlertChannel.STDOUT,
)
engine.add_alert(cost_alert)

# Manual check
metrics = get_current_metrics()
triggered = engine.check_and_notify(metrics)

for event in triggered:
    print(f"Alert triggered: {event.alert.name}")
    print(f"  Value: {event.current_value}")
    print(f"  Threshold: {event.alert.threshold}")
```
