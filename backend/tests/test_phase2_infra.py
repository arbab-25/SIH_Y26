"""Phase 2 infra tests: storage abstraction, Redis degradation, job endpoint.

Everything here must pass WITHOUT a live Redis or S3 endpoint (CI has
neither): the design degrades to in-process background tasks + filesystem
storage, which is exactly what the no-Redis free tier runs.
"""

import io

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services import redis_service, storage_service
from app.services.auth_service import create_access_token


def _auth_headers() -> dict:
    return {
        "Authorization": "Bearer "
        + create_access_token("00000000-0000-0000-0000-000000000001", "INSPECTOR")
    }


# ------------------------------------------------------------------- storage
def test_local_driver_roundtrip(tmp_path):
    driver = storage_service.LocalDriver(str(tmp_path))
    identifier = driver.save("reports/test.pdf", b"%PDF-1.4 fake", "application/pdf")
    assert driver.exists("reports/test.pdf")
    assert driver.open_bytes(identifier) == b"%PDF-1.4 fake"


def test_local_driver_rejects_path_traversal(tmp_path):
    driver = storage_service.LocalDriver(str(tmp_path))
    with pytest.raises(ValueError):
        driver.save("../../etc/passwd", b"nope")


def test_get_storage_selects_local_by_default(tmp_path, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "STORAGE_BACKEND", "local")
    monkeypatch.setattr(settings, "LOCAL_UPLOAD_DIR", str(tmp_path))
    storage_service.reset_storage()
    try:
        driver = storage_service.get_storage()
        assert isinstance(driver, storage_service.LocalDriver)
    finally:
        storage_service.reset_storage()


def test_s3_driver_roundtrip_with_stubbed_client(monkeypatch, tmp_path):
    """The S3 driver is exercised with a stubbed boto3 client — no network."""
    calls = {}

    class _StubClient:
        def put_object(self, Bucket, Key, Body, ContentType):
            calls["put"] = (Bucket, Key, bytes(Body), ContentType)
            return {}

        def get_object(self, Bucket, Key):
            calls["get"] = (Bucket, Key)
            return {"Body": io.BytesIO(b"%PDF-1.4 stored")}

    class _FakeBoto3:
        @staticmethod
        def client(service, **kwargs):
            calls["client_kwargs"] = kwargs
            return _StubClient()

    import sys

    monkeypatch.setitem(sys.modules, "boto3", _FakeBoto3)
    monkeypatch.setenv("S3_ACCESS_KEY_ID", "test-key")
    monkeypatch.setenv("S3_SECRET_ACCESS_KEY", "test-secret")

    driver = storage_service.S3Driver(
        bucket="codemaze-test",
        endpoint_url="https://example.r2.cloudflarestorage.com",
    )
    identifier = driver.save("reports/x.pdf", b"%PDF-1.4 x", "application/pdf")
    assert identifier.startswith("https://example.r2.cloudflarestorage.com/codemaze-test/")
    assert driver.open_bytes(identifier) == b"%PDF-1.4 stored"
    assert calls["client_kwargs"]["endpoint_url"] == "https://example.r2.cloudflarestorage.com"
    # boto3 remains importable for other tests (monkeypatch restores it)


# -------------------------------------------------------------------- redis
def test_redis_degrades_when_unconfigured(monkeypatch):
    monkeypatch.setattr(redis_service, "_available", None)
    monkeypatch.setattr(redis_service.settings, "REDIS_URL", None)
    redis_service.reset_redis_state()
    try:
        assert redis_service.redis_available() is False
        assert redis_service.cache_get("any") is None
        assert redis_service.cache_set("any", {"x": 1}) is False
        assert redis_service.enqueue_scan_job("abc", {}) is None
        assert redis_service.fetch_job_status("scan-abc") is None
    finally:
        redis_service.reset_redis_state()


def test_cache_roundtrip_with_fake_redis(monkeypatch):
    """cache_get/set work through a fake Redis client (no server needed)."""
    store = {}

    class _FakeRedis:
        def __init__(self, *a, **k):
            pass

        def ping(self):
            return True

        def get(self, key):
            return store.get(key)

        def setex(self, key, ttl, value):
            store[key] = value

    import sys
    import types

    fake_mod = types.ModuleType("redis")
    fake_mod.Redis = _FakeRedis
    fake_mod.ConnectionPool = types.SimpleNamespace(
        from_url=lambda *a, **k: object()
    )
    monkeypatch.setitem(sys.modules, "redis", fake_mod)
    monkeypatch.setattr(redis_service, "_available", True)
    monkeypatch.setattr(redis_service, "_pool", object())

    try:
        assert redis_service.cache_set("k", {"v": 42}, ttl=60) is True
        assert redis_service.cache_get("k") == {"v": 42}
    finally:
        monkeypatch.setattr(redis_service, "_pool", None)
        monkeypatch.setattr(redis_service, "_available", None)


# ---------------------------------------------------------------- scans API
@pytest.mark.asyncio
async def test_scan_dispatch_reports_in_process_without_redis(monkeypatch):
    """No Redis: POST /scans still 202s with dispatch=in-process (contract kept)."""
    monkeypatch.setattr(redis_service, "enqueue_scan_job", lambda *a, **k: None)

    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (600, 400), (255, 255, 255)).save(buf, format="JPEG")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post(
            "/api/v1/scans",
            files={"images": ("label.jpg", buf.getvalue(), "image/jpeg")},
            data={"category": "food"},
            headers=_auth_headers(),
        )
        assert resp.status_code == 202
        body = resp.json()
        assert body["dispatch"] == "in-process"
        assert body["job_id"] is None

        # Job status endpoint works for the in-process path too (job: null).
        job_resp = await ac.get(f"/api/v1/scans/{body['scan_id']}/job", headers=_auth_headers())
        assert job_resp.status_code == 200
        data = job_resp.json()
        assert data["scan_status"] in ("queued", "processing", "done", "failed")
        assert data["job"] is None
        assert data["done"] == (data["scan_status"] in ("done", "failed"))


@pytest.mark.asyncio
async def test_rules_endpoint_unaffected_by_cache_layer():
    """Rule endpoints behave identically with the cache layer inactive."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/v1/rules/rule-6-1-e")
        # 200 (seeded) or 404 (seed optional in constrained envs) — never a 500.
        assert resp.status_code in (200, 404)


def test_worker_module_exposes_process_scan_job():
    """RQ worker entry imports and exposes the sync job function."""
    from app.worker import process_scan_job

    assert callable(process_scan_job)
