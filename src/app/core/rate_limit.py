"""Rate limiting configuration using slowapi."""

import re

from fastapi import Request
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.responses import JSONResponse

from app.core.config import settings


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """
    Custom exception handler for rate limit exceeded errors.

    Provides a consistent response format with proper retry_after information
    and X-RateLimit-* headers.

    Args:
        request: The incoming request
        exc: The RateLimitExceeded exception

    Returns:
        JSONResponse with error details, retry_after, and rate limit headers
    """
    # Extract retry_after from the exception message
    # slowapi detail format: "X per Y {time_unit}" (e.g., "5 per 1 minute")
    retry_after = 60  # Default to 60 seconds

    # Try to extract the time value from the error message
    match = re.search(r"(\d+)\s+per\s+(\d+)\s+(\w+)", str(exc.detail))
    if match:
        time_value = int(match.group(2))
        time_unit = match.group(3)

        # Convert to seconds
        if time_unit.startswith("second"):
            retry_after = time_value
        elif time_unit.startswith("minute"):
            retry_after = time_value * 60
        elif time_unit.startswith("hour"):
            retry_after = time_value * 3600
        elif time_unit.startswith("day"):
            retry_after = time_value * 86400
    else:
        # Fallback: try to extract just the number
        match = re.search(r"(\d+)", str(exc.detail))
        if match:
            retry_after = int(match.group(1)) * 60  # Assume minutes

    # Create JSON response with consistent format
    response = JSONResponse(
        status_code=429,
        content={
            "detail": f"Rate limit exceeded: {exc.detail}",
            "retry_after": retry_after,
        },
    )

    # Add Retry-After header
    response.headers["Retry-After"] = str(retry_after)

    # Inject X-RateLimit-* headers manually to avoid issues with _inject_headers
    # The SlowAPIMiddleware will already add these headers to successful responses,
    # but we need to add them to 429 responses as well
    if hasattr(request.state, "view_rate_limit") and request.state.view_rate_limit:
        rate_limit_item = request.state.view_rate_limit[0]

        try:
            # Get window stats from limiter to calculate remaining and reset
            window_stats = request.app.state.limiter.limiter.get_window_stats(
                rate_limit_item, *request.state.view_rate_limit[1]
            )
            reset_in = 1 + window_stats[0]

            # Add X-RateLimit headers
            response.headers["X-RateLimit-Limit"] = str(rate_limit_item.amount)
            response.headers["X-RateLimit-Remaining"] = str(window_stats[1])
            response.headers["X-RateLimit-Reset"] = str(int(reset_in))
        except Exception:
            # If we can't get window stats, skip adding the headers
            # This can happen in some edge cases during testing
            pass

    return response


# Create limiter instance
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[],  # No default limits - each endpoint sets its own limit
    enabled=settings.RATE_LIMIT_ENABLED,
    headers_enabled=False,  # Disabled due to compatibility issues with FastAPI response models
)
