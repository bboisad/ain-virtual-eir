"""Where ventures are stored.

The UI only talks to the `VentureRepository` interface, so the storage can change
(in-memory demo → JSON files → the instructor's database) without touching any page.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol

from .migrate import upgrade
from .models import Venture
from .serde import from_dict, to_dict


class VentureRepository(Protocol):
    def list(self) -> list[Venture]: ...
    def get(self, venture_id: str) -> Venture: ...
    def save(self, venture: Venture) -> None: ...


class InMemoryRepository:
    """Prototype storage: lives for one browser session. Objects are edited in place."""

    def __init__(self, ventures: list[Venture]):
        self._items = {v.id: v for v in ventures}

    def list(self) -> list[Venture]:
        return list(self._items.values())

    def get(self, venture_id: str) -> Venture:
        return self._items[venture_id]

    def save(self, venture: Venture) -> None:
        self._items[venture.id] = venture


class JsonFileRepository:
    """One JSON file per venture — ventures never share a file (project isolation)."""

    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, venture_id: str) -> Path:
        return self.root / f"{venture_id}.json"

    def list(self) -> list[Venture]:
        return [self.get(p.stem) for p in sorted(self.root.glob("*.json"))]

    def get(self, venture_id: str) -> Venture:
        return upgrade(from_dict(Venture, json.loads(self._path(venture_id).read_text(encoding="utf-8"))))

    def save(self, venture: Venture) -> None:
        self._path(venture.id).write_text(json.dumps(to_dict(venture), ensure_ascii=False, indent=2), encoding="utf-8")
