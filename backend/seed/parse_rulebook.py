"""Parse RULE BOOK.pdf into structured rules.json and schedules.json.

Guarantees WORD-FOR-WORD extraction without hallucination per AGENTS.md §1 & §7.4.

v2: the first version of this script shipped a hand-curated list of 28 rules —
most of the book (rules 2, 4, 11, 14-23, 25, 27-30, 33, 34) never reached the
Rule Book UI or the engine's rule citations. This version DETECTS every main
rule heading in the PDF by its sequential number, slices the verbatim body
between headings, and merges the result with the curated granular entries
(rule-6-1-a, rule-7-2, ...) that violations deep-link to.

Usage:  python seed/parse_rulebook.py   (run from the backend/ directory)
"""

import json
import os
import re
import sys
from bisect import bisect_right

import pymupdf

BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PDF_PATH = os.path.join(os.path.dirname(BACKEND_ROOT), "RULE_BOOK.pdf")
RULES_OUT = os.path.join(BACKEND_ROOT, "seed", "rules.json")
CURATED_IN = os.path.join(BACKEND_ROOT, "seed", "rules_curated.json")
SCHEDULES_OUT = os.path.join(BACKEND_ROOT, "seed", "schedules.json")

CHAPTER_DEFAULTS = {
    1: "CHAPTER I - PRELIMINARY",
    2: "CHAPTER I - PRELIMINARY",
}


def extract_text_by_pages(pdf_path: str):
    doc = pymupdf.open(pdf_path)
    pages = []
    for i, page in enumerate(doc):
        pages.append({
            "page": i + 1,
            "text": page.get_text("text"),
        })
    return pages


def _combined_with_page_index(pages):
    """Concatenate page texts, recording the char offset where each page starts."""
    parts, offsets, page_numbers = [], [], []
    pos = 0
    for p in pages:
        offsets.append(pos)
        page_numbers.append(p["page"])
        parts.append(p["text"])
        pos += len(p["text"]) + 1  # +1 for the joining "\n"
    return "\n".join(parts), offsets, page_numbers


def _page_for(offset: int, offsets, page_numbers) -> int:
    idx = bisect_right(offsets, offset) - 1
    return page_numbers[max(0, idx)]


_HEADING_RE = re.compile(r"(?m)^[ \t]*(\d{1,2}[A-Z]?)[ \t]*\.[ \t]*")
_NUM_RE = re.compile(r"^(\d{1,2})([A-Z]?)$")


def num_int_from_key(key: str) -> int:
    return int(re.match(r"\d+", key).group())


def suffix_of_key(key: str) -> str:
    return key[len(str(num_int_from_key(key))):]

# Cut markers that end a rule title in this PDF's typography: ".-" is the
# standard statutory style ("Definitions:- ..."), but several rules use
# ". (" before sub-rule (1), an em-dash, or a plain hyphen.
_TITLE_CUT_MARKERS = (".-", ". –", ".—", ":-", ". (", ".  (", ".(", " - ")


def _clean_title(candidate: str) -> str:
    """Derive a display title from the first line(s) of a rule body."""
    t = re.sub(r"\s+", " ", candidate).strip()
    t = re.sub(r"^\(\s*1\s*\)\s+", "", t)  # "5. (1) Specific commodities..."
    cut = len(t)
    for marker in _TITLE_CUT_MARKERS:
        idx = t.find(marker, 0, 160)
        if idx != -1:
            cut = min(cut, idx)
    # "Power to relax- (1)The Central Government...": a dash directly before a
    # sub-rule marker also ends the title.
    m_dash = re.search(r"-\s*\(\s*1\s*\)", t[:160])
    if m_dash:
        cut = min(cut, m_dash.start())
    if cut == len(t):
        # No statutory marker: cut at a word boundary near 90 chars.
        if len(t) > 90:
            cut = t.rfind(" ", 0, 90)
            if cut == -1:
                cut = 90
    title = t[:cut].strip().rstrip("-–—:., ")
    return title


def _applies_to(num_int: int, suffix: str) -> dict:
    if num_int <= 2:
        return {"definitions": True}
    if num_int <= 13:
        return {"all_retail": True}
    if num_int <= 18:
        return {"declarations": True}
    if num_int <= 23:
        return {"verification": True}
    if num_int <= 25:
        return {"wholesale": True}
    if num_int == 26:
        return {"exemptions": True}
    if num_int <= 30:
        return {"registration": True}
    return {"penalties": True} if num_int == 32 else {"misc": True}


def detect_main_rules(full_text: str, offsets, page_numbers):
    """Locate every main rule (1..34) and slice its verbatim body."""
    # Schedules and notification letters repeat main-rule-style numbering
    # ("1. Maximum permissible errors..."); everything from the First Schedule
    # heading on is not a body rule, so collection stops there. The anchor must
    # be the line-style heading ("THE FIRST SCHEDULE" on its own line): an
    # unanchored search also matches inline prose like "specified in the First
    # Schedule" inside rule 2(e), which truncated the body scan after rule 2.
    stop = len(full_text)
    m_stop = re.search(r"(?im)^\s*THE\s+FIRST\s+SCHEDULE\s*$", full_text)
    if m_stop:
        stop = m_stop.start()

    candidates = []  # (num_int, suffix, heading_end_offset, heading_start_offset)
    last_accepted = 0
    for m in _HEADING_RE.finditer(full_text, 0, stop):
        nm = _NUM_RE.match(m.group(1))
        if not nm:
            continue
        num_int, suffix = int(nm.group(1)), nm.group(2)
        if num_int < 1 or num_int > 34:
            continue
        # Accept the next expected rule, a repeat (amended restatement — the
        # LAST occurrence is the operative text), or a small gap (rule 31 was
        # omitted by amendment). Anything smaller is sub-numbering inside a
        # body (tables, clause lists) and is rejected.
        if num_int < last_accepted or num_int > last_accepted + 2:
            continue
        last_accepted = num_int
        candidates.append((num_int, suffix, m.end(), m.start()))

    # Keep the LAST heading per FULL rule number (operative amended text; the
    # "32." vs "32A." distinction is preserved by keying on number+suffix —
    # keying on the integer alone collapsed rule 32 and 32A into one entry).
    # Slice each body up to the next accepted heading.
    by_key = {}
    order = []
    for num_int, suffix, end, start in candidates:
        key = f"{num_int}{suffix}"
        if key not in by_key:
            order.append(key)
        by_key.setdefault(key, []).append((end, start))

    rules = []
    for i, key in enumerate(order):
        end, start = by_key[key][-1]
        body_end = stop
        for _n2, _s2, _e2, next_start in candidates:
            if next_start > start:
                body_end = next_start
                break
        body = full_text[end:body_end].strip()
        body = re.sub(r"\n{3,}", "\n\n", body).strip()
        chapter_match = None
        for cm in re.finditer(
            r"(?m)^\s*CHAPTER\s*[–—-]\s*([IVX]+)\s*[\.\:]?\s*\n?\s*([A-Z][A-Z \-&,()0-9]{5,90})",
            full_text[:start],
        ):
            chapter_match = cm
        if chapter_match:
            chapter = f"CHAPTER {chapter_match.group(1)} - {re.sub(r'\s+', ' ', chapter_match.group(2)).strip()}"
        else:
            chapter = CHAPTER_DEFAULTS.get(num_int_from_key(key), "CHAPTER I - PRELIMINARY")
        rule_number = f"rule-{key}"
        rules.append({
            "rule_number": rule_number,
            "chapter": chapter,
            "title": _clean_title(body[:220]),
            "full_text": body,
            "schedule_ref": None,
            "applies_to": _applies_to(num_int_from_key(key), suffix_of_key(key)),
            "source_page": _page_for(start, offsets, page_numbers),
        })
    return rules


def build_merged_rules(pages):
    """PDF-extracted main rules merged with the curated granular entries.

    Curated entries (seed/rules_curated.json) win when a rule number exists in
    both: they carry human-verified applies_to hints and schedule references,
    and several are sub-rule level (rule-6-1-e) that violations cite directly.
    """
    full_text, offsets, page_numbers = _combined_with_page_index(pages)
    extracted = detect_main_rules(full_text, offsets, page_numbers)

    with open(CURATED_IN, encoding="utf-8") as f:
        curated = json.load(f)
    curated_by_number = {r["rule_number"]: r for r in curated}

    merged = list(curated)
    added = []
    for r in extracted:
        if r["rule_number"] in curated_by_number:
            continue
        merged.append(r)
        added.append(r["rule_number"])

    # Guard against regressions: the book contains 33 main rules (1-34 with
    # 31 omitted by amendment, including 32A). Extraction must find them all.
    expected_main = {
        f"rule-{n}" for n in range(1, 31)
    } | {"rule-32", "rule-32A", "rule-33", "rule-34"}
    missing = expected_main - {r["rule_number"] for r in extracted}
    if missing:
        raise SystemExit(
            f"[FAIL] Rule extraction regressed; missing from PDF: {sorted(missing)}"
        )

    def natural_key(rule):
        parts = re.findall(r"\d+|[A-Za-z]+", rule["rule_number"])
        return [int(p) if p.isdigit() else p.lower() for p in parts]

    merged.sort(key=natural_key)
    return merged, added, extracted


def main():
    if not os.path.exists(PDF_PATH):
        print(f"[ERROR] RULE_BOOK.pdf not found at {PDF_PATH}")
        sys.exit(1)

    pages = extract_text_by_pages(PDF_PATH)
    rules, added, extracted = build_merged_rules(pages)

    with open(RULES_OUT, "w", encoding="utf-8") as f:
        json.dump(rules, f, indent=2, ensure_ascii=False)

    print(f"[OK] PDF main rules detected: {len(extracted)} ({', '.join(r['rule_number'] for r in extracted)})")
    print(f"[OK] Newly added from PDF: {len(added)} ({', '.join(added) or 'none'})")
    print(f"[OK] Wrote {len(rules)} rules to {os.path.relpath(RULES_OUT, BACKEND_ROOT)}")


if __name__ == "__main__":
    main()
