"""The lead mentor's actions (function calling) and the rules that keep its record updates honest.

- Every write cites `source`: the tag of the team message it is based on ("m12"), a returned consultation
  ("consult:K-1a2b3c"), or practice feedback a member sent ("practice:R-1a2b3c"). Content comes from what the team
  said or did; the mentor grades the evidence.
- Practice is not evidence: a practice source is accepted only for a task, a new assumption, the focus, and the
  answer to "where have you pitched it" (pd_practice, rung 1, from a session with the judge).
- There is no action that marks a Foundry step complete, edits the team's own documents, or moves the module.
  The mentor reads project files (read_file, read-only) and suggests revisions as tasks linked to the file.
- Each call is one change group, so the team can undo it from the chat. A failed call changes nothing.
- Errors go back to the model as text, so it can correct itself in the same turn.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from . import changes, consult, experiments, files, modes, practice, records
from .filestore import FileStore
from .llm import ToolCall, ToolSpec
from .models import CANVAS_BLOCKS, EIR, Conclusion, Direction, FocusKind, Importance, LeadMode, Rung, Venture

READ_ONLY = ("read_file", "suggest_practice")  # actions that change no record
PRACTICE_ANSWER = "pd_practice"  # "Where have you pitched it, and what was the hardest question you got?"

TEXT = {"type": "string"}
SOURCE = {"type": "string", "description": 'Tag of the team message this is based on, e.g. "m3"; "consult:<id>" for a '
                                           'returned consultation summary; "practice:<id>" for practice feedback the '
                                           'team sent (tasks, new assumptions, the focus and pd_practice only).'}
RUNG = {"type": "integer", "minimum": 1, "maximum": 6,
        "description": "Evidence ladder: 1 assertion, 2 desk research, 3 customers said, 4 customers did, "
                       "5 customers paid, 6 retained behavior."}
IMPORTANCE = {"type": "integer", "minimum": 0, "maximum": 4,
              "description": "0 unrated, 1 low, 2 medium, 3 high, 4 fatal (if it is wrong, the project fails)."}
BOTH = (LeadMode.LAUNCH, LeadMode.OPTIMIZE)


def _obj(required: list[str], **props) -> dict:
    return {"type": "object", "properties": props, "required": required}


class ToolError(ValueError):
    pass


def _need(args: dict, key: str):
    value = args.get(key)
    if value is None or (isinstance(value, str) and not value.strip()):
        raise ToolError(f"missing argument: {key}")
    return value.strip() if isinstance(value, str) else value


def _rung(args: dict, key: str = "rung") -> Rung:
    try:
        rung = Rung(int(_need(args, key)))
    except (TypeError, ValueError):
        raise ToolError(f"{key} must be a whole number from 1 to 6") from None
    if rung == Rung.NONE:
        raise ToolError(f"{key} must be a whole number from 1 to 6")
    return rung


@dataclass
class ToolBox:
    """What the lead mentor may do in one turn, and what it did."""
    v: Venture
    refs: dict[str, str] = field(default_factory=dict)  # message tag ("m3") -> message id, from memory.window
    groups: list[str] = field(default_factory=list)  # change groups made this turn (the Undo buttons)
    opened: list[str] = field(default_factory=list)  # consultations opened this turn
    handoff: str = ""
    suggested_mode: LeadMode | None = None
    suggested_practice: str = ""  # a practice session the mentor suggests (a button under its reply)
    log: list[tuple[str, dict, str]] = field(default_factory=list)  # (action, arguments, result)
    files: FileStore | None = None  # where read_file finds the text of project files

    @property
    def last_ref(self) -> str:
        """The tag of the latest team message (scripted replies cite it)."""
        return list(self.refs)[-1] if self.refs else ""

    def specs(self) -> list[ToolSpec]:
        readable = self.files is not None and any(f.kind.readable for f in self.v.files)
        return [t.spec for t in TOOLS.values() if self.v.lead_mode in t.modes
                and (t.spec.name != "read_file" or readable)]

    def file_ids(self, args: dict, key: str) -> list[str]:
        ids = args.get(key) or []
        ids = [ids] if isinstance(ids, str) else list(ids)
        unknown = [i for i in ids if self.v.file(str(i)) is None]
        if unknown:
            raise ToolError(f"{key}: no project file {', '.join(map(str, unknown))}")
        return [str(i) for i in ids]

    def call(self, call: ToolCall) -> str:
        tool = TOOLS.get(call.name)
        if tool is None or self.v.lead_mode not in tool.modes:
            return f"ERROR: there is no action called {call.name} for the {modes.NAMES[self.v.lead_mode]}"
        group = changes.new_group()
        try:
            result = tool.run(self, call.args, group)
        except (ValueError, PermissionError, TypeError, KeyError) as err:
            self._discard(group)
            return f"ERROR: {err}"
        if changes.changes_in(self.v, group):
            self.groups.append(group)
        self.log.append((call.name, call.args, result))
        return result

    def _discard(self, group: str) -> None:
        if changes.changes_in(self.v, group):
            changes.undo_group(self.v, group, EIR)
        self.v.changes = [c for c in self.v.changes if c.group != group]

    def rollback(self) -> None:
        """Undo everything this turn did (the mentor's turn failed)."""
        for group in reversed(self.groups):
            if changes.undo_problem(self.v, group) is None:
                changes.undo_group(self.v, group, EIR)
            self.v.changes = [c for c in self.v.changes if c.group != group]
        self.v.consultations = [c for c in self.v.consultations if c.id not in self.opened]
        self.groups, self.opened, self.handoff, self.suggested_mode = [], [], "", None
        self.suggested_practice = ""

    # ---- argument checks ----
    def source(self, args: dict, practice_ok: bool = False) -> str:
        """The source of a write. A practice source is refused unless the action allows it (`practice_ok`)."""
        ref = str(args.get("source", "")).strip()
        if ref.startswith("consult:"):
            c = self.v.consultation(ref.removeprefix("consult:"))
            if c is None or c.summary is None:
                raise ToolError(f"source {ref}: there is no returned consultation with that id")
            return ref
        if ref.startswith("practice:"):
            r = self.v.rehearsal(ref.removeprefix("practice:"))
            if r is None or not r.shared_at or r.feedback is None:
                raise ToolError(f"source {ref}: the team sent you no practice feedback with that id")
            if not practice_ok:
                raise ToolError(f"source {ref}: practice is not evidence. Use practice feedback only for tasks, new "
                                "assumptions, the focus, or the answer to pd_practice; cite a team message for the rest.")
            return ref
        if ref in self.refs:
            return f"message {self.refs[ref]}"
        raise ToolError(f"source {ref or '(missing)'} not found: cite the tag of the team message the content comes "
                        "from, e.g. m3. Record only what the team said or did.")

    def owner(self, args: dict) -> str:
        name = str(args.get("owner") or "team").strip()
        if name == "team" or self.v.member(name):
            return name
        m = next((m for m in self.v.members if name.lower() in (m.first_name.lower(), m.name.lower())), None)
        if m is None:
            raise ToolError(f"owner {name}: not a team member (use a first name or \"team\")")
        return m.id


# ---- the actions ----
def _set_focus(box: ToolBox, a: dict, g: str) -> str:
    try:
        kind = FocusKind(str(_need(a, "kind")))
    except ValueError:
        raise ToolError("kind must be question, assumption, canvas or lens") from None
    f = records.set_focus(box.v, _need(a, "text"), kind, str(a.get("ref", "")), by=EIR, group=g,
                          source=box.source(a, practice_ok=True))
    return f"Focus set: {f.text}"


def _add_assumption(box: ToolBox, a: dict, g: str) -> str:
    h = records.add_assumption(box.v, _need(a, "statement"), by=EIR, importance=Importance(int(a.get("importance", 0))),
                               group=g, source=box.source(a, practice_ok=True))
    return f"Assumption {h.id} added"


def _update_assumption(box: ToolBox, a: dict, g: str) -> str:
    imp = a.get("importance")
    h = records.update_assumption(box.v, _need(a, "assumption_id"), by=EIR, statement=a.get("statement"),
                                  importance=None if imp is None else Importance(int(imp)), group=g,
                                  source=box.source(a))
    return f"Assumption {h.id} updated"


def _add_evidence(box: ToolBox, a: dict, g: str) -> str:
    direction = str(_need(a, "direction"))
    if direction not in (Direction.FOR.value, Direction.AGAINST.value):
        raise ToolError("direction must be for or against")
    hid = _need(a, "assumption_id")
    records.add_evidence(box.v, hid, _need(a, "text"), Direction(direction), _rung(a), by=EIR, group=g,
                         source=box.source(a))
    return f"Evidence recorded; {hid} is now at {box.v.hypothesis(hid).rung.label}"


def _record_answer(box: ToolBox, a: dict, g: str) -> str:
    qid, rung, why = _need(a, "question_id"), _rung(a), str(a.get("why", ""))
    source = box.source(a, practice_ok=qid == PRACTICE_ANSWER)
    if source.startswith("practice:"):  # where the team pitched: its own account (rung 1), from a judge session only
        r = box.v.rehearsal(source.removeprefix("practice:"))
        if practice.spec(r.character).sees != practice.SUBMISSION:
            raise ToolError(f"{PRACTICE_ANSWER} asks where the team pitched: only a session with the judge answers it")
        rung, why = Rung.ASSERTION, why or "A practice pitch with the AI judge: the team's own account, not evidence."
    ans = records.record_answer(box.v, qid, _need(a, "text"), rung, why, by=EIR, group=g, source=source)
    return f"Answer recorded at {ans.rung.label}"


def _update_canvas(box: ToolBox, a: dict, g: str) -> str:
    e = records.update_canvas(box.v, _need(a, "block"), by=EIR, text=_need(a, "text"), rung=_rung(a),
                              why=str(a.get("why", "")), group=g, source=box.source(a))
    return f"Canvas block {a['block']} at {e.rung.label}"


def _grade_lens(box: ToolBox, a: dict, g: str) -> str:
    lg = records.grade_lens(box.v, _need(a, "lens"), _rung(a), str(a.get("summary", "")), str(a.get("why", "")),
                            by=EIR, group=g, source=box.source(a))
    return f"Lens {a['lens']} at {lg.rung.label}"


def _set_bottleneck(box: ToolBox, a: dict, g: str) -> str:
    d = records.set_bottleneck(box.v, _need(a, "lens"), _need(a, "why"), by=EIR, group=g, source=box.source(a))
    return f"Bottleneck: {d.bottleneck}"


def _propose_experiment(box: ToolBox, a: dict, g: str) -> str:
    x = experiments.create(box.v, by=EIR, method=_need(a, "method"), assumption_id=str(a.get("assumption_id", "")),
                           lens=str(a.get("lens", "")), supported_if=_need(a, "supported_if"),
                           refuted_if=_need(a, "refuted_if"), method_rung=_rung(a, "method_rung"),
                           owner=box.owner(a), deadline=str(a.get("deadline", "")), group=g, source=box.source(a))
    return f"Draft experiment {x.id} created. The team starts it when ready; its criteria lock then."


def _record_result(box: ToolBox, a: dict, g: str) -> str:
    box.source(a)  # the result must come from what the team reported
    x = experiments.record_result(box.v, _need(a, "experiment_id"), _need(a, "result"), by=EIR, group=g)
    return f"Result recorded for {x.id}; judge it against its criteria"


def _judge_experiment(box: ToolBox, a: dict, g: str) -> str:
    try:
        conclusion = Conclusion(str(_need(a, "conclusion")))
    except ValueError:
        raise ToolError("conclusion must be Supported, Refuted or Inconclusive") from None
    x = experiments.judge(box.v, _need(a, "experiment_id"), conclusion, _need(a, "why"), by=EIR, group=g)
    return f"{x.id} judged {x.conclusion.value}"


def _add_task(box: ToolBox, a: dict, g: str) -> str:
    linked = box.file_ids(a, "file_id")
    t = records.add_task(box.v, _need(a, "text"), box.owner(a), by=EIR, due_date=str(a.get("due_date", "")),
                         file_id=linked[0] if linked else "", group=g, source=box.source(a, practice_ok=True))
    return f"Task {t.id} added" + (f", linked to {box.v.file(t.file_id).name}" if t.file_id else "")


def _read_file(box: ToolBox, a: dict, g: str) -> str:
    if box.files is None:
        raise ToolError("project files are not available right now")
    (fid,) = box.file_ids(a, "file_id") or [None]
    if fid is None:
        raise ToolError("missing argument: file_id")
    return files.read(box.files, box.v.file(fid), int(a.get("version") or 0), int(a.get("part") or 1))


def _complete_task(box: ToolBox, a: dict, g: str) -> str:
    t = records.complete_task(box.v, _need(a, "task_id"), by=EIR, result=str(a.get("result", "")), group=g,
                              source=box.source(a))
    return f"Task {t.id} marked done"


def _open_consultation(box: ToolBox, a: dict, g: str) -> str:
    cid = str(_need(a, "consultant"))
    c = consult.start(box.v, cid, _need(a, "question"), _need(a, "brief"), by=EIR,
                      file_ids=tuple(box.file_ids(a, "file_ids")))
    box.opened.append(c.id)
    return (f"Consultation {c.id} with the {consult.name_of(cid)} consultant is open. Tell the team to open it from "
            "the rail on the right; you will receive its summary.")


def _request_human(box: ToolBox, a: dict, g: str) -> str:
    box.handoff = str(_need(a, "topic"))
    return "Noted: the team can share a brief with a human AIN EIR from the menu"


def _suggest_mode_switch(box: ToolBox, a: dict, g: str) -> str:
    try:
        to = LeadMode(str(_need(a, "to")))
    except ValueError:
        raise ToolError("to must be Launch or Optimize") from None
    if to == box.v.lead_mode:
        raise ToolError(f"the {modes.NAMES[to]} is already the lead mentor")
    if to == LeadMode.OPTIMIZE:
        if box.v.optimize_suggested_on:
            raise ToolError("you already suggested the Optimize mentor once; do not suggest it again")
        modes.mark_optimize_suggested(box.v)
    box.suggested_mode = to
    return f"The team will see a button to switch to the {modes.NAMES[to]}; they decide"


def _suggest_practice(box: ToolBox, a: dict, g: str) -> str:
    s = practice.suggestion(box.v, str(_need(a, "character")), str(_need(a, "scenario")),
                            str(a.get("assumption_id", "")).strip())
    box.suggested_practice = str(s)
    return (f"The team will see a button under your reply: \"{s.label}\". Practice is theirs: you see its feedback "
            "only if they send it.")


@dataclass(frozen=True)
class Tool:
    spec: ToolSpec
    run: Callable[[ToolBox, dict, str], str]
    modes: tuple[LeadMode, ...] = BOTH


def _tools() -> dict[str, Tool]:
    lens = {"type": "string", "enum": list(modes.lens_ids())}
    defs = [
        Tool(ToolSpec("set_focus", "Set the ONE thing you are pressing now (top of the Overview and the briefing): "
                      "kind question (a key question id), assumption (an id like H2), canvas (a block name) or lens.",
                      _obj(["text", "kind", "ref", "source"], text=TEXT, ref=TEXT, source=SOURCE,
                           kind={"type": "string", "enum": ["question", "assumption", "canvas", "lens"]})), _set_focus),
        Tool(ToolSpec("add_assumption", "Record a belief the venture depends on, in the team's words. Rate its "
                      "importance: 4 means the project fails if it is wrong.",
                      _obj(["statement", "importance", "source"], statement=TEXT, importance=IMPORTANCE,
                           source=SOURCE)), _add_assumption),
        Tool(ToolSpec("update_assumption", "Say the same assumption more clearly, or re-rate its importance. Never turn "
                      "it into a different claim: when the team changes its mind, add a new assumption, and the old "
                      "one keeps its evidence. Evidence and conclusion change only through add_evidence and "
                      "judge_experiment.",
                      _obj(["assumption_id", "source"], assumption_id=TEXT, statement=TEXT, importance=IMPORTANCE,
                           source=SOURCE)), _update_assumption),
        Tool(ToolSpec("add_evidence", "Record evidence for or against an assumption from what the team reported. Grade "
                      "the KIND of evidence: what people said is 3 however many said it ('would pay' is 3); "
                      "sign-ups and letters of intent are 4; payments are 5.",
                      _obj(["assumption_id", "text", "direction", "rung", "source"], assumption_id=TEXT, text=TEXT,
                           direction={"type": "string", "enum": ["for", "against"]}, rung=RUNG, source=SOURCE)),
             _add_evidence),
        Tool(ToolSpec("record_answer", "Record the team's answer to a Foundry key question in their own words, graded "
                      "on the ladder. The team presses 'Check this step'; you never mark a step complete.",
                      _obj(["question_id", "text", "rung", "source"], question_id=TEXT, text=TEXT, rung=RUNG, why=TEXT,
                           source=SOURCE)), _record_answer, (LeadMode.LAUNCH,)),
        Tool(ToolSpec("update_canvas", "Write a business model canvas block in the team's words and grade its "
                      "evidence.",
                      _obj(["block", "text", "rung", "source"], block={"type": "string", "enum": list(CANVAS_BLOCKS)},
                           text=TEXT, rung=RUNG, why=TEXT, source=SOURCE)), _update_canvas, (LeadMode.LAUNCH,)),
        Tool(ToolSpec("grade_lens", "Grade one of the six lenses on the evidence ladder: a one-line summary of what "
                      "the team reported, and why this rung.",
                      _obj(["lens", "rung", "summary", "source"], lens=lens, rung=RUNG, summary=TEXT, why=TEXT,
                           source=SOURCE)), _grade_lens, (LeadMode.OPTIMIZE,)),
        Tool(ToolSpec("set_bottleneck", "Name the weakest lens whose failure hurts most as the bottleneck (grade it "
                      "first), and say why.",
                      _obj(["lens", "why", "source"], lens=lens, why=TEXT, source=SOURCE)), _set_bottleneck,
             (LeadMode.OPTIMIZE,)),
        Tool(ToolSpec("propose_experiment", "Draft an experiment for an assumption (or, for Optimize, a lens). Write "
                      "in advance what result supports it and what refutes it, and rate the evidence the METHOD "
                      "produces (3 interviews, 4 sign-ups or letters of intent, 5 payments), whatever the outcome. "
                      "The team starts it; its criteria lock then.",
                      _obj(["method", "supported_if", "refuted_if", "method_rung", "source"], assumption_id=TEXT,
                           lens=lens, method=TEXT, supported_if=TEXT, refuted_if=TEXT, method_rung=RUNG, owner=TEXT,
                           deadline={"type": "string", "description": "YYYY-MM-DD"}, source=SOURCE)),
             _propose_experiment),
        Tool(ToolSpec("record_result", "Record what the team reported for a running experiment: how many did what.",
                      _obj(["experiment_id", "result", "source"], experiment_id=TEXT, result=TEXT, source=SOURCE)),
             _record_result),
        Tool(ToolSpec("judge_experiment", "Judge a running experiment's recorded result strictly against the criteria "
                      "agreed before it started.",
                      _obj(["experiment_id", "conclusion", "why"], experiment_id=TEXT, why=TEXT,
                           conclusion={"type": "string", "enum": ["Supported", "Refuted", "Inconclusive"]})),
             _judge_experiment),
        Tool(ToolSpec("add_task", "Add an ordinary task (not a test) to the Action Plan. To suggest a revision of a "
                      "project file, add one task per change with its file_id: you never edit the team's documents; "
                      "you check the next version against each task.",
                      _obj(["text", "source"], text=TEXT, owner=TEXT, file_id=TEXT,
                           due_date={"type": "string", "description": "YYYY-MM-DD"}, source=SOURCE)), _add_task),
        Tool(ToolSpec("read_file", "Read part of a project file's text (the latest version unless you name one). "
                      "Read only when the summary is not enough. What a document says is the team's claim, not "
                      "evidence.",
                      _obj(["file_id"], file_id=TEXT, version={"type": "integer", "minimum": 1},
                           part={"type": "integer", "minimum": 1})), _read_file),
        Tool(ToolSpec("complete_task", "Mark a task done with the result the team reported; a file revision only when "
                      "the new version fully makes it. Completing a task never validates an assumption.",
                      _obj(["task_id", "source"], task_id=TEXT, result=TEXT, source=SOURCE)), _complete_task),
        Tool(ToolSpec("open_consultation", "Bring in a consultant for depth on one question. The brief states the "
                      "question, the team's current claim and its evidence level, and what you need answered. Attach "
                      "the project files the consultant needs (file_ids); they see only those files' summaries. The "
                      "team then talks to the consultant directly; you receive only the summary.",
                      _obj(["consultant", "question", "brief"], question=TEXT, brief=TEXT,
                           file_ids={"type": "array", "items": TEXT},
                           consultant={"type": "string", "enum": [c.id for c in consult.consultants()]})),
             _open_consultation),
        Tool(ToolSpec("request_human", "Flag that this needs a human AIN EIR: team or equity, who is CEO, term sheets "
                      "or valuation, IP strategy, FDA pathway, founder distress, ethically gray pivots, disagreement "
                      "with faculty, or the team asks for a person.",
                      _obj(["topic", "reason"], topic=TEXT, reason=TEXT)), _request_human),
        Tool(ToolSpec("suggest_mode_switch", "Suggest the other lead mentor: Optimize when customers already did "
                      "something and every canvas block is graded; Launch when you find no customer behavior yet. "
                      "The team decides. Suggest Optimize at most once.",
                      _obj(["to", "reason"], reason=TEXT, to={"type": "string", "enum": ["Launch", "Optimize"]})),
             _suggest_mode_switch),
        Tool(ToolSpec("suggest_practice", "Put a button under your reply that opens a practice session with an AI "
                      "character (the team decides): customer/discovery or customer/solution before real interviews; "
                      "judge/pitch or judge/qa before a competition or a pitch; challenger/holes, challenger/premortem, "
                      "or challenger/assumption with assumption_id when the team keeps defending a guess. At most one "
                      "per reply, and only when it helps.",
                      _obj(["character", "scenario", "reason"], reason=TEXT, assumption_id=TEXT,
                           character={"type": "string", "enum": [c.id for c in practice.characters()]},
                           scenario={"type": "string", "enum": sorted({s.id for c in practice.characters()
                                                                       for s in c.scenarios})})),
             _suggest_practice),
    ]
    return {t.spec.name: t for t in defs}


TOOLS = _tools()
