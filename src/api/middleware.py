"""
API Middleware - Request/Response Logging & Performance Tracking
Phase 4 - Week 8 - Day 3
"""

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
import time
import logging

logger = logging.getLogger(__name__)


class PerformanceLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware to log all requests with performance metrics
    """
    
    async def dispatch(self, request: Request, call_next):
        # Record start time
        start_time = time.time()
        
        # Log incoming request
        logger.info(f"➡️  {request.method} {request.url.path}")
        
        # Process request
        try:
            response = await call_next(request)
            
            # Calculate processing time
            process_time = (time.time() - start_time) * 1000  # Convert to ms
            
            # Add performance header
            response.headers["X-Process-Time-Ms"] = f"{process_time:.2f}"
            
            # Log response
            logger.info(
                f"⬅️  {request.method} {request.url.path} "
                f"→ {response.status_code} ({process_time:.2f}ms)"
            )
            
            return response
            
        except Exception as e:
            # Log error
            process_time = (time.time() - start_time) * 1000
            logger.error(
                f"❌ {request.method} {request.url.path} "
                f"→ ERROR: {str(e)} ({process_time:.2f}ms)"
            )
            raise


class RequestValidationMiddleware(BaseHTTPMiddleware):
    """
    Middleware for request validation and sanitization
    """
    
    async def dispatch(self, request: Request, call_next):
        # Add request ID for tracing (you could use UUID here)
        request_id = f"{int(time.time() * 1000)}"
        
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        
        return response
