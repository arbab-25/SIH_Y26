"""Tests for Rules API — listing, searching, deep-links, schedules."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_list_and_search_rules():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Get all rules
        response = await ac.get("/api/v1/rules")
        assert response.status_code == 200
        rules = response.json()
        assert len(rules) >= 20

        # Search for MRP
        search_resp = await ac.get("/api/v1/rules?q=MRP")
        assert search_resp.status_code == 200
        search_results = search_resp.json()
        assert len(search_results) > 0
        assert any("MRP" in r["full_text"] or "MRP" in (r["title"] or "") for r in search_results)


@pytest.mark.asyncio
async def test_get_rule_deep_link():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Deep link: /rules/rule-6-1-e
        response = await ac.get("/api/v1/rules/rule-6-1-e")
        assert response.status_code == 200
        rule = response.json()
        assert rule["rule_number"] == "rule-6-1-e"
        assert "retail sale price" in rule["full_text"].lower() or "mrp" in rule["full_text"].lower()
        assert rule["source_page"] is not None


@pytest.mark.asyncio
async def test_get_schedules():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Second Schedule
        response = await ac.get("/api/v1/schedules/second_schedule")
        assert response.status_code == 200
        commodities = response.json()
        assert len(commodities) == 19
        assert any(c["commodity"] == "Biscuits" for c in commodities)

        # Rule 7(2) Table-I
        t1_resp = await ac.get("/api/v1/schedules/table_1")
        assert t1_resp.status_code == 200
        t1 = t1_resp.json()
        assert "rows" in t1
        assert len(t1["rows"]) == 5
