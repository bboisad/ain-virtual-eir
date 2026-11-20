"""Cloud adapter contract tests with an HTTP boundary fake; no account or network."""
import base64
import copy
import io
import json
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, unquote, urlsplit

import pytest

from eir.cloud import CloudStorageError, StorageConflict, SupabaseFileStore, SupabaseRepository
from eir.seed import demo_ventures
from eir.serde import to_dict


KEY = "sb_secret_test_backend_key"
URL = "https://cloud.example.test"


class Response:
    def __init__(self, body):
        self.body = body if isinstance(body, bytes) else json.dumps(body).encode()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self.body


def http_error(code, body=None):
    return HTTPError(URL, code, "hidden upstream message", {},
                     io.BytesIO(json.dumps(body or {}).encode()))


class Backend:
    """Shares durable state across adapter instances, using the SQL CAS contract."""
    def __init__(self):
        self.rows = {}
        self.versions = []
        self.objects = {}
        self.requests = []
        self.fail = None

    def open(self, request, timeout):
        self.requests.append((request, timeout))
        if self.fail:
            raise self.fail
        url = urlsplit(request.full_url)
        path, query = unquote(url.path), parse_qs(url.query)
        if path == "/rest/v1/eir_ventures":
            rows = sorted(self.rows.values(), key=lambda r: r["id"])
            if "id" in query:
                rows = [r for r in rows if r["id"] == query["id"][0][3:]]
            offset = int(query.get("offset", [0])[0])
            limit = int(query.get("limit", [200])[0])
            return Response(copy.deepcopy(rows[offset:offset + limit]))
        if path == "/rest/v1/rpc/eir_save_venture":
            body = json.loads(request.data)
            row = self.rows.get(body["p_id"])
            current = row["revision"] if row else 0
            if current != body["p_expected_revision"]:
                raise http_error(409, {"code": "PT409"})
            saved = {"id": body["p_id"], "payload": body["p_payload"], "revision": current + 1}
            self.rows[saved["id"]] = copy.deepcopy(saved)
            self.versions.append(copy.deepcopy(saved))
            return Response({"revision": current + 1})
        prefix = "/storage/v1/object/eir-files"
        if request.method == "GET":
            assert path.startswith("/storage/v1/object/authenticated/")
            path = path.replace("/storage/v1/object/authenticated/", "/storage/v1/object/", 1)
        if path == prefix and request.method == "DELETE":
            for key in json.loads(request.data)["prefixes"]:
                self.objects.pop(key, None)
            return Response([])
        if path.startswith(prefix + "/"):
            key = path[len(prefix) + 1:]
            if request.method == "POST":
                if key in self.objects:
                    raise http_error(400, {"statusCode": "409", "error": "Duplicate"})
                self.objects[key] = request.data
                return Response({"Key": key})
            if request.method == "GET":
                if key not in self.objects:
                    raise http_error(400, {"statusCode": "404", "error": "not_found"})
                return Response(self.objects[key])
        raise AssertionError((request.method, request.full_url))


def repo(backend):
    adapter = SupabaseRepository(URL, KEY)
    adapter._client.opener = backend
    return adapter


def store(backend):
    adapter = SupabaseFileStore(URL, KEY)
    adapter._client.opener = backend
    return adapter


def test_project_persists_across_repository_instances_and_records_versions():
    backend = Backend()
    venture = demo_ventures()[0]
    repo(backend).save(venture)
    loaded = repo(backend).get(venture.id)
    assert loaded == venture
    loaded.description = "Updated project description"
    repo(backend).save(loaded)
    assert repo(backend).get(venture.id).description == "Updated project description"
    assert [v["revision"] for v in backend.versions] == [1, 2]
    assert "_storage_revision" not in backend.rows[venture.id]["payload"]
    assert backend.versions[0]["payload"]["description"] != loaded.description


def test_stale_writer_and_duplicate_creation_do_not_overwrite():
    backend = Backend()
    venture = demo_ventures()[0]
    writer = repo(backend)
    writer.save(venture)
    first, stale = writer.get(venture.id), writer.get(venture.id)
    first.description = "Latest accepted change"
    writer.save(first)
    stale.description = "Stale edit"
    # A fresh read in the same repository must not update the stale object's revision.
    writer.get(venture.id)
    with pytest.raises(StorageConflict):
        writer.save(stale)
    with pytest.raises(StorageConflict):
        writer.save(demo_ventures()[0])
    assert writer.get(venture.id).description == "Latest accepted change"
    assert len(backend.versions) == 2
    assert stale._storage_revision == 1


def test_project_list_paginates_and_missing_project_is_keyerror():
    backend = Backend()
    writer = repo(backend)
    writer.PAGE_SIZE = 2
    for n in range(5):
        venture = demo_ventures()[0]
        venture.id = f"V-{n}"
        writer.save(venture)
    assert [v.id for v in writer.list()] == [f"V-{n}" for n in range(5)]
    with pytest.raises(KeyError):
        writer.get("does-not-exist")


@pytest.mark.parametrize("error, words", [
    (http_error(403, {"message": KEY}), "denied"),
    (http_error(404), "supabase.sql"),
    (http_error(500, {"message": KEY}), "HTTP 500"),
    (URLError(KEY), "Cannot reach"),
    (TimeoutError(KEY), "Cannot reach"),
])
def test_cloud_errors_are_sanitized_and_not_retried(error, words):
    backend = Backend()
    backend.fail = error
    with pytest.raises(CloudStorageError, match=words) as caught:
        repo(backend).list()
    assert KEY not in str(caught.value)
    assert len(backend.requests) == 1


def test_invalid_cloud_payload_and_unconfirmed_save_fail_closed():
    backend = Backend()
    venture = demo_ventures()[0]
    repo(backend).save(venture)
    backend.rows[venture.id]["payload"]["id"] = "another-project"
    with pytest.raises(CloudStorageError, match="invalid"):
        repo(backend).get(venture.id)
    adapter = repo(backend)
    adapter._client.json = lambda *args, **kwargs: {"revision": 7}
    fresh = demo_ventures()[1]
    with pytest.raises(CloudStorageError, match="could not be confirmed"):
        adapter.save(fresh)
    assert not hasattr(fresh, "_storage_revision")


def test_file_bytes_survive_store_instances_and_removal_retains_backup_objects():
    backend = Backend()
    key = "V-CAMPUS/file-1/v1.pdf"
    content = b"%PDF\x00\xff\nfictional document"
    store(backend).put(key, content)
    assert store(backend).get(key) == content
    request, timeout = backend.requests[0]
    assert request.get_header("X-upsert") == "false"
    assert timeout == 20
    before = len(backend.requests)
    store(backend).delete(key)
    store(backend).delete(key)
    assert len(backend.requests) == before  # metadata removal cannot delete a newer writer's bytes
    assert store(backend).get(key) == content
    store(backend).purge(key)
    store(backend).purge(key)
    with pytest.raises(KeyError):
        store(backend).get(key)


def test_file_version_is_immutable_and_identical_retry_is_safe():
    backend = Backend()
    files = store(backend)
    key = "V-CAMPUS/file-1/v1.txt"
    files.put(key, b"original")
    files.put(key, b"original")
    with pytest.raises(StorageConflict, match="new version"):
        files.put(key, b"conflicting content")
    assert files.get(key) == b"original"


@pytest.mark.parametrize("key", ["../secret", "/secret", "a/../secret", "a//b", "a/./b",
                                "a\\b", "a/%2e%2e/x", "a\nsecret", "", "a/"])
def test_invalid_file_paths_never_reach_cloud(key):
    backend = Backend()
    files = store(backend)
    for operation in (lambda: files.put(key, b"x"), lambda: files.get(key), lambda: files.delete(key)):
        with pytest.raises(KeyError):
            operation()
    assert backend.requests == []


def test_packaged_demo_files_are_read_only_and_need_no_cloud_request():
    backend = Backend()
    files = store(backend)
    assert b"Campus" in files.get("seed:campus_interview_notes.md")
    with pytest.raises(KeyError, match="read-only"):
        files.put("seed:campus_interview_notes.md", b"replace")
    with pytest.raises(KeyError):
        files.get("seed:../../models.py")
    files.delete("seed:campus_interview_notes.md")
    assert backend.requests == []


def test_secret_keys_and_legacy_service_jwts_use_correct_headers():
    backend = Backend()
    repo(backend).list()
    request = backend.requests[-1][0]
    assert request.get_header("Apikey") == KEY
    assert request.get_header("Authorization") is None
    payload = base64.urlsafe_b64encode(json.dumps({"role": "service_role"}).encode()).decode().rstrip("=")
    jwt = f"eyJhbGciOiJIUzI1NiJ9.{payload}.test-signature"
    adapter = SupabaseRepository(URL, jwt)
    adapter._client.opener = backend
    adapter.list()
    request = backend.requests[-1][0]
    assert request.get_header("Authorization") == "Bearer " + jwt
    assert request.get_header("Apikey") == jwt


@pytest.mark.parametrize("url", ["http://cloud.example.test", "https://user:password@cloud.example.test",
                                "https://cloud.example.test/rest/v1", "https://cloud.example.test?key=secret"])
def test_untrusted_project_origins_are_rejected(url):
    with pytest.raises(CloudStorageError, match="HTTPS project origin"):
        SupabaseRepository(url, KEY)


def test_loopback_http_is_allowed_for_local_integration_tests_and_public_keys_rejected():
    SupabaseRepository("http://127.0.0.1:54321", KEY)
    with pytest.raises(CloudStorageError, match="backend secret"):
        SupabaseRepository(URL, "sb_publishable_public-key")


def test_sql_locks_down_direct_access_and_keeps_atomic_history():
    sql = (Path(__file__).resolve().parents[1] / "deploy" / "supabase.sql").read_text()
    assert "eir_ventures enable row level security" in sql
    assert "eir_venture_versions enable row level security" in sql
    assert "from public, anon, authenticated" in sql
    assert "grant execute on function public.eir_save_venture(text, jsonb, bigint) to service_role" in sql
    assert "where id = p_id and revision = p_expected_revision" in sql
    assert "raise sqlstate 'PT409'" in sql
    assert "insert into public.eir_venture_versions" in sql
    assert "values ('eir-files', 'eir-files', false" in sql
