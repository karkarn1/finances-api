# Request/Response Logging Middleware

## Overview

The application includes a centralized request/response logging middleware that provides:

- **Request Logging**: Logs all incoming HTTP requests with method, path, and client IP
- **Response Logging**: Logs responses with status code and processing time
- **Timing Metrics**: Adds `X-Process-Time` header with request duration
- **Noise Reduction**: Automatically skips logging for health checks and API documentation endpoints
- **Structured Output**: Timestamps and log levels for debugging and monitoring

## Architecture

### Components

#### 1. RequestLoggingMiddleware (`src/app/core/middleware.py`)

A Starlette `BaseHTTPMiddleware` that:
- Intercepts all HTTP requests before routing
- Records request start time
- Passes request to route handler
- Calculates processing duration
- Logs response with timing information
- Adds timing header to response

**Key Features:**
- Measures actual request processing time
- Uses directional arrows for visual clarity (→ for requests, ← for responses)
- Logs errors at WARNING level for visibility
- Skips quiet paths to reduce log noise

#### 2. Logging Configuration (`src/app/core/config.py`)

Centralized logging configuration with:
- Python's `logging.config.dictConfig` format
- Console output with timestamps
- ISO 8601 date format (`YYYY-MM-DD HH:MM:SS`)
- Configurable log levels

#### 3. Logging Setup (`src/main.py`)

Application startup code that:
- Imports logging configuration from settings
- Applies configuration via `logging.config.dictConfig()`
- Registers middleware after CORS setup
- Creates logger instance for application startup messages

## Log Format

### Request Log
```
2025-11-10 14:35:22 - app.core.middleware - INFO - → GET /api/v1/users/me from 127.0.0.1
```

### Response Log (Success)
```
2025-11-10 14:35:22 - app.core.middleware - INFO - ← GET /api/v1/users/me - 200 (0.045s)
```

### Response Log (Error)
```
2025-11-10 14:35:23 - app.core.middleware - WARNING - ← GET /api/v1/invalid - 404 (0.001s)
```

## Usage

### Basic Usage

The middleware is automatically enabled on application startup. No configuration is needed.

To use logging in your own code:

```python
import logging

logger = logging.getLogger(__name__)

@router.get("/example")
async def example_endpoint() -> dict:
    """Example endpoint with logging."""
    logger.info("Processing example request")
    # Implementation
    logger.info("Example request completed successfully")
    return {"status": "success"}
```

### Log Levels

- **INFO**: Normal request/response flow
- **WARNING**: Error responses (4xx, 5xx status codes)
- **DEBUG**: (Available but not enabled by default)

To enable DEBUG logging:

Edit `src/app/core/config.py`:
```python
LOGGING_CONFIG: dict = {
    # ...
    "root": {
        "level": "DEBUG",  # Changed from INFO
        "handlers": ["console"],
    },
}
```

## Quiet Paths (No Logging)

The middleware automatically skips logging for:

- `/health` - Health check endpoint
- `/docs` - Swagger UI documentation
- `/openapi.json` - OpenAPI schema
- `/redoc` - ReDoc documentation

This prevents log noise from automated monitoring and documentation tools.

To modify quiet paths, edit the middleware initialization in `src/app/core/middleware.py`:

```python
def __init__(self, app: ASGIApp) -> None:
    super().__init__(app)
    self._quiet_paths = {"/health", "/docs", "/openapi.json", "/redoc", "/your-new-path"}
```

## Response Headers

The middleware adds a timing header to all responses:

```
X-Process-Time: 0.045
```

This header contains the request processing time in seconds with millisecond precision.

### Using the Timing Header

Frontend or monitoring systems can use this header for:
- Client-side performance monitoring
- SLA validation
- Performance trending

Example (JavaScript/Fetch):
```javascript
fetch('/api/v1/example')
  .then(response => {
    const timing = response.headers.get('X-Process-Time');
    console.log(`Request took ${timing}s`);
  });
```

## Performance Considerations

### Overhead

The middleware adds minimal overhead:
- Uses efficient `time.time()` for timing (system call only)
- No string parsing or complex processing
- Skips quiet paths entirely
- No blocking operations

### Typical Impact

- Request latency increase: < 1ms
- Logging I/O: Asynchronous (non-blocking)
- Memory usage: Minimal (no request buffering)

## Monitoring and Debugging

### Viewing Logs

**In Docker:**
```bash
make logs-app      # View API logs
make logs          # View all service logs
```

**Local Development:**
```bash
# Logs appear in console automatically
cd finances-api && python -m uvicorn src.main:app --reload
```

### Filtering Logs

**By Status Code:**
```bash
make logs-app | grep " 5[0-9][0-9] "  # 5xx errors
make logs-app | grep " 4[0-9][0-9] "  # 4xx errors
```

**By Endpoint:**
```bash
make logs-app | grep "/api/v1/securities"  # Securities endpoints
make logs-app | grep "/api/v1/auth"        # Auth endpoints
```

**By Client IP:**
```bash
make logs-app | grep "from 192.168.1.1"  # Specific IP
```

### Timing Analysis

Extract request timings for performance analysis:

```bash
# Extract all response timings
make logs-app | grep "←" | sed -E 's/.*\((.*s)\).*/\1/'

# Find slow requests (> 500ms)
make logs-app | grep "←" | awk -F'(' '{print $2}' | awk '{print $1}' | \
  awk '$1 > 0.5 {print $0}'
```

## Testing

Tests are provided in `tests/api/routes/test_middleware.py`:

```bash
# Run middleware tests
make test tests/api/routes/test_middleware.py

# Run with verbose output
make test tests/api/routes/test_middleware.py -v
```

### Test Coverage

- Timing header is added to responses
- Health endpoint is not logged
- API endpoints are logged with request and response
- Error responses are logged at WARNING level
- Documentation endpoints are not logged

## Customization

### Changing Log Format

Edit `src/app/core/config.py` logging configuration:

```python
"formatters": {
    "default": {
        "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        "datefmt": "%Y-%m-%d %H:%M:%S",
    },
},
```

Available format variables:
- `%(asctime)s` - Date and time
- `%(name)s` - Logger name
- `%(levelname)s` - Log level (INFO, WARNING, etc.)
- `%(message)s` - Log message
- `%(pathname)s` - File path
- `%(lineno)d` - Line number

### Adding Additional Handlers

To add file logging, extend the configuration:

```python
"handlers": {
    "console": {
        "class": "logging.StreamHandler",
        "formatter": "default",
        "stream": "ext://sys.stdout",
    },
    "file": {
        "class": "logging.handlers.RotatingFileHandler",
        "filename": "logs/app.log",
        "maxBytes": 10485760,  # 10MB
        "backupCount": 5,
        "formatter": "default",
    },
},
"root": {
    "level": "INFO",
    "handlers": ["console", "file"],  # Add "file" here
},
```

### Changing Log Levels by Module

To enable DEBUG logging only for specific modules:

```python
"loggers": {
    "app": {
        "level": "INFO",
        "handlers": ["console"],
        "propagate": False,
    },
    "app.api.routes": {
        "level": "DEBUG",  # More verbose for routes
        "handlers": ["console"],
        "propagate": False,
    },
},
```

## Troubleshooting

### Logs Not Appearing

1. **Check middleware registration:**
   - Verify `app.add_middleware(RequestLoggingMiddleware)` in `src/main.py`

2. **Check logging configuration:**
   - Verify `logging.config.dictConfig(settings.LOGGING_CONFIG)` is called before middleware setup

3. **Check log level:**
   - Ensure `"level": "INFO"` in LOGGING_CONFIG (or DEBUG for more verbose output)

### Missing Timing Headers

The timing header should appear on all responses. If missing:

1. Verify middleware is registered in correct order
2. Check that response object is being returned properly
3. Verify no middleware is removing headers downstream

### Performance Concerns

If middleware adds noticeable latency:

1. Ensure quiet paths are configured (avoids logging for frequent endpoints)
2. Consider disabling logging for high-frequency operations
3. Check if file logging is enabled (can be slow)

## Related Documentation

- [FastAPI Middleware](https://fastapi.tiangolo.com/tutorial/middleware/)
- [Starlette Middleware](https://www.starlette.io/middleware/)
- [Python Logging Configuration](https://docs.python.org/3/library/logging.config.html)
- [Main Application Configuration](./ARCHITECTURE.md)

## Implementation Details

### Middleware Ordering

FastAPI applies middleware in reverse order of registration. Current order:

1. **RequestLoggingMiddleware** (outermost - first to execute)
2. **CORSMiddleware**
3. **Route handlers** (innermost)

This ensures:
- Logging wraps all requests (including CORS-rejected requests)
- CORS configuration applies before business logic
- Timing includes CORS processing

### Async Compatibility

The middleware is fully async-compatible:
- Uses `async def dispatch()` method
- Properly awaits `call_next(request)`
- Doesn't block event loop
- Works with all async route handlers

### Type Safety

The middleware includes full type hints:
```python
async def dispatch(
    self, request: Request, call_next: Callable
) -> Response:
```

This ensures IDE support and type checking compatibility.
