# Requirements trace: client asks → features → status (v0.19, 2026-11-13)

Sources: Roberto's kickoff video, the 2026-10-22 meeting and his *virtual_eir_briefing* slides, Liza meetings, and the
product decisions of 2026-11-05/06/07/12 (`../../design/multi_mentor_decisions_zh.md`). Statuses describe the
prototype; none of them means production-ready or validated with real EIRs and students.

| # | Client requirement | Feature | Status |
|---|---|---|---|
| R1 | A venture-building system, not a chatbot | Lead Virtual EIR + consultants; the Overview as the project's homepage, Action Plan, records with history and Undo | Implemented (prototype) |
| R2 | One EIR per venture that remembers it over time | One lead mentor per venture; records; day summaries ("last time"); 30-message window | Implemented; long-term behaviour unvalidated |
| R3 | Diagnose before advising | Question chain; Optimize diagnoses six lenses before an experiment | Implemented; evaluated on 10 cases |
| R4 | Constructive skepticism; tell the truth, don't judge the idea | Prompts with EIR habits from Roberto's examples; evidence ladder | Implemented; AI-judge scores in `eval/results/` |
| R5 | Coach and teach founders | Why + how to test; experiments with criteria agreed in advance | Implemented |
| R6 | Marketing, financing, IP guidance | Consultants (pricing & business model, strategy & competition, funding readiness); must-hand-off topics | Implemented; no IP consultant (IP goes to humans) |
| R7 | Readiness for investors / NextCorps | Funding-readiness consultant; Foundry step judgment; graduation by all EIRs | Implemented |
| R8 | Awareness of developments in each field | Live search | Deferred |
| R9 | Adapt to founders, from undergraduates to faculty | Member backgrounds and experience in the context; respect rules for senior founders | Partly; needs evaluation with real users |
| R10 | Real-venture nuance from EIRs | Roberto's 9 examples as habits in the prompt and as evaluation cases | Implemented; EIR review of results pending |
| R11 | Confidentiality, including research IP | Membership access; staff see no chats, consultations, practice sessions or files; consultants see brief + attached summaries; practice characters see only what their kind allows; IP rule | Application-level only; real auth, storage isolation pending |
| R12 | Cross-venture lessons | — | Deferred |
| R13 | Human judgment where decisions are hard to undo | request_human; consent-based brief; EIR calibration of first judgments; graduation | Implemented |
| R14 | Students who stay only for one part of the journey | Two lead mentors (Launch / Optimize), recommended at creation, switchable | Implemented |
| R15 | Work with the team's own documents | Project files on the Overview: upload, preview, download, versions; the team chooses when the Virtual EIR reads and discusses a file; summaries, claims, revision tasks | Implemented (images and links not read) |
| R16 | Prepare students for competitions and customer interviews (stumped by industry veterans; the Foundry requires pitching; the pitch-deck step asks for a mock Q&A) | Practice page: target customer, competition judge, challenger; feedback from a practice coach; the team decides whether its mentor sees it; never evidence | Implemented (prototype); 3 evaluation cases; voice input not built |
| R17 | A team sees its project at a glance: what it is, where it is stuck, what to do next, its files (product owner, 2026-11-12; redesigned from two outside answers) | Overview homepage: the project in the team's words; a focus card (why now, evidence for and against with its level and sources, what is missing, one main button); progress in words; a snapshot next to the graded evidence (the Virtual EIR's canvas text as a draft to adopt); recent activity; the latest files; the rest in dialogs; a start page for a new project | Implemented (prototype); not tried with students yet |

## Acceptance checks (demo, no key needed)

- Create a project: two questions, a recommended lead mentor, the team chooses.
- Every message gets a reply; a record update can be undone from the reply.
- Bring in a consultant from the rail, talk in the drawer, collapse and reopen it, preview and send the summary;
  the lead mentor reports it and adds the suggested tasks.
- Start an experiment (criteria lock), record a result, ask the mentor to judge; the rung comes from the method.
- Check a step (Not yet / Ready), and as AIN staff agree with or reopen the judgment.
- On the Overview, the focus card shows why the focus matters now, the evidence for and against (an evidence level
  opens what it means and where it comes from), what is missing, and one main button that follows the state.
- Edit the project and a snapshot line in their dialogs; the evidence levels stay as they were. The Virtual EIR's
  canvas text can be adopted as the team's statement.
- Add a document on the Overview: it is saved only ("not discussed yet", with a preview). Read and discuss it: the
  chat opens with the Virtual EIR's reply, and the file shows as discussed. A new version keeps the history, and every
  version can be downloaded. Attaching a document to a chat message still works.
- A new project's Overview is a start page ("Start the conversation"); after the first message the full page appears.
- The assumptions are at the top of the Action Plan; the project plan and stepping back are in the ⋯ menu.
- Practise a pitch with the judge from "Recommended now"; get the feedback (with the claims the records don't
  support); send it to the mentor, who adds a to-do and records where the team pitched; practise an interview with
  a made-up customer and ask for a hint.
- As AIN staff, see no chats, consultations, practice sessions or files.
