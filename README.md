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
cd ../backend && python -m pytest
```

## Security posture

- Rate limiting on scans, login and registration; guest accounts get 3 free scans then must sign in.
- Upload hardening: magic-byte validation, 10 MB cap, max 5 images per scan, EXIF stripped.
- Security headers on every API response: CSP, X-Frame-Options, X-Content-Type-Options, Referrer-Policy, Permissions-Policy.
- CORS restricted to configured origins; API docs (`/docs`) disabled unless `DEBUG=true`.
- Input sanitization on auth fields; parameterized SQLAlchemy queries throughout (no raw SQL string interpolation).
- `.env`, SQLite DBs, and `__pycache__` are git-ignored.
