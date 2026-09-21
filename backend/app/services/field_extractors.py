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

from app.utils.regulatory_parsing import is_known_country, parse_relative_period

# OCR engines emit fullwidth punctuation on Indian labels ("Exp.Date\uFF1A01-01-2027"),
# which silently breaks every ASCII-keyed regex. Normalized once, on ingestion.
_FULLWIDTH_MAP = str.maketrans({"\uFF1A": ":", "\uFF0E": ".", "\uFF0C": ",", "\u3000": " "})

# Date-shaped tokens, most specific first: DD-MM-YYYY before MM-YY so a full
# calendar date is never truncated to its prefix (truncating '02-01-2026' to
# '02-01' once displayed the manufacture date as 'Feb 2001'). Dot separators
# are excluded from numeric forms — '2.39' is a nutrition-table decimal, not
# a printed date.
_DATE_TOKEN_RE = re.compile(
    r"(?:\d{1,2}[/\-]\d{1,2}[/\-]\d{4}"
    r"|(?:0?[1-9]|1[0-2])[/\-](?:20)?\d{2}\b"
    r"|\b(?:20)?\d{2}[/\-](?:0?[1-9]|1[0-2])\b"
    r"|(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*[/\-. ]\s*(?:20)?\d{2,4})",
    re.IGNORECASE,
)

_BEST_BEFORE_KEYWORD_RE = re.compile(
    r"\b(best\s*before|use\s*by|exp(?:iry)?\.?|bb)\b", re.IGNORECASE
)


def _plausible_date_token(raw: str) -> bool:
    """True when a date-shaped token is trustworthy WITHOUT a keyword anchor.

    A bare two-digit/two-digit token ('02-01') is too ambiguous to store on
    its own — it could be day-month, month-year or YY-MM — so the fallback
    pass only accepts tokens containing a 4-digit year or a month name.
    """
    parts = re.split(r"[/\-.]", raw)
    if any(p.isdigit() and len(p) == 4 for p in parts):
        return True
    return bool(re.search(r"[A-Za-z]", raw))


def _plausible_bb_value(value: str) -> bool:
    """True when a Best-Before capture is a date or a declared shelf life.

    Guards against storing raw OCR prose: when 'Exp.' matched with nothing
    date-like after it, the old unanchored capture stored sentence text merged
    from an adjacent photo ('Date Basundi Mix maiemoe eicosuse ful oeam mi…')
    and displayed it as the expiry date.
    """
    if not value:
        return False
    if _DATE_TOKEN_RE.search(value):
        return True
    return parse_relative_period(value) is not None

# Declaration keywords that end an address block. Without this, the lines printed
# after the address (e-mail, customer care, licence number) were swallowed into the
# manufacturer address stored on the scan.
_DECLARATION_MARKER_RE = re.compile(
    r"\b(e-?mail|email|customer\s*care|consumer\s*care|care\s*(?:no|number)|ph\.?|phone|"
    r"telephone|mobile|helpline|toll\s*free|fssai|lic\.?\s*no|licence|license|"
    r"net\s*(?:wt|weight|qty|quantity|content|vol|volume)|nett\s*wt|mrp|max\.?\s*retail|"
    r"mfd|mfg|pkd|best\s*before|use\s*by|batch|lot\s*no|country\s*of\s*origin)\b",
    re.IGNORECASE,
)

# TLDs accepted when trimming a glued character off an OCR'd e-mail address
# ("paikynj@gmail.comD 81906028800030" is a real example from a packaged-food label).
_KNOWN_TLDS = {
    "com", "in", "org", "net", "co", "edu", "gov", "biz", "info", "io", "us",
    "uk", "mail", "store", "shop", "online", "site", "tech", "app", "institute",
}


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


# Fields that belong to one declaration and must be merged atomically: taking
# the value from one photo and the unit from another could pair '500' with
# 'ml' from a different panel.
_FIELD_GROUPS = (
    frozenset({"net_quantity_value", "net_quantity_unit"}),
    frozenset({"mrp", "mrp_inclusive_taxes", "mrp_detected_text"}),
)

_BOOLEAN_FIELDS = frozenset({"ingredients_declared", "nutritional_info_declared"})


def merge_extracted_fields(per_image: List["ExtractedData"]) -> ExtractedData:
    """Merge per-photo extractions into one result.

    Each photo was extracted independently: OCR items from different photos
    share one coordinate space, so merging their raw items first made line
    rebuilding interleave text across panels (a best-before value once picked
    up prose merged from the neighbouring photo). Merge rules, deterministic:

    - grouped fields (net-quantity pair, MRP trio) come from one photo;
    - boolean flags are True when any photo saw them;
    - every other field comes from the photo that read it most confidently,
      ties going to the earlier photo. Empty strings never win.
    """
    merged = ExtractedData()
    if not per_image:
        return merged

    dicts = [ext.to_dict() for ext in per_image]

    def _has_content(entry: Dict[str, Any]) -> bool:
        value = entry.get("value")
        return value is not None and value != ""

    claimed: set[str] = set()
    for group in _FIELD_GROUPS:
        best_i, best_score = None, -1.0
        for i, d in enumerate(dicts):
            present = [k for k in group if k in d and _has_content(d[k])]
            if not present:
                continue
            score = sum(float(d[k].get("confidence", 0.0) or 0.0) for k in present)
            if score > best_score:
                best_i, best_score = i, score
        if best_i is not None:
            for k in group:
                if k in dicts[best_i] and _has_content(dicts[best_i][k]):
                    merged.fields[k] = dicts[best_i][k]
                    claimed.add(k)

    for key in sorted({k for d in dicts for k in d}):
        if key in claimed:
            continue
        best_entry, best_i = None, None
        for i, d in enumerate(dicts):
            entry = d.get(key)
            if not entry or not _has_content(entry):
                continue
            if key in _BOOLEAN_FIELDS and entry.get("value") is not True:
                continue
            conf = float(entry.get("confidence", 0.0) or 0.0)
            if best_entry is None or conf > float(best_entry.get("confidence", 0.0) or 0.0):
                best_entry, best_i = entry, i
        if best_entry is not None:
            merged.fields[key] = best_entry
    return merged


def extract_fields_from_ocr(items: List[Any], full_text: Optional[str] = None) -> ExtractedData:
    """Extract structured product declarations from OCR items."""
    data = ExtractedData()

    if not items:
        return data

    # Normalize fullwidth punctuation in place before any regex runs.
    for it in items:
        if it.text and any(ch in it.text for ch in "\uFF1A\uFF0E\uFF0C\u3000"):
            it.text = it.text.translate(_FULLWIDTH_MAP)

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
    mfg_keywords = ["manufactured by", "mfd by", "packed by", "pkd by", "mktd by", "marketed by",
                    "manufacturedby", "mfdby", "packedby", "pkdby", "mktdby", "marketedby"]
    mfg_found = False
    for i, line in enumerate(text_lines):
        line_lower = line.lower()
        matched_kw = next((kw for kw in mfg_keywords if kw in line_lower), None)
        if matched_kw:
            mfg_found = True
            # Attribute the declaration to an OCR item that is actually on this line
            # (the previous items[i] index pointed at an unrelated word, so the crop
            # shown to the inspector did not contain the declaration).
            mfg_header_item = next(
                (
                    it for it in items
                    if len(it.text or "") > 2 and (it.text or "").lower() in line_lower
                ),
                items[0],
            )
            # Name = text after the keyword on the same line ("Marketed by: ACME Ltd")
            # else the following line; cap length to avoid swallowing the page.
            kw_pos = line_lower.find(matched_kw)
            after_kw = line[kw_pos + len(matched_kw):].strip(" :,-")
            name_from_next_line = not after_kw
            mfg_name = after_kw or (text_lines[i + 1] if i + 1 < len(text_lines) else line)
            mfg_name = mfg_name.strip()[:120]

            # Address = the lines after the name, stopping at the next declaration
            # block so consumer-care details are never stored as part of the address.
            address_start = i + 2 if name_from_next_line else i + 1
            address_lines = []
            for candidate in text_lines[address_start:address_start + 4]:
                if _DECLARATION_MARKER_RE.search(candidate):
                    break
                address_lines.append(candidate)
            full_address = ", ".join(address_lines)[:200]

            data.set_field("manufacturer_name", mfg_name, mfg_header_item.confidence, mfg_header_item.bbox, line)
            if full_address:
                data.set_field("manufacturer_address", full_address, mfg_header_item.confidence, mfg_header_item.bbox)
            break

    # Look for 6-digit Indian PIN code (cannot start with 0).
    # OCR often splits the PIN across a space ("387 620") or merges it into a
    # phone token ("Ph:(02691)252922"), so we search with flexibility.
    address_cues = re.compile(
        r"\b(mohmedpura|kapadwanj|road|street|plot|premises|nagar|vil|village|"
        r"industrial|estate|phase|block|floor|building|house|near|nearby|"
        r"district|tal|taulia|post|soi|sopan|\d{3,5}\s*[-.:]\s*\d{3,5})\b",
        re.IGNORECASE,
    )
    # Phone-signature patterns that mean a 6-digit run is part of a phone number,
    # including glued forms like "NoPh:" that OCR produces.
    phone_sig = re.compile(
        r"(?:phone|ph|tel|mob|mobile|call|contact|helpline|care|no\.?|number)",
        re.IGNORECASE,
    )
    # PIN regexes: strict 6-digit, and space-split pairs like "387 620"
    pin_strict = re.compile(r"\b([1-9]\d{5})\b")
    # Second group is \d{3} (3 digits), not [1-9]\d{3} (4 digits) — the split
    # runs 3+3 for a 6-digit PIN, e.g. "387 620" -> "387620".
    pin_split = re.compile(r"\b([1-9]\d{2})\s+(\d{3})\b")
    pin = None
    pin_item = items[0]
    line_start_for = {}
    line_end_for = {}
    for m in pin_strict.finditer(combined_text):
        ls = combined_text.rfind("\n", 0, m.start()) + 1
        le = combined_text.find("\n", m.end())
        if le == -1:
            le = len(combined_text)
        line_start_for[m.start()] = ls
        line_end_for[m.start()] = le
    for m in pin_split.finditer(combined_text):
        # Build the merged PIN and treat it as if it started at the first group
        merged = m.group(1) + m.group(2)
        fake_pos = m.start(1)
        ls = combined_text.rfind("\n", 0, m.start(1)) + 1
        le = combined_text.find("\n", m.end())
        if le == -1:
            le = len(combined_text)
        line_start_for[fake_pos] = ls
        line_end_for[fake_pos] = le
    # Collect all candidates with their line context
    candidates = []
    for m in pin_strict.finditer(combined_text):
        cand = m.group(1)
        ls = line_start_for.get(m.start(), 0)
        le = line_end_for.get(m.start(), len(combined_text))
        line = combined_text[ls:le]
        ctx = combined_text[max(0, m.start() - 12):m.end()]
        candidates.append((cand, line, ctx, m))
    for m in pin_split.finditer(combined_text):
        cand = m.group(1) + m.group(2)
        ls = line_start_for.get(m.start(1), 0)
        le = line_end_for.get(m.start(1), len(combined_text))
        line = combined_text[ls:le]
        ctx = combined_text[max(0, m.start() - 12):m.end()]
        candidates.append((cand, line, ctx, m))
    # Score candidates: address cue on the line = 2 pts; not in a phone token = 1 pt
    def score(cand, line, ctx):
        s = 0
        if address_cues.search(line):
            s += 2
        if not phone_sig.search(ctx):
            s += 1
        # A split-pair PIN (with space) that sits on an address line is almost
        # certainly the postal code, so boost it further.
        if " " in cand:
            s += 1
        return s
    candidates.sort(key=lambda c: score(c[0], c[1], c[2]), reverse=True)
    for cand, line, ctx, m in candidates:
        if score(cand, line, ctx) >= 2:
            pin = cand
            pin_item = next((it for it in items if cand.replace(" ", "") in it.text.replace(" ", "") or cand in it.text), items[0])
            break
    if pin:
        data.set_field("pin_code", pin, pin_item.confidence, pin_item.bbox, pin_item.text)

    # ----------------------------------------------------
    # 3. Consumer Care Details (Rule 6(2))
    # ----------------------------------------------------
    # Email
    email_match = re.search(
        r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)+", combined_text
    )
    if email_match:
        email = email_match.group(0).rstrip(".")
        # OCR commonly glues the following character onto the address, so trailing
        # characters are trimmed until the top-level domain is one we recognise.
        while "." in email and email.rsplit(".", 1)[-1].lower() not in _KNOWN_TLDS:
            email = email[:-1]
        if "." in email and email.rsplit(".", 1)[-1].lower() in _KNOWN_TLDS:
            local_part = email.split("@")[0]
            item_email = next(
                (it for it in items if local_part and local_part in (it.text or "")), items[0]
            )
            data.set_field("consumer_care_email", email, item_email.confidence, item_email.bbox, item_email.text)

    # Telephone / Phone
    # Contact keywords must sit on a word boundary and the bare word "no" is not
    # accepted: on a real label "Lic.No.10717012000120" matched the old pattern and
    # the FSSAI licence number was stored as the consumer-care telephone number,
    # which then passed the Rule 6(2) check.
    phone_regex = re.compile(
        r"\b(?:phone|ph|telephone|tel|mobile|mob|call|contact|helpline|toll\s*free|"
        r"customer\s*care|consumer\s*care|care\s*(?:no|number))\b"
        r"[^\d+]{0,12}?(\(?\+?\d[\d\s\-()]{5,17})",
        re.IGNORECASE,
    )
    for phone_match in phone_regex.finditer(combined_text):
        raw_phone = phone_match.group(1).strip().strip("- ")
        digits = re.sub(r"\D", "", raw_phone)
        # Indian consumer-care numbers carry 7-13 digits including STD or country
        # code; a 14-digit run is a licence number rather than a telephone number.
        if not 7 <= len(digits) <= 13:
            continue
        item_phone = next(
            (it for it in items if digits[:5] and digits[:5] in re.sub(r"\D", "", it.text or "")),
            items[0],
        )
        data.set_field("consumer_care_phone", raw_phone, item_phone.confidence, item_phone.bbox, item_phone.text)
        break

    # ----------------------------------------------------
    # 4. Maximum Retail Price (MRP) & Tax Qualification (Rule 6(1)(e))
    # ----------------------------------------------------
    mrp_regex = re.compile(
        r"(?:m\.?r\.?p\.?|max(?:imum)?\s*retail\s*price)[^\d₹Rs]*[₹Rs\.]*\s*([0-9]+(?:\.[0-9]{1,2})?)",
        re.IGNORECASE
    )
    mrp_match = mrp_regex.search(combined_text)
    if not mrp_match:
        # Secondary pattern: standalone Rs. XX.XX, rs.XX or ₹ XX.XX. The currency token
        # must not be the tail of another word — without the lookbehind, "Total Sugars
        # 71.9g" (a nutrition value) becomes a declared MRP of ₹71.90.
        mrp_match = re.search(
            r"(?<![A-Za-z])(?:₹|Rs\.?|INR)\s*([0-9]+(?:\.[0-9]{1,2})?)",
            combined_text,
            re.IGNORECASE,
        )

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
    # A declared net quantity must be preceded by a net-quantity keyword (or followed
    # by "net"/"e"). The previous pattern made the keyword optional, so on a real
    # basundi-mix label the nutrition-table reference "Per 100gm" was stored as the
    # declared net quantity. An unreadable net quantity now routes to NEEDS_REVIEW
    # rather than being replaced by a number taken from the nutrition table.
    net_qty_regex = re.compile(
        r"\b(?:net\s*(?:wt\.?|weight|qty\.?|quantity|content|vol\.?|volume)|nett\s*(?:wt|weight)|"
        r"pkd|packed|quantity|qty)\b"
        r"[^\d]{0,6}([0-9]+(?:\.[0-9]+)?)\s*"
        r"(kg|g|gm|gms|gram|grams|ml|l|ltr|litre|litres|liter|liters|n|u)\b",
        re.IGNORECASE,
    )
    trailing_net_regex = re.compile(
        r"([0-9]+(?:\.[0-9]+)?)\s*(kg|g|gm|gms|gram|grams|ml|l|ltr|litre|litres|liter|liters)\s*"
        r"(?:net|nett|e)\b",
        re.IGNORECASE,
    )
    qty_match = net_qty_regex.search(combined_text) or trailing_net_regex.search(combined_text)
    if qty_match:
        qty_val = float(qty_match.group(1))
        unit = qty_match.group(2).lower()
        best_qty_item = next((it for it in items if qty_match.group(1) in it.text and unit in it.text.lower()), items[0])
        data.set_field("net_quantity_value", qty_val, best_qty_item.confidence, best_qty_item.bbox, best_qty_item.text)
        data.set_field("net_quantity_unit", unit, best_qty_item.confidence, best_qty_item.bbox, best_qty_item.text)

    # Check for prohibited vague quantity words (Rule 12(6)).
    # Rule 12(6) prohibits qualifying words in the *quantity declaration*, so the word
    # must sit next to a number and unit; matching the word anywhere on the label
    # raised a non-compliance for unrelated prose ("About this pack", "Average values").
    vague_regex = re.compile(
        r"\b(minimum|not\s+less\s+than|average|about|approximately|approx\.?)\b"
        r"[^\d]{0,12}([0-9]+(?:\.[0-9]+)?)\s*"
        r"(kg|g|gm|gms|gram|grams|ml|l|ltr|litre|litres|liter|liters|n|u)\b",
        re.IGNORECASE,
    )
    vague_match = vague_regex.search(combined_text)
    if vague_match:
        vague_word = vague_match.group(1)
        vague_item = next(
            (it for it in items if vague_word.split()[0].lower() in (it.text or "").lower()),
            items[0],
        )
        data.set_field(
            "vague_quantity_found", vague_word, vague_item.confidence, vague_item.bbox, vague_item.text
        )

    # ----------------------------------------------------
    # 6. Date of Manufacture / Packing / Import (Rule 6(1)(d))
    # ----------------------------------------------------
    # Three layouts occur on real panels (all seen on one food box):
    #   a) same line:      "MFG 05/2026"
    #   b) stacked:        "Mfg. Date" on one line, ":02-01-2026" on the next
    #   c) keyword-only:   a bare date elsewhere on the label (least trusted)
    # Full DD-MM-YYYY dates are kept whole — truncating '02-01-2026' to the
    # MM-YY prefix '02-01' once displayed the manufacture date as 'Feb 2001'.
    # Dot-separated numbers are never dates ('2.39' is a nutrition decimal).
    raw_date = None
    date_item = None
    for idx, line in enumerate(text_lines):
        if not re.search(r"\b(?:mfd|mfg|mkd|pkd|packed|packaged|manufactured|manf|imported)\b", line, re.IGNORECASE):
            continue
        m = _DATE_TOKEN_RE.search(line)
        if m:
            raw_date = m.group(0)
            date_item = next((it for it in items if raw_date in (it.text or "")), None)
            break
        # Stacked layout: the value sits on the next line (often after a
        # fullwidth colon the normalizer already converted).
        if idx + 1 < len(text_lines):
            next_line = text_lines[idx + 1]
            stripped = next_line.strip(" :.-")
            m = _DATE_TOKEN_RE.search(stripped)
            if m and m.group(0) == stripped:
                raw_date = m.group(0)
                date_item = next((it for it in items if raw_date in (it.text or "")), None)
                break

    if raw_date is None:
        # Bare-date fallback: only unambiguous tokens qualify (4-digit year or
        # month name). '02-01' alone is ambiguous (day-month? month-year?) and
        # must not be stored as a manufacture date.
        for line in text_lines:
            if _BEST_BEFORE_KEYWORD_RE.search(line):
                continue  # belongs to the best-before declaration, not manufacture
            for m in _DATE_TOKEN_RE.finditer(line):
                if _plausible_date_token(m.group(0)):
                    raw_date = m.group(0)
                    date_item = next((it for it in items if raw_date in (it.text or "")), None)
                    break
            if raw_date:
                break

    if raw_date:
        if date_item is None:
            date_item = items[0]
        data.set_field("mfg_date_str", raw_date, date_item.confidence, date_item.bbox, date_item.text)

    # Best before / use by date (Rule 6(1)(da)).
    # Real panels print this declaration in three layouts (all observed on one
    # food box):
    #   a) keyword first: "Best Before: 01-01-2027" / "Exp.Date :01-01-2027"
    #   b) value first:   ":01-01-2027 Exp.Date"  (date printed left of keyword)
    #   c) stacked:       keyword alone, value on the next line
    # The previous single forward regex only knew (a): on layout (b) nothing
    # followed the keyword, so the expiry date was silently dropped. Its
    # unanchored capture also stored prose merged from a neighbouring photo as
    # the expiry date. Line-based matching with a plausibility gate fixes both:
    # a stored value must look like a date or a declared shelf life, never prose.
    bb_kw_re = re.compile(
        r"\b(?:best\s*before|use\s*by|exp(?:iry)?\.?\s*date|exp(?:iry)?\.?|bb)\s*[:\-.]?\s*",
        re.IGNORECASE,
    )
    for idx, line in enumerate(text_lines):
        kw = bb_kw_re.search(line)
        if not kw:
            continue
        # (a) keyword first: the value follows on the same line.
        value = line[kw.end():].strip(" :.,;-")
        if not _plausible_bb_value(value):
            # (b) value first: the date is printed BEFORE the keyword
            # (':01-01-2027 Exp.Date'). Only a clean date or shelf-life token
            # qualifies — nothing else from the line may leak into the value.
            before = line[:kw.start()].strip(" :.,;-")
            m = _DATE_TOKEN_RE.search(before)
            if m and m.group(0) == before:
                value = m.group(0)
            elif parse_relative_period(before) and re.fullmatch(r"\d{1,4}\s*[a-zA-Z]+", before):
                value = before
        if not _plausible_bb_value(value) and idx + 1 < len(text_lines):
            # (c) stacked: the keyword stands alone and the value is printed
            # on the following line.
            nxt = text_lines[idx + 1].strip(" :.,;-")
            if _plausible_bb_value(nxt):
                value = nxt
        if not _plausible_bb_value(value):
            continue  # prose or garbage — not a declaration; leave missing so
                      # the checker routes it to NEEDS_REVIEW
        bb_first_word = value.split()[0]
        item_bb = next(
            (it for it in items if bb_first_word.lower() in (it.text or "").lower()),
            items[0],
        )
        data.set_field("best_before", value, item_bb.confidence, item_bb.bbox, item_bb.text)
        break

    # ----------------------------------------------------
    # 7. Country of Origin (Rule 6(1)(aa))
    # ----------------------------------------------------
    # OCR frequently collapses whitespace ("MADE IN INDIA" -> "MAKEININDA"), so
    # match the declaration keywords both with and without internal spaces.
    origin_regex = re.compile(
        r"(?:country\s*of\s*origin|made\s*in|make\s*in|product\s*of|produce\s*of|manufactured\s*in|"
        r"makein|madein|manufacturedin|productof|produceof|countryoforigin)"
        r"[:\-.]?\s*([A-Za-z][A-Za-z\s]{2,30})",
        re.IGNORECASE
    )
    origin_match = origin_regex.search(combined_text)
    if origin_match:
        country = origin_match.group(1).strip()
        # The captured text often runs on into the next declaration; take the shortest
        # leading run of words that is a recognised country ("Italy Net Wt. 500 g" ->
        # "Italy", "United States Of America" -> "United States"), and store nothing
        # when no country can be read rather than recording a fragment as the origin.
        for word_count in (1, 2, 3):
            candidate = " ".join(country.split()[:word_count])
            if is_known_country(candidate):
                country = candidate
                break
        else:
            country = ""
        if country:
            item_origin = next(
                (
                    it for it in items
                    if any(
                        keyword in (it.text or "").lower()
                        for keyword in ("origin", "made in", "make in", "product of", "makein", "madein")
                    )
                ),
                items[0],
            )
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
            r"^(net|max|mrp|mfd|mfg|pkd|best|use|batch|lot|marketed|manufactured|country|fssai|lic|ingredients|nutrition|calories|directions|usage|serving|\d|per\s*\d)\b",
            second,
            re.IGNORECASE,
        )
        product_name = f"{header_line} {second}" if looks_like_descriptor and second else header_line

        def _cut_header(line: str, limit: int = 8) -> str:
            """Safety cut: a header that swallowed neighbouring declarations
            (degenerate line grouping) is trimmed at the first declaration
            keyword and capped to a few words."""
            cut = re.split(
                r"\b(net\s*qty|net\b|max\.?\s*retail|mrp|mfd\.?|mfg\.?|pkd|best\s*before|use\s*by|batch|lot|marketed|manufactured|country\s*of|fssai|ingredients|nutrition|calories|directions|usage|serving|per\s*\d)\b",
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
