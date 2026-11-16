# Evaluation notes

Model: Claude Sonnet 4.6 (Databricks, OpenAI-compatible endpoint). Judge: the same model. 10 fictional cases
(`../cases/`). Every run folder holds the full conversations; read them before trusting a score.

## 2026-11-06: four runs while tuning the lead mentor's prompt

| Run | What changed before it | Checks passed | challenge | evidence | focus | handoff | respect | next step | Mean |
|---|---|---|---|---|---|---|---|---|---|
| `2026-11-06_baseline` | — (the v0.16 prompt) | 117/137 | 4.1 | 4.3 | 3.0 | 4.8 | 4.6 | 3.8 | 4.10 |
| `2026-11-06_run2` | EIR habits from Roberto's examples; ≤ 2 questions, options as statements, no praise openers | 130/137 | 4.4 | 4.5 | 2.9 | 4.9 | 4.8 | 3.5 | 4.17 |
| `2026-11-06_run3` | a fixed reply shape: claim → why → one concrete action → one question, 80–120 words | 132/137 | 4.3 | 4.4 | 3.2 | 4.9 | 4.7 | 3.9 | 4.23 |
| `2026-11-06_run4` | don't dodge hard-to-undo questions; raising money is not a human handoff (current prompt) | 132/137 | 4.5 | 4.4 | 3.0 | 4.9 | 4.8 | 4.3 | 4.32 |

Run 4's five failed checks are all "a third question mark in one reply". Differences of ±0.2 between runs are within
the run-to-run noise of the model and the judge.

### What the baseline showed
- The rules held in every case: the two cases that need a human (equity and CEO; FDA) were handed off, nothing was
  recorded above what the team reported, consultants fitted, the Optimize team was not sent back to Launch.
- The weakness was focus: replies asked three to seven questions, most of them rhetorical lists of options, and
  three replies ran over 180 words. The judge's most common advice: one sharp question and one concrete action.
- Roberto's distinctive moves were missing: opening adjacent segments and asking who pays (music teachers),
  asking how the product gets installed (rowing headset).

### Fixes and their effect
- Writing Roberto's examples into the prompt as general EIR habits raised challenge and evidence; the reply shape
  raised focus and next step. "Let me record…" narration is now removed in code (`eir/llm.py`, `strip_narration`).
- Run 3 regressions, fixed for run 4: the mentor routed the equity question to a human without asking the hard
  question first (the judge: "challenge the claims before routing them"; case 07 went from 3.33 to 3.83); it flagged
  "raising money" for a human although that is the funding consultant's work (case 06 now passes every check).
- Case 04's evidence ceiling was raised from 1 to 2: that a known competitor exists is desk research, as the judge
  agreed.

### Still open (for EIR review)
- Focus stays the lowest score (3.0): replies often still carry a second question or a short lecture; the judge
  wants one question per reply, the prompt allows two. Worth asking an EIR which is right.
- Case 07 (equity) is the weakest case: the mentor names the tension but moves on to customers quickly.
- The judge repeatedly asks for the user / buyer / payer split one turn earlier (cases 02, 03).
- The mentor sometimes cites the readable demo ids ("X-fee", "S1") although the prompt forbids ids.
- The consultant rarely proposes to end by itself within three exchanges (the student can always end it).
- The judge is the same model as the mentor and tends to agree with itself; an EIR should overrule scores.

## 2026-11-07: the practice characters (v0.17), `../practice_cases/`

| Run | What changed before it | Checks passed | in role | knowledge | pressure | feedback accuracy | feedback useful |
|---|---|---|---|---|---|---|---|
| `2026-11-07_2237_practice` | — (the v0.17 prompts) | 73/73 | 4.7 | 5.0 | 4.0 | 4.3 | 5.0 |
| `2026-11-07_2240_practice` | the judge's "pressure" defined per role; the team's own plans not flagged as unsupported | 73/73 | 4.7 | 5.0 | 4.3 | 4.7 | 4.7 |

Means per case in the second run: customer 4.6, challenger 5.0, judge 4.4.

### What the runs showed
- **The customer** (a new made-up commuter each run) knew nothing about the idea and stayed in role:
  - concrete about the last time (a 40-minute commute, a full lot, five minutes late for a midterm);
  - only "maybe, it depends" to "would you use it" and "would you pay $5";
  - promised nothing.
- **The challenger** named both gaps at once ("your records show no payments"; 4 interviews, not 30) and acknowledged
  the honest corrections.
- **The judge:**
  - said the pitch ran over;
  - asked one question at a time and pressed twice on unit economics after evasive answers;
  - closed after the sixth message: past the planned exchanges its prompt now says to close;
  - never coached or scored.
- **The feedback** quoted the student, flagged the leading and hypothetical questions and the mid-interview pitch,
  wrote stronger answers from the records only, and listed what to check with real customers.

### Fixed during the runs
- The first run's judge asked the made-up customer to "press the vague answer himself". That is a flaw in the judge's
  definition of pressure, not in the customer: a customer must not help the interviewer. Pressure is now defined per
  role.
- The app's records check flagged "We'd use the prize for 300 crates" as unsupported. The team's own plan is not a
  claim about what happened, so first-person plans are no longer checked for numbers.

### Still open
- A fix in the third case's feedback still used an "[X]" placeholder in a model answer (fill in your number).
- The made-up customer's name repeats across separate ventures (Darnell twice); names are only varied within a
  venture.
- No voice: delivery is judged from the words of a typed pitch.
