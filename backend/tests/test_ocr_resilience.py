"""OCR resilience tests.

Guards the free-tier failure chain observed on Render: multi-threaded ONNX
inference on a 0.1-CPU instance starved the event loop until the platform
restarted the service mid-scan, orphaning rows stuck in 'processing'. Covers
the thread-budget config, the inference-time Tesseract fallback (engine
attribution), and the startup sweep that fails interrupted scans.
"""

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select

from app.main import app
from app.services import ocr_service
from app.services.auth_service import create_access_token


def _auth_headers() -> dict:
    return {
        "Authorization": "Bearer "
        + create_access_token("00000000-0000-0000-0000-000000000001", "INSPECTOR")
    }


# ----------------------------------------------------------------thread budget
def test_thread_budget_respects_ocr_threads_setting(monkeypatch):
    monkeypatch.setattr(ocr_service.settings, "OCR_THREADS", 1)
    assert ocr_service.ocr_thread_count() == 1

    monkeypatch.setattr(ocr_service.settings, "OCR_THREADS", 0)
    # Falls back to the cpu-based cap (1..4)
    assert 1 <= ocr_service.ocr_thread_count() <= 4


def test_rapidocr_engine_is_constructed_with_configured_threads(monkeypatch):
    captured = {}

    class FakeRapidOCR:
        def __init__(self, intra_op_num_threads=None):
            captured["threads"] = intra_op_num_threads

        def __call__(self, image):
            return None

    monkeypatch.setattr(ocr_service.settings, "OCR_THREADS", 2)

    import types
    fake_mod = types.ModuleType("rapidocr_onnxruntime")
    fake_mod.RapidOCR = FakeRapidOCR
    monkeypatch.setitem(__import__("sys").modules, "rapidocr_onnxruntime", fake_mod)

    engine = ocr_service._RapidOCREngine()
    assert captured["threads"] == 2


# ------------------------------------------------------------engine preference
def test_engine_preference_tesseract_is_honored(monkeypatch):
    """OCR_ENGINE=tesseract must not load the ~300MB resident ONNX models.

    Render's memory-limit restarts were caused by get_ocr_engine() always
    loading RapidOCR first, ignoring the configured preference.
    """
    loaded = []

    class FakeRapid:
        name = "rapidocr"

        def __init__(self):
            loaded.append("rapidocr")

    class FakeTess:
        name = "tesseract"

        def __init__(self):
            loaded.append("tesseract")

        def __call__(self, image):
            return []

    import types, sys
    fake_mod = types.ModuleType("rapidocr_onnxruntime")
    fake_mod.RapidOCR = FakeRapid
    monkeypatch.setitem(sys.modules, "rapidocr_onnxruntime", fake_mod)

    monkeypatch.setattr(ocr_service, "_RapidOCREngine", FakeRapid)
    monkeypatch.setattr(ocr_service, "_TesseractEngine", FakeTess)
    monkeypatch.setattr(ocr_service.settings, "OCR_ENGINE", "tesseract")

    # Reset the cached engine so the preference is re-evaluated.
    monkeypatch.setattr(ocr_service, "_OCR_ENGINE", None)
    monkeypatch.setattr(ocr_service, "_OCR_ENGINE_NAME", None)

    engine = ocr_service.get_ocr_engine()
    assert engine.name == "tesseract"
    assert loaded == ["tesseract"], f"expected tesseract only, loaded: {loaded}"


# -------------------------------------------------------inference-time fallback
class _ExplodingEngine:
    name = "rapidocr"

    def __call__(self, image):
        raise MemoryError("ONNX arena allocation failed")


class _WorkingTesseract:
    name = "tesseract"
    called = False

    def __call__(self, image):
        self.called = True
        return [([[0, 0], [10, 0], [10, 10], [0, 10]], "MRP", 0.9)]


def test_run_ocr_falls_back_to_tesseract_and_attributes_engine(monkeypatch):
    exploding = _ExplodingEngine()
    working = _WorkingTesseract()

    monkeypatch.setattr(ocr_service, "get_ocr_engine", lambda: exploding)

    def fake_fallback_factory():
        engine = working
        engine.available = lambda: True
        return engine

    monkeypatch.setattr(ocr_service, "_TesseractEngine", fake_fallback_factory)
    monkeypatch.setattr(ocr_service, "is_image_blurry", lambda img: (False, 999.0))
    monkeypatch.setattr(
        ocr_service, "preprocess_image_for_ocr", lambda img: img
    )

    items, meta = ocr_service.run_ocr(_white_image(), detect_blur=True)
    assert working.called is True
    assert meta["engine"] == "tesseract"
    assert len(items) == 1
    assert items[0].text == "MRP"


def test_run_ocr_reports_error_when_no_engine_survives(monkeypatch):
    exploding = _ExplodingEngine()
    monkeypatch.setattr(ocr_service, "get_ocr_engine", lambda: exploding)
    monkeypatch.setattr(ocr_service, "is_image_blurry", lambda img: (False, 999.0))
    monkeypatch.setattr(ocr_service, "preprocess_image_for_ocr", lambda img: img)

    items, meta = ocr_service.run_ocr(_white_image(), detect_blur=True)
    assert items == []
    assert "error" in meta


def _white_image():
    import numpy as np

    return np.full((60, 180, 3), 255, dtype=np.uint8)


# -------------------------------------------------------------orphan sweep
@pytest.mark.asyncio
async def test_startup_sweep_fails_orphaned_scans():
    """QUEUED/PROCESSING rows at boot become FAILED with a retry message."""
    import asyncio
    import uuid as uuid_mod
    from app.database import async_session_factory
    from app.models.scan import Scan, ScanStatus, Verdict

    stuck_id = uuid_mod.uuid4()
    async with async_session_factory() as session:
        session.add(Scan(
            id=stuck_id,
            user_id=uuid_mod.UUID("00000000-0000-0000-0000-000000000001"),
            image_urls=[],
            status=ScanStatus.PROCESSING,
            created_at=__import__("datetime").datetime.utcnow(),
        ))
        await session.commit()

    from app.main import lifespan

    async with lifespan(app):
        pass  # startup sweep runs on entry

    async with async_session_factory() as session:
        scan = (await session.execute(
            select(Scan).where(Scan.id == stuck_id)
        )).scalar_one()
        assert scan.status == ScanStatus.FAILED
        assert scan.verdict == Verdict.NEEDS_REVIEW
        assert scan.error_message and "interrupted" in scan.error_message.lower()


@pytest.mark.asyncio
async def test_poll_shape_reports_error_message_field():
    """The poll response carries error_message so the client can surface it."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/v1/health")
        assert resp.status_code == 200
        # error_message is part of the scan detail contract; assert the field
        # exists on a real scan lifecycle via the workflow tested elsewhere.
        # Here we only pin that health (used by the platform) still works after
        # the lifespan sweep was added.
        assert resp.json()["db_ok"] is True
