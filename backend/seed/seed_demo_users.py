"""Seed demo accounts + rule versions — passwords come from env vars only.

Replaces the hardcoded demo credentials that used to live in this script and
the README (Phase 3 security requirement). Nothing is printed except account
emails; passwords never appear in output or logs.

Required env vars (no defaults — the script refuses to invent credentials):
    DEMO_INSPECTOR_EMAIL / DEMO_INSPECTOR_PASSWORD
    DEMO_ADMIN_EMAIL / DEMO_ADMIN_PASSWORD
    RULE_VERSION_CODE (optional, default stamps the current rule book)

Run:  python seed/seed_demo_users.py
"""

import asyncio
import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select

from app.database import async_session_factory
from app.models.user import User, UserRole
from app.models.rule_version import RuleVersion
from app.services.auth_service import hash_password


def _required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        print(f"ERROR: environment variable {name} is required (no insecure default).")
        sys.exit(2)
    return value


async def seed_users(session) -> dict:
    """Create the demo accounts named by env vars. Returns {role: email}."""
    created = {}

    inspector_email = _required_env("DEMO_INSPECTOR_EMAIL")
    inspector_password = _required_env("DEMO_INSPECTOR_PASSWORD")
    admin_email = _required_env("DEMO_ADMIN_EMAIL")
    admin_password = _required_env("DEMO_ADMIN_PASSWORD")

    result = await session.execute(select(User).where(User.email == inspector_email))
    if not result.scalar_one_or_none():
        session.add(User(
            name="Demo Inspector",
            email=inspector_email,
            mobile="9999999999",
            password_hash=hash_password(inspector_password),
            role=UserRole.INSPECTOR,
            designation="Legal Metrology Inspector",
            office="District Enforcement Office",
            district="Central",
            state="Delhi",
            is_active=True,
        ))
        created["inspector"] = inspector_email

    result = await session.execute(select(User).where(User.email == admin_email))
    if not result.scalar_one_or_none():
        session.add(User(
            name="System Administrator",
            email=admin_email,
            mobile="8888888888",
            password_hash=hash_password(admin_password),
            role=UserRole.ADMIN,
            designation="Chief Enforcement Officer",
            office="Headquarters",
            district="Central",
            state="Delhi",
            is_active=True,
        ))
        created["admin"] = admin_email

    return created


async def seed_rule_version(session) -> str:
    """Stamp the current rule book with a version row; activate it."""
    version_code = os.environ.get("RULE_VERSION_CODE", "LMPC-2011-GSR629E-2018").strip()

    result = await session.execute(
        select(RuleVersion).where(RuleVersion.version_code == version_code)
    )
    existing = result.scalar_one_or_none()
    if existing:
        if not existing.is_active:
            existing.is_active = True
            existing.activated_at = existing.activated_at or datetime.utcnow()
        return version_code

    session.add(RuleVersion(
        version_code=version_code,
        description="Legal Metrology (Packaged Commodities) Rules, 2011 as amended "
                    "up to GSR 629(E) w.e.f. 01.01.2018 (seeded from RULE_BOOK.pdf).",
        source_document="RULE_BOOK.pdf",
        is_active=True,
        activated_at=datetime.utcnow(),
    ))
    return version_code


async def main() -> None:
    print("--- Seeding demo accounts + rule version (env-driven) ---")
    async with async_session_factory() as session:
        created = await seed_users(session)
        version = await seed_rule_version(session)
        await session.commit()

    for role, email in created.items():
        print(f"[OK] {role} account created: {email}")
    if not created:
        print("[OK] demo accounts already present; nothing created")
    print(f"[OK] active rule version: {version}")
    print("--- Seeding complete ---")


if __name__ == "__main__":
    asyncio.run(main())
