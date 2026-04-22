"""
HTTP middleware: performance telemetry and request tracing.
"""

import time
import uuid
import logging
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class PerformanceLoggingMiddleware(BaseHTTPMiddleware):
    """Adds X-Process-Time-Ms to every response using perf_counter for sub-millisecond accuracy."""

    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        logger.info("%s %s", request.method, request.url.path)
        try:
            response = await call_next(request)
            elapsed_ms = (time.perf_counter() - start) * 1000
            response.headers["X-Process-Time-Ms"] = f"{elapsed_ms:.2f}"
            logger.info("%s %s -> %s (%.2fms)",
                        request.method, request.url.path, response.status_code, elapsed_ms)
            return response
        except Exception as e:
            elapsed_ms = (time.perf_counter() - start) * 1000
            logger.error("%s %s -> ERROR: %s (%.2fms)",
                         request.method, request.url.path, e, elapsed_ms)
            raise


class RequestValidationMiddleware(BaseHTTPMiddleware):
    """Attaches a unique request ID to every response for distributed tracing."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Request-ID"] = str(uuid.uuid4())
        return response
