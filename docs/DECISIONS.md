# Product decisions

Oldest first; each section is dated. **v0.16 (Nov 5–6) supersedes the member-workspace sections below:** the lead
mentor now answers every message (no @EIR), the notebook, meeting mode, discussion review, profile interview and
history pages were removed, and the records are kept by the mentor with Undo. The current product design is
`../../design/multi_mentor_decisions_zh.md`; the v0.16 and v0.17 decisions are the last sections of this file
(consultant drawer, project files, evaluation, practice). The older sections stay as the record of why things were
built.

## Member workspace (decided with the project owner, October 13, 2026; superseded by v0.16)

- **One group = one venture.** Members share the project's conversation, notebook, canvas, actions and history.
- **Conversation on the left, work area on the right.** The work area offers Notebook, Canvas and Actions.
  Notebook is the default; the conversation remains available when changing the right-side view.
- **EIR joins when asked.** Ordinary team messages do not trigger a coach reply. Members mention `@EIR` to
  request help. Discussion review can be written manually; its explicit EIR-draft button requests assistance.
- **No mandatory coaching-mode selector.** Explore, Validate and Prepare may inform coaching behavior,
  but members express their purpose in the message. Stages are contextual labels, not mandatory steps.
- **Start with a small amount of information.** Creating a project opens its workspace immediately.
  The Project profile starts as a **Draft**: the team can let the EIR interview them or edit the fields directly,
  and it becomes **Confirmed** only when a member explicitly confirms it. The EIR briefing reminds the team
  while it is still a draft, but nothing is locked.
- **The EIR brings memory into the room.** The workspace opens with the EIR's briefing (last session,
  follow-ups, open disagreements). When asked a question, the EIR raises related open items first.
- **Lightweight actions first.** Track action text, owner, date and result beside the conversation.
  Calendar views, reminders and calendar-provider integrations are deferred.
- **Secondary navigation stays small.** Project profile and History are secondary pages. Members and
  Mentor brief are contextual workspace actions, and discussion review is an explicit flow.

## Identity and collaboration

- Every member has an account identity separate from their display name and their membership in a venture.
- Creating a project adds the creator. Other founders join through the project's demo invite flow;
  typing another person's name is not evidence that they accepted an invitation.
- A member normally posts as themselves. In a meeting at one screen, the signed-in member may record a
  present teammate's words. The message records both the speaker and the person who entered it.
- The current demo uses account selection and an in-memory repository per browser session. Switching
  accounts within that session demonstrates collaboration. Different browser sessions are independent.
  Real authentication, server-side membership enforcement and concurrent editing remain future work.

## Records and decisions

Where each kind of information lives, and how trusted it is:

| Place | What it holds | Trust level |
|---|---|---|
| Conversation | what members and the EIR said | a record of contributions, nothing verified |
| Notebook | the team's working drafts | editable, never treated as evidence |
| Review | turns a discussion into proposed memory changes | the only bridge from talk to memory |
| Canvas / hypotheses | the current model of the business | team-confirmed, each entry labelled statement / hypothesis / evidence |
| Actions | who does what by when, and the result | completion is not validation |
| Project profile | the team's own description (Draft / Confirmed) | the team's statements, not evidence |
| History | reviewed sessions, revisions, events | append-only record of what changed and why |

- **Conversation is a record of contributions**, not a collection of verified facts.
- **Notebook is editable working material.** Members can write directly or copy useful messages into it;
  saved revisions and source attribution help explain where a note came from. Unsaved drafts belong to their
  editor. If another demo member saves a change first, the original editor must compare the latest version
  before saving their draft over it.
- **Canvas is the current model of the business.** Entries retain their statement / hypothesis / evidence
  status and source. Filling a canvas is not a viability score.
- **EIR memory changes are proposals.** A member explicitly accepts or rejects suggested canvas, hypothesis
  and action changes. Record the confirmer's identity rather than labelling the outcome as team consensus.
- **Completion is not validation.** Record action results separately from task status. A completed interview
  or experiment does not by itself establish that the hypothesis was supported.
- **History preserves context.** Reviewed discussions, notebook revisions and decision events let members
  revisit what changed and why.

## Confidentiality and human help

- Founder workspace navigation is filtered by membership. AIN staff retain a directory containing project
  metadata and explicitly shared Mentor Briefs; they cannot open the member workspace through the app.
- Sharing a Mentor Brief is an explicit, logged action by a member. This version does not implement a
  whole-team consent policy or temporary mentor workspace access.
- An IP-sensitive flag displays guidance and supplies a coach instruction. It does not implement automatic
  technical-detail detection or redaction, and must not be described as an absolute privacy guarantee.
- Cross-venture lessons, de-identification and their approval workflow are future work.
- **Invite codes are demo-only.** A code is derived from the project id: it never expires, cannot be revoked,
  and anyone holding it can join without owner approval. That is acceptable for a classroom demo in one
  browser session. A production version needs random, expiring, revocable codes (or university-account invites)
  and an owner approval step before a new member can see the project.

## AIN Foundry Roadmap (v0.13)

- The venture's stage follows AIN's own Foundry Roadmap (M1 canvas, M2 pitch, M3 business plan) instead of a
  generic idea/validation/MVP scale, so the EIR speaks AIN's language. The canvas is M1's deliverable, not the
  whole framework.
- Module progress is gated: AI pre-check (every item has evidence) → team submits → a human AIN EIR approves.
  The AI only suggests. This mirrors the EIR Foundry Sessions already in every module.
- "Claimed" vs "Evidence" makes the client's skepticism requirement concrete: the EIR's job is to turn claims
  into evidence.
- Human handoff names an expertise area, not a person. The AI never speaks as a real AIN EIR.

## Design v0.2 (v0.14, after the 2026-10-22 client meeting)

- The Virtual EIR serves ventures without a dedicated EIR. Its core job is to question every claim until it has
  evidence ("diagnostic before advisory; evidence-graded, not encouraging").
- It judges whether a step is complete (client: "I would be okay with the virtual EIR judging if a step is
  complete"); an AIN EIR checks the first three judgments per venture. Decisions that are hard to undo
  (team and equity, term sheets, graduation) stay with humans; graduation needs all EIRs.
- Required rungs per question and the interview count are our initial standard and will be calibrated from the
  EIRs' checks. No maintained knowledge base: only the Foundry / 24-step process content.
- Delivery form (web app vs Blackboard embedding) is open; Liza is investigating.

## Open questions for the instructor / client

1. Who may confirm each type of project-memory change: any member, an assigned owner, or the whole team?
2. Who may approve sharing a Mentor Brief, and what content should a mentor normally receive?
3. How should departures, membership administration and conflicting notebook edits work?
4. Which coaching examples best show useful diagnosis, constructive challenge and a concrete next step?
5. Can AIN share the Foundry capstone rubrics and the Blackboard step list? The checklist criteria are drafts.
6. What is the "Customer Discovery AI Validation Process" in Module 1, and should the Virtual EIR connect to it?
7. Who approves a capstone today (which EIR / staff role), and does it happen in an EIR Foundry Session?
8. What identity and database services can the instructor support for a later multiuser version?

## Consultant drawer (v0.16, decided 2026-11-06)

The multi-mentor design (`../design/multi_mentor_decisions_zh.md`) opens each consultant in a drawer that expands
leftward over most of the Mentor page, on top of the lead mentor's chat. The consultant rail stays visible on the right.

- **Spike:** `spikes/drawer_spike.py` (deleted after phase 5; it is in the stage 1–4 backups), run in Streamlit 1.66.1. It compared a CSS overlay (fixed-position keyed
  containers, `.st-key-*`) with `st.dialog(position="right")`, checked with AppTest and with screenshots in Edge at
  1366×768 and 1920×1080.
- **What both variants passed:**
  - each chat input posts to its own transcript;
  - collapsing keeps the consultation open;
  - reopening keeps the transcript;
  - AppTest can drive both inputs.
- **Decision: the CSS overlay.** It covers most of the page on top of the mentor chat and keeps the rail visible, as
  designed. The dialog covers the rail and adds its own title and close button.
- **Mentor input while the drawer is open:** it is not rendered. A caption tells the student to collapse the panel, so
  a message cannot go to the wrong mentor.
- **To fix in the real page:**
  - Avatar colours need `!important`, because Streamlit's focus styles override them.
  - On wide screens the drawer should leave a fixed strip of the mentor chat visible; the 1100px cap covered only 57%
    at 1920px.
  - The default Streamlit header overlaps the page title.
- **Fallback:** if a Streamlit upgrade breaks the CSS, use the dialog variant from the spike.
- **Built (phase 5):** `ui/consult_drawer.py`, styles in `ui/theme.css`.
  - The drawer spans from 26% of the screen width to the rail (`left: 26vw; right: 76px; width: auto !important`),
    so a strip of the mentor chat stays visible at any width (70% coverage at 1920px). Without `width: auto`,
    Streamlit's own width made the drawer as wide as the screen and cut its content off.
  - The rail and drawer start below the 3.75rem header. Consultant colours use `!important`.
  - "End and send back" sits in the drawer header, next to "Collapse", so it never scrolls away. The chat is an
    autoscrolling container. In the summary preview the conversation folds away, so the summary comes first.
  - Screenshots: `scripts/shoot_ui.py <dir> <width> <height> --drawer`.

## Project files (v0.16, decided 2026-11-06)

Design section 6: teams share documents in the Mentor chat, listed under Materials on the Overview. (Since v0.18 the
Overview's Project files is the main place to upload and manage them; see "The Overview as the project's homepage".)

- **Storage:** the venture record keeps only names, versions, summaries and claims (`ProjectFile`, `FileVersion`).
  The bytes and the extracted text live in a file store (`eir/filestore.py`): plain files under
  `~/.virtual_eir/files/<venture>/<file>/v<n>.<ext>` (+ `.txt`), memory in tests. Plain files are a prototype limit;
  production needs the university's storage with access control.
- **Reading on this computer:** PDF with pypdfium2; .docx and .pptx with the standard library (zip + XML); .xlsx with
  openpyxl; CSV and text decoded. No service sees a file to extract it. Images and links are listed, not read.
- **Documents only:** code and archives are refused; 10 MB per file.
- **Versions:** an upload whose name matches an earlier file of the same kind (ignoring "v2", "final", "(1)"…) is
  its next version; an identical upload is refused.
- **What a document is:** the team's claims. The summary lists them with the evidence the document gives. The mentor
  records the important ones as assumptions and grades evidence only where the document reports who, how many and what
  they did.
- **Mentor's access:** it reads summaries in its context and opens text in parts with the read-only `read_file`.
  Revisions are tasks linked to the file (`NextStep.file_id`); with a new version the mentor sees both summaries and
  the open revisions, and ticks off what was fixed.
- **Consultants:** see only the summaries of files the lead mentor attaches (`open_consultation` `file_ids`). AIN staff
  see no files.
- **Tool loop (found with the real model):** replies are the text of every round, de-duplicated, without
  "Let me record…" narration (`eir/llm.py`).
- Checks: `tests/test_files.py`; real model `scripts/smoke_files.py`; a browser upload `scripts/shoot_ui.py … --files`.

## Evaluation (v0.16, 2026-11-06)

- **Cases:** Roberto's nine coaching examples from the 2026-10-22 meeting, plus a two-session research spin-out, as ten
  fictional ventures in `eval/cases/`. Each holds the team's messages, "what a good EIR does here" in Roberto's terms,
  and expectations that need no judgment.
- **Two kinds of scoring:** checks without judgment (length, at most two questions, no internal ids, no narration, no
  "step complete" claim, the right human handoff, no evidence above the case's rung, a fitting consultant, no switch
  away from Optimize), and an AI judge scoring six dimensions 1–5. The judge is the same model as the mentor, so its
  scores are a quick signal for prompt changes, not a verdict; EIRs should review the saved conversations.
- **Prompt changes come with a run.** Each run is kept in `eval/results/<date>_<time>/`; notes in `eval/results/NOTES.md`.
- **The habits in the prompt come from the client.** Roberto's examples are written into `lead_common.md` as general
  EIR habits (novelty, user / buyer / payer, day-one deployment, investors' returns, status is not evidence, hard-to-undo
  decisions), not as answers to the cases.

## Practice (v0.17, decided with the product owner 2026-11-07)

Design section 10 in `../../design/multi_mentor_decisions_zh.md`. Why: Roberto said students get stumped when an
industry veteran questions them at a competition; the Foundry requires pitching at competitions; M1 asks for many
customer interviews; design v0.2 put a mock Q&A in the pitch-deck criteria.

- **An independent conversation on its own page** (Practice, the fourth page), not a mode of the mentor chat: the
  student rehearses without the mentor watching, and starts again as often as they like.
- **Three characters in v1:**
  - a target customer;
  - a competition judge;
  - a challenger: the product owner's addition, for the tricky questions that find a project's weak spots.

  An investor and an enterprise buyer can be added later as entries in `knowledge/practice.json`; until then, the
  challenger asks investor-style questions.
- **What a character knows depends on its kind** (`access.character_view`, rule 8):
  - The target customer knows only who they are, never the idea, so the interview can't be steered by the
    character's knowledge. A new person is made up for every session, from the segment only. If the persona prompt
    saw the team's problem statement, it would build their hypothesis into the person.
  - The judge reads the Overview and the material the team chooses, like a judge who read the submission.
  - The challenger reads every record and the files' summaries.
  - IP-sensitive ventures: summaries only.
- **Practice is never evidence**, enforced in code (`ToolBox.source`). Feedback the team sent may become a task, a
  new assumption, the focus, or the answer to "where have you pitched it" (rung 1, judge sessions only). Anything
  else that cites practice is refused, because nothing a made-up character says is a customer's answer.
- **The team decides whether the mentor sees anything,** and then only the feedback with one line of its own, never the
  conversation (`access.lead_view_of_practice` raises until a member sends it). The mentor may also suggest a session; a
  button under its reply opens the setup, pre-filled. AIN staff and consultants never see practice.
- **A separate practice coach writes the feedback,** not the character: the character stays in role, and the feedback
  can check what the student said against the records. An app check (numbers the records don't contain, payments that
  aren't recorded) is merged into the coach's list. The team's own plans ("we'd buy 300 crates") are not flagged.
- **Closing on time doesn't depend on the model counting:** past the planned number of exchanges, the character's
  prompt says to close now (`AICoach._pace`).
- **Without AI** the characters use prepared lines (Campus Loop: a pitch to the judge, an interview with "Maya", a
  challenger session) or simple rules, and the feedback comes from keyword checks, marked as simplified.
- **Not in v1:** voice (pitches are typed or pasted and timed at 140 words a minute; local speech-to-text with Whisper,
  or a speech model on Databricks, is the open choice), meeting the same made-up customer again, practice sessions as
  Action Plan items (only the tasks the mentor adds from feedback appear there).
- **Checks:** `tests/test_practice.py`, `tests/test_practice_mentor.py`, the Practice tests in `tests/test_ui.py`;
  real model `scripts/smoke_practice.py`; evaluation `eval/run_practice_eval.py`; screenshots
  `scripts/shoot_ui.py … --practice`.

## The Overview as the project's homepage (v0.18 2026-11-12, redesigned in v0.19 the same week)

**v0.18** made the Overview the project's homepage, with four blocks of similar weight (intro, where it stands, core
cards, project files) and seven folded details. It still felt like too much for a first-time student. The product
owner sent one question to three people: the project, every feature built, the page, and eight questions on function
and style. The three were a classmate, ChatGPT (GPT-6), and a third person who said the first two covered their
view. Both answers agreed: the homepage is where you start, not where everything is kept. It answers three questions:
what are we doing, where are we stuck, what do we do next.

**Decided with the product owner (2026-11-12), from what both answers agreed on:**
- **The focus card is the page's main block.** It shows:
  - the current focus;
  - why it matters now;
  - the evidence for it and against it, each with its own level and where it comes from;
  - what is still missing;
  - the next step.

  It has one main button, which follows the state:
  - a draft test: "Review and start the test";
  - a running test: "Record the result";
  - a task: "Open the Action Plan";
  - nothing planned: "Ask your Virtual EIR what to test".

  Every line except the focus is a rule over the records (`overview.focus_card`). The focus itself is the Virtual
  EIR's suggestion, or a member's ("Set by Bob").
- **A new project gets a start page, with the conversation first.** "Start the conversation" is the main button;
  uploading material and inviting the team come second. `overview.is_new` means no team message and no records yet.
  The page fills in as the team talks.
- **All assumptions are in the Action Plan,** first on the page: what you believe, then how you test it, then what you
  do. The homepage shows only the current one, in the focus card.
- **Evidence shows its name first, then the level:** "Customer statements · Level 3" (`Rung.plain`).
  - Clicking it shows what the level means, what stronger evidence would be, and the records behind it: who, when,
    for or against.
  - The ladder is no longer printed at the bottom of the page.
  - Models, prompts and the evaluation still read `Rung.label`, so nothing they see has changed.

**Decided by me where the two answers differed:**
- **Files stay on the Overview, as a short list:** the latest three with their status, "Add a file" and "All files".
  They are managed in dialogs.
  - One answer wanted a Files page; the other only wanted files to weigh less.
  - A fifth page is one more thing for a new student to learn.
  - The product owner's first requirement was uploading on the Overview.
- **The canvas, all key questions and the full history open in dialogs from the block they belong to:** the snapshot,
  the progress and the recent activity. They do not get their own pages or one folded "Details" area. This avoids a
  junk drawer (first answer), groups things by meaning (second answer), and adds no navigation.
- **Recent activity shows three items, including the timeline:** milestones, decisions and shared files.
  - A timeline event has only a date, so it comes after the record changes of the same day.
  - Seeing what the Virtual EIR changed builds trust in its automatic updates.
- **Progress is one row:** the four deliverables (✓, now, later) and the key question to answer now, in its own words.
  - The step number ("step 23") appears only in the key questions dialog: "step 3" read as "we are at step 3, so why
    no progress?".
  - The progress line never names a different question from the focus card.
- **"Drafted by your Virtual EIR" appears only in the snapshot.** When the team has not written a line, the canvas text
  the Virtual EIR recorded is shown as a draft, with "Use this as our statement".
  - A review queue for every change (first answer) waits for later.
  - It would undo the decision frozen on 2026-11-06: the Virtual EIR updates the records directly, and every update
    is visible and can be undone.
- **Source tags, once per block:** ✎ Team statement, ✓ From records, ✦ Virtual EIR suggestion (purple). The focus card
  ends with "A suggestion: your team decides."

**Moved or removed:**
- The "where it stands" sentences: the progress row replaces them.
- The stage and type chips: they are in Project settings.
- The explanatory captions and the ladder line.
- The preliminary plan and "Step back": they moved into the ⋯ menu.
- "Who it serves" and "Target customer" no longer appear twice: the snapshot's customer line is the one place.

**Kept from v0.18:**
- Files are saved first; the Virtual EIR reads one only when the team asks.
  - "Read and discuss it", with an optional line on what to look at, opens the chat, where the Virtual EIR replies.
  - If the reply fails, the message stays, ready for "Ask the Virtual EIR again".
  - The status (not discussed yet, read, discussed) is worked out from the chat; nothing extra is stored.
  - Links are listed with the team's description and are never opened or discussed.
- The team's own description is in the Virtual EIR's context, as claims (`memory._team_description`).
- A project opens on the chat. The navigation order stays: Virtual EIR · Overview · Action Plan · Practice.
- The top navigation fix: after a page change made by code, the old tab was sometimes still selected. `state.go_to`
  now gives the control a new key.

**Dialogs:** a click inside a dialog reruns only the dialog. Buttons there that change the page or close the dialog
do their work in the run and then call `st.rerun()`.

**Later:**
- a review queue;
- stall alerts;
- a decision log page;
- a weekly team review;
- homepages per role;
- plain-language change summaries (they still say "H2");
- a reason from the Virtual EIR when it sets the focus (a prompt change, then an evaluation run).

**Checks:**
- `tests/test_overview.py`: the focus card and its main button, progress, the snapshot, the start page, the activity
  with the timeline, the plain evidence names.
- `tests/test_files.py`: saving without the Virtual EIR, discussing, a failed reply.
- `tests/test_ui.py`: the Overview, its dialogs, the Action Plan's assumptions and the menu.
- Real model: `scripts/smoke_files.py` (v0.18).
- Screenshots: `scripts/shoot_ui.py … --overview` (Campus Loop, every dialog, a new project before and after its
  first message).
