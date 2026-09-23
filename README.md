# CODE MAZE — Legal Metrology Compliance Checker

Full-stack label-compliance workspace for Legal Metrology inspectors: React + Vite frontend, FastAPI backend with deterministic rule engine, OCR, PDF reports, and PostgreSQL persistence.

## Live services

- Frontend: https://codemaze-frontend-m6f0.onrender.com
- API: https://codemaze-api-m6f0.onrender.com
- API health: https://codemaze-api-m6f0.onrender.com/api/v1/health

## Repository layout

```text
frontend/   React + TypeScript + Vite interface
backend/    FastAPI API, SQLAlchemy models, migrations, rule engine, reports
ml/         OCR command-line helpers
assets/     logo, legal PDFs (RULE_BOOK.pdf, fssai.pdf), sample label, colour reference
infra/      deployment notes
```

## Local setup

1. Copy `.env.example` to `backend/.env` and fill in database credentials.
2. Backend: `cd backend && pip install -r requirements.txt && uvicorn app.main:app --reload`
3. Frontend: `cd frontend && npm ci && npm run dev` (set `VITE_API_BASE_URL=http://localhost:8000/api/v1`).

Docker Compose files provide the matching local service arrangement.

## Render + Neon deployment

`render.yaml` defines the backend Docker service and the frontend static site.

Render secret environment variables (set in the Render dashboard, never in git):

| Key | Notes |
| --- | --- |
| `DATABASE_URL` | Neon PostgreSQL connection string (`postgresql://...`). `?sslmode=` is stripped automatically; TLS is forced for remote hosts. |
| `DATABASE_URL_SYNC` | Sync URL used by Alembic. |
| `JWT_SECRET` | Long random string. |
| `SMTP_USER` / `SMTP_PASSWORD` | Optional — enables live report emails. Without them, emails are mock-delivered and logged. |
| `RESEND_API_KEY` | Optional alternative email provider. |
| `REPORT_RECIPIENT_EMAIL` | Reports are sent here (default `arbab.momin.2008@gmail.com`). |
| `CORS_ORIGINS` | Must include the frontend origin. |

On boot the backend runs `render_start.sh`: waits for the database, applies Alembic migrations, seeds the full rule book + schedules + demo accounts, then starts uvicorn.

## Demo accounts (env-seeded — no hardcoded credentials)

The seed script **refuses to invent passwords**. Set these env vars before
`python seed/seed_db.py` (or configure them in the Render dashboard):

```
DEMO_INSPECTOR_EMAIL=inspector@your-domain.gov.in
DEMO_INSPECTOR_PASSWORD=<long random password>
DEMO_ADMIN_EMAIL=admin@your-domain.gov.in
DEMO_ADMIN_PASSWORD=<long random password>
RULE_VERSION_CODE=LMPC-2011-GSR629E-2018   # optional, stamps scans
```

The script prints only the account emails, never the passwords.

## Verification

```text
cd frontend && npm ci && npm run build && npm run lint
cd ../backend && python -m pytest          # 172 tests, ~11 s
cd ../backend && python scripts/benchmark_ocr.py   # OCR field precision/recall
cd ../frontend && npx playwright install chromium && npm run e2e   # needs E2E_TEST_EMAIL/PASSWORD
```

The benchmark prints per-field precision/recall plus a macro average over the
labeled seed set in `backend/tests/benchdata/` (synthetic; see the protocol in
`docs/EVALUATION.md` for real-photo evaluation). Playwright e2e runs against a
live environment and self-skips when no credentials are configured.

The second command is the full journey — sign-in, a real label photograph through the OCR engine, the rule engine, report generation, PDF, email and history — and is skipped by default because it needs an OCR engine and `assets/test 1.jpeg`.

## Measured performance

Measured in this workspace, not estimated. `assets/test 1.jpeg` is a 1200x1600 JPEG photograph of a real package; the figure is the API's own `processing_time_ms` for upload-to-verdict.

| Environment | OCR engine | Threads | Processing time |
| --- | --- | --- | --- |
| AMD EPYC 9254 sandbox, 48 vCPU | RapidOCR (ONNX Runtime, threads pinned to 4) | 4 | 6.7 s / 7.2 s / 8.6 s (three runs) |
| Same, ONNX Runtime default thread count | RapidOCR | unset | ~75 s |

The 1 vCPU / 2 GB deployment target has not been benchmarked from this workspace, so no figure is claimed for it. The thread cap is what makes the difference and is set in `backend/app/services/ocr_service.py` (`ocr_thread_count`).

## Evaluation data

- `docs/EVALUATION.md` — published OCR baselines (PaddleOCR PP-OCRv3/v4, Tesseract 5) quoted
  from official project documentation with citations, our measured timings, and the committed
  precision/recall + confusion-matrix protocol for held-out evaluation.
- `backend/seed/external_baselines.json` — the same external analysis data as a versioned,
  reproducible dataset with source URLs.

## What a scan decides, and on what basis

Every mandatory declaration in Rule 6(1) of the Legal Metrology (Packaged Commodities) Rules, 2011 is checked by a deterministic regex/rule function — no model decides a verdict. Each extracted field carries the OCR confidence and the crop it came from, and a declaration that could not be read is reported as NEEDS_REVIEW rather than as compliance or a violation. Every violation cites the rule the checker applied, resolved against the seeded rule book (parsed from `RULE_BOOK.pdf`), and links to that rule's quoted text.

## Security posture

- Rate limiting on scans, login and registration; guest mode is removed — sign-in is required for every scan, report, and history view.
- Report reads are scoped to the generating inspector (Senior Officers and Admins see the office's records) with a read-only share token for the report's PDF, so sequential report numbers cannot be used to enumerate inspections.
- Upload hardening: magic-byte validation, 10 MB cap, max 5 images per scan, EXIF stripped.
- Security headers on every API response: CSP, X-Frame-Options, X-Content-Type-Options, Referrer-Policy, Permissions-Policy.
- CORS restricted to configured origins; API docs (`/docs`) disabled unless `DEBUG=true`.
- Input sanitization on auth fields; parameterized SQLAlchemy queries throughout (no raw SQL string interpolation).
- `.env`, SQLite DBs, and `__pycache__` are git-ignored.

---

## Architecture (post Phase 1–5 upgrades)

```
Label photo ──► Upload API (202) ──► dispatch
                                     ├─ RQ + Redis worker (REDIS_URL set)
                                     └─ in-process background task (fallback)
OCR: RapidOCR (PP-OCR ONNX) ⇄ Tesseract fallback
Preprocess: deskew (Hough) → NL-means denoise → CLAHE → bounded upscale
Cross-check: pyzbar EAN/QR → confirm / demote / fill-at-review
Deterministic rule engine (no ML decides verdicts) ──► Postgres + audit trail
Report: WeasyPrint PDF (mirrored to S3/R2 when STORAGE_BACKEND=s3) + openpyxl Excel
Frontend: React 19 + TanStack Query + react-i18next (en/hi) + PWA (offline queue)
```

### Optional services (all degrade gracefully)

| Service | Env var | When unset | Free option |
| --- | --- | --- | --- |
| Job queue + cache | `REDIS_URL` | Scans run in-process, no caching | Valkey 8 (open source), Upstash free Redis |
| Object storage | `STORAGE_BACKEND=s3` + `S3_*` | Local `uploads/` dir | Cloudflare R2 (10 GB) |
| Error tracking | `SENTRY_DSN` | Fully disabled, zero overhead | sentry.io developer tier |
| Email | `SMTP_*` / `RESEND_API_KEY` | Mock-delivered + logged | Brevo free tier / Gmail app password |

### Job queue & worker

With `REDIS_URL` set, scans run in an RQ worker (`python -m app.worker`,
queue `scans`) and `GET /scans/{id}/job` reports both the RQ job state and the
authoritative scan row. `docker compose up` provisions Valkey + the worker
automatically; on Render add the `codemaze-worker` service from `render.yaml`
(worker instances need a paid plan — otherwise keep scans in-process on the
free tier; the API behaves identically without Redis).

### CI/CD

GitHub Actions runs on every push/PR: backend lint (ruff), typecheck (mypy,
informational), pytest, pip-audit; frontend oxlint, build, npm audit.
Dependabot updates pip/npm/actions weekly-monthly. Playwright e2e
(`npm run e2e`) is repo-available and self-skips without seeded credentials.

### UptimeRobot (avoid free-tier cold starts)

Free plan, 50 monitors: HTTP monitor → `https://codemaze-api-m6f0.onrender.com/api/v1/health`
every 5–10 minutes. The deep health check reports `db_ok`, `redis_ok` and the
loaded OCR engine, so the monitor doubles as a status dashboard. This keeps
the Render instance warm and avoids ~50 s cold-start spins for inspectors.
