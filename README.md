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

## Demo accounts (seeded)

- Inspector: `inspector@demo.gov.in` / `Demo@1234`
- Admin: `admin@codemaze.app` / `Admin@1234`

## Verification

```text
cd frontend && npm ci && npm run build
cd ../backend && python -m pytest          # 115 tests, ~5 s, 0 warnings
cd ../backend && CODEMAZE_E2E=1 python -m pytest tests/test_e2e_local_journey.py -q -s
```

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
