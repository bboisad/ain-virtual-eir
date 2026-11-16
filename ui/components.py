"""Small reusable UI pieces. Pages build from these instead of writing raw HTML."""
from __future__ import annotations

import base64
import re
from datetime import datetime
from functools import lru_cache
from html import escape
from pathlib import Path

import streamlit as st

from eir.models import (EIR, SYSTEM, Conclusion, ExperimentStatus, HypothesisStatus, Importance, LeadMode, Rung,
                        Venture)

AVATAR_COLORS = ("#216451", "#3b5b92", "#9a5b2e", "#7a4a8c", "#2f7f86")
MENTOR_COLORS = {LeadMode.LAUNCH: "#1f2d2a", LeadMode.OPTIMIZE: "#2f4f7a"}


def inject_css() -> None:
    st.markdown(f"<style>{_css()}</style>", unsafe_allow_html=True)


@lru_cache
def _css() -> str:
    return (Path(__file__).parent / "theme.css").read_text(encoding="utf-8")


@lru_cache
def _avatar_svg(text: str, color: str) -> str:
    size = 13 if len(text) > 2 else 15
    svg = (f"<svg xmlns='http://www.w3.org/2000/svg' width='40' height='40'>"
           f"<circle cx='20' cy='20' r='20' fill='{color}'/>"
           f"<text x='50%' y='54%' dominant-baseline='middle' text-anchor='middle' font-family='Helvetica,Arial' "
           f"font-size='{size}' font-weight='600' fill='white'>{escape(text)}</text></svg>")
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()


def mentor_avatar(mode: LeadMode | None) -> str:
    return _avatar_svg("EIR", MENTOR_COLORS[mode or LeadMode.LAUNCH])


def consultant_avatar(initials: str, color: str) -> str:
    return _avatar_svg(initials, color)


def character_avatar(spec) -> str:
    """A practice character's badge (eir.practice.CharacterSpec)."""
    return _avatar_svg(spec.initials, spec.color)


def score_bars(spec, feedback) -> str:
    """One bar per rubric dimension, 1 to 5 (HTML). Render with st.markdown(..., unsafe_allow_html=True)."""
    rows = []
    for d in spec.rubric:
        if d.id not in feedback.scores:
            continue
        score = feedback.scores[d.id]
        tone = "ok" if score >= 4 else "warn" if score <= 2 else ""
        rows.append(f"<div class='score-row'><span class='score-name'>{escape(d.title)}</span>"
                    f"<span class='score-bar'><span class='score-fill {tone}' style='width:{score * 20}%'></span></span>"
                    f"<b>{score}</b></div>")
    return f"<div class='score-bars'>{''.join(rows)}</div>"


def avatar(v: Venture, author: str, mode: LeadMode | None = None) -> str:
    """Initials avatar (data URI) for a member, or the lead mentor's badge."""
    if author in (EIR, SYSTEM):
        return mentor_avatar(mode or v.lead_mode)
    ids = [m.id for m in v.members]
    m = v.member(author)
    color = AVATAR_COLORS[ids.index(author) % len(AVATAR_COLORS)] if m else "#888888"
    return _avatar_svg(m.initials if m else "?", color)


def md(text: str) -> str:
    """Free text for st.markdown / st.caption: a "$" would otherwise start a formula ("$3 … $1")."""
    return re.sub(r"(?<!\\)\$", r"\\$", text)


def chip(text: str, tone: str = "") -> str:
    """Inline pill (HTML). tone: "" | "ok" | "warn" | "bad". Render with st.markdown(..., unsafe_allow_html=True)."""
    return f"<span class='chip {tone}'>{escape(text)}</span>"


def chips(*items: str) -> None:
    st.markdown(" ".join(items), unsafe_allow_html=True)


RUNG_TONE = {Rung.NONE: "", Rung.ASSERTION: "warn", Rung.SECONDARY: "warn"}  # 3 and up: "ok"


def rung_chip(rung: Rung, prefix: str = "Evidence") -> str:
    """The evidence level as students read it ("Customer statements · Level 3")."""
    rung = Rung(rung)
    return chip(f"{prefix}: {rung.plain}" if prefix else rung.plain, RUNG_TONE.get(rung, "ok"))


# What each level means and what stronger evidence would be: opened from an evidence label, never shown on the page.
LADDER_HELP = {
    Rung.NONE: ("Nothing is recorded for this yet.", "Tell your Virtual EIR what you know, or who you could ask."),
    Rung.ASSERTION: ("Your team believes it; nobody outside the team has confirmed it.",
                     "customers describing it in their own words, in interviews."),
    Rung.SECONDARY: ("Reports, articles, web data or AI estimates support it.",
                     "customers telling you about it themselves."),
    Rung.SAID: ("Customers described it in interviews or surveys.",
                "customers doing something about it: signing up, trying it, switching."),
    Rung.DID: ("Customers acted on it: they signed up, tried it or switched.", "customers paying for it."),
    Rung.PAID: ("Customers paid for it.", "customers coming back and paying again."),
    Rung.RETAINED: ("Customers came back: repeat use or repeat payment.", ""),
}
LADDER_LINE = " · ".join(r.plain for r in Rung if r)


def evidence_popover(rung: Rung, sources=(), key: str | None = None) -> None:
    """An evidence level as a quiet button. It opens what the level means, what stronger evidence would be and the
    records behind it (`sources`: eir.overview.Source)."""
    rung = Rung(rung)
    meaning, stronger = LADDER_HELP[rung]
    with st.popover(rung.plain, type="tertiary", key=key):
        st.markdown(f"**{rung.plain}**  \n{md(meaning)}")
        if stronger:
            st.caption(f"Stronger evidence would be {md(stronger)}")
        shown = [s for s in sources if s and s.text]
        if shown:
            st.markdown("**Where it comes from**")
            for s in shown:
                tail = " · ".join(x for x in (s.rung.plain, "against" if s.against else "", s.source or s.date) if x)
                st.markdown(f"- {md(escape(s.text))}  \n<span class='muted'>{md(escape(tail))}</span>",
                            unsafe_allow_html=True)
        st.caption("All levels: " + LADDER_LINE)


SOURCES = {"team": ("✎", "Team statement"), "records": ("✓", "From records"), "eir": ("✦", "Virtual EIR suggestion")}


def source_tag(kind: str) -> str:
    """Where a block comes from, marked once per block: the team's words, the records, or the Virtual EIR (HTML)."""
    icon, text = SOURCES[kind]
    return f"<span class='src {kind}'>{icon} {text}</span>"


STATUS_TONE = {HypothesisStatus.SUPPORTED: "ok", HypothesisStatus.REFUTED: "bad", HypothesisStatus.TESTING: "warn",
               Conclusion.SUPPORTED: "ok", Conclusion.REFUTED: "bad", ExperimentStatus.RUNNING: "warn",
               ExperimentStatus.CONCLUDED: "ok"}


def status_chip(status) -> str:
    return chip(status.value, STATUS_TONE.get(status, ""))


IMPORTANCE = {Importance.FATAL: "Fatal if wrong", Importance.HIGH: "High stakes", Importance.MEDIUM: "Medium stakes",
              Importance.LOW: "Low stakes", Importance.UNRATED: "Stakes not rated"}


def importance_chip(importance: Importance) -> str:
    importance = Importance(importance)
    return chip(IMPORTANCE[importance], "bad" if importance == Importance.FATAL else "")


def when(timestamp: str) -> str:
    """An ISO timestamp as a short local label, e.g. "Nov 6, 14:05". Date labels ("Oct 5") pass through."""
    try:
        t = datetime.fromisoformat(timestamp).astimezone()
    except ValueError:
        return timestamp
    return f"{t:%b} {t.day}, {t:%H:%M}"


def page_title(title: str, caption: str = "") -> None:
    st.markdown(f"## {escape(title)}")
    if caption:
        st.caption(caption)


def member_row(v: Venture, member_id: str, size: int = 32) -> None:
    m = v.member(member_id)
    a, b = st.columns([1, 8], vertical_alignment="center")
    a.image(avatar(v, member_id), width=size)
    b.markdown(f"**{escape(m.name)}**  \n<span class='muted'>{escape(m.background)}</span>", unsafe_allow_html=True)
