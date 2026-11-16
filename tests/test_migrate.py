"""v0.15 data loads and is upgraded to the multi-mentor format (schema 2); upgrading twice changes nothing."""
import json
from pathlib import Path

from eir.migrate import CURRENT, upgrade
from eir.models import Direction, ExperimentStatus, Rung, Venture
from eir.repository import JsonFileRepository
from eir.seed import demo_ventures
from eir.serde import from_dict, to_dict

FIXTURE = Path(__file__).parent / "fixtures" / "v015_campus_loop.json"


def old_campus() -> Venture:
    return from_dict(Venture, json.loads(FIXTURE.read_text(encoding="utf-8"))["venture"])


def test_v015_venture_is_upgraded_and_keeps_its_old_fields():
    v = old_campus()
    assert v.schema == 1 and not v.experiments
    upgrade(v)
    assert v.schema == CURRENT
    assert v.canvas["Channels"].rung == Rung.SAID  # "Evidence-backed" becomes rung 3, to be re-graded
    assert v.canvas["Value Propositions"].rung == Rung.ASSERTION
    assert v.canvas["Customer Relationships"].rung == Rung.NONE
    assert v.canvas["Channels"].status.value == "Evidence-backed"  # the old label is kept
    h2 = v.hypothesis("H2")
    assert [(i.direction, i.rung) for i in h2.evidence_items] == [(Direction.UNCLEAR, Rung.SAID)]
    (x,) = v.experiments
    assert x.assumption_id == "H2" and x.method == h2.test and x.status == ExperimentStatus.DRAFT
    assert not x.supported_if and not x.refuted_if  # it cannot start until the team writes down the criteria


def test_upgrade_is_idempotent():
    v = upgrade(old_campus())
    before = to_dict(v)
    assert to_dict(upgrade(v)) == before


def test_json_repository_upgrades_on_load_and_keeps_new_fields(tmp_path):
    repo = JsonFileRepository(tmp_path)
    old = old_campus()
    (tmp_path / f"{old.id}.json").write_text(json.dumps(to_dict(old)), encoding="utf-8")
    v = repo.get(old.id)
    assert v.schema == CURRENT and v.experiments
    v.focus.text = "Will sellers pay?"
    repo.save(v)
    assert repo.get(old.id).focus.text == "Will sellers pay?"


def test_demo_seeds_are_current_and_not_duplicated():
    for v in demo_ventures():
        assert v.schema == CURRENT
    campus = next(v for v in demo_ventures() if v.id == "V-CAMPUS")
    assert [x.id for x in campus.experiments] == ["X-fee"]  # no second experiment from the old test text
