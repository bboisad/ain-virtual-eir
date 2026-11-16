"""Where project files live: outside the venture records, which keep only names, versions and summaries.

Keys look like "<venture id>/<file id>/v<n>.<ext>"; a version's extracted text is stored under the same key + ".txt".
Keys that start with "seed:" are read-only demo files in eir/seed/files/.

Prototype limit: files are stored as plain files on this computer (production would use the university's storage
with access control and encryption). Only team members can open them in the app.
"""
from __future__ import annotations

from pathlib import Path
from typing import Protocol

SEED = "seed:"
SEED_FILES = Path(__file__).resolve().parent / "seed" / "files"


class FileStore(Protocol):
    def put(self, key: str, data: bytes) -> None: ...
    def get(self, key: str) -> bytes: ...  # raises KeyError when missing
    def delete(self, key: str) -> None: ...


def _seed(key: str) -> bytes:
    path = (SEED_FILES / key.removeprefix(SEED)).resolve()
    if SEED_FILES not in path.parents or not path.is_file():
        raise KeyError(key)
    return path.read_bytes()


class LocalFileStore:
    """One file per key under `root`."""

    def __init__(self, root: Path):
        self.root = Path(root).resolve()

    def _path(self, key: str) -> Path:
        path = (self.root / key).resolve()
        if self.root not in path.parents:
            raise KeyError(f"invalid key: {key}")
        return path

    def put(self, key: str, data: bytes) -> None:
        if key.startswith(SEED):
            raise KeyError("demo files are read-only")
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def get(self, key: str) -> bytes:
        if key.startswith(SEED):
            return _seed(key)
        path = self._path(key)
        if not path.is_file():
            raise KeyError(key)
        return path.read_bytes()

    def delete(self, key: str) -> None:
        if not key.startswith(SEED):
            self._path(key).unlink(missing_ok=True)


class MemoryFileStore:
    """For tests and the in-memory demo."""

    def __init__(self):
        self._items: dict[str, bytes] = {}

    def put(self, key: str, data: bytes) -> None:
        if key.startswith(SEED):
            raise KeyError("demo files are read-only")
        self._items[key] = bytes(data)

    def get(self, key: str) -> bytes:
        if key.startswith(SEED):
            return _seed(key)
        return self._items[key]

    def delete(self, key: str) -> None:
        self._items.pop(key, None)
