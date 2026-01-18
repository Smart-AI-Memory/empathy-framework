"""Alert CLI Wizard

Interactive wizard for setting up LLM telemetry alerts.

**Usage:**
    empathy alerts init
    empathy alerts list
    empathy alerts delete <id>
    empathy alerts watch [--daemon]

**Implementation:** Sprint 3 (Week 3)

Copyright 2025 Smart-AI-Memory
Licensed under Fair Source License 0.9
"""

import sqlite3
from pathlib import Path
from typing import Any

import click


class AlertEngine:
    """Alert engine with SQLite storage"""

    def __init__(self, db_path: str = ".empathy/alerts.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        """Initialize SQLite database"""
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
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
        )

        conn.commit()
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
    ) -> None:
        """Add a new alert"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO alerts (id, name, metric, threshold, channel, webhook_url, email)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
            (alert_id, name, metric, threshold, channel, webhook_url, email),
        )

        conn.commit()
        conn.close()

    def list_alerts(self) -> list[dict[str, Any]]:
        """List all alerts"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM alerts")
        rows = cursor.fetchall()

        conn.close()

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

    def delete_alert(self, alert_id: str) -> bool:
        """Delete an alert by ID"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("DELETE FROM alerts WHERE id = ?", (alert_id,))
        deleted = cursor.rowcount > 0

        conn.commit()
        conn.close()

        return deleted


@click.group()
def alerts():
    """Alert management commands"""
    pass


@alerts.command()
def init():
    """Initialize alert with interactive wizard"""
    click.echo("🔔 Alert Setup Wizard\n")

    # Question 1: What metric?
    click.echo("1. What metric do you want to monitor?")
    click.echo("   a) Daily cost")
    click.echo("   b) Error rate")
    click.echo("   c) Latency (avg response time)")
    click.echo("   d) Token usage")

    metric_choice = click.prompt("Choose (a/b/c/d)", type=click.Choice(["a", "b", "c", "d"]))

    metric_map = {
        "a": ("daily_cost", "Daily Cost"),
        "b": ("error_rate", "Error Rate"),
        "c": ("avg_latency", "Average Latency"),
        "d": ("token_usage", "Token Usage"),
    }

    metric, metric_name = metric_map[metric_choice]

    # Question 2: What threshold?
    click.echo(f"\n2. What threshold for {metric_name}?")
    if metric == "daily_cost":
        threshold = click.prompt("Daily cost threshold (USD)", type=float, default=10.0)
    elif metric == "error_rate":
        threshold = click.prompt("Error rate threshold (%)", type=float, default=10.0)
    elif metric == "avg_latency":
        threshold = click.prompt("Latency threshold (ms)", type=int, default=3000)
    else:  # token_usage
        threshold = click.prompt("Token usage threshold", type=int, default=100000)

    # Question 3: Where to send?
    click.echo("\n3. Where should alerts be sent?")
    click.echo("   a) Webhook (Slack, Discord, etc.)")
    click.echo("   b) Email")
    click.echo("   c) VSCode output (console)")

    channel_choice = click.prompt("Choose (a/b/c)", type=click.Choice(["a", "b", "c"]))

    channel_map = {
        "a": "webhook",
        "b": "email",
        "c": "vscode_output",
    }

    channel = channel_map[channel_choice]

    webhook_url = None
    email = None

    if channel == "webhook":
        webhook_url = click.prompt("Webhook URL")
    elif channel == "email":
        email = click.prompt("Email address")

    # Create alert
    engine = AlertEngine()
    alert_id = f"alert_{metric}_{int(__import__('time').time())}"

    engine.add_alert(
        alert_id=alert_id,
        name=f"{metric_name} Alert",
        metric=metric,
        threshold=threshold,
        channel=channel,
        webhook_url=webhook_url,
        email=email,
    )

    click.echo("\n✅ Alert created successfully!")
    click.echo(f"   ID: {alert_id}")
    click.echo(f"   Metric: {metric_name}")
    click.echo(f"   Threshold: {threshold}")
    click.echo(f"   Channel: {channel}")

    click.echo("\n💡 Tip: Run 'empathy alerts watch' to start monitoring")


@alerts.command(name="list")
def list_cmd():
    """List all configured alerts"""
    engine = AlertEngine()
    alerts_list = engine.list_alerts()

    if not alerts_list:
        click.echo("No alerts configured. Run 'empathy alerts init' to create one.")
        return

    click.echo("📋 Configured Alerts:\n")

    for alert in alerts_list:
        status = "✓ Enabled" if alert["enabled"] else "✗ Disabled"
        click.echo(f"  [{status}] {alert['name']}")
        click.echo(f"    ID: {alert['id']}")
        click.echo(f"    Metric: {alert['metric']} > {alert['threshold']}")
        click.echo(f"    Channel: {alert['channel']}")
        click.echo()


@alerts.command()
@click.argument("alert_id")
def delete(alert_id: str):
    """Delete an alert by ID"""
    engine = AlertEngine()
    deleted = engine.delete_alert(alert_id)

    if deleted:
        click.echo(f"✅ Alert '{alert_id}' deleted successfully")
    else:
        click.echo(f"❌ Alert '{alert_id}' not found")


@alerts.command()
@click.option("--daemon", is_flag=True, help="Run as background daemon (enterprise)")
@click.option("--interval", default=60, help="Check interval in seconds (default: 60)")
def watch(daemon: bool, interval: int):
    """Watch telemetry and trigger alerts"""
    from empathy_os.monitoring.alerts import AlertEngine, get_current_metrics

    engine = AlertEngine()

    if daemon:
        click.echo("🔄 Starting alert watcher as daemon...")
        click.echo("⚠️  Note: Daemon mode is an enterprise feature for 24/7 monitoring")
        click.echo("   For development, use VSCode extension polling instead.")
        # Daemon mode would fork to background - not implemented for CLI
        click.echo("   Running in foreground mode instead...")

    click.echo(f"🔄 Starting alert watcher (checking every {interval}s, Ctrl+C to stop)...")
    click.echo("💡 Tip: Use VSCode extension for automatic monitoring")

    alerts_list = engine.get_alerts()
    if not alerts_list:
        click.echo("⚠️  No alerts configured. Run 'empathy alerts init' first.")
        return

    click.echo(f"   Monitoring {len(alerts_list)} alert(s)")

    try:
        check_count = 0
        while True:
            check_count += 1
            metrics = get_current_metrics()

            if metrics:
                triggered = engine.check_and_notify(metrics)
                if triggered:
                    for event in triggered:
                        click.echo(f"🚨 Triggered: {event.alert.name}")
                else:
                    # Only show status every 5 checks to reduce noise
                    if check_count % 5 == 0:
                        click.echo(f"   ✓ Check #{check_count}: All metrics within thresholds")

            __import__("time").sleep(interval)
    except KeyboardInterrupt:
        click.echo(f"\n✓ Alert watcher stopped after {check_count} checks")


if __name__ == "__main__":
    alerts()
