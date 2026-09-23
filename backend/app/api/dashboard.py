"""Dashboard API Router — Enforcement Statistics, Compliance Trends, Top Violations per §7.8."""

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.product import Product
from app.models.rule import Rule
from app.models.scan import Scan, Verdict
from app.models.violation import Violation

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


def _rule_label(rule_number: str | None, field_key: str) -> str:
    """Render a seeded rule number as inspectors cite it ('Rule 6(1)(e)').

    Falls back to the declaration name when the violation predates rule linking.
    """
    if not rule_number:
        return f"Rule {field_key.replace('_', ' ').title()}"
    parts = rule_number.replace("rule-", "").split("-")
    return f"Rule {parts[0]}{''.join(f'({p})' for p in parts[1:])}"


@router.get("/stats")
async def get_dashboard_stats(db: AsyncSession = Depends(get_db)):
    """Enforcement summary statistics for dashboard display."""
    now = datetime.utcnow()
    today_start = datetime(now.year, now.month, now.day)
    week_start = today_start - timedelta(days=7)
    month_start = today_start - timedelta(days=30)

    # Scans today
    today_res = await db.execute(
        select(func.count(Scan.id)).where(Scan.created_at >= today_start)
    )
    scans_today = today_res.scalar() or 0

    # Scans week
    week_res = await db.execute(
        select(func.count(Scan.id)).where(Scan.created_at >= week_start)
    )
    scans_week = week_res.scalar() or 0

    # Scans month
    month_res = await db.execute(
        select(func.count(Scan.id)).where(Scan.created_at >= month_start)
    )
    scans_month = month_res.scalar() or 0

    # Average OCR confidence
    # Real average only: a placeholder percentage here would report an OCR quality
    # figure that no scan produced.
    avg_conf_res = await db.execute(
        # .is_not(None) is the typed SQLAlchemy 2 form of `IS NOT NULL`
        select(func.avg(Scan.avg_ocr_confidence)).where(Scan.avg_ocr_confidence.is_not(None))
    )
    avg_conf_value = avg_conf_res.scalar()
    avg_ocr_confidence = round(float(avg_conf_value), 2) if avg_conf_value is not None else 0.0

    # Total Scans & Verdict breakdown
    total_res = await db.execute(select(func.count(Scan.id)))
    total_scans = total_res.scalar() or 0

    compliant_res = await db.execute(
        select(func.count(Scan.id)).where(Scan.verdict == Verdict.COMPLIANT)
    )
    compliant_count = compliant_res.scalar() or 0

    non_comp_res = await db.execute(
        select(func.count(Scan.id)).where(Scan.verdict == Verdict.NON_COMPLIANT)
    )
    non_comp_count = non_comp_res.scalar() or 0

    needs_rev_res = await db.execute(
        select(func.count(Scan.id)).where(Scan.verdict == Verdict.NEEDS_REVIEW)
    )
    needs_rev_count = needs_rev_res.scalar() or 0

    # Top Violated Rules (Bar chart data) — grouped by the exact rule the checker
    # cited, so the chart names the statutory rule rather than the field name.
    # An empty result stays empty: invented counts must never be shown as enforcement
    # statistics for a government inspection workspace.
    viol_res = await db.execute(
        select(Violation.field_key, Rule.rule_number, func.count(Violation.id).label("cnt"))
        .join(Rule, Violation.rule_id == Rule.id, isouter=True)
        .group_by(Violation.field_key, Rule.rule_number)
        .order_by(desc("cnt"))
        .limit(6)
    )
    top_violations = []
    for field_key, rule_number, count in viol_res.all():
        top_violations.append({
            "rule": _rule_label(rule_number, field_key),
            "field": field_key,
            "violations_count": count
        })

    # Top Non-Compliant Manufacturers
    mfg_stmt = (
        select(Product.manufacturer_name, func.count(Scan.id).label("cnt"))
        .join(Scan, Product.scan_id == Scan.id)
        .where(Scan.verdict == Verdict.NON_COMPLIANT, Product.manufacturer_name != "")
        .group_by(Product.manufacturer_name)
        .order_by(desc("cnt"))
        .limit(5)
    )
    mfg_res = await db.execute(mfg_stmt)
    top_non_compliant_mfgs = []
    for row in mfg_res.all():
        top_non_compliant_mfgs.append({
            "manufacturer": row[0],
            "violations_count": row[1]
        })

    # Compliance Trend (Line chart data for the past 7 days), aggregated from the
    # recorded scans themselves. Days with no inspections report zero.
    trend_res = await db.execute(
        select(
            func.date(Scan.created_at).label("day"),
            Scan.verdict,
            func.count(Scan.id).label("cnt"),
        )
        .where(Scan.created_at >= today_start - timedelta(days=6))
        .group_by("day", Scan.verdict)
    )

    buckets: dict[str, dict[str, int]] = {}
    for day_value, verdict_value, count in trend_res.all():
        bucket = buckets.setdefault(
            str(day_value)[:10],
            {"compliant": 0, "non_compliant": 0, "needs_review": 0},
        )
        verdict_key = getattr(verdict_value, "value", verdict_value)
        if verdict_key == Verdict.COMPLIANT.value:
            bucket["compliant"] += count
        elif verdict_key == Verdict.NON_COMPLIANT.value:
            bucket["non_compliant"] += count
        elif verdict_key == Verdict.NEEDS_REVIEW.value:
            bucket["needs_review"] += count

    compliance_trend = []
    if buckets:
        for i in range(6, -1, -1):
            day = today_start - timedelta(days=i)
            # Distinct name from the setdefault-loop `bucket` above: days with
            # no scans are legitimately absent from `buckets`, so this lookup
            # is Optional (mypy assignment error, not a runtime bug).
            day_bucket = buckets.get(day.strftime("%Y-%m-%d"))
            compliance_trend.append({
                "date": day.strftime("%d %b"),
                "compliant": day_bucket["compliant"] if day_bucket else 0,
                "non_compliant": day_bucket["non_compliant"] if day_bucket else 0,
                "needs_review": day_bucket["needs_review"] if day_bucket else 0,
            })

    return {
        "scans_today": scans_today,
        "scans_this_week": scans_week,
        "scans_this_month": scans_month,
        "total_scans": total_scans,
        "average_ocr_confidence": avg_ocr_confidence,
        "verdict_breakdown": {
            "compliant": compliant_count,
            "non_compliant": non_comp_count,
            "needs_review": needs_rev_count
        },
        "top_violated_rules": top_violations,
        "top_non_compliant_manufacturers": top_non_compliant_mfgs,
        "compliance_trend": compliance_trend
    }
