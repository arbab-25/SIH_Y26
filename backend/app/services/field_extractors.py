"""Deterministic field extractors using Regex and RapidFuzz per §3 & §8.
Extracts:
- Brand, Product Name, Generic Name
- Net Quantity (value + SI unit) & detect vague quantity words
- Maximum Retail Price (MRP) & check tax qualification
- Month and Year of manufacture / packing / import
- Manufacturer / Packer / Importer name, address, and 6-digit PIN
- Consumer Care contact (Phone, Email, Address)
- FSSAI License Number (14-digits) & Food attributes
- Country of Origin
- Barcode / GTIN
"""

import re
from typing import Dict, Any, List, Optional
from rapidfuzz import fuzz, process


class ExtractedData:
    def __init__(self):
        self.fields: Dict[str, Dict[str, Any]] = {}

    def set_field(
        self,
        key: str,
        value: Any,
        confidence: float,
        bbox: Optional[list] = None,
        source_text: Optional[str] = None
    ):
        self.fields[key] = {
            "value": value,
            "confidence": round(confidence, 2),
            "bbox": bbox,
            "source_text": source_text
        }

    def get(self, key: str, default=None):
        return self.fields.get(key, {}).get("value", default)

    def to_dict(self) -> Dict[str, Any]:
        return self.fields


def _rebuild_display_lines(items: List[Any], fallback_lines: List[str]) -> List[str]:
    """Reconstruct visual text lines from OCR items.

    OCR engines often emit word-level items. Joining raw item texts with newlines
    breaks every line-aware regex (e.g. 'Best Before: 6 months' becomes
    'Best\\nBefore:\\n6'). Group items into lines by vertical box overlap when
    bboxes are available; otherwise fall back to the provided raw lines.
    """
    boxed = [it for it in items if getattr(it, "bbox", None) and len(it.bbox) >= 4]

    def _bbox_sig(b) -> tuple:
        """Flatten any bbox shape (flat [x,y,w,h] or polygon [[x,y],...]) into
        a hashable float signature."""
        try:
            out: List[float] = []
            stack = list(b)
            while stack:
                v = stack.pop(0)
                if isinstance(v, (int, float)):
                    out.append(float(v))
                else:
                    stack = list(v) + stack
            return tuple(out)
        except (TypeError, ValueError):
            return ()

    sigs = {_bbox_sig(it.bbox) for it in boxed}
    # Degenerate case: no geometry at all, or every item shares the same bbox
    # (word-level test mocks). Merge the words into ONE space-joined line so
    # sentence-level regexes still see 'Best Before: 6 months from packaging'
    # instead of 'Best\nBefore:\n6'.
    if not boxed or (sigs != {()} and len(sigs) < max(2, len(boxed) // 3)):
        merged = " ".join((it.text or "").strip() for it in items if (it.text or "").strip())
        if merged and not full_multiline_source(fallback_lines):
            return [merged]
        return fallback_lines or ([merged] if merged else [])
    if len(boxed) < 2:
        return fallback_lines or [it.text for it in items]

    def _bbox_y_h(b) -> tuple:
        """Return (top_y, height) for any bbox shape: flat [x,y,w,h] or
        polygon [[x,y],...]. Used only for line grouping, so approximations
        are acceptable."""
        try:
            flat: List[float] = []
            stack = list(b)
            while stack:
                v = stack.pop(0)
                if isinstance(v, (int, float)):
                    flat.append(float(v))
                else:
                    stack = list(v) + stack
            if len(flat) >= 8:  # polygon: x1,y1,x2,y2,...
                ys = flat[1::2]
                return min(ys), max(ys) - min(ys)
            if len(flat) >= 4:  # flat [x, y, w, h]
                return flat[1], flat[3]
        except (TypeError, ValueError):
            pass
        return 0.0, 0.0

    sorted_items = sorted(boxed, key=lambda it: _bbox_y_h(it.bbox)[0])
    lines_out: List[str] = []
    current: List[str] = []
    current_y = None
    for it in sorted_items:
        y, h = _bbox_y_h(it.bbox)
        if current_y is not None and abs(y - current_y) > max(10.0, float(h) * 0.7):
            lines_out.append(" ".join(current))
            current = []
        current.append(it.text)
        current_y = y
    if current:
        lines_out.append(" ".join(current))
    lines_out = [l.strip() for l in lines_out if l and l.strip()]
    return lines_out or fallback_lines or [it.text for it in items]


def full_multiline_source(lines: List[str]) -> bool:
    """True when the fallback lines already look like real multi-word lines."""
    return any(len(l.split()) >= 3 for l in lines)


def extract_fields_from_ocr(items: List[Any], full_text: Optional[str] = None) -> ExtractedData:
    """Extract structured product declarations from OCR items."""
    data = ExtractedData()

    if not items:
        return data

    # Rebuild visual lines first — every downstream regex depends on sane lines.
    raw_lines = [item.text for item in items]
    text_lines = _rebuild_display_lines(items, raw_lines)
    combined_text = full_text if full_text else "\n".join(text_lines)

    # ----------------------------------------------------
    # 1. FSSAI License Number (14 digits)
    # ----------------------------------------------------
    fssai_match = re.search(r"(?:lic(?:ence)?(?:\s*no\.?)?|fssai(?:\s*no\.?)?)[^\d]*(\d{14})\b", combined_text, re.IGNORECASE)
    if not fssai_match:
        # Standalone 14-digit sequence
        fssai_match = re.search(r"\b(1\d{13})\b", combined_text)

    if fssai_match:
        fssai_num = fssai_match.group(1)
        # Find corresponding OCR item for confidence and bbox
        best_item = max(
            (it for it in items if fssai_num in it.text or "fssai" in it.text.lower() or "lic" in it.text.lower()),
            key=lambda x: x.confidence,
            default=items[0]
        )
        data.set_field("fssai_number", fssai_num, best_item.confidence, best_item.bbox, best_item.text)

    # ----------------------------------------------------
    # 2. Manufacturer Name & Address & PIN Code (Rule 10(1))
    # ----------------------------------------------------
    mfg_keywords = ["manufactured by", "mfd by", "packed by", "pkd by", "mktd by", "marketed by"]
    mfg_found = False
    for i, line in enumerate(text_lines):
        line_lower = line.lower()
        matched_kw = next((kw for kw in mfg_keywords if kw in line_lower), None)
        if matched_kw:
            mfg_found = True
            mfg_header_item = items[i]
            # Name = text after the keyword on the same line ("Marketed by: ACME Ltd")
            # else the following line; cap length to avoid swallowing the page.
            after_kw = line[re.search(re.escape(matched_kw), line_lower).end():].strip(" :,-")
            mfg_name = after_kw or (text_lines[i + 1] if i + 1 < len(text_lines) else line)
            mfg_name = mfg_name.strip()[:120]
            address_lines = text_lines[i + 2:i + 5] if i + 2 < len(text_lines) else []
            full_address = (", ".join(address_lines) if address_lines else mfg_name)[:200]

            data.set_field("manufacturer_name", mfg_name, mfg_header_item.confidence, mfg_header_item.bbox, line)
            if full_address:
                data.set_field("manufacturer_address", full_address, mfg_header_item.confidence, mfg_header_item.bbox)
            break

    # Look for 6-digit Indian PIN code (cannot start with 0)
    pin_match = re.search(r"\b([1-9]\d{5})\b", combined_text)
    if pin_match:
        pin = pin_match.group(1)
        item_with_pin = next((it for it in items if pin in it.text), items[0])
        data.set_field("pin_code", pin, item_with_pin.confidence, item_with_pin.bbox, item_with_pin.text)

    # ----------------------------------------------------
    # 3. Consumer Care Details (Rule 6(2))
    # ----------------------------------------------------
    # Email
    email_match = re.search(r"([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)", combined_text)
    if email_match:
        email = email_match.group(1).rstrip(".")
        item_email = next((it for it in items if email[:10] in it.text), items[0])
        data.set_field("consumer_care_email", email, item_email.confidence, item_email.bbox, item_email.text)

    # Telephone / Phone
    phone_match = re.search(r"(?:ph(?:one)?|tel|care|call|customer\s*care|no\.?)[^\d+]*(\+?[\d\s\-()]{7,16})", combined_text, re.IGNORECASE)
    if phone_match:
        raw_phone = phone_match.group(1).strip()
        cleaned_phone = re.sub(r"[^\d+]", "", raw_phone)
        if len(cleaned_phone) >= 7:
            item_phone = next((it for it in items if raw_phone[:5] in it.text), items[0])
            data.set_field("consumer_care_phone", raw_phone, item_phone.confidence, item_phone.bbox, item_phone.text)

    # ----------------------------------------------------
    # 4. Maximum Retail Price (MRP) & Tax Qualification (Rule 6(1)(e))
    # ----------------------------------------------------
    mrp_regex = re.compile(
        r"(?:m\.?r\.?p\.?|max(?:imum)?\s*retail\s*price)[^\d₹Rs]*[₹Rs\.]*\s*([0-9]+(?:\.[0-9]{1,2})?)",
        re.IGNORECASE
    )
    mrp_match = mrp_regex.search(combined_text)
    if not mrp_match:
        # Secondary pattern: standalone Rs. XX.XX or ₹ XX.XX
        mrp_match = re.search(r"(?:₹|Rs\.?)\s*([0-9]+(?:\.[0-9]{1,2})?)", combined_text)

    if mrp_match:
        val_str = mrp_match.group(1)
        val = float(val_str)
        # Find item matching MRP
        best_mrp_item = next((it for it in items if val_str in it.text or "mrp" in it.text.lower()), items[0])
        data.set_field("mrp", val, best_mrp_item.confidence, best_mrp_item.bbox, best_mrp_item.text)

        # Check for "inclusive of all taxes" or "incl. of all taxes"
        context_around_mrp = combined_text[max(0, mrp_match.start() - 50):min(len(combined_text), mrp_match.end() + 100)].lower()
        has_taxes = ("incl" in context_around_mrp and "tax" in context_around_mrp) or "inclusive of all taxes" in context_around_mrp
        data.set_field("mrp_inclusive_taxes", has_taxes, best_mrp_item.confidence, best_mrp_item.bbox, context_around_mrp)
    else:
        # Check if the text explicitly states MRP
        for it in items:
            if "mrp" in it.text.lower():
                data.set_field("mrp_detected_text", it.text, it.confidence, it.bbox, it.text)
                break

    # ----------------------------------------------------
    # 5. Net Quantity & Units (Rule 6(1)(c), Rule 12(6), Rule 13)
    # ----------------------------------------------------
    qty_regex = re.compile(
        r"(?:net\s*(?:wt\.?|weight|qty\.?|quantity)|pkd\.?|volume)?\s*([0-9]+(?:\.[0-9]+)?)\s*(kg|g|gm|gms|gram|grams|ml|l|ltr|litre|litres|liter|liters|n|u)\b",
        re.IGNORECASE
    )
    qty_match = qty_regex.search(combined_text)
    if qty_match:
        qty_val = float(qty_match.group(1))
        unit = qty_match.group(2).lower()
        best_qty_item = next((it for it in items if qty_match.group(1) in it.text and unit in it.text.lower()), items[0])
        data.set_field("net_quantity_value", qty_val, best_qty_item.confidence, best_qty_item.bbox, best_qty_item.text)
        data.set_field("net_quantity_unit", unit, best_qty_item.confidence, best_qty_item.bbox, best_qty_item.text)

    # Check for prohibited vague quantity words (Rule 12(6))
    vague_words = ["minimum", "not less than", "average", "about", "approximately"]
    for vw in vague_words:
        if vw in combined_text.lower():
            vague_item = next((it for it in items if vw in it.text.lower()), items[0])
            data.set_field("vague_quantity_found", vw, vague_item.confidence, vague_item.bbox, vague_item.text)
            break

    # ----------------------------------------------------
    # 6. Date of Manufacture / Packing / Import (Rule 6(1)(d))
    # ----------------------------------------------------
    # Pass 1 (keyword-anchored): a date line explicitly labelled mfd/mfg/pkd/
    # manufactured/imported — prevents picking the Best-Before date or barcode
    # digits on multi-date labels like 'MFG 05/2026 BB 05/2027'.
    date_match = None
    for line in text_lines:
        line_match = re.search(
            r"\b(?:mfd|mfg|mkd|pkd|packed|packaged|manufactured|manf|imported)\b[^0-9a-z]{0,12}"
            r"((?:0?[1-9]|1[0-2])[/\-.](?:20)?\d{2}|"
            r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*[/\-. \\] \s*(?:20)?\d{2,4}|"
            r"(?:20)?\d{2}[/\-.](?:0?[1-9]|1[0-2]))",
            line,
            re.IGNORECASE,
        )
        if line_match:
            date_match = line_match
            break

    # Pass 2 (fallback): any plausible month/year token anywhere on the label
    # (kept for bare panels where the keyword was OCR-mangled).
    if not date_match:
        date_match = re.search(
            r"\b((?:0?[1-9]|1[0-2])[/\-.](?:20)?\d{2}\b|\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*[\s/\.-]+(?:20)?\d{2}\b)",
            combined_text,
            re.IGNORECASE,
        )

    if date_match:
        raw_date = date_match.group(1)
        item_date = next((it for it in items if raw_date in it.text), items[0])
        data.set_field("mfg_date_str", raw_date, item_date.confidence, item_date.bbox, item_date.text)

    # Best before / use by date (Rule 6(1)(da))
    # Terminators: line end or the start of the next declaration, so merged
    # single-line OCR text never leaks neighbouring declarations into the value.
    bb_regex = re.compile(
        r"(?:best\s*before|use\s*by|expiry|exp\.?)\s*[:\-.]?\s*"
        r"(.+?)(?=\n|$|,|;|\bb(?:est)?\s*before\b|\buse\s*by\b|\bmfd\b|\bmfg\b|\bmrp\b|\bnet\b|\bbatch\b|\blot\b|\bmarketed\b|\bmanufactured\b|\bfssai\b)",
        re.IGNORECASE
    )
    bb_match = bb_regex.search(combined_text)
    if bb_match:
        # Stop at line/segment boundaries and strip page-junk so we never store
        # values like "6 monthsfrom packaging\nMa" from adjacent OCR lines.
        bb_text = bb_match.group(1).strip().split("\n")[0].strip(" \t.,;:-")
        # Walk forward in the combined text to grab the remainder of this line
        # (e.g. "6 months from packaging") that the bounded regex may cut off.
        tail_start = bb_match.end(1)
        next_nl = combined_text.find("\n", tail_start)
        if next_nl == -1:
            next_nl = len(combined_text)
        extra = combined_text[tail_start:next_nl].strip()
        if extra and re.match(r"^[a-zA-Z0-9 ,./-]+$", extra) and len(extra) <= 30:
            bb_text = (bb_text + " " + extra).strip()
        # Prefer a matching OCR item on the SAME line as the matched text
        bb_first_word = bb_text.split()[0] if bb_text.split() else ""
        item_bb = next(
            (it for it in items if bb_first_word and bb_first_word.lower() in it.text.lower()),
            items[0]
        )
        data.set_field("best_before", bb_text, item_bb.confidence, item_bb.bbox, item_bb.text)

    # ----------------------------------------------------
    # 7. Country of Origin (Rule 6(1)(aa))
    # ----------------------------------------------------
    origin_regex = re.compile(
        r"(?:country\s*of\s*origin|made\s*in|product\s*of)\s*[:\-.]?\s*([a-zA-Z\s]{3,30})",
        re.IGNORECASE
    )
    origin_match = origin_regex.search(combined_text)
    if origin_match:
        country = origin_match.group(1).strip()
        item_origin = next((it for it in items if "origin" in it.text.lower() or "made in" in it.text.lower()), items[0])
        data.set_field("country_of_origin", country, item_origin.confidence, item_origin.bbox, item_origin.text)

    # ----------------------------------------------------
    # 8. Brand & Product / Generic Name (Rule 6(1)(b))
    # ----------------------------------------------------
    if len(items) > 0:
        # text_lines are already rebuilt visual lines (see top of function).
        header_line = text_lines[0].strip() if text_lines else ""
        # Brand = first line of the label header; product name = header + second
        # line when the second line looks like a product descriptor (not a stat).
        second = text_lines[1].strip() if len(text_lines) > 1 else ""
        looks_like_descriptor = bool(second) and not re.match(
            r"^(net|max|mrp|mfd|mfg|pkd|best|use|batch|lot|marketed|manufactured|country)\b",
            second,
            re.IGNORECASE,
        )
        product_name = f"{header_line} {second}" if looks_like_descriptor and second else header_line

        def _cut_header(line: str, limit: int = 6) -> str:
            """Safety cut: a header that swallowed neighbouring declarations
            (degenerate line grouping) is trimmed at the first declaration
            keyword and capped to a few words."""
            cut = re.split(
                r"\b(net\s*qty|net\b|max\.?\s*retail|mrp|mfd\.?|mfg\.?|pkd|best\s*before|use\s*by|batch|lot|marketed|manufactured|country\s*of|fssai|ingredients)\b",
                line,
                maxsplit=1,
                flags=re.IGNORECASE,
            )[0].strip(" :.,-")
            words = cut.split()
            return " ".join(words[:limit]) if len(words) > limit else cut
        # Attach the confidence of the OCR item(s) that formed the header
        header_words = header_line.split()[:2]
        header_items = [it for it in items if any(w and w.lower() in (it.text or "").lower() for w in header_words)]
        hdr_conf = max((it.confidence for it in header_items), default=items[0].confidence)
        brand_name = _cut_header(header_line)
        product_cut = _cut_header(product_name)
        data.set_field("brand", brand_name or "", hdr_conf if brand_name else 0.0, items[0].bbox, header_line)
        data.set_field("product_name", product_cut or "", hdr_conf if product_cut else 0.0, items[0].bbox, header_line)

    # ----------------------------------------------------
    # 9. Ingredients & Nutritional Facts (FSSAI / Food articles)
    # ----------------------------------------------------
    if "ingredients" in combined_text.lower():
        ing_item = next((it for it in items if "ingredients" in it.text.lower()), items[0])
        data.set_field("ingredients_declared", True, ing_item.confidence, ing_item.bbox, ing_item.text)

    if any(term in combined_text.lower() for term in ["nutritional", "nutrition facts", "nutririon", "calories", "energy"]):
        nut_item = next((it for it in items if any(k in it.text.lower() for k in ["nutrition", "energy", "calories"])), items[0])
        data.set_field("nutritional_info_declared", True, nut_item.confidence, nut_item.bbox, nut_item.text)

    # ----------------------------------------------------
    # 10. Barcode / GTIN
    # ----------------------------------------------------
    # Check for 13 or 14-digit GTIN / EAN barcode numbers
    gtin_match = re.search(r"\b([0-9]{13,14})\b", combined_text)
    if gtin_match and (not fssai_match or gtin_match.group(1) != fssai_match.group(1)):
        gtin = gtin_match.group(1)
        item_gtin = next((it for it in items if gtin in it.text), items[0])
        data.set_field("barcode_gtin", gtin, item_gtin.confidence, item_gtin.bbox, item_gtin.text)

    return data
