"""Operator tools against fake durable storage, never real cloud accounts."""
import copy
import hashlib
import sys
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import cloud_check
import migrate_cloud
import restore_cloud
from eir.cloud import CloudStorageError, StorageConflict
from eir.filestore import LocalFileStore
from eir.models import FileKind, FileVersion, ProjectFile
from eir.seed import demo_ventures
from eir.serde import to_dict
from test_cloud import Backend, Response, repo, store


class HistoryBackend(Backend):
    def __init__(self):
        super().__init__()
        self.history_response = None

    def open(self, request, timeout):
        url = urlsplit(request.full_url)
        if unquote(url.path) == "/rest/v1/eir_venture_versions":
            self.requests.append((request, timeout))
            if self.history_response is not None:
                return Response(self.history_response)
            query = parse_qs(url.query)
            venture_id = query["venture_id"][0].removeprefix("eq.")
            revision = int(query["revision"][0].removeprefix("eq."))
            rows = [{"venture_id": v["id"], "revision": v["revision"], "payload": copy.deepcopy(v["payload"])}
                    for v in self.versions if v["id"] == venture_id and v["revision"] == revision]
            return Response(rows)
        return super().open(request, timeout)


def local_project(tmp_path):
    venture = demo_ventures()[0]
    original = "虚构访谈：三位学生提到搬家需求。".encode()
    key = f"{venture.id}/F-MIGRATE/v1.md"
    source = LocalFileStore(tmp_path)
    source.put(key, original)
    source.put(key + ".txt", original)
    venture.files = [ProjectFile(name="notes.md", kind=FileKind.TEXT,
        versions=[FileVersion(number=1, blob=key, sha256=hashlib.sha256(original).hexdigest(),
                              chars=len(original.decode()))])]
    return venture, source, key, original


def history(backend, tmp_path):
    venture, source, key, original = local_project(tmp_path)
    adapter, blobs = repo(backend), store(backend)
    migrate_cloud.migrate([venture], source, adapter, blobs)
    old_description = venture.description
    changed = adapter.get(venture.id)
    changed.description = "Current accepted change"
    changed.files = []  # Old file bytes remain private and available to history.
    adapter.save(changed)
    return adapter, blobs, venture.id, old_description, key


def test_migration_checks_payload_blobs_and_is_idempotent(tmp_path):
    venture, source, key, original = local_project(tmp_path)
    backend = HistoryBackend()
    assert migrate_cloud.migrate([venture], source, repo(backend), store(backend)) == (1, 0)
    assert backend.objects[key] == original
    assert backend.objects[key + ".txt"] == original
    saved = to_dict(repo(backend).get(venture.id))
    # Re-running never overwrites an existing project with newly edited source data.
    changed = copy.deepcopy(venture)
    changed.description = "Do not overwrite"
    assert migrate_cloud.migrate([changed], source, repo(backend), store(backend)) == (0, 1)
    assert to_dict(repo(backend).get(venture.id)) == saved
    assert len(backend.versions) == 1


def test_migration_rejects_corrupt_source_and_different_cloud_blob(tmp_path):
    venture, source, key, original = local_project(tmp_path)
    source.put(key, b"corrupt")
    with pytest.raises(ValueError, match="checksum"):
        migrate_cloud.planned_blobs(venture, source)
    source.put(key, original)
    backend = HistoryBackend()
    backend.objects[key] = b"prior cloud object"
    with pytest.raises(ValueError, match="different content"):
        migrate_cloud.migrate([venture], source, repo(backend), store(backend))
    assert backend.objects[key] == b"prior cloud object"
    assert not backend.rows


def test_seed_migration_dry_run_does_not_load_cloud_settings(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("A dry run must not access cloud settings")
    monkeypatch.setattr(migrate_cloud, "settings", forbidden)
    assert migrate_cloud.main(["--seed-demo"]) == 0


def test_cloud_check_write_fixture_rejects_stale_and_purges_only_its_file():
    backend = HistoryBackend()
    backend.objects["V-OTHER/F1/v1.txt"] = b"keep"
    fixture = cloud_check.write_test(repo(backend), store(backend))
    assert fixture.startswith("V-CLOUDCHECK-")
    assert backend.objects == {"V-OTHER/F1/v1.txt": b"keep"}
    assert [v["revision"] for v in backend.versions] == [1, 2]


def test_secrets_override_environment_like_the_app(tmp_path, monkeypatch):
    secret = tmp_path / "secrets.toml"
    secret.write_text('SUPABASE_URL="https://file.example.test"\nSUPABASE_SECRET_KEY="sb_secret_file"\n')
    monkeypatch.setenv("SUPABASE_URL", "https://env.example.test")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "sb_secret_env")
    configured = cloud_check.settings(secret)
    assert configured["url"] == "https://file.example.test"
    assert configured["key"] == "sb_secret_file"


def test_bucket_check_disallows_redirects(monkeypatch):
    observed = []
    class Opener:
        def open(self, request, timeout):
            assert request.get_header("Authorization") is None  # New secret keys are not JWTs.
            return Response({"id": "eir-files", "public": False})
    def fake_build(*handlers):
        observed.extend(handlers)
        return Opener()
    monkeypatch.setattr(cloud_check, "build_opener", fake_build)
    cloud_check.check_bucket({"url": "https://example.test", "key": "sb_secret_test", "bucket": "eir-files"})
    assert len(observed) == 1
    assert observed[0].redirect_request(None, None, 302, "", {}, "https://other.test") is None


def test_restore_dry_plan_preserves_history_and_apply_appends_revision(tmp_path):
    backend = HistoryBackend()
    adapter, blobs, venture_id, old_description, key = history(backend, tmp_path)
    before = copy.deepcopy(backend.versions)
    plan = restore_cloud.prepare_restore(adapter, blobs, venture_id, 1)
    assert plan.current_revision == 2 and plan.checked_objects == 2
    assert plan.venture.description == old_description
    assert backend.versions == before  # Planning is read-only.
    assert restore_cloud.apply_restore(adapter, plan) == 3
    assert backend.versions[:2] == before
    assert adapter.get(venture_id).description == old_description
    assert key in backend.objects


def test_restore_rejects_wrong_project_unknown_revision_and_missing_bytes(tmp_path):
    backend = HistoryBackend()
    adapter, blobs, venture_id, _, key = history(backend, tmp_path)
    with pytest.raises(ValueError, match="does not exist"):
        restore_cloud.prepare_restore(adapter, blobs, venture_id, 99)
    payload = copy.deepcopy(backend.versions[0]["payload"])
    payload["id"] = "V-OTHER"
    backend.history_response = [{"venture_id": venture_id, "revision": 1, "payload": payload}]
    with pytest.raises(ValueError, match="does not match"):
        restore_cloud.prepare_restore(adapter, blobs, venture_id, 1)
    backend.history_response = None
    del backend.objects[key]
    with pytest.raises(ValueError, match="file needed"):
        restore_cloud.prepare_restore(adapter, blobs, venture_id, 1)
    assert len(backend.versions) == 2


def test_restore_rejects_intervening_write_and_reviewed_revision_mismatch(tmp_path):
    backend = HistoryBackend()
    adapter, blobs, venture_id, _, _ = history(backend, tmp_path)
    plan = restore_cloud.prepare_restore(adapter, blobs, venture_id, 1)
    changed = adapter.get(venture_id)
    changed.description = "A newer concurrent edit"
    adapter.save(changed)
    with pytest.raises(StorageConflict):
        restore_cloud.apply_restore(adapter, plan)
    assert adapter.get(venture_id).description == "A newer concurrent edit"
    with pytest.raises(CloudStorageError, match="changed since"):
        restore_cloud.prepare_restore(adapter, blobs, venture_id, 1, expected_current=2)
    assert len(backend.versions) == 3
