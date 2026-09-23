"""Contract tests for the asynchronous scan pipeline.

The upload endpoint returns 202 immediately and processing (OCR + rule engine)
runs as a background task. This exists because on the free deployment tier
(Render, 512 MB / 0.1 CPU) synchronous OCR inside the request exhausted the
instance and the proxy answered 502 before the worker finished. These tests
pin the client-visible contract: accept-then-poll, a terminal status for every
scan, and a user-facing error message on failure.
"""

import asyncio
import io

import pytest
from httpx import ASGITransport, AsyncClient
from PIL import Image, ImageDraw

from app.main import app
from app.services.auth_service import create_access_token


def _auth_headers() -> dict:
    return {
        "Authorization": "Bearer "
        + create_access_token("00000000-0000-0000-0000-000000000001", "INSPECTOR")
    }


def _label_bytes() -> bytes:
    img = Image.new("RGB", (800, 500), color=(255, 255, 255))
    d = ImageDraw.Draw(img)
    d.text((30, 30), "Britannia Good Day Biscuits", fill=(0, 0, 0))
    d.text((30, 70), "Net Wt. 100 g", fill=(0, 0, 0))
    d.text((30, 110), "MRP Rs. 25.00 incl. of all taxes", fill=(0, 0, 0))
    d.text((30, 150), "Mfd: 01/2026", fill=(0, 0, 0))
    d.text((30, 190), "Marketed by ACME Foods Pvt Ltd", fill=(0, 0, 0))
    d.text((30, 230), "12 MG Road, Pune 411001", fill=(0, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


async def _wait_terminal(ac: AsyncClient, scan_id: str, headers: dict) -> dict:
    deadline = asyncio.get_event_loop().time() + 120.0
    last: dict = {}
    while asyncio.get_event_loop().time() < deadline:
        resp = await ac.get(f"/api/v1/scans/{scan_id}", headers=headers)
        assert resp.status_code == 200, resp.text
        last = resp.json()
        if last["status"] in ("done", "failed"):
            return last
        await asyncio.sleep(0.2)
    raise AssertionError(f"scan never reached a terminal status: {last}")


@pytest.mark.asyncio
async def test_scan_upload_returns_202_and_polls_to_done():
    """202 immediately, terminal status later, result fields populated."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post(
            "/api/v1/scans",
            files={"images": ("label.jpg", _label_bytes(), "image/jpeg")},
            data={"category": "food", "package_type": "retail"},
            headers=_auth_headers(),
        )
        assert resp.status_code == 202, resp.text
        body = resp.json()
        scan_id = body["scan_id"]
        assert body["status"] in ("queued", "processing")
        assert body["verdict"] is None

        details = await _wait_terminal(ac, scan_id, _auth_headers())
        assert details["status"] == "done"
        assert details["verdict"] in ("COMPLIANT", "NON_COMPLIANT", "NEEDS_REVIEW")
        assert details["compliance_score"] is not None
        assert details["processing_time_ms"] is not None


@pytest.mark.asyncio
async def test_queued_scan_details_expose_no_premature_verdict():
    """A freshly accepted scan must not expose a verdict before processing runs."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post(
            "/api/v1/scans",
            files={"images": ("label.jpg", _label_bytes(), "image/jpeg")},
            data={"category": "food", "package_type": "retail"},
            headers=_auth_headers(),
        )
        scan_id = resp.json()["scan_id"]

        # First poll: status is an in-flight state, verdict absent.
        first = (await ac.get(f"/api/v1/scans/{scan_id}", headers=_auth_headers())).json()
        assert first["status"] in ("queued", "processing", "done")
        if first["status"] in ("queued", "processing"):
            assert first["verdict"] is None

        await _wait_terminal(ac, scan_id, _auth_headers())


@pytest.mark.asyncio
async def test_failed_scan_carries_error_message():
    """A rejected scan reports FAILED with a user-facing error, never stuck."""
    # A solid-color image produces no OCR items and trips blur rejection.
    img = Image.new("RGB", (400, 300), color=(128, 128, 128))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post(
            "/api/v1/scans",
            files={"images": ("blur.jpg", buf.getvalue(), "image/jpeg")},
            data={"category": "food", "package_type": "retail"},
            headers=_auth_headers(),
        )
        assert resp.status_code == 202
        scan_id = resp.json()["scan_id"]

        details = await _wait_terminal(ac, scan_id, _auth_headers())
        assert details["status"] == "failed"
        assert details.get("error_message")
