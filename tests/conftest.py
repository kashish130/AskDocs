import os
import subprocess
from collections.abc import AsyncIterator, Awaitable, Callable

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings
from app.db import get_db
from app.main import app
from app.models import Base

TEST_DB_URL = make_url(settings.database_url).set(database="askdocs_test")
RLS_TEST_DB = "askdocs_rls_test"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    engine = create_async_engine(TEST_DB_URL, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async def override_get_db() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

    app.dependency_overrides.clear()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def login_as(
    client: AsyncClient,
) -> Callable[[str], Awaitable[dict[str, str]]]:
    async def _login(email: str) -> dict[str, str]:
        creds = {"email": email, "password": "correct-horse-battery"}
        await client.post("/auth/signup", json=creds)
        resp = await client.post("/auth/login", json=creds)
        return {"Authorization": f"Bearer {resp.json()['access_token']}"}

    return _login


async def _recreate_test_db(admin_default_url: str) -> None:
    # Drop the create a fresh RLS test database
    engine = create_async_engine(
        admin_default_url, isolation_level="Autocommit", poolclass=NullPool
    )
    async with engine.connect() as conn:
        await conn.execute(
            text(
                f"Select pg_terminate_backend(pid) from pg_stat_activity"
                f" where datname = '{RLS_TEST_DB}' AND pid <> pg_backend_pid();"
            )
        )
        await conn.execute(text(f"DROP DATABASE IF EXISTS {RLS_TEST_DB}"))
        await conn.execute(text(f"CREATE DATABASE {RLS_TEST_DB}"))
    await engine.dispose()


@pytest.fixture
async def rls_client() -> AsyncIterator[AsyncClient]:
    # 1. Build URLs targeting the RLS test db
    admin_default_url = make_url(settings.database_url).set(database="postgres")
    admin_test_url = make_url(settings.database_url).set(database=RLS_TEST_DB)
    app_test_url = make_url(settings.app_database_url).set(database=RLS_TEST_DB)

    # 2. Fresh DB
    await _recreate_test_db(admin_default_url)
    # 3. Run real migrations on the RLS test db
    env = os.environ.copy()
    env["DATABASE_URL"] = admin_test_url.render_as_string(hide_password=False)
    subprocess.run(["alembic", "upgrade", "head"], env=env, check=True)

    # 4. App engine connects as askdocs_app to the RLS test db(non superuser)
    app_engine = create_async_engine(app_test_url, poolclass=NullPool)
    session_factory = async_sessionmaker(app_engine, expire_on_commit=False)

    async def override_get_db() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

    app.dependency_overrides.clear()
    await app_engine.dispose()


@pytest.fixture
async def rls_login_as(
    rls_client: AsyncClient,
) -> Callable[[str], Awaitable[dict[str, str]]]:
    async def _login(email: str) -> dict[str, str]:
        creds = {"email": email, "password": "correct-horse-battery"}
        await rls_client.post("/auth/signup", json=creds)
        resp = await rls_client.post("/auth/login", json=creds)
        return {"Authorization": f"Bearer {resp.json()['access_token']}"}

    return _login
