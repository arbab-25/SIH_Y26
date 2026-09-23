# CODE MAZE Backend FastAPI Application Entrypoint
"""
Main FastAPI app configuration for the CODE MAZE compliance checker.
Sets up CORS + security headers, includes API routers, and provides a runnable entry point.
"""

import os
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from app.api import auth, dashboard, health, reports, rules, scans
from app.config import settings
from app.services.sentry_service import init_sentry

# Sentry (Phase 5): a no-op unless SENTRY_DSN is set in the environment.
# Must run before the app object is created so early exceptions are captured.
init_sentry()


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

    # Orphan sweep: background scans live in this process's memory, so a platform
    # restart (OOM, deploy) leaves rows stuck in QUEUED/PROCESSING forever — the
    # poller would spin until the client timeout with no answer. Mark them FAILED
    # at boot so inspectors get a clear retry message instead of a hang.
    try:
        from sqlalchemy import update

        from app.database import async_session_factory
        from app.models.scan import Scan, ScanStatus, Verdict

        async with async_session_factory() as session:
            result = await session.execute(
                update(Scan)
                .where(Scan.status.in_([ScanStatus.QUEUED, ScanStatus.PROCESSING]))
                .values(
                    status=ScanStatus.FAILED,
                    verdict=Verdict.NEEDS_REVIEW,
                    error_message=(
                        "Processing was interrupted by a server restart. "
                        "Please scan the label again."
                    ),
                )
            )
            await session.commit()
            # CursorResult exposes rowcount for UPDATE statements on all
            # SQLAlchemy dialects; the async Result stub just doesn't declare it.
            updated = getattr(result, "rowcount", 0)
            if updated:
                print(f"[OK] Marked {updated} interrupted scan(s) as failed at startup.")
    except Exception as exc:
        print(f"[WARN] Startup orphan sweep failed: {exc}")

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
        # The API is HTTPS-only behind Render's TLS terminator; HSTS is sent
        # unconditionally (browsers only honour it over HTTPS anyway).
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        response.headers.setdefault("Cross-Origin-Resource-Policy", "same-site")
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
app.mount("/uploads", StaticFiles(directory=uploads_dir), name="uploads")

# Include API routers under /api/v1
app.include_router(auth.router, prefix="/api/v1")
app.include_router(health.router, prefix="/api/v1")
app.include_router(rules.router, prefix="/api/v1")
app.include_router(scans.router, prefix="/api/v1")
app.include_router(reports.router, prefix="/api/v1")
app.include_router(dashboard.router, prefix="/api/v1")


@app.get("/", response_class=HTMLResponse)
async def landing():
    # Prefer the first configured https origin (the live frontend URL);
    # fall back to the known Render frontend for the demo button.
    frontend_url = "https://codemaze-frontend-m6f0.onrender.com"
    for origin in settings.cors_origins_list:
        if origin.startswith("https://"):
            frontend_url = origin
            break

    html = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>CODE MAZE — Legal Metrology Compliance, Automated</title>
<style>
  :root{
    --navy:#12355B; --navy-2:#0F2C4C; --teal:#0E7490; --cyan:#22D3EE;
    --amber:#F59E0B; --ink:#172033; --slate:#475569; --mist:#F1F5F9;
  }
  *{margin:0;padding:0;box-sizing:border-box}
  html{scroll-behavior:smooth}
  body{font-family:'Segoe UI',system-ui,-apple-system,sans-serif;background:#F8FAFC;color:var(--ink);line-height:1.6}
  .wrap{max-width:1080px;margin:0 auto;padding:0 24px}

  /* ---------- hero ---------- */
  header{position:sticky;top:0;z-index:50;backdrop-filter:blur(10px);background:rgba(255,255,255,.85);border-bottom:1px solid #E2E8F0}
  .nav{display:flex;align-items:center;justify-content:space-between;padding:14px 0}
  .brand{display:flex;align-items:center;gap:12px;text-decoration:none}
  .brand img{height:44px;width:44px;border-radius:10px;object-fit:contain;background:#fff;border:1px solid #E2E8F0;padding:2px}
  .brand b{font-size:1.15rem;color:var(--navy);letter-spacing:-.01em}
  .brand span{display:block;font-size:.72rem;color:var(--teal);font-weight:600;letter-spacing:.08em;text-transform:uppercase}
  .nav a.cta{background:var(--navy);color:#fff;text-decoration:none;font-weight:700;font-size:.85rem;padding:10px 18px;border-radius:10px;transition:.2s}
  .nav a.cta:hover{background:var(--teal);transform:translateY(-1px)}

  .hero{padding:72px 0 56px;display:grid;grid-template-columns:1.1fr .9fr;gap:48px;align-items:center}
  .pill{display:inline-flex;align-items:center;gap:8px;background:#ECFEFF;border:1px solid #A5F3FC;color:#155E75;font-size:.8rem;font-weight:700;padding:7px 14px;border-radius:999px}
  .dot{width:8px;height:8px;border-radius:50%;background:#10B981;animation:pulse 2s infinite}
  @keyframes pulse{0%,100%{box-shadow:0 0 0 0 rgba(16,185,129,.5)}50%{box-shadow:0 0 0 6px rgba(16,185,129,0)}}
  .hero h1{font-size:clamp(2rem,4.6vw,3.2rem);line-height:1.12;color:var(--navy);letter-spacing:-.02em;margin:18px 0 14px}
  .hero h1 em{font-style:normal;color:var(--teal);position:relative;white-space:nowrap}
  .hero h1 em::after{content:"";position:absolute;left:0;right:0;bottom:4px;height:10px;background:rgba(34,211,238,.25);border-radius:4px;z-index:-1}
  .hero p.lead{font-size:1.06rem;color:var(--slate);max-width:520px}
  .hero-actions{display:flex;gap:12px;margin-top:26px;flex-wrap:wrap}
  .btn{display:inline-flex;align-items:center;gap:9px;padding:13px 22px;border-radius:12px;font-weight:700;font-size:.92rem;text-decoration:none;transition:.2s;min-height:46px}
  .btn.primary{background:linear-gradient(135deg,var(--teal),#0891B2);color:#fff;box-shadow:0 8px 20px -8px rgba(14,116,144,.55)}
  .btn.primary:hover{transform:translateY(-2px);box-shadow:0 12px 26px -8px rgba(14,116,144,.65)}
  .btn.ghost{border:1.5px solid #CBD5E1;color:var(--navy)}
  .btn.ghost:hover{border-color:var(--teal);color:var(--teal)}

  .hero-art{position:relative;display:flex;justify-content:center}
  .scan-stage{position:relative;width:min(360px,80vw);aspect-ratio:3/4;border-radius:20px;overflow:hidden;
    box-shadow:0 30px 60px -20px rgba(18,53,91,.35), 0 0 0 1px #E2E8F0;animation:float 6s ease-in-out infinite}
  .scan-stage img{width:100%;height:100%;object-fit:cover;display:block}
  .scan-beam{position:absolute;left:0;right:0;height:86px;top:-90px;pointer-events:none;
    background:linear-gradient(to bottom,rgba(34,211,238,0),rgba(34,211,238,.28) 55%,rgba(34,211,238,.85) 98%,rgba(255,255,255,.9));
    border-bottom:2px solid var(--cyan);animation:scan 3.2s ease-in-out infinite;filter:drop-shadow(0 0 12px rgba(34,211,238,.65))}
  @keyframes scan{0%{top:-90px}55%{top:calc(100% - 10px)}100%{top:-90px}}
  @keyframes float{0%,100%{transform:translateY(0)}50%{transform:translateY(-10px)}}
  .badge-chip{position:absolute;background:#fff;border:1px solid #E2E8F0;box-shadow:0 10px 24px -10px rgba(18,53,91,.35);
    border-radius:12px;padding:10px 14px;font-size:.78rem;font-weight:700;color:var(--navy);display:flex;align-items:center;gap:8px}
  .badge-chip.ok{top:22px;left:-38px;animation:float 5s ease-in-out infinite .6s}
  .badge-chip.warn{bottom:26px;right:-30px;animation:float 7s ease-in-out infinite 1.1s}
  .badge-chip small{display:block;font-weight:600;color:var(--slate)}

  /* ---------- sections ---------- */
  section{padding:64px 0}
  .eyebrow{color:var(--teal);font-weight:800;letter-spacing:.14em;text-transform:uppercase;font-size:.75rem}
  h2{font-size:clamp(1.5rem,3vw,2.1rem);color:var(--navy);letter-spacing:-.01em;margin:8px 0 10px}
  .sub{color:var(--slate);max-width:640px}

  .demo-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:26px;margin-top:34px}
  .demo-card{background:#fff;border:1px solid #E2E8F0;border-radius:18px;overflow:hidden;transition:.25s;box-shadow:0 4px 14px -8px rgba(18,53,91,.18)}
  .demo-card:hover{transform:translateY(-5px);box-shadow:0 24px 44px -18px rgba(18,53,91,.35)}
  .demo-thumb{position:relative;aspect-ratio:3/4;overflow:hidden;background:var(--mist)}
  .demo-thumb img{width:100%;height:100%;object-fit:cover;transition:.4s}
  .demo-card:hover .demo-thumb img{transform:scale(1.04)}
  .verdict{position:absolute;top:14px;left:14px;font-size:.72rem;font-weight:800;letter-spacing:.06em;padding:6px 12px;border-radius:999px;color:#fff}
  .verdict.pass{background:#059669}.verdict.fail{background:#DC2626}
  .demo-body{padding:18px 20px 22px}
  .demo-body h3{font-size:1.02rem;color:var(--navy)}
  .demo-body p{font-size:.86rem;color:var(--slate);margin-top:6px}
  .demo-body .tags{display:flex;flex-wrap:wrap;gap:6px;margin-top:12px}
  .tag{font-size:.68rem;font-weight:700;background:var(--mist);color:var(--slate);border-radius:6px;padding:4px 8px}
  .tag.rule{background:#ECFEFF;color:#155E75}

  .steps{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:18px;margin-top:34px}
  .step{background:#fff;border:1px solid #E2E8F0;border-radius:16px;padding:22px;position:relative;transition:.2s}
  .step:hover{border-color:#A5F3FC}
  .step .n{width:34px;height:34px;border-radius:10px;background:linear-gradient(135deg,var(--navy),var(--teal));color:#fff;font-weight:800;display:flex;align-items:center;justify-content:center;margin-bottom:12px}
  .step h3{font-size:.98rem;color:var(--navy)}
  .step p{font-size:.85rem;color:var(--slate);margin-top:5px}

  footer{border-top:1px solid #E2E8F0;padding:30px 0;color:#94A3B8;font-size:.82rem;display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap}
  footer a{color:var(--teal);text-decoration:none;font-weight:600}

  @media(max-width:860px){
    .hero{grid-template-columns:1fr;padding:48px 0;text-align:center}
    .hero p.lead{margin:0 auto}
    .hero-actions{justify-content:center}
    .badge-chip.ok{left:-8px}.badge-chip.warn{right:-8px}
  }
</style>
</head>
<body>

<header>
  <div class="wrap nav">
    <a class="brand" href="/">
      <img src="/logo.jpeg" alt="CODE MAZE logo">
      <div><b>CODE MAZE</b><span>Legal Metrology AI</span></div>
    </a>
    <a class="cta" href="{frontend_url}" target="_blank" rel="noopener">Open the App ↗</a>
  </div>
</header>

<div class="wrap">
  <div class="hero">
    <div>
      <span class="pill"><span class="dot"></span> Deterministic rule engine · live</span>
      <h1>Every label,<br>checked against <em>every rule</em>.</h1>
      <p class="lead">CODE MAZE reads packaged-commodity labels with OCR, then verifies all 34 main rules of the
      Legal Metrology (Packaged Commodities) Rules, 2011 — MRP, net quantity, dates, addresses, symbols and more —
      with a deterministic, auditable verdict.</p>
      <div class="hero-actions">
        <a class="btn primary" href="{frontend_url}" target="_blank" rel="noopener">Start a Scan →</a>
        <a class="btn ghost" href="/docs">API Docs</a>
      </div>
    </div>
    <div class="hero-art">
      <div class="scan-stage">
        <div class="scan-beam"></div>
        <img src="/assets/demo/demo_label_compliant.png" alt="Demo label being scanned">
        <div class="badge-chip ok">✅ MRP · Qty · Dates<small>4 declarations verified</small></div>
        <div class="badge-chip warn">⚠ 6(1)(e) MRP<small>missing tax note</small></div>
      </div>
    </div>
  </div>

  <section id="demo">
    <span class="eyebrow">See it in action</span>
    <h2>Two labels. Two very different verdicts.</h2>
    <p class="sub">These demo packs are checked by the exact same deterministic pipeline inspectors use in the field —
    try them in the app with the one-tap sample scan.</p>

    <div class="demo-grid">
      <div class="demo-card">
        <div class="demo-thumb">
          <span class="verdict pass">✔ COMPLIANT</span>
          <img src="/assets/demo/demo_label_compliant.png" alt="Compliant biscuits label">
        </div>
        <div class="demo-body">
          <h3>Butter Cookies — 100 g</h3>
          <p>Every mandatory declaration present: net quantity, MRP with tax note, manufacture &amp; best-before dates, full address with PIN, consumer care and the veg symbol.</p>
          <div class="tags">
            <span class="tag rule">Rule 6(1)(a)</span><span class="tag rule">6(1)(c)</span>
            <span class="tag rule">6(1)(d)</span><span class="tag rule">6(1)(e)</span>
            <span class="tag rule">Rule 10</span><span class="tag rule">FSSAI</span>
          </div>
        </div>
      </div>

      <div class="demo-card">
        <div class="demo-thumb">
          <span class="verdict fail">✘ NON-COMPLIANT</span>
          <img src="/assets/demo/demo_label_violation.png" alt="Non-compliant detergent label">
        </div>
        <div class="demo-body">
          <h3>Shine Detergent — 500 g</h3>
          <p>Looks innocent — but the MRP, manufacture month/year, PIN code and consumer-care details are all missing. The engine catches every gap automatically.</p>
          <div class="tags">
            <span class="tag rule">Rule 6(1)(d)</span><span class="tag rule">6(1)(e)</span>
            <span class="tag rule">Rule 9</span><span class="tag rule">Rule 10</span>
            <span class="tag rule">Rule 6(2)</span>
          </div>
        </div>
      </div>
    </div>
  </section>

  <section id="how">
    <span class="eyebrow">How it works</span>
    <h2>Photo in. Verdict out. Nothing in between but rules.</h2>
    <p class="sub">No black boxes decide compliance — a model reads the pixels, the statute decides the verdict.</p>
    <div class="steps">
      <div class="step"><div class="n">1</div><h3>Capture</h3><p>Inspectors photograph any panel — camera, gallery or offline queue that syncs later.</p></div>
      <div class="step"><div class="n">2</div><h3>Enhance &amp; Read</h3><p>Deskew, denoise and contrast-normalize, then OCR (PP-OCR models + Tesseract fallback) extracts every word with confidence.</p></div>
      <div class="step"><div class="n">3</div><h3>Verify</h3><p>All 34 main rules from the official 2011 Rule Book run as deterministic checks; barcodes cross-check the GTIN.</p></div>
      <div class="step"><div class="n">4</div><h3>Report</h3><p>Signed PDF &amp; Excel reports with cited rule text — audit-ready for enforcement action.</p></div>
    </div>
  </section>

  <footer>
    <span>© 2026 CODE MAZE — Smart India Hackathon</span>
    <span><a href="/api/v1/health">System health</a> · <a href="/docs">OpenAPI docs</a> · <a href="{frontend_url}">Web app</a></span>
  </footer>
</div>

</body>
</html>"""
    # The page is a plain string (its CSS braces rule out an f-string), so the
    # frontend URL is substituted explicitly. Without this every CTA linked to
    # a literal "{frontend_url}" placeholder.
    return HTMLResponse(content=html.replace("{frontend_url}", frontend_url))


# Serve the logo for the status page (and any branding needs)
@app.get("/logo.jpeg", include_in_schema=False)
async def logo():
    for candidate in [
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "LOGO.jpeg"),
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "LOGO.jpeg"),
    ]:
        if os.path.exists(candidate):
            return FileResponse(candidate, media_type="image/jpeg")
    return JSONResponse(status_code=404, content={"detail": "logo not found"})

# Demo label images and other static assets used by the landing page
_assets_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")
if os.path.isdir(_assets_dir):
    app.mount("/assets", StaticFiles(directory=_assets_dir), name="assets")


@app.get("/health", include_in_schema=False)
async def simple_health():
    """Ultra-cheap liveness probe for uptime pingers (deep checks: /api/v1/health)."""
    return JSONResponse({"status": "ok"})


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",  # nosec B104 — required for Docker/Render containers; the host is protected by the platform
        port=8000,
        reload=settings.DEBUG,
    )
