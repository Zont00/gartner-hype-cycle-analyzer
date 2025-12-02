from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import health, analysis
from app.database import init_db
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app instance
app = FastAPI(
    title="Gartner Hype Cycle Analyzer",
    description="Analyzes technologies and positions them on the Gartner Hype Cycle",
    version="0.1.0",
    docs_url="/api/docs",      # Swagger UI at /api/docs
    redoc_url="/api/redoc",    # ReDoc at /api/redoc
)

# CORS configuration (needed for frontend on different port)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Lifespan events for startup/shutdown
@app.on_event("startup")
async def startup_event():
    """Initialize database on startup"""
    logger.info("Initializing database...")
    await init_db()
    logger.info("Application startup complete")

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("Application shutting down...")

# Include routers
app.include_router(health.router, prefix="/api", tags=["health"])
app.include_router(analysis.router, prefix="/api", tags=["analysis"])

# Root endpoint
@app.get("/")
async def root():
    return {
        "message": "Gartner Hype Cycle Analyzer API",
        "docs": "/api/docs"
    }
