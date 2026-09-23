# CHANGELOG

All notable changes to CODE MAZE. Format based on [Keep a Changelog](https://keepachangelog.com/).

## [2.0.0] — 2026-09-23 — Phased upgrade (branch `improvement/phased-upgrades`)

Five phases of accuracy, performance, security, frontend and DevOps work.
Every phase has passing tests, its own commit, and no breaking API or DB changes.

### Phase 1 — OCR accuracy (`e3d7e15`)

**Added**
- OpenCV enhancement pipeline before OCR: Hough-based deskew (±15° misdetection guard), NL-means denoise, CLAHE, bounded 1.5× upscale for small frames. Legacy light pipeline retained as an automatic two-pass fallback when the enhanced read underperforms, and selectable via `OCR_ENHANCE=false` for A/B benchmarking.
- pyzbar barcode/QR reading (`detect_barcodes`) with one retry on upscaled frames; degrades to no-op when libzbar is absent.
- Deterministic barcode cross-check (`apply_barcode_crosscheck`, Rule 6(4A)(a)): OCR GTIN matching the decoded digits is confirmed; a mismatch is demoted below the review threshold (never auto-corrected); a missing OCR read is filled at 0.60 confidence so it stays in NEEDS_REVIEW.
- Benchmark script `backend/scripts/benchmark_ocr.py` printing per-field precision/recall + macro average over the labeled set in `backend/tests/benchdata/` (synthetic seed samples rendered on demand; one deliberately skewed). Real-photo protocol remains defined in `docs/EVALUATION.md`.
- New Alembic migration `b4d1c7a9e3f2`: nullable `scans.scan_meta` JSON column (barcode cross-check telemetry).
- 12 tests.

**Decisions**
- Kept **RapidOCR** (PaddleOCR PP-OCR models via ONNX Runtime) instead of full PaddleOCR or EasyOCR. EasyOCR needs PyTorch + ~2 GB models (impossible on Render free tier); full PaddleOCR runtime costs ~500 MB+ resident RAM; RapidOCR ships the same PP-OCRv4 models at ~65 MB and was already thread-tuned for the 1-vCPU instance. Hindi stays on tesseract-ocr-hin (already in the Docker image) until the PaddleOCR devanagari rec model (~10 MB) is evaluated.

### Phase 2 — Backend performance & reliability (`5c38679`)

**Added**
- `redis_service`: optional Redis layer (any RESP-compatible server — Valkey 8, Upstash). Cache helpers (namespaced GET/SET/SCAN-invalidate) and RQ enqueue/status helpers. Every helper no-ops when `REDIS_URL` is unset, so the previous behaviour is the default.
- RQ dispatch for scans: `POST /scans` enqueues to the `scans` queue when Redis is configured and falls back to the existing in-process background task otherwise; response now includes `job_id` and `dispatch` mode.
- `GET /scans/{id}/job` status endpoint combining RQ job state with the authoritative scan row.
- `app/worker.py` RQ worker entrypoint (`python -m app.worker` or `rq worker scans`).
- Storage abstraction (`storage_service`): `local` driver (default) and `s3` driver for any S3-compatible API (Cloudflare R2 free tier, Backblaze B2, MinIO) selected by `STORAGE_BACKEND`; report PDFs mirrored to object storage and restored on download when the local copy is gone.
- Redis caching for rule lookups: `GET /rules/cached-all` plus per-rule deep-link caching with 1 h TTL.
- Dependencies: `redis`, `rq`, `boto3`.
- 9 tests (all pass without live Redis/S3).

**Changed**
- The 202 + poll scan contract is unchanged; existing clients keep working.

### Phase 3 — Rules, audit & security (`ed9aa52`)

**Added**
- Refresh tokens (`refresh_tokens` table): stored as SHA-256 hashes, rotated on every `POST /auth/refresh`, per-token revocation on `POST /auth/logout`, logout-everywhere via `POST /auth/logout-all`. Reuse of an already-rotated token is treated as theft: the whole token family is revoked and committed before the 401.
- Finer RBAC: `SUPERVISOR` role added to the enum; `app/api/rbac.py` dependency helpers (`require_supervisor_or_above`, `require_officer_or_above`, `require_admin`) for office-wide visibility vs escalation vs administration.
- Audit trail: `scan.create` events now write `audit_logs` (actor, SHA-256 input fingerprint, dispatch mode, IP, timestamp) via a fail-open audit service that never blocks the scanned operation.
- Rule versioning: `rule_versions` table + nullable `scans.rule_version`; the active version is stamped on every completed scan so amendments never silently rewrite past verdicts. New versions ship as seed data — no code changes.
- `seed/seed_demo_users.py` — env-driven demo seeding helper.
- Alembic migration `c7e2f8a4b9d1` (refresh_tokens, rule_versions, scans.rule_version).
- 9 tests.

**Changed**
- **Security fix:** demo credentials (`inspector@demo.gov.in / Demo@1234`, `admin@codemaze.app / Admin@1234`) removed from the seed script and README. `seed_db.py` now reads `DEMO_INSPECTOR_EMAIL`, `DEMO_INSPECTOR_PASSWORD`, `DEMO_ADMIN_EMAIL`, `DEMO_ADMIN_PASSWORD` from env vars with no insecure defaults, and skips account seeding (with a warning) when they are missing. Legacy deployments can pass the old values explicitly.
- Login/register responses now include a `refresh_token` field (additive; the access-token contract is unchanged).

### Phase 4 — Frontend (`160a285`)

**Added**
- TanStack Query: global `AppProviders` (query client + PWA registration + language sync + offline-queue drain), `useScanJobStatus` hook polling `GET /scans/{id}/job` with adaptive intervals (1.5 s → 2.5 s → 3 s) replacing blind fixed-rate polling; Dashboard migrated to `useQuery` with cache, loading and error states.
- react-i18next (`src/i18n/index.ts`) wrapping the existing `translations.ts` en/hi dictionaries — no duplicated strings; `cmd_lang` localStorage stays the single source of truth.
- PWA via `vite-plugin-pwa`: installable manifest (navy/teal icons incl. maskable), autoUpdate service worker, offline app shell, NetworkFirst runtime cache for `/api/v1/rules*` so the Rule Book works with patchy connectivity. The existing IndexedDB offline scan queue now auto-drains on reconnect (`offlineSync`); failed syncs stay queued.
- Job progress UI on the scan page: live server status (RQ worker state or scan status) with an `aria-live` polite region during the free-tier OCR wait.
- Accessibility: explicit `label[for]` bindings on the category and package-type selects, `aria-label`s on the three Rule 7(2) dimension inputs, status live region. Existing WCAG conventions (44px targets, colour+icon+text status) retained.
- PWA icons `frontend/public/pwa-icon-{192,512}.png`.

### Phase 5 — DevOps & quality (`d24fb78`)

**Added**
- GitHub Actions CI (`.github/workflows/ci.yml`): backend — ruff lint, mypy (informational), pytest, pip-audit; frontend — oxlint, type-check build, npm audit. Runs on every push and PR.
- Dependabot (`.github/dependabot.yml`): weekly pip + npm, monthly GitHub Actions.
- Playwright e2e (`frontend/e2e/scan-flow.spec.ts`, chromium + mobile-chrome): login journey, scan-to-verdict journey, report-PDF download journey (share-token download asserted byte-level). Tests self-skip without `E2E_TEST_EMAIL`/`E2E_TEST_PASSWORD` so CI without a seeded backend stays green.
- Sentry error tracking (`sentry_service`): fully optional — no import, no network, no overhead unless `SENTRY_DSN` is set. Request bodies and Authorization headers scrubbed; free developer tier.
- Deep `GET /api/v1/health`: adds `redis_configured` / `redis_ok` to the existing DB + OCR payload, failure categories only (never connection strings). Doubles as the UptimeRobot target.
- `docker-compose.yml`: Valkey 8 (open-source Redis) + `codemaze-worker` RQ service; demo credentials via env; shared uploads volume.
- `render.yaml`: documents `REDIS_URL`, `S3_*` (R2), `SENTRY_DSN`, `DEMO_*` secrets, `RULE_VERSION_CODE`, `OCR_ENHANCE`; adds the `codemaze-worker` service; sets `no-cache` for `/sw.js`; comments document the free UptimeRobot ping to avoid cold starts.
- 3 tests.

### Phase 1 & 4 completion pass (`9b8e2c1`)

**Added**
- **Hindi OCR (completes the Phase-1 "English + Hindi" requirement):** the tesseract engine now requests `OCR_LANGUAGES` packs (`eng+hin` default; tesseract-ocr-hin ships in the Docker image) and degrades to English-only at inference time when a pack is missing on the host — never failing the scan. Devanagari OCR items flow through the deterministic extractors; a Hindi-only label yields no fabricated declarations and routes NEEDS_REVIEW (fail-closed). 5 tests.
- **TanStack Query migration completed (completes the Phase-4 "all API calls" requirement):** ScanHistory, ReportHistory and RuleBook moved from manual `useEffect` fetches to `useQuery` with cache + loading + error states; ReportHistory uses server-side pagination via `keepPreviousData` (no table flicker between pages); RuleBook search/chapter/schedule queries cache per key with 5-minute staleTime (deep-link selection derived render-safe, React-Compiler friendly).

**Changed**
- Skipped-items list updated: Vitest unit tests remain future work; the TanStack and Hindi items are now done.

### Tooling added (all free / open source)

| Tool | Role | Cost |
| --- | --- | --- |
| RapidOCR (kept) | PaddleOCR PP-OCR models on ONNX Runtime | Apache-2.0 |
| pyzbar / libzbar0 | EAN/QR decode for cross-check | MIT-ish / LGPL |
| redis-py + RQ | cache + background job queue | BSD |
| Valkey 8 | Redis-compatible server (compose/CI) | BSD (open source) |
| boto3 | S3-compatible storage driver (R2/B2/MinIO) | Apache-2.0 |
| Cloudflare R2 (optional) | 10 GB object storage free tier | free tier |
| TanStack Query | data fetching/caching on the frontend | MIT |
| react-i18next / i18next | internationalization (en/hi) | MIT |
| vite-plugin-pwa + Workbox | installable PWA + offline shell | MIT |
| Playwright | end-to-end browser tests | Apache-2.0 |
| Sentry SDK (optional) | error tracking | free developer tier |
| ruff / mypy / pip-audit | Python lint / typecheck / CVE audit | MIT / Apache-2.0 |
| GitHub Actions + Dependabot | CI and dependency updates | free for public repos |

### Skipped or deferred (and why)

- **Full PaddleOCR / EasyOCR engines** — rejected on free-tier memory grounds (see Phase 1 decision). RapidOCR already runs PaddleOCR's PP-OCR models.
- **PaddleOCR Devanagari rec model** — planned; needs a memory-footprint measurement on the target instance before enabling by default. tesseract-ocr-hin covers Hindi today.
- **Frontend unit tests (Vitest + RTL)** — not in the phase brief's committed scope for this pass; Playwright e2e covers the critical journeys. Natural next step.
- **Render free-tier worker** — Render workers require a paid plan; on the free tier scans stay in-process (identical API contract). The `codemaze-worker` service is pre-configured in `render.yaml` for when Redis is enabled on a paid plan.
- **Real-photo precision/recall numbers** — deliberately not fabricated; the seed benchmark uses synthetic labels and `docs/EVALUATION.md` defines the held-out protocol for real measurements.
- **alembic autogenerate tsvector full-text search for rules** — pre-existing tsvector column exists but PopSQL/Neon full-text remains as-is; not touched to avoid behaviour change.

### Migration notes

- Two new Alembic migrations (`b4d1c7a9e3f2`, `c7e2f8a4b9d1`) apply cleanly to existing databases; all new columns are nullable or new tables.
- New env vars (all optional): `REDIS_URL`, `S3_ENDPOINT_URL`, `S3_BUCKET`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`, `S3_REGION`, `SENTRY_DSN`, `SENTRY_TRACES_SAMPLE_RATE`, `OCR_ENHANCE`, `DEMO_INSPECTOR_EMAIL`, `DEMO_INSPECTOR_PASSWORD`, `DEMO_ADMIN_EMAIL`, `DEMO_ADMIN_PASSWORD`, `RULE_VERSION_CODE`.
- **Action required on deploy:** set the four `DEMO_*` variables (old demo logins no longer exist in the seed).
