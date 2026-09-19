# CODE MAZE Backend FastAPI Application Entrypoint
"""
Main FastAPI app configuration for the CODE MAZE compliance checker.
Sets up CORS + security headers, includes API routers, and provides a runnable entry point.
"""

import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import uvicorn

from app.config import settings
from app.api import auth, health, rules, scans, reports, dashboard

app = FastAPI(
    title="CODE MAZE",
    description="Legal Metrology compliance checker for government inspectors",
    version=settings.APP_VERSION,
    # Interactive docs only when explicitly enabled (disable debug mode in production)
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    openapi_url="/openapi.json" if settings.DEBUG else None,
)

# Configure CORS – explicit origins only (never wildcard-with-credentials)
origins = settings.cors_origins_list if settings.CORS_ORIGINS else []
if "*" in origins:
    origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials="*" not in origins,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Guest-Device-Id"],
    max_age=3600,
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Security headers on every response per hardening checklist:
    XSS protection, clickjacking defense, MIME sniffing defense, HTTPS enforcement hints.
    """

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("X-XSS-Protection", "1; mode=block")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault(
            "Permissions-Policy", "camera=(self), microphone=(), geolocation=(self)"
        )
        if settings.SECURE_COOKIES:
            # Behind Render/TLS proxies; only meaningful when cookies are ever set
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        # Minimal CSP for the API (serves only JSON + PDF/static uploads)
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'none'; frame-ancestors 'none'; sandbox",
        )
        return response


app.add_middleware(SecurityHeadersMiddleware)


# Custom error handlers — never leak stack traces or internals (disable debug mode)
@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    if settings.DEBUG:
        return JSONResponse(status_code=500, content={"detail": f"Internal Server Error: {exc}"})
    return JSONResponse(status_code=500, content={"detail": "Internal server error. Please try again later."})


# Mount static uploads directory for serving captured label crops and generated PDFs
uploads_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "uploads")
os.makedirs(uploads_dir, exist_ok=True)
from fastapi.staticfiles import StaticFiles
app.mount("/uploads", StaticFiles(directory=uploads_dir), name="uploads")

# Include API routers under /api/v1
app.include_router(auth.router, prefix="/api/v1")
app.include_router(health.router, prefix="/api/v1")
app.include_router(rules.router, prefix="/api/v1")
app.include_router(scans.router, prefix="/api/v1")
app.include_router(reports.router, prefix="/api/v1")
app.include_router(dashboard.router, prefix="/api/v1")


@app.get("/")
async def root():
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "ok",
        "docs": "/docs (enabled only when DEBUG=true)",
    }


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
    )
