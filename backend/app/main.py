# CODE MAZE Backend FastAPI Application Entrypoint
"""
Main FastAPI app configuration for the CODE MAZE compliance checker.
Sets up CORS, includes API routers, and provides a runnable entry point.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from app.config import settings
# Import API routers (they will be created in subsequent steps)
# from app.api import auth, scans, reports, rules, dashboard, health

app = FastAPI(
    title="CODE MAZE",
    description="Legal Metrology compliance checker for government inspectors",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Configure CORS – allow origins defined in environment or default to all (development)
if settings.CORS_ORIGINS:
    origins = [origin.strip() for origin in settings.CORS_ORIGINS.split(",")]
else:
    origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routers (placeholders – will be implemented later)
# app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
# app.include_router(scans.router, prefix="/api/v1/scans", tags=["scans"])
# app.include_router(reports.router, prefix="/api/v1/reports", tags=["reports"])
# app.include_router(rules.router, prefix="/api/v1/rules", tags=["rules"])
# app.include_router(dashboard.router, prefix="/api/v1/dashboard", tags=["dashboard"])
# app.include_router(health.router, prefix="/api/v1/health", tags=["health"])

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
