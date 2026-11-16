"""Data model and storage."""
from eir.models import Venture
from eir.repository import JsonFileRepository
from eir.seed import demo_ventures
from eir.serde import from_dict, to_dict


def test_seed_roundtrip():
    for v in demo_ventures():
        assert from_dict(Venture, to_dict(v)) == v


def test_old_data_without_new_fields_still_loads():
    raw = to_dict(demo_ventures()[0])
    for newer_field in ("disagreements", "mode", "handoff", "conversation"):
        raw.pop(newer_field)
    v = from_dict(Venture, raw)
    assert v.disagreements == [] and v.handoff is None


def test_json_repository(tmp_path):
    repo = JsonFileRepository(tmp_path)
    v = demo_ventures()[1]
    repo.save(v)
    assert repo.get(v.id) == v and [x.id for x in repo.list()] == [v.id]
