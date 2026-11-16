"""The only place that reads the clock, so dates look the same everywhere.

- `today()`     display label used for sessions, events and steps, e.g. "Oct 13"
- `timestamp()` precise UTC time for records that need ordering (messages, notebook revisions)
Due dates entered by users stay ISO dates (YYYY-MM-DD) because they come from a date picker.
"""
from __future__ import annotations

from datetime import date, datetime, timezone


def today() -> str:
    d = date.today()
    return f"{d:%b} {d.day}"


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
