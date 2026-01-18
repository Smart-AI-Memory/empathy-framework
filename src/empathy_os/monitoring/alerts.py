"""Alert System for LLM Telemetry Monitoring

Provides threshold-based alerting for LLM usage metrics.

**Features:**
- Interactive CLI wizard (`empathy alerts init`)
- Multiple notification channels (webhook, email, stdout)
- Threshold triggers (daily cost, error rate, etc.)
- Cooldown mechanism (prevent spam)
- Enterprise background daemon (`empathy alerts watch --daemon`)

**Supported Metrics:**
- daily_cost: Total cost for the current day (USD)
- error_rate: Percentage of failed LLM calls
- avg_latency: Average response time (ms)
- token_usage: Total tokens used today

**Implementation Status:** Sprint 3 (Week 3)

Copyright 2025 Smart-AI-Memory
Licensed under Fair Source License 0.9
"""

import json
import logging
import smtplib
import sqlite3
import urllib.request
import urllib.error
from dataclasses import dataclass
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any

from empathy_os.models.telemetry import TelemetryStore, get_telemetry_store

logger = logging.getLogger(__name__)


@dataclass
class AlertResult:
    """Result of an alert check.

    Attributes:
        alert_id: The alert that was triggered
        alert_name: Human-readable name of the alert
        metric: The metric that triggered the alert
        threshold: The configured threshold value
        current_value: The actual metric value
        triggered: Whether the threshold was exceeded
        notification_sent: Whether notification was successfully sent
        notification_error: Error message if notification failed
    """

    alert_id: str
    alert_name: str
    metric: str
    threshold: float
    current_value: float
    triggered: bool
    notification_sent: bool = False
    notification_error: str | None = None


@dataclass
class MetricValues:
    """Current values for all tracked metrics.

    Attributes:
        daily_cost: Total cost for the current day (USD)
        error_rate: Percentage of failed LLM calls (0-100)
        avg_latency: Average response time in milliseconds
        token_usage: Total tokens used today
        timestamp: When these metrics were collected
    """

    daily_cost: float
    error_rate: float
    avg_latency: float
    token_usage: int
    timestamp: datetime


class AlertEngine:
    """Alert engine with SQLite storage and notification delivery.

    Manages alert configurations, checks metrics against thresholds,
    and sends notifications via webhook, email, or stdout.

    Example:
        >>> engine = AlertEngine()
        >>> engine.add_alert(
        ...     alert_id="cost_alert_1",
        ...     name="Daily Cost Alert",
        ...     metric="daily_cost",
        ...     threshold=10.0,
        ...     channel="webhook",
        ...     webhook_url="https://hooks.slack.com/..."
        ... )
        >>> results = engine.check_alerts()
        >>> for result in results:
        ...     if result.triggered:
        ...         print(f"Alert {result.alert_name} triggered!")
    """

    def __init__(
        self,
        db_path: str = ".empathy/alerts.db",
        telemetry_store: TelemetryStore | None = None,
    ) -> None:
        """Initialize the alert engine.

        Args:
            db_path: Path to SQLite database for alert storage
            telemetry_store: Optional TelemetryStore for metrics (uses default if None)
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._telemetry_store = telemetry_store
        self._init_db()

    @property
    def telemetry_store(self) -> TelemetryStore:
        """Get the telemetry store, creating default if needed."""
        if self._telemetry_store is None:
            self._telemetry_store = get_telemetry_store()
        return self._telemetry_store

    def _init_db(self) -> None:
        """Initialize SQLite database with alerts and cooldown tables."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Alerts table
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
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """
            )

            # Cooldown tracking table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS alert_cooldowns (
                    alert_id TEXT PRIMARY KEY,
                    last_triggered TIMESTAMP,
                    FOREIGN KEY (alert_id) REFERENCES alerts(id) ON DELETE CASCADE
                )
            """
            )

            conn.commit()
        except sqlite3.Error as e:
            logger.error(f"Failed to initialize alerts database: {e}")
            raise
        finally:
            conn.close()

    def add_alert(
        self,
        alert_id: str,
        name: str,
        metric: str,
        threshold: float,
        channel: str,
        webhook_url: str | None = None,
        email: str | None = None,
        cooldown: int = 3600,
    ) -> None:
        """Add a new alert configuration.

        Args:
            alert_id: Unique identifier for the alert
            name: Human-readable name for the alert
            metric: Metric to monitor (daily_cost, error_rate, avg_latency, token_usage)
            threshold: Value that triggers the alert
            channel: Notification channel (webhook, email, vscode_output)
            webhook_url: URL for webhook notifications
            email: Email address for email notifications
            cooldown: Seconds between repeat notifications (default: 1 hour)

        Raises:
            ValueError: If metric is not recognized
            sqlite3.Error: If database operation fails
        """
        valid_metrics = {"daily_cost", "error_rate", "avg_latency", "token_usage"}
        if metric not in valid_metrics:
            raise ValueError(f"Invalid metric: {metric}. Must be one of {valid_metrics}")

        valid_channels = {"webhook", "email", "vscode_output"}
        if channel not in valid_channels:
            raise ValueError(f"Invalid channel: {channel}. Must be one of {valid_channels}")

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO alerts (id, name, metric, threshold, channel, webhook_url, email, cooldown)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (alert_id, name, metric, threshold, channel, webhook_url, email, cooldown),
            )

            conn.commit()
            logger.info(f"Added alert: {alert_id} ({name})")
        except sqlite3.Error as e:
            logger.error(f"Failed to add alert {alert_id}: {e}")
            raise
        finally:
            conn.close()

    def get_alert(self, alert_id: str) -> dict[str, Any] | None:
        """Retrieve a single alert by ID.

        Args:
            alert_id: The unique identifier of the alert

        Returns:
            Alert configuration dict or None if not found
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("SELECT * FROM alerts WHERE id = ?", (alert_id,))
            row = cursor.fetchone()

            if row is None:
                return None

            return {
                "id": row[0],
                "name": row[1],
                "metric": row[2],
                "threshold": row[3],
                "channel": row[4],
                "webhook_url": row[5],
                "email": row[6],
                "enabled": bool(row[7]),
                "cooldown": row[8],
                "created_at": row[9],
            }
        except sqlite3.Error as e:
            logger.error(f"Failed to get alert {alert_id}: {e}")
            raise
        finally:
            conn.close()

    def list_alerts(self) -> list[dict[str, Any]]:
        """List all configured alerts.

        Returns:
            List of alert configuration dicts
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("SELECT * FROM alerts")
            rows = cursor.fetchall()

            alerts = []
            for row in rows:
                alerts.append(
                    {
                        "id": row[0],
                        "name": row[1],
                        "metric": row[2],
                        "threshold": row[3],
                        "channel": row[4],
                        "webhook_url": row[5],
                        "email": row[6],
                        "enabled": bool(row[7]),
                        "cooldown": row[8],
                        "created_at": row[9],
                    }
                )

            return alerts
        except sqlite3.Error as e:
            logger.error(f"Failed to list alerts: {e}")
            raise
        finally:
            conn.close()

    def delete_alert(self, alert_id: str) -> bool:
        """Delete an alert by ID.

        Args:
            alert_id: The unique identifier of the alert to delete

        Returns:
            True if alert was deleted, False if not found
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("DELETE FROM alerts WHERE id = ?", (alert_id,))
            deleted = cursor.rowcount > 0

            conn.commit()

            if deleted:
                logger.info(f"Deleted alert: {alert_id}")
            else:
                logger.warning(f"Alert not found for deletion: {alert_id}")

            return deleted
        except sqlite3.Error as e:
            logger.error(f"Failed to delete alert {alert_id}: {e}")
            raise
        finally:
            conn.close()

    def enable_alert(self, alert_id: str, enabled: bool = True) -> bool:
        """Enable or disable an alert.

        Args:
            alert_id: The unique identifier of the alert
            enabled: Whether to enable (True) or disable (False)

        Returns:
            True if alert was updated, False if not found
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute(
                "UPDATE alerts SET enabled = ? WHERE id = ?",
                (1 if enabled else 0, alert_id),
            )
            updated = cursor.rowcount > 0

            conn.commit()

            if updated:
                status = "enabled" if enabled else "disabled"
                logger.info(f"Alert {alert_id} {status}")

            return updated
        except sqlite3.Error as e:
            logger.error(f"Failed to update alert {alert_id}: {e}")
            raise
        finally:
            conn.close()

    def get_current_metrics(self) -> MetricValues:
        """Get current values for all tracked metrics.

        Returns:
            MetricValues with current metric data
        """
        now = datetime.now()
        today_start = datetime(now.year, now.month, now.day)

        # Get calls from today
        calls = self.telemetry_store.get_calls(since=today_start, limit=100000)

        if not calls:
            return MetricValues(
                daily_cost=0.0,
                error_rate=0.0,
                avg_latency=0.0,
                token_usage=0,
                timestamp=now,
            )

        # Calculate metrics
        total_cost = sum(c.estimated_cost for c in calls)
        total_calls = len(calls)
        error_count = sum(1 for c in calls if not c.success)
        error_rate = (error_count / total_calls * 100) if total_calls > 0 else 0.0
        total_latency = sum(c.latency_ms for c in calls)
        avg_latency = total_latency / total_calls if total_calls > 0 else 0.0
        total_tokens = sum(c.input_tokens + c.output_tokens for c in calls)

        return MetricValues(
            daily_cost=total_cost,
            error_rate=error_rate,
            avg_latency=avg_latency,
            token_usage=total_tokens,
            timestamp=now,
        )

    def _is_in_cooldown(self, alert_id: str, cooldown_seconds: int) -> bool:
        """Check if an alert is in cooldown period.

        Args:
            alert_id: The alert to check
            cooldown_seconds: Cooldown period in seconds

        Returns:
            True if alert is in cooldown, False otherwise
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute(
                "SELECT last_triggered FROM alert_cooldowns WHERE alert_id = ?",
                (alert_id,),
            )
            row = cursor.fetchone()

            if row is None or row[0] is None:
                return False

            last_triggered = datetime.fromisoformat(row[0])
            cooldown_end = last_triggered + timedelta(seconds=cooldown_seconds)

            return datetime.now() < cooldown_end
        except sqlite3.Error as e:
            logger.error(f"Failed to check cooldown for {alert_id}: {e}")
            return False
        finally:
            conn.close()

    def _update_cooldown(self, alert_id: str) -> None:
        """Update the last triggered timestamp for an alert.

        Args:
            alert_id: The alert that was triggered
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT OR REPLACE INTO alert_cooldowns (alert_id, last_triggered)
                VALUES (?, ?)
            """,
                (alert_id, datetime.now().isoformat()),
            )

            conn.commit()
        except sqlite3.Error as e:
            logger.error(f"Failed to update cooldown for {alert_id}: {e}")
        finally:
            conn.close()

    def _send_webhook(
        self,
        webhook_url: str,
        alert_name: str,
        metric: str,
        threshold: float,
        current_value: float,
    ) -> tuple[bool, str | None]:
        """Send alert notification via webhook.

        Args:
            webhook_url: The webhook URL to send to
            alert_name: Name of the triggered alert
            metric: The metric that triggered
            threshold: The configured threshold
            current_value: The actual value

        Returns:
            Tuple of (success, error_message)
        """
        payload = {
            "text": f"Alert: {alert_name}",
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Alert Triggered: {alert_name}*\n"
                        f"Metric `{metric}` exceeded threshold.\n"
                        f"- Threshold: {threshold}\n"
                        f"- Current Value: {current_value:.2f}",
                    },
                }
            ],
        }

        try:
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                webhook_url,
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )

            with urllib.request.urlopen(req, timeout=10) as response:
                if response.status == 200:
                    logger.info(f"Webhook notification sent for alert: {alert_name}")
                    return True, None
                else:
                    error_msg = f"Webhook returned status {response.status}"
                    logger.error(error_msg)
                    return False, error_msg

        except urllib.error.URLError as e:
            error_msg = f"Webhook request failed: {e}"
            logger.error(error_msg)
            return False, error_msg
        except urllib.error.HTTPError as e:
            error_msg = f"Webhook HTTP error: {e.code} {e.reason}"
            logger.error(error_msg)
            return False, error_msg
        except OSError as e:
            error_msg = f"Webhook network error: {e}"
            logger.error(error_msg)
            return False, error_msg

    def _send_email(
        self,
        email_address: str,
        alert_name: str,
        metric: str,
        threshold: float,
        current_value: float,
        smtp_host: str = "localhost",
        smtp_port: int = 25,
        smtp_user: str | None = None,
        smtp_password: str | None = None,
    ) -> tuple[bool, str | None]:
        """Send alert notification via email.

        Args:
            email_address: The email address to send to
            alert_name: Name of the triggered alert
            metric: The metric that triggered
            threshold: The configured threshold
            current_value: The actual value
            smtp_host: SMTP server hostname
            smtp_port: SMTP server port
            smtp_user: Optional SMTP username for authentication
            smtp_password: Optional SMTP password for authentication

        Returns:
            Tuple of (success, error_message)
        """
        subject = f"Empathy Alert: {alert_name}"
        body = f"""
Empathy Framework Alert Notification

Alert: {alert_name}
Metric: {metric}
Threshold: {threshold}
Current Value: {current_value:.2f}

The metric has exceeded the configured threshold.

---
This is an automated message from Empathy Framework.
        """.strip()

        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = f"alerts@empathy-framework.local"
        msg["To"] = email_address

        try:
            with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
                if smtp_user and smtp_password:
                    server.starttls()
                    server.login(smtp_user, smtp_password)
                server.send_message(msg)

            logger.info(f"Email notification sent to {email_address} for alert: {alert_name}")
            return True, None

        except smtplib.SMTPException as e:
            error_msg = f"SMTP error: {e}"
            logger.error(error_msg)
            return False, error_msg
        except OSError as e:
            error_msg = f"Email network error: {e}"
            logger.error(error_msg)
            return False, error_msg

    def _send_notification(
        self,
        alert: dict[str, Any],
        metric: str,
        threshold: float,
        current_value: float,
    ) -> tuple[bool, str | None]:
        """Send notification based on alert channel configuration.

        Args:
            alert: Alert configuration dict
            metric: The metric that triggered
            threshold: The configured threshold
            current_value: The actual value

        Returns:
            Tuple of (success, error_message)
        """
        channel = alert["channel"]
        alert_name = alert["name"]

        if channel == "webhook":
            webhook_url = alert.get("webhook_url")
            if not webhook_url:
                error_msg = "No webhook URL configured"
                logger.error(f"Alert {alert['id']}: {error_msg}")
                return False, error_msg
            return self._send_webhook(webhook_url, alert_name, metric, threshold, current_value)

        elif channel == "email":
            email_address = alert.get("email")
            if not email_address:
                error_msg = "No email address configured"
                logger.error(f"Alert {alert['id']}: {error_msg}")
                return False, error_msg
            return self._send_email(email_address, alert_name, metric, threshold, current_value)

        elif channel == "vscode_output":
            # VSCode output just logs to stdout/logger
            message = (
                f"[ALERT] {alert_name}: {metric} = {current_value:.2f} "
                f"(threshold: {threshold})"
            )
            print(message)
            logger.warning(message)
            return True, None

        else:
            error_msg = f"Unknown notification channel: {channel}"
            logger.error(error_msg)
            return False, error_msg

    def check_alerts(self) -> list[AlertResult]:
        """Check all enabled alerts against current metrics.

        Compares current telemetry metrics against configured thresholds
        and sends notifications for triggered alerts (respecting cooldowns).

        Returns:
            List of AlertResult objects describing check outcomes

        Example:
            >>> engine = AlertEngine()
            >>> results = engine.check_alerts()
            >>> triggered = [r for r in results if r.triggered]
            >>> print(f"{len(triggered)} alerts triggered")
        """
        results: list[AlertResult] = []
        alerts = self.list_alerts()
        metrics = self.get_current_metrics()

        # Map metric names to values
        metric_values = {
            "daily_cost": metrics.daily_cost,
            "error_rate": metrics.error_rate,
            "avg_latency": metrics.avg_latency,
            "token_usage": float(metrics.token_usage),
        }

        for alert in alerts:
            alert_id = alert["id"]
            alert_name = alert["name"]
            metric = alert["metric"]
            threshold = alert["threshold"]
            enabled = alert["enabled"]
            cooldown = alert["cooldown"]

            # Skip disabled alerts
            if not enabled:
                logger.debug(f"Skipping disabled alert: {alert_id}")
                continue

            # Get current value for this metric
            current_value = metric_values.get(metric, 0.0)

            # Check if threshold is exceeded
            triggered = current_value > threshold

            result = AlertResult(
                alert_id=alert_id,
                alert_name=alert_name,
                metric=metric,
                threshold=threshold,
                current_value=current_value,
                triggered=triggered,
            )

            if triggered:
                logger.info(
                    f"Alert triggered: {alert_name} ({metric}={current_value:.2f} > {threshold})"
                )

                # Check cooldown
                if self._is_in_cooldown(alert_id, cooldown):
                    logger.debug(f"Alert {alert_id} is in cooldown, skipping notification")
                    result.notification_sent = False
                    result.notification_error = "Alert in cooldown period"
                else:
                    # Send notification
                    success, error = self._send_notification(
                        alert, metric, threshold, current_value
                    )
                    result.notification_sent = success
                    result.notification_error = error

                    if success:
                        self._update_cooldown(alert_id)

            results.append(result)

        return results


# Module-level convenience function
def check_alerts(db_path: str = ".empathy/alerts.db") -> list[AlertResult]:
    """Convenience function to check all alerts.

    Args:
        db_path: Path to alerts database

    Returns:
        List of AlertResult objects
    """
    engine = AlertEngine(db_path=db_path)
    return engine.check_alerts()
