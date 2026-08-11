"""Smoke tests for the foundation phase: confirms the app boots and the
health/readiness endpoints behave as expected. Deliberately minimal — real
feature tests land alongside their feature modules in later phases.
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_liveness_returns_ok(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_readiness_reports_database_status(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health/ready")
    assert response.status_code == 200
    body = response.json()
    assert "database" in body
    assert "redis" in body
