# Evaluation run 2026-11-06 22:31 · databricks-claude-sonnet-4-6

Fictional cases from Roberto's examples (eval/cases/). Checks need no judgment; scores (1–5) come from an AI judge and can be overruled by the team.

| Case | Checks passed | challenge | evidence | focus | handoff | respect | next step | Mean |
|---|---|---|---|---|---|---|---|---|
| case01_sliced_bread | 12/12 | 5 | 4 | 3 | 5 | 5 | 4 | 4.33 |
| case02_music_teachers | 11/12 | 4 | 4 | 2 | 5 | 4 | 3 | 3.67 |
| case03_user_buyer_payer | 12/12 | 4 | 5 | 3 | 5 | 5 | 2 | 4.0 |
| case04_competitors | 13/13 | 5 | 4 | 3 | 5 | 5 | 3 | 4.17 |
| case05_implementation | 11/12 | 4 | 5 | 3 | 5 | 4 | 3 | 4.0 |
| case06_funding_reality | 13/13 | 5 | 5 | 3 | 4 | 5 | 4 | 4.33 |
| case07_team_equity | 11/12 | 3 | 4 | 3 | 5 | 5 | 4 | 4.0 |
| case08_sold_to_three | 12/13 | 5 | 5 | 3 | 5 | 5 | 4 | 4.5 |
| case09_prestige | 10/11 | 5 | 4 | 3 | 5 | 5 | 4 | 4.33 |
| case10_research_spinout | 25/27 | 4 | 5 | 3 | 5 | 5 | 4 | 4.33 |
| **All** | **130/137** | **4.4** | **4.5** | **2.9** | **4.9** | **4.8** | **3.5** | |

## Failed checks
- case02_music_teachers: turn 1: at most 2 questions (3 question marks)
- case05_implementation: turn 1: at most 2 questions (3 question marks)
- case07_team_equity: turn 1: at most 2 questions (4 question marks)
- case08_sold_to_three: turn 2: at most 2 questions (3 question marks)
- case09_prestige: turn 2: at most 2 questions (3 question marks)
- case10_research_spinout: turn 2: at most 2 questions (3 question marks)
- case10_research_spinout: turn 4: at most 2 questions (3 question marks)

## The judge's main improvement per case
- case01_sliced_bread: Cut each response to one sharp question: after Jordan's second message the only thing that matters is 'name five students you will talk to this week' — everything else (competitor framing, HelloFresh rebuttal) should be dropped or saved for after evidence comes back.
- case02_music_teachers: Cut each response to one sharp question and end with a single concrete next action (e.g., 'talk to five music teachers and find out the last time they lost their voice and what it cost them') — the current responses are too long and bury the ask.
- case03_user_buyer_payer: End every turn with one explicit next action: after surfacing the buyer/payer split, the mentor should have said 'Your next step is to book a 30-minute meeting with the disability services director this week and ask whether they would replace or supplement note-taker funding with a software tool.'
- case04_competitors: End each response with exactly one assigned action and a deadline — for example, 'Before we meet again, interview three students who study from lecture slides and ask them to show you how they make flashcards today; bring back what they said and did, not what they think they would use.'
- case05_implementation: End every reply with one concrete assigned action and a number — e.g., 'Before next session, interview five coaches at programs other than your own and ask what specifically goes wrong when rowers can't hear the cox' — so the team leaves with a test, not just a question.
- case06_funding_reality: Collapse each response to a single, unnested question — pick one: either 'Who is your target student?' or 'Have you spoken to any of them?' — so the team cannot deflect by answering the easier sub-question and the mentor gets a clean, testable answer next session.
- case07_team_equity: Cut the explanatory preamble in each reply to one sentence and spend that space on a single sharper challenge — e.g., 'If one of you graduates in May and the others don't, should that person's equity vest faster?' — so the team arrives at the human EIR already stress-tested, not just informed.
- case08_sold_to_three: Reduce each response to one prioritized question — in session 2, drop the 'do you have any of those today' half and just ask Omar to share whatever written requirements IT has already sent, so the next session starts from a document rather than another verbal report.
- case09_prestige: Trim the explanatory scaffolding (procurement committees, named competitors, switching-cost theory) and let the two sharp questions do the work alone — the mentor is teaching when it should be probing.
- case10_research_spinout: Reduce each response to one single sharp question — the multi-part questioning dilutes focus and buries the most important ask; in session 2 the mentor should have closed with exactly one action: 'Find out when this year's budget cycle closes and get in front of the right person before that date.'

Mentor reply time: 6.9 s on average, 14.7 s at most.
