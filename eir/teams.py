"""Prototype projects and invitations. Demo codes are locators, not credentials.

The default repository lives in one browser session. Real invitations need
shared storage and authenticated accounts.
"""
from __future__ import annotations

from hashlib import sha256
from uuid import uuid4

from .access import Account, Role
from .clock import today
from .migrate import CURRENT
from .models import Event, EventKind, Goal, LeadMode, Member, ModeChoice, Stage, Traction, Venture, VentureType
from .modes import recommend
from .repository import VentureRepository


def _founder(account: Account) -> None:
    if account.role != Role.FOUNDER or not account.id or not account.name.strip():
        raise PermissionError("A signed-in founder account is required")


def create_workspace(repo: VentureRepository, creator: Account, name: str, description: str,
                     challenge: str = "", background: str = "Other", stage: Stage = Stage.IDEA,
                     venture_type: VentureType = VentureType.MARKET, ip_sensitive: bool = False,
                     lead_mode: LeadMode = LeadMode.LAUNCH, traction: Traction | None = None,
                     goal: Goal | None = None) -> Venture:
    """Create an immediately usable project with only the signed-in creator and the lead mentor they chose."""
    _founder(creator)
    if not name.strip():
        raise ValueError("Enter a project name.")
    member = Member(f"member-{uuid4().hex}", creator.name, background, creator.id)
    lead_mode = LeadMode(lead_mode)
    choice = ModeChoice(traction, goal, recommend(traction, goal, venture_type), lead_mode, member.id, today())
    venture = Venture(id=f"venture-{uuid4().hex}", name=name.strip(), description=description.strip(),
                      stage=stage, type=venture_type, members=[member], ip_sensitive=ip_sensitive,
                      lead_mode=lead_mode, mode_choice=choice, schema=CURRENT)
    venture.profile.one_liner = description.strip()
    venture.profile.need = challenge.strip()  # the profile stays a draft until a member confirms it
    venture.timeline.append(Event(today(), EventKind.MILESTONE, "Project workspace created", member.id))
    repo.save(venture)
    return venture


def invitation_code(venture: Venture) -> str:
    """Stable non-secret lookup code for this browser-session prototype."""
    return "AIN-" + sha256(venture.id.encode("utf-8")).hexdigest()[:12].upper()


def find_invited_venture(repo: VentureRepository, code: str) -> Venture | None:
    normalized = code.strip().upper()
    if not normalized:
        return None
    return next((v for v in repo.list() if invitation_code(v) == normalized), None)


def join_venture(venture: Venture, account: Account, background: str = "Other") -> Member:
    """Accept an invitation as the current account. Repeat acceptance is harmless."""
    _founder(account)
    existing = venture.member_for_account(account.id)
    if existing:
        return existing
    member = Member(f"member-{uuid4().hex}", account.name, background, account.id)
    venture.members.append(member)
    venture.timeline.append(Event(today(), EventKind.UPDATE,
                                  f"{account.name} accepted the invitation and joined the project", member.id))
    return member


def save_project_details(venture: Venture, by: str, name: str, description: str, stage: Stage,
                         venture_type: VentureType, ip_sensitive: bool) -> None:
    """Project settings (menu): name, description and background labels. Never evidence, never the canvas."""
    if venture.member(by) is None:
        raise PermissionError("Only a project member can edit these details")
    if not name.strip():
        raise ValueError("Enter a project name.")
    venture.name, venture.description = name.strip(), description.strip()
    venture.stage, venture.type, venture.ip_sensitive = Stage(stage), VentureType(venture_type), bool(ip_sensitive)
    venture.profile.one_liner = description.strip()
    venture.timeline.append(Event(today(), EventKind.UPDATE, "Project settings edited", by))


def _set_profile(venture: Venture, **fields: str | None) -> bool:
    """Write the team's own words into the profile; None leaves a field as it is. Returns whether anything changed."""
    changed = False
    for field, value in fields.items():
        if value is None:
            continue
        value = value.strip()
        if getattr(venture.profile, field) != value:
            setattr(venture.profile, field, value)
            venture.profile.notes.pop(field, None)  # an older note on the previous wording no longer applies
            changed = True
    return changed


def _confirm(venture: Venture, by: str) -> None:
    """The member who saves the team's description confirms it (Overview: "confirmed by Alice")."""
    venture.profile.completed_by, venture.profile.completed_on = by, today()


def save_project_intro(venture: Venture, by: str, *, name: str, one_liner: str, customer: str,
                       problem: str) -> None:
    """The Overview's project intro, in the team's words: name, one line, who it serves, what problem it solves.
    Saving confirms it. Never evidence: the Virtual EIR grades evidence in separate records."""
    if venture.member(by) is None:
        raise PermissionError("Only a project member can edit these details")
    if not name.strip():
        raise ValueError("Enter a project name.")
    venture.name = name.strip()
    venture.description = venture.profile.one_liner = " ".join(one_liner.split())
    _set_profile(venture, customer=customer, problem=problem)
    _confirm(venture, by)
    venture.timeline.append(Event(today(), EventKind.UPDATE, "Project intro confirmed", by))


def save_project_essentials(venture: Venture, by: str, *, customer: str | None = None, problem: str | None = None,
                            solution: str | None = None, revenue: str | None = None) -> None:
    """The team's own description of its customer, problem, solution and business model (the Overview's core cards).
    Only the fields given change. Evidence and AI assessments remain separate records."""
    if venture.member(by) is None:
        raise PermissionError("Only a project member can edit these details")
    if _set_profile(venture, customer=customer, problem=problem, solution=solution, revenue=revenue):
        _confirm(venture, by)
        venture.timeline.append(Event(today(), EventKind.UPDATE, "Project essentials edited", by))
