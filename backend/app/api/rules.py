"""Rules API — Searchable and filterable reference directly from RULE_BOOK.pdf.
Deep-links from all violations to exact quoted legal text per §3 & §7.4.
"""

import json
import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.rule import Rule
from app.schemas.rule import RuleResponse
from app.services.redis_service import cache_get, cache_set

router = APIRouter(tags=["Rule Book"])

# The rule book is amended rarely; cache full listing + single rules for an
# hour. cache_get/set no-op when Redis isn't configured, so local dev and the
# Redis-less free tier are unaffected.
RULES_CACHE_KEY = "rules:all"
RULE_CACHE_KEY_PREFIX = "rules:one:"
RULES_TTL_SECONDS = 3600


@router.get("/rules", response_model=list[RuleResponse])
async def list_rules(
    q: Optional[str] = Query(None, description="Search query across rules text or title"),
    chapter: Optional[str] = Query(None, description="Filter by chapter"),
    db: AsyncSession = Depends(get_db)
):
    """Search and filter the official Legal Metrology Rules 2011."""
    stmt = select(Rule)

    if chapter:
        stmt = stmt.where(Rule.chapter.ilike(f"%{chapter}%"))

    if q:
        search_filter = or_(
            Rule.full_text.ilike(f"%{q}%"),
            Rule.title.ilike(f"%{q}%"),
            Rule.rule_number.ilike(f"%{q}%")
        )
        stmt = stmt.where(search_filter)

    result = await db.execute(stmt)
    rules = result.scalars().all()

    res = []
    # Add highlighted snippet if search query provided (cache the serialized
    # response only for the unfiltered call; search/chapter queries stay live).
    for r in rules:
        r_dict = {
            "id": r.id,
            "rule_number": r.rule_number,
            "chapter": r.chapter,
            "title": r.title,
            "full_text": r.full_text,
            "schedule_ref": r.schedule_ref,
            "applies_to": r.applies_to,
            "source_page": r.source_page,
            "highlight": None
        }
        if q and q.lower() in r.full_text.lower():
            idx = r.full_text.lower().find(q.lower())
            start = max(0, idx - 40)
            end = min(len(r.full_text), idx + len(q) + 60)
            snippet = r.full_text[start:end].replace("\n", " ")
            r_dict["highlight"] = f"...{snippet}..."
        res.append(RuleResponse.model_validate(r_dict))

    return res


@router.get("/rules/cached-all", response_model=list[RuleResponse])
async def list_rules_cached(db: AsyncSession = Depends(get_db)):
    """Redis-cached variant of the full rule listing (Phase 2 demonstration).

    Identical payload to GET /rules with no filters; the cache is checked
    before Postgres. A cache miss or Redis outage simply falls through to the
    database, so this endpoint is always at least as available as /rules.
    """
    cached = cache_get(RULES_CACHE_KEY)
    if cached is not None:
        return [RuleResponse(**r) for r in cached]

    result = await db.execute(select(Rule))
    rules = result.scalars().all()
    serialized = [RuleResponse.model_validate(r).model_dump(mode="json") for r in rules]
    cache_set(RULES_CACHE_KEY, serialized, ttl=RULES_TTL_SECONDS)
    return [RuleResponse(**r) for r in serialized]


@router.get("/rules/{rule_number}", response_model=RuleResponse)
async def get_rule_by_number(rule_number: str, db: AsyncSession = Depends(get_db)):
    """Deep-link endpoint to get exact rule by rule_number (e.g. rule-6-1-e)."""
    clean_num = rule_number.strip().lower()

    # Violations deep-link here on every scan detail view; cache per rule.
    cache_key = RULE_CACHE_KEY_PREFIX + clean_num
    cached = cache_get(cache_key)
    if cached is not None:
        return RuleResponse(**cached)

    stmt = select(Rule).where(Rule.rule_number == clean_num)
    result = await db.execute(stmt)
    rule = result.scalar_one_or_none()

    if not rule:
        # Try matching without prefix or case-insensitive
        stmt2 = select(Rule).where(Rule.rule_number.ilike(f"%{clean_num}%"))
        result2 = await db.execute(stmt2)
        rule = result2.scalar_one_or_none()

    if not rule:
        raise HTTPException(status_code=404, detail=f"Rule '{rule_number}' not found")

    response = RuleResponse.model_validate(rule)
    cache_set(cache_key, response.model_dump(mode="json"), ttl=RULES_TTL_SECONDS)
    return response


@router.get("/schedules/{name}")
async def get_schedule_by_name(name: str):
    """Retrieve structured schedule data (e.g. rule_7_2_table_1, second_schedule_commodities, etc.)."""
    backend_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    schedules_path = os.path.join(backend_root, "seed", "schedules.json")
    if not os.path.exists(schedules_path):
        raise HTTPException(status_code=404, detail=f"Schedules file not found at {schedules_path}")

    with open(schedules_path, encoding="utf-8") as f:
        schedules_data = json.load(f)

    # Normalize lookup
    norm_name = name.strip().lower().replace("-", "_")
    if norm_name in schedules_data:
        return schedules_data[norm_name]
    elif "second_schedule" in norm_name:
        return schedules_data.get("second_schedule_commodities", [])
    elif "table_1" in norm_name or "table1" in norm_name:
        return schedules_data.get("rule_7_2_table_1", {})
    elif "fifth" in norm_name:
        return schedules_data.get("fifth_schedule_sampling", {})

    return schedules_data
