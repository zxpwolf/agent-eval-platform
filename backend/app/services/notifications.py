"""Notification channels for alert dispatching.

Supports Slack webhooks, email (SMTP), and generic webhooks.
Channels are registered with the alert manager and invoked when
alerts are triggered.
"""

import json
import logging
import smtplib
import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Any, Dict, List, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class ChannelType(str, Enum):
    """Supported notification channel types."""
    WEBHOOK = "webhook"
    SLACK = "slack"
    EMAIL = "email"


@dataclass
class NotificationChannel:
    """Configuration for a notification channel."""
    channel_id: str
    name: str
    channel_type: ChannelType
    enabled: bool = True

    # Channel-specific config
    webhook_url: Optional[str] = None       # Generic webhook or Slack webhook URL
    email_from: Optional[str] = None        # SMTP sender address
    email_recipients: List[str] = field(default_factory=list)
    smtp_host: Optional[str] = None
    smtp_port: int = 587
    smtp_user: Optional[str] = None
    smtp_password: Optional[str] = None
    smtp_tls: bool = True

    # Headers / custom fields
    headers: Dict[str, str] = field(default_factory=dict)

    # Rate limiting
    min_interval_seconds: int = 300  # 5 min between notifications per channel
    last_sent_at: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "channel_id": self.channel_id,
            "name": self.name,
            "channel_type": self.channel_type.value,
            "enabled": self.enabled,
            "webhook_url": self.webhook_url,
            "email_from": self.email_from,
            "email_recipients": self.email_recipients,
            "smtp_host": self.smtp_host,
            "smtp_port": self.smtp_port,
            "smtp_tls": self.smtp_tls,
            "min_interval_seconds": self.min_interval_seconds,
            "last_sent_at": self.last_sent_at,
        }
        return d


@dataclass
class NotificationPayload:
    """Data to send via a notification channel."""
    title: str
    message: str
    severity: str = "warning"
    timestamp: float = field(default_factory=time.time)
    fields: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "message": self.message,
            "severity": self.severity,
            "timestamp": self.timestamp,
            "fields": self.fields,
        }


class NotificationDispatcher:
    """Manages notification channels and dispatches alert notifications."""

    def __init__(self):
        self._channels: Dict[str, NotificationChannel] = {}

    def register_channel(self, channel: NotificationChannel) -> None:
        """Register a notification channel."""
        self._channels[channel.channel_id] = channel
        logger.info(f"Registered notification channel: {channel.name} ({channel.channel_type.value})")

    def remove_channel(self, channel_id: str) -> bool:
        """Remove a notification channel."""
        if channel_id in self._channels:
            del self._channels[channel_id]
            return True
        return False

    def list_channels(self) -> List[Dict[str, Any]]:
        """List all registered channels."""
        return [ch.to_dict() for ch in self._channels.values()]

    def get_channel(self, channel_id: str) -> Optional[NotificationChannel]:
        """Get a channel by ID."""
        return self._channels.get(channel_id)

    def dispatch(self, payload: NotificationPayload, channel_ids: Optional[List[str]] = None) -> Dict[str, Any]:
        """Dispatch a notification to specified channels (or all enabled channels).

        Returns a dict with per-channel send results.
        """
        target_channels = []
        if channel_ids:
            for cid in channel_ids:
                ch = self._channels.get(cid)
                if ch and ch.enabled:
                    target_channels.append(ch)
        else:
            target_channels = [ch for ch in self._channels.values() if ch.enabled]

        results = {}
        for ch in target_channels:
            # Rate limiting
            now = time.time()
            if now - ch.last_sent_at < ch.min_interval_seconds:
                results[ch.channel_id] = {"status": "rate_limited", "message": "Too soon since last notification"}
                continue

            try:
                if ch.channel_type == ChannelType.WEBHOOK:
                    self._send_webhook(ch, payload)
                elif ch.channel_type == ChannelType.SLACK:
                    self._send_slack(ch, payload)
                elif ch.channel_type == ChannelType.EMAIL:
                    self._send_email(ch, payload)
                else:
                    results[ch.channel_id] = {"status": "error", "message": f"Unknown channel type: {ch.channel_type}"}
                    continue

                ch.last_sent_at = now
                results[ch.channel_id] = {"status": "sent"}
            except Exception as e:
                logger.error(f"Failed to send notification via {ch.name}: {e}")
                results[ch.channel_id] = {"status": "error", "message": str(e)}

        return results

    # ── Webhook ────────────────────────────────────────────

    def _send_webhook(self, channel: NotificationChannel, payload: NotificationPayload) -> None:
        """Send a generic webhook notification."""
        import urllib.request
        import urllib.error

        if not channel.webhook_url:
            raise ValueError(f"Webhook channel '{channel.name}' has no URL configured")

        data = json.dumps(payload.to_dict()).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        headers.update(channel.headers)

        req = urllib.request.Request(
            channel.webhook_url,
            data=data,
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status >= 400:
                raise RuntimeError(f"Webhook returned {resp.status}")

        logger.info(f"Webhook notification sent to {channel.name}")

    # ── Slack ──────────────────────────────────────────────

    def _send_slack(self, channel: NotificationChannel, payload: NotificationPayload) -> None:
        """Send a Slack webhook notification with formatted blocks."""
        import urllib.request
        import urllib.error

        if not channel.webhook_url:
            raise ValueError(f"Slack channel '{channel.name}' has no webhook URL configured")

        severity_emoji = {
            "info": ":information_source:",
            "warning": ":warning:",
            "critical": ":rotating_light:",
        }
        emoji = severity_emoji.get(payload.severity, ":bell:")

        # Build Slack block message
        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": f"{emoji} {payload.title}"},
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": payload.message},
            },
        ]

        # Add fields if present
        if payload.fields:
            field_blocks = []
            for key, value in payload.fields.items():
                field_blocks.append({
                    "type": "mrkdwn",
                    "text": f"*{key}:* {value}",
                })
            if field_blocks:
                blocks.append({
                    "type": "section",
                    "fields": field_blocks[:10],  # Slack max 10 fields
                })

        slack_payload = {
            "blocks": blocks,
            "text": f"{emoji} {payload.title}: {payload.message[:100]}",
        }

        data = json.dumps(slack_payload).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        headers.update(channel.headers)

        req = urllib.request.Request(
            channel.webhook_url,
            data=data,
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status >= 400:
                raise RuntimeError(f"Slack webhook returned {resp.status}")

        logger.info(f"Slack notification sent to {channel.name}")

    # ── Email ──────────────────────────────────────────────

    def _send_email(self, channel: NotificationChannel, payload: NotificationPayload) -> None:
        """Send an email notification via SMTP."""
        if not channel.email_recipients:
            raise ValueError(f"Email channel '{channel.name}' has no recipients")

        smtp_host = channel.smtp_host or os.environ.get("SMTP_HOST", "localhost")
        smtp_port = channel.smtp_port
        smtp_user = channel.smtp_user or os.environ.get("SMTP_USER")
        smtp_password = channel.smtp_password or os.environ.get("SMTP_PASSWORD")
        email_from = channel.email_from or os.environ.get("SMTP_FROM", "alerts@agent-eval.local")

        # Build email
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"[{payload.severity.upper()}] {payload.title}"
        msg["From"] = email_from
        msg["To"] = ", ".join(channel.email_recipients)

        # Plain text body
        text_body = f"{payload.message}\n\n"
        if payload.fields:
            text_body += "Details:\n"
            for key, value in payload.fields.items():
                text_body += f"  {key}: {value}\n"

        # HTML body
        severity_colors = {
            "info": "#36a64f",
            "warning": "#f2c744",
            "critical": "#e01e5a",
        }
        color = severity_colors.get(payload.severity, "#666666")

        html_body = f"""
        <html><body style="font-family: sans-serif;">
        <div style="border-left: 4px solid {color}; padding: 12px 20px; margin: 16px 0; background: #f9f9f9;">
            <h2 style="margin:0; color: {color};">{payload.severity.upper()}: {payload.title}</h2>
            <p style="margin: 8px 0;">{payload.message}</p>
        </div>
        """
        if payload.fields:
            html_body += '<table style="border-collapse: collapse; margin: 8px 0;">'
            for key, value in payload.fields.items():
                html_body += f'<tr><td style="padding: 4px 12px; font-weight: bold;">{key}:</td><td style="padding: 4px 12px;">{value}</td></tr>'
            html_body += '</table>'
        html_body += '</body></html>'

        msg.attach(MIMEText(text_body, "plain"))
        msg.attach(MIMEText(html_body, "html"))

        # Send
        try:
            if channel.smtp_tls:
                server = smtplib.SMTP(smtp_host, smtp_port)
                server.starttls()
            else:
                server = smtplib.SMTP(smtp_host, smtp_port)

            if smtp_user and smtp_password:
                server.login(smtp_user, smtp_password)

            server.sendmail(email_from, channel.email_recipients, msg.as_string())
            server.quit()
            logger.info(f"Email notification sent to {channel.email_recipients}")
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            raise


# ── Global dispatcher ────────────────────────────────────

_dispatcher: Optional[NotificationDispatcher] = None


def get_dispatcher() -> NotificationDispatcher:
    """Get the global notification dispatcher."""
    global _dispatcher
    if _dispatcher is None:
        _dispatcher = NotificationDispatcher()
    return _dispatcher


def set_dispatcher(dispatcher: NotificationDispatcher) -> None:
    """Set the global notification dispatcher."""
    global _dispatcher
    _dispatcher = dispatcher
