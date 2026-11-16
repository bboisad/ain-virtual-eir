# Evaluation run 2026-11-06 22:36 · databricks-claude-sonnet-4-6

Fictional cases from Roberto's examples (eval/cases/). Checks need no judgment; scores (1–5) come from an AI judge and can be overruled by the team.

| Case | Checks passed | challenge | evidence | focus | handoff | respect | next step | Mean |
|---|---|---|---|---|---|---|---|---|
| case01_sliced_bread | 12/12 | 5 | 5 | 4 | 5 | 5 | 4 | 4.67 |
| case02_music_teachers | 12/12 | 4 | 5 | 3 | 5 | 4 | 4 | 4.17 |
| case03_user_buyer_payer | 11/12 | 4 | 5 | 3 | 5 | 5 | 2 | 4.0 |
| case04_competitors | 12/13 | 5 | 4 | 3 | 5 | 5 | 4 | 4.33 |
| case05_implementation | 12/12 | 4 | 5 | 3 | 5 | 4 | 4 | 4.17 |
| case06_funding_reality | 11/13 | 5 | 4 | 3 | 4 | 5 | 4 | 4.17 |
| case07_team_equity | 11/12 | 2 | 2 | 3 | 5 | 4 | 4 | 3.33 |
| case08_sold_to_three | 13/13 | 4 | 5 | 4 | 5 | 5 | 5 | 4.67 |
| case09_prestige | 11/11 | 5 | 5 | 3 | 5 | 5 | 4 | 4.5 |
| case10_research_spinout | 27/27 | 5 | 4 | 3 | 5 | 5 | 4 | 4.33 |
| **All** | **132/137** | **4.3** | **4.4** | **3.2** | **4.9** | **4.7** | **3.9** | |

## Failed checks
- case03_user_buyer_payer: turn 1: no narration
- case04_competitors: records no evidence above rung 1 (highest: 2)
- case06_funding_reality: turn 1: at most 2 questions (3 question marks)
- case06_funding_reality: no human handoff needed (Funding strategy and investor readiness)
- case07_team_equity: turn 1: at most 2 questions (4 question marks)

## The judge's main improvement per case
- case01_sliced_bread: Assign a named owner to the interview experiment before closing the session — 'who can run those ten conversations by Friday?' is the right question, but the session should not end until Jordan commits a specific person's name, so the record reflects an owned next step rather than a perpetual draft.
- case02_music_teachers: After challenging the music-teacher assumption, briefly surface one or two adjacent customer segments (e.g., call-center agents, broadcasters) to stress-test why this group specifically — a good EIR opens that door without abandoning the idea, and it sharpens the team's thinking before they even run the interviews.
- case03_user_buyer_payer: End every turn with one specific, time-bound action: after surfacing the buyer/payer split the mentor should have said 'This week, schedule a 20-minute meeting with your disability services office and ask two things: who approves new vendor contracts, and what your institution currently spends per student on hearing support' — without that, the team has insight but no momentum.
- case04_competitors: When the team returns in session 2 without having done the interviews, call that out explicitly and make completing the five conversations a hard gate before moving any other topic forward, rather than re-issuing the same assignment as if it were fresh.
- case05_implementation: Cut each response to one sharp question — the mentor should have asked the installation and day-one question unprompted in session 1 rather than waiting for Diego to surface it, and should trim the multi-part closings to a single clear next action.
- case06_funding_reality: Cut the explanatory preamble in each response to one sentence and lead with the single sharp question — the mentor is currently teaching a mini-lecture before asking, which dilutes urgency and buries the call to action.
- case07_team_equity: Challenge the claims before routing them: ask 'What makes equal split the right starting point given potentially unequal time commitments?' and 'What does staying in med school mean concretely — ten hours a week or forty?' so the team arrives at the human EIR with pressure-tested positions rather than untested assumptions.
- case08_sold_to_three: In session 2, split the two asks — get the written security checklist first, then identify the HR system — so Omar has a single unambiguous priority rather than two parallel tasks that could stall each other.
- case09_prestige: Each turn should end with exactly one sharp question or one concrete action — session 1 should have asked only for the specific clinical setting first, deferring the 'name three hospitals' prompt to after Helena answers.
- case10_research_spinout: Reduce each response to one primary question and explicitly connect the annual budget-cycle finding to a timed action ('find out when the next cycle opens and schedule a meeting before it closes'), rather than treating it only as a runway-planning data point.

Mentor reply time: 9.4 s on average, 20.2 s at most.
