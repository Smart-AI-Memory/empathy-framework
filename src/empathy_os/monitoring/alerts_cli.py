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

import time

import click

from empathy_os.monitoring.alerts import AlertEngine


@click.group()
def alerts() -> None:
    """Alert management commands."""
    pass


@alerts.command()
def init() -> None:
    """Initialize alert with interactive wizard."""
    click.echo("Alert Setup Wizard\n")

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
    alert_id = f"alert_{metric}_{int(time.time())}"

    engine.add_alert(
        alert_id=alert_id,
        name=f"{metric_name} Alert",
        metric=metric,
        threshold=threshold,
        channel=channel,
        webhook_url=webhook_url,
        email=email,
    )

    click.echo("\nAlert created successfully!")
    click.echo(f"   ID: {alert_id}")
    click.echo(f"   Metric: {metric_name}")
    click.echo(f"   Threshold: {threshold}")
    click.echo(f"   Channel: {channel}")

    click.echo("\nTip: Run 'empathy alerts watch' to start monitoring")


@alerts.command(name="list")
def list_cmd() -> None:
    """List all configured alerts."""
    engine = AlertEngine()
    alerts_list = engine.list_alerts()

    if not alerts_list:
        click.echo("No alerts configured. Run 'empathy alerts init' to create one.")
        return

    click.echo("Configured Alerts:\n")

    for alert in alerts_list:
        status = "Enabled" if alert["enabled"] else "Disabled"
        click.echo(f"  [{status}] {alert['name']}")
        click.echo(f"    ID: {alert['id']}")
        click.echo(f"    Metric: {alert['metric']} > {alert['threshold']}")
        click.echo(f"    Channel: {alert['channel']}")
        click.echo()


@alerts.command()
@click.argument("alert_id")
def delete(alert_id: str) -> None:
    """Delete an alert by ID."""
    engine = AlertEngine()
    deleted = engine.delete_alert(alert_id)

    if deleted:
        click.echo(f"Alert '{alert_id}' deleted successfully")
    else:
        click.echo(f"Alert '{alert_id}' not found")


@alerts.command()
@click.argument("alert_id")
def get(alert_id: str) -> None:
    """Get details of a specific alert."""
    engine = AlertEngine()
    alert = engine.get_alert(alert_id)

    if alert is None:
        click.echo(f"Alert '{alert_id}' not found")
        return

    status = "Enabled" if alert["enabled"] else "Disabled"
    click.echo(f"Alert: {alert['name']}")
    click.echo(f"  ID: {alert['id']}")
    click.echo(f"  Status: {status}")
    click.echo(f"  Metric: {alert['metric']}")
    click.echo(f"  Threshold: {alert['threshold']}")
    click.echo(f"  Channel: {alert['channel']}")
    if alert["webhook_url"]:
        click.echo(f"  Webhook URL: {alert['webhook_url']}")
    if alert["email"]:
        click.echo(f"  Email: {alert['email']}")
    click.echo(f"  Cooldown: {alert['cooldown']} seconds")
    click.echo(f"  Created: {alert['created_at']}")


@alerts.command()
@click.argument("alert_id")
def enable(alert_id: str) -> None:
    """Enable an alert."""
    engine = AlertEngine()
    updated = engine.enable_alert(alert_id, enabled=True)

    if updated:
        click.echo(f"Alert '{alert_id}' enabled")
    else:
        click.echo(f"Alert '{alert_id}' not found")


@alerts.command()
@click.argument("alert_id")
def disable(alert_id: str) -> None:
    """Disable an alert."""
    engine = AlertEngine()
    updated = engine.enable_alert(alert_id, enabled=False)

    if updated:
        click.echo(f"Alert '{alert_id}' disabled")
    else:
        click.echo(f"Alert '{alert_id}' not found")


@alerts.command()
def check() -> None:
    """Check alerts once and report status."""
    engine = AlertEngine()
    results = engine.check_alerts()

    if not results:
        click.echo("No alerts configured. Run 'empathy alerts init' to create one.")
        return

    click.echo("Alert Check Results:\n")

    triggered_count = 0
    for result in results:
        if result.triggered:
            triggered_count += 1
            status = "TRIGGERED"
            if result.notification_sent:
                status += " (notification sent)"
            elif result.notification_error:
                status += f" (notification failed: {result.notification_error})"
        else:
            status = "OK"

        click.echo(f"  [{status}] {result.alert_name}")
        click.echo(f"    {result.metric}: {result.current_value:.2f} (threshold: {result.threshold})")
        click.echo()

    click.echo(f"Summary: {triggered_count}/{len(results)} alerts triggered")


@alerts.command()
@click.option("--daemon", is_flag=True, help="Run as background daemon (enterprise)")
@click.option("--interval", default=60, help="Check interval in seconds")
def watch(daemon: bool, interval: int) -> None:
    """Watch telemetry and trigger alerts."""
    if daemon:
        click.echo("Starting alert watcher as daemon...")
        click.echo("Note: Daemon mode is an enterprise feature for 24/7 monitoring")
        click.echo("   For development, use VSCode extension polling instead.")
        # TODO: Implement daemon mode with proper process management
    else:
        click.echo(f"Starting alert watcher (checking every {interval}s, Ctrl+C to stop)...")
        click.echo("Tip: Use VSCode extension for automatic monitoring")

        engine = AlertEngine()

        try:
            while True:
                results = engine.check_alerts()
                triggered = [r for r in results if r.triggered]

                if triggered:
                    click.echo(f"\n[{time.strftime('%H:%M:%S')}] {len(triggered)} alert(s) triggered:")
                    for result in triggered:
                        click.echo(f"  - {result.alert_name}: {result.metric}={result.current_value:.2f}")
                else:
                    click.echo(f"[{time.strftime('%H:%M:%S')}] All alerts OK", nl=False)
                    click.echo("\r", nl=False)

                time.sleep(interval)
        except KeyboardInterrupt:
            click.echo("\nAlert watcher stopped")


if __name__ == "__main__":
    alerts()
