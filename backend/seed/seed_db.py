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


def _demo_credentials():
    """Demo account credentials from env vars ONLY (no insecure defaults).

    Values set in backend/.env are honored: the seed script loads the same
    dotenv file the application config uses, so a locally-configured .env is
    enough for accounts to exist. Before this, the script read only the process
    environment — DEMO_* lines in .env were silently ignored, no accounts were
    created, and a fresh deployment had no way to sign in.

    Legacy deployments that relied on the old hardcoded demo logins can set:
      DEMO_INSPECTOR_EMAIL=inspector@demo.gov.in  DEMO_INSPECTOR_PASSWORD=Demo@1234
      DEMO_ADMIN_EMAIL=admin@codemaze.app         DEMO_ADMIN_PASSWORD=Admin@1234
    Fresh deployments choose their own. Missing vars skip account seeding with
    a warning rather than inventing a password.
    """
    import os
    try:
        from dotenv import load_dotenv
        load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))
    except ImportError:
        pass  # python-dotenv ships with pydantic-settings; absence is unheard of

    inspector = (
        os.environ.get("DEMO_INSPECTOR_EMAIL", "").strip(),
        os.environ.get("DEMO_INSPECTOR_PASSWORD", ""),
    )
    admin = (
        os.environ.get("DEMO_ADMIN_EMAIL", "").strip(),
        os.environ.get("DEMO_ADMIN_PASSWORD", ""),
    )
    missing = []
    if not inspector[0] or not inspector[1]:
        missing.append("DEMO_INSPECTOR_EMAIL/DEMO_INSPECTOR_PASSWORD")
    if not admin[0] or not admin[1]:
        missing.append("DEMO_ADMIN_EMAIL/DEMO_ADMIN_PASSWORD")
    if missing:
        print("[WARN] Skipping demo accounts; set " + ", ".join(missing) + " to enable.")
    return (
        inspector if (inspector[0] and inspector[1]) else None,
        admin if (admin[0] and admin[1]) else None,
    )


async def seed_users(session):
    """Seed demo accounts from env-configured credentials."""
    inspector, admin = _demo_credentials()

    if inspector:
        result = await session.execute(
            select(User).where(User.email == inspector[0])
        )
        if not result.scalar_one_or_none():
            session.add(User(
                name="Demo Inspector",
                email=inspector[0],
                mobile="9999999999",
                password_hash=hash_password(inspector[1]),
                role=UserRole.INSPECTOR,
                designation="Legal Metrology Inspector",
                office="District Enforcement Office",
                district="Central",
                state="Delhi",
                is_active=True,
            ))
            print(f"[OK] Demo inspector created: {inspector[0]}")

    if admin:
        result = await session.execute(
            select(User).where(User.email == admin[0])
        )
        if not result.scalar_one_or_none():
            session.add(User(
                name="System Administrator",
                email=admin[0],
                mobile="8888888888",
                password_hash=hash_password(admin[1]),
                role=UserRole.ADMIN,
                designation="Chief Enforcement Officer",
                office="Headquarters",
                district="Central",
                state="Delhi",
                is_active=True,
            ))
            print(f"[OK] Admin created: {admin[0]}")


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


async def seed_rule_version(session):
    """Stamp the rule book version scans are attributed to (Phase 3)."""
    import os
    from datetime import datetime
    from app.models.rule_version import RuleVersion

    version_code = os.environ.get("RULE_VERSION_CODE", "LMPC-2011-GSR629E-2018").strip()
    result = await session.execute(
        select(RuleVersion).where(RuleVersion.version_code == version_code)
    )
    existing = result.scalar_one_or_none()
    if not existing:
        session.add(RuleVersion(
            version_code=version_code,
            description="Legal Metrology (Packaged Commodities) Rules, 2011 as amended "
                        "up to GSR 629(E) w.e.f. 01.01.2018 (seeded from RULE_BOOK.pdf).",
            source_document="RULE_BOOK.pdf",
            is_active=True,
            activated_at=datetime.utcnow(),
        ))
        print(f"[OK] Rule version registered: {version_code}")


async def main():
    print("--- Seeding Database ---")
    async with async_session_factory() as session:
        await seed_users(session)
        await seed_rules(session)
        await seed_schedules(session)
        await seed_rule_version(session)
        await session.commit()
    print("--- Seeding Complete ---")


if __name__ == "__main__":
    asyncio.run(main())
