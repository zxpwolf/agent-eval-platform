"""API endpoints for custom dashboard builder."""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..services.dashboards import (
    WidgetType,
    create_dashboard,
    get_dashboard,
    list_dashboards,
    update_dashboard,
    delete_dashboard,
    add_widget,
    update_widget,
    delete_widget,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/dashboards", tags=["dashboards"])


# ── Request Models ───────────────────────────────────────


class CreateDashboardRequest(BaseModel):
    name: str
    description: str = ""
    is_public: bool = False


class UpdateDashboardRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    layout: Optional[List[Dict[str, Any]]] = None
    is_public: Optional[bool] = None


class AddWidgetRequest(BaseModel):
    widget_type: str
    title: str
    config: Optional[Dict[str, Any]] = None
    position_x: int = 0
    position_y: int = 0
    width: int = 4
    height: int = 2


class UpdateWidgetRequest(BaseModel):
    widget_type: Optional[str] = None
    title: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    position_x: Optional[int] = None
    position_y: Optional[int] = None
    width: Optional[int] = None
    height: Optional[int] = None


class BatchWidgetUpdateRequest(BaseModel):
    widgets: List[Dict[str, Any]]


# ── Dashboard Endpoints ─────────────────────────────────


@router.post("/", status_code=201)
async def api_create_dashboard(request: CreateDashboardRequest):
    """Create a new dashboard."""
    return create_dashboard(
        name=request.name,
        description=request.description,
        is_public=request.is_public,
    )


@router.get("/")
async def api_list_dashboards(limit: int = 50, offset: int = 0):
    """List all dashboards."""
    dashboards = list_dashboards(limit=limit, offset=offset)
    return {"dashboards": dashboards}


@router.get("/{dashboard_id}")
async def api_get_dashboard(dashboard_id: str):
    """Get a dashboard with its widgets."""
    dashboard = get_dashboard(dashboard_id)
    if not dashboard:
        raise HTTPException(status_code=404, detail="Dashboard not found")
    return dashboard


@router.patch("/{dashboard_id}")
async def api_update_dashboard(dashboard_id: str, request: UpdateDashboardRequest):
    """Update dashboard metadata."""
    success = update_dashboard(dashboard_id, request.model_dump(exclude_unset=True))
    if not success:
        raise HTTPException(status_code=500, detail="Failed to update dashboard")
    return {"message": "Dashboard updated"}


@router.delete("/{dashboard_id}")
async def api_delete_dashboard(dashboard_id: str):
    """Delete a dashboard."""
    success = delete_dashboard(dashboard_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete dashboard")
    return {"message": "Dashboard deleted"}


# ── Widget Endpoints ────────────────────────────────────


@router.post("/{dashboard_id}/widgets", status_code=201)
async def api_add_widget(dashboard_id: str, request: AddWidgetRequest):
    """Add a widget to a dashboard."""
    # Verify dashboard exists
    dashboard = get_dashboard(dashboard_id)
    if not dashboard:
        raise HTTPException(status_code=404, detail="Dashboard not found")

    valid_types = {WidgetType.STAT_CARD, WidgetType.TIME_SERIES, WidgetType.MODEL_TABLE,
                   WidgetType.ERROR_TABLE, WidgetType.TOP_TRACES, WidgetType.SPAN_TYPE_PIE,
                   WidgetType.COST_BREAKDOWN, WidgetType.LATENCY_CHART, WidgetType.CUSTOM_QUERY}
    if request.widget_type not in valid_types:
        raise HTTPException(status_code=422, detail=f"Invalid widget type. Must be one of: {', '.join(valid_types)}")

    return add_widget(
        dashboard_id=dashboard_id,
        widget_type=request.widget_type,
        title=request.title,
        config=request.config,
        position_x=request.position_x,
        position_y=request.position_y,
        width=request.width,
        height=request.height,
    )


@router.patch("/{dashboard_id}/widgets/{widget_id}")
async def api_update_widget(dashboard_id: str, widget_id: str, request: UpdateWidgetRequest):
    """Update a widget."""
    success = update_widget(widget_id, request.model_dump(exclude_unset=True))
    if not success:
        raise HTTPException(status_code=500, detail="Failed to update widget")
    return {"message": "Widget updated"}


@router.delete("/{dashboard_id}/widgets/{widget_id}")
async def api_delete_widget(dashboard_id: str, widget_id: str):
    """Delete a widget."""
    success = delete_widget(widget_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete widget")
    return {"message": "Widget deleted"}


@router.put("/{dashboard_id}/widgets/batch")
async def api_batch_update_widgets(dashboard_id: str, request: BatchWidgetUpdateRequest):
    """Batch update widget positions (for drag-and-drop layout changes)."""
    dashboard = get_dashboard(dashboard_id)
    if not dashboard:
        raise HTTPException(status_code=404, detail="Dashboard not found")

    for widget_data in request.widgets:
        widget_id = widget_data.get("widget_id")
        if not widget_id:
            continue
        update_data = {k: v for k, v in widget_data.items() if k != "widget_id"}
        update_widget(widget_id, update_data)

    return get_dashboard(dashboard_id)


@router.get("/widget-types")
async def api_get_widget_types():
    """Get available widget types and their default configs."""
    from ..services.dashboards import WIDGET_DEFAULTS
    return {
        "widget_types": [
            {"type": wt, "default_config": cfg}
            for wt, cfg in WIDGET_DEFAULTS.items()
        ]
    }
