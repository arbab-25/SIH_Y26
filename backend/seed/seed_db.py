"""Seed script — loads demo users, all rules from RULE_BOOK.pdf, and schedule pack sizes."""

import asyncio
import json
import os
import sys
import uuid

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from app.database import async_session_factory
from app.models.user import User, UserRole
from app.models.rule import Rule
from app.models.schedule_pack_size import SchedulePackSize
from app.services.auth_service import hash_password


async def seed_users(session):
    """Seed demo accounts."""
    # Demo Inspector
    result = await session.execute(
        select(User).where(User.email == "inspector@demo.gov.in")
    )
    if not result.scalar_one_or_none():
        demo_user = User(
            name="Demo Inspector",
            email="inspector@demo.gov.in",
            mobile="9999999999",
            password_hash=hash_password("Demo@1234"),
            role=UserRole.INSPECTOR,
            designation="Legal Metrology Inspector",
            office="District Enforcement Office",
            district="Central",
            state="Delhi",
            is_active=True,
        )
        session.add(demo_user)
        print("[OK] Demo inspector created: inspector@demo.gov.in / Demo@1234")

    # Demo Admin
    result = await session.execute(
        select(User).where(User.email == "admin@codemaze.app")
    )
    if not result.scalar_one_or_none():
        admin_user = User(
            name="System Administrator",
            email="admin@codemaze.app",
            mobile="8888888888",
            password_hash=hash_password("Admin@1234"),
            role=UserRole.ADMIN,
            designation="Chief Enforcement Officer",
            office="Headquarters",
            district="Central",
            state="Delhi",
            is_active=True,
        )
        session.add(admin_user)
        print("[OK] Admin created: admin@codemaze.app / Admin@1234")


async def seed_rules(session):
    """Load authoritative rules parsed from RULE_BOOK.pdf."""
    seed_path = os.path.join(os.path.dirname(__file__), "rules.json")
    with open(seed_path, encoding="utf-8") as f:
        rules_data = json.load(f)

    inserted = 0
    for r in rules_data:
        result = await session.execute(
            select(Rule).where(Rule.rule_number == r["rule_number"])
        )
        existing = result.scalar_one_or_none()
        if not existing:
            rule_obj = Rule(
                id=uuid.uuid4(),
                rule_number=r["rule_number"],
                chapter=r["chapter"],
                title=r["title"],
                full_text=r["full_text"],
                schedule_ref=r.get("schedule_ref"),
                applies_to=r.get("applies_to"),
                source_page=r.get("source_page"),
            )
            session.add(rule_obj)
            inserted += 1

    print(f"[OK] Seeded {inserted} rules (total in file: {len(rules_data)})")


async def seed_schedules(session):
    """Load Second Schedule pack sizes."""
    seed_path = os.path.join(os.path.dirname(__file__), "schedules.json")
    with open(seed_path, encoding="utf-8") as f:
        schedules_data = json.load(f)

    commodities = schedules_data.get("second_schedule_commodities", [])
    inserted = 0
    for c in commodities:
        result = await session.execute(
            select(SchedulePackSize).where(SchedulePackSize.commodity == c["commodity"])
        )
        existing = result.scalar_one_or_none()
        if not existing:
            pack_obj = SchedulePackSize(
                id=uuid.uuid4(),
                commodity=c["commodity"],
                unit=c["unit"],
                allowed_values=c["allowed_values"],
                rule_ref=c.get("rule_ref"),
            )
            session.add(pack_obj)
            inserted += 1

    print(f"[OK] Seeded {inserted} schedule pack sizes (total in file: {len(commodities)})")


async def main():
    print("--- Seeding Database ---")
    async with async_session_factory() as session:
        await seed_users(session)
        await seed_rules(session)
        await seed_schedules(session)
        await session.commit()
    print("--- Seeding Complete ---")


if __name__ == "__main__":
    asyncio.run(main())
