# Practice evaluation run 2026-11-07 22:37 · databricks-claude-sonnet-4-6

Fictional practice cases (eval/practice_cases/). Checks need no judgment; scores (1–5) come from an AI judge and can be overruled by the team.

| Case | Checks passed | in role | knowledge | pressure | feedback accuracy | feedback useful | Mean |
|---|---|---|---|---|---|---|---|
| p01_customer_stays_in_role | 24/24 | 5 | 5 | 3 | 4 | 5 | 4.4 |
| p02_challenger_catches_contradictions | 25/25 | 5 | 5 | 5 | 5 | 5 | 5.0 |
| p03_judge_wraps_up_without_coaching | 24/24 | 4 | 5 | 4 | 4 | 5 | 4.4 |
| **All** | **73/73** | **4.7** | **5.0** | **4.0** | **4.3** | **5.0** | |

## Failed checks
- none

## The judge's main improvement per case
- p01_customer_stays_in_role: Darnell should have gently pressed the vague 'stress, mostly' answer himself — something like a brief pause and 'Can you say more about that?' — so the character models the interviewing gap in real time rather than leaving it entirely to the feedback coach to catch.
- p02_challenger_catches_contradictions: The character should have followed its final question ('who actually pays the fee?') with one more press if the team had answered, but since the session ended there, the single most important improvement is for the feedback to add a specific willingness-to-pay test design (e.g., 'show a mock invoice to two lab managers and record yes/no') rather than leaving 'a structured test' as a concept the team must still invent.
- p03_judge_wraps_up_without_coaching: When Sofia deflects a direct economics question with an unrelated answer, the judge should restate the specific number from the question ('at 25% loss, does $2 still cover costs?') rather than broadening to 'do you know your cost per crate at all'—tighter re-asks force the student to either answer or explicitly admit they cannot, which is more instructive pressure.

Character reply time: 1.6 s on average, 2.4 s at most.
