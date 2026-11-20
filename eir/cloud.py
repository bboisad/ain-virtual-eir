"""Server-side Supabase persistence for the classroom prototype.

Only this module knows the cloud REST API. The existing repository and file-store
interfaces remain unchanged. A backend secret key belongs in deployment secrets,
never in the browser. Application membership checks and the private-demo access
gate still apply; this adapter does not turn demo account selection into real auth.
"""
from __future__ import annotations

import base64
import json
import re
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .filestore import SEED, _seed
from .migrate import upgrade
from .models import Venture
from .serde import from_dict, to_dict


class CloudStorageError(RuntimeError):
    """A sanitized configuration, connection, permission or cloud response error."""


class StorageConflict(CloudStorageError):
    """The project or file changed since it was loaded; never retry as an overwrite."""


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # A redirected request must not carry the backend key to another origin.
        return None


def _project_id(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}", value):
        raise ValueError("Invalid project identifier.")
    return value


def _object_key(value: str) -> str:
    if (not isinstance(value, str) or not value or len(value) > 1024
            or "\\" in value or "%" in value or any(ord(c) < 32 or ord(c) == 127 for c in value)
            or any(part in ("", ".", "..") for part in value.split("/"))):
        raise KeyError("Invalid file key.")
    return value


def _legacy_service_key(key: str) -> bool:
    try:
        head, payload, signature = key.split(".")
        if not head or not signature:
            return False
        decoded = base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4))
        return json.loads(decoded).get("role") == "service_role"
    except (ValueError, TypeError, AttributeError):
        return False


class _Client:
    def __init__(self, url: str, key: str, timeout: float):
        parts = urlsplit(url.strip())
        local = parts.hostname in ("localhost", "127.0.0.1", "::1")
        if (not parts.hostname or (parts.scheme != "https" and not (local and parts.scheme == "http"))
                or parts.username or parts.password or parts.query or parts.fragment
                or parts.path not in ("", "/")):
            raise CloudStorageError("SUPABASE_URL must be the HTTPS project origin.")
        legacy = _legacy_service_key(key)
        if not (legacy or (key.startswith("sb_secret_") and len(key) > len("sb_secret_"))):
            raise CloudStorageError("Configure a Supabase backend secret key, not a publishable or anon key.")
        if any(c in key for c in "\r\n"):
            raise CloudStorageError("Invalid Supabase backend key.")
        if not 0 < timeout <= 120:
            raise CloudStorageError("Cloud request timeout must be between 0 and 120 seconds.")
        self.origin = url.strip().rstrip("/")
        self.timeout = timeout
        self.headers = {"apikey": key, "Accept": "application/json"}
        # New secret keys are not JWTs. Sending one as a Bearer JWT is invalid.
        if legacy:
            self.headers["Authorization"] = f"Bearer {key}"
        self.opener = build_opener(_NoRedirect())

    def request(self, method: str, path: str, *, data: bytes | None = None,
                headers: dict[str, str] | None = None, missing_key: str | None = None) -> bytes:
        request = Request(self.origin + path, data=data, method=method,
                          headers={**self.headers, **(headers or {})})
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                return response.read()
        except HTTPError as error:
            status = error.code
            try:
                detail = json.loads(error.read(4096))
                code = str(detail.get("statusCode") or detail.get("code") or detail.get("error") or "")
            except (ValueError, AttributeError):
                code = ""
            if status == 409 or code in ("PT409", "409", "Duplicate", "KeyAlreadyExists"):
                raise StorageConflict("Another session changed this item. Reload before trying again.") from None
            if missing_key is not None and (status == 404 or code in ("404", "not_found", "NoSuchKey")):
                raise KeyError(missing_key) from None
            if status in (401, 403):
                raise CloudStorageError("Cloud access was denied. Check the server key and database permissions.") from None
            if status == 404:
                raise CloudStorageError("Cloud endpoint not found. Run deploy/supabase.sql and check the project URL.") from None
            raise CloudStorageError(f"Cloud request failed (HTTP {status}). No changes were retried.") from None
        except (URLError, TimeoutError, OSError, ValueError):
            raise CloudStorageError("Cannot reach cloud storage. Check the connection and try again.") from None

    def json(self, method: str, path: str, body=None):
        data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
        raw = self.request(method, path, data=data,
                           headers={"Content-Type": "application/json"} if body is not None else None)
        try:
            return json.loads(raw)
        except (ValueError, UnicodeError):
            raise CloudStorageError("Cloud storage returned an invalid response.") from None


class SupabaseRepository:
    """One versioned JSONB snapshot per venture, with atomic optimistic writes.

    Each loaded object carries its own revision, rather than a repository-global
    revision. Loading the same project elsewhere cannot accidentally authorize a
    stale object's save. New untagged objects may only create new projects.
    """
    PAGE_SIZE = 200

    def __init__(self, url: str, key: str, *, timeout: float = 20.0):
        self._client = _Client(url, key, timeout)

    def _load(self, row: dict) -> Venture:
        try:
            payload, revision = row["payload"], row["revision"]
            if not isinstance(payload, dict) or type(revision) is not int or revision < 1:
                raise ValueError
            venture = upgrade(from_dict(Venture, payload))
            if row["id"] != venture.id:
                raise ValueError
            _project_id(venture.id)
        except (KeyError, ValueError, TypeError, AttributeError):
            raise CloudStorageError("Cloud project data is invalid. Restore a known good version.") from None
        venture._storage_revision = revision
        return venture

    def list(self) -> list[Venture]:
        result, offset = [], 0
        while True:
            query = urlencode({"select": "id,payload,revision", "order": "id.asc",
                               "limit": self.PAGE_SIZE, "offset": offset})
            rows = self._client.json("GET", "/rest/v1/eir_ventures?" + query)
            if not isinstance(rows, list):
                raise CloudStorageError("Cloud storage returned an invalid project list.")
            result.extend(self._load(row) for row in rows)
            if len(rows) < self.PAGE_SIZE:
                return result
            offset += len(rows)

    def get(self, venture_id: str) -> Venture:
        identifier = _project_id(venture_id)
        query = urlencode({"id": "eq." + identifier, "select": "id,payload,revision", "limit": 1})
        rows = self._client.json("GET", "/rest/v1/eir_ventures?" + query)
        if not isinstance(rows, list):
            raise CloudStorageError("Cloud storage returned invalid project data.")
        if not rows:
            raise KeyError(identifier)
        venture = self._load(rows[0])
        if venture.id != identifier:
            raise CloudStorageError("Cloud storage returned a different project.")
        return venture

    def save(self, venture: Venture) -> None:
        identifier = _project_id(venture.id)
        expected = getattr(venture, "_storage_revision", 0)
        if type(expected) is not int or expected < 0:
            raise CloudStorageError("Invalid local project version. Reload the project.")
        result = self._client.json("POST", "/rest/v1/rpc/eir_save_venture", {
            "p_id": identifier, "p_payload": to_dict(venture), "p_expected_revision": expected,
        })
        if not isinstance(result, dict) or result.get("revision") != expected + 1:
            raise CloudStorageError("Cloud save could not be confirmed. Reload before saving again.")
        venture._storage_revision = expected + 1


class SupabaseFileStore:
    """Private cloud objects and packaged read-only demo files.

    Version paths are immutable. An identical retry is accepted; another upload
    cannot overwrite an existing version before the project CAS detects a conflict.
    Removing a project attachment retains its private blobs, so a stale metadata
    writer cannot destroy a newer session's files or the version-history backup.
    """
    immutable_versions = True

    def __init__(self, url: str, key: str, bucket: str = "eir-files", *, timeout: float = 20.0):
        if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,62}", bucket):
            raise CloudStorageError("Invalid cloud file bucket name.")
        self._client = _Client(url, key, timeout)
        self.bucket = bucket

    def _path(self, key: str, *, authenticated: bool = False) -> str:
        prefix = "/storage/v1/object/" + ("authenticated/" if authenticated else "")
        return prefix + self.bucket + "/" + quote(_object_key(key), safe="/")

    def put(self, key: str, data: bytes) -> None:
        if key.startswith(SEED):
            raise KeyError("Demo files are read-only.")
        path = self._path(key)
        try:
            self._client.request("POST", path, data=bytes(data), headers={
                "Content-Type": "application/octet-stream", "x-upsert": "false",
                "Cache-Control": "private, no-store",
            })
        except StorageConflict:
            if self.get(key) != bytes(data):
                raise StorageConflict("This file version already exists. Reload and upload a new version.") from None

    def get(self, key: str) -> bytes:
        if key.startswith(SEED):
            return _seed(key)
        return self._client.request("GET", self._path(key, authenticated=True),
                                    headers={"Accept": "application/octet-stream"},
                                    missing_key=key)

    def delete(self, key: str) -> None:
        """Validate removal, retaining private bytes until an operator purges them.

        The calling action removes the file from project metadata, which is saved
        with optimistic concurrency. A blob cannot be safely deleted before that
        save succeeds; it may still be referenced by another session or a backup.
        """
        if key.startswith(SEED):
            return
        _object_key(key)

    def purge(self, key: str) -> None:
        """Operator-only physical deletion after checking live and backup references.

        Not called by the app. This deliberately requires an explicit separate
        retention decision; purging breaks snapshots that still reference the key.
        """
        if key.startswith(SEED):
            raise KeyError("Demo files are read-only.")
        _object_key(key)
        # Storage's documented batch remove endpoint also accepts a single prefix.
        self._client.json("DELETE", "/storage/v1/object/" + self.bucket, {"prefixes": [key]})
