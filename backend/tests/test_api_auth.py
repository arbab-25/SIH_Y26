"""Tests for Auth API — register, login (email and mobile), profile, roles."""

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.database import async_session_factory
from app.services.auth_service import hash_password
from app.models.user import User, UserRole
import uuid


@pytest.mark.asyncio
async def test_health():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ("healthy", "degraded")
        assert "version" in data


@pytest.mark.asyncio
async def test_login_demo_inspector():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Login with email
        response = await ac.post("/api/v1/auth/login", json={
            "identifier": "inspector@demo.gov.in",
            "password": "Demo@1234"
        })
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert data["token"]["access_token"] != ""
        assert data["user"]["email"] == "inspector@demo.gov.in"
        assert data["user"]["role"] == "INSPECTOR"

        token = data["token"]["access_token"]

        # Get /me with bearer token
        me_resp = await ac.get("/api/v1/auth/me", headers={
            "Authorization": f"Bearer {token}"
        })
        assert me_resp.status_code == 200
        assert me_resp.json()["name"] == "Demo Inspector"


@pytest.mark.asyncio
async def test_login_mobile():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Login using 10-digit mobile number
        response = await ac.post("/api/v1/auth/login", json={
            "identifier": "9999999999",
            "password": "Demo@1234"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["user"]["email"] == "inspector@demo.gov.in"


@pytest.mark.asyncio
async def test_register_new_user():
    random_id = str(uuid.uuid4())[:8]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/api/v1/auth/register", json={
            "name": f"Officer {random_id}",
            "email": f"officer_{random_id}@codemaze.app",
            "mobile": "9876543210",
            "password": "Password@123",
            "role": "INSPECTOR"
        })
        # If mobile already exists or registered
        assert response.status_code in (201, 400)
