# Evaluation

`cases/` holds 10 fictional coaching cases. Nine come from the examples Roberto Colangelo gave in the 2026-10-22
meeting (`../../client_materials/meeting_2026-10-22_roberto_notes.md`, section 3): sliced bread, the voice device
for music teachers, the user is not the buyer, 47,000 competitors, installing a device in a boat, investors want 10×,
who is CEO, sold to three people, telling a renowned doctor the truth. The tenth is a research spin-out over two
sessions (continuity, IP, FDA).

Each case has the team's messages, what a good EIR does there (`good_eir`, from Roberto's words) and expectations that
need no judgment (`expect`: hand off to a human or not, the strongest evidence the mentor may record, which consultant
fits, no switch away from Optimize).

```bash
python eval/run_eval.py                    # all cases with the configured model and the AI judge (~6 minutes)
python eval/run_eval.py --cases case07     # some cases
python eval/run_eval.py --no-judge         # checks only
python eval/run_eval.py --scripted         # the keyless mentor: tests the harness, not the coaching
```
Results go to `results/<date>_<time>/`: one JSON file per case (the conversation, record updates, checks, scores) and
`summary.md`. The judge is the same model as the mentor, so its scores are a quick signal, not a verdict: read the
conversations, overrule scores where an EIR would, and note failures and fixes in `results/NOTES.md`. Run it after
every prompt change. Only fictional data here.

## Practice characters

`practice_cases/` holds 3 fictional practice sessions, one per character, each with records for the character to
know (or not know), the student's turns, what a good character and good feedback do there, and checks:

| Case | Character | What must hold |
|---|---|---|
| `p01_customer_stays_in_role` | Target customer | Never names the idea or the venture before the student describes it; vague about "would you", promises nothing; the feedback flags the leading and hypothetical questions and lists what to check with real customers |
| `p02_challenger_catches_contradictions` | Challenger | Names the gap right after "50 paying customers" and "30 interviews" (the records show no payment and 4 interviews); never rude; the feedback lists both claims and the weak spots |
| `p03_judge_wraps_up_without_coaching` | Competition judge | Says the 4-minute pitch ran over; never coaches, praises or announces a score; closes within six team messages; the feedback scores delivery low |

```bash
python eval/run_practice_eval.py                 # all 3 cases with the configured model and the AI judge (~1 minute)
python eval/run_practice_eval.py --cases p02     # one case
python eval/run_practice_eval.py --scripted      # the characters without AI: tests the harness only
```
Results go to `results/<date>_<time>_practice/`. The judge scores five dimensions: in role, knowledge (only what the
character may know), pressure (right for the role and difficulty), feedback accuracy and feedback usefulness. Run it
after changing `knowledge/practice.json` or a `practice_*.md` prompt.
