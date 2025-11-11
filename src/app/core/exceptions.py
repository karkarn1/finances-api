"""Centralized exception hierarchy and handlers for the application.

This module provides a unified exception system that maps all application errors
to appropriate HTTP status codes and response formats. All services and routes
should raise exceptions from this hierarchy rather than generic exceptions or
HTTPException directly.

Exception Hierarchy:
    AppException (base)
    ├── ValidationError (400)
    ├── AuthenticationError (401)
    ├── NotFoundError (404)
    ├── ConflictError (409)
    └── ExternalAPIError (503)

Usage in Services:
    from app.core.exceptions import ValidationError, ExternalAPIError

    def process_data(value: int) -> str:
        if value < 0:
            raise ValidationError("Value must be non-negative")
        try:
            return external_api_call(value)
        except Exception as e:
            raise ExternalAPIError(f"API call failed: {e}") from e

Usage in Routes:
    from fastapi import APIRouter
    from app.core.exceptions import NotFoundError

    @router.get("/items/{item_id}")
    async def get_item(item_id: int):
        item = await db.get(Item, item_id)
        if not item:
            raise NotFoundError(f"Item {item_id} not found")
        return item

The exception handler automatically converts these to HTTP responses.
"""

import logging
from typing import Any

from fastapi import Request, status
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class AppException(Exception):
    """
    Base exception class for all application errors.

    Provides standard structure for application exceptions that can be
    automatically converted to HTTP responses with appropriate status codes.

    Attributes:
        status_code: HTTP status code for this error type
        detail: User-facing error message
        error_code: Machine-readable error code (optional)
    """

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    detail: str = "Internal server error"
    error_code: str | None = None

    def __init__(
        self,
        detail: str | None = None,
        *,
        error_code: str | None = None,
    ) -> None:
        """
        Initialize the exception.

        Args:
            detail: Custom error message (overrides class default)
            error_code: Machine-readable error identifier
        """
        self.detail = detail or self.__class__.detail
        self.error_code = error_code or self.__class__.error_code
        super().__init__(self.detail)


class ValidationError(AppException):
    """
    Raised when input validation fails.

    Used for invalid request parameters, malformed data, or constraint violations.
    Maps to HTTP 400 Bad Request.
    """

    status_code = status.HTTP_400_BAD_REQUEST
    detail = "Validation error"
    error_code = "VALIDATION_ERROR"


class AuthenticationError(AppException):
    """
    Raised when authentication fails.

    Used for invalid credentials, expired tokens, or missing authentication.
    Maps to HTTP 401 Unauthorized.
    """

    status_code = status.HTTP_401_UNAUTHORIZED
    detail = "Authentication failed"
    error_code = "AUTHENTICATION_ERROR"


class NotFoundError(AppException):
    """
    Raised when a requested resource is not found.

    Used when querying for non-existent resources or entities.
    Maps to HTTP 404 Not Found.
    """

    status_code = status.HTTP_404_NOT_FOUND
    detail = "Resource not found"
    error_code = "NOT_FOUND"


class ConflictError(AppException):
    """
    Raised when there's a conflict in the operation.

    Used for concurrent modifications, duplicate entries, or state conflicts.
    Maps to HTTP 409 Conflict.
    """

    status_code = status.HTTP_409_CONFLICT
    detail = "Resource conflict"
    error_code = "CONFLICT"


class ExternalAPIError(AppException):
    """
    Raised when an external API call fails.

    Used when third-party services (Yahoo Finance, etc.) are unavailable
    or return errors.
    Maps to HTTP 503 Service Unavailable.
    """

    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    detail = "External service unavailable"
    error_code = "EXTERNAL_API_ERROR"


async def app_exception_handler(
    request: Request,
    exc: AppException,
) -> JSONResponse:
    """
    Handle application exceptions and convert to HTTP responses.

    This handler is registered with FastAPI to automatically convert
    AppException instances to properly formatted JSON responses with
    appropriate HTTP status codes.

    Args:
        request: FastAPI request object
        exc: The exception instance

    Returns:
        JSONResponse with error details and HTTP status code

    Response Format:
        {
            "detail": "User-facing error message",
            "error_code": "MACHINE_READABLE_CODE"  # optional
        }

    Logging:
        - Errors (500): Full stack trace
        - Client errors (4xx): Message only
        - Service errors (5xx): Full stack trace with context
    """
    # Log the error appropriately based on status code
    if exc.status_code >= 500:
        # Server errors: log full context for debugging
        logger.error(
            f"{exc.__class__.__name__}: {exc.detail}",
            exc_info=True,
            extra={
                "status_code": exc.status_code,
                "error_code": exc.error_code,
                "request_path": request.url.path,
            },
        )
    else:
        # Client errors: log without full stack trace
        logger.warning(
            f"{exc.__class__.__name__}: {exc.detail}",
            extra={
                "status_code": exc.status_code,
                "error_code": exc.error_code,
                "request_path": request.url.path,
            },
        )

    # Build response body
    response_body: dict[str, Any] = {"detail": exc.detail}
    if exc.error_code:
        response_body["error_code"] = exc.error_code

    return JSONResponse(
        status_code=exc.status_code,
        content=response_body,
    )
