import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient

from app.main import app

client = TestClient(app)


# def test_health_returns_ok() -> None:
#     response = client.get("/health")

#     assert response.status_code == 200
#     assert response.json() == {"status": "ok", "database": "up"}


pytestmark = pytest.mark.anyio


async def test_health_returns_ok(client: AsyncClient) -> None:
    response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "up"}
