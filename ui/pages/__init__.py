"""Workspace pages, in top-navigation order. To add a page: create a module with `render(ctx)` and add one line here.
Everything else a team does (members, human EIR, settings) is a dialog in the ⋯ menu (ui/menu.py)."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from . import action_plan, mentor_chat, overview, practice


@dataclass(frozen=True)
class Page:
    title: str
    icon: str  # Material icon shortcode
    render: Callable


PAGES: list[Page] = [
    Page("Mentor", ":material/forum:", mentor_chat.render),
    Page("Overview", ":material/dashboard:", overview.render),
    Page("Action Plan", ":material/checklist:", action_plan.render),
    Page("Practice", ":material/record_voice_over:", practice.render),
]
BY_TITLE = {p.title: p for p in PAGES}
