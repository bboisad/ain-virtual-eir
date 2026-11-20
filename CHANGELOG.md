# Changelog

## v0.19 — 2026-11-13  A simpler Overview, from outside feedback
`docs/DECISIONS.md` "The Overview as the project's homepage" explains the reasons. The design came from one question,
answered by a classmate and by ChatGPT (GPT-6); a third person said those two covered their view. The product owner
decided on Nov 12.
- **The Overview answers three things:** what we are doing, where we are stuck, what we do next.
  - **Header:** the project in the team's words, marked "✎ Team statement", with Edit.
  - **Focus card, the main block:**
    - the current focus and why now;
    - the evidence for and against, each with its own level;
    - what is still missing and the next step;
    - one main button that follows the state: review and start the test, record the result, open the Action Plan,
      or ask your Virtual EIR.

    Every line except the focus is a rule over the records.
  - **Progress:** the four deliverables in one row, and the key question to answer now.
  - **Snapshot:** customer, solution and business model in the team's words, next to their evidence levels. When the
    team has not written a line, the Virtual EIR's canvas text is offered as a draft ("Use this as our statement").
  - **Recent activity:** the last three changes, the timeline included, next to the latest files.
- **Dialogs, opened from where each belongs:**
  - the key questions and Check this step, from the progress;
  - the full canvas or the six lenses, and editing a snapshot line, from the snapshot;
  - the full history with the decisions, from the recent activity;
  - Add a file, All files and each file, from the files.
- **A new project gets a start page:** "Start the conversation", then upload a file or invite the team. The full page
  appears once the team has said something or there is a record.
- **Evidence shows its name first:** for example "Customer statements · Level 3". Click it to see what the level
  means, what stronger evidence would be, and where it comes from. This applies to chips across the app and to the
  briefing. Models, prompts and the evaluation still read the old labels.
- **Moved:**
  - all assumptions → the top of the Action Plan (what you believe → how you test it → what you do);
  - the preliminary plan and stepping back a module → the ⋯ menu.
- **Removed from the Overview:** the folded Details area, the "where it stands" sentences, the stage and type chips, the
  explanatory captions, and the evidence-ladder line.
- **Code:**
  - `eir/overview.py`: `focus_card`, `steps`, `current_question`, `is_new`, `decisions`; `recent_changes(...,
    events=True)`; `progress_lines` is removed;
  - `eir/models.py`: `Rung.plain` and `RUNG_NAMES`;
  - `ui/components.py`: `evidence_popover` and `source_tag`.
- **Unchanged:** the data model, the rules, and what the models see, so no new evaluation run is needed.
- **Checks:**
  - 237 tests (226 before);
  - screenshots in Edge at 1366 and 1920 (`scripts/shoot_ui.py … --overview`): Campus Loop, every dialog, and a new
    project before and after its first message;
  - the main, files, drawer and practice flows still run.

## v0.18 — 2026-11-12  The Overview becomes the project's homepage
Design: `../design/multi_mentor_decisions_zh.md`, sections 3, 4 and 6 (decided with the product owner on Nov 12);
`docs/DECISIONS.md` "The Overview as the project's homepage".
- **Four blocks on the Overview,** in this order:
  1. **Project intro** in the team's words: name, one line, who it serves, the problem. "Edit the project intro" →
     **Save and confirm** records who confirmed it and when.
  2. **Where it stands, from the records only:** the Foundry position (or the bottleneck), two or three lines of
     progress built from the records (finished steps and whether an AIN EIR confirmed them, the latest tested
     experiment, the strongest evidence), the step check, and **Your Virtual EIR suggests**. That box has its own tint
     and an AI chip, and shows the focus and the next step with who set them.
  3. **Core of the project:** target customer, product or solution, business model, in the team's words. Next to each
     is the evidence grade from the canvas (Launch) or the lens (Optimize). **View and edit** shows the full text and
     what the records say; editing the words never changes the grade.
  4. **Project files.**
- **Project files on the Overview:**
  - **Upload:** a file is **saved only**, with no model call and no change to the records.
  - **Discuss when you choose:** **Read and discuss it** (optionally saying what to look at) or **Discuss** opens the
    chat, where the Virtual EIR reads the file and replies. Back on the Overview the file shows as discussed, with
    **Open the chat**.
  - **Each file shows:** type, version, update time and who uploaded it, its status (Not discussed yet · Read by your
    Virtual EIR · Discussed with your Virtual EIR), and Download.
  - **Preview and details:** the Virtual EIR's summary (AI chip), the start of the text or the picture, the key claims,
    the open revisions, every version to download, and remove with a confirmation.
  - **Links** are listed with the team's description and never opened or discussed.
  - Attaching a file to a chat message still works.
- **Folded at the bottom:** the riskiest assumptions, the evidence map, key questions, recent changes, all
  assumptions, the preliminary plan and stepping back. Tasks and experiments stay in the Action Plan.
- **Unchanged:** a project still opens on the Virtual EIR chat, and the navigation keeps its order (decided Nov 12).
- **The Virtual EIR now sees the team's own description** (who it serves, problem, solution, business model) in its
  context, as claims and not evidence. Edits on the Overview reach it.
- **Fixed: the top navigation sometimes kept the old tab selected** after a page change made by code (about half the
  time when switching the Virtual EIR from the menu, in Edge), so clicking that tab did nothing. Now `state.go_to`
  gives the control a new key, and discussing a file changes the page before the run.
- **Code:**
  - `eir/actions.py`: `save_file` and `discuss_file` (`upload_file` does both);
  - `eir/teams.py`: `save_project_intro`; `save_project_essentials` now takes only the fields given;
  - `eir/overview.py`: `progress_lines`, `focus_owner`, `set_by`, `essentials`;
  - `eir/files.py`: `discussion`, `read_by_eir`, `saved_summary`;
  - `ui/state`: the upload box, the file to discuss, the navigation key.
- **Checks:**
  - 226 tests (from 214);
  - real model (Claude Sonnet 4.6): `scripts/smoke_files.py` now saves version 2 on the Overview (no model call), then
    discusses it. The Virtual EIR compared the versions and ticked off the fixed revision;
  - screenshots: `scripts/shoot_ui.py … --overview` at 1366 and 1920. The script's labels now say "Virtual EIR".
- **Also in this version, made on the product owner's computer (Nov 8):**
  - **"Mentor" became "Virtual EIR"** in the interface and the prompts: the navigation, "Launch Virtual EIR", "Human
    EIR brief", "Ask the Virtual EIR again", "Ask the Virtual EIR to judge". The chat page's internal id stays "Mentor".
  - **OpenAI GPT-5.6 Luna** works through `eir/llm.py`: `reasoning_effort="none"` with function tools, and
    `max_completion_tokens`. Evaluation: lead Virtual EIR 135 of 137, practice 70 of 70. Five model-behavior findings
    are still open (`docs/OPENAI_MODEL_TEST_2026-11-08.md`).

## v0.17 — 2026-11-07  Practice: rehearse with AI characters
Design: `../design/multi_mentor_decisions_zh.md`, section 10 (decided with the product owner on Nov 7).
- **A fourth page, Practice,** with three AI role-play characters, each labelled as fictional:
  - **Target customer:** interview practice. A made-up person from the team's segment who knows nothing about the
    idea.
  - **Competition judge:** a 3-minute pitch and the panel's questions, as at the Mark Ain competition. Reads the
    Overview and the material the team chooses.
  - **Challenger:** tough questions on every record. Names what the team says that its records don't support.
- **Around the sessions:**
  - scenarios per character and three difficulty levels;
  - a "Recommended now" card that follows the venture's step;
  - a setup dialog with defaults;
  - pitch timing estimated from the word count;
  - hints from a practice coach, which the character never sees.
- **Feedback from a separate practice coach:**
  - scores per rubric dimension, what worked, three fixes, and the toughest questions with a stronger answer;
  - the challenger's weak spots, and the customer's points to check with real customers;
  - the claims the records don't support: the app's own check, merged with the coach's.
- **The session is the team's own.** The mentor, consultants and AIN staff never see it. A member may send the
  feedback (never the conversation), with one line, to the lead mentor.
- **Practice is not evidence.** From it, the mentor may only add tasks, new assumptions or the focus, and record a
  session with the judge as "where have you pitched it" (rung 1). Anything else citing practice is refused in code.
- **The mentor suggests practice** before a pitch or a round of interviews, or after a new deck. A button under its
  reply opens the setup, pre-filled.
- **Evaluation:** `eval/run_practice_eval.py` with 3 fictional cases:
  - the customer stays in role and doesn't know the idea;
  - the challenger catches contradictions with the records;
  - the judge notes an overlong pitch, doesn't coach and closes on time.

  Both runs passed 73 of 73 checks; the AI judge's mean was about 4.7 of 5.
- **Found with the real model and fixed:**
  - a stronger answer invented a fact;
  - the mentor wrote the internal "judge/pitch";
  - the judge said "Good pitch" mid-session;
  - the team's own plan ("we'd buy 300 crates") was flagged as unsupported.
- **Without AI:** the characters use prepared lines (Campus Loop) or simple rules, and the feedback comes from keyword
  checks, marked as simplified.
- **No voice yet:** pitches are typed or pasted.

## v0.16 — 2026-11-06  Multi-mentor: a lead mentor, consultants and project files
Design: `../design/multi_mentor_decisions_zh.md` (frozen item by item, 2026-11-05/06). Runs on a real model
(Claude Sonnet 4.6 through an OpenAI-compatible endpoint); the scripted coach keeps the keyless demo working.
- **Two lead mentors, the team chooses.** Launch (A: from an idea to a first launch on the Foundry roadmap; exit
  artifact: a one-page preliminary project plan) and Optimize (B: grades six lenses, names the bottleneck, runs one
  experiment). Creating a project asks two questions and recommends one; Optimize first checks for customer behavior
  (rung 4+) and suggests Launch if there is none; Launch suggests Optimize once. Switching keeps every record.
- **Every message gets a reply** (no more @EIR). The mentor updates the records itself through actions (function
  calling): focus, assumptions and evidence, key-question answers, canvas, lenses, experiments, tasks. Each update cites
  the team message it comes from, is listed under the reply and can be undone. It never marks a step complete.
- **Consultants** (pricing & business model, strategy & competition, funding readiness): the lead mentor writes a
  brief; the student talks to the consultant in a drawer over the chat (rail of avatars on the right, collapse keeps it
  open); the consultant proposes to end; the student previews the fixed-format summary, adds one line and sends it; the
  lead mentor reports the key points and updates the records. Must-hand-off topics (term sheets, valuation, …) always
  go to a human. The lead mentor never sees a consultation's transcript.
- **New pages:** top navigation Mentor · Overview · Action Plan, and a ⋯ menu (members, ask a human EIR, switch mentor,
  project settings). Overview: where you are (with the step check), next actions, riskiest assumptions, recent
  changes, evidence map, materials. Action Plan: experiments (criteria written before the start, locked while
  running, judged by the mentor; the rung comes from the method) apart from tasks.
- **Project files:** attach documents in the Mentor chat (PDF, Word, PowerPoint, Excel, CSV, text; images and links
  listed but not read; no code). Text is extracted on this computer; each version gets a summary and its key claims
  (claims, not evidence); same-name uploads become versions; the mentor suggests revisions as tasks and checks them in
  the next version; consultants see only attached summaries.
- **Evaluation:** `eval/cases/` holds 10 fictional cases from Roberto's coaching examples; `eval/run_eval.py` replays
  them, runs checks that need no judgment and an AI judge (results in `eval/results/`). Four tuning runs on Nov 6
  (EIR habits from Roberto's examples, a fixed reply shape, clearer handoff rules): checks 117 → 132 of 137, judge mean
  4.10 → 4.32 of 5 (`eval/results/NOTES.md`).
- **Removed:** the v0.14 team tools (notebook, meeting mode, manual canvas labels, discussion review, history and
  profile pages, intake interview) and the simple/full switch. Older saved ventures load and are upgraded.
- Real-model findings fixed on the way: replies split around tool calls were lost (now joined, without "Let me…"
  narration); a summary invented a disagreement from the brief; a pivot was recorded by rewording the old
  assumption; a vague document claim was recorded as evidence.

## v0.15 — 2026-10-29  Simple mode: questioning and step checks only
- **Simple mode is the default.** Students see two pages: *Conversation* (3-line EIR briefing + chat with two
  one-click prompts: "Question our weakest assumption", "What would prove us wrong?") and *Roadmap & step check*.
  Notebook, canvas, actions, discussion review, mentor brief, history, members and session scheduling are hidden,
  not deleted: sidebar → Prototype info → *Show all team tools* (or `EIR_FULL=1`) brings back the v0.14 version.
- **The Virtual EIR grades the evidence, students no longer do.** Students write the answer; `Coach.grade_evidence`
  returns the rung and a reason (scripted: keyword grader in `eir/grading.py`; AI: the model, falling back to the
  keyword grader). Answers that do not say how many or who are capped below "customers said".
- Under every answer that is not yet strong enough, the Roadmap shows the next question of the chain
  (`questioning.follow_up`).
- 85 tests, pyflakes clean.

## v0.14 — 2026-10-29  Design v0.2: the Virtual EIR questions and judges
Based on the 2026-10-22 meeting with Roberto Colangelo and his *virtual_eir_briefing* slides.
- **Roadmap = Foundry modules + the four deliverables AIN asks for** (customer discovery, business model canvas,
  pitch deck, business plan). Each deliverable lists its Disciplined Entrepreneurship steps (24-step book) and
  5–6 key questions (`knowledge/roadmap.json`).
- **6-rung evidence ladder** (assertion → desk research → customers said → did → paid → retained) replaces
  Claimed/Evidence. Every key question has a required rung (initial standard, to be calibrated).
- **Questioning engine** (`eir/questioning.py`): the Virtual EIR presses the weakest claim and climbs the chain
  be specific → evidence → alternatives → consequence → test. Used by the scripted coach and given to the AI prompt.
- **The Virtual EIR judges step completion** (*Ask the Virtual EIR to check this step*): Ready / Not yet, a reason
  per question, and "if I were you I would also consider" (optional). Ready moves the venture on, never past M3.
- **EIR calibration:** the first 3 Ready judgments per venture wait for an AIN EIR to agree or reopen (with a note).
  Graduation to NextCorps replaces the capstone gate: requested by the team, decided only by AIN EIRs.
- **Compact briefing** (3 lines: last time, open action, question being pressed), **learning log** (History →
  Learning log, or ⋯ → Save as my insight), **member experience** on the Members page.
- **Data survives refresh:** ventures are stored as JSON files in `.data/ventures` (tests use memory).
- 83 tests, pyflakes clean.

## v0.13 — 2026-10-14  AIN Foundry Roadmap
- **Roadmap position** (`Venture.module`: M1 Business Model Canvas → M2 The Perfect Pitch → M3 The Business Plan →
  alumni network), taken from the public AIN Foundry Roadmap. Sidebar shows done / current / upcoming modules and
  the current module's checklist; the coaching lens now follows the module (M1 Explore, M2 Validate, M3 Prepare).
- **Claimed vs Evidence.** Each checklist item is Not started / Claimed / Evidence; Evidence needs a description.
  The EIR brings up claimed-but-unproven items right after open disagreements (`memory.open_threads`), and the
  AI prompt receives the checklist with the rule that it never announces a module change.
- **Capstone gate.** When every item has evidence a member submits the capstone (checklist locked). Only AIN staff
  approve (next module) or return it with required feedback (`access.decide_capstone`). Teams can step back a
  module with a logged reason. New **Roadmap** page; staff directory shows module and pending capstones.
- **Human EIR sessions.** Workspace card with the next EIR Foundry session date and *Prepare brief*; the Mentor
  Brief gains roadmap checklist, session date and suggested EIR expertise area (routing by expertise, never by
  impersonating a named EIR). *Suggested from AIN* lists Foundry Fridays, competitions and programs for the module.
- Data in `knowledge/roadmap.json` (checklist criteria are drafts until AIN confirms capstone rubrics) and
  `knowledge/ain_resources.json`. Seeds: Campus Loop in M2 (M1 approved), LumaSense in M1. 81 tests, pyflakes clean.

## v0.12 — 2026-10-13  EIR memory in the workspace, optional interview, cleanup
- **EIR briefing** at the top of the workspace (open by default before the first message): last session,
  follow-ups and open disagreements, plus a reminder while the project profile is still a draft.
- **@EIR replies remember the project.** When a question doesn't match a prepared reply, the scripted EIR first
  names the open disagreements and open actions (`memory.open_threads`); the AI prompt has the same rule.
- **Project profile: interview or edit.** Tab 1 is the optional EIR interview (describe → one question at a time,
  skip allowed, skeptical notes). Tab 2 edits the details directly. The profile is shown as **Draft** until a
  member presses *Confirm profile for the team* (`actions.confirm_profile`); creating or editing never confirms it.
- Message actions moved into a small `⋯` menu; chat area taller; header no longer clips *Back to workspace*.
- Cleanup: canvas and action edits go through `actions.edit_canvas_block` / `actions.update_step` (validated,
  logged); one date source `eir/clock.py`; `ui/state.py` split into the `ui/state/` package (core, notebook,
  review); removed dead pages (`coach`, `home`, `canvas`) and unused functions/imports. 70 tests, pyflakes clean.

## v0.11 — 2026-10-13  Team conversation + notebook workspace
- Main member workspace now places the team conversation on the left and Notebook / Canvas / Actions on the right.
- Ordinary team messages leave the EIR quiet; explicitly mention `@EIR` to request coaching. Discussion review
  remains an explicit action, with individually attributed approval of proposed memory changes.
- Notebook supports direct editing, saved revisions and copying chat content with attribution. Actions track
  owners, dates and results. Calendar display and external calendar integration are deferred.
- New projects open their workspace immediately. Project profile and History are secondary navigation;
  Members, Mentor brief and review are contextual flows. No mandatory Explore / Validate / Prepare switch.
- Project joining uses a demo invite flow. The account selector and repository remain local to one browser
  session; separate browsers do not yet synchronize or authenticate members.
- Updated documentation and UI regression coverage for the member workflow. Live AI, persistent storage and
  real multiuser behavior remain unverified or pending; see README for prototype boundaries.

## v0.10 — 2026-10-12  Venture intake → profile (design doc F01)
- New **Profile** page: the team describes the venture in its own words, the EIR fills what it can and asks
  about the rest one question at a time (skip allowed), with skeptical notes ("very broad", "no numbers yet").
- Confirmed profile = the venture's "business card": shown on Home, sent to the AI as context, seeds the canvas
  as student statements. New ventures start here; coaching is locked until the profile exists.
- Interview questions live in `eir/intake.py` (`QUESTIONS`); coach interface gained `extract_profile` and
  `intake_note` (scripted rules now, LLM when a key is set). 25 tests.

## v0.9 — 2026-10-12  No posting as someone else
- Removed the free "typing as" switch: you always post and approve as the signed-in member.
- New "Team meeting at this screen" toggle: record who is present, pick who is speaking; messages show
  "typed by Alice in team meeting" (`Message.entered_by`). Enforced in `actions.post_message`.
- Session review: approver is always the signed-in member.
- Sidebar menu dots hidden on older Streamlit versions too. 22 tests.

## v0.8 — 2026-10-12  Sign-in and confidentiality
- Sign-in screen with roles (demo accounts; production: university sign-in).
- Founders see and open only their own venture; other teams' ventures are never listed.
- AIN staff get a venture directory + only the Mentor Briefs teams chose to share; no workspace access.
- "Share with AIN" is an explicit, logged consent step; shared briefs are stored on the venture.
- IP-sensitive flag (LumaSense): composer notice, LLM instruction, brief disclaimer.
- All rules in `eir/access.py`, applied when building `PageContext`. 20 tests (7 new on access rules).

## v0.7 — 2026-10-12  Clean architecture
- One codebase instead of two: the clickable prototype and the AI version now share the same data model and screens.
- `eir/` domain package (no Streamlit): typed dataclasses + enums, JSON serde, repository interface, memory, proposals, review, brief, actions.
- **Coach interface**: `ScriptedCoach` (demo, no API) and `AICoach` (LLM) are interchangeable; the app picks AI automatically when a key is configured.
- Demo ventures and scripted conversations moved to JSON (`eir/seed/`); prompts in `eir/prompts/`.
- `ui/`: one file per page + page registry, `PageContext`, all session state in `ui/state.py`, CSS in `ui/theme.css`.
- Docs: `docs/ARCHITECTURE.md` (rules + how-to), `docs/DECISIONS.md`. 13 tests (domain, AI coach with fake client, UI click-through).
- Retired: `core/`, old `ui/*_tab.py`, `app_connected.py`, top-level `prompts/` (superseded; backup in `_to_delete/`).

## v0.6 — 2026-10-12
- Removed the "who's using the workspace" screen and emoji avatars: open a venture and go straight in.
- Identity is a quiet "Signed in as (demo)" selector in the sidebar (stand-in for login).
- One composer block in EIR coach: "typing as" selector (for team meetings) + suggested messages as chips + a working free-text box.
- Initials avatars, author names instead of @handles/IDs, sidebar navigation as a plain list, coaching focus as a compact switch.

## v0.5 — 2026-10-12
Product decisions: one group = one venture · group memory only · no invites / no login · all EIR chat visible to the group.
- New entry: choose venture → choose who you are (**alone**) or **Team meeting** (one screen, switch speaker per message).
- EIR opening recap is generated from group memory: last session, follow-ups with owners (⏳/✅), and unresolved
  disagreements between members (e.g. @alice vs @bob on willingness to pay).
- Messages are attributed to members; sample messages change with the selected speaker.
- Canvas shows four statuses (Empty / Student statement / Hypothesis / Evidence-backed) with source and date; hypotheses list with owners.
- Session review lists each proposed change (before → after), records who approved, then updates memory — the next recap changes accordingly.
- New 📈 Timeline channel (history, session summaries, next-steps board); Mentor brief built from group memory.
- Second demo venture: LumaSense (solo PhD founder, research commercialization, FDA handoff).
- Removed account creation, group invites and invite codes.
- Logic in `core/workspace.py` + `core/demo_data.py` (planned group schema v3); UI in `ui/prototype.py`. 9 tests pass.

## v0.4 — 2026-10-12
- Reworked the prototype around a chat-style account and group model.
- Added display names, usernames, stable demo User IDs, Group IDs, ownership, member records, and permanent demo invite links.
- Creating a group now makes the creator its owner and opens the group workspace immediately.
- Joining by invite code adds the current account to the same group and opens it immediately.
- Moved project setup, coaching, Canvas, review, mentor brief, and members into group channels.
- Verified create-and-enter and join-existing-group flows with end-to-end UI tests.

## v0.3 — 2026-10-12
- Default entry now opens a clickable, session-only prototype with simulated identities and group creation/joining.
- Added overview, project setup, scripted coaching modes, canvas review, mentor-brief preview, and team identity switching.
- No API calls, database writes, real authentication, or outbound mentor messages in the default app.
- Preserved former connected entry as `app_connected.py`.
- Validated two end-to-end walkthrough tests.

## v0.2 — 2026-10-12
- Restructured into `core/` (logic) · `ui/` (tabs) · `prompts/` (all prompt text) for weekly iteration.
- Added founder profile at intake (client R9: adapt to undergrad → PhD founders).
- Added hypotheses & evidence tracker; session summary can propose new hypotheses / status updates (R1, R4).
- Schema versioning + automatic migration of saved ventures.
- Fixed: canvas form overwrote canvas updates accepted at end of session.
- Tests: core logic + full UI click-through in mock mode.

## v0.1 — 2026-10-12
- First Streamlit template: intake, coach chat (3 modes, challenge always on), canvas, session summary
  with batch review, recap, consent-based mentor brief, static pathways, mock mode.
