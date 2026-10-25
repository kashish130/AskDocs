from pathlib import Path

import pytest

from app.storage import LocalStorage

pytestmark = pytest.mark.anyio


@pytest.fixture
def storage(tmp_path: Path) -> LocalStorage:
    return LocalStorage(tmp_path)


async def test_put_then_get_returns_same_bytes(storage: LocalStorage) -> None:
    await storage.put("org1/doc1", b"hello")

    assert await storage.get("org1/doc1") == b"hello"


async def test_put_creates_nested_folders(storage: LocalStorage, tmp_path: Path) -> None:
    await storage.put("org1/doc1/file.txt", b"x")

    assert (tmp_path / "org1" / "doc1" / "file.txt").exists()


async def test_put_overwrites_existing_file(storage: LocalStorage) -> None:
    await storage.put("k", b"old")
    await storage.put("k", b"new")

    assert await storage.get("k") == b"new"


async def test_get_missing_key_raises(storage: LocalStorage) -> None:
    with pytest.raises(FileNotFoundError):
        await storage.get("nope")


async def test_delete_removes_the_file(storage: LocalStorage) -> None:
    await storage.put("k", b"x")
    await storage.delete("k")

    with pytest.raises(FileNotFoundError):
        await storage.get("k")


async def test_delete_missing_key_is_fine(storage: LocalStorage) -> None:
    await storage.delete("never-existed")


@pytest.mark.parametrize("bad_key", ["../escape", "a/../../escape", "/etc/passwd", "", "."])
async def test_bad_keys_are_rejected(storage: LocalStorage, bad_key: str) -> None:
    with pytest.raises(ValueError):
        await storage.put(bad_key, b"x")
