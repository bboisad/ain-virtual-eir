"""The Virtual EIR grades the evidence behind an answer; students no longer grade themselves.

`grade()` is the keyword-based grader used by the scripted coach. The AI coach asks the model and falls back
to this when the call fails. Rule shared by both: an answer that does not say how many / who is capped below
"customers said", because the first question of the chain is "be specific".
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .models import Rung

_PATTERNS: list[tuple[Rung, str, re.Pattern]] = [
    (Rung.RETAINED, "repeat use or renewal",
     re.compile(r"\b(repeat|renew\w*|came back|reorder\w*|retention|retained|still using|every (week|month))\b", re.I)),
    (Rung.PAID, "customers paid",
     re.compile(r"\b(paid|pre-?order\w*|purchased|bought|deposits?|paying customers?|revenue of)\b", re.I)),
    (Rung.DID, "customers did something",
     re.compile(r"\b(signed up|sign-?ups?|letters? of intent|LOIs?|joined|switched|wait-?list|used (it|the)|"
                r"downloaded|pilot\w*|committed|registered)\b", re.I)),
    (Rung.SAID, "what customers told you",
     re.compile(r"\b(interview\w*|told (us|me)|said|says|survey\w*|quotes?|talked (to|with)|spoke (to|with)|"
                r"asked \d+)\b", re.I)),
    (Rung.SECONDARY, "desk research",
     re.compile(r"\b(reports?|census|according to|statista|industry|data from|estimates?|research|website|"
                r"article|chatgpt|google|online)\b", re.I)),
]
_SPECIFIC = re.compile(r"\d|\b(one|two|three|four|five|six|seven|eight|nine|ten|dozen|all|none|nobody|no one)\b", re.I)


@dataclass(frozen=True)
class Grade:
    rung: Rung
    why: str


def grade(text: str) -> Grade:
    text = text.strip()
    if not text:
        return Grade(Rung.NONE, "not answered")
    for rung, label, pattern in _PATTERNS:
        if pattern.search(text):
            if rung >= Rung.SAID and not _SPECIFIC.search(text):
                return Grade(Rung(rung - 1), f"mentions {label}, but does not say how many or who")
            return Grade(rung, f"mentions {label}")
    return Grade(Rung.ASSERTION, "no source given: this is your belief")


# ---- experiment methods: what evidence a method can produce, whatever the outcome ----
_STATED = re.compile(r"\b(would|willing to|whether (they|people)(['’]d| would)?)\s+pay", re.I)
_METHOD_PATTERNS: list[tuple[Rung, str, re.Pattern]] = [
    (Rung.RETAINED, "repeat use or renewal",
     re.compile(r"\b(repeat\w*|renew\w*|second (order|purchase)|come back|retention|reorder\w*)\b", re.I)),
    (Rung.PAID, "money changing hands",
     re.compile(r"\b(prepa\w*|pre-?order\w*|deposits?|charg\w*|paid (pilot|trial|listing)s?|purchas\w*|"
                r"pay(s|ing)?\s+(a\s+|the\s+)?(\$|fee|deposit|price))", re.I)),
    (Rung.DID, "customers taking an action",
     re.compile(r"\b(sign(s|ed)?[\s-]?ups?|wait-?list\w*|letters? of intent|LOIs?|register\w*|download\w*|"
                r"pilot\w*|trial\w*|switch\w*|landing page|smoke test)\b", re.I)),
    (Rung.SAID, "what customers tell you",
     re.compile(r"\b(interview\w*|survey\w*|ask\w*|talk\w* (to|with)|call\w*|focus groups?|questionnaires?)\b", re.I)),
    (Rung.SECONDARY, "desk research",
     re.compile(r"\b(desk research|reports?|census|statista|market research|google|estimat\w*)\b", re.I)),
]


def method_rung(method: str) -> Grade:
    """The evidence an experiment's method can produce, whatever the result: a payment test is rung 5 even if nobody
    pays. Asking whether people *would* pay is what they say (rung 3). Keyword fallback for the AI rating."""
    method = method.strip()
    if not method:
        return Grade(Rung.NONE, "no method yet")
    for rung, label, pattern in _METHOD_PATTERNS:
        if rung == Rung.PAID and _STATED.search(method) and not re.search(r"\b(prepa|deposit|pre-?order)", method, re.I):
            continue  # "would you pay $3?" asks for an opinion, not money
        if pattern.search(method):
            return Grade(rung, f"the method observes {label}")
    return Grade(Rung.ASSERTION, "the method does not observe customers; say what they will do or pay")
