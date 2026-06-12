"""Custom exception classes for structured error responses."""

from typing import Optional


class AppError(Exception):
    """Base application error."""

    def __init__(self, message: str, detail: Optional[str] = None):
        self.message = message
        self.detail = detail
        super().__init__(message)


class NotFoundError(AppError):
    """Resource not found (HTTP 404)."""

    def __init__(self, resource: str, resource_id: str):
        super().__init__(
            message=f"{resource} not found",
            detail=f"{resource} '{resource_id}' does not exist",
        )
        self.resource = resource
        self.resource_id = resource_id


class ValidationError(AppError):
    """Invalid request data (HTTP 422)."""

    def __init__(self, detail: str):
        super().__init__(message="Validation error", detail=detail)


class ConflictError(AppError):
    """Resource already exists (HTTP 409)."""

    def __init__(self, resource: str, resource_id: str):
        super().__init__(
            message=f"{resource} already exists",
            detail=f"{resource} '{resource_id}' already exists",
        )
        self.resource = resource
        self.resource_id = resource_id


class ServiceError(AppError):
    """Internal service failure (HTTP 500)."""

    def __init__(self, message: str, detail: Optional[str] = None):
        super().__init__(message=message, detail=detail)
