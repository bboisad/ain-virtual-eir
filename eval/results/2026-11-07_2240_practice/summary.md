# Practice evaluation run 2026-11-07 22:40 · databricks-claude-sonnet-4-6

Fictional practice cases (eval/practice_cases/). Checks need no judgment; scores (1–5) come from an AI judge and can be overruled by the team.

| Case | Checks passed | in role | knowledge | pressure | feedback accuracy | feedback useful | Mean |
|---|---|---|---|---|---|---|---|
| p01_customer_stays_in_role | 24/24 | 5 | 5 | 4 | 5 | 4 | 4.6 |
| p02_challenger_catches_contradictions | 25/25 | 5 | 5 | 5 | 5 | 5 | 5.0 |
| p03_judge_wraps_up_without_coaching | 24/24 | 4 | 5 | 4 | 4 | 5 | 4.4 |
| **All** | **73/73** | **4.7** | **5.0** | **4.3** | **4.7** | **4.7** | |

## Failed checks
- none

## The judge's main improvement per case
- p01_customer_stays_in_role: The 'To check with real customers' section should open with an explicit disclaimer that Renata is a simulated character and her details (the $12 garage cost, the notebook habit, the referral difficulty) are hypotheses to test, not data points already collected, so the team does not treat the AI's invented specifics as partial validation.
- p02_challenger_catches_contradictions: The feedback's 'Toughest questions' section already supplies model answers, which is valuable, but it should explicitly instruct the team to rehearse delivering those answers aloud before the next session so the habit of leading with real evidence becomes automatic under pressure.
- p03_judge_wraps_up_without_coaching: When a student gives a completely off-topic answer to a direct follow-up (as Sofia did twice on the 90% question), the judge must name the evasion explicitly—e.g., 'That still doesn't tell me where the 90% comes from; is it data or a guess?'—rather than closing the line of questioning, so the pressure matches the Realistic difficulty setting.

Character reply time: 1.8 s on average, 5.9 s at most.
