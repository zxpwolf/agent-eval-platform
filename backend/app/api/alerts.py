"""API endpoints for cost alerting."""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..services.alerts import AlertLevel, CostAlertManager, get_alert_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/alerts", tags=["alerts"])

# Global alert manager instance
alert_manager: Optional[CostAlertManager] = None


def set_alert_manager(manager: CostAlertManager):
    """Set the alert manager instance."""
    global alert_manager
    alert_manager = manager


# Request/Response Models
class CreateAlertRequest(BaseModel):
    name: str
    threshold: float
    level: AlertLevel = AlertLevel.WARNING
    user_id: Optional[str] = None
    project_id: Optional[str] = None
    model: Optional[str] = None
    webhook_url: Optional[str] = None
    email_recipients: Optional[List[str]] = None


class RecordCostRequest(BaseModel):
    cost: float
    user_id: Optional[str] = None
    project_id: Optional[str] = None
    model: Optional[str] = None
    trace_id: Optional[str] = None


@router.post("/create")
async def create_alert(request: CreateAlertRequest):
    """Create a new cost alert."""
    if alert_manager is None:
        raise HTTPException(status_code=500, detail="Alert manager not initialized")

    alert = alert_manager.create_alert(
        name=request.name,
        threshold=request.threshold,
        level=request.level,
        user_id=request.user_id,
        project_id=request.project_id,
        model=request.model,
        webhook_url=request.webhook_url,
        email_recipients=request.email_recipients,
    )

    return {
        "alert_id": alert.alert_id,
        "message": "Alert created successfully",
    }


@router.get("/list")
async def list_alerts():
    """List all configured alerts."""
    if alert_manager is None:
        raise HTTPException(status_code=500, detail="Alert manager not initialized")

    alerts = alert_manager.list_alerts()
    return {"alerts": alerts}


@router.delete("/{alert_id}")
async def delete_alert(alert_id: str):
    """Delete a cost alert."""
    if alert_manager is None:
        raise HTTPException(status_code=500, detail="Alert manager not initialized")

    success = alert_manager.delete_alert(alert_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")

    return {"message": "Alert deleted"}


@router.post("/record-cost")
async def record_cost(request: RecordCostRequest):
    """Record a cost and check for alert triggers."""
    if alert_manager is None:
        raise HTTPException(status_code=500, detail="Alert manager not initialized")

    alert_manager.record_cost(
        cost=request.cost,
        user_id=request.user_id,
        project_id=request.project_id,
        model=request.model,
        trace_id=request.trace_id,
    )

    return {"message": "Cost recorded"}


@router.get("/summary")
async def get_cost_summary(
    user_id: Optional[str] = None,
    project_id: Optional[str] = None,
    model: Optional[str] = None,
):
    """Get cost summary."""
    if alert_manager is None:
        raise HTTPException(status_code=500, detail="Alert manager not initialized")

    summary = alert_manager.get_cost_summary(
        user_id=user_id,
        project_id=project_id,
        model=model,
    )

    return summary


@router.post("/{alert_id}/reset")
async def reset_alert(alert_id: str):
    """Reset an alert's triggered state."""
    if alert_manager is None:
        raise HTTPException(status_code=500, detail="Alert manager not initialized")

    alert_manager.reset_alert(alert_id)
    return {"message": "Alert reset"}


@router.post("/reset-all")
async def reset_all_costs():
    """Reset all cost tracking."""
    if alert_manager is None:
        raise HTTPException(status_code=500, detail="Alert manager not initialized")

    alert_manager.reset_all_costs()
    return {"message": "All costs reset"}


@router.get("/events")
async def get_event_history(limit: int = 50):
    """Get recent alert events."""
    if alert_manager is None:
        raise HTTPException(status_code=500, detail="Alert manager not initialized")

    events = alert_manager.get_event_history(limit=limit)
    return {"events": events}
