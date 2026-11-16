"""Upgrade older venture data on load. Idempotent: running it twice changes nothing.

Schema 1 → 2 (v0.15 → v0.16, multi-mentor design):
- canvas: the 4-level label becomes a rung (statement / hypothesis → 1, evidence-backed → 3), to be re-graded;
- assumptions: the free-text evidence becomes an evidence item (direction unknown);
- assumptions: the free-text test becomes a DRAFT experiment with empty criteria, so it cannot start until the team
  writes down what result supports or refutes the assumption.
Legacy fields stay in place so re-saving loses nothing.
"""
from __future__ import annotations

from .models import Direction, Evidence, EvidenceItem, Experiment, Rung, Venture

CURRENT = 2
_LABEL_RUNG = {Evidence.STATEMENT: Rung.ASSERTION, Evidence.HYPOTHESIS: Rung.ASSERTION, Evidence.EVIDENCE: Rung.SAID}


def upgrade(v: Venture) -> Venture:
    if v.schema >= CURRENT:
        return v
    for e in v.canvas.values():
        if e.text and e.rung == Rung.NONE and e.status in _LABEL_RUNG:
            e.rung = _LABEL_RUNG[e.status]
            e.why = e.why or f"Converted from the earlier label \"{e.status.value}\"; the mentor will re-grade it."
    for h in v.hypotheses:
        if h.evidence and not h.evidence_items:
            h.evidence_items.append(EvidenceItem(h.evidence, Direction.UNCLEAR, h.rung, h.source))
        if h.test and not any(x.assumption_id == h.id for x in v.experiments):
            v.experiments.append(Experiment(assumption_id=h.id, method=h.test, created_by="migrated"))
    v.schema = CURRENT
    return v
