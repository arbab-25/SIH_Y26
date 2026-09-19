# MASTER BUILD PROMPT — CODE MAZE (SIH26034)
Give the role of a senior full-stack engineer. Build, test, deploy, and browser-verify a complete
production web application exactly as specified. Do not skip sections. Do not invent legal text.

## 1. ANTI GRAVITY EXECUTION WORKFLOW (MANDATORY)
1. First inspect the workspace: confirm RULE_BOOK.pdf, LOGO.jpeg (and fssai.pdf if present) exist.
   If a file is missing, STOP and ask; never generate rule text from memory.
2. Produce an implementation_plan.md artifact (architecture, DB schema, API contracts, file tree,
   task list) and PAUSE for my approval before writing production code.
3. Build in this milestone order: repo+docker+DB+migrations+auth → rule-book parser+seed+Rule Book
   UI → OCR CLI → field extractors + rule engine + tests → scan API + summary UI + accuracy pie
   chart → detailed analysis + overrides + PDF report → history pages + dashboard + email report →
   PWA + Hindi + accessibility pass → deployment.
4. After every milestone: run lint, unit tests, migrations; then use the browser sub-agent to
   navigate the real UI (scan flow, login, Hindi toggle, rule links), capture screenshots, and
   verify zero console errors at 360, 768, 1280 and 1920 px widths, before continuing.
5. Never invent credentials, API keys, or legal text. If a secret is missing, add it to .env.example
   and ask me. Deploy only after all tests pass; run a live health check + smoke scan on the deployed
   URL; finish with a walkthrough.md (URLs, screenshots, test evidence, measured performance, limitations).

## 2. WHAT TO BUILD
"CODE MAZE" — a fully deployed working web app that checks compliance of pre-packaged commodity
labels against the Legal Metrology (Packaged Commodities) Rules, 2011 (as amended up to GSR 629(E),
w.e.f. 01.01.2018). The user photographs or uploads a product label; the system OCR-extracts the
declarations, validates them with a deterministic rule engine, and produces a bilingual compliance
report. Users are non-technical government Legal Metrology inspectors on low-end Android phones with
patchy internet. Plain language, large tap targets, clean and spacious UI.

Definition of done: a non-technical user on a phone photographs a real packet of biscuits, gets a
verdict with cited rules, corrects one misread field, downloads a PDF, and emails the report — with
every confidence number traceable to the OCR engine and every rule quote traceable to RULE_BOOK.pdf.

## 3. NO-HALLUCINATION RULES (NON-NEGOTIABLE — FAIL CLOSED)
- This is a government enforcement tool. A wrong "Compliant" is worse than no verdict.
- Every extracted field carries: OCR confidence % + bounding-box crop of where it was found.
- If a field is not found or confidence < OCR_CONFIDENCE_THRESHOLD (default 0.75, env-configurable),
  mark it NOT_DETECTED → verdict NEEDS_REVIEW → "Needs manual review". NEVER auto-mark non-compliant
  for a missing read, and NEVER fabricate or autocomplete a value.
- Exactly three verdict states per field: COMPLIANT | NON_COMPLIANT | NEEDS_REVIEW.
- Every non-compliance cites the exact rule with QUOTED TEXT loaded from the seeded rules table
  (parsed from RULE_BOOK.pdf), deep-linked to the Rule Book page. Never write rule text from memory.
- Compliance is decided ONLY by deterministic regex + rule-engine functions. No LLM decides verdicts.
- Unknown/ambiguous inputs (category, package type, import status, package dimensions) → NEEDS_REVIEW.
- Multi-image conflicting readings → keep every crop and source image, route to NEEDS_REVIEW.
- Visible disclaimer on every report: "Verify against the physical package before issuing any notice."
- All accuracy numbers come from the OCR engine only. The pie chart is an "OCR confidence
  distribution" — do not label it as legal accuracy.

## 4. BRAND, COLOR & UI TOKENS (USE EXACTLY)
Site name: CODE MAZE. LOGO.jpeg in the top-LEFT corner of the header of every page and on the login
screen. Login button in the top-RIGHT corner of every page.
:root{
  --navy:#12355B; --teal:#0E7490; --bg:#F8FAFC; --card:#FFFFFF; --text:#172033;
  --success:#16A34A; --warning:#D97706; --error:#DC2626;
}
- Fixed navy left sidebar on desktop (logo top-left, nav: Home, Scan/Upload, Rule Book, Reports,
  Scan History, Settings); bottom tab bar on mobile (<768px).
- White rounded-xl cards, shadow-sm, 1px #E2E8F0 border; Inter + Noto Sans (+ Noto Sans Devanagari);
  base 16px, never below 14px. Clean, spacious, uncluttered.
- Status is never colour-only: always colour + icon + text label (WCAG AA). 44x44px min tap targets.
- One primary action per screen; empty states with illustration + single CTA; recovery-step error
  messages ("Image too blurry — hold steady and retake").

## 5. TECH STACK (OPEN SOURCE, FREE TIER, LOW LATENCY — DO NOT SUBSTITUTED WITHOUT ASKING)
- OCR: PaddleOCR (PP-OCRv4/v5, en + devanagari), per-word confidence; fallback Tesseract 5 --psm 6.
- Image pre-processing (before OCR): OpenCV — deskew, perspective-correct, CLAHE, denoise, upscale.
  Region detection: PaddleOCR built-in DBNet (Apache-2.0) to isolate the principal display panel.
  (Do NOT use YOLOv8 — AGPL is a problem for government deployment.)
- Barcode/QR: pyzbar (EAN-13/GTIN, QR) → Rule 6(4A)(a). Fuzzy matching: RapidFuzz.
- Backend: FastAPI (Python 3.11) + Uvicorn; background processing via FastAPI BackgroundTasks
  (keep POST response <200ms, poll for result). Cache OCR models in memory at startup, never per-request.
- Database: PostgreSQL (Neon free tier) via SQLAlchemy + Alembic. All analysis/results tables are
  server-side. Object storage: Supabase Storage free tier (label images + PDFs).
- Frontend: React 18 + Vite + TypeScript + TailwindCSS; charts: Recharts (pie). PWA: vite-plugin-pwa
  + IndexedDB offline scan queue with sync badge. PDF: WeasyPrint. Excel: openpyxl.
- Auth: JWT + bcrypt. Email: SMTP (Brevo free tier or Gmail App Password) — credentials in env only.
- Deploy: backend → Render/Fly.io free; frontend → Vercel/Netlify; DB → Neon. docker-compose for
  local run. Target: upload→verdict < 3s on 1 vCPU/2GB for 1080p (report measured numbers only).

## 6. DATA + SECURITY
- Login with EMAIL OR MOBILE NUMBER + password (OTP optional later); JWT; roles INSPECTOR,
  SENIOR_OFFICER, ADMIN. Login UI/modal on every page's top-right.
- GUEST FREE SCANS (HIDDEN): any unauthenticated device gets 3 free scans before login is forced.
  Implement via an anonymous device/session id (cookie/localStorage + server-side count); do NOT
  show or mention this limit anywhere in the UI; after 3 scans, show a normal "Sign in to continue"
  modal. Guest records store the device id, never a real user id.
- FIRST-TIME REPORT POPUP: the first time a user generates a formal report (per account), show a
  one-time modal explaining what the report contains and confirming the recipient, then continue.
- Import login/registration data into BOTH the PostgreSQL users table AND an Excel workbook
  (admin-only export). NEVER export or store plaintext passwords or password hashes in Excel —
  export only profile metadata (id, name, email/mobile, role, office, created_at, last_login).
- Rate-limit scan creation (30/min/user); validate uploads jpg/png/webp/heic/pdf ≤10MB with
  magic-byte check; strip EXIF except orientation. Audit log for every sensitive action.

## 7. PAGES / SECTIONS (BUILD ALL)
7.1 Scan/Upload (Home): two upload options side by side — (1) "Capture from Camera"
(getUserMedia with explicit camera-permission request; fallback <input capture="environment">)
and (2) "Upload from Gallery/Files". Drag-drop + multi-image (front/back/side panels) merged into
one product record. Client-side compress to max 1600px long edge. Live progress steps: Uploading →
Enhancing image → Reading text → Checking rules → Done. Optional category dropdown (food /
cosmetics / cement / paint / garment / other) that switches Second-Schedule pack lists and FSSAI checks.
BLUR/RETRY HANDLING: if the image is too blurry, low-contrast, or no product label is detected
(launched-text heuristic + OCR word count below threshold), show a human-language retry error:
e.g. "We couldn't read this label clearly. Please move closer, hold steady, and retake the photo."
Never return a guessed verdict for unreadable images.
7.2 Summary (shown immediately after scan, no scroll on desktop): big verdict pill COMPLIANT /
NON-COMPLIANT / NEEDS REVIEW; compliance score = compliant/applicable fields %; extracted-data
table (Field | Value) exactly like the reference mockup; Recharts PIE chart of OCR confidence
distribution over applicable fields — slices: High (≥90%), Medium (75–89%), Low (<75%), Not
detected — tooltip lists which fields are in each slice; avg OCR confidence shown below the chart.
Buttons: View Detailed Analysis, Download PDF, Report this Product.
7.3 Detailed Analysis: per-field accordion — field name, extracted value, OCR confidence %, crop
thumbnail; verdict chip + exact rule reference and quoted rule text; suggested plain-language
corrective action (bilingual). Inspector override ("Mark as correct" / "Correct this value") writes
field_overrides with user id, timestamp, reason; overrides recompute the verdict and are flagged
"manually amended" in the PDF. Side-by-side original image with bounding boxes, zoom/pan.
7.4 Rule Book (left sidebar section): searchable, filterable, offline-available reference built
WORD-FOR-WORD from RULE_BOOK.pdf (attach @RULE_BOOK.pdf): tree Chapter → Rule → Sub-rule, plus
First–Seventh Schedules as sortable structured tables — MUST include as data, not prose: Rule 7(2)
Table-I (min letter/numeral height by PDP area: A≤50→1.0mm (1.5 blown); 50<A≤100→1.5(3.0);
100<A≤500→2.5(4.0); 500<A≤2500→4.0(6.0); 2500<A→6.0(6.0)); First Schedule Table-I & II (max
permissible error); Second Schedule (standard pack quantities — 19 commodity groups, e.g. biscuits
25g/50g/75g/100g/150g/200g/250g/300g/350g/400g then multiples of 500g to 5kg; mineral water
100–5000ml list); Third Schedule ("when packed" commodities); Fourth Schedule (exceptions);
Fifth Schedule (sample size + correction factor: 100–500→50/0.379/3; 501–3200→80/0.295/5; >3200→125/0.234/7).
Postgres tsvector full-text search with highlighted hits. Every violation deep-links here (/rulebook/rule-6-1-e).
7.5 Product Report: formal report — CODEMAZE logo header + "Legal Metrology Compliance Report",
report number, timestamp, inspector name (or "Guest device"), optional geotag, device info;
product summary, extracted declarations, violations table with rule citations, OCR confidence pie
chart, captured label images, signature block; "verify against physical package" disclaimer.
Export PDF (WeasyPrint) + CSV/Excel (openpyxl). Expiring signed shareable read-only link.
7.6 Product Report History: server-side paginated (25/page) table — report id, product,
manufacturer, verdict, score, inspector, date, actions (view / PDF / re-send email); filters date
range, verdict, category, manufacturer, inspector; bulk Excel export. Report contains: user id
(or guest device id), full detailed analysis, and the captured images.
7.7 Scan History: every scan attempt incl. failed/discarded — thumbnail, timestamp, verdict, OCR
confidence, processing time ms, re-run action (re-process stored image with current model).
Per-user by default; SENIOR_OFFICER/ADMIN see all.
7.8 Dashboard (Home): scans today/week/month, average OCR confidence, top violated rules (bar),
compliance trend (line), top non-compliant manufacturers.

## 8. RULE ENGINE (CHECKLIST — AUTHORITATIVE TEXT FROM RULE_BOOK.PDF ONLY)
Registry of independent checker functions, each returning {field, status, confidence, rule_ref,
message_en, message_hi, suggested_fix}. Apply applicability/exemptions BEFORE scoring:
- Rule 3: chapter does not apply to >25kg/25L, cement/fertilizer/farm bags >50kg, industrial/
  institutional packages ("not for retail sale").
- Rule 26: exempt ≤10g/10ml (except tobacco), restaurant/hotel fast food, DPCO-2013 scheduled
  formulations (not medical devices declared as drugs), thread in coil to handloom weavers.
- Rule 24: wholesale packages need only manufacturer/packer name+address, commodity identity, and
  number of retail packages or net quantity.
- Rule 6(1) retail declarations: (a) manufacturer/packer/importer name+address (Rule 10(1) complete
  postal address incl. 6-digit PIN — regex validate); (aa) country of origin for imported; (b)
  common/generic name; (c) net quantity in SI units (Rule 13: g below 1kg, ml below 1L, L preferred
  over l, reject dozen/score/gross per Rule 13(4), N/U for number per 13(5)); (d) month+year of
  manufacture/pre-packing/import (exemptions: bidis, incense sticks, 14.2kg/5kg domestic LPG);
  (da) best-before/use-by where perishable; (e) MRP must match one of the four permitted
  illustrations ("Max. retail/MPR Rs xx.xx inclusive of all taxes" variants) — flag MRP without
  "incl. of all taxes"; check rounding to nearest rupee or 50 paise; (f) dimensions where size relevant.
- Rule 6(2): consumer-care name, address, telephone, e-mail (validate phone + email formats).
- Rule 6(3)/(4): stickers may reduce MRP only; no sticker to alter other declarations.
- Rule 6(7): "GM" at top of PDP for GM food. Rule 6(8): red/brown dot (non-veg) or green dot (veg)
  at top of PDP for soap/shampoo/toothpaste/cosmetics/toiletries — detect via colour blob + shape
  in the top region of the crop.
- Rule 6(10): e-commerce display of mandatory declarations (note only).
- Rule 7(2)/Table-I: min letter height by PDP area; measure glyph height in mm from OCR boxes.
  If package dimensions not supplied → NEEDS_REVIEW, never guess. Rule 7(3): width ≥ ⅓ height
  except "1", "i", "I", "l". Rule 7(4): PDP area formulas (rectangular h×w; cylindrical 40% h×circ).
- Rule 8(1): declarations on PDP; quantity declaration clear space ≥1× numeral height above/below,
  ≥2× left/right. Rule 9(1)(b): MRP + net quantity numerals contrast with background (compute
  contrast ratio from crop). Rule 9(4): declarations in Hindi (Devanagari) or English.
- Rule 12(6): reject vague quantity words: minimum, not less than, average, about, approximately.
- Rule 5 + Second Schedule: for the 19 listed commodity groups validate net quantity against
  allowed pack sizes (seeded JSON table parsed from the PDF).
- Rule 6(1)(e) Explanation III + food: for category=food, defer date checks to FSS Act and ALSO
  check (only if fssai.pdf is attached; otherwise skip with an explicit "FSSAI checks unavailable"
  notice): FSSAI licence number (14 digits), logo, veg/non-veg mark, ingredients list, nutritional
  info, allergen declaration, lot/batch no., manufacture date, best-before.
- Penalty context display-only: Rule 32 (₹4,000 for rules 27&28; ₹5,000 otherwise) + Rule 32A
  compounding table. Label as "for reference only, not a legal determination".

## 9. DATABASE SCHEMA (SERVER-SIDE POSTGRESQL — CREATE EXACTLY)
users(id, name, email UNIQUE, mobile UNIQUE, password_hash, role, designation, office, district,
  state, is_active, created_at, last_login)
products(id, scan_id FK, product_name, generic_name, brand, category, manufacturer_name,
  manufacturer_address, pin_code, country_of_origin, net_quantity_value, net_quantity_unit, mrp,
  mrp_text, mfg_month, mfg_year, best_before, batch_no, fssai_number, consumer_care_phone,
  consumer_care_email, barcode_gtin, created_at)
scans(id, user_id FK NULL, guest_device_id, image_urls JSONB, package_type, category,
  status ENUM('queued','processing','done','failed'),
  verdict ENUM('COMPLIANT','NON_COMPLIANT','NEEDS_REVIEW'), compliance_score NUMERIC(5,2),
  avg_ocr_confidence NUMERIC(5,2), processing_time_ms INT, ocr_engine, model_version,
  geo_lat, geo_lng, device_info, created_at)
extracted_fields(id, scan_id FK, field_key, field_value TEXT, confidence NUMERIC(5,2), bbox JSONB,
  source_image_index, status ENUM('COMPLIANT','NON_COMPLIANT','NEEDS_REVIEW'), created_at)
violations(id, scan_id FK, field_key, rule_id FK, severity ENUM('MAJOR','MINOR'), message_en,
  message_hi, suggested_fix, created_at)
rules(id, rule_number, chapter, title, full_text, schedule_ref, applies_to JSONB,
  search_vector TSVECTOR, source_page INT)
schedule_pack_sizes(id, commodity, unit, allowed_values JSONB, rule_ref)
field_overrides(id, scan_id FK, field_key, old_value, new_value, reason, overridden_by FK users, created_at)
reports(id, scan_id FK, report_number UNIQUE, pdf_url, generated_by FK, emailed_to, emailed_at,
  share_token, created_at)
email_logs(id, report_id FK, to_address, subject, status, error, sent_at)
audit_logs(id, user_id FK, action, entity, entity_id, meta JSONB, ip, created_at)
Indexes: scans(user_id, created_at DESC), violations(rule_id), GIN on rules(search_vector),
products(manufacturer_name). Seed script parses RULE_BOOK.pdf into rules + schedule_pack_sizes;
commit seed JSON so builds are reproducible.

## 10. API SURFACE (FastAPI, /api/v1)
POST /auth/register  POST /auth/login (email OR mobile)  GET /auth/me
POST /scans (multipart images[], category, package_type) → {scan_id, status}
GET /scans/{id} → fields, violations, confidence buckets   GET /scans?page&verdict&from&to&q
POST /scans/{id}/rerun   PATCH /scans/{id}/fields/{key} (override)   DELETE /scans/{id}
POST /reports  GET /reports/{id}  GET /reports/{id}/pdf  GET /reports?filters
POST /reports/{id}/email
GET /rules?q&chapter   GET /rules/{rule_number}   GET /schedules/{name}
GET /dashboard/stats   GET /health (model loaded, db ok)
Upload validation per §6. Guests use guest_device_id header.

## 11. REPORTING A PRODUCT BY EMAIL
"Report this Product" buttons on summary, detailed analysis and report pages. Modal: reason
dropdown (Suspected non-compliance / Misleading MRP / Counterfeit-duplicate / Short quantity /
Other), free-text remarks, checkbox to attach label images + PDF. Backend POST
/reports/{id}/email sends to arbab.momin.2008@gmail.com (REPORT_RECIPIENT_EMAIL env var,
configurable, optional CC list). Subject: "[LM Compliance] {verdict} — {product} — {report_number}".
Branded HTML body (navy/teal) with product summary, violation table with rule citations, score,
inspector, timestamp, share link. Attachments: PDF + compressed images <10MB total. Async with 3
retries + exponential backoff; log every attempt in email_logs; UI shows Sent ✓ / Failed — Retry.

## 12. MULTILINGUAL + UX
English ⇄ हिन्दी toggle in the header, persisted in localStorage; ALL UI strings and all rule
messages stored bilingually (message_en / message_hi). Plain language: say "Month and year of
manufacture is missing", not "mfg_date: null". First-run guided tour (3 steps) + ? help drawer on
every page. Keyboard navigable, ARIA labels, focus rings, prefers-reduced-motion. PWA: queue scans
offline in IndexedDB, badge "3 pending sync", auto-upload on reconnect. Works Chrome/Edge/Safari/
Firefox, Android 9+, iOS 14+. Responsive at 360/768/1280/1920 px — laptop AND mobile.

## 13. ENV VARS (.env.example — EVERY VAR)
DATABASE_URL, REDIS_URL (optional), JWT_SECRET, SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD,
REPORT_RECIPIENT_EMAIL=arbab.momin.2008@gmail.com, STORAGE_* , OCR_CONFIDENCE_THRESHOLD=0.75,
CORS_ORIGINS, VITE_API_BASE_URL. Credentials only in env vars, never in the repo.

## 14. TESTS + DELIVERABLES
- pytest for every rule checker (≥40 cases: compliant label, missing MRP, MRP without "incl. of all
  taxes", missing month/year, non-standard pack size, imported without country of origin, exempt
  ≤10g package, blurry image → NEEDS_REVIEW, vague quantity words, Hindi-only label). Vitest +
  React Testing Library for frontend; Playwright for scan→report happy path.
- Monorepo: /backend /frontend /ml /docs /infra + docker-compose.yml + README.md (architecture
  diagram, setup, deploy steps, licences, measured benchmark table) + EVALUATION.md (field-level
  precision/recall on a held-out set of real label photos, confusion matrix).
- Seed demo account inspector@demo.gov.in. Record measured performance numbers only — never
  advertise unmeasured accuracy.
