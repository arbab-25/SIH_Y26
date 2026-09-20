# CODE MAZE verification walkthrough

## Warning-resolution and external-baseline pass

- Frontend `npm run lint`: **0 warnings, 0 errors** (was 7 warnings — five
  `react(set-state-in-effect)` in Dashboard/RuleBook/ReportHistory/ScanHistory, one unused
  variable in `App.tsx`, one `exhaustive-deps` misuse). The data-fetch effects were restructured
  so fetches are pure functions and every `setState` happens in the promise continuation, which
  is also what the React Compiler lint requires. `npx tsc -b --noEmit` and `npm run build` pass.
- Backend `python -m pytest`: **115 passed, 1 skipped, 0 warnings** (was 3 Pydantic
  `PydanticDeprecatedSince20` warnings — class-based `Config` replaced with
  `model_config = ConfigDict(from_attributes=True)` in the auth and rule schemas).
- Added `docs/EVALUATION.md` and `backend/seed/external_baselines.json`: published OCR
  analysis data (PP-OCRv3/v4 accuracy and model-size tables, Tesseract 5 official benchmark
  and release facts) quoted from the official PaddleOCR and Tesseract documentation with URLs
  and retrieval dates, clearly separated from CODE MAZE's own measured numbers, plus the
  committed precision/recall + confusion-matrix protocol for the future held-out evaluation.
  No external figure is presented as a CODE MAZE measurement.

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

## Mandatory-declaration pass (Rule 6 completeness)

The rule engine covered the manufacturer/address, MRP, net quantity, dates, consumer care and food checks, but two mandatory Rule 6(1) declarations were never evaluated and three existing checks could pass invalid reads:

- **Rule 6(1)(b) common/generic name** — read by the extractor but never checked; a missing name or a number-only header passed as compliant. Now checked (missing/low-confidence → NEEDS_REVIEW, unreadable value → NON_COMPLIANT).
- **Rule 6(1)(da) best before / use by** — extracted but listed as display-only, so it always reported COMPLIANT. Now evaluated for perishable categories; a shelf life printed as "6 months from packaging" is resolved against the month and year of manufacture, a date at or before the packing month is NON_COMPLIANT, a passed date is flagged, and a date inside the current month is reported as expiring soon. Unresolvable values route to NEEDS_REVIEW.
- **MRP of ₹0** previously passed the rounding and tax checks and was reported COMPLIANT. A non-positive price is now NON_COMPLIANT.
- **Month of manufacture** is now sanity-checked: an unreadable value → NEEDS_REVIEW, a month in the future → NON_COMPLIANT.
- **Country of origin** is validated for content on imported packages: text that is not a recognised country name or ISO alpha-2 code → NEEDS_REVIEW instead of an automatic pass.

The quoting of Rule 6(1)(d), 6(1)(e) and 6(1)(da) text was replaced with the verbatim strings held in `backend/seed/rules.json`, and `backend/app/utils/regulatory_parsing.py` holds the deterministic date, shelf-life and country parsers.

## Rule citations, dashboard integrity and frontend metadata

- Violations now store the rule the checker actually cited (`violations.rule_id` → `rules.rule_number`), so the API, the PDF report and the email report cite `rule-6-1-e` rather than a reference synthesised from the field name, and the "Read in Rule Book" deep link resolves. Rows written before this change fall back to the previous form.
- `/dashboard/stats` no longer returns placeholder statistics. The top-violated-rules list, the manufacturer table and the 7-day trend are aggregated from recorded scans, the average OCR confidence is the real average, and each series is empty when nothing has been recorded. Previously the endpoint returned invented counts (14/9/7/5/4 breaches, a formula-generated trend, an 88.5% confidence default) while the dashboard empty state claimed that only real inspection records are shown.
- The compact scan summary counted only extracted-field rows, so a scan rejected because a declaration was missing still read "All scanned declarations are compliant." It now counts violations as well and lists each cited breach with its rule reference and corrective action.
- `frontend/index.html` now sets the page title ("CodeMaze - Legal Metrology Compliance Checker"), a meta description, theme colour and social/favicon metadata instead of the template default `frontend`.

## Evidence for this pass

- `python -m pytest` in `backend/`: **84 passed** (62 before, 22 added for the new declarations, MRP amount guard, date sanity, country content and shelf-life resolution).
- `npx tsc -b --noEmit` in `frontend/`: passed. `npm run lint` (oxlint): 0 errors, 7 pre-existing warnings in untouched files.
- The scan→report integration test additionally asserts that every cited violation rule exists in the seeded rule book.
- Verification environment: `backend/.venv` (git-ignored) with the FastAPI/SQLAlchemy/OpenCV/PyMuPDF subset of `backend/requirements.txt`. The OCR binaries themselves are not installed in the sandbox, so the scan tests exercise the no-text paths of the pipeline; the declaration checkers are covered directly by unit tests.

## Local end-to-end run on a real label

The full API was driven in-process (real database, real OCR engine, real PDF writer, mocked SMTP transport) against `assets/test 1.jpeg`, a 1200x1600 photograph of a real package. `POST /scans` produced a NEEDS_REVIEW verdict at 57.14% with a 90.73% average OCR confidence, and the run produced a report number, a 29.6 KB PDF, an Excel export and dashboard aggregates. That run exposed defects the unit tests could not:

- **A country of origin was being invented.** `products.country_of_origin` defaulted to `"India"` for every non-imported package, so the record asserted a declaration that may not be printed anywhere on the label. It is now stored only when it was actually read.
- **Undetected quantity and price were stored as zero.** `net_quantity_value` and `mrp` were coerced to `0.0` when the label did not yield them, which the API then rendered as `Rs. 0.00` — indistinguishable from a package genuinely declaring a zero price. Both columns now hold NULL when nothing was read, and the scan response returns an empty value that the interface shows as "Not Detected".
- **The scan recorded the wrong OCR engine.** `scans.ocr_engine` was written from the configured preference rather than the engine that ran, so a stored confidence could be attributed to the wrong engine. It now records the loaded engine.
- **Multi-panel scans reported one panel's confidence.** `scans.avg_ocr_confidence` took the last processed image's average; it now averages every word read across all panels.
- **The OCR model is loaded on the request path.** The first scan paid for model initialisation, and the runtime's default thread count left this photo at roughly 75 s of inference. Pinning intra-op threads to the available cores brought the same photo to roughly 7.5 s (three measured runs: 6.7 s, 7.2 s, 8.6 s). The model is now warmed once at application startup, and `/api/v1/health` reports `ocr_engine` (the loaded engine), `ocr_engine_loaded`, `ocr_engine_preferred` and `ocr_threads` so a deployment can tell which engine is really serving scans.

## Report access control and history

A verification run showed `GET /api/v1/reports` answering an unauthenticated request with the office's report list and a full Excel export, and `GET /reports/{report_number}` returning an inspector's report — including violations and extracted fields — to anyone who knew the number. Report numbers are sequential (`CMD-20260919-0001`), so the number is guessable. Fixed as follows:

- The report list and the bulk Excel export now require authentication and apply the same visibility rule as scans: an inspector sees their own reports, Senior Officers and Admins see all.
- A single report and its PDF are readable by the inspector who generated it, by a Senior Officer/Admin, or by a caller presenting that report's own unguessable share token (`?share_token=`, compared with a constant-time check). A signed-in inspector from another account gets 403; an anonymous caller gets 401.
- The Excel export wrote the literal string `"Inspector"` into every row. It now names the real generating account, or `"Guest device"` for records written before accounts were required. The same value is returned as `inspector_name` in the report list.

## Frontend follow-ups in this pass

- The report history table now has the inspector column (§7.6) fed by the real account name.
- Its `View` button previously switched to the scan-analysis tab, showing an unrelated screen. It now opens the formal report PDF, which is the read-only view of the report; the access token travels on the request rather than in the URL.

## Verification added

- `backend/tests/test_e2e_local_journey.py` — the whole journey against the real stack and a real label photo, including the access-control expectations above. It needs an OCR engine and the photo, so it is skipped by default and enabled with `CODEMAZE_E2E=1`.
- The scan/report integration test now asserts that anonymous reads of a report, its PDF, the report list and the Excel export are rejected, that another inspector receives 403, that an Admin can read it, that the share token grants read-only access, and that the report list carries a real inspector name.

## Known limitation (not changed in this pass)

When the OCR engine is unavailable on the server, a scan currently still reaches a verdict computed from an empty extraction (every declaration routes to NEEDS_REVIEW, so the verdict fails closed and never reports compliance, but the scan is not reported as a service failure). The blur/word-count guard covers unreadable photos, `/health` now exposes whether an engine is loaded, and the model is warmed at startup; a hard "no OCR engine" condition should still return an explicit service error rather than a compliance verdict. Fixing that changes the `POST /scans` contract and the scan integration test, so it is left as a separate, deliberately scoped change.

## Remaining validation

- Configure Neon, storage, SMTP, and JWT secrets on Render.
- Run backend pytest in a Python environment that includes `backend/requirements.txt`.
- Test upload, OCR, PDF generation, authenticated reporting, and field overrides against the production services.
- Capture production screenshots and measured processing timings after deployment.
- The measured timings above come from a 48-core sandbox with 4 OCR threads pinned; the 1 vCPU / 2 GB deployment target has not been benchmarked from this workspace.
- `backend/.venv` is git-ignored and local only. The sandbox lacks the GUI libraries the production Docker image installs, so it runs headless OpenCV; no production code depends on that.
