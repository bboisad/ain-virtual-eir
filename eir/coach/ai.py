"""AI coach: same interface as the scripted coach, answers come from an LLM.

Behaviour is tuned in eir/prompts/ (no code changes needed).
"""
from __future__ import annotations

import re
from pathlib import Path
from string import Template

from .. import access, consult, files, grading, memory, modes, practice
from ..llm import LLMClient
from ..models import (CHARACTER, CONSULTANT, EIR, SYSTEM, Consultation, ConsultationSummary, FileVersion, LeadMode,
                      Message, ProjectFile, Rehearsal, RehearsalFeedback, Rung, Venture)
from ..seed import consult_script_for, script_for
from ..tools import PRACTICE_ANSWER, ToolBox
from .base import ConsultTurn, FileSummary, LeadEvent, LeadTurn, PracticeStart, PracticeTurn
from .scripted import ScriptedCoach, first_question, plain_file_summary

PROMPTS = Path(__file__).resolve().parent.parent / "prompts"
PROPOSE_END = re.compile(r"\[\[\s*PROPOSE[_ ]END\s*\]\]", re.IGNORECASE)
WRAP_UP = re.compile(r"\[\[\s*WRAP[_ ]UP\s*\]\]", re.IGNORECASE)
FEEDBACK_LISTS = {  # which lists of the feedback each kind of character fills
    practice.SEGMENT: "Fill checks (at most 3). Leave tough_questions, problems and unsupported_claims empty.",
    practice.SUBMISSION: "Fill tough_questions (at most 3) and unsupported_claims. Leave problems and checks empty.",
    practice.RECORDS: "Fill problems (at most 3, most severe first), tough_questions (at most 2) and "
                      "unsupported_claims. Leave checks empty.",
}


def _merge_claims(model: list[str], app: list[str], limit: int = 4) -> list[str]:
    """The model's unsupported claims, plus the app's own that the model did not already name."""
    out = list(model)
    for claim in app:
        quoted = claim.split('"')[1] if claim.count('"') >= 2 else claim
        number = re.search(r"don't show (\S+?)\.?$", claim)
        if not any(quoted[:40].lower() in m.lower() or (number and number.group(1) in m) for m in model):
            out.append(claim)
    return out[:limit]


def _strings(value) -> list[str]:
    """A JSON field that should be a list of strings (the model sometimes returns one string, or nothing)."""
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if isinstance(value, list):
        return [str(x).strip() for x in value if str(x).strip()]
    return []


def _template(name: str) -> Template:
    return Template((PROMPTS / name).read_text(encoding="utf-8"))


class AICoach:
    def __init__(self, client: LLMClient):
        self.client = client
        self.label = client.cfg.model_name

    def suggestions(self, v: Venture, speaker: str) -> list[str]:
        sent = {m.text for m in v.conversation}
        return [l.text for l in script_for(v.id) if l.speaker in ("any", speaker) and l.text not in sent][:3]

    # ---- grading ----
    def grade_evidence(self, v: Venture, question: str, answer: str) -> grading.Grade:
        """Grade on the evidence ladder; falls back to the keyword grader if the model call fails."""
        fallback = grading.grade(answer)
        if fallback.rung == Rung.NONE:
            return fallback
        ladder = "\n".join(f"{int(r)} = {r.label}" for r in Rung if r != Rung.NONE)
        prompt = (f"Key question: {question}\nTeam's answer: \"\"\"{answer}\"\"\"\n\nGrade the strongest evidence the "
                  f"answer actually reports, on this ladder:\n{ladder}\nBeliefs and predictions (\"they would pay\") are 1. "
                  "If the answer does not say how many or who, grade it at most 2. "
                  'Return JSON: {"rung": <1-6>, "why": "<one short sentence>"}')
        try:
            data = self.client.chat_json("You are a skeptical startup mentor grading evidence. Strict JSON only.", prompt)
            return grading.Grade(Rung(int(data["rung"])), str(data.get("why", ""))[:200])
        except Exception:  # noqa: BLE001 — the grade must never block saving an answer
            return fallback

    # ---- lead mentor (multi-mentor design) ----
    def lead_turn(self, v: Venture, box: ToolBox, event: LeadEvent | None = None) -> LeadTurn:
        messages, box.refs = memory.window(v)
        if event is not None:
            memory.add_note(messages, self._event_note(v, event))
        if not messages:
            messages = [{"role": "user", "content": "(note) The team opened the chat for the first time. Greet them "
                                                    "in one line and ask what they are working on."}]
        rules = (PROMPTS / ("lead_launch.md" if v.lead_mode == LeadMode.LAUNCH else "lead_optimize.md")
                 ).read_text(encoding="utf-8")
        system = _template("lead_common.md").substitute(mode_name=modes.NAMES[v.lead_mode], mode_rules=rules,
                                                        context=memory.lead_context(v))
        run = self.client.run_tools(system, messages, box.specs(), box.call)
        return LeadTurn(run.text.strip() or "What happened since we last talked?")

    @staticmethod
    def _event_note(v: Venture, event: LeadEvent) -> str:
        if event.kind == "invite":
            return (f"A team member clicked the {consult.name_of(event.ref)} consultant in the rail and asks you to "
                    "bring them in. Open the consultation now (open_consultation) with a brief built from the current "
                    "focus and the records, then tell the team in one line.")
        if event.kind == "summary":
            c = v.consultation(event.ref)
            return (f"The consultation consult:{event.ref} has ended. Tell the team its key points in your own words, "
                    f"update the records it supports (source consult:{event.ref}) and add the to-dos you agree "
                    f"with.\n{access.lead_view_of_consultation(c)}")
        if event.kind == "practice":
            r = v.rehearsal(event.ref)
            pitched = practice.spec(r.character).sees == practice.SUBMISSION and v.lead_mode == LeadMode.LAUNCH
            return (f"A team member sent you the feedback of a practice session (practice:{event.ref}). You never see "
                    "the conversation, and practice is not evidence. In your own words, give the one or two points "
                    "that matter most for the venture and what to do next; add the tasks or new assumptions you agree "
                    f"with (source practice:{event.ref})."
                    + (f" It was a session with the judge: record where the team practised its pitch and the hardest "
                       f"question as the answer to {PRACTICE_ANSWER} (rung 1)." if pitched else "")
                    + f"\n{access.lead_view_of_practice(v, r)}")
        if event.kind == "judge":
            x = v.experiment(event.ref)
            return (f"The team asks you to judge experiment {event.ref}. Recorded result: {x.result}. Compare it "
                    f"strictly with the criteria agreed in advance (supported if {x.supported_if}; refuted if "
                    f"{x.refuted_if}) and use judge_experiment.")
        return f"Event: {event.kind} {event.ref}"

    def summarize_day(self, v: Venture, label: str, messages: list[Message]) -> str:
        def speaker(m: Message) -> str:
            return "Mentor" if m.author == EIR else "Note" if m.author == SYSTEM else v.display_name(m.author)

        prompt = _template("day_summary.md").substitute(
            label=label, transcript="\n".join(f"{speaker(m)}: {m.text}" for m in messages))
        return self.client.chat("You write short, factual notes of mentoring chats.",
                                [{"role": "user", "content": prompt}], max_tokens=200).strip()

    def rate_method(self, v: Venture, method: str) -> grading.Grade:
        """The evidence an experiment's method can produce; falls back to the keyword rating if the call fails."""
        fallback = grading.method_rung(method)
        if fallback.rung == Rung.NONE:
            return fallback
        ladder = "\n".join(f"{int(r)} = {r.label}" for r in Rung if r != Rung.NONE)
        prompt = (f"Experiment method: \"\"\"{method}\"\"\"\n\nWhat is the strongest evidence this METHOD can produce, "
                  f"whatever its result? Ladder:\n{ladder}\nAsking people whether they would pay is 3 (what they say). "
                  "Sign-ups, letters of intent and unpaid pilots are 4. Pre-orders, deposits and paid pilots are 5, "
                  'even if nobody pays. Return JSON: {"rung": <1-6>, "why": "<one short sentence>"}')
        try:
            data = self.client.chat_json("You rate experiment methods on an evidence ladder. Strict JSON only.", prompt)
            return grading.Grade(Rung(int(data["rung"])), str(data.get("why", ""))[:200])
        except Exception:  # noqa: BLE001 — rating must never block saving an experiment
            return fallback

    # ---- consultants ----
    @staticmethod
    def _consultant_system(v: Venture, c: Consultation) -> str:
        s = consult.spec(c.consultant)

        def bullets(items) -> str:
            return "\n".join(f"- {x}" for x in items)

        return _template("consultant.md").substitute(
            name=s.name.lower(), scope=s.scope, checklist=bullets(s.checklist), red_flags=bullets(s.red_flags),
            evidence=bullets(f"{rung} = {text}" for rung, text in s.evidence), answer=", ".join(s.answer),
            prepare_only=", ".join(s.prepare_only), must_hand_off=", ".join(s.must_hand_off),
            hand_off_expertise=s.hand_off_expertise.lower(), view=access.consultant_view(v, c))

    @staticmethod
    def _consultation_messages(v: Venture, c: Consultation) -> list[dict]:
        """The consultation for the model: the consultant's turns as assistant, the team's as "Name: text"."""
        out = [{"role": "user", "content": "(note) The consultation is open; you greeted the team first."}]
        for m in c.messages:
            role = "assistant" if m.author == CONSULTANT else "user"
            content = m.text if role == "assistant" else f"{v.display_name(m.author)}: {m.text}"
            if out[-1]["role"] == role:
                out[-1]["content"] += "\n\n" + content
            else:
                out.append({"role": role, "content": content})
        return out

    def consult_turn(self, v: Venture, c: Consultation) -> ConsultTurn:
        text = self.client.chat(self._consultant_system(v, c), self._consultation_messages(v, c), max_tokens=700)
        propose = bool(PROPOSE_END.search(text))
        return ConsultTurn(PROPOSE_END.sub("", text).strip() or "Could you say a little more?", propose)

    def consult_summary(self, v: Venture, c: Consultation) -> ConsultationSummary:
        s = consult.spec(c.consultant)
        prompt = _template("consultant_summary.md").substitute(
            name=s.name.lower(), must_hand_off=", ".join(s.must_hand_off), brief=c.brief,
            transcript=consult.transcript(v, c))
        data = self.client.chat_json("You write factual consultation summaries as strict JSON.", prompt)
        return ConsultationSummary(
            question=str(data.get("question") or c.question).strip(),
            conclusions=_strings(data.get("conclusions"))[:4], missing_evidence=_strings(data.get("missing_evidence")),
            suggested_todos=_strings(data.get("suggested_todos"))[:3], needs_human=bool(data.get("needs_human")),
            human_topic=str(data.get("human_topic") or "").strip(), disagreements=_strings(data.get("disagreements")),
            out_of_scope=_strings(data.get("out_of_scope")))

    def consult_suggestions(self, v: Venture, c: Consultation, speaker: str) -> list[str]:
        script = consult_script_for(v.id, c.consultant)
        if script is None:
            return []
        sent = {m.text for m in c.messages}
        return [l.text for l in script.lines if l.text not in sent and l.speaker in ("any", speaker)][:3]

    # ---- project files ----
    SUMMARY_CHARS = 12_000  # the start of the document the summary is written from

    def summarize_file(self, v: Venture, f: ProjectFile, version: FileVersion, text: str,
                       previous: FileVersion | None = None) -> FileSummary:
        """Summary and key claims from the model; the plain summary if it fails (an upload never waits on AI)."""
        if not f.kind.readable or not text.strip():
            return plain_file_summary(f, version, text, previous)
        prompt = _template("file_summary.md").substitute(
            name=f.name, kind=files.LABELS[f.kind], number=version.number, note=version.note or "(nothing)",
            previous=(f"Previous version's summary: {previous.summary}\n" if previous is not None else ""),
            ip_rule=(access.IP_RULE + "\n" if v.ip_sensitive else ""),
            changes="; then what changed since the previous version" if previous is not None else "",
            text=text[:self.SUMMARY_CHARS])
        try:
            data = self.client.chat_json("You summarize documents for a startup mentor as strict JSON.", prompt)
            summary = str(data.get("summary") or "").strip()
            if not summary:
                raise ValueError("no summary")
            return FileSummary(summary[:1200], [c[:300] for c in _strings(data.get("claims"))][:5])
        except Exception:  # noqa: BLE001 - the upload must never fail because the summary did
            return plain_file_summary(f, version, text, previous)

    # ---- practice characters (prompts: practice_character, practice_customer_profile, practice_feedback,
    # practice_hint). The character sees only access.character_view; the practice coach sees the records. ----
    @staticmethod
    def _role(r: Rehearsal) -> str:
        s = practice.spec(r.character)
        if s.sees == practice.SEGMENT:
            return f"{r.persona or 'a person'}, one of the team's target customers"
        return f"a {s.name.lower()} ({s.purpose})"

    @staticmethod
    def _facts(r: Rehearsal) -> str:
        t = practice.pitch_timing(r)
        if t is None:
            return ""
        return f"TIMING: the team's pitch (its first message) is {t.label}: {'over' if t.over else 'within'} the limit."

    @staticmethod
    def _pace(r: Rehearsal) -> str:
        """Closing on time does not depend on the model counting: past the planned exchanges, it is told to close."""
        planned, sent = practice.spec(r.character).wrap_after, practice.turns(r)
        if sent < planned:
            return ""
        return (f"PACE: the team has sent {sent} messages and you planned about {planned}. Close the session now, in "
                "character, and put [[WRAP_UP]] alone on the last line.")

    def _character_system(self, v: Venture, r: Rehearsal, material: str) -> str:
        s, sc = practice.spec(r.character), practice.scenario_of(r)
        facts = "\n".join(x for x in (self._facts(r), self._pace(r)) if x)
        return _template("practice_character.md").substitute(
            role=self._role(r), scenario=f"{sc.title}. {sc.description}", direction=sc.direction,
            difficulty=r.difficulty.value, how=s.how(r.difficulty), behaviour="\n".join(f"- {b}" for b in s.behaviour),
            never="; ".join(s.never), wrap_after=s.wrap_after, wrap_up=s.wrap_up, facts=facts,
            view=access.character_view(v, r, material))

    @staticmethod
    def _practice_messages(v: Venture, r: Rehearsal) -> list[dict]:
        """The session for the model: the character's turns as assistant, the team's as "Name: text"."""
        out = [{"role": "user", "content": "(note) The practice session has started; you spoke first."}]
        for m in r.messages:
            role = "assistant" if m.author == CHARACTER else "user"
            content = (m.text.replace(practice.DEMO_MARK, "").strip() if role == "assistant"
                       else f"{v.display_name(m.author)}: {m.text}")
            if out[-1]["role"] == role:
                out[-1]["content"] += "\n\n" + content
            else:
                out.append({"role": role, "content": content})
        return out

    def _persona(self, v: Venture, r: Rehearsal) -> tuple[str, str]:
        """A new made-up target customer for every session ("", "" if the model fails)."""
        used = sorted({practice.first_name(x) for x in v.rehearsals if x.character == r.character and x.persona})
        prompt = _template("practice_customer_profile.md").substitute(
            segment=practice.segment(v), how=practice.spec(r.character).how(r.difficulty),
            avoid=", ".join(used) or "(any name)")
        try:
            data = self.client.chat_json("You invent ordinary, fictional people for interview practice. Strict JSON "
                                         "only.", prompt)
        except Exception:  # noqa: BLE001 - the scripted persona keeps the session going
            return "", ""
        return (" ".join(str(data.get("persona") or "").split())[:120],
                " ".join(str(data.get("profile") or "").split())[:1500])

    def practice_start(self, v: Venture, r: Rehearsal, material: str = "") -> PracticeStart:
        s, sc = practice.spec(r.character), practice.scenario_of(r)
        persona = profile = ""
        if s.sees == practice.SEGMENT:
            persona, profile = self._persona(v, r)
            if not persona:
                return ScriptedCoach().practice_start(v, r, material)
        first = ""
        if "{first}" in sc.opening:
            ask = [{"role": "user", "content": "(note) The session starts now. Ask your first question: one or two "
                                               "sentences, in character, no greeting."}]
            try:
                first = WRAP_UP.sub("", self.client.chat(self._character_system(v, r, material), ask,
                                                         max_tokens=200)).strip()
            except Exception:  # noqa: BLE001 - the scripted first question keeps the session going
                first = ""
            first = first or first_question(v, r)
        return PracticeStart(practice.opening(v, r, first, persona), persona, profile)

    def practice_turn(self, v: Venture, r: Rehearsal, material: str = "") -> PracticeTurn:
        text = self.client.chat(self._character_system(v, r, material), self._practice_messages(v, r), max_tokens=500)
        wrap = bool(WRAP_UP.search(text))
        text = WRAP_UP.sub("", text).strip()
        name = practice.first_name(r) or practice.spec(r.character).name
        text = re.sub(rf"^\W*{re.escape(name)}\W*:\s*", "", text, flags=re.IGNORECASE)  # "Maya: ..." -> "..."
        return PracticeTurn(text or "Sorry, could you say that again?", wrap)

    def practice_feedback(self, v: Venture, r: Rehearsal, material: str = "") -> RehearsalFeedback:
        """The practice coach's feedback; the keyword feedback if the model fails or gives no scores. The app's own
        check of claims against the records is always included."""
        s, sc = practice.spec(r.character), practice.scenario_of(r)
        plain = practice.plain_feedback(v, r)
        facts = [self._facts(r)] + ([f"The member asked the coach for {len(r.hints)} hint(s); they are not in the "
                                     "transcript."] if r.hints else [])
        prompt = _template("practice_feedback.md").substitute(
            character=practice.character_label(r), scenario=sc.title, difficulty=r.difficulty.value, goal=sc.goal,
            rubric="\n".join(f"- {d.id} ({d.title}). Strong: {d.good} Needs work: {d.fix}" for d in s.rubric),
            facts="\n".join(f for f in facts if f), score_keys=", ".join(f'"{d.id}": <1-5>' for d in s.rubric),
            lists=FEEDBACK_LISTS.get(s.sees, ""), records=practice.records_text(v, technical=not v.ip_sensitive),
            material=(f"\nMATERIAL THE TEAM CHOSE:\n{material[:4000]}\n" if material else ""),
            app_checks="; ".join(plain.unsupported_claims) or "none", transcript=practice.transcript(v, r))
        try:
            data = self.client.chat_json("You are a practice coach who writes honest, specific feedback as strict "
                                         "JSON.", prompt)
        except Exception:  # noqa: BLE001 - ending a session never waits on AI
            return plain
        raw = data.get("scores")
        scores = practice.clean_scores(s, raw if isinstance(raw, dict) else {})
        if not scores:
            return plain
        scores = {d.id: scores.get(d.id, plain.scores[d.id]) for d in s.rubric}
        fb = RehearsalFeedback(scores=scores, strengths=_strings(data.get("strengths"))[:2],
                               fixes=_strings(data.get("fixes"))[:3] or plain.fixes,
                               verdict=str(data.get("verdict") or "").strip()[:300]
                               or practice.verdict(practice.overall(scores)))
        if s.sees == practice.SEGMENT:
            fb.checks = _strings(data.get("checks"))[:3]
        else:
            fb.tough_questions = _strings(data.get("tough_questions"))[:3]
            fb.unsupported_claims = _merge_claims(_strings(data.get("unsupported_claims")), plain.unsupported_claims)
        if s.sees == practice.RECORDS:
            fb.problems = _strings(data.get("problems"))[:3] or plain.problems
        return fb

    def practice_hint(self, v: Venture, r: Rehearsal, material: str = "") -> str:
        s, sc = practice.spec(r.character), practice.scenario_of(r)
        prompt = _template("practice_hint.md").substitute(
            character=practice.character_label(r), scenario=sc.title, goal=sc.goal,
            tips="\n".join(f"- {t}" for t in s.tips), records=practice.records_text(v, technical=not v.ip_sensitive),
            transcript=practice.transcript(v, r))
        text = self.client.chat("You are a practice coach. Reply with the hint only.",
                                [{"role": "user", "content": prompt}], max_tokens=150)
        return " ".join(text.split()).strip("\"' ")

    def practice_suggestions(self, v: Venture, r: Rehearsal, speaker: str) -> list[str]:
        return ScriptedCoach().practice_suggestions(v, r, speaker)[:3]
