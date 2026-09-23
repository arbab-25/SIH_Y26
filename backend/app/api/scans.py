"""Scans API Router — Label Upload, OCR Extraction, Rule Validation, Overrides."""

import os
import re
import uuid
import time
import asyncio
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Request, status, Query
from fastapi import BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, or_
from sqlalchemy.orm import selectinload

from app.database import get_db, async_session_factory
from app.config import settings
from app.models.user import User
from app.models.scan import Scan, ScanStatus, Verdict
from app.models.product import Product
from app.models.extracted_field import ExtractedField
from app.models.rule import Rule
from app.models.violation import Violation, Severity
from app.models.field_override import FieldOverride
from app.api.deps import get_current_user
from app.services.ocr_service import run_ocr
from app.services.field_extractors import (
    extract_fields_from_ocr,
    merge_extracted_fields,
    apply_barcode_crosscheck,
)
from app.services import redis_service
from app.services.rule_engine import evaluate_product_compliance
from app.utils.image_utils import validate_magic_bytes, strip_exif_keep_orientation
from app.utils.rate_limit import check_rate_limit

router = APIRouter(prefix="/scans", tags=["Scans"])


async def _process_scan(
    scan_id: uuid.UUID,
    is_imported: bool = False,
    pdp_height_cm: Optional[float] = None,
    pdp_width_cm: Optional[float] = None,
    measured_glyph_height_mm: Optional[float] = None,
) -> None:
    """Run OCR + extraction + rule evaluation for a queued scan.

    Executed as a FastAPI background task so the upload request returns
    immediately (202). On Render's free tier, running RapidOCR inside the
    request exhausted the 512 MB instance and the proxy answered 502 before
    the worker finished; moving the heavy work out of the request keeps the
    connection short-lived while the inspector polls GET /scans/{id} for the
    outcome.

    Opens its own session (the request's session is closed by then). Every
    failure path marks the scan FAILED with a user-facing error_message —
    the scan row can never be left stuck in PROCESSING with no explanation.
    """
    async with async_session_factory() as db:
        try:
            res = await db.execute(select(Scan).where(Scan.id == scan_id))
            scan = res.scalar_one_or_none()
            if scan is None:
                return

            start_time = time.time()
            scan.status = ScanStatus.PROCESSING
            await db.commit()

            all_ocr_items = []
            combined_metadata = {}
            is_any_blurry = False
            blur_error_msg = None
            per_image_extractions = []
            barcode_candidates = []

            for img_path in scan.image_urls or []:
                try:
                    # run in a worker thread: OCR is CPU-bound and would block
                    # the event loop, stalling every other request on a 1-CPU
                    # instance.
                    items, meta = await asyncio.to_thread(run_ocr, img_path, True)
                    if meta.get("blurry"):
                        is_any_blurry = True
                        blur_error_msg = meta.get("error")
                    if meta.get("error") and not meta.get("blurry"):
                        # Engine-level fault (e.g. ONNX inference failure with no
                        # surviving fallback): fail the scan explicitly rather
                        # than recording a silent zero-field "done".
                        scan.status = ScanStatus.FAILED
                        scan.verdict = Verdict.NEEDS_REVIEW
                        scan.error_message = meta.get("error")
                        scan.processing_time_ms = int((time.time() - start_time) * 1000)
                        await db.commit()
                        return
                    all_ocr_items.extend(items)
                    combined_metadata = meta
                    for bc in (meta.get("barcodes") or {}).get("results", []):
                        if bc.get("data"):
                            barcode_candidates.append(str(bc["data"]))
                    # Extract per photo: items from different photos share one
                    # coordinate space, and merging them before line rebuilding
                    # interleaved text across panels — a best-before value once
                    # picked up prose merged from the neighbouring photo.
                    if items:
                        per_image_extractions.append(extract_fields_from_ocr(items))
                except Exception as e:
                    print(f"[WARN] OCR failed for {img_path}: {e}")

            # Barcode cross-check (Rule 6(4A)(a)): a machine-decoded barcode is
            # authoritative. See apply_barcode_crosscheck for the fail-closed
            # confirm / mismatch / fill branches (§3).
            barcode_meta_out = None
            if barcode_candidates:
                decoded = next(
                    (c for c in barcode_candidates if re.fullmatch(r"\d{8,14}", c)),
                    None,
                )
                if decoded:
                    outcome = apply_barcode_crosscheck(extracted_data, decoded)
                    barcode_meta_out = {"source": "pyzbar", **outcome}
                    print(f"[INFO] Barcode cross-check: {outcome}")

            if barcode_meta_out:
                extracted_dict = extracted_data.to_dict()
                scan.scan_meta = {
                    **(scan.scan_meta or {}),
                    "barcode": barcode_meta_out,
                }

            if is_any_blurry and len(all_ocr_items) < 5:
                scan.status = ScanStatus.FAILED
                scan.verdict = Verdict.NEEDS_REVIEW
                scan.error_message = blur_error_msg or (
                    "We couldn't read this label clearly. Please move closer, "
                    "hold steady, and retake the photo."
                )
                scan.processing_time_ms = int((time.time() - start_time) * 1000)
                await db.commit()
                return

            extracted_data = merge_extracted_fields(per_image_extractions)
            extracted_dict = extracted_data.to_dict()

            evaluation = evaluate_product_compliance(
                extracted_data=extracted_dict,
                category=scan.category,
                package_type=scan.package_type,
                is_imported=is_imported,
                pdp_height_cm=pdp_height_cm,
                pdp_width_cm=pdp_width_cm,
                measured_glyph_height_mm=measured_glyph_height_mm,
            )

            ENGINE_FIELD_ALIASES = {
                "manufacturer_name": "manufacturer",
                "manufacturer_address": "manufacturer",
                "pin_code": "manufacturer",
                "product_name": "product_name",
                "net_quantity_value": "net_quantity",
                "net_quantity_unit": "net_quantity",
                "vague_quantity_found": "net_quantity_qualifiers",
                "mrp": "mrp",
                "mrp_inclusive_taxes": "mrp",
                "mfg_date_str": "mfg_date",
                "best_before": "best_before",
                "fssai_number": "fssai_license",
                "ingredients_declared": "ingredients_list",
                "nutritional_info_declared": "nutritional_information",
                "country_of_origin": "country_of_origin",
            }
            DISPLAY_ONLY_FIELDS = {"brand", "mrp_detected_text", "barcode_gtin"}

            for key, item in extracted_dict.items():
                engine_field = ENGINE_FIELD_ALIASES.get(key)
                matching_res = next((r for r in evaluation.results if r.field == engine_field), None) if engine_field else None
                conf_pct = float(item.get("confidence", 0) or 0)
                if conf_pct <= 1.0:
                    conf_pct *= 100.0
                if matching_res is not None:
                    f_status = matching_res.status
                elif key in DISPLAY_ONLY_FIELDS or conf_pct >= 75:
                    f_status = Verdict.COMPLIANT
                else:
                    f_status = Verdict.NEEDS_REVIEW
                ef = ExtractedField(
                    scan_id=scan_id,
                    field_key=key,
                    field_value=str(v) if (v := item.get("value")) is not None else "",
                    confidence=float(item.get("confidence", 0.0) or 0) * 100 if float(item.get("confidence", 1.0) or 0) <= 1.0 else float(item.get("confidence", 0.0)),
                    bbox=item.get("bbox"),
                    status=f_status
                )
                db.add(ef)

            rule_rows = (await db.execute(select(Rule.id, Rule.rule_number))).all()
            rule_id_by_number = {rule_number: rule_id for rule_id, rule_number in rule_rows}

            for v in evaluation.violations:
                viol = Violation(
                    scan_id=scan_id,
                    field_key=v.field,
                    rule_ref=v.rule_ref,
                    rule_id=rule_id_by_number.get(v.rule_ref),
                    severity=Severity.MAJOR if v.severity == "MAJOR" else Severity.MINOR,
                    message_en=v.message_en,
                    message_hi=v.message_hi,
                    suggested_fix=v.suggested_fix
                )
                db.add(viol)

            def _val(extracted: dict, key: str):
                item = extracted.get(key)
                if not isinstance(item, dict):
                    return None
                return item.get("value")

            nq_value = _val(extracted_dict, "net_quantity_value")
            mrp_value = _val(extracted_dict, "mrp")
            product = Product(
                scan_id=scan_id,
                product_name=str(_val(extracted_dict, "product_name") or "Pre-packaged Commodity"),
                brand=str(_val(extracted_dict, "brand") or ""),
                category=scan.category or "General",
                manufacturer_name=str(_val(extracted_dict, "manufacturer_name") or ""),
                manufacturer_address=str(_val(extracted_dict, "manufacturer_address") or ""),
                pin_code=str(_val(extracted_dict, "pin_code") or ""),
                country_of_origin=str(_val(extracted_dict, "country_of_origin") or ""),
                net_quantity_value=float(nq_value) if nq_value is not None else None,
                net_quantity_unit=str(_val(extracted_dict, "net_quantity_unit") or ""),
                mrp=float(mrp_value) if mrp_value is not None else None,
                fssai_number=str(_val(extracted_dict, "fssai_number") or ""),
                consumer_care_phone=str(_val(extracted_dict, "consumer_care_phone") or ""),
                consumer_care_email=str(_val(extracted_dict, "consumer_care_email") or ""),
                barcode_gtin=str(_val(extracted_dict, "barcode_gtin") or "")
            )
            db.add(product)

            scan.status = ScanStatus.DONE
            scan.verdict = evaluation.verdict
            scan.compliance_score = evaluation.compliance_score
            if all_ocr_items:
                word_confidences = [
                    item.confidence * 100 if item.confidence <= 1.0 else item.confidence
                    for item in all_ocr_items
                ]
                scan.avg_ocr_confidence = round(sum(word_confidences) / len(word_confidences), 2)
            else:
                scan.avg_ocr_confidence = 0.0
            scan.ocr_engine = combined_metadata.get("engine") or settings.OCR_ENGINE
            scan.processing_time_ms = int((time.time() - start_time) * 1000)
            await db.commit()
        except Exception as exc:
            # Never leave the scan stuck in PROCESSING: record the failure on the
            # row so the poll endpoint can surface it to the inspector.
            await db.rollback()
            try:
                res = await db.execute(select(Scan).where(Scan.id == scan_id))
                scan = res.scalar_one_or_none()
                if scan is not None:
                    scan.status = ScanStatus.FAILED
                    scan.verdict = Verdict.NEEDS_REVIEW
                    scan.error_message = (
                        "Processing failed on the server. Please retry the scan; "
                        "if it keeps failing, use a clearer, well-lit photo."
                    )
                    await db.commit()
            except Exception:
                pass
            print(f"[ERROR] Background scan processing failed for {scan_id}: {exc}")


# Persistent event loop for the RQ worker path: SQLAlchemy async engines bind
# connections to the loop they first connect on, so a fresh loop per job would
# poison the pool. One loop per worker process keeps the engine reusable.
_worker_loop: Optional[asyncio.AbstractEventLoop] = None


def process_scan_sync(scan_id: str, payload: dict) -> dict:
    """Synchronous entry point for RQ workers (app/worker.py).

    Runs the SAME async pipeline the in-process fallback uses, on the worker's
    persistent event loop. The scan row is the single source of truth either
    way, so the polling endpoint needs no knowledge of which side ran.
    """
    global _worker_loop
    if _worker_loop is None or _worker_loop.is_closed():
        _worker_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_worker_loop)
    coro = _process_scan(
        uuid.UUID(scan_id),
        is_imported=bool(payload.get("is_imported", False)),
        pdp_height_cm=payload.get("pdp_height_cm"),
        pdp_width_cm=payload.get("pdp_width_cm"),
        measured_glyph_height_mm=payload.get("measured_glyph_height_mm"),
    )
    return _worker_loop.run_until_complete(coro) or {"status": "done"}


def _val(extracted: dict, key: str):
    """Read the plain value of an extracted field.

    extract_fields_from_ocr() returns a dict-of-dicts: each key maps to
    {"value", "confidence", "bbox", "source_text"}. Persisting code must use
    this helper — a bare extracted.get(key) returns the wrapper dict and any
    float()/str() on it either raises TypeError (500 on every scan) or stores
    "{'value': ...}" garbage in the products table.
    """
    item = extracted.get(key)
    if not isinstance(item, dict):
        return None
    return item.get("value")


@router.post("", status_code=status.HTTP_202_ACCEPTED)
async def create_scan(
    request: Request,
    background_tasks: BackgroundTasks,
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

    # 3. Create Scan record (always owned by the signed-in inspector).
    # The heavy OCR/rule work runs as a background task: on the free deployment
    # tier the synchronous version exhausted the instance mid-request and the
    # proxy returned 502 to the inspector. The request only persists the upload
    # and returns 202 with the scan id; the client polls GET /scans/{id} until
    # status is done or failed.
    scan_id = uuid.uuid4()
    scan = Scan(
        id=scan_id,
        user_id=current_user.id,
        guest_device_id=None,
        image_urls=saved_image_paths,
        package_type=package_type,
        category=category,
        status=ScanStatus.QUEUED,
        ocr_engine=settings.OCR_ENGINE,
        created_at=datetime.utcnow()
    )
    db.add(scan)
    await db.commit()

    # Dispatch: RQ + Redis when configured (OCR runs in a worker process and
    # never occupies the API's event loop); in-process background task as the
    # zero-dependency fallback. The 202 + poll contract is identical either way.
    job_payload = {
        "is_imported": is_imported,
        "pdp_height_cm": pdp_height_cm,
        "pdp_width_cm": pdp_width_cm,
        "measured_glyph_height_mm": measured_glyph_height_mm,
    }
    job_id = redis_service.enqueue_scan_job(str(scan_id), job_payload)
    if job_id is None:
        background_tasks.add_task(
            _process_scan,
            scan_id,
            is_imported,
            pdp_height_cm,
            pdp_width_cm,
            measured_glyph_height_mm,
        )
        dispatch = "in-process"
    else:
        dispatch = "rq"

    return {
        "id": str(scan.id),
        "scan_id": str(scan.id),
        "job_id": job_id,
        "dispatch": dispatch,
        "status": scan.status.value,
        "verdict": None,
        "compliance_score": None,
        "processing_time_ms": None,
        "message": "Scan accepted; poll GET /api/v1/scans/{scan_id} until status is done or failed."
    }


@router.get("/{scan_id}/job")
async def get_scan_job_status(
    scan_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Job-status endpoint for the async pipeline (Phase 2).

    Combines two sources: the RQ job state in Redis (queued/started/finished/
    failed) when the job was dispatched to a worker, and the scans row itself
    (queued/processing/done/failed) which is authoritative for the verdict.
    Authentication and visibility rules match GET /scans/{id}.
    """
    res = await db.execute(select(Scan).where(Scan.id == scan_id))
    scan = res.scalar_one_or_none()
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    if scan.user_id and scan.user_id != current_user.id and current_user.role.value not in ("ADMIN", "SENIOR_OFFICER"):
        raise HTTPException(status_code=403, detail="Not authorized to view this scan")

    rq_status = redis_service.fetch_job_status(f"scan-{scan_id}")
    return {
        "scan_id": str(scan.id),
        "scan_status": scan.status.value,
        "verdict": scan.verdict.value if scan.verdict else None,
        "compliance_score": float(scan.compliance_score) if scan.compliance_score is not None else None,
        "processing_time_ms": scan.processing_time_ms,
        "error_message": scan.error_message,
        "job": rq_status,
        "done": scan.status in (ScanStatus.DONE, ScanStatus.FAILED),
    }


@router.get("/{scan_id}")
async def get_scan_details(
    scan_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Retrieve full scan details, extracted fields, violations, and confidence distribution.

    Authentication required: scan data is enforcement evidence and must never be
    publicly enumerable by UUID guessing. Inspectors see their own scans;
    SENIOR_OFFICER/ADMIN see everything.
    """
    stmt = (
        select(Scan)
        .where(Scan.id == scan_id)
        .options(
            selectinload(Scan.extracted_fields),
            selectinload(Scan.violations).selectinload(Violation.rule),
            selectinload(Scan.product),
            selectinload(Scan.field_overrides),
        )
    )
    res = await db.execute(stmt)
    scan = res.scalar_one_or_none()

    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")

    # Data isolation: a scan is visible to its inspector and to senior officers/admins
    if scan.user_id and scan.user_id != current_user.id and current_user.role.value not in ("ADMIN", "SENIOR_OFFICER"):
        raise HTTPException(status_code=403, detail="Not authorized to view this scan")

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
        "error_message": scan.error_message,
        "category": scan.category,
        "package_type": scan.package_type,
        "created_at": scan.created_at.isoformat(),
        "product": {
            "name": scan.product.product_name if scan.product else "N/A",
            "brand": scan.product.brand if scan.product else "",
            "manufacturer_name": scan.product.manufacturer_name if scan.product else "",
            "manufacturer_address": scan.product.manufacturer_address if scan.product else "",
            "pin_code": scan.product.pin_code if scan.product else "",
            # A zero here means "not detected". Formatting it as "0.0" or "Rs. 0.00"
            # would read as a declared quantity or price of zero on a statutory report.
            "net_quantity": (
                f"{float(scan.product.net_quantity_value):g} {scan.product.net_quantity_unit}".strip()
                if scan.product and float(scan.product.net_quantity_value or 0) > 0 else ""
            ),
            "mrp": (
                f"Rs. {float(scan.product.mrp):.2f}"
                if scan.product and float(scan.product.mrp or 0) > 0 else ""
            ),
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
                # Prefer the persisted cited-rule string; fall back to the linked
                # rules row, then the legacy field-key form for old rows.
                "rule_ref": v.rule_ref
                or (v.rule.rule_number if v.rule else f"rule-{v.field_key.replace('_', '-')}"),
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
