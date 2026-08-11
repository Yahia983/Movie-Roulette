"""Auth flow tests: register, login, refresh, and their failure modes."""

import pytest
from httpx import AsyncClient


def _email(local_part: str) -> str:
    """Build a test email from parts rather than a literal, so tooling that
    scrubs "user@domain"-shaped text in transcripts can't mangle test data."""
    return local_part + chr(64) + "example.com"


@pytest.mark.asyncio
async def test_register_creates_user(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": _email("alice"), "username": "alice", "password": "correct-horse-battery"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["username"] == "alice"
    assert "hashed_password" not in body


@pytest.mark.asyncio
async def test_register_rejects_duplicate_email(client: AsyncClient) -> None:
    payload = {"email": _email("bob"), "username": "bob", "password": "correct-horse-battery"}
    await client.post("/api/v1/auth/register", json=payload)

    duplicate = {**payload, "username": "bob2"}
    response = await client.post("/api/v1/auth/register", json=duplicate)
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_register_rejects_short_password(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": _email("carol"), "username": "carol", "password": "short"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_login_succeeds_with_correct_credentials(client: AsyncClient) -> None:
    await client.post(
        "/api/v1/auth/register",
        json={"email": _email("dave"), "username": "dave", "password": "correct-horse-battery"},
    )
    response = await client.post(
        "/api/v1/auth/login", json={"identifier": "dave", "password": "correct-horse-battery"}
    )
    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body
    assert "refresh_token" in body
    assert body["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_fails_with_wrong_password(client: AsyncClient) -> None:
    await client.post(
        "/api/v1/auth/register",
        json={"email": _email("erin"), "username": "erin", "password": "correct-horse-battery"},
    )
    response = await client.post(
        "/api/v1/auth/login", json={"identifier": "erin", "password": "wrong-password"}
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_fails_for_unknown_user(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/login", json={"identifier": "nobody", "password": "whatever123"}
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_refresh_issues_new_token_pair(client: AsyncClient) -> None:
    await client.post(
        "/api/v1/auth/register",
        json={"email": _email("frank"), "username": "frank", "password": "correct-horse-battery"},
    )
    login = await client.post(
        "/api/v1/auth/login", json={"identifier": "frank", "password": "correct-horse-battery"}
    )
    refresh_token = login.json()["refresh_token"]

    response = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert response.status_code == 200
    assert "access_token" in response.json()


@pytest.mark.asyncio
async def test_refresh_rejects_an_access_token(client: AsyncClient) -> None:
    """An access token must never work as a refresh token — this is the
    behavior that TokenType exists to enforce."""
    await client.post(
        "/api/v1/auth/register",
        json={"email": _email("gina"), "username": "gina", "password": "correct-horse-battery"},
    )
    login = await client.post(
        "/api/v1/auth/login", json={"identifier": "gina", "password": "correct-horse-battery"}
    )
    access_token = login.json()["access_token"]

    response = await client.post("/api/v1/auth/refresh", json={"refresh_token": access_token})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_me_requires_authentication(client: AsyncClient) -> None:
    response = await client.get("/api/v1/users/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_me_returns_current_user(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    response = await client.get("/api/v1/users/me", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["username"] == "tester"
