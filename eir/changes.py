"""Every change to a record the lead mentor maintains is logged, so it can be shown and undone.

The lead mentor updates the Overview and the Action Plan directly; each update is shown in the chat with an Undo
button. `track()` snapshots one record before and after a block of code; if it changed, a Change is appended to
`v.changes`. Undo works per group (one mentor action), all or nothing, and only while none of those records changed
since; otherwise the student edits the record directly. Students' own edits are logged too but are not undone here.
"""
from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from .clock import timestamp
from .models import (EIR, Answer, CanvasEntry, Change, Diagnosis, Experiment, Focus, Hypothesis, LensGrade,
                     NextStep, RecordKind, Venture)
from .serde import from_dict, to_dict


@dataclass(frozen=True)
class _Accessor:
    cls: type
    get: Callable[[Venture, str], Any]  # the current record, or None
    put: Callable[[Venture, str, Any, int], None]  # record None removes it; int = list position to re-insert
    index: Callable[[Venture, str], int]  # list position, or -1


def _in_list(attr: str, cls: type) -> _Accessor:
    def index(v: Venture, rid: str) -> int:
        return next((i for i, x in enumerate(getattr(v, attr)) if x.id == rid), -1)

    def get(v: Venture, rid: str) -> Any:
        i = index(v, rid)
        return getattr(v, attr)[i] if i >= 0 else None

    def put(v: Venture, rid: str, record: Any, position: int) -> None:
        items, i = getattr(v, attr), index(v, rid)
        if record is None:
            if i >= 0:
                del items[i]
        elif i >= 0:
            items[i] = record
        else:
            items.insert(position if 0 <= position <= len(items) else len(items), record)

    return _Accessor(cls, get, put, index)


def _in_dict(attr: str, cls: type) -> _Accessor:
    def put(v: Venture, key: str, record: Any, _position: int) -> None:
        if record is None:
            getattr(v, attr).pop(key, None)
        else:
            getattr(v, attr)[key] = record

    return _Accessor(cls, lambda v, key: getattr(v, attr).get(key), put, lambda v, key: -1)


def _single(attr: str, cls: type) -> _Accessor:
    def put(v: Venture, _key: str, record: Any, _position: int) -> None:
        setattr(v, attr, record if record is not None else cls())

    return _Accessor(cls, lambda v, _key: getattr(v, attr), put, lambda v, _key: -1)


ACCESSORS: dict[RecordKind, _Accessor] = {
    RecordKind.ASSUMPTION: _in_list("hypotheses", Hypothesis),
    RecordKind.EXPERIMENT: _in_list("experiments", Experiment),
    RecordKind.TASK: _in_list("next_steps", NextStep),
    RecordKind.CANVAS: _in_dict("canvas", CanvasEntry),
    RecordKind.LENS: _in_dict("lenses", LensGrade),
    RecordKind.ANSWER: _in_dict("answers", Answer),
    RecordKind.FOCUS: _single("focus", Focus),
    RecordKind.DIAGNOSIS: _single("diagnosis", Diagnosis),
}


def snapshot(v: Venture, kind: RecordKind, record_id: str) -> dict | None:
    record = ACCESSORS[kind].get(v, record_id)
    return None if record is None else to_dict(record)


def new_group() -> str:
    """One group = one mentor action or one student action. Undo works per group."""
    return f"G-{uuid4().hex[:10]}"


@contextmanager
def track(v: Venture, kind: RecordKind, record_id: str, *, by: str, group: str = "", summary: str = "",
          source: str = "") -> Iterator[None]:
    """Log what the enclosed code changes in one record. Nothing is logged if the record did not change."""
    acc = ACCESSORS[kind]
    before, position = snapshot(v, kind, record_id), acc.index(v, record_id)
    yield
    after = snapshot(v, kind, record_id)
    if before != after:
        v.changes.append(Change(group=group or new_group(), kind=kind, record_id=record_id, summary=summary,
                                before=before, after=after,
                                position=position if position >= 0 else acc.index(v, record_id),
                                by=by, source=source))


def changes_in(v: Venture, group: str) -> list[Change]:
    """The changes of one group that are not undone yet, oldest first."""
    return [c for c in v.changes if c.group == group and not c.undone_at]


def undo_problem(v: Venture, group: str) -> Exception | None:
    """Why this group cannot be undone (as the exception undo would raise), or None if it can."""
    cs = changes_in(v, group)
    if not cs:
        return ValueError("Nothing to undo")
    if any(c.by != EIR for c in cs):
        return PermissionError("Only the mentor's updates can be undone. Edit your own changes directly.")
    expected: dict[tuple[RecordKind, str], dict | None] = {}
    for c in reversed(cs):  # walking back from the newest change, each record must still look as the change left it
        key = (c.kind, c.record_id)
        current = expected[key] if key in expected else snapshot(v, c.kind, c.record_id)
        if current != c.after:
            return ValueError("This record changed after the mentor's update. Edit it directly instead.")
        expected[key] = c.before
    return None


def undo_group(v: Venture, group: str, by: str) -> list[Change]:
    """Undo every change of one mentor action, all or nothing."""
    problem = undo_problem(v, group)
    if problem is not None:
        raise problem
    undone = changes_in(v, group)
    for c in reversed(undone):
        acc = ACCESSORS[c.kind]
        acc.put(v, c.record_id, None if c.before is None else from_dict(acc.cls, c.before), c.position)
        c.undone_by, c.undone_at = by, timestamp()
    return undone
