Write the $name consultant's summary of the consultation below for the team's lead mentor. The mentor never sees the
conversation, only this summary, and the student reads it before it is sent. Use only what was said in the
CONSULTATION; never invent. The brief is context: nothing in it counts as said in this consultation (for example, a
belief the brief mentions is not a disagreement unless the student said it here). Empty lists are fine.

Return one JSON object with exactly these keys:
{"question": "<the question you were asked>",
 "conclusions": ["<what the consultation established, each with its evidence level: said / did / paid>"],
 "missing_evidence": ["<what would still have to be shown>"],
 "suggested_todos": ["<a concrete next step in one sentence>"],
 "needs_human": <true or false>,
 "human_topic": "<the topic for a human AIN EIR, or empty>",
 "disagreements": ["<where the student disagreed with you>"],
 "out_of_scope": ["<questions the student asked that are outside your scope, for the mentor>"]}
At most 4 conclusions and 3 to-dos. needs_human is true if any of these came up: $must_hand_off.

BRIEF FROM THE LEAD MENTOR:
$brief

CONSULTATION:
$transcript
