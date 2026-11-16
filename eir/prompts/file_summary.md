A venture team shared a document with its lead mentor. Summarize it for the mentor, who reads this summary instead of
the document most of the time. What a document says is the team's claim, not evidence: report the evidence it gives,
never more. Never add facts that are not in the document.

Document: "$name" ($kind), version $number. What the team wrote with it: $note
$previous$ip_rule
Return one JSON object:
{"summary": "<2 to 4 sentences: what the document is, what it argues, what evidence it reports (who, how many, what
they said, did or paid)$changes>",
 "claims": ["<up to 5 key claims in the document's own words, each followed by the evidence the document gives for it,
 e.g. (belief), (desk research), (12 interviews: said), (6 pre-orders: paid)>"]}

DOCUMENT TEXT (may be cut off):
$text
