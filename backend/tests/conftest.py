"""Pytest fixtures and configuration."""

import asyncio
import os
import sys

# Tests must never inherit a developer or production Neon URL from .env.
# These variables are set before FastAPI imports application settings.
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test.db"
os.environ["DATABASE_URL_SYNC"] = "sqlite:///./test.db"
os.environ["JWT_SECRET"] = "test-only-secret-not-for-production"

# Ensure backend root is in sys.path
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)



def pytest_configure(config):
    """Create all tables and seed demo data once per test session.

    Runs synchronously via asyncio.run() to avoid pytest-asyncio
    session/function event-loop scope mismatches.
    """
    if config.pluginmanager.hasplugin("asyncio"):
        async def _prepare():
            import json
            import uuid as _uuid

            from app.database import Base, async_session_factory, engine
            from app.models.rule import Rule
            from app.models.schedule_pack_size import SchedulePackSize
            from app.models.user import User, UserRole
            from app.services.auth_service import hash_password

            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.drop_all)
                await conn.run_sync(Base.metadata.create_all)

            async with async_session_factory() as session:
                # Seed rules + schedules from the authoritative seed JSON
                seed_dir = os.path.join(backend_dir, "seed")
                try:
                    with open(os.path.join(seed_dir, "rules.json"), encoding="utf-8") as f:
                        for r in json.load(f):
                            session.add(Rule(
                                id=_uuid.uuid4(),
                                rule_number=r["rule_number"],
                                chapter=r["chapter"],
                                title=r["title"],
                                full_text=r["full_text"],
                                schedule_ref=r.get("schedule_ref"),
                                applies_to=r.get("applies_to"),
                                source_page=r.get("source_page"),
                            ))
                    with open(os.path.join(seed_dir, "schedules.json"), encoding="utf-8") as f:
                        for c in json.load(f).get("second_schedule_commodities", []):
                            session.add(SchedulePackSize(
                                id=_uuid.uuid4(),
                                commodity=c["commodity"],
                                unit=c["unit"],
                                allowed_values=c["allowed_values"],
                                rule_ref=c.get("rule_ref"),
                            ))
                except FileNotFoundError:
                    pass  # seed files optional in constrained environments

                session.add(User(
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
                ))
                session.add(User(
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
                ))
                # Deterministic test inspector matching the fixed UUID used by
                # integration tests for their bearer tokens (guest mode removed:
                # every scan request must carry an Authorization header).
                session.add(User(
                    id=_uuid.UUID("00000000-0000-0000-0000-000000000001"),
                    name="Integration Inspector",
                    email="integration@test.gov.in",
                    mobile="7777777777",
                    password_hash=hash_password("Integration@1234"),
                    role=UserRole.INSPECTOR,
                    designation="Inspector (integration tests)",
                    office="Test Office",
                    is_active=True,
                ))
                await session.commit()

        asyncio.run(_prepare())
