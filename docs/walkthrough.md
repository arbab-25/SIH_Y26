# CODE MAZE verification walkthrough

## Completed professionalization pass

- Removed the synthetic biscuits-label generator and its demo-only entry point.
- Removed fabricated dashboard metrics, manufacturer trends, OCR confidence, and scan summary data.
- Replaced synthetic content with explicit loading, empty, and recovery states.
- Restored the inspection journey to **Scan / Upload → Summary → Detailed Analysis**.
- Improved the application shell, title hierarchy, desktop navigation, mobile layout, upload panels, visual tokens, and focus styling.
- Split production JavaScript into React, charting, networking, and application bundles.

## Evidence

- `npm run build` in `frontend/` passed.
- `python -m pytest` in `backend/` passed: 62 tests.
- Browser-checked the revised scan workspace at desktop width and at 360px width.
- Browser-checked dashboard empty/error states: it explicitly says only real inspection records are shown.
- The deployed API health endpoint returned HTTP 200 with `db_ok: true` and OCR engine `tesseract`.

## Deployment note

The deployed API currently rejects localhost browser requests through CORS. This is correct for a production deployment that permits only the Render frontend origin. For local end-to-end testing either run the FastAPI backend locally with `CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173`, or temporarily add the local Vite origin to the Render API service environment. Do not weaken production CORS to `*` when credentialed access is enabled.

Render database configuration must use the real Neon connection string as the value of each secret. Do not paste a dotenv assignment such as `DATABASE_URL=postgresql://…` into Render's `DATABASE_URL` value field. The backend now rejects that error before attempting migrations and automatically converts a valid Neon runtime URL to SQLAlchemy's asyncpg dialect.

## Remaining validation

- Configure Neon, storage, SMTP, and JWT secrets on Render.
- Run backend pytest in a Python environment that includes `backend/requirements.txt`.
- Test upload, OCR, PDF generation, authenticated reporting, and field overrides against the production services.
- Capture production screenshots and measured processing timings after deployment.
