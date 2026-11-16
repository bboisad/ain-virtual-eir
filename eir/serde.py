"""Dataclass <-> plain dict conversion, driven by type hints.

Used for JSON seed files and any storage backend. Missing keys fall back to the
dataclass default, so adding a field with a default never breaks older data.
"""
from __future__ import annotations

import dataclasses
import types
import typing
from enum import Enum
from typing import Any, TypeVar

T = TypeVar("T")


def to_dict(obj: Any) -> Any:
    if dataclasses.is_dataclass(obj):
        return {f.name: to_dict(getattr(obj, f.name)) for f in dataclasses.fields(obj)}
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, list):
        return [to_dict(x) for x in obj]
    if isinstance(obj, dict):
        return {k: to_dict(v) for k, v in obj.items()}
    return obj


def from_dict(cls: type[T], data: Any) -> T:
    return _convert(cls, data)


def _convert(tp: Any, value: Any) -> Any:
    if value is None:
        return None
    origin = typing.get_origin(tp)
    args = typing.get_args(tp)
    if origin in (typing.Union, types.UnionType):  # Optional[X] / X | None
        inner = [a for a in args if a is not type(None)]
        return _convert(inner[0], value)
    if origin is list:
        return [_convert(args[0], v) for v in value]
    if origin is dict:
        return {k: _convert(args[1], v) for k, v in value.items()}
    if isinstance(tp, type) and issubclass(tp, Enum):
        return tp(value)
    if dataclasses.is_dataclass(tp):
        hints = typing.get_type_hints(tp)
        kwargs = {f.name: _convert(hints[f.name], value[f.name])
                  for f in dataclasses.fields(tp) if f.init and f.name in value}
        return tp(**kwargs)
    return value
