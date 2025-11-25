from fastapi import APIRouter, Depends
from app.database import get_db
import aiosqlite

router = APIRouter()

@router.get("/health")
async def health_check(db: aiosqlite.Connection = Depends(get_db)):
    """
    Health check endpoint - verifies API and database connectivity
    """
    try:
        # Test database connection
        async with db.execute("SELECT 1") as cursor:
            result = await cursor.fetchone()
            db_status = "healthy" if result else "unhealthy"
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"

    return {
        "status": "healthy" if db_status == "healthy" else "degraded",
        "database": db_status,
        "version": "0.1.0"
    }
