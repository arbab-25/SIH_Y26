"""Deterministic parsers shared by the Legal Metrology rule checkers.

These helpers only interpret text the OCR engine already produced — they never
invent a value. Anything they cannot interpret returns ``None`` so the calling
checker can route that declaration to NEEDS_REVIEW (fail-closed, per the
no-hallucination rules: a wrong "Compliant" is worse than no verdict).
"""

import re
from datetime import date
from typing import Optional, Tuple

from rapidfuzz import fuzz, process

MONTH_ABBREVIATIONS = (
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
)

_MONTH_TOKENS = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}

# Longest month tokens first so "sept" is never truncated to "sep".
_MONTH_NAME_RE = re.compile(
    r"\b("
    + "|".join(sorted(_MONTH_TOKENS, key=len, reverse=True))
    + r")[a-z]*\.?\s*[/,.\-]?\s*(\d{2,4})\b",
    re.IGNORECASE,
)

# Month-first numeric dates: "05/2026", "5-26" — the format Rule 6(1)(d)
# prescribes for the month and year of manufacture. Dot separators are NOT
# accepted here: "2.39" is a nutrition-table decimal, and reading the dot as a
# separator manufactured a "Feb 2039" date out of one.
_NUMERIC_MONTH_YEAR_RE = re.compile(r"\b(\d{1,2})\s*[/\-]\s*(\d{2,4})\b")

# Full calendar dates as printed on Indian retail packs: "02-01-2026",
# "02/01/2026" (DD-MM-YYYY). Parsed before the month-year forms so a
# three-component date is never truncated to its MM-YY prefix — truncating
# '02-01-2026' to '02-01' reported the manufacture date as 'Feb 2001'.
_NUMERIC_FULL_DATE_RE = re.compile(r"\b(\d{1,2})\s*[/\-]\s*(\d{1,2})\s*[/\-]\s*(\d{4})\b")

# Year-first numeric dates: "2026-05" as printed on some imported packs.
_NUMERIC_YEAR_MONTH_RE = re.compile(r"\b(\d{4})\s*[/\-.]\s*(\d{1,2})\b")

# Shelf-life declarations: "Best before: 6 months from packaging".
_RELATIVE_PERIOD_RE = re.compile(
    r"\b(\d{1,3})\s*(days?|weeks?|months?|years?)\b", re.IGNORECASE
)


def _expand_year(raw: str) -> Optional[int]:
    """Return a four-digit year from '2026' or the two-digit form '26'."""
    digits = re.sub(r"\D", "", str(raw))
    if len(digits) == 4:
        return int(digits)
    if len(digits) == 2:
        return 2000 + int(digits)
    return None


def _month_from_token(token: str) -> Optional[int]:
    cleaned = str(token).lower().strip(". ")
    if cleaned in _MONTH_TOKENS:
        return _MONTH_TOKENS[cleaned]
    if cleaned[:3] in _MONTH_TOKENS:
        return _MONTH_TOKENS[cleaned[:3]]
    return None


def month_index(year: int, month: int) -> int:
    """Absolute month counter so two label dates can be ordered."""
    return int(year) * 12 + (int(month) - 1)


def current_month_index(today: Optional[date] = None) -> int:
    """Absolute month counter for today (or an injected reference date)."""
    reference = today or date.today()
    return month_index(reference.year, reference.month)


def months_until(target_index: int, today: Optional[date] = None) -> int:
    """Whole months from today (or an injected reference date) to a month index."""
    return target_index - current_month_index(today)


def format_month_year(year_month: Tuple[int, int]) -> str:
    """Render (year, month) as 'Jan 2026' for operator-facing messages."""
    year, month = year_month
    if not 1 <= int(month) <= 12:
        return f"{month:02d}/{year}"
    return f"{MONTH_ABBREVIATIONS[int(month) - 1]} {year}"


def parse_month_year(value: Optional[str]) -> Optional[Tuple[int, int]]:
    """Return ``(year, month)`` for a label date, or ``None`` when unreadable.

    Accepts the declarations found on Indian retail packs: full calendar dates
    (``DD-MM-YYYY`` / ``DD/MM/YYYY``), ``MM/YYYY``, ``MM-YY``, ``Month YYYY``
    and the ISO ``YYYY-MM`` form.
    """
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None

    # Full DD-MM-YYYY first: the most specific form, and its MM-YY prefix must
    # never win ('02-01-2026' is January 2026, not 'Feb 2001').
    full = _NUMERIC_FULL_DATE_RE.search(text)
    if full:
        day, month, year = int(full.group(1)), int(full.group(2)), int(full.group(3))
        if 1 <= month <= 12 and 1 <= day <= 31:
            return (year, month)

    named = _MONTH_NAME_RE.search(text)
    if named:
        month = _month_from_token(named.group(1))
        year = _expand_year(named.group(2))
        if month and year:
            return (year, month)

    month_first = _NUMERIC_MONTH_YEAR_RE.search(text)
    if month_first:
        month = int(month_first.group(1))
        year = _expand_year(month_first.group(2))
        if year and 1 <= month <= 12:
            return (year, month)

    year_first = _NUMERIC_YEAR_MONTH_RE.search(text)
    if year_first:
        year = int(year_first.group(1))
        month = int(year_first.group(2))
        if 1 <= month <= 12:
            return (year, month)

    return None


def parse_relative_period(value: Optional[str]) -> Optional[Tuple[int, str]]:
    """Return ``(amount, unit)`` for a declared shelf life such as "6 months"."""
    if value is None:
        return None
    match = _RELATIVE_PERIOD_RE.search(str(value))
    if not match:
        return None
    amount = int(match.group(1))
    if amount <= 0:
        return None
    return (amount, match.group(2).lower().rstrip("s"))


def add_period(year: int, month: int, amount: int, unit: str) -> Tuple[int, int]:
    """Advance a ``(year, month)`` pair by a declared shelf-life period.

    Rule 6(1)(da) only requires the month and year of the best-before/use-by
    date, so day and week periods are converted to whole months. The conversion
    is documented in the reported message so a reviewer can see how the
    estimate was derived rather than being handed a silent guess.
    """
    unit = (unit or "").lower().rstrip("s")
    if unit == "year":
        months = amount * 12
    elif unit == "month":
        months = amount
    elif unit == "week":
        months = max(1, round(amount * 7 / 30))
    elif unit == "day":
        months = max(1, round(amount / 30))
    else:
        months = amount

    total = month_index(year, month) + months
    return (total // 12, total % 12 + 1)


# ISO 3166-1 alpha-2 codes — a two-letter origin declaration is only accepted
# when it is a real country code rather than an OCR fragment.
_ISO_ALPHA2 = set(
    """
    ad ae af ag ai al am ao aq ar as at au aw ax az
    ba bb bd be bf bg bh bi bj bl bm bn bo bq br bs bt bv bw by bz
    ca cc cd cf cg ch ci ck cl cm cn co cr cu cv cw cx cy cz
    de dj dk dm do dz
    ec ee eg eh er es et
    fi fj fk fm fo fr
    ga gb gd ge gf gg gh gi gl gm gn gp gq gr gs gt gu gw gy
    hk hm hn hr ht hu
    id ie il im in io iq ir is it
    je jm jo jp
    ke kg kh ki km kn kp kr kw ky kz
    la lb lc li lk lr ls lt lu lv ly
    ma mc md me mf mg mh mk ml mm mn mo mp mq mr ms mt mu mv mw mx my mz
    na nc ne nf ng ni nl no np nr nu nz
    om
    pa pe pf pg ph pk pl pm pn pr ps pt pw py
    qa
    re ro rs ru rw
    sa sb sc sd se sg sh si sj sk sl sm sn so sr ss st sv sx sy sz
    tc td tf tg th tj tk tl tm tn to tr tt tv tw tz
    ua ug um us uy uz
    va vc ve vg vi vn vu
    wf ws
    ye yt
    za zm zw
    """.split()
)

_COUNTRY_NAMES = {
    "india", "indian", "afghanistan", "argentina", "australia", "austria",
    "bahrain", "bangladesh", "belgium", "bhutan", "brazil", "bulgaria",
    "canada", "chile", "china", "colombia", "cyprus", "czech republic",
    "denmark", "egypt", "england", "estonia", "ethiopia", "finland", "france",
    "germany", "ghana", "greece", "hong kong", "hungary", "iceland",
    "indonesia", "iran", "iraq", "ireland", "israel", "italy", "japan",
    "jordan", "kenya", "kuwait", "latvia", "lebanon", "lithuania",
    "luxembourg", "malaysia", "maldives", "malta", "mauritius", "mexico",
    "morocco", "myanmar", "nepal", "netherlands", "new zealand", "nigeria",
    "norway", "oman", "pakistan", "philippines", "poland", "portugal", "qatar",
    "romania", "russia", "saudi arabia", "scotland", "singapore", "slovakia",
    "slovenia", "south africa", "south korea", "spain", "sri lanka", "sudan",
    "sweden", "switzerland", "taiwan", "tanzania", "thailand", "tunisia",
    "turkey", "uganda", "ukraine", "united arab emirates", "united kingdom",
    "united states", "usa", "vietnam", "wales", "zambia", "zimbabwe",
}


def is_known_country(value: Optional[str]) -> bool:
    """True only when a declared origin matches a country name or ISO alpha-2 code.

    Used to separate a genuine country-of-origin declaration from OCR noise on an
    imported package. An unrecognised reading is routed to NEEDS_REVIEW by the
    caller rather than being treated as a violation, because a garbled read is
    not evidence that the declaration is absent.
    """
    if not value:
        return False

    token = re.sub(r"[^a-z\s]", " ", str(value).lower())
    token = re.sub(r"\s+", " ", token).strip()
    if not token:
        return False

    compact = token.replace(" ", "")
    if len(compact) == 2 and compact in _ISO_ALPHA2:
        return True

    if token in _COUNTRY_NAMES:
        return True

    if len(token) >= 4:
        for name in _COUNTRY_NAMES:
            if name in token:
                return True
        return bool(
            process.extractOne(
                token, _COUNTRY_NAMES, scorer=fuzz.token_set_ratio, score_cutoff=88
            )
        )

    return False
