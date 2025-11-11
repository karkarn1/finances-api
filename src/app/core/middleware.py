"""Logging and monitoring middleware for HTTP requests and responses."""

import logging
import time
from collections.abc import Callable

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for logging HTTP requests and responses with timing metrics.

    Automatically logs:
    - Incoming requests with method, path, and client information
    - Response status codes and processing time
    - Adds X-Process-Time header for observability

    Skips logging for:
    - Health check endpoints (/health)
    - API documentation endpoints (/docs, /openapi.json, /redoc)
    """

    def __init__(self, app: ASGIApp) -> None:
        """Initialize the middleware.

        Args:
            app: The ASGI application instance
        """
        super().__init__(app)
        self._quiet_paths = {"/health", "/docs", "/openapi.json", "/redoc"}

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process the request and log details about it.

        Measures request processing time and logs both incoming request
        and outgoing response with timing information.

        Args:
            request: The incoming HTTP request
            call_next: The next middleware/route handler in the chain

        Returns:
            The HTTP response with timing header added
        """
        # Skip logging for quiet paths to reduce noise
        if request.url.path in self._quiet_paths:
            return await call_next(request)

        # Get client information
        client_host = request.client.host if request.client else "unknown"

        # Log incoming request
        logger.info(f"→ {request.method} {request.url.path} from {client_host}")

        # Record start time for duration calculation
        start_time = time.time()

        # Process the request through the next middleware/route handler
        response = await call_next(request)

        # Calculate processing duration
        duration = time.time() - start_time

        # Determine appropriate log level based on status code
        log_level = logging.WARNING if response.status_code >= 400 else logging.INFO

        # Log response with timing
        logger.log(
            log_level,
            f"← {request.method} {request.url.path} - {response.status_code} ({duration:.3f}s)",
        )

        # Add timing header for observability
        response.headers["X-Process-Time"] = f"{duration:.3f}"

        return response
