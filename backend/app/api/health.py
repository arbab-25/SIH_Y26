"""Health check endpoint."""

import asyncio

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.database import get_db
from app.config import settings
from app.services.ocr_service import get_ocr_engine_name, ocr_thread_count

router = APIRouter(tags=["Health"])


def _db_error_class(exc: Exception) -> str:
    """Classify a database failure without leaking credentials or hosts.

    Returns only the exception class name plus a coarse category — enough for
    operators to diagnose (auth vs DNS vs TLS vs timeout) without exposing any
    connection-string content in a public endpoint.
    """
    cls_name = type(exc).__name__
    msg = str(exc).lower()
    category = "unknown"
    if "password authentication" in msg or "authentication failed" in msg or "28p01" in msg:
        category = "auth_failed"
    elif "does not exist" in msg and ("database" in msg or "3d000" in msg):
        category = "database_missing"
    elif "name or service not known" in msg or "getaddrinfo" in msg or "nodename" in msg:
        category = "dns_failure"
    elif "connection refused" in msg:
        category = "connection_refused"
    elif "timeout" in msg or "timed out" in msg:
        category = "timeout"
    elif "ssl" in msg or "tls" in msg or "certificate" in msg:
        category = "ssl_error"
    elif "too many connections" in msg or "53300" in msg:
        category = "connection_limit"
    return f"{cls_name}:{category}"


@router.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    """Health check — verifies database and OCR readiness."""
    db_ok = False
    db_error = None
    try:
        result = await db.execute(text("SELECT 1"))
        db_ok = result.scalar() == 1
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        db_ok = False
        db_error = _db_error_class(exc)

    # Report the engine that is actually loaded rather than the configured
    # preference: the previous value always echoed OCR_ENGINE, so a deployment check
    # could not tell which engine had really served the scans.
    active_engine = get_ocr_engine_name()
    response = {
        "status": "healthy" if db_ok else "degraded",
        "db_ok": db_ok,
        "ocr_engine": active_engine or settings.OCR_ENGINE,
        "ocr_engine_loaded": active_engine is not None,
        "ocr_engine_preferred": settings.OCR_ENGINE,
        "ocr_threads": ocr_thread_count(),
        "version": settings.APP_VERSION,
    }
    # Sanitized failure signature only — never credentials, hosts, or URLs.
    if db_error:
        response["db_error"] = db_error
    return response
