"""PDF Generation Service for CODE MAZE Legal Metrology Compliance Reports.
Uses PyMuPDF (fitz) to generate crisp, professional, government-grade PDF reports.
Includes CODEMAZE header, report metadata, product details, extracted declarations,
violations table with rule citations, OCR confidence summary, and physical verification disclaimer.
"""

import os
import uuid
import fitz  # PyMuPDF
from datetime import datetime
from typing import Dict, Any, List, Optional


def generate_compliance_pdf(
    report_data: Dict[str, Any],
    output_path: str,
    logo_path: Optional[str] = None,
    image_paths: Optional[List[str]] = None,
) -> str:
    """Generate a formal compliance report PDF.
    Returns absolute path of generated PDF file.
    """
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)  # A4 size in points (72 pt/inch)
    
    # Palette constants
    NAVY = (0.07, 0.21, 0.36)       # #12355B
    TEAL = (0.05, 0.45, 0.56)       # #0E7490
    BG_LIGHT = (0.97, 0.98, 0.99)   # #F8FAFC
    CARD_BORDER = (0.88, 0.91, 0.94) # #E2E8F0
    TEXT_DARK = (0.09, 0.13, 0.20)  # #172033
    TEXT_MUTED = (0.40, 0.45, 0.55) # #64748B
    
    verdict = report_data.get("verdict", "NEEDS_REVIEW")
    if verdict == "COMPLIANT":
        VERDICT_COLOR = (0.09, 0.64, 0.29)  # Green #16A34A
    elif verdict == "NON_COMPLIANT":
        VERDICT_COLOR = (0.86, 0.15, 0.15)  # Red #DC2626
    else:
        VERDICT_COLOR = (0.85, 0.47, 0.02)  # Orange #D97706

    # Header Bar (Navy)
    header_rect = fitz.Rect(0, 0, 595, 75)
    page.draw_rect(header_rect, color=NAVY, fill=NAVY)

    # Header Text
    page.insert_text((30, 36), "CODE MAZE", fontsize=18, color=(1, 1, 1), fontname="helv")
    page.insert_text((30, 54), "LEGAL METROLOGY (PACKAGED COMMODITIES) COMPLIANCE REPORT", fontsize=9, color=(0.8, 0.9, 1), fontname="helv")

    # Insert Logo if provided
    if logo_path and os.path.exists(logo_path):
        try:
            logo_rect = fitz.Rect(525, 12, 575, 62)
            page.insert_image(logo_rect, filename=logo_path)
        except Exception:
            pass

    # Meta Info Bar
    rep_num = report_data.get("report_number", f"CMD-{datetime.utcnow().strftime('%Y%m%d')}-001")
    gen_at = report_data.get("generated_at", datetime.utcnow().strftime("%d-%b-%Y %H:%M UTC"))
    inspector = report_data.get("inspector_name", "Officer on Duty (Guest)")
    score = report_data.get("compliance_score", 0.0)
    avg_conf = report_data.get("avg_ocr_confidence", 0.0)

    meta_rect = fitz.Rect(30, 85, 565, 125)
    page.draw_rect(meta_rect, color=CARD_BORDER, fill=BG_LIGHT)

    page.insert_text((42, 102), f"Report No: {rep_num}", fontsize=10, color=TEXT_DARK, fontname="helv")
    page.insert_text((42, 117), f"Date & Time: {gen_at}", fontsize=9, color=TEXT_MUTED, fontname="helv")

    page.insert_text((240, 102), f"Inspector: {inspector}", fontsize=10, color=TEXT_DARK, fontname="helv")
    page.insert_text((240, 117), f"Ruleset: LM (PC) Rules, 2011 (as amended)", fontsize=9, color=TEXT_MUTED, fontname="helv")

    # Verdict Badge Box
    v_box = fitz.Rect(435, 92, 555, 118)
    page.draw_rect(v_box, color=VERDICT_COLOR, fill=VERDICT_COLOR)
    page.insert_text((445, 108), f"VERDICT: {verdict}", fontsize=9, color=(1, 1, 1), fontname="helv")

    # Product Summary Card
    curr_y = 145
    page.insert_text((30, curr_y), "1. PRODUCT SUMMARY & SCORE", fontsize=12, color=NAVY, fontname="helv")
    curr_y += 12

    card1 = fitz.Rect(30, curr_y, 565, curr_y + 60)
    page.draw_rect(card1, color=CARD_BORDER, fill=(1, 1, 1))

    prod_name = report_data.get("product_name", "Pre-packaged Commodity")
    mfg_name = report_data.get("manufacturer_name", "Not Detected / Missing")
    category = report_data.get("category", "General Retail").capitalize()

    page.insert_text((42, curr_y + 20), f"Product Name: {prod_name}", fontsize=10, color=TEXT_DARK, fontname="helv")
    page.insert_text((42, curr_y + 36), f"Manufacturer: {mfg_name[:45]}", fontsize=9, color=TEXT_MUTED, fontname="helv")
    page.insert_text((42, curr_y + 50), f"Category: {category}", fontsize=9, color=TEXT_MUTED, fontname="helv")

    page.insert_text((350, curr_y + 24), f"Compliance Score: {score:.1f}%", fontsize=11, color=TEAL, fontname="helv")
    page.insert_text((350, curr_y + 42), f"Avg OCR Confidence: {avg_conf:.1f}%", fontsize=10, color=TEXT_MUTED, fontname="helv")

    curr_y += 80

    # Violations Section
    page.insert_text((30, curr_y), "2. STATUTORY VIOLATIONS & NON-COMPLIANCES", fontsize=12, color=NAVY, fontname="helv")
    curr_y += 14

    violations: List[Dict[str, Any]] = report_data.get("violations", [])
    if not violations:
        no_v_rect = fitz.Rect(30, curr_y, 565, curr_y + 30)
        page.draw_rect(no_v_rect, color=(0.7, 0.9, 0.8), fill=(0.94, 0.99, 0.95))
        page.insert_text((45, curr_y + 19), "✓ No statutory violations identified on scanned declarations.", fontsize=10, color=(0.09, 0.6, 0.25), fontname="helv")
        curr_y += 45
    else:
        for v in violations[:5]:  # fit top violations on page 1
            v_h = 42
            v_box = fitz.Rect(30, curr_y, 565, curr_y + v_h)
            page.draw_rect(v_box, color=(0.9, 0.8, 0.8), fill=(0.99, 0.95, 0.95))
            
            rule_ref = v.get("rule_ref", "LM Rule")
            msg = v.get("message_en", "Violation detected")
            fix = v.get("suggested_fix", "")
            
            page.insert_text((40, curr_y + 15), f"• Violation under {rule_ref.upper()}:", fontsize=9, color=VERDICT_COLOR, fontname="helv")
            page.insert_text((40, curr_y + 27), f"  {msg[:95]}", fontsize=8.5, color=TEXT_DARK, fontname="helv")
            if fix:
                page.insert_text((40, curr_y + 38), f"  Corrective Action: {fix[:90]}", fontsize=8, color=TEAL, fontname="helv")
            
            curr_y += v_h + 6

    # Extracted Declarations Table
    curr_y += 10
    page.insert_text((30, curr_y), "3. EXTRACTED MANDATORY DECLARATIONS", fontsize=12, color=NAVY, fontname="helv")
    curr_y += 14

    # Table Header
    th_rect = fitz.Rect(30, curr_y, 565, curr_y + 20)
    page.draw_rect(th_rect, color=CARD_BORDER, fill=BG_LIGHT)
    page.insert_text((38, curr_y + 14), "Mandatory Field (Rule 6)", fontsize=8.5, color=NAVY, fontname="helv")
    page.insert_text((195, curr_y + 14), "Extracted Value", fontsize=8.5, color=NAVY, fontname="helv")
    page.insert_text((390, curr_y + 14), "Confidence", fontsize=8.5, color=NAVY, fontname="helv")
    page.insert_text((475, curr_y + 14), "Field Status", fontsize=8.5, color=NAVY, fontname="helv")
    curr_y += 20

    fields = report_data.get("extracted_fields", [])
    for f in fields[:10]:
        row_rect = fitz.Rect(30, curr_y, 565, curr_y + 18)
        page.draw_rect(row_rect, color=CARD_BORDER, fill=(1, 1, 1))

        f_key = str(f.get("field_key", "")).replace("_", " ").title()
        f_val = str(f.get("field_value", "Not Detected"))[:32]
        f_conf = f.get("confidence", 0.0)
        f_stat = str(f.get("status", "NEEDS_REVIEW"))

        page.insert_text((38, curr_y + 12), f_key[:24], fontsize=8, color=TEXT_DARK, fontname="helv")
        page.insert_text((195, curr_y + 12), f_val, fontsize=8, color=TEXT_DARK, fontname="helv")
        page.insert_text((390, curr_y + 12), f"{f_conf:.1f}%", fontsize=8, color=TEXT_MUTED, fontname="helv")

        st_color = (0.09, 0.64, 0.29) if f_stat == "COMPLIANT" else ((0.86, 0.15, 0.15) if f_stat == "NON_COMPLIANT" else (0.85, 0.47, 0.02))
        page.insert_text((475, curr_y + 12), f_stat, fontsize=8, color=st_color, fontname="helv")

        curr_y += 18

    # Statutory Disclaimer Block per §3
    disc_y = 745
    disc_rect = fitz.Rect(30, disc_y, 565, disc_y + 40)
    page.draw_rect(disc_rect, color=(0.85, 0.88, 0.92), fill=BG_LIGHT)
    page.insert_text(
        (40, disc_y + 16),
        "MANDATORY LEGAL DISCLAIMER: Verify against the physical package before issuing any notice.",
        fontsize=8.5, color=TEXT_DARK, fontname="helv"
    )
    page.insert_text(
        (40, disc_y + 30),
        "Generated deterministically by CODE MAZE compliance engine. All rule text quoted from the Legal Metrology Rules, 2011.",
        fontsize=7.5, color=TEXT_MUTED, fontname="helv"
    )

    # Signature Block
    sig_y = 795
    page.insert_text((40, sig_y), "Inspector Signature: _______________________", fontsize=8.5, color=TEXT_DARK, fontname="helv")
    page.insert_text((380, sig_y), "Official Seal / Verification Stamp", fontsize=8.5, color=TEXT_MUTED, fontname="helv")

    # Save PDF
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    doc.save(output_path)
    doc.close()
    return output_path
