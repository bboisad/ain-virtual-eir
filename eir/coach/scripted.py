"""Scripted coach for the clickable prototype: prepared replies from eir/seed/*.json, no API calls.

It plays the lead mentor with the same actions as the AI (eir/tools.py), so the keyless demo and the tests exercise
the real record updates, undo and consultations.
"""
from __future__ import annotations

import re

from copy import deepcopy

from .. import consult, files, grading, memory, modes, overview, practice, questioning, roadmap
from ..clock import today
from ..llm import ToolCall
from ..models import (CHARACTER, CONSULTANT, EIR, SYSTEM, Conclusion, Consultation, ConsultationSummary, Difficulty,
                      Experiment, FileVersion, LeadMode, Message, ProjectFile, Rehearsal, RehearsalFeedback, Rung,
                      Venture)
from ..seed import ScriptLine, consult_script_for, practice_script_for, script_for
from ..tools import ToolBox
from .base import ConsultTurn, FileSummary, LeadEvent, LeadTurn, PracticeStart, PracticeTurn

LEAD_FALLBACK = ("{name}, what decision are you trying to make, and what is still uncertain? Let's write the working "
                 "assumption down, then choose a small test that could change your mind. An interview observation "
                 "counts as evidence too, with its source and its limits.\n\n_Scripted demo reply (no AI connected)._")
OPENING = modes.GREETING
MENTOR_REPLY = ("Happy to bring in a human mentor. Open the menu (⋯) and choose **Ask a human EIR**: I've drafted a "
                "brief from your records, and your team reviews it before anything is shared.")
SCRIPTED = "\n\n" + practice.DEMO_MARK


def _customer_reply(text: str) -> str:
    """A made-up customer without AI: vague about the future, concrete about the past, polite to a pitch."""
    if practice.PITCH.search(text) or len(text.split()) > 60:
        return "Sounds interesting, I guess. I'd have to see it before I say anything."
    if practice.HYPOTHETICAL.search(text) and not practice.NEXT_STEP.search(text):
        return "Maybe? It sounds useful. Hard to say until I actually need it."
    if practice.SPECIFIC.search(text):
        return "I'm not sure exactly. I've never really added it up."
    if practice.PAST.search(text):
        return ("The last time it came up I just did whatever was quickest, even if it cost me a bit. I didn't look "
                "for anything better.")
    if "?" not in text:
        return "Okay. What did you want to ask me?"
    return "Hm, what do you mean exactly?"


PRACTICE_WORDS = re.compile(r"\b(?:rehears\w*|practi[cs]e|mock (?:pitch|interview|q&a)|pitching at|"
                            r"prepare for (?:the|our) pitch)\b", re.I)


def practice_for(v: Venture, text: str) -> tuple[str, str, str]:
    """(character, scenario, reason) for a team that asks to rehearse: from what it names, else the recommendation."""
    low = text.lower()
    if re.search(r"interview|customer", low):
        return "customer", "discovery", "Rehearse the interview with a made-up customer before the real ones."
    if re.search(r"pitch|judge|competition", low):
        return "judge", "pitch", "Pitch for three minutes to an AI competition judge and take its questions."
    if re.search(r"question|tough|challeng|investor", low):
        return "challenger", "holes", "Let a challenger find the weak spots before an investor does."
    rec = practice.recommended(v)
    return rec.character, rec.scenario, rec.reason


def first_question(v: Venture, r: Rehearsal) -> str:
    """The first question of a scripted judge or challenger (prepared for the demo ventures)."""
    script = practice_script_for(v.id, r.character, r.scenario)
    return (script.first if script else "") or next(iter(scripted_questions(v, r)), "")


def scripted_questions(v: Venture, r: Rehearsal) -> list[str]:
    """The questions a scripted judge or challenger asks, in order."""
    s, sc = practice.spec(r.character), practice.scenario_of(r)
    if s.sees != practice.RECORDS:
        return list(s.asks)
    if sc.needs_assumption:
        return list(roadmap.question_chain())
    if "{first}" not in sc.opening:
        return list(s.asks)
    weak = [h for h in overview.key_assumptions(v, limit=len(v.hypotheses)) if h.status.is_open and h.rung < Rung.DID]
    return [f"Your records say \"{h.statement}\", and the evidence so far is "
            f"{h.rung.label.split(' · ')[-1].lower()}. Why should anyone believe it?" for h in weak[:2]] + list(s.asks)


def _first_int(text: str) -> int | None:
    m = re.search(r"\d+", text)
    return int(m.group()) if m else None


def scripted_judgment(x: Experiment) -> tuple[Conclusion, str]:
    """Compare the first number of the result with "N or more" / "fewer than N" / "N or fewer" in the criteria."""
    n = _first_int(x.result)
    if n is None:
        return Conclusion.INCONCLUSIVE, "The result has no number to compare with the criteria."
    supported = re.search(r"(\d+)\s*(?:or more|\+)", x.supported_if, re.I)
    below = re.search(r"(?:fewer than|less than|under)\s*(\d+)", x.refuted_if, re.I)
    at_most = re.search(r"(\d+)\s*(?:or fewer|or less)", x.refuted_if, re.I)
    if supported and n >= int(supported.group(1)):
        return Conclusion.SUPPORTED, f"{n} meets \"{x.supported_if}\"."
    if (below and n < int(below.group(1))) or (at_most and n <= int(at_most.group(1))):
        return Conclusion.REFUTED, f"{n} meets \"{x.refuted_if}\"."
    return Conclusion.INCONCLUSIVE, f"{n} falls between the two criteria."


def plain_file_summary(f: ProjectFile, version: FileVersion, text: str,
                       previous: FileVersion | None = None) -> FileSummary:
    """A summary without AI: the document's first lines, and its sentences with numbers as its claims."""
    if not f.kind.readable:
        return FileSummary(f"{files.LABELS[f.kind]}: not read in this version." + (
            f" The team says: {version.note}" if version.note else ""))
    if not text.strip():
        return FileSummary("No readable text: the file may be scanned, protected or damaged.")
    lines = [re.sub(r"^[#*\-\s\[\]0-9.]*(?=\S)", "", line).strip() for line in text.splitlines()]
    lines = [line for line in lines if len(line) > 3]
    summary = " ".join(lines[:2])[:300]
    sentences = [s.strip(" -*#") for s in re.split(r"(?<=[.!?])\s+|\n", text)]
    numbered = [s for s in sentences if re.search(r"\d|%|\$", s) and len(s) > 12]
    # "28 of 40 said …", percentages and prices read as claims; "we asked 40 students" is the method
    claims = sorted(numbered, key=lambda s: not re.search(r"\d+\s+of\s+\d+|%|\$\d", s))[:4]
    claims = [s[:200] for s in claims]
    if previous is not None:
        summary = f"Version {version.number}. {summary}"
    return FileSummary(summary + " (Summary without AI: the document's first lines.)", claims)


class ScriptedCoach:
    label = "Scripted demo (no AI)"

    def _used(self, v: Venture) -> list[ScriptLine]:
        sent = {self._untag(m.text) for m in v.conversation if m.author not in (EIR, SYSTEM)}
        return [line for line in script_for(v.id) if line.text in sent]

    @staticmethod
    def _untag(text: str) -> str:
        """Messages saved by v0.15 may still start with @EIR."""
        return re.sub(r"@eir(?![A-Za-z0-9_])", "", text, flags=re.IGNORECASE).strip(" \t\n:：")

    def suggestions(self, v: Venture, speaker: str) -> list[str]:
        used = {line.id for line in self._used(v)}
        return [line.text for line in script_for(v.id) if line.id not in used and line.speaker in ("any", speaker)]

    @staticmethod
    def _grounded(v: Venture) -> str:
        """Bring up what the team left unresolved before answering, like a human EIR would."""
        threads = memory.open_threads(v)
        if not threads:
            return ""
        return "Before we go further, a few things from your project are still open:\n" + "\n".join(threads) + "\n\n"

    # ---- grading ----
    def grade_evidence(self, v: Venture, question: str, answer: str) -> grading.Grade:
        return grading.grade(answer)

    def rate_method(self, v: Venture, method: str) -> grading.Grade:
        return grading.method_rung(method)

    # ---- lead mentor (multi-mentor design): deterministic stand-in for the AI, using the same actions ----
    def lead_turn(self, v: Venture, box: ToolBox, event: LeadEvent | None = None) -> LeadTurn:
        _, box.refs = memory.window(v)
        if event is not None:
            return LeadTurn(self._event(v, box, event))
        last = next((m for m in reversed(v.thread(v.lead_mode)) if m.author not in (EIR, SYSTEM)), None)
        if last is None:
            return LeadTurn(OPENING[v.lead_mode])
        text, name = self._untag(last.text), v.display_name(last.author)
        if last.file_id and (f := v.file(last.file_id)) is not None:
            return LeadTurn(self._file_reply(v, box, f, f.version(last.file_version) or f.latest, name))
        line = next((l for l in script_for(v.id) if l.text == text), None)
        if line is not None:
            for t in line.tools:
                box.call(ToolCall(t["name"], t["name"], {"source": box.last_ref, **t.get("args", {})}))
            return LeadTurn(line.reply)
        if v.lead_mode == LeadMode.OPTIMIZE and not any(m.author == EIR for m in v.thread(LeadMode.OPTIMIZE)):
            ok, best = modes.entry_check(v)
            if not ok:
                box.call(ToolCall("switch", "suggest_mode_switch",
                                  {"to": LeadMode.LAUNCH.value, "reason": "No customer behavior recorded yet"}))
                return LeadTurn(f"{name}, before we optimize anything: {modes.entry_message(best)}")
        topic = consult.topic_of(text)
        busy = v.open_consultation(topic) if topic else None
        if busy is not None:  # topics don't cross: the open consultation answers this
            return LeadTurn(f"{name}, that is exactly what the {consult.name_of(busy.consultant)} consultant is working "
                            "on with you. Open their panel on the right and continue there, so you get one clear "
                            "answer; I'll pick it up from their summary.")
        low = text.lower()
        if PRACTICE_WORDS.search(text):
            character, scenario, reason = practice_for(v, text)
            box.call(ToolCall("practice", "suggest_practice", {"character": character, "scenario": scenario,
                                                               "reason": reason}))
            return LeadTurn(f"Good idea to rehearse first, {name}. {reason} I've put a button under this reply. "
                            "The session is yours: I see its feedback only if you send it to me.")
        if any(w in low for w in ("consultant", "expert", "specialist")):
            cid = topic or "pricing"
            result = box.call(ToolCall("consult", "open_consultation",
                                       {"consultant": cid, "question": text[:160], "brief": self._brief(v, text)}))
            if result.startswith("ERROR"):
                return LeadTurn(f"{name}, the {consult.name_of(cid)} consultant is already working with you. Open their "
                                "panel on the right and continue there.")
            return LeadTurn(f"Good idea, {name}. I've asked the {consult.name_of(cid)} consultant to work on this with "
                            "you and wrote them a brief. Open them from the rail on the right; I'll take it from their "
                            "summary.")
        if any(w in low for w in ("human", "real mentor", "real person")):
            box.call(ToolCall("human", "request_human", {"topic": text[:120], "reason": "the team asked for a person"}))
            return LeadTurn(MENTOR_REPLY)
        if any(w in low for w in ("remember", "recall", "之前", "记得", "回忆")):
            from .. import recall
            hits = recall.search(v, text, exclude_message_ids={last.id}, limit=3)
            if hits:
                quotes = "\n\n".join(f"**{hit.source_label}**\n> {hit.text}" for hit in hits)
                return LeadTurn("Here are related entries from your team's saved history:\n\n" + quotes +
                                "\n\nThese are earlier statements. Use the current project records to check what "
                                "has changed; retrieval does not verify a claim.")
        pressing = questioning.next_question(v) if v.lead_mode == LeadMode.LAUNCH else self._lens_question(v)
        if pressing:
            return LeadTurn(self._grounded(v) + f"{name}, before we go on:\n\n{pressing}")
        return LeadTurn(self._grounded(v) + LEAD_FALLBACK.format(name=name))

    @staticmethod
    def _brief(v: Venture, question: str) -> str:
        return overview.consultation_brief(v, question or overview.status(v).focus)

    @staticmethod
    def _file_reply(v: Venture, box: ToolBox, f: ProjectFile, version: FileVersion, name: str) -> str:
        """An upload: what the document claims is a claim, not evidence. New file: record its first claim as an
        assumption and suggest one revision (a task linked to the file). New version: ask which revisions it made."""
        if not f.kind.readable or not version.chars:
            return (f"{name}, I can't read {f.name} in this version. Tell me in one or two sentences what it shows and "
                    "what you want to learn from it.")
        if version.number > 1:
            pending = files.revision_tasks(v, f)
            asks = "\n".join(f"- {s.text}" for s in pending) or "- none were open"
            return (f"Thanks, {name}: version {version.number} of {f.name}. {version.summary}\n\nOpen revisions for "
                    f"this file:\n{asks}\n\nWhich of these did this version address? Tick them off in the Action Plan, "
                    "or tell me what changed.")
        claims = version.claims[:3]
        if not claims:
            return (f"Thanks, {name}. I read {f.name}: {version.summary}\n\nWhich claim in it matters most for your "
                    "venture, and what evidence do you have for it?")
        box.call(ToolCall("assume", "add_assumption", {"statement": claims[0], "importance": 0,
                                                       "source": box.last_ref}))
        box.call(ToolCall("revise", "add_task", {"text": f"Revise {f.name}: say who said or did this, and how many: "
                                                         f"\"{claims[0][:80]}\"", "file_id": f.id,
                                                 "source": box.last_ref}))
        listed = "\n".join(f"- {c}" for c in claims)
        return (f"Thanks, {name}. I read {f.name}. Its key claims, as the document states them:\n{listed}\n\n"
                "A document is your claim, not evidence yet: I recorded the first one as an assumption to test, and "
                "suggested a revision. Who said or did each of these, and how many?")

    @staticmethod
    def _lens_question(v: Venture) -> str:
        for x in modes.lenses():
            if x.id not in v.lenses:
                return f"**{x.title}** · {x.question}" + (f"\n\n{x.probes[0]}" if x.probes else "")
        b = modes.lens(v.diagnosis.bottleneck)
        if b is None:
            return "Every lens has a grade. Which one hurts most if it fails? That is your bottleneck."
        return f"Your bottleneck is **{b.title}**. What is the smallest experiment this week, and what result would " \
               "prove you wrong?"

    def _event(self, v: Venture, box: ToolBox, event: LeadEvent) -> str:
        if event.kind == "invite":
            question = overview.consultation_question(v, event.ref)
            box.call(ToolCall("consult", "open_consultation", {"consultant": event.ref, "question": question,
                                                               "brief": self._brief(v, question)}))
            return (f"I've asked the {consult.name_of(event.ref)} consultant to look at this with you: {question} "
                    "Their panel is open on the right; I'll take it from their summary.")
        if event.kind == "summary":
            c = v.consultation(event.ref)
            s = c.summary
            for todo in s.suggested_todos:
                box.call(ToolCall("task", "add_task", {"text": todo, "source": f"consult:{c.id}"}))
            if s.needs_human:
                box.call(ToolCall("human", "request_human", {"topic": s.human_topic or c.question,
                                                             "reason": "the consultant flagged it"}))
            lines = [f"The {consult.name_of(c.consultant)} consultant's key points:",
                     *(f"- {x}" for x in s.conclusions or ["(no conclusions recorded)"])]
            if s.student_note:
                lines.append(f"\nYour note: \"{s.student_note}\"")
            if s.needs_human:
                lines.append(f"\nThis needs a human EIR ({s.human_topic}). Use the menu to share a brief.")
            if s.suggested_todos:
                lines.append("\nI added their suggested to-dos to your Action Plan; undo any you disagree with.")
            return "\n".join(lines)
        if event.kind == "practice":
            return self._practice_event(v, box, v.rehearsal(event.ref))
        if event.kind == "judge":
            x = v.experiment(event.ref)
            conclusion, why = scripted_judgment(x)
            result = box.call(ToolCall("judge", "judge_experiment",
                                       {"experiment_id": x.id, "conclusion": conclusion.value, "why": why}))
            if result.startswith("ERROR"):
                return f"I can't judge it yet: {result.removeprefix('ERROR: ')}"
            return (f"Against the criteria you agreed in advance: **{conclusion.value}**. {why} This method produces "
                    f"{x.method_rung.label.lower()} evidence, whatever the result.")
        return "Noted."

    @staticmethod
    def _practice_event(v: Venture, box: ToolBox, r: Rehearsal) -> str:
        """Practice feedback came in: the top fix becomes a task and, after a session with the judge, where the team
        practised its pitch answers pd_practice (rung 1). Nothing else changes: practice is not evidence."""
        f, source = r.feedback, f"practice:{r.id}"
        top = next(iter(f.fixes or f.problems or f.checks), "")
        if top:
            box.call(ToolCall("task", "add_task", {"text": f"From practice: {top}"[:240], "source": source}))
        pitched = practice.spec(r.character).sees == practice.SUBMISSION and v.lead_mode == LeadMode.LAUNCH
        if pitched:
            hardest = f.tough_questions[0].split(" → ")[0] if f.tough_questions else ""
            box.call(ToolCall("answer", "record_answer", {
                "question_id": "pd_practice", "rung": 1, "source": source,
                "text": f"Practised the pitch with the AI competition judge ({today()})."
                        + (f" Hardest question: {hardest}" if hardest else "")}))
        lines = [f"Thanks for sending this, {v.display_name(r.shared_by)}. The practice coach's verdict: {f.verdict}"]
        if top:
            lines.append(f"The point that matters most for the venture: {top} I added it to your Action Plan; undo it "
                         "if you disagree.")
        lines.append(("I also recorded where you practised your pitch. " if pitched else "")
                     + "Practice is not evidence, so nothing else in your records changes.")
        if r.shared_note:
            lines.append(f"Your note: \"{r.shared_note}\"")
        return "\n\n".join(lines)

    def summarize_day(self, v: Venture, label: str, messages: list[Message]) -> str:
        team = [m for m in messages if m.author not in (EIR, SYSTEM)]
        first = self._untag(team[0].text)[:160] if team else ""
        return (f"{len(team)} team message(s). It started with {v.display_name(team[0].author)}: \"{first}\"."
                if team else "Only notes from the app.")

    # ---- consultants (deterministic stand-ins: prepared lines, else the consultant's checklist) ----
    @staticmethod
    def _team_messages(c: Consultation) -> list[Message]:
        return [m for m in c.messages if m.author != CONSULTANT]

    def consult_turn(self, v: Venture, c: Consultation) -> ConsultTurn:
        s = consult.spec(c.consultant)
        team = self._team_messages(c)
        text = team[-1].text.strip() if team else ""
        script = consult_script_for(v.id, c.consultant)
        line = next((l for l in script.lines if l.text == text), None) if script else None
        if line is not None:
            return ConsultTurn(line.reply, line.propose_end)
        low = text.lower()
        hand_off = next((t for t in s.must_hand_off if t in low), None)
        if hand_off:
            return ConsultTurn(f"{hand_off[0].upper()}{hand_off[1:]} is a decision for a human AIN EIR, not for me. "
                               "I'll flag it in my summary so your mentor routes it to someone with "
                               f"{s.hand_off_expertise.lower()} experience. Meanwhile I can help you prepare the "
                               "questions to ask them.")
        other = consult.topic_of(text)
        if other and other != c.consultant:
            return ConsultTurn(f"That is a {consult.name_of(other).lower()} question, outside what I cover. I'll note "
                               f"it for your mentor. Back to what your mentor asked me: {c.question}")
        asked = sum(1 for m in c.messages if m.author == CONSULTANT)  # the opening asked the first check
        if asked < len(s.checklist):
            return ConsultTurn(f"Noted. Next check: {s.checklist[asked]}\n\n_Scripted demo reply (no AI connected)._")
        return ConsultTurn("I think we have covered your mentor's question. Shall I write the summary for your mentor? "
                           "Press **End and send back** when you are ready.", propose_end=True)

    def consult_summary(self, v: Venture, c: Consultation) -> ConsultationSummary:
        team = self._team_messages(c)
        script = consult_script_for(v.id, c.consultant)
        if script and script.summary and {m.text for m in team} & {l.text for l in script.lines}:
            return deepcopy(script.summary)
        s = consult.spec(c.consultant)
        asked = sum(1 for m in c.messages if m.author == CONSULTANT)
        said = [f"{v.display_name(m.author)} said: {m.text[:200]}" for m in team[-3:]]
        return ConsultationSummary(
            question=c.question,
            conclusions=(said or ["Nothing was discussed yet."]) + ["(Scripted demo summary: no AI connected.)"],
            missing_evidence=[f"Not covered yet: {q}" for q in s.checklist[asked:asked + 2]],
            out_of_scope=[m.text for m in team if (t := consult.topic_of(m.text)) and t != c.consultant])

    def consult_suggestions(self, v: Venture, c: Consultation, speaker: str) -> list[str]:
        script = consult_script_for(v.id, c.consultant)
        if script is None:
            return []
        sent = {m.text for m in self._team_messages(c)}
        return [l.text for l in script.lines if l.text not in sent and l.speaker in ("any", speaker)]

    # ---- project files ----
    def summarize_file(self, v: Venture, f: ProjectFile, version: FileVersion, text: str,
                       previous: FileVersion | None = None) -> FileSummary:
        return plain_file_summary(f, version, text, previous)

    # ---- practice characters (prepared lines for the demo ventures, else the simple rules below) ----
    def practice_start(self, v: Venture, r: Rehearsal, material: str = "") -> PracticeStart:
        script = practice_script_for(v.id, r.character, r.scenario)
        persona = profile = ""
        if practice.spec(r.character).sees == practice.SEGMENT:
            persona, profile = ((script.persona, script.persona_profile) if script and script.persona
                                else practice.plain_persona(v, r))
        return PracticeStart(practice.opening(v, r, first_question(v, r), persona), persona, profile)

    def practice_turn(self, v: Venture, r: Rehearsal, material: str = "") -> PracticeTurn:
        s, sc = practice.spec(r.character), practice.scenario_of(r)
        team = practice.team_messages(r)
        text = team[-1].text.strip() if team else ""
        script = practice_script_for(v.id, r.character, r.scenario)
        line = next((l for l in script.lines if l.text == text), None) if script else None
        if line is not None:
            return PracticeTurn(line.reply, line.wrap_up)
        if practice.turns(r) >= s.wrap_after:
            return PracticeTurn(s.wrap_up, True)
        if s.sees == practice.SEGMENT:
            return PracticeTurn(_customer_reply(text) + SCRIPTED)
        queue = scripted_questions(v, r)
        replies = sum(1 for m in r.messages[1:] if m.author == CHARACTER)
        index = replies + (1 if "{first}" in sc.opening else 0)
        if index >= len(queue):
            return PracticeTurn(s.wrap_up, True)
        lead = ""
        if sc.pitch_seconds and replies == 0:  # the pitch
            t = practice.estimate(text, sc.pitch_seconds)
            lead = (f"That ran about {practice.clock(t.seconds)}, over your {practice.clock(t.target)}. " if t.over
                    else "Thank you. ")
        elif s.sees == practice.RECORDS and (claims := practice.find_unsupported(v, [text])):
            sentence, why = claims[0]
            return PracticeTurn(f"Hold on: {practice.quote(sentence.rstrip('.!'))}? {why[0].upper()}{why[1:]}. "
                                "Which is it?" + SCRIPTED)
        elif practice.HONEST.search(text):
            lead = "Fair, that's honest. "
        elif r.difficulty == Difficulty.TOUGH and not practice.NUMBER.search(text):
            lead = "I didn't hear a number there. "
        elif r.difficulty == Difficulty.FRIENDLY:
            lead = "Thanks, that helps. "
        return PracticeTurn(lead + queue[index] + SCRIPTED)

    def practice_feedback(self, v: Venture, r: Rehearsal, material: str = "") -> RehearsalFeedback:
        """The prepared feedback when every team message was a prepared line, else the keyword checks."""
        script = practice_script_for(v.id, r.character, r.scenario)
        said = {m.text.strip() for m in practice.team_messages(r)}
        if script and script.feedback and said and said <= {l.text for l in script.lines}:
            return deepcopy(script.feedback)
        return practice.plain_feedback(v, r)

    def practice_hint(self, v: Venture, r: Rehearsal, material: str = "") -> str:
        return practice.plain_hint(v, r)

    def practice_suggestions(self, v: Venture, r: Rehearsal, speaker: str) -> list[str]:
        script = practice_script_for(v.id, r.character, r.scenario)
        if script is None:
            return []
        said = {m.text for m in practice.team_messages(r)}
        return [l.text for l in script.lines if l.text not in said and l.speaker in ("any", speaker)]
