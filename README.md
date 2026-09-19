# CODE MAZE

CODE MAZE is a full-stack label-compliance workspace for Legal Metrology inspectors. It combines a responsive React/Vite client with a FastAPI API, deterministic rule checks, OCR processing, report generation, and Neon PostgreSQL persistence.

## Live services

- Frontend: https://codemaze-frontend.onrender.com
- API: https://codemaze-api-hz92.onrender.com
- API health: https://codemaze-api-hz92.onrender.com/api/v1/health

## Repository layout

```text
frontend/   React + TypeScript + Vite interface
backend/    FastAPI API, SQLAlchemy models, migrations, rule engine, reports
ml/         OCR command-line helpers
assets/     supplied logo, legal PDFs, sample label, and colour reference
docs/       architecture and delivery evidence
infra/      deployment notes and operational configuration
```

## Local setup

1. Copy `.env.example` to `.env` and fill in Neon and optional SMTP/storage values.
2. Start the API with `uvicorn app.main:app --app-dir backend --reload`.
3. Install frontend dependencies with `npm ci` from `frontend/`.
4. Start the UI with `npm run dev` from `frontend/`.

The Docker Compose files provide the matching local service arrangement. The application defaults to local storage for development; use an object-storage provider for persistent Render deployments.

## Render + Neon

`render.yaml` defines the backend Docker service and the frontend static service. Set `DATABASE_URL` to the Neon connection string, `DATABASE_URL_SYNC` for migrations, and update `CORS_ORIGINS` if the frontend hostname changes. `VITE_API_BASE_URL` is already configured for the supplied deployed API.

Never commit `.env`, database URLs, SMTP credentials, JWT secrets, or API keys. Render secret values belong in the service dashboard or secret groups.

## Safety and traceability

- Low-confidence and unreadable fields fail closed to `NEEDS_REVIEW`.
- Legal citations are sourced from the supplied `RULE_BOOK.pdf` seed workflow.
- OCR confidence is reported as OCR confidence, not legal accuracy.
- Reports include the physical-package verification disclaimer.

## Verification

```text
cd frontend
npm ci
npm run build
npm run lint

cd ../backend
pytest
```

The frontend build is currently passing. Lint passes with existing non-blocking unused-import and hook-dependency warnings in the inherited baseline; backend test execution depends on the Python environment and configured database/OCR dependencies.
