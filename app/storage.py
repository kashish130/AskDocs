import asyncio
from pathlib import Path
from typing import Protocol

from app.config import settings


class Storage(Protocol):
    async def put(self, key: str, data: bytes) -> None: ...

    async def get(self, key: str) -> bytes: ...

    async def delete(self, key: str) -> None: ...


def _write_file(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


class LocalStorage:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def _path_for(self, key: str) -> Path:
        path = (self.root / key).resolve()
        if path == self.root or not path.is_relative_to(self.root):
            raise ValueError("Invalid storage key")
        return path

    async def put(self, key: str, data: bytes) -> None:
        path = self._path_for(key)
        await asyncio.to_thread(_write_file, path, data)

    async def get(self, key: str) -> bytes:
        path = self._path_for(key)
        return await asyncio.to_thread(path.read_bytes)

    async def delete(self, key: str) -> None:
        path = self._path_for(key)
        await asyncio.to_thread(path.unlink, missing_ok=True)


def get_storage() -> Storage:
    return LocalStorage(Path(settings.storage_dir))
