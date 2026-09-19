# Deployment checklist

## GitHub

Push this folder as the repository root. Do not include `.env`, local uploads, generated PDFs, `node_modules`, or `frontend/dist`.

## Neon

Create a PostgreSQL database and provide:

- `DATABASE_URL`: runtime SQLAlchemy connection string
- `DATABASE_URL_SYNC`: migration-compatible connection string

Run the Alembic migration and seed workflow from `backend/` before enabling production scans.

## Render

Connect the GitHub repository and select `render.yaml`. The frontend is a static site and the backend is a Docker web service. Configure secret variables in Render, then smoke-test:

- `GET /api/v1/health`
- frontend load and API connection
- authenticated login
- sample label upload
- report generation

## Persistence

The current local storage mode is appropriate for development only. Configure Supabase/object storage variables before relying on uploaded images and generated reports across Render restarts.
