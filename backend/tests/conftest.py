"""Pytest fixtures and configuration."""

import sys
import os

# Tests must never inherit a developer or production Neon URL from .env.
# These variables are set before FastAPI imports application settings.
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test.db"
os.environ["DATABASE_URL_SYNC"] = "sqlite:///./test.db"
os.environ["JWT_SECRET"] = "test-only-secret-not-for-production"

# Ensure backend root is in sys.path
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)
