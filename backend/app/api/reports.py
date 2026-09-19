"""Reports API Router — Generate, View, Download PDF, Bulk Excel, and Email Reports."""

import os
import uuid
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status, Response
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.user import User
from app.models.scan import Scan
from app.models.report import Report
from app.api.deps import get_current_user
from app.services.pdf_service import generate_compliance_pdf
from app.services.email_service import send_report_email
from app.services.excel_service import export_reports_to_excel

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_report(
    payload: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Generate formal Legal Metrology compliance report and compile PDF (auth required)."""
    scan_id_str = payload.get("scan_id")
    if not scan_id_str:
        raise HTTPException(status_code=400, detail="scan_id is required")

    try:
        scan_id = uuid.UUID(scan_id_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid scan_id UUID format")

    stmt = (
        select(Scan)
        .where(Scan.id == scan_id)
        .options(
            selectinload(Scan.product),
            selectinload(Scan.extracted_fields),
            selectinload(Scan.violations)
        )
    )
    res = await db.execute(stmt)
    scan = res.scalar_one_or_none()
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")

    # Generate sequential report number
    date_str = datetime.utcnow().strftime("%Y%m%d")
    count_res = await db.execute(select(func.count(Report.id)))
    count = (count_res.scalar() or 0) + 1
    report_number = f"CMD-{date_str}-{count:04d}"

    # Generate PDF
    backend_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    reports_dir = os.path.join(backend_root, "uploads", "reports")
    os.makedirs(reports_dir, exist_ok=True)
    pdf_filename = f"{report_number}.pdf"
    pdf_path = os.path.join(reports_dir, pdf_filename)

    logo_path = os.path.join(backend_root, "..", "LOGO.jpeg")
    if not os.path.exists(logo_path):
        logo_path = os.path.join(backend_root, "..", "assets", "LOGO.jpeg")
    if not os.path.exists(logo_path):
        logo_path = os.path.join(backend_root, "LOGO.jpeg")

    report_payload = {
        "report_number": report_number,
        "generated_at": datetime.utcnow().strftime("%d-%b-%Y %H:%M UTC"),
        "inspector_name": current_user.name,
        "verdict": scan.verdict.value if scan.verdict else "NEEDS_REVIEW",
        "compliance_score": float(scan.compliance_score or 0.0),
        "avg_ocr_confidence": float(scan.avg_ocr_confidence or 0.0),
        "product_name": scan.product.product_name if scan.product else "Pre-packaged Commodity",
        "manufacturer_name": scan.product.manufacturer_name if scan.product else "N/A",
        "category": scan.category or "Retail",
        "violations": [
            {
                "field_key": v.field_key,
                "message_en": v.message_en,
                "suggested_fix": v.suggested_fix,
                "rule_ref": getattr(v, "rule_ref", None) or f"rule-{v.field_key.replace('_', '-')}"
            }
            for v in scan.violations
        ],
        "extracted_fields": [
            {
                "field_key": f.field_key,
                "field_value": f.field_value,
                "confidence": float(f.confidence or 0.0),
                "status": f.status.value
            }
            for f in scan.extracted_fields
        ]
    }

    try:
        generate_compliance_pdf(
            report_data=report_payload,
            output_path=pdf_path,
            logo_path=logo_path if os.path.exists(logo_path) else None
        )
    except Exception as e:
        print(f"[WARN] PDF generation error: {e}")

    report = Report(
        id=uuid.uuid4(),
        scan_id=scan.id,
        report_number=report_number,
        pdf_url=f"/api/v1/reports/{report_number}/pdf",
        generated_by=current_user.id,
        share_token=str(uuid.uuid4()),
        created_at=datetime.utcnow()
    )
    db.add(report)
    await db.commit()

    return {
        "id": str(report.id),
        "report_number": report.report_number,
        "pdf_url": report.pdf_url,
        "share_token": report.share_token,
        "created_at": report.created_at.isoformat(),
        "summary": report_payload
    }


@router.get("/{report_id_or_number}")
async def get_report(report_id_or_number: str, db: AsyncSession = Depends(get_db)):
    """Fetch report details by ID or report_number."""
    stmt = (
        select(Report)
        .options(
            selectinload(Report.scan).selectinload(Scan.product),
            selectinload(Report.scan).selectinload(Scan.violations),
            selectinload(Report.scan).selectinload(Scan.extracted_fields),
        )
    )
    try:
        uid = uuid.UUID(report_id_or_number)
        stmt = stmt.where(Report.id == uid)
    except ValueError:
        stmt = stmt.where(Report.report_number == report_id_or_number)

    res = await db.execute(stmt)
    report = res.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    scan = report.scan
    return {
        "id": str(report.id),
        "report_number": report.report_number,
        "pdf_url": report.pdf_url,
        "share_token": report.share_token,
        "created_at": report.created_at.isoformat(),
        "verdict": scan.verdict.value if scan and scan.verdict else "NEEDS_REVIEW",
        "compliance_score": float(scan.compliance_score or 0.0) if scan else 0.0,
        "product_name": scan.product.product_name if scan and scan.product else "Pre-packaged Commodity",
        "manufacturer_name": scan.product.manufacturer_name if scan and scan.product else "N/A",
        "category": scan.category if scan else "Retail",
        "violations": [
            {
                "field_key": v.field_key,
                "message_en": v.message_en,
                "message_hi": v.message_hi,
                "suggested_fix": v.suggested_fix,
                "rule_ref": f"rule-{v.field_key.replace('_', '-')}"
            }
            for v in (scan.violations if scan else [])
        ],
        "extracted_fields": [
            {
                "field_key": f.field_key,
                "field_value": f.field_value,
                "confidence": float(f.confidence or 0.0),
                "status": f.status.value
            }
            for f in (scan.extracted_fields if scan else [])
        ]
    }


@router.get("/{report_id_or_number}/pdf")
async def download_report_pdf(report_id_or_number: str, db: AsyncSession = Depends(get_db)):
    """Download the generated compliance PDF file."""
    stmt = select(Report)
    try:
        uid = uuid.UUID(report_id_or_number)
        stmt = stmt.where(Report.id == uid)
    except ValueError:
        stmt = stmt.where(Report.report_number == report_id_or_number)

    res = await db.execute(stmt)
    report = res.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    backend_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    pdf_path = os.path.join(backend_root, "uploads", "reports", f"{report.report_number}.pdf")

    if not os.path.exists(pdf_path):
        # Regenerate if missing
        stmt_scan = (
            select(Scan)
            .where(Scan.id == report.scan_id)
            .options(
                selectinload(Scan.product),
                selectinload(Scan.extracted_fields),
                selectinload(Scan.violations)
            )
        )
        scan = (await db.execute(stmt_scan)).scalar_one()
        logo_path = os.path.join(backend_root, "..", "assets", "LOGO.jpeg")
        generate_compliance_pdf(
            report_data={
                "report_number": report.report_number,
                "verdict": scan.verdict.value if scan.verdict else "NEEDS_REVIEW",
                "compliance_score": float(scan.compliance_score or 0.0),
                "avg_ocr_confidence": float(scan.avg_ocr_confidence or 0.0),
                "product_name": scan.product.product_name if scan.product else "Commodity",
                "manufacturer_name": scan.product.manufacturer_name if scan.product else "",
                "category": scan.category or "Retail",
                "violations": [{"message_en": v.message_en, "rule_ref": v.field_key} for v in scan.violations],
                "extracted_fields": [{"field_key": f.field_key, "field_value": f.field_value, "confidence": float(f.confidence or 0), "status": f.status.value} for f in scan.extracted_fields]
            },
            output_path=pdf_path,
            logo_path=logo_path if os.path.exists(logo_path) else None
        )

    return FileResponse(
        path=pdf_path,
        media_type="application/pdf",
        filename=f"{report.report_number}.pdf"
    )


@router.post("/{report_id_or_number}/email")
async def email_report(
    report_id_or_number: str,
    payload: dict = {},
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """'Report this Product' via email with formal PDF and cited violations per §11."""
    stmt = (
        select(Report)
        .options(
            selectinload(Report.scan).selectinload(Scan.product),
            selectinload(Report.scan).selectinload(Scan.violations)
        )
    )
    try:
        uid = uuid.UUID(report_id_or_number)
        stmt = stmt.where(Report.id == uid)
    except ValueError:
        stmt = stmt.where(Report.report_number == report_id_or_number)

    res = await db.execute(stmt)
    report = res.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    backend_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    pdf_path = os.path.join(backend_root, "uploads", "reports", f"{report.report_number}.pdf")

    scan = report.scan
    product_name = scan.product.product_name if scan and scan.product else "Pre-packaged Product"
    verdict = scan.verdict.value if scan and scan.verdict else "NEEDS_REVIEW"
    score = float(scan.compliance_score or 0.0) if scan else 0.0
    inspector_name = current_user.name

    violations_data = [
        {
            "rule_ref": v.field_key,
            "message_en": v.message_en,
            "suggested_fix": v.suggested_fix
        }
        for v in (scan.violations if scan else [])
    ]

    result = await send_report_email(
        db=db,
        report_id=report.id,
        report_number=report.report_number,
        product_name=product_name,
        verdict=verdict,
        compliance_score=score,
        inspector_name=inspector_name,
        pdf_path=pdf_path if os.path.exists(pdf_path) else None,
        recipient_email=payload.get("recipient_email"),
        reason=payload.get("reason"),
        remarks=payload.get("remarks"),
        violations=violations_data
    )

    return result


@router.get("")
async def list_reports(
    page: int = Query(1, ge=1),
    size: int = Query(25, ge=1, le=100),
    verdict: Optional[str] = Query(None),
    format: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """Paginated list of reports, or Excel export if ?format=excel per §7.6."""
    stmt = (
        select(Report)
        .options(
            selectinload(Report.scan).selectinload(Scan.product),
            selectinload(Report.scan).selectinload(Scan.violations)
        )
        .order_by(desc(Report.created_at))
    )

    res = await db.execute(stmt)
    all_reports = res.scalars().all()

    # Apply in-memory verdict filter if requested
    if verdict:
        all_reports = [r for r in all_reports if r.scan and r.scan.verdict and r.scan.verdict.value == verdict.upper()]

    if format == "excel":
        excel_rows = []
        for r in all_reports:
            s = r.scan
            excel_rows.append({
                "report_number": r.report_number,
                "created_at": r.created_at.strftime("%Y-%m-%d %H:%M"),
                "product_name": s.product.product_name if s and s.product else "N/A",
                "manufacturer_name": s.product.manufacturer_name if s and s.product else "N/A",
                "category": s.category if s else "General",
                "verdict": s.verdict.value if s and s.verdict else "NEEDS_REVIEW",
                "compliance_score": float(s.compliance_score or 0.0) if s else 0.0,
                "avg_ocr_confidence": float(s.avg_ocr_confidence or 0.0) if s else 0.0,
                "inspector_name": "Inspector",
                "violations_count": len(s.violations) if s else 0
            })
        excel_bytes = export_reports_to_excel(excel_rows)
        return Response(
            content=excel_bytes,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=compliance_reports.xlsx"}
        )

    # Paginate
    total = len(all_reports)
    start = (page - 1) * size
    paged = all_reports[start:start + size]

    items = []
    for r in paged:
        s = r.scan
        items.append({
            "id": str(r.id),
            "report_number": r.report_number,
            "created_at": r.created_at.isoformat(),
            "pdf_url": r.pdf_url,
            "verdict": s.verdict.value if s and s.verdict else "NEEDS_REVIEW",
            "compliance_score": float(s.compliance_score or 0.0) if s else 0.0,
            "product_name": s.product.product_name if s and s.product else "Pre-packaged Item",
            "manufacturer_name": s.product.manufacturer_name if s and s.product else "N/A",
            "category": s.category if s else "General"
        })

    return {
        "items": items,
        "total": total,
        "page": page,
        "size": size,
        "pages": (total + size - 1) // size
    }
