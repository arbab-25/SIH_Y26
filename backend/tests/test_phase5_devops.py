"""Phase 5 DevOps tests: deep health payload + optional Sentry init."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services import redis_service


@pytest.mark.asyncio
async def test_health_reports_redis_and_ocr_fields(monkeypatch):
    """/health reports DB, Redis (configured vs reachable), OCR and version."""
    monkeypatch.setattr(redis_service, "_available", None)
    monkeypatch.setattr(redis_service.settings, "REDIS_URL", None)
    redis_service.reset_redis_state()
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get("/api/v1/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["db_ok"] is True
        assert body["redis_configured"] is False
        assert body["redis_ok"] is False
        assert "ocr_engine" in body and "ocr_threads" in body
        assert body["version"]
    finally:
        redis_service.reset_redis_state()


def test_init_sentry_disabled_without_dsn(monkeypatch):
    """No SENTRY_DSN -> init is a no-op returning False (and imports nothing)."""
    import builtins

    from app.services.sentry_service import init_sentry

    real_import = builtins.__import__

    def _reject(name, *args, **kwargs):
        if name.startswith("sentry_sdk"):
            raise AssertionError("sentry_sdk must not be imported when DSN is unset")
        return real_import(name, *args, **kwargs)

    monkeypatch.delenv("SENTRY_DSN", raising=False)
    monkeypatch.setattr(builtins, "__import__", _reject)
    assert init_sentry() is False


def test_init_sentry_reports_missing_package(monkeypatch):
    """DSN set but SDK absent -> warn and continue, never crash the service."""
    import sys

    from app.services import sentry_service

    monkeypatch.setenv("SENTRY_DSN", "https://public@example.ingest.sentry.io/1")

    saved = {name: mod for name, mod in sys.modules.items() if name.startswith("sentry_sdk")}
    for name in list(saved):
        sys.modules.pop(name)
    monkeypatch.setitem(sys.modules, "sentry_sdk", None)  # import fails -> ImportError path

    # sentry_sdk IS installed in dev; simulate the ImportError path instead.
    real_import = __import__

    def _fail(name, *args, **kwargs):
        if name.startswith("sentry_sdk"):
            raise ImportError("simulated: sentry-sdk not installed")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", _fail)
    try:
        assert sentry_service.init_sentry() is False
    finally:
        for name, mod in saved.items():
            sys.modules[name] = mod
