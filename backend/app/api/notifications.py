"""API endpoints for notification channel management."""

import logging
import secrets
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..services.notifications import (
    ChannelType,
    NotificationChannel,
    NotificationDispatcher,
    NotificationPayload,
    get_dispatcher,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/notifications", tags=["notifications"])

# Global dispatcher
_dispatcher: Optional[NotificationDispatcher] = None


def set_dispatcher(dispatcher: NotificationDispatcher):
    """Set the notification dispatcher instance."""
    global _dispatcher
    _dispatcher = dispatcher


# ── Request/Response Models ──────────────────────────────


class CreateChannelRequest(BaseModel):
    name: str
    channel_type: ChannelType
    enabled: bool = True
    webhook_url: Optional[str] = None
    email_from: Optional[str] = None
    email_recipients: Optional[List[str]] = None
    smtp_host: Optional[str] = None
    smtp_port: int = 587
    smtp_user: Optional[str] = None
    smtp_password: Optional[str] = None
    smtp_tls: bool = True
    min_interval_seconds: int = 300


class UpdateChannelRequest(BaseModel):
    name: Optional[str] = None
    enabled: Optional[bool] = None
    webhook_url: Optional[str] = None
    email_from: Optional[str] = None
    email_recipients: Optional[List[str]] = None
    smtp_host: Optional[str] = None
    smtp_port: Optional[int] = None
    smtp_user: Optional[str] = None
    smtp_password: Optional[str] = None
    smtp_tls: Optional[bool] = None
    min_interval_seconds: Optional[int] = None


class SendNotificationRequest(BaseModel):
    title: str
    message: str
    severity: str = "warning"
    channel_ids: Optional[List[str]] = None
    fields: Optional[Dict[str, Any]] = None


class TestChannelRequest(BaseModel):
    channel_id: str


# ── Endpoints ────────────────────────────────────────────


@router.post("/channels", status_code=201)
async def create_channel(request: CreateChannelRequest):
    """Create a new notification channel."""
    if _dispatcher is None:
        raise HTTPException(status_code=500, detail="Notification dispatcher not initialized")

    channel = NotificationChannel(
        channel_id=secrets.token_hex(8),
        name=request.name,
        channel_type=request.channel_type,
        enabled=request.enabled,
        webhook_url=request.webhook_url,
        email_from=request.email_from,
        email_recipients=request.email_recipients or [],
        smtp_host=request.smtp_host,
        smtp_port=request.smtp_port,
        smtp_user=request.smtp_user,
        smtp_password=request.smtp_password,
        smtp_tls=request.smtp_tls,
        min_interval_seconds=request.min_interval_seconds,
    )

    _dispatcher.register_channel(channel)
    return channel.to_dict()


@router.get("/channels")
async def list_channels():
    """List all notification channels."""
    if _dispatcher is None:
        raise HTTPException(status_code=500, detail="Notification dispatcher not initialized")
    return {"channels": _dispatcher.list_channels()}


@router.get("/channels/{channel_id}")
async def get_channel(channel_id: str):
    """Get a notification channel by ID."""
    if _dispatcher is None:
        raise HTTPException(status_code=500, detail="Notification dispatcher not initialized")

    channel = _dispatcher.get_channel(channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    return channel.to_dict()


@router.patch("/channels/{channel_id}")
async def update_channel(channel_id: str, request: UpdateChannelRequest):
    """Update a notification channel."""
    if _dispatcher is None:
        raise HTTPException(status_code=500, detail="Notification dispatcher not initialized")

    channel = _dispatcher.get_channel(channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    # Update fields
    for key, value in request.model_dump(exclude_unset=True).items():
        if hasattr(channel, key):
            setattr(channel, key, value)

    return channel.to_dict()


@router.delete("/channels/{channel_id}")
async def delete_channel(channel_id: str):
    """Delete a notification channel."""
    if _dispatcher is None:
        raise HTTPException(status_code=500, detail="Notification dispatcher not initialized")

    if not _dispatcher.remove_channel(channel_id):
        raise HTTPException(status_code=404, detail="Channel not found")
    return {"message": "Channel deleted"}


@router.post("/send")
async def send_notification(request: SendNotificationRequest):
    """Send a notification to specified or all enabled channels."""
    if _dispatcher is None:
        raise HTTPException(status_code=500, detail="Notification dispatcher not initialized")

    payload = NotificationPayload(
        title=request.title,
        message=request.message,
        severity=request.severity,
        fields=request.fields or {},
    )

    results = _dispatcher.dispatch(payload, channel_ids=request.channel_ids)
    return {"results": results}


@router.post("/test/{channel_id}")
async def test_channel(channel_id: str):
    """Send a test notification to a specific channel."""
    if _dispatcher is None:
        raise HTTPException(status_code=500, detail="Notification dispatcher not initialized")

    channel = _dispatcher.get_channel(channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    payload = NotificationPayload(
        title="Test Notification",
        message="This is a test notification from Agent Observability Platform.",
        severity="info",
        fields={"source": "test", "channel": channel.name},
    )

    # Bypass rate limiting for test
    channel.last_sent_at = 0
    results = _dispatcher.dispatch(payload, channel_ids=[channel_id])
    return {"results": results}
