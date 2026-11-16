# Architecture (v0.19)

```
app.py                 entry point: page config + router (wiring only)
eir/                   domain package: no Streamlit imports (a test enforces it)
  models.py            Venture and everything it remembers (dataclasses + enums; every field has a default)
  serde.py, migrate.py dict <-> dataclass (missing fields fall back to defaults); upgrade of older saved ventures
  repository.py        VentureRepository + InMemoryRepository / JsonFileRepository
  filestore.py         where project files live (outside the venture records): LocalFileStore / MemoryFileStore
  clock.py             the one place that produces dates and timestamps
  access.py            every confidentiality rule: who sees which venture, what staff see, what a consultant and a
                       practice character see, what the lead mentor gets from a consultation or a practice session
  actions.py           everything a member does inside a venture (pages call only these)
  teams.py             create / join a project, project settings, the intro and core content the team writes on the
                       Overview (never evidence)
  records.py           the records the lead mentor keeps: focus, assumptions + evidence, answers, canvas, lenses, tasks
  changes.py           every record change with before/after snapshots: "Recent changes" and Undo per mentor action
  experiments.py       criteria agreed before the start, locked while running, judged by the mentor
  roadmap.py           Foundry modules, deliverables, key questions on the 6-rung ladder, step judgment, calibration,
                       graduation; knowledge/roadmap.json
  modes.py             the two lead mentors (Launch / Optimize): recommendation, entry check, switch, six lenses
  consult.py           consultants: skeletons (knowledge/consultants.json), start, rules, finish, rail state
  practice.py          practice characters (knowledge/practice.json): sessions, what each character knows, pitch
                       timing, the "Recommended now" choice, checks against the records, feedback without AI
  files.py, extract.py project files: kinds, versions, text extraction on this computer, reading in parts; whether a
                       file was read or discussed (from the chat, nothing extra stored)
  overview.py          read models for the Overview, the project's homepage: the focus card (why now, evidence for
                       and against, what is missing, the main button; rules over the records), progress in words,
                       the snapshot, recent activity with the timeline, the start page of a new project; the briefing;
                       the preliminary plan
  memory.py            the briefing, the mentor's context (with the team's own description, as claims), the chat
                       window, day summaries
  tools.py             the lead mentor's actions (function calling) and the rules that keep them honest
  llm.py               OpenAI-compatible / Anthropic client; native tool loop with a JSON-actions fallback
  grading.py           keyword grading of evidence and experiment methods (scripted coach; AI fallback)
  questioning.py       the question chain: specific → evidence → alternatives → consequence → test
  brief.py             the consent-based brief for a human AIN EIR
  coach/               the mentors behind one interface (base.py: Coach protocol)
    ai.py              AICoach: lead mentor, consultants, practice characters and coach, summaries, grading
    scripted.py        ScriptedCoach: the same behaviour without AI (prepared lines from eir/seed/*.json)
  prompts/             all prompt text: lead_common / lead_launch / lead_optimize, consultant, consultant_summary,
                       file_summary, day_summary, practice_character / _customer_profile / _feedback / _hint
                       (tune behaviour here, no code changes)
  seed/                fictional demo ventures, their scripts (mentor, consultants, practice); seed/files/ documents
knowledge/             roadmap.json, diagnostics.json (six lenses), consultants.json, practice.json, ain_resources.json
ui/                    Streamlit screens: thin, call eir/ for everything
  state/core.py        the only code that touches st.session_state: sign-in, page (and the top navigation's key),
                       dialog, drawer, the open practice session and setup, the Overview's upload box and the file
                       to discuss in the chat, PageContext
  topbar.py, menu.py   top navigation (Virtual EIR · Overview · Action Plan · Practice; the chat's page id is still
                       "Mentor") and the ⋯ menu with its dialogs
  pages/               mentor_chat.py, overview.py, action_plan.py, practice.py (registry in __init__.py)
  consult_drawer.py    the consultant rail and drawer on the Mentor page
  lobby.py, login.py, staff.py, components.py, theme.css
eval/                  coaching cases from Roberto's examples + run_eval.py; practice_cases/ + run_practice_eval.py
                       (replay, checks, AI judge)
scripts/               smoke_llm.py (connection), smoke_lead / smoke_consult / smoke_files / smoke_practice
                       (real-model checks), shoot_ui.py (screenshots in Edge)
tests/                 domain, coach (fake model), UI click-through (AppTest), eval harness
```

## Rules that keep it clean

1. **Dependency direction:** `ui → eir`, never the other way. Nothing in `eir/` imports Streamlit.
2. **Pages never edit a `Venture` directly.** They call `eir/actions.py` or `eir/teams.py` (which check membership and
   validate), then `ctx.save()`.
3. **Pages receive a `PageContext`** (account, venture, member id, repo, coach, file store). All `st.session_state`
   access lives in `ui/state/`; widget keys aside.
4. **Every record change goes through `records` / `experiments`**, so it is logged in `Venture.changes` (Recent
   changes) and a mentor's change can be undone. Students' own edits are logged but not undone from the chat.
5. **Enum values are saved in venture files:** add values, never rename them. New fields always get a default.
6. **The mentor writes only through its actions** (`eir/tools.py`). Every write cites the team message it comes from
   (`m3`), a returned consultation (`consult:<id>`) or practice feedback the team sent (`practice:<id>`; accepted only
   for a task, a new assumption, the focus and the answer to `pd_practice`, at rung 1). There is no action that
   completes a Foundry step, moves the module or edits the team's documents; `read_file` and `suggest_practice`
   change no record.
7. **Access rules live in `eir/access.py`:** staff see the directory, judgments to check, graduation packets and
   shared briefs, never chats, consultations, practice sessions or files. A consultant sees its brief, a read-only
   overview and the summaries of attached files, never the mentor chat. A practice character sees what its kind
   allows (`character_view`: a customer only who they are). The lead mentor gets only a consultation's summary and
   the feedback of a practice session a member sent, never the conversations. Practice characters get no actions.
8. **The AI never moves a venture on the roadmap.** The rules judge a step (`roadmap.judge`); AIN EIRs check the first
   three Ready judgments and decide graduation.
9. **Code changes the page with `state.go_to`.** It gives the top navigation a new key, so the browser draws it with
   the new page selected. (Setting the old control's value sometimes left the old tab selected when another run
   followed at once, e.g. after a dialog closed.) On the page, call it from a button's `on_click`. Inside a dialog,
   call it in the run and then `st.rerun()`: a click in a dialog reruns only the dialog.
10. **Run `python -m pytest -q` before a demo** and report the actual result. Run `python eval/run_eval.py` after
   changing a mentor prompt, and `python eval/run_practice_eval.py` after changing a practice prompt or character.

## One mentor reply, step by step

1. `actions.mentor_message` saves the member's message, then `_lead_reply`:
2. `memory.ensure_day_summaries` writes a 2–3 sentence summary of each earlier day once (the briefing's "last time").
3. A `ToolBox` collects what the mentor may do this turn. `coach.lead_turn` builds the system prompt (`lead_common.md`
   + the Launch or Optimize rules + `memory.lead_context`) and the chat window (`memory.window`: the last 30 messages
   / 16k characters, team messages tagged `[m1]`…).
4. `llm.run_tools` runs the native tool loop (or, if the endpoint rejects tools, a JSON `actions` block). Each action
   is one change group; a failed action changes nothing; if the whole turn fails, `ToolBox.rollback` undoes it and
   the member's message stays (Ask again).
5. The reply is saved with its change groups (the "Record updates" list with Undo), an opened consultation and a
   suggested switch of mentor, if any.

Events use the same path (`actions.mentor_event`):
- a member asks for a consultant from the rail;
- a consultation summary comes back;
- an experiment needs judging;
- a member sends practice feedback.

The event note remembers the event, so a failed reply can be retried.

## A project file from the Overview, step by step

1. **Save.** The upload box in the "Add a file" dialog calls `actions.save_file`. The file becomes a new file, or the
   next version of one with the same name. Its text is extracted on this computer, and the summary is the start of
   that text, marked "not reviewed" (`files.saved_summary`). There is no model call and no change to any record; the
   timeline notes the upload.
2. **Choose to discuss.** "Read and discuss it" (with an optional note) or a file's "Discuss" calls
   `state.request_discussion`, which opens the chat. These buttons sit in dialogs, so they act in the run and call
   `st.rerun()`.
3. **Discuss.** The chat page (`mentor_chat._discuss_file`) calls `actions.discuss_file`:
   - the Virtual EIR summarizes the latest version, against the previous one if there is one;
   - a team message with the file and the note is posted;
   - the normal reply follows (`_lead_reply`).

   If the reply fails, the message stays and "Ask the Virtual EIR again" retries it.
4. **Status on the Overview,** worked out from the chat (`files.discussion`): "Discussed with your Virtual EIR" when a
   team message carries the latest version; "Read by your Virtual EIR" when the summary is the Virtual EIR's
   (`files.read_by_eir`); otherwise "Not discussed yet".

A file attached to a chat message does both steps at once (`actions.upload_file`).

## One practice session, step by step

1. **Start.** `actions.start_practice` checks the settings (`practice.new`). Then `coach.practice_start` writes:
   - a target customer: a new made-up person, generated from the segment only;
   - a judge or challenger: its first question.

   The opening line comes from the scenario's template. If the model fails, the scripted opening is used.
2. **Each message.** `coach.practice_turn` sees:
   - only `access.character_view`;
   - `practice.material`: the chosen files' summaries, plus the start of their text unless the venture is
     IP-sensitive;
   - the conversation.

   The character ends the session with `[[WRAP_UP]]`. Once the team has sent the planned number of messages, the
   prompt tells it to close. If a reply fails, the member's message stays and `practice_retry` asks again.
3. **Hints.** `practice_hint` comes from the practice coach (the prompt sees the records). The character never sees a
   hint.
4. **End.** `actions.end_practice`: the practice coach writes the feedback (`practice_feedback.md`), including the
   app's own check of what the team said against the records (`practice.unsupported_claims`). If the model fails,
   `practice.plain_feedback` (keyword checks) is used.
5. **Send.** `actions.share_practice` sends the feedback and one line through `mentor_event("practice")`. The mentor
   reads `access.lead_view_of_practice`, never the conversation.

## Storage and collaboration boundary

- Ventures: JSON files in `~/.virtual_eir/ventures` (`EIR_DATA_DIR`), seeded with the demo ventures when empty. Project
  files: `~/.virtual_eir/files/<venture>/<file>/v<n>.<ext>` plus the extracted text (`EIR_FILES_DIR`). Both stay
  outside the project folder because that folder may be synced. `EIR_STORAGE=memory` keeps everything in the session
  (tests).
- Plain JSON and plain files are a demo layer: no real accounts, no authorization at the storage boundary, no
  concurrent writes, no encryption. A production version needs the university's sign-in, a database and file storage
  with access control; only `ui/state/core.py` constructs the stores.

## How to…

| Task | Where |
|---|---|
| Change how the mentor coaches | `eir/prompts/lead_common.md` (+ `lead_launch.md`, `lead_optimize.md`), then `python eval/run_eval.py` |
| Change a consultant | `knowledge/consultants.json` (scope, checklist, red flags, evidence, what must go to a human) and `eir/prompts/consultant*.md` |
| Change or add a practice character | `knowledge/practice.json` (what it sees, scenarios, difficulty, behaviour, rubric with good/fix, questions without AI) and `eir/prompts/practice_*.md`, then `python eval/run_practice_eval.py` |
| Change key questions or required evidence | `knowledge/roadmap.json` |
| Add a mentor action | a function and a `Tool` entry in `eir/tools.py` (validate arguments, cite a source, one change group) |
| Add a field to the venture | the dataclass in `eir/models.py` **with a default**; upgrade old data in `eir/migrate.py` if needed |
| Add / edit a demo venture or its scripts | a JSON file in `eir/seed/` (`script`, `consult_script`, `practice_script`); demo documents in `eir/seed/files/` |
| Add an evaluation case | a JSON file in `eval/cases/` (the mentor) or `eval/practice_cases/` (a practice character); fictional only |
| Configure the real AI | `~/.streamlit/secrets.toml` (see `.streamlit/secrets.toml.example`); check with `python scripts/smoke_llm.py` |
| Use real storage | implement the `VentureRepository` and `FileStore` interfaces; return them from `ui/state/core.py` |
| Change colours / spacing | `ui/theme.css` and `.streamlit/config.toml` |
