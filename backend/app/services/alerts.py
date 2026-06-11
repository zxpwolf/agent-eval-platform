"""Cost alerting system for monitoring API expenses.

This module provides functionality to track costs and send alerts
when spending exceeds configured thresholds.
"""

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class AlertLevel(str, Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class CostAlert:
    """Configuration for a cost alert."""
    alert_id: str
    name: str
    threshold: float  # Dollar amount
    level: AlertLevel = AlertLevel.WARNING
    enabled: bool = True

    # Scope filters
    user_id: Optional[str] = None
    project_id: Optional[str] = None
    model: Optional[str] = None

    # Notification config
    webhook_url: Optional[str] = None
    email_recipients: List[str] = field(default_factory=list)

    # State
    triggered: bool = False
    last_triggered_at: Optional[float] = None
    trigger_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "alert_id": self.alert_id,
            "name": self.name,
            "threshold": self.threshold,
            "level": self.level.value,
            "enabled": self.enabled,
            "user_id": self.user_id,
            "project_id": self.project_id,
            "model": self.model,
            "webhook_url": self.webhook_url,
            "email_recipients": self.email_recipients,
            "triggered": self.triggered,
            "last_triggered_at": self.last_triggered_at,
            "trigger_count": self.trigger_count,
        }


@dataclass
class CostEvent:
    """A cost event that triggered an alert."""
    alert_id: str
    current_cost: float
    threshold: float
    exceeded_by: float
    timestamp: float
    context: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "alert_id": self.alert_id,
            "current_cost": self.current_cost,
            "threshold": self.threshold,
            "exceeded_by": self.exceeded_by,
            "timestamp": self.timestamp,
            "context": self.context,
        }


class CostAlertManager:
    """Manages cost alerts and notifications.

    Tracks spending across different dimensions and triggers alerts
    when thresholds are exceeded.
    """

    def __init__(self):
        self._alerts: Dict[str, CostAlert] = {}
        self._cost_tracker: Dict[str, float] = {}
        self._event_history: List[CostEvent] = []
        self._notification_handlers: Dict[str, Callable] = {}

    def create_alert(
        self,
        name: str,
        threshold: float,
        level: AlertLevel = AlertLevel.WARNING,
        user_id: Optional[str] = None,
        project_id: Optional[str] = None,
        model: Optional[str] = None,
        webhook_url: Optional[str] = None,
        email_recipients: Optional[List[str]] = None,
    ) -> CostAlert:
        """Create a new cost alert."""
        import uuid

        alert = CostAlert(
            alert_id=str(uuid.uuid4()),
            name=name,
            threshold=threshold,
            level=level,
            user_id=user_id,
            project_id=project_id,
            model=model,
            webhook_url=webhook_url,
            email_recipients=email_recipients or [],
        )
        self._alerts[alert.alert_id] = alert
        logger.info(f"Created cost alert: {name} (threshold: ${threshold})")
        return alert

    def delete_alert(self, alert_id: str) -> bool:
        """Delete a cost alert."""
        if alert_id in self._alerts:
            del self._alerts[alert_id]
            return True
        return False

    def list_alerts(self) -> List[Dict[str, Any]]:
        """List all configured alerts."""
        return [alert.to_dict() for alert in self._alerts.values()]

    def record_cost(
        self,
        cost: float,
        user_id: Optional[str] = None,
        project_id: Optional[str] = None,
        model: Optional[str] = None,
        trace_id: Optional[str] = None,
    ):
        """Record a cost and check for alert triggers."""
        # Build tracker key
        key_parts = []
        if user_id:
            key_parts.append(f"user:{user_id}")
        if project_id:
            key_parts.append(f"project:{project_id}")
        if model:
            key_parts.append(f"model:{model}")

        key = "|".join(key_parts) if key_parts else "global"

        # Update cost tracker
        self._cost_tracker[key] = self._cost_tracker.get(key, 0.0) + cost

        # Check alerts
        current_cost = self._cost_tracker[key]
        self._check_alerts(current_cost, key, user_id, project_id, model, trace_id)

    def _check_alerts(
        self,
        current_cost: float,
        key: str,
        user_id: Optional[str],
        project_id: Optional[str],
        model: Optional[str],
        trace_id: Optional[str],
    ):
        """Check if any alerts should be triggered."""
        for alert in self._alerts.values():
            if not alert.enabled:
                continue

            # Check scope filters
            if alert.user_id and alert.user_id != user_id:
                continue
            if alert.project_id and alert.project_id != project_id:
                continue
            if alert.model and alert.model != model:
                continue

            # Check threshold
            if current_cost >= alert.threshold and not alert.triggered:
                self._trigger_alert(alert, current_cost, trace_id)

    def _trigger_alert(
        self,
        alert: CostAlert,
        current_cost: float,
        trace_id: Optional[str] = None,
    ):
        """Trigger an alert and send notifications."""
        exceeded_by = current_cost - alert.threshold

        event = CostEvent(
            alert_id=alert.alert_id,
            current_cost=current_cost,
            threshold=alert.threshold,
            exceeded_by=exceeded_by,
            timestamp=time.time(),
            context={
                "trace_id": trace_id,
                "message": f"Cost alert '{alert.name}' triggered: ${current_cost:.4f} exceeds ${alert.threshold:.4f} threshold",
            },
        )

        # Update alert state
        alert.triggered = True
        alert.last_triggered_at = event.timestamp
        alert.trigger_count += 1

        # Store event
        self._event_history.append(event)

        # Send notifications
        self._send_notifications(alert, event)

        logger.warning(
            f"Cost alert triggered: {alert.name} - "
            f"${current_cost:.4f} exceeds ${alert.threshold:.4f} by ${exceeded_by:.4f}"
        )

    def _send_notifications(self, alert: CostAlert, event: CostEvent):
        """Send notifications for an alert."""
        # Webhook notification
        if alert.webhook_url:
            self._send_webhook(alert.webhook_url, event)

        # Email notification (placeholder - would need email service)
        if alert.email_recipients:
            self._send_email(alert.email_recipients, alert, event)

    def _send_webhook(self, url: str, event: CostEvent):
        """Send webhook notification."""
        try:
            import requests

            payload = {
                "alert_type": "cost_threshold_exceeded",
                **event.to_dict(),
            }
            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
            logger.info(f"Webhook notification sent for alert {event.alert_id}")
        except Exception as e:
            logger.error(f"Failed to send webhook notification: {e}")

    def _send_email(
        self,
        recipients: List[str],
        alert: CostAlert,
        event: CostEvent,
    ):
        """Send email notification (placeholder)."""
        # In production, integrate with email service (SES, SendGrid, etc.)
        logger.info(
            f"Email notification would be sent to {recipients} for alert {alert.name}"
        )

    def get_cost_summary(
        self,
        user_id: Optional[str] = None,
        project_id: Optional[str] = None,
        model: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get cost summary for specified filters."""
        key_parts = []
        if user_id:
            key_parts.append(f"user:{user_id}")
        if project_id:
            key_parts.append(f"project:{project_id}")
        if model:
            key_parts.append(f"model:{model}")

        key = "|".join(key_parts) if key_parts else "global"

        return {
            "current_cost": self._cost_tracker.get(key, 0.0),
            "active_alerts": len([a for a in self._alerts.values() if a.enabled]),
            "triggered_alerts": len([a for a in self._alerts.values() if a.triggered]),
            "total_events": len(self._event_history),
        }

    def reset_alert(self, alert_id: str):
        """Reset an alert's triggered state."""
        alert = self._alerts.get(alert_id)
        if alert:
            alert.triggered = False
            logger.info(f"Reset alert: {alert.name}")

    def reset_all_costs(self):
        """Reset all cost tracking."""
        self._cost_tracker.clear()
        for alert in self._alerts.values():
            alert.triggered = False
        logger.info("Reset all cost tracking")

    def get_event_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent alert events."""
        return [event.to_dict() for event in self._event_history[-limit:]]


# Global alert manager instance
_default_manager: Optional[CostAlertManager] = None


def get_alert_manager() -> CostAlertManager:
    """Get the global alert manager."""
    global _default_manager
    if _default_manager is None:
        _default_manager = CostAlertManager()
    return _default_manager


def set_alert_manager(manager: CostAlertManager):
    """Set the global alert manager."""
    global _default_manager
    _default_manager = manager
