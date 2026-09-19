# CODE MAZE — SIH Y26 Implementation Plan

## Goal

Create a clean, production-oriented full-stack CODE MAZE workspace in this folder only. The app will help inspectors upload a packaged-product label, extract declarations, evaluate deterministic Legal Metrology checks, and produce a traceable report.

The source baseline is `D:\ARBAB\SIH DATA\codemaze`. The reference assets in this folder are authoritative inputs and will remain unchanged: `RULE_BOOK.pdf`, `fssai.pdf`, `LOGO.jpeg`, `COLOR CODE.png`, and `test 1.jpeg`.

## Deployment targets

- Frontend: Render static service, using the existing deployed reference at https://codemaze-frontend.onrender.com
- Backend: Render web service, using the existing deployed reference at https://codemaze-api-hz92.onrender.com
- Database: Neon PostgreSQL through `DATABASE_URL`
- Source control: GitHub-ready monorepo layout
- Secrets: environment variables only; no credentials committed

## Clean repository layout

```text
SIH Y26/
├── frontend/                  # React + Vite + TypeScript UI
│   ├── public/                # logo, favicon, offline assets
│   └── src/
│       ├── components/         # shared shell, dialogs, charts, status UI
│       ├── pages/              # dashboard, scan, analysis, rules, reports, history
│       ├── services/           # typed API client and offline queue
│       ├── types/              # shared frontend contracts
│       └── styles/             # design tokens and global styles
├── backend/                   # FastAPI service
│   ├── app/api/               # versioned API routers
│   ├── app/models/            # SQLAlchemy models
│   ├── app/schemas/           # request/response contracts
│   ├── app/services/          # OCR, extraction, rules, reports, auth
│   ├── app/rule_checkers/     # deterministic statutory checks
│   ├── alembic/               # Neon migrations
│   ├── seed/                  # reproducible parsed rule data
│   └── tests/                 # backend tests
├── ml/                        # OCR CLI and model helpers
├── docs/                      # architecture, walkthrough, evaluation
├── infra/                     # Render and Docker deployment files
├── assets/                    # local copies of supplied reference assets
├── .env.example               # documented non-secret configuration
├── docker-compose.yml         # local full-stack development
├── README.md                  # setup, architecture, deployment
└── EVALUATION.md              # measured test/evaluation evidence
```

## Data strategy

1. Parse `RULE_BOOK.pdf` into a committed, reproducible rules seed; do not invent legal text.
2. Keep `fssai.pdf` available for food-category checks and surface an explicit unavailable notice if a deployment does not include it.
3. Use Neon for users, scans, extracted fields, violations, rules, overrides, reports, audit logs, and history.
4. Store images/PDF outputs behind an object-storage interface; local disk is development-only.
5. Keep every extracted value tied to OCR confidence, source image index, and bounding box.
6. Fail closed: unreadable or low-confidence fields become `NEEDS_REVIEW`; only deterministic rule functions assign legal statuses.

## Core API contracts

All routes are under `/api/v1`:

- `POST /auth/register`, `POST /auth/login`, `GET /auth/me`
- `POST /scans`, `GET /scans/{id}`, `GET /scans`, `POST /scans/{id}/rerun`, `PATCH /scans/{id}/fields/{key}`
- `GET /rules`, `GET /rules/{rule_number}`, `GET /schedules/{name}`
- `POST /reports`, `GET /reports/{id}`, `GET /reports/{id}/pdf`, `GET /reports`
- `GET /dashboard/stats`, `GET /health`

The frontend will use a typed Axios client with an environment-configured `VITE_API_BASE_URL`, request error normalization, auth token handling, and offline scan queue support.

## Build milestones

1. Copy and normalize the existing source into this folder; preserve legal/reference files and create the clean layout.
2. Add root configuration, Docker/Render files, `.env.example`, README, and Neon migration/seed workflow.
3. Harden backend configuration, CORS, health checks, upload validation, auth, and database connection behavior.
4. Upgrade the frontend shell and responsive design: professional visual hierarchy, navigation, empty/error/loading states, accessible status labels, and bilingual UI.
5. Connect scan upload → processing → summary → detailed analysis; display confidence buckets and rule citations.
6. Complete Rule Book search/deep links, report history, scan history, dashboard, PDF/report actions, and overrides.
7. Add/repair automated backend and frontend tests, run build/lint/test checks, and document measured results.
8. Verify deployed Render endpoints and provide GitHub/Render/Neon setup instructions without committing secrets.

## Quality gates

- No legal wording is authored from memory; statutory text comes from the supplied PDF/seed.
- No secrets, password hashes, or database URLs are committed.
- Only `D:\ARBAB\SIH Y26` will be modified.
- Backend tests and frontend production build must pass before completion.
- Verify at 360px, 768px, 1280px, and 1920px widths where the browser environment is available.
- Final delivery includes `walkthrough.md` with URLs, test evidence, measured performance, and limitations.

## Immediate implementation decisions

- Use the existing SIH DATA implementation as the functional baseline instead of starting from an empty scaffold.
- Centralize deployment URLs through environment variables so local, Render preview, and production environments do not require code edits.
- Prefer a focused, consistent dashboard experience over adding unsupported third-party features.
- Keep reference assets in `assets/` and link/copy them into frontend public assets as part of the repository arrangement.
