"""
FastAPI Main Application
Phase 4 - Week 8

Real-Time Cryptocurrency Market Analyzer API

Features:
- REST endpoints for latest prices (Redis)
- REST endpoints for historical data (PostgreSQL)
- WebSocket streaming for real-time updates
- Auto-generated interactive API documentation
- CORS support for frontend integration

Author: Zaid
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from datetime import datetime
import logging
import sys

# Import configuration and database
from .config import settings
from .database import db_manager

# Import routers
from .endpoints import latest, historical, websocket

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title=settings.API_TITLE,
    version=settings.API_VERSION,
    description=settings.API_DESCRIPTION,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    """
    Initialize services on application startup
    """
    logger.info("=" * 60)
    logger.info(f"🚀 Starting {settings.API_TITLE} v{settings.API_VERSION}")
    logger.info("=" * 60)
    
    try:
        # Connect to Redis
        db_manager.connect_redis()
        logger.info("✅ Redis connection established")
        
        # Connect to PostgreSQL
        db_manager.connect_postgres()
        logger.info("✅ PostgreSQL connection pool created")
        
        logger.info("=" * 60)
        logger.info("✅ All services initialized successfully!")
        logger.info(f"📡 API running at: http://{settings.API_HOST}:{settings.API_PORT}")
        logger.info(f"📚 API docs: http://localhost:{settings.API_PORT}/docs")
        logger.info(f"🔌 WebSocket test: http://localhost:{settings.API_PORT}/ws/test")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"❌ Startup failed: {e}")
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """
    Cleanup on application shutdown
    """
    logger.info("🛑 Shutting down API...")
    db_manager.close_all()
    logger.info("✅ Connections closed. Goodbye!")


@app.get("/", tags=["Root"])
async def root():
    """
    Root endpoint - API information
    """
    return {
        "message": "Crypto Market Analyzer API",
        "version": settings.API_VERSION,
        "docs": "/docs",
        "redoc": "/redoc",
        "health": "/health",
        "websocket_test": "/ws/test"
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """
    Health check endpoint - Verify all services are operational
    """
    services = {}
    
    # Check Redis
    try:
        redis_client = db_manager.connect_redis()
        redis_client.ping()
        services["redis"] = "healthy"
    except Exception as e:
        services["redis"] = f"unhealthy: {str(e)}"
    
    # Check PostgreSQL
    try:
        conn = db_manager.get_postgres_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.close()
        db_manager.return_postgres_connection(conn)
        services["postgresql"] = "healthy"
    except Exception as e:
        services["postgresql"] = f"unhealthy: {str(e)}"
    
    # Overall status
    all_healthy = all(status == "healthy" for status in services.values())
    
    return {
        "status": "healthy" if all_healthy else "degraded",
        "timestamp": datetime.utcnow().isoformat(),
        "services": services
    }


# Exception handler for general errors
@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """
    Global exception handler
    """
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": str(exc),
            "timestamp": datetime.utcnow().isoformat()
        }
    )


# Include routers
app.include_router(latest.router, prefix="/api/v1")
app.include_router(historical.router, prefix="/api/v1")
app.include_router(websocket.router)


# Entry point for running with uvicorn
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=True,  # Auto-reload on code changes (development only)
        log_level="info"
    )
