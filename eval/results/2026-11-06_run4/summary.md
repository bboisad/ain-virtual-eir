# Evaluation run 2026-11-06 22:43 · databricks-claude-sonnet-4-6

Fictional cases from Roberto's examples (eval/cases/). Checks need no judgment; scores (1–5) come from an AI judge and can be overruled by the team.

| Case | Checks passed | challenge | evidence | focus | handoff | respect | next step | Mean |
|---|---|---|---|---|---|---|---|---|
| case01_sliced_bread | 10/12 | 5 | 4 | 3 | 5 | 5 | 4 | 4.33 |
| case02_music_teachers | 12/12 | 4 | 5 | 3 | 5 | 4 | 4 | 4.17 |
| case03_user_buyer_payer | 12/12 | 4 | 4 | 3 | 5 | 5 | 5 | 4.33 |
| case04_competitors | 13/13 | 5 | 4 | 3 | 5 | 5 | 4 | 4.33 |
| case05_implementation | 11/12 | 5 | 5 | 3 | 5 | 4 | 4 | 4.33 |
| case06_funding_reality | 13/13 | 5 | 5 | 3 | 4 | 5 | 5 | 4.5 |
| case07_team_equity | 12/12 | 3 | 3 | 3 | 5 | 5 | 4 | 3.83 |
| case08_sold_to_three | 12/13 | 4 | 5 | 3 | 5 | 5 | 4 | 4.33 |
| case09_prestige | 11/11 | 5 | 4 | 3 | 5 | 5 | 5 | 4.5 |
| case10_research_spinout | 26/27 | 5 | 5 | 3 | 5 | 5 | 4 | 4.5 |
| **All** | **132/137** | **4.5** | **4.4** | **3.0** | **4.9** | **4.8** | **4.3** | |

## Failed checks
- case01_sliced_bread: turn 1: at most 2 questions (3 question marks)
- case01_sliced_bread: turn 2: at most 2 questions (3 question marks)
- case05_implementation: turn 2: at most 2 questions (3 question marks)
- case08_sold_to_three: turn 2: at most 2 questions (3 question marks)
- case10_research_spinout: turn 4: at most 2 questions (3 question marks)

## The judge's main improvement per case
- case01_sliced_bread: Narrow each reply to one single question before moving on — the mentor repeatedly asks three variants of the same question (which student type?) in the same turn, letting the team dodge by picking none; force a committed answer before layering in the next question.
- case02_music_teachers: When the $250 price comes up, pivot immediately to budget reality — ask who actually controls the purchasing decision and whether a school district, insurer, or employer would pay — rather than simply deferring price to after problem validation, which leaves the team without any signal on the payment-source question.
- case03_user_buyer_payer: In session 1, the moment Priya says 'students will buy it,' the mentor should immediately separate user, buyer, and payer — asking who actually controls the budget and who decides — before drilling into problem depth; surfacing the disability-office buyer in session 2 is a full turn late.
- case04_competitors: Trim the explanatory paragraphs to one sentence each — the mentor is lecturing where a single sharp follow-up question would do more work and leave more room for the student to think.
- case05_implementation: Cut each response to one focused question — the installation and buyer-identity questions are the most critical and should each get their own turn rather than being stacked with secondary asks that dilute the team's attention.
- case06_funding_reality: Eliminate the near-identical closing question repeated in session 1 turn 2 — once the experiment is set and ownership is asked, the second turn should either advance the conversation or stay silent rather than re-asking the same prompt, which wastes the team's attention and dilutes the sharpness of the coaching.
- case07_team_equity: Before pivoting to the customer question, the mentor should explicitly challenge the 'we all want to stay in school' premise by naming the tension it creates — e.g., 'Investors typically expect at least one founder to be full-time; bring a concrete answer to how you address that to the EIR, not just that you all want to stay' — so the team arrives at the human conversation prepared to defend a position rather than restate a preference.
- case08_sold_to_three: Lead with the single sharpest question first: ask who inside the hospital system has the budget authority to sign the contract and whether that person has explicitly sponsored the deal — because no IT conversation matters until the economic buyer is identified and committed.
- case09_prestige: Cut the multi-paragraph procurement lecture in session 1 and replace it with a single crisp follow-up question; the mentor is doing the thinking for Helena rather than letting one pointed question pull the insight out of her.
- case10_research_spinout: In session 2, after learning the budget cycle is annual, the mentor should immediately pivot to the time-sensitive question a good EIR would ask: 'Who inside the hospital needs to champion this before the budget window closes, and do you have a clinical contact who can make that case?' — the follow-up procurement call it assigns instead delays the more critical clinical-side gap that has never been closed.

Mentor reply time: 7.8 s on average, 14.6 s at most.
