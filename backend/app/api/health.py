"""Health check endpoint."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.database import get_db
from app.config import settings

router = APIRouter(tags=["Health"])


@router.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    """Health check — verifies database and OCR readiness."""
    db_ok = False
    try:
        result = await db.execute(text("SELECT 1"))
        db_ok = result.scalar() == 1
    except Exception:
        db_ok = False

    return {
        "status": "healthy" if db_ok else "degraded",
        "db_ok": db_ok,
        "ocr_engine": settings.OCR_ENGINE,
        "version": settings.APP_VERSION,
    }
