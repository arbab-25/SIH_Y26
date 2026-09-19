"""Scans API Router — Label Upload, OCR Extraction, Rule Validation, Overrides."""

import os
import uuid
import time
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Request, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, or_
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.config import settings
from app.models.user import User
from app.models.scan import Scan, ScanStatus, Verdict
from app.models.product import Product
from app.models.extracted_field import ExtractedField
from app.models.violation import Violation, Severity
from app.models.field_override import FieldOverride
from app.api.deps import get_current_user
from app.services.ocr_service import run_ocr
from app.services.field_extractors import extract_fields_from_ocr
from app.services.rule_engine import evaluate_product_compliance
from app.utils.image_utils import validate_magic_bytes, strip_exif_keep_orientation
from app.utils.rate_limit import check_rate_limit

router = APIRouter(prefix="/scans", tags=["Scans"])


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_scan(
    request: Request,
    images: List[UploadFile] = File(...),
    category: Optional[str] = Form(None),
    package_type: Optional[str] = Form("retail"),
    is_imported: bool = Form(False),
    pdp_height_cm: Optional[float] = Form(None),
    pdp_width_cm: Optional[float] = Form(None),
    measured_glyph_height_mm: Optional[float] = Form(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Upload product label images and run full Legal Metrology compliance scan.

    Authentication is required — guest mode has been removed; every scan is
    attributed to a signed-in inspector account.
    """
    start_time = time.time()

    # Rate limiting (30/min per user)
    check_rate_limit(str(current_user.id), max_requests=30, window_seconds=60)

    # 2. Save uploaded images (secure upload handling: count + size + magic-byte checks)
    if len(images) > settings.MAX_IMAGES_PER_SCAN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Too many images. Maximum {settings.MAX_IMAGES_PER_SCAN} per scan."
        )

    upload_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "uploads")
    os.makedirs(upload_dir, exist_ok=True)

    saved_image_paths = []
    for img in images:
        content = await img.read()
        
        if len(content) > 10 * 1024 * 1024:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File {img.filename} exceeds 10MB limit."
            )
            
        if not validate_magic_bytes(content[:16]):
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail=f"Invalid file format for {img.filename}. Supported: jpg, png, webp, heic, pdf."
            )

        ext = os.path.splitext(img.filename)[1] or ".jpg"
        unique_name = f"{uuid.uuid4()}{ext}"
        target_path = os.path.join(upload_dir, unique_name)
        
        with open(target_path, "wb") as f:
            f.write(content)
            
        if ext.lower() in [".jpg", ".jpeg", ".heic", ".webp", ".png"]:
            strip_exif_keep_orientation(target_path)
            
        saved_image_paths.append(target_path)

    # 3. Create Scan record (always owned by the signed-in inspector)
    scan_id = uuid.uuid4()
    scan = Scan(
        id=scan_id,
        user_id=current_user.id,
        guest_device_id=None,
        image_urls=saved_image_paths,
        package_type=package_type,
        category=category,
        status=ScanStatus.PROCESSING,
        ocr_engine=settings.OCR_ENGINE,
        created_at=datetime.utcnow()
    )
    db.add(scan)
    await db.commit()

    # 4. Process OCR on images
    all_ocr_items = []
    combined_metadata = {}
    is_any_blurry = False
    blur_error_msg = None

    for img_path in saved_image_paths:
        try:
            items, meta = run_ocr(img_path, detect_blur=True)
            if meta.get("blurry"):
                is_any_blurry = True
                blur_error_msg = meta.get("error")
            all_ocr_items.extend(items)
            combined_metadata = meta
        except Exception as e:
            print(f"[WARN] OCR failed for {img_path}: {e}")

    # Blur / retry handling per §7.1
    if is_any_blurry and len(all_ocr_items) < 5:
        scan.status = ScanStatus.FAILED
        scan.verdict = Verdict.NEEDS_REVIEW
        scan.processing_time_ms = int((time.time() - start_time) * 1000)
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=blur_error_msg or "We couldn't read this label clearly. Please move closer, hold steady, and retake the photo."
        )

    # 5. Extract Declarations
    extracted_data = extract_fields_from_ocr(all_ocr_items)
    extracted_dict = extracted_data.to_dict()

    # 6. Evaluate Rules
    evaluation = evaluate_product_compliance(
        extracted_data=extracted_dict,
        category=category,
        package_type=package_type,
        is_imported=is_imported,
        pdp_height_cm=pdp_height_cm,
        pdp_width_cm=pdp_width_cm,
        measured_glyph_height_mm=measured_glyph_height_mm
    )

    # 7. Persist Extracted Fields
    for key, item in extracted_dict.items():
        # Determine status from evaluation results
        matching_res = next((r for r in evaluation.results if r.field == key), None)
        f_status = matching_res.status if matching_res else (
            Verdict.COMPLIANT if item.get("confidence", 0) >= 75 else Verdict.NEEDS_REVIEW
        )
        ef = ExtractedField(
            scan_id=scan_id,
            field_key=key,
            field_value=str(item.get("value", "")),
            confidence=item.get("confidence", 0.0),
            bbox=item.get("bbox"),
            status=f_status
        )
        db.add(ef)

    # 8. Persist Violations
    for v in evaluation.violations:
        viol = Violation(
            scan_id=scan_id,
            field_key=v.field,
            severity=Severity.MAJOR if v.severity == "MAJOR" else Severity.MINOR,
            message_en=v.message_en,
            message_hi=v.message_hi,
            suggested_fix=v.suggested_fix
        )
        db.add(viol)

    # 9. Persist Product summary record
    product = Product(
        scan_id=scan_id,
        product_name=str(extracted_data.get("product_name") or "Pre-packaged Commodity"),
        brand=str(extracted_data.get("brand") or ""),
        category=category or "General",
        manufacturer_name=str(extracted_data.get("manufacturer_name") or ""),
        manufacturer_address=str(extracted_data.get("manufacturer_address") or ""),
        pin_code=str(extracted_data.get("pin_code") or ""),
        country_of_origin=str(extracted_data.get("country_of_origin") or ("India" if not is_imported else "")),
        net_quantity_value=float(extracted_data.get("net_quantity_value") or 0.0),
        net_quantity_unit=str(extracted_data.get("net_quantity_unit") or ""),
        mrp=float(extracted_data.get("mrp") or 0.0),
        fssai_number=str(extracted_data.get("fssai_number") or ""),
        consumer_care_phone=str(extracted_data.get("consumer_care_phone") or ""),
        consumer_care_email=str(extracted_data.get("consumer_care_email") or ""),
        barcode_gtin=str(extracted_data.get("barcode_gtin") or "")
    )
    db.add(product)

    # 10. Update Scan record
    scan.status = ScanStatus.DONE
    scan.verdict = evaluation.verdict
    scan.compliance_score = evaluation.compliance_score
    scan.avg_ocr_confidence = combined_metadata.get("avg_confidence", 0.0)
    scan.processing_time_ms = int((time.time() - start_time) * 1000)

    await db.commit()

    return {
        "id": str(scan.id),
        "scan_id": str(scan.id),
        "status": scan.status.value,
        "verdict": scan.verdict.value,
        "compliance_score": scan.compliance_score,
        "processing_time_ms": scan.processing_time_ms
    }


@router.get("/{scan_id}")
async def get_scan_details(scan_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Retrieve full scan details, extracted fields, violations, and confidence distribution."""
    stmt = (
        select(Scan)
        .where(Scan.id == scan_id)
        .options(
            selectinload(Scan.extracted_fields),
            selectinload(Scan.violations),
            selectinload(Scan.product),
            selectinload(Scan.field_overrides),
        )
    )
    res = await db.execute(stmt)
    scan = res.scalar_one_or_none()

    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")

    # Compute Recharts pie chart distribution per §7.2
    # Slices: High (≥90%), Medium (75–89%), Low (<75%), Not detected
    high_fields = []
    med_fields = []
    low_fields = []

    for f in scan.extracted_fields:
        c = float(f.confidence or 0.0)
        label = f.field_key.replace("_", " ").title()
        if c >= 90.0:
            high_fields.append(label)
        elif c >= 75.0:
            med_fields.append(label)
        else:
            low_fields.append(label)

    confidence_pie = [
        {"name": "High (≥90%)", "value": len(high_fields), "fields": high_fields, "color": "#16A34A"},
        {"name": "Medium (75–89%)", "value": len(med_fields), "fields": med_fields, "color": "#0E7490"},
        {"name": "Low (<75%)", "value": len(low_fields), "fields": low_fields, "color": "#D97706"},
    ]

    return {
        "id": str(scan.id),
        "scan_id": str(scan.id),
        "status": scan.status.value,
        "verdict": scan.verdict.value if scan.verdict else None,
        "compliance_score": float(scan.compliance_score or 0.0),
        "avg_ocr_confidence": float(scan.avg_ocr_confidence or 0.0),
        "processing_time_ms": scan.processing_time_ms,
        "category": scan.category,
        "package_type": scan.package_type,
        "created_at": scan.created_at.isoformat(),
        "product": {
            "name": scan.product.product_name if scan.product else "N/A",
            "brand": scan.product.brand if scan.product else "",
            "manufacturer_name": scan.product.manufacturer_name if scan.product else "",
            "manufacturer_address": scan.product.manufacturer_address if scan.product else "",
            "pin_code": scan.product.pin_code if scan.product else "",
            "net_quantity": f"{scan.product.net_quantity_value} {scan.product.net_quantity_unit}" if scan.product else "",
            "mrp": f"Rs. {scan.product.mrp}" if scan.product else "",
            "fssai_number": scan.product.fssai_number if scan.product else "",
            "consumer_care_phone": scan.product.consumer_care_phone if scan.product else "",
            "consumer_care_email": scan.product.consumer_care_email if scan.product else "",
            "barcode_gtin": scan.product.barcode_gtin if scan.product else "",
        } if scan.product else None,
        "extracted_fields": [
            {
                "id": str(f.id),
                "field_key": f.field_key,
                "field_value": f.field_value,
                "confidence": float(f.confidence or 0.0),
                "bbox": f.bbox,
                "status": f.status.value,
            }
            for f in scan.extracted_fields
        ],
        "violations": [
            {
                "id": str(v.id),
                "field_key": v.field_key,
                "severity": v.severity.value,
                "message_en": v.message_en,
                "message_hi": v.message_hi,
                "suggested_fix": v.suggested_fix,
                "rule_ref": f"rule-{v.field_key.replace('_', '-')}"
            }
            for v in scan.violations
        ],
        "field_overrides": [
            {
                "field_key": o.field_key,
                "old_value": o.old_value,
                "new_value": o.new_value,
                "reason": o.reason,
                "created_at": o.created_at.isoformat()
            }
            for o in scan.field_overrides
        ],
        "confidence_pie": confidence_pie,
        "disclaimer": "Verify against the physical package before issuing any notice."
    }


@router.get("")
async def list_scans(
    request: Request,
    page: int = Query(1, ge=1),
    size: int = Query(25, ge=1, le=100),
    verdict: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Paginated list of scans with filtering per §7.6 & §7.7.

    Authentication required. Inspectors see only their own scans;
    Senior Officers and Admins see everything.
    """
    offset = (page - 1) * size
    stmt = select(Scan).options(selectinload(Scan.product))

    if verdict:
        stmt = stmt.where(Scan.verdict == Verdict(verdict.upper()))
    if category:
        stmt = stmt.where(Scan.category.ilike(f"%{category}%"))

    # Data isolation: inspectors see only their own scans; admins/senior officers see all.
    sees_all = current_user.role.value in ("ADMIN", "SENIOR_OFFICER")
    if not sees_all:
        stmt = stmt.where(Scan.user_id == current_user.id)

    stmt = stmt.order_by(desc(Scan.created_at)).offset(offset).limit(size)
    res = await db.execute(stmt)
    scans = res.scalars().all()

    # Total count (mirror the same visibility filter)
    count_stmt = select(func.count(Scan.id))
    if not sees_all:
        count_stmt = count_stmt.where(Scan.user_id == current_user.id)
    if verdict:
        count_stmt = count_stmt.where(Scan.verdict == Verdict(verdict.upper()))
    total = (await db.execute(count_stmt)).scalar() or 0

    items = []
    for s in scans:
        items.append({
            "id": str(s.id),
            "created_at": s.created_at.isoformat(),
            "verdict": s.verdict.value if s.verdict else "NEEDS_REVIEW",
            "compliance_score": float(s.compliance_score or 0.0),
            "avg_ocr_confidence": float(s.avg_ocr_confidence or 0.0),
            "product_name": s.product.product_name if s.product else "Pre-packaged Item",
            "manufacturer_name": s.product.manufacturer_name if s.product else "N/A",
            "category": s.category or "General",
            "processing_time_ms": s.processing_time_ms
        })

    return {
        "items": items,
        "total": total,
        "page": page,
        "size": size,
        "pages": (total + size - 1) // size
    }


@router.patch("/{scan_id}/fields/{field_key}")
async def override_field(
    scan_id: uuid.UUID,
    field_key: str,
    payload: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Inspector manual override ('Mark as correct' / 'Correct this value') per §7.3.

    Authentication required; overrides are attributed to the signed-in inspector.
    """
    new_value = payload.get("new_value")
    reason = payload.get("reason", "Manual inspector verification against physical sample")

    # Find the extracted field
    stmt = select(ExtractedField).where(
        ExtractedField.scan_id == scan_id,
        ExtractedField.field_key == field_key
    )
    res = await db.execute(stmt)
    field = res.scalar_one_or_none()

    if not field:
        raise HTTPException(status_code=404, detail=f"Field '{field_key}' not found in scan")

    old_value = field.field_value
    field.field_value = str(new_value)
    field.status = Verdict.COMPLIANT
    field.confidence = 100.0

    # Log override
    override = FieldOverride(
        scan_id=scan_id,
        field_key=field_key,
        old_value=old_value,
        new_value=str(new_value),
        reason=reason,
        overridden_by=current_user.id,
        created_at=datetime.utcnow()
    )
    db.add(override)

    # Recompute scan verdict
    all_fields_res = await db.execute(
        select(ExtractedField).where(ExtractedField.scan_id == scan_id)
    )
    all_fields = all_fields_res.scalars().all()
    
    non_comp = [f for f in all_fields if f.status == Verdict.NON_COMPLIANT]
    needs_rev = [f for f in all_fields if f.status == Verdict.NEEDS_REVIEW]
    comp = [f for f in all_fields if f.status == Verdict.COMPLIANT]

    scan_res = await db.execute(select(Scan).where(Scan.id == scan_id))
    scan = scan_res.scalar_one()

    if len(non_comp) > 0:
        scan.verdict = Verdict.NON_COMPLIANT
    elif len(needs_rev) > 0:
        scan.verdict = Verdict.NEEDS_REVIEW
    else:
        scan.verdict = Verdict.COMPLIANT

    scan.compliance_score = (len(comp) / max(1, len(all_fields))) * 100.0
    await db.commit()

    return {
        "status": "overridden",
        "field_key": field_key,
        "new_value": new_value,
        "new_verdict": scan.verdict.value,
        "new_compliance_score": scan.compliance_score
    }


@router.delete("/{scan_id}")
async def delete_scan(
    scan_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete scan attempt (authenticated users only; admins or owning inspectors)."""
    stmt = select(Scan).where(Scan.id == scan_id)
    res = await db.execute(stmt)
    scan = res.scalar_one_or_none()
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    if scan.user_id and scan.user_id != current_user.id and current_user.role.value != "ADMIN":
        raise HTTPException(status_code=403, detail="Not authorized to delete this scan")
    await db.delete(scan)
    await db.commit()
    return {"status": "deleted", "scan_id": str(scan_id)}
