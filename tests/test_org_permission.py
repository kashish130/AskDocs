from collections.abc import Awaitable, Callable
from uuid import uuid4

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.anyio

Login = Callable[[str], Awaitable[dict[str, str]]]


async def make_org(client: AsyncClient, headers: dict[str, str]) -> str:
    resp = await client.post("/orgs", json={"name": "Acme"}, headers=headers)
    return str(resp.json()["id"])


async def test_member_can_view_org(client: AsyncClient, login_as: Login) -> None:
    asha = await login_as("asha@example.com")
    org_id = await make_org(client, asha)

    resp = await client.get(f"/orgs/{org_id}", headers=asha)

    assert resp.status_code == 200
    assert resp.json()["role"] == "owner"


async def test_non_member_gets_404(client: AsyncClient, login_as: Login) -> None:
    asha = await login_as("asha@example.com")
    ravi = await login_as("ravi@example.com")
    org_id = await make_org(client, asha)

    resp = await client.get(f"/orgs/{org_id}", headers=ravi)

    assert resp.status_code == 404


async def test_unknown_org_looks_the_same_as_non_member(
    client: AsyncClient, login_as: Login
) -> None:
    asha = await login_as("asha@example.com")
    ravi = await login_as("ravi@example.com")
    org_id = await make_org(client, asha)

    real = await client.get(f"/orgs/{org_id}", headers=ravi)
    fake = await client.get(f"/orgs/{uuid4()}", headers=ravi)

    assert real.status_code == fake.status_code == 404
    assert real.json() == fake.json()


async def test_invalid_org_id_returns_422(client: AsyncClient, login_as: Login) -> None:
    asha = await login_as("asha@example.com")

    resp = await client.get("/orgs/not-a-uuid", headers=asha)

    assert resp.status_code == 422


async def test_org_requires_login(client: AsyncClient) -> None:
    resp = await client.get(f"/orgs/{uuid4()}")

    assert resp.status_code in (401, 403)


async def test_owner_adds_member_who_then_sees_org(client: AsyncClient, login_as: Login) -> None:
    asha = await login_as("asha@example.com")
    ravi = await login_as("ravi@example.com")
    org_id = await make_org(client, asha)

    added = await client.post(
        f"/orgs/{org_id}/members", json={"email": "ravi@example.com"}, headers=asha
    )
    listing = await client.get("/orgs", headers=ravi)

    assert added.status_code == 201
    assert [(o["name"], o["role"]) for o in listing.json()] == [("Acme", "member")]


async def test_member_cannot_add_members(client: AsyncClient, login_as: Login) -> None:
    asha = await login_as("asha@example.com")
    ravi = await login_as("ravi@example.com")
    await login_as("sam@example.com")
    org_id = await make_org(client, asha)
    await client.post(f"/orgs/{org_id}/members", json={"email": "ravi@example.com"}, headers=asha)

    resp = await client.post(
        f"/orgs/{org_id}/members", json={"email": "sam@example.com"}, headers=ravi
    )

    assert resp.status_code == 403


async def test_outsider_cannot_add_themselves(client: AsyncClient, login_as: Login) -> None:
    asha = await login_as("asha@example.com")
    ravi = await login_as("ravi@example.com")
    org_id = await make_org(client, asha)

    resp = await client.post(
        f"/orgs/{org_id}/members", json={"email": "ravi@example.com"}, headers=ravi
    )
    listing = await client.get("/orgs", headers=ravi)

    assert resp.status_code == 404
    assert listing.json() == []


async def test_add_unknown_email_returns_404(client: AsyncClient, login_as: Login) -> None:
    asha = await login_as("asha@example.com")
    org_id = await make_org(client, asha)

    resp = await client.post(
        f"/orgs/{org_id}/members", json={"email": "nobody@example.com"}, headers=asha
    )

    assert resp.status_code == 404


async def test_add_same_member_twice_returns_409(client: AsyncClient, login_as: Login) -> None:
    asha = await login_as("asha@example.com")
    await login_as("ravi@example.com")
    org_id = await make_org(client, asha)
    body = {"email": "ravi@example.com"}
    await client.post(f"/orgs/{org_id}/members", json=body, headers=asha)

    resp = await client.post(f"/orgs/{org_id}/members", json=body, headers=asha)

    assert resp.status_code == 409


async def test_list_members_shows_everyone(client: AsyncClient, login_as: Login) -> None:
    asha = await login_as("asha@example.com")
    await login_as("ravi@example.com")
    org_id = await make_org(client, asha)
    await client.post(f"/orgs/{org_id}/members", json={"email": "ravi@example.com"}, headers=asha)

    resp = await client.get(f"/orgs/{org_id}/members", headers=asha)

    assert {m["email"] for m in resp.json()} == {"asha@example.com", "ravi@example.com"}


async def test_non_member_cannot_list_members(client: AsyncClient, login_as: Login) -> None:
    asha = await login_as("asha@example.com")
    ravi = await login_as("ravi@example.com")
    org_id = await make_org(client, asha)

    resp = await client.get(f"/orgs/{org_id}/members", headers=ravi)

    assert resp.status_code == 404
