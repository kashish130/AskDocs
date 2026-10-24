import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.anyio


async def auth_headers(client: AsyncClient, email: str) -> dict[str, str]:
    creds = {"email": email, "password": "correct-horse-battery"}
    await client.post("/auth/signup", json=creds)
    resp = await client.post("/auth/login", json=creds)
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def test_create_org_makes_creator_owner(client: AsyncClient) -> None:
    headers = await auth_headers(client, "asha@example.com")

    resp = await client.post("/orgs", json={"name": "Acme"}, headers=headers)

    assert resp.status_code == 201
    assert resp.json()["name"] == "Acme"
    assert resp.json()["role"] == "owner"


async def test_create_org_requires_login(client: AsyncClient) -> None:
    resp = await client.post("/orgs", json={"name": "Acme"})

    assert resp.status_code in (401, 403)


async def test_create_org_blank_name_returns_422(client: AsyncClient) -> None:
    headers = await auth_headers(client, "asha@example.com")

    resp = await client.post("/orgs", json={"name": "   "}, headers=headers)

    assert resp.status_code == 422


async def test_list_orgs_returns_my_orgs(client: AsyncClient) -> None:
    headers = await auth_headers(client, "asha@example.com")
    await client.post("/orgs", json={"name": "Acme"}, headers=headers)

    resp = await client.get("/orgs", headers=headers)

    assert resp.status_code == 200
    assert [o["name"] for o in resp.json()] == ["Acme"]


async def test_list_orgs_hides_other_users_orgs(client: AsyncClient) -> None:
    asha = await auth_headers(client, "asha@example.com")
    ravi = await auth_headers(client, "ravi@example.com")
    await client.post("/orgs", json={"name": "Acme"}, headers=asha)

    resp = await client.get("/orgs", headers=ravi)

    assert resp.json() == []
