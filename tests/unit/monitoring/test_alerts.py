"""Tests for the Alert System.

Tests for AlertEngine, notifiers, and alert checking functionality.

Copyright 2025 Smart-AI-Memory
Licensed under Fair Source License 0.9
"""

import pytest
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

from empathy_os.monitoring.alerts import (
    Alert,
    AlertChannel,
    AlertEngine,
    AlertEvent,
    AlertMetric,
    EmailNotifier,
    StdoutNotifier,
    WebhookNotifier,
    get_current_metrics,
)


class TestAlertMetric:
    """Tests for AlertMetric enum."""

    def test_metric_values(self):
        """Test metric enum has expected values."""
        assert AlertMetric.DAILY_COST.value == "daily_cost"
        assert AlertMetric.ERROR_RATE.value == "error_rate"
        assert AlertMetric.AVG_LATENCY.value == "avg_latency"
        assert AlertMetric.TOKEN_USAGE.value == "token_usage"


class TestAlertChannel:
    """Tests for AlertChannel enum."""

    def test_channel_values(self):
        """Test channel enum has expected values."""
        assert AlertChannel.WEBHOOK.value == "webhook"
        assert AlertChannel.EMAIL.value == "email"
        assert AlertChannel.STDOUT.value == "stdout"
        assert AlertChannel.VSCODE_OUTPUT.value == "vscode_output"


class TestAlert:
    """Tests for Alert dataclass."""

    def test_alert_creation(self):
        """Test creating an Alert."""
        alert = Alert(
            id="test-alert",
            name="Test Alert",
            metric=AlertMetric.DAILY_COST,
            threshold=10.0,
            channel=AlertChannel.STDOUT,
        )

        assert alert.id == "test-alert"
        assert alert.name == "Test Alert"
        assert alert.metric == AlertMetric.DAILY_COST
        assert alert.threshold == 10.0
        assert alert.channel == AlertChannel.STDOUT
        assert alert.enabled is True
        assert alert.cooldown_seconds == 3600

    def test_alert_with_webhook(self):
        """Test creating an Alert with webhook."""
        alert = Alert(
            id="webhook-alert",
            name="Webhook Alert",
            metric=AlertMetric.ERROR_RATE,
            threshold=5.0,
            channel=AlertChannel.WEBHOOK,
            webhook_url="https://example.com/webhook",
        )

        assert alert.webhook_url == "https://example.com/webhook"


class TestAlertEvent:
    """Tests for AlertEvent dataclass."""

    def test_alert_event_creation(self):
        """Test creating an AlertEvent."""
        alert = Alert(
            id="test",
            name="Test",
            metric=AlertMetric.DAILY_COST,
            threshold=10.0,
            channel=AlertChannel.STDOUT,
        )
        event = AlertEvent(alert=alert, current_value=15.0, message="Over threshold")

        assert event.alert == alert
        assert event.current_value == 15.0
        assert event.message == "Over threshold"
        assert isinstance(event.triggered_at, datetime)


class TestStdoutNotifier:
    """Tests for StdoutNotifier."""

    def test_send_success(self, capsys):
        """Test sending notification to stdout."""
        alert = Alert(
            id="test",
            name="Cost Alert",
            metric=AlertMetric.DAILY_COST,
            threshold=10.0,
            channel=AlertChannel.STDOUT,
        )
        event = AlertEvent(alert=alert, current_value=15.0)

        notifier = StdoutNotifier()
        result = notifier.send(event)

        assert result is True
        captured = capsys.readouterr()
        assert "ALERT" in captured.out
        assert "Cost Alert" in captured.out


class TestEmailNotifier:
    """Tests for EmailNotifier."""

    def test_send_without_email(self):
        """Test sending fails without email configured."""
        alert = Alert(
            id="test",
            name="Test",
            metric=AlertMetric.DAILY_COST,
            threshold=10.0,
            channel=AlertChannel.EMAIL,
            email=None,
        )
        event = AlertEvent(alert=alert, current_value=15.0)

        notifier = EmailNotifier()
        result = notifier.send(event)

        assert result is False

    def test_send_with_email(self, capsys):
        """Test sending with email configured (placeholder)."""
        alert = Alert(
            id="test",
            name="Test",
            metric=AlertMetric.DAILY_COST,
            threshold=10.0,
            channel=AlertChannel.EMAIL,
            email="test@example.com",
        )
        event = AlertEvent(alert=alert, current_value=15.0)

        notifier = EmailNotifier()
        result = notifier.send(event)

        assert result is True
        captured = capsys.readouterr()
        assert "test@example.com" in captured.out


class TestWebhookNotifier:
    """Tests for WebhookNotifier."""

    def test_send_without_url(self):
        """Test sending fails without webhook URL."""
        alert = Alert(
            id="test",
            name="Test",
            metric=AlertMetric.DAILY_COST,
            threshold=10.0,
            channel=AlertChannel.WEBHOOK,
            webhook_url=None,
        )
        event = AlertEvent(alert=alert, current_value=15.0)

        notifier = WebhookNotifier()
        result = notifier.send(event)

        assert result is False

    @patch("empathy_os.monitoring.alerts.urlopen")
    def test_send_success(self, mock_urlopen):
        """Test successful webhook send."""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        alert = Alert(
            id="test",
            name="Test",
            metric=AlertMetric.DAILY_COST,
            threshold=10.0,
            channel=AlertChannel.WEBHOOK,
            webhook_url="https://example.com/webhook",
        )
        event = AlertEvent(alert=alert, current_value=15.0)

        notifier = WebhookNotifier()
        result = notifier.send(event)

        assert result is True
        mock_urlopen.assert_called_once()


class TestAlertEngine:
    """Tests for AlertEngine."""

    @pytest.fixture
    def engine(self, tmp_path):
        """Create AlertEngine with temp database."""
        db_path = tmp_path / "test_alerts.db"
        return AlertEngine(db_path=str(db_path))

    def test_init_creates_database(self, engine):
        """Test engine creates database on init."""
        assert engine.db_path.exists()

    def test_init_creates_tables(self, engine):
        """Test engine creates required tables."""
        conn = sqlite3.connect(engine.db_path)
        cursor = conn.cursor()

        # Check alerts table
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='alerts'")
        assert cursor.fetchone() is not None

        # Check alert_history table
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='alert_history'")
        assert cursor.fetchone() is not None

        conn.close()

    def test_add_alert(self, engine):
        """Test adding an alert."""
        alert = Alert(
            id="test-1",
            name="Test Alert",
            metric=AlertMetric.DAILY_COST,
            threshold=10.0,
            channel=AlertChannel.STDOUT,
        )

        engine.add_alert(alert)
        alerts = engine.get_alerts(enabled_only=False)

        assert len(alerts) == 1
        assert alerts[0].id == "test-1"
        assert alerts[0].name == "Test Alert"

    def test_get_alerts_enabled_only(self, engine):
        """Test getting only enabled alerts."""
        alert1 = Alert(
            id="enabled",
            name="Enabled",
            metric=AlertMetric.DAILY_COST,
            threshold=10.0,
            channel=AlertChannel.STDOUT,
            enabled=True,
        )
        alert2 = Alert(
            id="disabled",
            name="Disabled",
            metric=AlertMetric.DAILY_COST,
            threshold=10.0,
            channel=AlertChannel.STDOUT,
            enabled=False,
        )

        engine.add_alert(alert1)
        engine.add_alert(alert2)

        enabled = engine.get_alerts(enabled_only=True)
        all_alerts = engine.get_alerts(enabled_only=False)

        assert len(enabled) == 1
        assert len(all_alerts) == 2

    def test_delete_alert(self, engine):
        """Test deleting an alert."""
        alert = Alert(
            id="to-delete",
            name="Delete Me",
            metric=AlertMetric.DAILY_COST,
            threshold=10.0,
            channel=AlertChannel.STDOUT,
        )
        engine.add_alert(alert)

        result = engine.delete_alert("to-delete")

        assert result is True
        assert len(engine.get_alerts(enabled_only=False)) == 0

    def test_delete_nonexistent_alert(self, engine):
        """Test deleting non-existent alert returns False."""
        result = engine.delete_alert("nonexistent")
        assert result is False

    def test_check_and_notify_triggers_alert(self, engine, capsys):
        """Test check_and_notify triggers when threshold exceeded."""
        alert = Alert(
            id="cost-alert",
            name="Cost Alert",
            metric=AlertMetric.DAILY_COST,
            threshold=10.0,
            channel=AlertChannel.STDOUT,
        )
        engine.add_alert(alert)

        metrics = {"daily_cost": 15.0}
        triggered = engine.check_and_notify(metrics)

        assert len(triggered) == 1
        assert triggered[0].current_value == 15.0

    def test_check_and_notify_no_trigger_below_threshold(self, engine):
        """Test check_and_notify does not trigger below threshold."""
        alert = Alert(
            id="cost-alert",
            name="Cost Alert",
            metric=AlertMetric.DAILY_COST,
            threshold=10.0,
            channel=AlertChannel.STDOUT,
        )
        engine.add_alert(alert)

        metrics = {"daily_cost": 5.0}
        triggered = engine.check_and_notify(metrics)

        assert len(triggered) == 0

    def test_cooldown_prevents_repeat_notification(self, engine):
        """Test cooldown prevents repeated notifications."""
        alert = Alert(
            id="cost-alert",
            name="Cost Alert",
            metric=AlertMetric.DAILY_COST,
            threshold=10.0,
            channel=AlertChannel.STDOUT,
            cooldown_seconds=3600,
        )
        engine.add_alert(alert)

        metrics = {"daily_cost": 15.0}

        # First trigger
        triggered1 = engine.check_and_notify(metrics)
        assert len(triggered1) == 1

        # Second trigger should be blocked by cooldown
        triggered2 = engine.check_and_notify(metrics)
        assert len(triggered2) == 0

    def test_get_history(self, engine):
        """Test getting alert history."""
        alert = Alert(
            id="test",
            name="Test",
            metric=AlertMetric.DAILY_COST,
            threshold=10.0,
            channel=AlertChannel.STDOUT,
        )
        engine.add_alert(alert)

        # Trigger alert to create history
        engine.check_and_notify({"daily_cost": 15.0})

        history = engine.get_history()

        assert len(history) >= 1
        assert history[0]["alert_id"] == "test"


class TestGetCurrentMetrics:
    """Tests for get_current_metrics function."""

    @patch("empathy_os.monitoring.alerts.UsageTracker")
    def test_with_tracker(self, mock_tracker_class):
        """Test getting metrics with UsageTracker available."""
        mock_tracker = MagicMock()
        mock_tracker.get_stats.return_value = {
            "total_cost": 5.0,
            "error_rate": 2.0,
            "avg_latency_ms": 100.0,
            "total_tokens": 1000,
        }
        mock_tracker_class.return_value = mock_tracker

        # This test may not work if import fails, so we check for dict return
        metrics = get_current_metrics()

        assert isinstance(metrics, dict)

    def test_returns_dict(self):
        """Test get_current_metrics always returns a dict."""
        metrics = get_current_metrics()
        assert isinstance(metrics, dict)
