# CODE MAZE — Continuation Guide for the Next AI

## User goal

Build and professionally upgrade a full-stack CODE MAZE website using the supplied application/data, Neon PostgreSQL, Render, and GitHub. Modify files only inside:

`D:\ARBAB\SIH Y26`

Do not modify `D:\ARBAB\CODEX` or `D:\ARBAB\SIH DATA`.

## What has been completed

1. Inspected all three folders.
2. Confirmed `SIH DATA\codemaze` is the existing functional baseline:
   - React/Vite/TypeScript frontend
   - FastAPI backend
   - OCR, rule engine, reports, dashboard, auth, scans, history, migrations, tests
3. Created and approved:
   - `implementation_plan.md`
4. Copied the application into `SIH Y26` and arranged it as:

```text
frontend/
backend/
ml/
assets/
docs/
infra/
render.yaml
docker-compose.yml
docker-compose.prod.yml
.env.example
README.md
```

5. Added:
   - `README.md`
   - `docs/ARCHITECTURE.md`
   - `infra/DEPLOYMENT.md`
6. Updated `render.yaml` so the frontend uses:

`https://codemaze-api-hz92.onrender.com/api/v1`

7. Added the supplied reference files to `assets/` while retaining the original reference files at the SIH Y26 root because the local build instructions require them.
8. Removed demo behavior from the frontend:
   - no synthetic biscuits label generator
   - no invented scan-summary values
   - no invented dashboard figures, rule trends, or manufacturers
   - real-data empty and connection-recovery states instead
9. Upgraded the interface hierarchy, scan workspace, navigation shell, mobile layout, visual tokens, and build output splitting.
10. Linked the workspace to Neon project `misty-term-18610406` (`FINAL`) on the `production` database branch.
11. Added `neon.ts` and `hello.ts`, then deployed the configured Neon Auth service and `api` Neon Function.

## Verification already completed

From `D:\ARBAB\SIH Y26\frontend`:

- `npm ci` completed successfully.
- `npm run build` passed successfully.
- The subsequent quality pass fixed the inherited unused-import, stale dependency, and render-created component warnings. `npm run lint` now has only React's conservative async effect/set-state advisories; `npm run build` passes.
- Backend validation now passes: `python -m pytest` completed with **62 passed**. Tests are isolated to `test.db` and never inherit a Neon URL from `.env`.

Live endpoint checks using PowerShell:

- `https://codemaze-frontend.onrender.com` returned HTTP 200.
- `https://codemaze-api-hz92.onrender.com/api/v1/health` returned HTTP 200:

```json
{"status":"healthy","db_ok":true,"ocr_engine":"tesseract","version":"1.0.0"}
```

Backend pytest could not run because the current Python environment has no `pytest` module. The copied backend contains local `.venv`, `venv`, `.pytest_cache`, `codemaze.db`, and `test.db`; these should be treated as inherited development artifacts and must not be committed.

The browser check at localhost showed an expected dashboard API CORS failure when pointed at the deployed Render API. Render is configured for the deployed frontend origin, not localhost. See `docs/walkthrough.md` for the safe local-testing configuration.

## Neon deployment state

- Project: `misty-term-18610406` (`FINAL`)
- Database branch: `production` (`br-damp-fire-b3m4492q`)
- Region: `aws-ap-southeast-1`
- Neon config: `neon.ts`
- Function source: `hello.ts`
- Function slug: `api`
- Invocation URL: `https://br-damp-fire-b3m4492q-api.compute.c-4.ap-southeast-1.aws.neon.tech/`
- Verified response: HTTP 200, `Hello from Neon Functions`

Neon writes branch connection values to the ignored `.env.local` file and link metadata to the ignored `.neon` file. Never commit either file or print their connection strings. The GitHub source branch remains `deploy-v2`; Neon database branches and Git branches are separate.

## Render database troubleshooting

If Render reports `Could not parse SQLAlchemy URL from string 'DATABASE_URL=...'`, its `DATABASE_URL` secret contains a copied dotenv assignment or a placeholder. In Render, replace both `DATABASE_URL` and `DATABASE_URL_SYNC` with real Neon connection-string values only. No `DATABASE_URL=` prefix belongs in the Value fields.

The deployment script now stops with a direct secret-safe configuration error before Alembic. A valid normal Neon `postgresql://…` runtime URL is converted internally to `postgresql+asyncpg://…`; keep the Alembic sync URL as a normal PostgreSQL URL.

## Important known cleanup item

`frontend/node_modules` was incomplete in the copied baseline. It was moved recoverably to:

`D:\ARBAB\SIH Y26\.recovery-node-modules-incomplete`

The correct dependencies were restored with `npm ci`. Keep the recovery folder out of Git, or move it outside the project after confirming the build remains healthy. Do not delete it without checking with the user unless deletion is explicitly requested.

## Recommended next actions

### 1. Clean repository artifacts

Review `.gitignore` and ensure these are ignored:

```text
.env
__pycache__/
.pytest_cache/
.venv/
venv/
node_modules/
dist/
uploads/*
*.db
.recovery-node-modules-incomplete/
```

Do not remove supplied legal/reference files. Do not copy secrets.

Do not commit `.agents/`; it contains locally installed Neon agent skills. It is now ignored alongside `.neon`.

### 2. Finish functional frontend polish

Review the inherited warnings in:

- `frontend/src/pages/ScanHistory.tsx`
- `frontend/src/pages/Dashboard.tsx`
- `frontend/src/pages/ReportHistory.tsx`
- `frontend/src/pages/ScanSummary.tsx`
- `frontend/src/components/Header.tsx`
- `frontend/src/components/Sidebar.tsx`
- `frontend/src/pages/DetailedAnalysis.tsx`
- `frontend/src/pages/RuleBook.tsx`
- `frontend/src/pages/ScanUpload.tsx`

Remove unused imports, fix hook dependency warnings, and refactor callbacks captured during initialization. Re-run:

```text
cd frontend
npm run build
npm run lint
```

### 3. Backend validation

Install backend requirements in a disposable/approved Python environment, then run:

```text
cd backend
python -m pytest
```

If dependencies are missing, install from `backend/requirements.txt`. Do not commit virtual environments.

### 4. Neon/Render production readiness

In Render, configure secret values from `.env.example`:

- `DATABASE_URL`
- `DATABASE_URL_SYNC`
- `JWT_SECRET`
- SMTP values if email reports are enabled
- storage values if persistent object storage is enabled

Run Alembic migrations and the reproducible seed workflow before production scans. The current deployed health response confirms the remote database and OCR service are healthy, but it does not prove the complete upload-to-report flow.

### 5. Browser QA

Use the live frontend at `https://codemaze-frontend.onrender.com` and verify at 360, 768, 1280, and 1920px:

- initial load has no console errors
- upload/camera scan flow
- summary and detailed analysis
- rule-book search and deep links
- bilingual toggle
- login modal
- report/history/dashboard navigation
- responsive mobile bottom navigation

Record evidence in a final `walkthrough.md` with tested URLs, screenshots if available, measured timings only, and limitations.

## Do not claim yet

- Do not claim backend tests pass until pytest is installed and executed.
- Do not claim OCR accuracy without a measured held-out evaluation set.
- Do not claim object-storage persistence while Render is configured for local storage.
- Do not claim the deployed UI is fully browser-verified until the flows above are tested.
