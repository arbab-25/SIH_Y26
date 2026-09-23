"""Integration tests for Scans, Overrides, Reports, PDF export, Email, and Dashboard API."""

import asyncio
import io

import pytest
from httpx import ASGITransport, AsyncClient
from PIL import Image, ImageDraw

from app.main import app
from app.services.auth_service import create_access_token


async def _wait_for_scan(
    ac: AsyncClient, scan_id: str, headers: dict, timeout_s: float = 120.0
) -> dict:
    """Poll GET /scans/{id} until the background processing reports done/failed."""
    deadline = asyncio.get_event_loop().time() + timeout_s
    last: dict = {}
    while asyncio.get_event_loop().time() < deadline:
        resp = await ac.get(f"/api/v1/scans/{scan_id}", headers=headers)
        assert resp.status_code == 200, resp.text
        last = resp.json()
        if last["status"] in ("done", "failed"):
            return last
        await asyncio.sleep(0.2)
    raise AssertionError(f"Scan {scan_id} never finished processing; last={last}")


async def _login(ac: AsyncClient, identifier: str, password: str) -> dict:
    """Sign in and return an Authorization header for that account."""
    resp = await ac.post(
        "/api/v1/auth/login", json={"identifier": identifier, "password": password}
    )
    assert resp.status_code == 200, resp.text
    return {"Authorization": "Bearer " + resp.json()["token"]["access_token"]}


def create_mock_label_image():
    """Create a minimal valid image bytes for testing upload."""
    img = Image.new("RGB", (600, 400), color=(255, 255, 255))
    d = ImageDraw.Draw(img)
    d.text((30, 30), "Britannia Good Day Biscuits", fill=(0, 0, 0))
    d.text((30, 70), "Net Qty: 100g", fill=(0, 0, 0))
    d.text((30, 110), "MRP Rs. 25.00 incl. of all taxes", fill=(0, 0, 0))
    d.text((30, 150), "Mfd: 01/2026", fill=(0, 0, 0))
    d.text((30, 190), "Mfd by Britannia Industries Ltd, Kolkata 700017", fill=(0, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    buf.seek(0)
    return buf.getvalue()


@pytest.mark.asyncio
async def test_full_scan_report_workflow():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Create scan via image upload
        img_bytes = create_mock_label_image()
        files = {
            "images": ("label.jpg", img_bytes, "image/jpeg")
        }
        data = {
            "category": "food",
            "package_type": "retail"
        }
        headers = {
            "Authorization": "Bearer " + create_access_token("00000000-0000-0000-0000-000000000001", "INSPECTOR")
        }

        scan_resp = await ac.post("/api/v1/scans", files=files, data=data, headers=headers)
        assert scan_resp.status_code == 202
        scan_data = scan_resp.json()
        assert "scan_id" in scan_data
        scan_id = scan_data["scan_id"]
        # Accepted scan starts queued/processing with no verdict yet.
        assert scan_data["status"] in ("queued", "processing")
        assert scan_data["verdict"] is None

        # 2. Get scan details once background processing completes
        details = await _wait_for_scan(ac, scan_id, headers)
        assert details["status"] == "done"
        assert "verdict" in details
        assert "confidence_pie" in details
        assert len(details["confidence_pie"]) == 3

        # Every violation must cite a rule that really exists in the seeded rule book,
        # so the Rule Book deep link from the analysis screen resolves.
        if details["violations"]:
            rules_resp = await ac.get("/api/v1/rules")
            assert rules_resp.status_code == 200
            seeded_rules = {r["rule_number"] for r in rules_resp.json()}
            for violation in details["violations"]:
                assert violation["rule_ref"] in seeded_rules

        # 3. Test Field Override (Inspector amends a field)
        patch_resp = await ac.patch(
            f"/api/v1/scans/{scan_id}/fields/net_quantity_value",
            json={"new_value": "100.0", "reason": "Verified on physical packaging"},
            headers=headers,
        )
        # If field exists or is overridden
        assert patch_resp.status_code in (200, 404)

        # 4. Generate Formal Report
        rep_resp = await ac.post("/api/v1/reports", json={"scan_id": scan_id}, headers=headers)
        assert rep_resp.status_code == 201
        rep_data = rep_resp.json()
        report_number = rep_data["report_number"]
        assert "CMD-" in report_number

        # 5. Fetch Report Details (generating inspector)
        get_rep_resp = await ac.get(f"/api/v1/reports/{report_number}", headers=headers)
        assert get_rep_resp.status_code == 200
        assert get_rep_resp.json()["report_number"] == report_number

        # 6. Download PDF
        pdf_resp = await ac.get(f"/api/v1/reports/{report_number}/pdf", headers=headers)
        assert pdf_resp.status_code == 200
        assert pdf_resp.headers["content-type"] == "application/pdf"
        assert len(pdf_resp.content) > 100

        # 6b. A report is an inspection record: an anonymous caller must not be able
        # to read it by report number (the numbers are sequential and guessable).
        assert (await ac.get(f"/api/v1/reports/{report_number}")).status_code == 401
        assert (await ac.get(f"/api/v1/reports/{report_number}/pdf")).status_code == 401

        # 6c. Another inspector cannot read it either, but a Senior Officer/Admin can.
        other_inspector = await _login(ac, "inspector@demo.gov.in", "Demo@1234")
        assert (
            await ac.get(f"/api/v1/reports/{report_number}", headers=other_inspector)
        ).status_code == 403
        assert (
            await ac.get(f"/api/v1/reports/{report_number}/pdf", headers=other_inspector)
        ).status_code == 403
        admin_headers = await _login(ac, "admin@codemaze.app", "Admin@1234")
        assert (
            await ac.get(f"/api/v1/reports/{report_number}", headers=admin_headers)
        ).status_code == 200

        # 6d. The report's own share token grants read-only access without an account.
        share_token = rep_data["share_token"]
        shared = await ac.get(
            f"/api/v1/reports/{report_number}", params={"share_token": share_token}
        )
        assert shared.status_code == 200
        assert shared.json()["report_number"] == report_number

        # 7. Test 'Report this Product' Email Escalation
        email_resp = await ac.post(
            f"/api/v1/reports/{report_number}/email",
            json={
                "reason": "Suspected non-compliance",
                "remarks": "Net quantity font height borderline under Rule 7"
            },
            headers=headers,
        )
        assert email_resp.status_code == 200
        assert email_resp.json()["status"] in ("sent", "failed")

        # 8. List Scans (authenticated as the same inspector)
        list_resp = await ac.get("/api/v1/scans?page=1&size=10", headers=headers)
        assert list_resp.status_code == 200
        assert len(list_resp.json()["items"]) >= 1

        # 9. List Reports & Excel export (authenticated; the office record is not public)
        assert (await ac.get("/api/v1/reports?page=1&size=10")).status_code == 401
        assert (await ac.get("/api/v1/reports?format=excel")).status_code == 401

        rep_list_resp = await ac.get("/api/v1/reports?page=1&size=10", headers=headers)
        assert rep_list_resp.status_code == 200
        listed = rep_list_resp.json()["items"]
        assert any(r["report_number"] == report_number for r in listed)
        # The inspector column must name the real generating account, not a placeholder.
        assert all(r["inspector_name"] for r in listed)

        excel_resp = await ac.get("/api/v1/reports?format=excel", headers=headers)
        assert excel_resp.status_code == 200
        assert len(excel_resp.content) > 50

        # An inspector's list must not expose another inspector's reports.
        other_list = await ac.get("/api/v1/reports?page=1&size=25", headers=other_inspector)
        assert other_list.status_code == 200
        assert all(r["report_number"] != report_number for r in other_list.json()["items"])

        # 10. Dashboard stats
        dash_resp = await ac.get("/api/v1/dashboard/stats")
        assert dash_resp.status_code == 200
        dash_data = dash_resp.json()
        assert "total_scans" in dash_data
        assert "top_violated_rules" in dash_data
        assert "compliance_trend" in dash_data
