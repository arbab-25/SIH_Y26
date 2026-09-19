# CODE MAZE Backend FastAPI Application Entrypoint
"""
Main FastAPI app configuration for the CODE MAZE compliance checker.
Sets up CORS, includes API routers, and provides a runnable entry point.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

import os
from fastapi.staticfiles import StaticFiles
from app.config import settings
from app.api import auth, health, rules, scans, reports, dashboard

app = FastAPI(
    title="CODE MAZE",
    description="Legal Metrology compliance checker for government inspectors",
    version=settings.APP_VERSION,
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

# Mount static uploads directory for serving captured label crops and generated PDFs
uploads_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "uploads")
os.makedirs(uploads_dir, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=uploads_dir), name="uploads")

# Include API routers under /api/v1
app.include_router(auth.router, prefix="/api/v1")
app.include_router(health.router, prefix="/api/v1")
app.include_router(rules.router, prefix="/api/v1")
app.include_router(scans.router, prefix="/api/v1")
app.include_router(reports.router, prefix="/api/v1")
app.include_router(dashboard.router, prefix="/api/v1")

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
