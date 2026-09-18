"""Initialize all database tables and seed with demo users + authoritative legal rules."""

import asyncio
import os
import sys

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import engine, Base
# Import all models to register with Base.metadata
from app.models import *  # noqa: F401, F403
from seed.seed_db import main as seed_main


async def init_db():
    print("--- Initializing Database Tables ---")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("[OK] All tables created successfully!")

    print("--- Seeding Data ---")
    await seed_main()
    print("[OK] Database setup complete!")


if __name__ == "__main__":
    asyncio.run(init_db())
