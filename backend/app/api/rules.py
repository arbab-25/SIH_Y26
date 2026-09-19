"""Rules API — Searchable and filterable reference directly from RULE_BOOK.pdf.
Deep-links from all violations to exact quoted legal text per §3 & §7.4.
"""

import json
import os
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from typing import Optional

from app.database import get_db
from app.models.rule import Rule
from app.models.schedule_pack_size import SchedulePackSize
from app.schemas.rule import RuleResponse, SchedulePackSizeResponse

router = APIRouter(tags=["Rule Book"])


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

    # Add highlighted snippet if search query provided
    res = []
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
        res.append(RuleResponse(**r_dict))

    return res


@router.get("/rules/{rule_number}", response_model=RuleResponse)
async def get_rule_by_number(rule_number: str, db: AsyncSession = Depends(get_db)):
    """Deep-link endpoint to get exact rule by rule_number (e.g. rule-6-1-e)."""
    clean_num = rule_number.strip().lower()
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

    return RuleResponse.model_validate(rule)


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
