"""API endpoints for data retention policies and auto-cleanup."""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..api.auth_routes import get_current_user, require_admin
from ..services.rbac import Permission, check_permission
from ..services.retention import (
    RetentionType,
    RetentionEngine,
    create_retention_policy,
    get_retention_policy,
    list_retention_policies,
    update_retention_policy,
    delete_retention_policy,
    list_retention_runs,
    get_retention_engine,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/retention", tags=["retention"])


# ── Request Models ───────────────────────────────────────


class CreateRetentionPolicyRequest(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    retention_type: str
    enabled: bool = True
    params: Optional[Dict[str, Any]] = None
    scope: str = "all"


class UpdateRetentionPolicyRequest(BaseModel):
    name: Optional[str] = None
    retention_type: Optional[str] = None
    enabled: Optional[bool] = None
    params: Optional[Dict[str, Any]] = None
    scope: Optional[str] = None


# ── Policy CRUD Endpoints ──────────────────────────────


@router.post("/policies", status_code=201)
async def api_create_policy(
    request: CreateRetentionPolicyRequest,
    current_user: dict = Depends(get_current_user),
):
    """Create a new retention policy."""
    valid_types = {RetentionType.AGE, RetentionType.COUNT, RetentionType.SIZE}
    if request.retention_type not in valid_types:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid retention type. Must be one of: {', '.join(valid_types)}",
        )

    valid_scopes = {"all", "traces", "spans", "evaluations", "alerts", "dashboards"}
    if request.scope not in valid_scopes:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid scope. Must be one of: {', '.join(valid_scopes)}",
        )

    return create_retention_policy(
        name=request.name,
        retention_type=request.retention_type,
        enabled=request.enabled,
        params=request.params,
        scope=request.scope,
    )


@router.get("/policies")
async def api_list_policies(
    enabled_only: bool = False,
    current_user: dict = Depends(get_current_user),
):
    """List all retention policies."""
    policies = list_retention_policies(enabled_only=enabled_only)
    return {"policies": policies}


@router.get("/policies/{policy_id}")
async def api_get_policy(
    policy_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Get a retention policy by ID."""
    policy = get_retention_policy(policy_id)
    if not policy:
        raise HTTPException(status_code=404, detail="Retention policy not found")
    return policy


@router.patch("/policies/{policy_id}")
async def api_update_policy(
    policy_id: str,
    request: UpdateRetentionPolicyRequest,
    current_user: dict = Depends(get_current_user),
):
    """Update a retention policy."""
    success = update_retention_policy(policy_id, request.model_dump(exclude_unset=True))
    if not success:
        raise HTTPException(status_code=500, detail="Failed to update retention policy")
    return {"message": "Retention policy updated"}


@router.delete("/policies/{policy_id}")
async def api_delete_policy(
    policy_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Delete a retention policy."""
    success = delete_retention_policy(policy_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete retention policy")
    return {"message": "Retention policy deleted"}


# ── Execution Endpoints ────────────────────────────────


@router.post("/policies/{policy_id}/run")
async def api_run_policy(
    policy_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Execute a single retention policy immediately."""
    policy = get_retention_policy(policy_id)
    if not policy:
        raise HTTPException(status_code=404, detail="Retention policy not found")

    engine = get_retention_engine()
    result = engine.run_policy(policy)
    return result


@router.post("/run-all")
async def api_run_all_policies(
    current_user: dict = Depends(get_current_user),
):
    """Execute all enabled retention policies."""
    engine = get_retention_engine()
    results = engine.run_all_enabled()
    return {"results": results}


@router.get("/runs")
async def api_list_runs(
    policy_id: Optional[str] = None,
    limit: int = 20,
    current_user: dict = Depends(get_current_user),
):
    """List retention policy execution history."""
    runs = list_retention_runs(policy_id=policy_id, limit=limit)
    return {"runs": runs}


# ── Database Stats Endpoint ────────────────────────────


@router.get("/stats")
async def api_get_db_stats(
    current_user: dict = Depends(get_current_user),
):
    """Get database size and record counts."""
    engine = get_retention_engine()
    return engine.get_db_stats()


# ── Retention Types Info ───────────────────────────────


@router.get("/types")
async def api_get_retention_types():
    """Get available retention types and their parameters."""
    return {
        "types": [
            {
                "type": RetentionType.AGE,
                "description": "Delete data older than a specified number of days",
                "params": [
                    {"name": "max_age_days", "type": "int", "description": "Maximum age in days", "default": 30},
                ],
            },
            {
                "type": RetentionType.COUNT,
                "description": "Keep at most N traces, deleting the oldest",
                "params": [
                    {"name": "max_count", "type": "int", "description": "Maximum number of traces to keep", "default": 10000},
                ],
            },
            {
                "type": RetentionType.SIZE,
                "description": "Keep database under a specified size in MB",
                "params": [
                    {"name": "max_size_mb", "type": "float", "description": "Maximum database size in MB", "default": 100},
                ],
            },
        ],
        "scopes": [
            {"scope": "all", "description": "Apply to all data types"},
            {"scope": "traces", "description": "Apply only to traces and spans"},
            {"scope": "evaluations", "description": "Apply only to evaluation data"},
            {"scope": "alerts", "description": "Apply only to alert events"},
            {"scope": "dashboards", "description": "Apply only to dashboards"},
        ],
    }
