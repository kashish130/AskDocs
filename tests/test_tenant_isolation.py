from collections.abc import Awaitable, Callable
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings

pytestmark = pytest.mark.anyio

Login = Callable[[str], Awaitable[dict[str, str]]]
RLS_DB = "askdocs_rls_test"


async def make_org(client: AsyncClient, headers: dict[str, str], name: str) -> dict[str, Any]:
    resp = await client.post("/orgs", json={"name": name}, headers=headers)
    assert resp.status_code == 201, resp.text
    return dict(resp.json())


async def upload_pdf(
    client: AsyncClient, headers: dict[str, str], org_id: str, body: bytes
) -> dict[str, Any]:
    resp = await client.post(
        f"/orgs/{org_id}/documents",
        headers=headers,
        files={"file": ("doc.txt", body, "text/plain")},
    )
    assert resp.status_code == 201, resp.text
    return dict(resp.json())


async def test_fixture_works(rls_client: AsyncClient) -> None:
    resp = await rls_client.get("/health")

    assert resp.status_code == 200


async def test_user_cannot_list_user_b_docs(rls_client: AsyncClient, rls_login_as: Login) -> None:
    headers_a = await rls_login_as("alice@example.com")
    org_a = await make_org(rls_client, headers_a, "Org A")
    doc_a = await upload_pdf(rls_client, headers_a, org_a["id"], b"alice")

    headers_b = await rls_login_as("bob@example.com")
    org_b = await make_org(rls_client, headers_b, "Org B")
    doc_b = await upload_pdf(rls_client, headers_b, org_b["id"], b"bob")

    resp = await rls_client.get(f"/orgs/{org_a['id']}/documents", headers=headers_a)

    assert resp.status_code == 200
    ids = {d["id"] for d in resp.json()}
    assert ids == {doc_a["id"]}
    assert doc_b["id"] not in ids


async def test_user_a_gets_404_on_user_b_doc(rls_client: AsyncClient, rls_login_as: Login) -> None:
    headers_a = await rls_login_as("alice@example.com")
    org_a = await make_org(rls_client, headers_a, "Org A")

    headers_b = await rls_login_as("bob@example.com")
    org_b = await make_org(rls_client, headers_b, "Org B")
    doc_b = await upload_pdf(rls_client, headers_b, org_b["id"], b"bob")

    resp = await rls_client.get(f"/orgs/{org_a['id']}/documents/{doc_b['id']}", headers=headers_a)

    assert resp.status_code == 404
    assert resp.json() == {"detail": "Document not found"}


async def test_raw_query_without_context_sees_nothing(
    rls_client: AsyncClient, rls_login_as: Login
) -> None:
    headers = await rls_login_as("alice@example.com")
    org = await make_org(rls_client, headers, "Org A")
    await upload_pdf(rls_client, headers, org["id"], b"alice")

    owner_url = make_url(settings.database_url).set(database=RLS_DB)
    app_url = make_url(settings.app_database_url).set(database=RLS_DB)
    owner_engine = create_async_engine(owner_url, poolclass=NullPool)
    app_engine = create_async_engine(app_url, poolclass=NullPool)
    try:
        async with owner_engine.connect() as conn:
            total = (await conn.execute(text("SELECT COUNT(*) FROM documents"))).scalar()
        async with app_engine.connect() as conn:
            visible = (await conn.execute(text("SELECT COUNT(*) FROM documents"))).scalar()
    finally:
        await owner_engine.dispose()
        await app_engine.dispose()

    assert total == 1
    assert visible == 0
