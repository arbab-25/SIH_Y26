"""Integration tests for Scans, Overrides, Reports, PDF export, Email, and Dashboard API."""

import pytest
import io
from PIL import Image, ImageDraw
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.services.auth_service import create_access_token


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
        assert scan_resp.status_code == 201
        scan_data = scan_resp.json()
        assert "scan_id" in scan_data
        scan_id = scan_data["scan_id"]

        # 2. Get scan details (auth required: scan data is enforcement evidence)
        detail_resp = await ac.get(f"/api/v1/scans/{scan_id}", headers=headers)
        assert detail_resp.status_code == 200
        details = detail_resp.json()
        assert "verdict" in details
        assert "confidence_pie" in details
        assert len(details["confidence_pie"]) == 3

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

        # 5. Fetch Report Details
        get_rep_resp = await ac.get(f"/api/v1/reports/{report_number}")
        assert get_rep_resp.status_code == 200
        assert get_rep_resp.json()["report_number"] == report_number

        # 6. Download PDF
        pdf_resp = await ac.get(f"/api/v1/reports/{report_number}/pdf")
        assert pdf_resp.status_code == 200
        assert pdf_resp.headers["content-type"] == "application/pdf"
        assert len(pdf_resp.content) > 100

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

        # 9. List Reports & Excel export
        rep_list_resp = await ac.get("/api/v1/reports?page=1&size=10")
        assert rep_list_resp.status_code == 200

        excel_resp = await ac.get("/api/v1/reports?format=excel")
        assert excel_resp.status_code == 200
        assert len(excel_resp.content) > 50

        # 10. Dashboard stats
        dash_resp = await ac.get("/api/v1/dashboard/stats")
        assert dash_resp.status_code == 200
        dash_data = dash_resp.json()
        assert "total_scans" in dash_data
        assert "top_violated_rules" in dash_data
        assert "compliance_trend" in dash_data
