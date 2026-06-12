"""API endpoints for RBAC with team/organization support."""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..api.auth_routes import get_current_user, require_admin
from ..services.rbac import (
    Role,
    Permission,
    create_organization,
    get_organization,
    list_organizations,
    update_organization,
    delete_organization,
    create_team,
    get_team,
    list_teams,
    update_team,
    delete_team,
    add_org_member,
    remove_org_member,
    update_org_member_role,
    list_org_members,
    add_team_member,
    remove_team_member,
    update_team_member_role,
    list_team_members,
    get_user_permissions,
    check_permission,
    get_user_teams,
    get_user_orgs,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/rbac", tags=["rbac"])


# ── Request Models ───────────────────────────────────────


class CreateOrganizationRequest(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    slug: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9][a-z0-9\-]*[a-z0-9]$")
    description: str = ""


class UpdateOrganizationRequest(BaseModel):
    name: Optional[str] = None
    slug: Optional[str] = None
    description: Optional[str] = None


class CreateTeamRequest(BaseModel):
    org_id: str
    name: str = Field(min_length=1, max_length=128)
    slug: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9][a-z0-9\-]*[a-z0-9]$")
    description: str = ""


class UpdateTeamRequest(BaseModel):
    name: Optional[str] = None
    slug: Optional[str] = None
    description: Optional[str] = None


class AddMemberRequest(BaseModel):
    user_id: str
    role: str = "viewer"


class UpdateMemberRoleRequest(BaseModel):
    role: str


class CheckPermissionRequest(BaseModel):
    permission: str
    org_id: Optional[str] = None
    team_id: Optional[str] = None


# ── Organization Endpoints ──────────────────────────────


@router.post("/organizations", status_code=201)
async def api_create_organization(
    request: CreateOrganizationRequest,
    current_user: dict = Depends(get_current_user),
):
    """Create a new organization. Creator is auto-added as owner."""
    try:
        org = create_organization(
            name=request.name,
            slug=request.slug,
            description=request.description,
            owner_user_id=current_user["user_id"],
        )
        return org
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.get("/organizations")
async def api_list_organizations(
    current_user: dict = Depends(get_current_user),
):
    """List organizations the current user belongs to."""
    orgs = list_organizations(user_id=current_user["user_id"])
    return {"organizations": orgs}


@router.get("/organizations/{org_id}")
async def api_get_organization(
    org_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Get organization details."""
    org = get_organization(org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return org


@router.patch("/organizations/{org_id}")
async def api_update_organization(
    org_id: str,
    request: UpdateOrganizationRequest,
    current_user: dict = Depends(get_current_user),
):
    """Update an organization. Requires org owner or admin role."""
    # Check permission
    if not check_permission(current_user["user_id"], Permission.ORG_MANAGE, org_id=org_id):
        raise HTTPException(status_code=403, detail="Insufficient permissions to manage this organization")
    success = update_organization(org_id, request.model_dump(exclude_unset=True))
    if not success:
        raise HTTPException(status_code=500, detail="Failed to update organization")
    return {"message": "Organization updated"}


@router.delete("/organizations/{org_id}")
async def api_delete_organization(
    org_id: str,
    current_user: dict = Depends(require_admin),
):
    """Delete an organization. Requires system admin."""
    success = delete_organization(org_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete organization")
    return {"message": "Organization deleted"}


# ── Organization Members ────────────────────────────────


@router.get("/organizations/{org_id}/members")
async def api_list_org_members(
    org_id: str,
    current_user: dict = Depends(get_current_user),
):
    """List members of an organization."""
    members = list_org_members(org_id)
    return {"members": members}


@router.post("/organizations/{org_id}/members", status_code=201)
async def api_add_org_member(
    org_id: str,
    request: AddMemberRequest,
    current_user: dict = Depends(get_current_user),
):
    """Add a member to an organization."""
    if not check_permission(current_user["user_id"], Permission.ORG_MANAGE, org_id=org_id):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    try:
        member = add_org_member(org_id, request.user_id, request.role)
        return member
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.patch("/organizations/{org_id}/members/{user_id}")
async def api_update_org_member(
    org_id: str,
    user_id: str,
    request: UpdateMemberRoleRequest,
    current_user: dict = Depends(get_current_user),
):
    """Update a member's role in an organization."""
    if not check_permission(current_user["user_id"], Permission.ORG_MANAGE, org_id=org_id):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    try:
        success = update_org_member_role(org_id, user_id, request.role)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    if not success:
        raise HTTPException(status_code=404, detail="Member not found")
    return {"message": "Member role updated"}


@router.delete("/organizations/{org_id}/members/{user_id}")
async def api_remove_org_member(
    org_id: str,
    user_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Remove a member from an organization."""
    if not check_permission(current_user["user_id"], Permission.ORG_MANAGE, org_id=org_id):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    success = remove_org_member(org_id, user_id)
    if not success:
        raise HTTPException(status_code=404, detail="Member not found")
    return {"message": "Member removed"}


# ── Team Endpoints ──────────────────────────────────────


@router.post("/teams", status_code=201)
async def api_create_team(
    request: CreateTeamRequest,
    current_user: dict = Depends(get_current_user),
):
    """Create a new team. Creator is auto-added as team owner."""
    # Verify user is member of the org
    if not check_permission(current_user["user_id"], Permission.ORG_READ, org_id=request.org_id):
        raise HTTPException(status_code=403, detail="Must be an org member to create teams")
    try:
        team = create_team(
            org_id=request.org_id,
            name=request.name,
            slug=request.slug,
            description=request.description,
            creator_user_id=current_user["user_id"],
        )
        return team
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.get("/teams")
async def api_list_teams(
    org_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    """List teams. Optionally filter by org or user membership."""
    if org_id:
        teams = list_teams(org_id=org_id)
    else:
        teams = list_teams(user_id=current_user["user_id"])
    return {"teams": teams}


@router.get("/teams/{team_id}")
async def api_get_team(
    team_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Get team details."""
    team = get_team(team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    return team


@router.patch("/teams/{team_id}")
async def api_update_team(
    team_id: str,
    request: UpdateTeamRequest,
    current_user: dict = Depends(get_current_user),
):
    """Update a team. Requires team admin role."""
    if not check_permission(current_user["user_id"], Permission.TEAM_MANAGE, team_id=team_id):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    success = update_team(team_id, request.model_dump(exclude_unset=True))
    if not success:
        raise HTTPException(status_code=500, detail="Failed to update team")
    return {"message": "Team updated"}


@router.delete("/teams/{team_id}")
async def api_delete_team(
    team_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Delete a team. Requires team owner or org admin."""
    team = get_team(team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    if not check_permission(
        current_user["user_id"], Permission.TEAM_MANAGE,
        org_id=team.get("org_id"), team_id=team_id,
    ):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    success = delete_team(team_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete team")
    return {"message": "Team deleted"}


# ── Team Members ────────────────────────────────────────


@router.get("/teams/{team_id}/members")
async def api_list_team_members(
    team_id: str,
    current_user: dict = Depends(get_current_user),
):
    """List members of a team."""
    members = list_team_members(team_id)
    return {"members": members}


@router.post("/teams/{team_id}/members", status_code=201)
async def api_add_team_member(
    team_id: str,
    request: AddMemberRequest,
    current_user: dict = Depends(get_current_user),
):
    """Add a member to a team."""
    if not check_permission(current_user["user_id"], Permission.TEAM_MANAGE, team_id=team_id):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    try:
        member = add_team_member(team_id, request.user_id, request.role)
        return member
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.patch("/teams/{team_id}/members/{user_id}")
async def api_update_team_member(
    team_id: str,
    user_id: str,
    request: UpdateMemberRoleRequest,
    current_user: dict = Depends(get_current_user),
):
    """Update a member's role in a team."""
    if not check_permission(current_user["user_id"], Permission.TEAM_MANAGE, team_id=team_id):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    try:
        success = update_team_member_role(team_id, user_id, request.role)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    if not success:
        raise HTTPException(status_code=404, detail="Member not found")
    return {"message": "Member role updated"}


@router.delete("/teams/{team_id}/members/{user_id}")
async def api_remove_team_member(
    team_id: str,
    user_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Remove a member from a team."""
    if not check_permission(current_user["user_id"], Permission.TEAM_MANAGE, team_id=team_id):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    success = remove_team_member(team_id, user_id)
    if not success:
        raise HTTPException(status_code=404, detail="Member not found")
    return {"message": "Member removed"}


# ── Permission Endpoints ────────────────────────────────


@router.get("/permissions")
async def api_get_permissions():
    """Get all available permissions and role definitions."""
    return {
        "roles": {
            role: {
                "permissions": perms if perms != "all" else "all",
                "description": desc,
            }
            for role, perms, desc in [
                (Role.OWNER, Role.PERMISSIONS[Role.OWNER], "Full access to all resources"),
                (Role.ADMIN, Role.PERMISSIONS[Role.ADMIN], "Manage all resources except org settings"),
                (Role.EDITOR, Role.PERMISSIONS[Role.EDITOR], "Create and edit resources, no delete or manage"),
                (Role.VIEWER, Role.PERMISSIONS[Role.VIEWER], "Read-only access to resources"),
            ]
        },
        "permissions": [
            {"key": v, "category": v.split(":")[0], "action": v.split(":")[1]}
            for k, v in vars(Permission).items()
            if isinstance(v, str) and ":" in v
        ],
    }


@router.get("/users/me/permissions")
async def api_get_my_permissions(
    org_id: Optional[str] = None,
    team_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    """Get the current user's effective permissions in a given context."""
    perms = get_user_permissions(current_user["user_id"], org_id=org_id, team_id=team_id)
    return perms


@router.post("/users/me/check-permission")
async def api_check_permission(
    request: CheckPermissionRequest,
    current_user: dict = Depends(get_current_user),
):
    """Check if the current user has a specific permission."""
    allowed = check_permission(
        current_user["user_id"],
        request.permission,
        org_id=request.org_id,
        team_id=request.team_id,
    )
    return {"permission": request.permission, "allowed": allowed}


@router.get("/users/me/teams")
async def api_get_my_teams(
    current_user: dict = Depends(get_current_user),
):
    """Get all teams the current user belongs to."""
    teams = get_user_teams(current_user["user_id"])
    return {"teams": teams}


@router.get("/users/me/orgs")
async def api_get_my_orgs(
    current_user: dict = Depends(get_current_user),
):
    """Get all organizations the current user belongs to."""
    orgs = get_user_orgs(current_user["user_id"])
    return {"organizations": orgs}
