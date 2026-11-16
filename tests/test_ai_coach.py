"""AI coach grading with a fake LLM client (no network): the model's grade is used when valid, and the keyword
rules take over when the call fails or the answer is empty."""
from eir.coach.ai import AICoach
from eir.models import Rung
from eir.seed import demo_ventures


class FakeClient:
    class cfg:
        model_name = "fake-model"

    def __init__(self, data=None, fail=False):
        self.data, self.fail, self.calls = data or {}, fail, 0

    def chat_json(self, system, prompt):
        self.calls += 1
        if self.fail:
            raise RuntimeError("the endpoint timed out")
        return self.data


def test_the_models_evidence_grade_is_used():
    v = demo_ventures()[0]
    g = AICoach(FakeClient({"rung": 3, "why": "12 movers told them"})).grade_evidence(v, "Who pays?", "12 movers said yes")
    assert g.rung == Rung.SAID and g.why == "12 movers told them"


def test_grading_falls_back_to_the_rules_when_the_model_fails_or_says_nonsense():
    v = demo_ventures()[0]
    answer = "15 students signed up for the waitlist"
    assert AICoach(FakeClient(fail=True)).grade_evidence(v, "q", answer).rung == Rung.DID
    assert AICoach(FakeClient({"rung": "lots"})).grade_evidence(v, "q", answer).rung == Rung.DID
    empty = FakeClient({"rung": 6})
    assert AICoach(empty).grade_evidence(v, "q", "  ").rung == Rung.NONE and empty.calls == 0


def test_method_rating_uses_the_model_and_falls_back_to_keywords():
    v = demo_ventures()[0]
    method = "Offer prepaid $3 listings to 10 movers"
    assert AICoach(FakeClient({"rung": 5, "why": "a payment test"})).rate_method(v, method).rung == Rung.PAID
    assert AICoach(FakeClient(fail=True)).rate_method(v, method).rung == Rung.PAID
