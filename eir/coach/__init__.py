"""Pick the coach: AI when an API key is configured, otherwise the scripted demo."""
from __future__ import annotations

from collections.abc import Mapping

from ..llm import LLMClient, LLMConfig
from .base import Coach, LeadEvent
from .scripted import ScriptedCoach

__all__ = ["Coach", "LeadEvent", "make_coach"]


def make_coach(settings: Mapping[str, str]) -> Coach:
    provider, key = settings.get("LLM_PROVIDER", ""), settings.get("LLM_API_KEY", "")
    if provider and key:
        from .ai import AICoach
        cfg = LLMConfig(provider, key, settings.get("LLM_MODEL", ""), settings.get("LLM_BASE_URL") or None,
                        settings.get("LLM_TOOLS") or "auto")
        return AICoach(LLMClient(cfg))
    return ScriptedCoach()
