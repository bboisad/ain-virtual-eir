# AIN Center Virtual EIR (prototype v0.19)

A Virtual Entrepreneur in Residence for AIN Center ventures that have no dedicated EIR (MSAIB capstone, Fall 2026).

- **One lead Virtual EIR per venture,** chosen by the team: **Launch** (from an idea to a first launch, on the AIN
  Foundry roadmap) or **Optimize** (for something that already runs: six lenses, the bottleneck, one experiment).
- **The Overview is the project's homepage.** It answers what we are doing, where we are stuck and what we do next:
  - a **focus card** shows why now, the evidence for and against, what is missing, and one next step;
  - below it are the progress, a three-line snapshot in the team's words, recent activity and the latest **project
    files**.

  Everything else opens in a dialog from where it belongs. A new project gets a start page that begins with the
  conversation. The team chooses when the Virtual EIR reads and discusses a file.
- It **questions every claim** until it has evidence, grades evidence on a 6-rung ladder (1 assertion · 2 desk research
  · 3 customers said · 4 did · 5 paid · 6 retained), and keeps the venture's records up to date: every update is
  listed under its reply and can be undone.
- It **brings in consultants** (pricing & business model, strategy & competition, funding readiness). The student talks
  to them directly; the lead mentor receives only their summary.
- Teams **practise with AI characters** before the real thing: a target customer (who knows nothing about the idea), a
  competition judge (a 3-minute pitch and questions) and a challenger (tough questions on every record). A practice
  coach writes the feedback; the team decides whether its mentor sees it. Practice is never evidence.
- **The rules judge whether a Foundry step is complete;** an AIN EIR checks the first three judgments, and only the
  EIRs decide graduation to NextCorps. Decisions that are hard to undo (team, equity, valuation, IP, FDA) go to humans.

Design: `../design/multi_mentor_decisions_zh.md` (Chinese) · decisions: `docs/DECISIONS.md` · code layout:
`docs/ARCHITECTURE.md` · history: `CHANGELOG.md` · evaluation: `eval/README.md`.

## Run

Python 3.10+ (tested with 3.13 and 3.14), in a virtual environment of your choice:
```bash
python -m venv .venv          # or any folder outside a synced drive
.venv/bin/pip install -r requirements.txt            # Windows: .venv\Scripts\pip.exe install -r requirements.txt
.venv/bin/python -m streamlit run app.py             # http://localhost:8501
.venv/bin/python -m pytest -q                        # all tests must pass before a demo
```
On Windows, use `.venv\Scripts\python.exe` in place of `.venv/bin/python`.

**Model.** One configured model serves the lead Virtual EIR, the consultants, the practice characters, the feedback
and the evaluation judge. It is set per computer in `~/.streamlit/secrets.toml`, outside the project: copy
`.streamlit/secrets.toml.example` there, fill it in, and check it with `python scripts/smoke_llm.py`. Two
configurations have been tested, both through the Chat Completions interface with native function calling:
- **Claude Sonnet 4.6** through an OpenAI-compatible endpoint: the v0.16 and v0.17 evaluations, and the v0.18 file check.
- **OpenAI GPT-5.6 Luna** (`gpt-5.6-luna`) through the official API. For this model the client sends
  `reasoning_effort="none"` so function calling works, and bounds the reply with `max_completion_tokens`. Results and
  known model behavior: [OpenAI model test, Nov 8](docs/OPENAI_MODEL_TEST_2026-11-08.md).

Without a key, the scripted demo Virtual EIR and a keyword grader run (prepared lines for the demo ventures).
**Never commit or share a key.** Use real models with fictional demo data only until the university approves a key
for student data.

Data stays outside the project folder: ventures in `~/.virtual_eir/ventures/`, project files in `~/.virtual_eir/files/`
(`EIR_DATA_DIR`, `EIR_FILES_DIR`). Menu (⋯) → Prototype info → **Reset demo** restores the demo ventures.

## Demo accounts (no password)

| Account | Role | What they see |
|---|---|---|
| Alice Chen, Bob Lee, Carol Diaz | Founders, Campus Loop (M2, Launch Virtual EIR) | Their venture only |
| Priya Raman | Founder, LumaSense (M1, IP-sensitive research spin-out) | Their venture only |
| AIN staff (demo) | EIR / staff | Directory, judgments to check, graduation reviews, shared briefs. Never chats, consultations, practice sessions or files |

## Demo path (8 minutes, works without a key)

1. Sign in as **Alice**, open Campus Loop. It opens on the **Virtual EIR** chat; the **briefing** says the current
   focus, the next action and last time.
2. Virtual EIR: open **Prepared messages** and send "Everyone we talked to loved it…". It pushes back; open
   **Record updates** under its reply and **Undo** one.
3. Click **P** in the rail: the Virtual EIR writes a brief and the pricing consultant opens in the drawer. Send the
   prepared messages, **Collapse** (it stays open), reopen, **Review the summary**, add one line, **Send to my Virtual
   EIR**: it reports the key points and adds the suggested to-dos (undoable).
4. Action Plan: **Start the experiment** (criteria lock), record "2 of 10 movers prepaid $3", **Ask the Virtual EIR to
   judge**: Refuted, and the assumption now has rung 5 evidence (the method, whatever the result).
5. Overview, the project's homepage. The **focus card** shows the $3 question: why it matters now, the evidence for
   it (Alice's belief, Level 1) and against it (2 of 3 interviewees, Level 3), what is missing, and the next step.
   - Click an evidence level to see what it means and where it comes from.
   - **See all key questions** → **Check this step**: Not yet, with what is missing.
   - In the snapshot, open **Business model**: the team's words next to the canvas level, which editing never changes.
   - Assumptions are now at the top of the **Action Plan**.
6. Overview → **Add a file**: upload a document, e.g. a short survey as .md.
   - It is only saved, and its status is "not discussed yet". Open the file to see a preview.
   - Add what you want it to look at, then press **Read and discuss it**: the chat opens, and the Virtual EIR reads
     the file and replies.
   - Back on the Overview, the file shows as "discussed". Attaching a file to a chat message, with the + in the
     input, still works too.
   - Then show a new project: ⋯ → **My projects**, create "Lab Share" and choose **Start with Launch**. Its Overview
     is a start page: **Start the conversation**. After the first message, the full page appears.
7. Practice: **Recommended now → Start** (a pitch to the competition judge). Send the prepared pitch and answers from
   **Prepared messages**; the judge wraps up. **Get my feedback**: scores, three fixes and "Claims your records don't
   support" (the waitlist of 40). **Send to my Virtual EIR** with one line: it adds a to-do (undoable) and records where
   you practised your pitch. Then **Practise** with the target customer: ask a "would you" question and press **Stuck?
   Get a hint**.
8. Sign out, sign in as **AIN staff**: the directory and the judgments to check, nothing from the chats, practice or
   files.

## Prototype boundaries

- Sign-in is a demo selector, not authentication; membership and role checks are application-level only.
- JSON files and plain files on one computer, not a database: no multiuser sync, no encryption.
- Required evidence per key question and the step numbers are our initial standard, to be calibrated by AIN EIRs.
- The AI mentor is checked with `eval/run_eval.py` (10 cases from Roberto's examples) and the practice characters with
  `eval/run_practice_eval.py` (3 cases); the judge is the same model. Neither is checked by real EIRs or students yet.
- Practice pitches are typed or pasted (timed from their words); voice input is not built yet.
