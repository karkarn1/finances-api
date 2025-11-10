"""Integration tests for user endpoints."""

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


@pytest.mark.integration
async def test_get_user_by_id_own_profile(
    client: AsyncClient, test_user: User, auth_headers: dict[str, str]
):
    """Test getting own user profile returns 200."""
    response = await client.get(f"/api/v1/users/{test_user.id}", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == test_user.id
    assert data["username"] == test_user.username
    assert data["email"] == test_user.email
    assert "hashed_password" not in data


@pytest.mark.integration
async def test_get_user_by_id_other_user_forbidden(
    client: AsyncClient, test_user: User, test_superuser: User, auth_headers: dict[str, str]
):
    """Test getting other user profile returns 403 for regular user."""
    response = await client.get(f"/api/v1/users/{test_superuser.id}", headers=auth_headers)

    assert response.status_code == 403


@pytest.mark.integration
async def test_get_user_by_id_as_superuser(
    client: AsyncClient,
    test_user: User,
    test_superuser: User,
    superuser_auth_headers: dict[str, str],
):
    """Test superuser can get any user profile."""
    response = await client.get(f"/api/v1/users/{test_user.id}", headers=superuser_auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == test_user.id
    assert data["username"] == test_user.username


@pytest.mark.integration
async def test_get_user_by_id_without_auth(client: AsyncClient, test_user: User):
    """Test getting user without auth returns 401."""
    response = await client.get(f"/api/v1/users/{test_user.id}")

    assert response.status_code == 401


@pytest.mark.integration
async def test_get_user_by_id_nonexistent(
    client: AsyncClient, superuser_auth_headers: dict[str, str]
):
    """Test getting nonexistent user returns 404 when accessed by superuser."""
    response = await client.get("/api/v1/users/99999", headers=superuser_auth_headers)

    assert response.status_code == 404


@pytest.mark.integration
async def test_list_users_as_regular_user(
    client: AsyncClient, test_user: User, auth_headers: dict[str, str]
):
    """Test listing all users as regular user returns 403."""
    response = await client.get("/api/v1/users/", headers=auth_headers)

    assert response.status_code == 403


@pytest.mark.integration
async def test_list_users_as_superuser(
    client: AsyncClient,
    test_user: User,
    test_superuser: User,
    superuser_auth_headers: dict[str, str],
):
    """Test superuser can list all users."""
    response = await client.get("/api/v1/users/", headers=superuser_auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 2  # At least test_user and test_superuser


@pytest.mark.integration
async def test_list_users_without_auth(client: AsyncClient):
    """Test listing users without auth returns 401."""
    response = await client.get("/api/v1/users/")

    assert response.status_code == 401


@pytest.mark.integration
async def test_list_users_with_pagination(
    client: AsyncClient, test_db: AsyncSession, superuser_auth_headers: dict[str, str]
):
    """Test listing users with skip and limit parameters."""
    response = await client.get(
        "/api/v1/users/?skip=0&limit=1", headers=superuser_auth_headers
    )

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 1


@pytest.mark.integration
async def test_update_own_user_email(
    client: AsyncClient, test_user: User, auth_headers: dict[str, str], test_db: AsyncSession
):
    """Test updating own user email."""
    new_email = "newemail@example.com"
    response = await client.patch(
        f"/api/v1/users/{test_user.id}",
        headers=auth_headers,
        json={"email": new_email},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["email"] == new_email

    # Verify in database
    await test_db.refresh(test_user)
    assert test_user.email == new_email


@pytest.mark.integration
async def test_update_own_user_username(
    client: AsyncClient, test_user: User, auth_headers: dict[str, str], test_db: AsyncSession
):
    """Test updating own username."""
    new_username = "newusername"
    response = await client.patch(
        f"/api/v1/users/{test_user.id}",
        headers=auth_headers,
        json={"username": new_username},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["username"] == new_username

    # Verify in database
    await test_db.refresh(test_user)
    assert test_user.username == new_username


@pytest.mark.integration
async def test_update_own_user_password(
    client: AsyncClient, test_user: User, auth_headers: dict[str, str], test_db: AsyncSession
):
    """Test updating own password."""
    response = await client.patch(
        f"/api/v1/users/{test_user.id}",
        headers=auth_headers,
        json={"password": "NewPassword123"},
    )

    assert response.status_code == 200

    # Verify can login with new password
    login_response = await client.post(
        "/api/v1/auth/login",
        data={
            "username": test_user.username,
            "password": "NewPassword123",
        },
    )
    assert login_response.status_code == 200


@pytest.mark.integration
async def test_update_other_user_forbidden(
    client: AsyncClient, test_user: User, test_superuser: User, auth_headers: dict[str, str]
):
    """Test regular user cannot update other user."""
    response = await client.patch(
        f"/api/v1/users/{test_superuser.id}",
        headers=auth_headers,
        json={"email": "hacked@example.com"},
    )

    assert response.status_code == 403


@pytest.mark.integration
async def test_update_user_as_superuser(
    client: AsyncClient,
    test_user: User,
    superuser_auth_headers: dict[str, str],
    test_db: AsyncSession,
):
    """Test superuser can update any user."""
    response = await client.patch(
        f"/api/v1/users/{test_user.id}",
        headers=superuser_auth_headers,
        json={"email": "updated@example.com"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "updated@example.com"


@pytest.mark.integration
async def test_update_user_to_duplicate_email(
    client: AsyncClient,
    test_user: User,
    test_superuser: User,
    auth_headers: dict[str, str],
):
    """Test updating to duplicate email returns 400."""
    response = await client.patch(
        f"/api/v1/users/{test_user.id}",
        headers=auth_headers,
        json={"email": test_superuser.email},
    )

    assert response.status_code == 400


@pytest.mark.integration
async def test_update_user_to_duplicate_username(
    client: AsyncClient,
    test_user: User,
    test_superuser: User,
    auth_headers: dict[str, str],
):
    """Test updating to duplicate username returns 400."""
    response = await client.patch(
        f"/api/v1/users/{test_user.id}",
        headers=auth_headers,
        json={"username": test_superuser.username},
    )

    assert response.status_code == 400


@pytest.mark.integration
async def test_update_user_without_auth(client: AsyncClient, test_user: User):
    """Test updating user without auth returns 401."""
    response = await client.patch(
        f"/api/v1/users/{test_user.id}",
        json={"email": "newemail@example.com"},
    )

    assert response.status_code == 401


@pytest.mark.integration
async def test_delete_user_as_regular_user_forbidden(
    client: AsyncClient, test_user: User, test_superuser: User, auth_headers: dict[str, str]
):
    """Test regular user cannot delete any user."""
    response = await client.delete(f"/api/v1/users/{test_superuser.id}", headers=auth_headers)

    assert response.status_code == 403


@pytest.mark.integration
async def test_delete_user_as_superuser(
    client: AsyncClient,
    test_user: User,
    superuser_auth_headers: dict[str, str],
    test_db: AsyncSession,
):
    """Test superuser can delete a user."""
    response = await client.delete(
        f"/api/v1/users/{test_user.id}", headers=superuser_auth_headers
    )

    assert response.status_code == 204

    # Verify user is deleted from database
    result = await test_db.execute(select(User).where(User.id == test_user.id))
    deleted_user = result.scalar_one_or_none()
    assert deleted_user is None


@pytest.mark.integration
async def test_delete_nonexistent_user(
    client: AsyncClient, superuser_auth_headers: dict[str, str]
):
    """Test deleting nonexistent user returns 404."""
    response = await client.delete("/api/v1/users/99999", headers=superuser_auth_headers)

    assert response.status_code == 404


@pytest.mark.integration
async def test_delete_user_without_auth(client: AsyncClient, test_user: User):
    """Test deleting user without auth returns 401."""
    response = await client.delete(f"/api/v1/users/{test_user.id}")

    assert response.status_code == 401


@pytest.mark.integration
async def test_regular_user_cannot_promote_self_to_superuser(
    client: AsyncClient, test_user: User, auth_headers: dict[str, str], test_db: AsyncSession
):
    """Test regular user cannot promote themselves to superuser."""
    response = await client.patch(
        f"/api/v1/users/{test_user.id}",
        headers=auth_headers,
        json={"is_superuser": True},
    )

    # Should succeed but is_superuser should not change
    assert response.status_code == 200

    # Verify in database that user is still not a superuser
    await test_db.refresh(test_user)
    assert test_user.is_superuser is False


@pytest.mark.integration
async def test_regular_user_cannot_deactivate_self(
    client: AsyncClient, test_user: User, auth_headers: dict[str, str], test_db: AsyncSession
):
    """Test regular user cannot deactivate themselves."""
    response = await client.patch(
        f"/api/v1/users/{test_user.id}",
        headers=auth_headers,
        json={"is_active": False},
    )

    # Should succeed but is_active should not change
    assert response.status_code == 200

    # Verify in database that user is still active
    await test_db.refresh(test_user)
    assert test_user.is_active is True
