"""API endpoints for authentication and user management."""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Header, Request
from pydantic import BaseModel, Field

from .. import auth

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])


# ── Request/Response Models ──────────────────────────────


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=6, max_length=128)
    email: Optional[str] = None
    display_name: Optional[str] = None


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    token: str
    user_id: str
    username: str
    role: str
    display_name: Optional[str] = None
    email: Optional[str] = None


class UserResponse(BaseModel):
    user_id: str
    username: str
    email: Optional[str] = None
    display_name: Optional[str] = None
    role: str


class ApiKeyRequest(BaseModel):
    name: str = Field(min_length=1, max_length=64)


class ApiKeyResponse(BaseModel):
    key_id: str
    key: str
    key_prefix: str
    name: str


class ApiKeyInfo(BaseModel):
    key_id: str
    key_prefix: str
    name: str
    created_at: Optional[str] = None
    last_used: Optional[str] = None


# ── Auth Dependency ──────────────────────────────────────


async def get_current_user(
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
) -> dict:
    """FastAPI dependency to extract and verify the current user.

    Supports two auth methods:
    1. Bearer token: Authorization: Bearer <jwt>
    2. API key: X-API-Key: <key>
    """
    # Try Bearer token first
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:]
        payload = auth.verify_token(token)
        if payload is None:
            raise HTTPException(status_code=401, detail="Invalid or expired token")
        user = auth.get_user_by_id(payload["sub"])
        if user is None:
            raise HTTPException(status_code=401, detail="User not found")
        return user

    # Try API key
    if x_api_key:
        key_info = auth.verify_api_key(x_api_key)
        if key_info is None:
            raise HTTPException(status_code=401, detail="Invalid API key")
        user = auth.get_user_by_id(key_info["user_id"])
        if user is None:
            raise HTTPException(status_code=401, detail="User not found")
        return user

    raise HTTPException(status_code=401, detail="Authentication required")


async def require_admin(current_user: dict = Depends(get_current_user)) -> dict:
    """FastAPI dependency that requires admin role."""
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


# ── Auth Endpoints ───────────────────────────────────────


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(req: RegisterRequest):
    """Register a new user account."""
    try:
        user = auth.register_user(
            username=req.username,
            password=req.password,
            email=req.email,
            display_name=req.display_name,
        )
        # Auto-login after registration
        result = auth.authenticate_user(req.username, req.password)
        if result is None:
            raise HTTPException(status_code=500, detail="Registration succeeded but auto-login failed")
        return TokenResponse(
            token=result["token"],
            user_id=result["user_id"],
            username=result["username"],
            role=result["role"],
            display_name=result.get("display_name"),
            email=result.get("email"),
        )
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest):
    """Login with username and password."""
    result = auth.authenticate_user(req.username, req.password)
    if result is None:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    return TokenResponse(
        token=result["token"],
        user_id=result["user_id"],
        username=result["username"],
        role=result["role"],
        display_name=result.get("display_name"),
        email=result.get("email"),
    )


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: dict = Depends(get_current_user)):
    """Get the current authenticated user's profile."""
    return UserResponse(**current_user)


@router.get("/users", response_model=list)
async def list_users(
    limit: int = 50,
    offset: int = 0,
    current_user: dict = Depends(require_admin),
):
    """List all users (admin only)."""
    return auth.list_users(limit=limit, offset=offset)


# ── API Key Endpoints ────────────────────────────────────


@router.post("/api-keys", response_model=ApiKeyResponse, status_code=201)
async def create_api_key(
    req: ApiKeyRequest,
    current_user: dict = Depends(get_current_user),
):
    """Create a new API key for the current user."""
    result = auth.create_api_key(current_user["user_id"], req.name)
    return ApiKeyResponse(**result)


@router.get("/api-keys", response_model=list)
async def list_api_keys(current_user: dict = Depends(get_current_user)):
    """List API keys for the current user."""
    return auth.list_api_keys(current_user["user_id"])


@router.delete("/api-keys/{key_id}")
async def delete_api_key(
    key_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Delete an API key."""
    success = auth.delete_api_key(current_user["user_id"], key_id)
    if not success:
        raise HTTPException(status_code=404, detail="API key not found")
    return {"message": "API key deleted"}


# ── Token Refresh ────────────────────────────────────────


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(current_user: dict = Depends(get_current_user)):
    """Refresh the current JWT token."""
    token = auth.create_token(
        current_user["user_id"],
        extra={"username": current_user["username"], "role": current_user["role"]},
    )
    return TokenResponse(
        token=token,
        user_id=current_user["user_id"],
        username=current_user["username"],
        role=current_user["role"],
        display_name=current_user.get("display_name"),
        email=current_user.get("email"),
    )
