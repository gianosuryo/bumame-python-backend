from fastapi import APIRouter, HTTPException, status
from helper.database import db_postgres
from typing import Dict

router = APIRouter()

@router.get("/healthcheck", response_model=Dict[str, str])
async def healthcheck():
    """
    Check the health of database and Redis connections.
    Returns:
        200 OK if all services are healthy
        503 Service Unavailable if any service is down
    """
    try:
        database_status = "disconnected"
        # Check database connection
        if db_postgres.fetch_query("SELECT 1") is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database connection failed"
            )
        else:
            database_status = "connected"

        
        return {
            "status": "healthy",
            "database": database_status,
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Service unhealthy: {str(e)}"
        )
