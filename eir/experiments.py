"""Validation experiments: agree what result supports or refutes an assumption before you start; the mentor judges.

- `create` / `edit`: a DRAFT can change freely.
- `start`: needs a method, its rated evidence level and both criteria. From then on the criteria are locked.
- `stop`: ends it without a conclusion; with `replace` a new DRAFT copy opens, so the team can change the criteria.
- `record_result`: the team reports what happened (RUNNING only).
- `judge`: the mentor compares the result with the criteria agreed in advance. The evidence rung comes from the
  METHOD, whatever the outcome: zero payers in a payment test is rung 5 evidence against, and the assumption is Refuted.
Completing a task never concludes an experiment.
"""
from __future__ import annotations

from . import changes, records
from .clock import today
from .models import (EIR, Conclusion, Direction, Experiment, ExperimentStatus, HypothesisStatus, RecordKind, Rung,
                     Venture)
from .modes import lens_ids

EDITABLE = ("method", "supported_if", "refuted_if", "method_rung", "owner", "deadline")
_DIRECTION = {Conclusion.SUPPORTED: Direction.FOR, Conclusion.REFUTED: Direction.AGAINST,
              Conclusion.INCONCLUSIVE: Direction.UNCLEAR}
_STATUS = {Conclusion.SUPPORTED: HypothesisStatus.SUPPORTED, Conclusion.REFUTED: HypothesisStatus.REFUTED,
           Conclusion.INCONCLUSIVE: HypothesisStatus.INCONCLUSIVE}


def _get(v: Venture, eid: str) -> Experiment:
    x = v.experiment(eid)
    if x is None:
        raise ValueError("This experiment does not exist")
    return x


def create(v: Venture, *, by: str, method: str, assumption_id: str = "", lens: str = "", supported_if: str = "",
           refuted_if: str = "", method_rung: Rung = Rung.NONE, owner: str = "team", deadline: str = "",
           replaces: str = "", group: str = "", source: str = "") -> Experiment:
    if not assumption_id and not lens:
        raise ValueError("An experiment tests an assumption (or, with the Optimize mentor, a lens)")
    if assumption_id and v.hypothesis(assumption_id) is None:
        raise ValueError(f"Unknown assumption {assumption_id}")
    if lens and lens not in lens_ids():
        raise ValueError(f"Unknown lens: {lens}")
    method = method.strip()
    if not method:
        raise ValueError("Describe the method: who, how many, and what you will ask them to do")
    if owner != "team" and v.member(owner) is None:
        raise ValueError("The owner must be a team member or the team")
    x = Experiment(assumption_id=assumption_id, lens=lens, method=method, supported_if=supported_if.strip(),
                   refuted_if=refuted_if.strip(), method_rung=Rung(method_rung), owner=owner,
                   deadline=records.check_due(deadline), replaces=replaces, created_by=by, created_at=today())
    with changes.track(v, RecordKind.EXPERIMENT, x.id, by=by, group=group, source=source,
                       summary=f"New experiment (draft): {method}"):
        v.experiments.append(x)
    return x


def edit(v: Venture, eid: str, *, by: str, group: str = "", source: str = "", **fields) -> Experiment:
    """Change a DRAFT. Once an experiment runs its criteria are locked."""
    x = _get(v, eid)
    if x.status != ExperimentStatus.DRAFT:
        raise ValueError("The criteria are locked once the experiment runs. Stop it and start a new one to change them.")
    unknown = sorted(set(fields) - set(EDITABLE))
    if unknown:
        raise ValueError(f"Cannot edit {', '.join(unknown)}")
    if "method" in fields and not str(fields["method"]).strip():
        raise ValueError("Describe the method: who, how many, and what you will ask them to do")
    if "owner" in fields and fields["owner"] != "team" and v.member(fields["owner"]) is None:
        raise ValueError("The owner must be a team member or the team")
    with changes.track(v, RecordKind.EXPERIMENT, eid, by=by, group=group, source=source,
                       summary=f"Experiment draft edited: {fields.get('method', x.method)}"):
        for name, value in fields.items():
            if name == "method_rung":
                value = Rung(value)
            elif name == "deadline":
                value = records.check_due(value)
            elif isinstance(value, str):
                value = value.strip()
            setattr(x, name, value)
    return x


def missing_to_start(x: Experiment) -> list[str]:
    """What the team still has to write down before the experiment can start."""
    checks = (("the method", x.method), ("what result supports the assumption", x.supported_if),
              ("what result refutes it", x.refuted_if))
    missing = [label for label, value in checks if not value.strip()]
    if x.method_rung == Rung.NONE:
        missing.append("the evidence level of the method (ask the mentor to rate it)")
    return missing


def start(v: Venture, eid: str, *, by: str, group: str = "") -> Experiment:
    x = _get(v, eid)
    if x.status != ExperimentStatus.DRAFT:
        raise ValueError("Only a draft experiment can start")
    missing = missing_to_start(x)
    if missing:
        raise ValueError("Before you start, write down " + ", ".join(missing) + ".")
    group = group or changes.new_group()
    with changes.track(v, RecordKind.EXPERIMENT, eid, by=by, group=group,
                       summary=f"Experiment started, criteria locked: {x.method}"):
        x.status, x.started_at = ExperimentStatus.RUNNING, today()
    h = v.hypothesis(x.assumption_id) if x.assumption_id else None
    if h is not None and h.status == HypothesisStatus.UNTESTED:
        records.set_status(v, h.id, HypothesisStatus.TESTING, by=by, group=group, source=f"experiment {x.id}")
    return x


def stop(v: Venture, eid: str, reason: str, *, by: str, replace: bool = True, group: str = "") -> Experiment | None:
    """End an experiment without a conclusion. With `replace`, returns a new DRAFT copy to change and start again."""
    x = _get(v, eid)
    if not x.is_open:
        raise ValueError("This experiment has already ended")
    reason = reason.strip()
    if not reason:
        raise ValueError("Say why you stop it, so the record stays honest")
    group = group or changes.new_group()
    with changes.track(v, RecordKind.EXPERIMENT, eid, by=by, group=group,
                       summary=f"Experiment stopped ({reason}): {x.method}"):
        x.status, x.stop_reason, x.ended_at = ExperimentStatus.STOPPED, reason, today()
    if not replace:
        return None
    return create(v, by=by, method=x.method, assumption_id=x.assumption_id, lens=x.lens, supported_if=x.supported_if,
                  refuted_if=x.refuted_if, method_rung=x.method_rung, owner=x.owner, deadline=x.deadline,
                  replaces=x.id, group=group, source=f"replaces {x.id}")


def record_result(v: Venture, eid: str, result: str, *, by: str, group: str = "") -> Experiment:
    x = _get(v, eid)
    if x.status != ExperimentStatus.RUNNING:
        raise ValueError("Start the experiment before recording its result")
    result = result.strip()
    if not result:
        raise ValueError("Write what happened: how many did what")
    with changes.track(v, RecordKind.EXPERIMENT, eid, by=by, group=group, summary=f"Result recorded: {result}"):
        x.result, x.result_by = result, by
    return x


def judge(v: Venture, eid: str, conclusion: Conclusion, why: str, *, by: str, group: str = "") -> Experiment:
    """The mentor's judgment of the result against the criteria agreed in advance (never the team's own)."""
    if by != EIR:
        raise PermissionError("The mentor judges the result against the criteria you agreed in advance")
    x = _get(v, eid)
    if x.status != ExperimentStatus.RUNNING or not x.result:
        raise ValueError("The experiment needs a recorded result before it can be judged")
    conclusion, why = Conclusion(conclusion), why.strip()
    if conclusion == Conclusion.NONE:
        raise ValueError("Choose Supported, Refuted or Inconclusive")
    if not why:
        raise ValueError("Explain the conclusion against the criteria")
    group = group or changes.new_group()
    with changes.track(v, RecordKind.EXPERIMENT, eid, by=by, group=group,
                       summary=f"Experiment judged {conclusion.value}: {x.method}"):
        x.status, x.conclusion, x.judged_why, x.ended_at = ExperimentStatus.CONCLUDED, conclusion, why, today()
    if x.assumption_id:
        records.add_evidence(v, x.assumption_id, f"{x.method}: {x.result}", _DIRECTION[conclusion], x.method_rung,
                             by=by, group=group, source=f"experiment {x.id}", experiment_id=x.id)
        records.set_status(v, x.assumption_id, _STATUS[conclusion], by=by, group=group, source=f"experiment {x.id}")
    return x
