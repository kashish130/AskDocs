from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
import pytest
from httpx import AsyncClient

from app.config import settings

pytestmark = pytest.mark.anyio

CREDS = {"email": "asha@example.com", "password": "correct-horse-battery"}


async def login_token(client: AsyncClient) -> str:
    await client.post("/auth/signup", json=CREDS)
    resp = await client.post("/auth/login", json=CREDS)
    return str(resp.json()["access_token"])


async def test_signup_succeeds_and_hides_password(client: AsyncClient) -> None:
    resp = await client.post("/auth/signup", json=CREDS)

    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == CREDS["email"]
    assert "password" not in body
    assert "password_hash" not in body


async def test_signup_duplicate_email_returns_409(client: AsyncClient) -> None:
    await client.post("/auth/signup", json=CREDS)
    resp = await client.post("/auth/signup", json=CREDS)

    assert resp.status_code == 400


async def test_signup_short_password_returns_422(client: AsyncClient) -> None:
    resp = await client.post("/auth/signup", json={**CREDS, "password": "short"})

    assert resp.status_code == 422


async def test_login_wrong_password_returns_401(client: AsyncClient) -> None:
    await client.post("/auth/signup", json=CREDS)
    resp = await client.post("/auth/login", json={**CREDS, "password": "totally-wrong-pass"})

    assert resp.status_code == 401


async def test_login_unknown_email_returns_401(client: AsyncClient) -> None:
    resp = await client.post("/auth/login", json=CREDS)

    assert resp.status_code == 401


async def test_me_with_valid_token_returns_user(client: AsyncClient) -> None:
    token = await login_token(client)
    resp = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert resp.status_code == 200
    assert resp.json()["email"] == CREDS["email"]


async def test_me_without_token_is_rejected(client: AsyncClient) -> None:
    resp = await client.get("/auth/me")

    assert resp.status_code in (401, 403)


async def test_me_with_expired_token_returns_401(client: AsyncClient) -> None:
    expired = jwt.encode(
        {"sub": str(uuid4()), "exp": datetime.now(UTC) - timedelta(minutes=1)},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    resp = await client.get("/auth/me", headers={"Authorization": f"Bearer {expired}"})

    assert resp.status_code == 401


async def test_me_with_tampered_token_returns_401(client: AsyncClient) -> None:
    token = await login_token(client)
    tampered = token[:-1] + ("A" if token[-1] != "A" else "B")
    resp = await client.get("/auth/me", headers={"Authorization": f"Bearer {tampered}"})

    assert resp.status_code == 401
