import logging

from fastapi import APIRouter, Response, status
from sqlalchemy import text

from app.database import engine

router = APIRouter(tags=["health"])
logger = logging.getLogger(__name__)


@router.get("/health")
async def health():
    """Liveness : le processus répond."""
    return {"status": "ok", "product": "AutoFlow AI", "phase": "observation+automation"}


@router.get("/health/ready")
async def ready(response: Response):
    """Readiness : la base de données est joignable."""
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception:
        logger.exception("Readiness check failed")
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "unavailable", "database": "down"}
    return {"status": "ok", "database": "up"}
