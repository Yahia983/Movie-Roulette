"""Collection CRUD, item management, and ownership-isolation tests."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_and_get_collection(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    create_response = await client.post(
        "/api/v1/collections", json={"name": "Favorites"}, headers=auth_headers
    )
    assert create_response.status_code == 201
    collection_id = create_response.json()["id"]

    get_response = await client.get(f"/api/v1/collections/{collection_id}", headers=auth_headers)
    assert get_response.status_code == 200
    assert get_response.json()["items"] == []


@pytest.mark.asyncio
async def test_add_and_remove_collection_item(
    client: AsyncClient, seed_titles: dict[str, int], auth_headers: dict[str, str]
) -> None:
    collection = await client.post(
        "/api/v1/collections", json={"name": "Weekend"}, headers=auth_headers
    )
    collection_id = collection.json()["id"]
    title_id = seed_titles["popular-movie"]

    add_response = await client.put(
        f"/api/v1/collections/{collection_id}/items/{title_id}", headers=auth_headers
    )
    assert add_response.status_code == 204

    detail = await client.get(f"/api/v1/collections/{collection_id}", headers=auth_headers)
    assert len(detail.json()["items"]) == 1

    remove_response = await client.delete(
        f"/api/v1/collections/{collection_id}/items/{title_id}", headers=auth_headers
    )
    assert remove_response.status_code == 204

    detail = await client.get(f"/api/v1/collections/{collection_id}", headers=auth_headers)
    assert detail.json()["items"] == []


@pytest.mark.asyncio
async def test_update_collection(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    collection = await client.post(
        "/api/v1/collections", json={"name": "Old Name"}, headers=auth_headers
    )
    collection_id = collection.json()["id"]

    response = await client.patch(
        f"/api/v1/collections/{collection_id}",
        json={"name": "New Name", "is_public": True},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["name"] == "New Name"
    assert response.json()["is_public"] is True


@pytest.mark.asyncio
async def test_delete_collection(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    collection = await client.post(
        "/api/v1/collections", json={"name": "Temp"}, headers=auth_headers
    )
    collection_id = collection.json()["id"]

    delete_response = await client.delete(
        f"/api/v1/collections/{collection_id}", headers=auth_headers
    )
    assert delete_response.status_code == 204

    get_response = await client.get(f"/api/v1/collections/{collection_id}", headers=auth_headers)
    assert get_response.status_code == 404


@pytest.mark.asyncio
async def test_user_cannot_access_another_users_collection(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    """Ownership isolation: a collection ID belonging to user A must 404 —
    not 403 — when user B requests it, so existence itself isn't leaked."""
    owner_collection = await client.post(
        "/api/v1/collections", json={"name": "Private"}, headers=auth_headers
    )
    collection_id = owner_collection.json()["id"]

    other_email = "other" + chr(64) + "example.com"
    await client.post(
        "/api/v1/auth/register",
        json={"email": other_email, "username": "otheruser", "password": "correct-horse-battery"},
    )
    login = await client.post(
        "/api/v1/auth/login",
        json={"identifier": "otheruser", "password": "correct-horse-battery"},
    )
    other_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    response = await client.get(f"/api/v1/collections/{collection_id}", headers=other_headers)
    assert response.status_code == 404
