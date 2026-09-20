"""Opt-in end-to-end journey against the real HTTP stack, real OCR and a real label photo.

Runs the whole inspection path in-process: health -> login -> rule book -> label scan
(with the OCR engine actually reading a photograph) -> report -> PDF -> email ->
override -> history. It needs an OCR engine and the label photo, so it is skipped by
default and enabled with:

    CODEMAZE_E2E=1 python -m pytest tests/test_e2e_local_journey.py -q -s

It exists because the default suite must stay fast and environment-independent, while
this path is the one that catches pipeline-level regressions (an extractor that starts
mis-reading the real label, a document the PDF step cannot build, an access rule that
locks the inspector out of their own report).
"""

import os

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LABEL = os.path.join(REPO_ROOT, "assets", "test 1.jpeg")

pytestmark = pytest.mark.skipif(
    os.environ.get("CODEMAZE_E2E") != "1",
    reason="Real-OCR end-to-end journey; set CODEMAZE_E2E=1 to run it.",
)

VALID_VERDICTS = {"COMPLIANT", "NON_COMPLIANT", "NEEDS_REVIEW"}


@pytest.mark.asyncio
async def test_local_journey_on_real_label():
    if not os.path.exists(LABEL):
        pytest.skip(f"Real label photo not available at {LABEL}")

    with open(LABEL, "rb") as fh:
        label_bytes = fh.read()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://local") as ac:
        # 1. Health reports the database and the OCR engine it will actually use.
        health = await ac.get("/api/v1/health")
        assert health.status_code == 200
        assert health.json()["db_ok"] is True
        print("\n1) health            ", health.json())

        # 2. Sign in with the seeded demo inspector.
        login = await ac.post(
            "/api/v1/auth/login",
            json={"identifier": "inspector@demo.gov.in", "password": "Demo@1234"},
        )
        assert login.status_code == 200
        token = login.json()["token"]["access_token"]
        auth = {"Authorization": f"Bearer {token}"}
        print("2) login             ", login.json()["user"]["role"])

        me = await ac.get("/api/v1/auth/me", headers=auth)
        assert me.status_code == 200 and me.json()["email"] == "inspector@demo.gov.in"

        # 3. The Rule Book the violations deep-link into is served from the seed data.
        rules = await ac.get("/api/v1/rules", params={"q": "best before"})
        assert rules.status_code == 200 and rules.json()
        schedules = await ac.get("/api/v1/schedules/second_schedule_commodities")
        assert schedules.status_code == 200 and len(schedules.json()) == 19

        # 4. Scan the real label.
        scan = await ac.post(
            "/api/v1/scans",
            files={"images": ("label.jpg", label_bytes, "image/jpeg")},
            data={"category": "food", "package_type": "retail"},
            headers=auth,
        )
        assert scan.status_code == 201, scan.text
        scan_id = scan.json()["scan_id"]
        assert scan.json()["verdict"] in VALID_VERDICTS

        details = (await ac.get(f"/api/v1/scans/{scan_id}", headers=auth)).json()
        assert details["verdict"] in VALID_VERDICTS
        assert 0.0 <= details["avg_ocr_confidence"] <= 100.0
        assert len(details["confidence_pie"]) == 3
        # Every citation must resolve to a seeded rule, so the deep link works.
        if details["violations"]:
            seeded = {r["rule_number"] for r in (await ac.get("/api/v1/rules")).json()}
            assert all(v["rule_ref"] in seeded for v in details["violations"])
        print(f"4) scan              {details['verdict']} | score {details['compliance_score']} "
              f"| avg OCR {details['avg_ocr_confidence']}% | {details['processing_time_ms']} ms")
        print(f"   product           {details['product']['name']} | "
              f"{details['product']['manufacturer_name']} | net qty "
              f"{details['product']['net_quantity']!r} | MRP {details['product']['mrp']!r}")
        for field in details["extracted_fields"]:
            print(f"   {field['status']:13} {field['field_key']:24} "
                  f"{str(field['field_value'])[:36]:38} {field['confidence']:.1f}%")

        # 5. Generate the formal report.
        report = await ac.post("/api/v1/reports", json={"scan_id": scan_id}, headers=auth)
        assert report.status_code == 201
        report_number = report.json()["report_number"]
        assert report_number.startswith("CMD-")
        share_token = report.json()["share_token"]

        # 6. The report is readable by its inspector, by its share token, and by nobody else.
        assert (await ac.get(f"/api/v1/reports/{report_number}", headers=auth)).status_code == 200
        assert (await ac.get(f"/api/v1/reports/{report_number}")).status_code == 401
        assert (
            await ac.get(f"/api/v1/reports/{report_number}", params={"share_token": share_token})
        ).status_code == 200
        assert (
            await ac.get(f"/api/v1/reports/{report_number}", params={"share_token": "wrong"})
        ).status_code == 401

        # 7. The PDF is a real document.
        pdf = await ac.get(f"/api/v1/reports/{report_number}/pdf", headers=auth)
        assert pdf.status_code == 200
        assert pdf.headers["content-type"] == "application/pdf"
        assert pdf.content[:4] == b"%PDF"
        print(f"5) report            {report_number} | PDF {len(pdf.content)} bytes")

        # 8. 'Report this Product' escalation (mocked transport in the sandbox).
        mail = await ac.post(
            f"/api/v1/reports/{report_number}/email",
            json={"reason": "Suspected non-compliance", "remarks": "end-to-end run"},
            headers=auth,
        )
        assert mail.status_code == 200
        assert mail.json()["status"] in ("sent", "failed")

        # 9. An inspector override recomputes the verdict.
        override = await ac.patch(
            f"/api/v1/scans/{scan_id}/fields/fssai_number",
            json={"new_value": "10717012000120", "reason": "verified on pack"},
            headers=auth,
        )
        assert override.status_code == 200
        assert override.json()["new_verdict"] in VALID_VERDICTS

        # 10. History, bulk Excel export and dashboard all reflect recorded work only.
        history = await ac.get("/api/v1/scans", params={"page": 1, "size": 5}, headers=auth)
        assert history.status_code == 200 and history.json()["total"] >= 1

        assert (await ac.get("/api/v1/reports")).status_code == 401
        reports = await ac.get("/api/v1/reports", params={"size": 25}, headers=auth)
        assert reports.status_code == 200
        assert any(r["report_number"] == report_number for r in reports.json()["items"])
        assert all(r["inspector_name"] for r in reports.json()["items"])

        excel = await ac.get("/api/v1/reports", params={"format": "excel"}, headers=auth)
        assert excel.status_code == 200 and len(excel.content) > 50

        dashboard = await ac.get("/api/v1/dashboard/stats")
        assert dashboard.status_code == 200
        payload = dashboard.json()
        assert payload["total_scans"] >= 1
        print("6) dashboard         ", payload["scans_today"], "today |",
              payload["average_ocr_confidence"], "% avg OCR |",
              len(payload["compliance_trend"]), "trend points")
