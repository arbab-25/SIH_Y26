# CODE MAZE Backend FastAPI Application Entrypoint
"""
Main FastAPI app configuration for the CODE MAZE compliance checker.
Sets up CORS + security headers, includes API routers, and provides a runnable entry point.
"""

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse
from starlette.middleware.base import BaseHTTPMiddleware
import uvicorn

from app.config import settings
from app.api import auth, health, rules, scans, reports, dashboard


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load the OCR model once at boot so no scan request pays for model loading.

    A warm-up failure is logged only: the service still starts and /health reports
    whether an engine is loaded (a scan without one returns a review verdict rather
    than a fabricated result).
    """
    from app.services.ocr_service import get_ocr_engine, get_ocr_engine_name

    try:
        get_ocr_engine()
        print(f"[OK] OCR engine ready at startup: {get_ocr_engine_name()}")
    except Exception as exc:
        print(f"[WARN] OCR engine warm-up failed: {exc}")
    yield


app = FastAPI(
    title="CODE MAZE",
    description="Legal Metrology compliance checker for government inspectors",
    version=settings.APP_VERSION,
    lifespan=lifespan,
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
    allow_headers=["Authorization", "Content-Type"],
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
        # CSP: allow self-hosted assets + inline styles (status page); scripts stay blocked
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'none'; img-src 'self'; style-src 'self' 'unsafe-inline'; frame-ancestors 'none'; sandbox allow-same-origin",
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


@app.get("/", response_class=HTMLResponse)
async def root():
    """Branded status page so opening the API URL in a browser shows a friendly
    screen instead of raw JSON. The API itself lives under /api/v1."""
    frontend_url = "https://codemaze-frontend-m6f0.onrender.com"
    for origin in settings.cors_origins_list:
        if origin.startswith("https://"):
            frontend_url = origin  # first configured https origin = the live frontend
            break
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>CODE MAZE — API Server</title>
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ font-family:'Segoe UI',system-ui,sans-serif; background:#F8FAFC; color:#172033;
         min-height:100vh; display:flex; align-items:center; justify-content:center; padding:24px; }}
  .card {{ background:#fff; border:1px solid #E2E8F0; border-radius:16px; box-shadow:0 4px 12px rgba(18,53,91,.08);
          max-width:520px; width:100%; overflow:hidden; }}
  .head {{ background:#12355B; color:#fff; padding:28px 32px; display:flex; align-items:center; gap:14px; }}
  .head img {{ height:48px; width:48px; object-fit:contain; background:#fff; border-radius:10px; padding:3px; }}
  .head h1 {{ font-size:1.35rem; }} .head p {{ font-size:.8rem; color:#A5D8E8; margin-top:2px; }}
  .body {{ padding:28px 32px; }}
  .badge {{ display:inline-flex; align-items:center; gap:8px; background:#DCFCE7; color:#166534;
           border:1px solid #86EFAC; border-radius:999px; padding:6px 14px; font-weight:600; font-size:.85rem; }}
  .dot {{ width:9px; height:9px; border-radius:50%; background:#16A34A; }}
  p.note {{ margin-top:16px; color:#475569; font-size:.92rem; line-height:1.55; }}
  .links {{ margin-top:22px; display:flex; flex-direction:column; gap:10px; }}
  .links a {{ display:block; text-align:center; padding:12px; border-radius:10px; text-decoration:none;
             font-weight:600; font-size:.9rem; min-height:44px; line-height:20px; }}
  .primary {{ background:#0E7490; color:#fff; }} .primary:hover {{ background:#0c6178; }}
  .secondary {{ background:#F1F5F9; color:#12355B; border:1px solid #E2E8F0; }} .secondary:hover {{ background:#E2E8F0; }}
  .meta {{ margin-top:22px; padding-top:16px; border-top:1px solid #E2E8F0; font-size:.75rem; color:#94A3B8;
          display:flex; justify-content:space-between; }}
</style>
</head>
<body>
  <main class="card">
    <div class="head">
      <img src="/logo.jpeg" alt="CODE MAZE logo" onerror="this.style.display='none'">
      <div><h1>CODE MAZE</h1><p>Legal Metrology Compliance System — API Server</p></div>
    </div>
    <div class="body">
      <span class="badge"><span class="dot"></span> API is running</span>
      <p class="note">This is the backend server for CODE MAZE. Inspectors should use the
      web app below — it handles label scanning, compliance analysis, and reports.</p>
      <div class="links">
        <a class="primary" href="{frontend_url}">Open the CODE MAZE App</a>
        <a class="secondary" href="/api/v1/health">Check API health (JSON)</a>
      </div>
      <div class="meta"><span>v{settings.APP_VERSION}</span><span>Docs enabled only in DEBUG mode</span></div>
    </div>
  </main>
</body>
</html>"""
    return HTMLResponse(content=html)


# Serve the logo for the status page (and any branding needs)
from fastapi.responses import FileResponse

@app.get("/logo.jpeg", include_in_schema=False)
async def logo():
    for candidate in [
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "LOGO.jpeg"),
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "LOGO.jpeg"),
    ]:
        if os.path.exists(candidate):
            return FileResponse(candidate, media_type="image/jpeg")
    return JSONResponse(status_code=404, content={"detail": "logo not found"})


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
    )
