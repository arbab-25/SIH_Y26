# Architecture

```text
Inspector browser
      │ HTTPS / VITE_API_BASE_URL
      ▼
Render static React app ───────► Render FastAPI service
                                      │
                                      ├── OCR + image preprocessing
                                      ├── deterministic rule engine
                                      ├── report/PDF services
                                      └── Neon PostgreSQL
```

The frontend is a responsive single-page application with desktop sidebar and mobile tab navigation. The API is versioned under `/api/v1`; database records retain scan history, extracted-field confidence, violations, overrides, and reports for auditability.
