"""Alert System for LLM Telemetry Monitoring

Provides threshold-based alerting for LLM usage metrics.

**Features:**
- Interactive CLI wizard (`empathy alerts init`)
- Multiple notification channels (webhook, email, stdout)
- Threshold triggers (daily cost, error rate, etc.)
- Cooldown mechanism (prevent spam)
- Enterprise background daemon (`empathy alerts watch --daemon`)

Copyright 2025 Smart-AI-Memory
Licensed under Fair Source License 0.9
"""

from __future__ import annotations

import json
import logging
import sqlite3
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Protocol
from urllib.error import URLError
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)


class AlertMetric(str, Enum):
    """Supported alert metrics."""

    DAILY_COST = "daily_cost"
    ERROR_RATE = "error_rate"
    AVG_LATENCY = "avg_latency"
    TOKEN_USAGE = "token_usage"


class AlertChannel(str, Enum):
    """Supported notification channels."""

    WEBHOOK = "webhook"
    EMAIL = "email"
    STDOUT = "stdout"
    VSCODE_OUTPUT = "vscode_output"


@dataclass
class Alert:
    """Alert configuration."""

    id: str
    name: str
    metric: AlertMetric
    threshold: float
    channel: AlertChannel
    webhook_url: str | None = None
    email: str | None = None
    enabled: bool = True
    cooldown_seconds: int = 3600  # 1 hour default
    created_at: datetime = field(default_factory=datetime.now)
    last_triggered: datetime | None = None


@dataclass
class AlertEvent:
    """An alert trigger event."""

    alert: Alert
    current_value: float
    triggered_at: datetime = field(default_factory=datetime.now)
    message: str = ""


class NotificationHandler(Protocol):
    """Protocol for notification handlers."""

    def send(self, event: AlertEvent) -> bool:
        """Send notification. Returns True on success."""
        ...


class WebhookNotifier:
    """Send alerts via webhook (Slack, Discord, etc.)."""

    def send(self, event: AlertEvent) -> bool:
        """Send webhook notification."""
        if not event.alert.webhook_url:
            logger.error("Webhook URL not configured for alert %s", event.alert.id)
            return False

        payload = {
            "text": f"🚨 Alert: {event.alert.name}",
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*{event.alert.name}*\n"
                        f"Metric `{event.alert.metric.value}` exceeded threshold.\n"
                        f"Current: {event.current_value:.2f} | Threshold: {event.alert.threshold:.2f}",
                    },
                }
            ],
        }

        try:
            req = Request(
                event.alert.webhook_url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urlopen(req, timeout=10) as response:
                return response.status == 200
        except URLError as e:
            logger.error("Failed to send webhook: %s", e)
            return False
        except TimeoutError:
            logger.error("Webhook request timed out")
            return False


class StdoutNotifier:
    """Print alerts to stdout (for VSCode output, console)."""

    def send(self, event: AlertEvent) -> bool:
        """Print alert to stdout."""
        print(f"\n🚨 ALERT: {event.alert.name}")
        print(f"   Metric: {event.alert.metric.value}")
        print(f"   Current: {event.current_value:.2f}")
        print(f"   Threshold: {event.alert.threshold:.2f}")
        print(f"   Time: {event.triggered_at.isoformat()}")
        return True


class EmailNotifier:
    """Send alerts via email (placeholder - requires SMTP config)."""

    def send(self, event: AlertEvent) -> bool:
        """Send email notification (placeholder)."""
        if not event.alert.email:
            logger.error("Email not configured for alert %s", event.alert.id)
            return False

        # Note: Full implementation requires SMTP configuration
        logger.info(
            "Email notification would be sent to %s for alert %s",
            event.alert.email,
            event.alert.name,
        )
        print(f"📧 Email alert would be sent to {event.alert.email}")
        return True


class AlertEngine:
    """Core alert engine with SQLite storage and notification dispatch."""

    NOTIFIERS: dict[AlertChannel, type[NotificationHandler]] = {
        AlertChannel.WEBHOOK: WebhookNotifier,
        AlertChannel.EMAIL: EmailNotifier,
        AlertChannel.STDOUT: StdoutNotifier,
        AlertChannel.VSCODE_OUTPUT: StdoutNotifier,
    }

    def __init__(self, db_path: str = ".empathy/alerts.db"):
        """Initialize alert engine.

        Args:
            db_path: Path to SQLite database for alert storage.
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        self._cooldowns: dict[str, datetime] = {}

    def _init_db(self) -> None:
        """Initialize SQLite database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS alerts (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                metric TEXT NOT NULL,
                threshold REAL NOT NULL,
                channel TEXT NOT NULL,
                webhook_url TEXT,
                email TEXT,
                enabled INTEGER DEFAULT 1,
                cooldown INTEGER DEFAULT 3600,
                last_triggered TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS alert_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                alert_id TEXT NOT NULL,
                value REAL NOT NULL,
                triggered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                notified INTEGER DEFAULT 0,
                FOREIGN KEY (alert_id) REFERENCES alerts(id)
            )
        """
        )

        conn.commit()
        conn.close()

    def add_alert(self, alert: Alert) -> None:
        """Add or update an alert configuration."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT OR REPLACE INTO alerts
            (id, name, metric, threshold, channel, webhook_url, email, enabled, cooldown, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                alert.id,
                alert.name,
                alert.metric.value,
                alert.threshold,
                alert.channel.value,
                alert.webhook_url,
                alert.email,
                1 if alert.enabled else 0,
                alert.cooldown_seconds,
                alert.created_at.isoformat(),
            ),
        )

        conn.commit()
        conn.close()

    def get_alerts(self, enabled_only: bool = True) -> list[Alert]:
        """Get all configured alerts."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        query = "SELECT * FROM alerts"
        if enabled_only:
            query += " WHERE enabled = 1"

        cursor.execute(query)
        rows = cursor.fetchall()
        conn.close()

        alerts = []
        for row in rows:
            last_triggered = None
            if row[9]:
                try:
                    last_triggered = datetime.fromisoformat(row[9])
                except ValueError:
                    pass

            alerts.append(
                Alert(
                    id=row[0],
                    name=row[1],
                    metric=AlertMetric(row[2]),
                    threshold=row[3],
                    channel=AlertChannel(row[4]),
                    webhook_url=row[5],
                    email=row[6],
                    enabled=bool(row[7]),
                    cooldown_seconds=row[8],
                    last_triggered=last_triggered,
                )
            )

        return alerts

    def delete_alert(self, alert_id: str) -> bool:
        """Delete an alert by ID."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("DELETE FROM alerts WHERE id = ?", (alert_id,))
        deleted = cursor.rowcount > 0

        conn.commit()
        conn.close()

        return deleted

    def check_and_notify(self, metrics: dict[str, float]) -> list[AlertEvent]:
        """Check metrics against alerts and send notifications.

        Args:
            metrics: Dict mapping metric names to current values.
                Example: {"daily_cost": 15.50, "error_rate": 5.2}

        Returns:
            List of triggered AlertEvents.
        """
        alerts = self.get_alerts(enabled_only=True)
        triggered = []

        for alert in alerts:
            metric_value = metrics.get(alert.metric.value)
            if metric_value is None:
                continue

            # Check if threshold exceeded
            if metric_value > alert.threshold:
                # Check cooldown
                if self._is_in_cooldown(alert):
                    logger.debug(
                        "Alert %s in cooldown, skipping notification", alert.id
                    )
                    continue

                event = AlertEvent(
                    alert=alert,
                    current_value=metric_value,
                    message=f"{alert.name}: {metric_value:.2f} exceeded threshold {alert.threshold:.2f}",
                )

                # Send notification
                if self._send_notification(event):
                    self._record_trigger(alert, metric_value)
                    triggered.append(event)

        return triggered

    def _is_in_cooldown(self, alert: Alert) -> bool:
        """Check if alert is in cooldown period."""
        last_trigger = self._cooldowns.get(alert.id)
        if last_trigger is None:
            return False

        cooldown_end = last_trigger + timedelta(seconds=alert.cooldown_seconds)
        return datetime.now() < cooldown_end

    def _send_notification(self, event: AlertEvent) -> bool:
        """Send notification for an alert event."""
        notifier_class = self.NOTIFIERS.get(event.alert.channel)
        if notifier_class is None:
            logger.error("Unknown notification channel: %s", event.alert.channel)
            return False

        notifier = notifier_class()
        try:
            return notifier.send(event)
        except Exception as e:
            logger.exception("Failed to send notification: %s", e)
            return False

    def _record_trigger(self, alert: Alert, value: float) -> None:
        """Record alert trigger in database and memory."""
        now = datetime.now()
        self._cooldowns[alert.id] = now

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Update last_triggered
        cursor.execute(
            "UPDATE alerts SET last_triggered = ? WHERE id = ?",
            (now.isoformat(), alert.id),
        )

        # Add to history
        cursor.execute(
            "INSERT INTO alert_history (alert_id, value, notified) VALUES (?, ?, 1)",
            (alert.id, value),
        )

        conn.commit()
        conn.close()

    def get_history(
        self, alert_id: str | None = None, limit: int = 100
    ) -> list[dict[str, Any]]:
        """Get alert trigger history.

        Args:
            alert_id: Optional filter by alert ID.
            limit: Maximum number of records to return.

        Returns:
            List of history records.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        if alert_id:
            cursor.execute(
                "SELECT * FROM alert_history WHERE alert_id = ? ORDER BY triggered_at DESC LIMIT ?",
                (alert_id, limit),
            )
        else:
            cursor.execute(
                "SELECT * FROM alert_history ORDER BY triggered_at DESC LIMIT ?",
                (limit,),
            )

        rows = cursor.fetchall()
        conn.close()

        return [
            {
                "id": row[0],
                "alert_id": row[1],
                "value": row[2],
                "triggered_at": row[3],
                "notified": bool(row[4]),
            }
            for row in rows
        ]


def get_current_metrics() -> dict[str, float]:
    """Get current telemetry metrics for alert checking.

    Returns:
        Dict of metric name to current value.
    """
    # Try to import telemetry module
    try:
        from empathy_os.telemetry.tracker import UsageTracker

        tracker = UsageTracker()
        stats = tracker.get_stats()

        return {
            "daily_cost": stats.get("total_cost", 0.0),
            "error_rate": stats.get("error_rate", 0.0),
            "avg_latency": stats.get("avg_latency_ms", 0.0),
            "token_usage": stats.get("total_tokens", 0),
        }
    except ImportError:
        logger.warning("Telemetry module not available, using mock metrics")
        return {
            "daily_cost": 0.0,
            "error_rate": 0.0,
            "avg_latency": 0.0,
            "token_usage": 0,
        }
    except Exception as e:
        logger.error("Failed to get telemetry metrics: %s", e)
        return {}
