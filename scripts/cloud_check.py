"""Check the deployed database and private file bucket without printing secrets.

Read-only by default. --write-test explicitly creates a uniquely named fictional
venture and exercises persistence, stale-write detection and file round trips.
That venture's version snapshots remain for inspection; the temporary file is deleted.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tomllib
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import HTTPRedirectHandler, Request, build_opener
from uuid import uuid4

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from eir.cloud import CloudStorageError, StorageConflict, SupabaseFileStore, SupabaseRepository
from eir.seed import demo_ventures
from eir.serde import to_dict


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Never forward the backend key to a redirected origin.
        return None


def settings(path: Path | None = None) -> dict[str, str]:
    """Read secrets before environment variables, matching the Streamlit app.

    Credentials are never included in returned error messages or console output.
    A named file must exist; absent conventional files are normal.
    """
    files = [path] if path else [ROOT / ".streamlit" / "secrets.toml", Path.home() / ".streamlit" / "secrets.toml"]
    values: dict[str, str] = {}
    for candidate in files:
        if candidate is None or (not candidate.is_file() and path is None):
            continue
        try:
            with candidate.open("rb") as handle:
                raw = tomllib.load(handle)
        except (OSError, tomllib.TOMLDecodeError):
            raise ValueError("Could not read the local secrets file. Check its path and TOML syntax.") from None
        for name, value in raw.items():
            if isinstance(value, (str, int, float, bool)):
                values.setdefault(name, str(value))
    names = ("SUPABASE_URL", "SUPABASE_SECRET_KEY", "SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_BUCKET")
    for name in names:
        if name not in values and os.environ.get(name):
            values[name] = os.environ[name]
    url = values.get("SUPABASE_URL", "").strip()
    key = values.get("SUPABASE_SECRET_KEY") or values.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not key or key.strip() == "...":
        raise ValueError("Configure SUPABASE_URL and SUPABASE_SECRET_KEY in environment variables or local secrets.")
    return {"url": url.rstrip("/"), "key": key.strip(), "bucket": values.get("SUPABASE_BUCKET") or "eir-files"}


def check_bucket(config: dict[str, str]) -> None:
    """Inspect bucket configuration; never accept a public project-files bucket."""
    headers = {"apikey": config["key"], "Accept": "application/json"}
    if not config["key"].startswith("sb_secret_"):
        headers["Authorization"] = f"Bearer {config['key']}"
    request = Request(f"{config['url']}/storage/v1/bucket/{quote(config['bucket'], safe='')}", headers=headers)
    try:
        with build_opener(_NoRedirect()).open(request, timeout=20) as response:
            bucket = json.load(response)
    except HTTPError as error:
        raise CloudStorageError(f"Could not inspect the file bucket (HTTP {error.code}). Check the bucket and backend key.") from None
    except (URLError, TimeoutError, OSError, ValueError):
        raise CloudStorageError("Could not inspect the file bucket. Check the network and Supabase configuration.") from None
    if not isinstance(bucket, dict) or bucket.get("id") != config["bucket"]:
        raise CloudStorageError("The file bucket returned unexpected metadata.")
    if bucket.get("public") is not False:
        raise CloudStorageError("The project-files bucket must be private.")


def write_test(repo: SupabaseRepository, store: SupabaseFileStore) -> str:
    token = uuid4().hex[:12]
    venture = demo_ventures()[0]
    venture.id = f"V-CLOUDCHECK-{token}"
    venture.name = f"Cloud validation {token} (fictional)"
    venture.files = []
    venture.description = "Disposable fictional project created by cloud_check.py --write-test."
    repo.save(venture)
    first, stale = repo.get(venture.id), repo.get(venture.id)
    if to_dict(first) != to_dict(venture):
        raise CloudStorageError("Saved project did not match the reloaded data.")
    first.description = "Cloud persistence verified; this project is only a validation fixture."
    repo.save(first)
    try:
        stale.description = "This stale update must be rejected."
        repo.save(stale)
    except StorageConflict:
        pass
    else:
        raise CloudStorageError("Stale-write test failed: concurrent data could be overwritten.")
    key, data = f"{venture.id}/cloud-check/v1.txt", f"Fictional cloud check {token}".encode()
    created = False
    try:
        store.put(key, data)
        created = True
        if hashlib.sha256(store.get(key)).digest() != hashlib.sha256(data).digest():
            raise CloudStorageError("The file round-trip checksum did not match.")
    finally:
        if created:
            # This unique object is not referenced by project metadata or snapshots.
            store.purge(key)
    return venture.id


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--secrets", type=Path, help="Local secrets TOML path; never pass a key as a command argument.")
    parser.add_argument("--write-test", action="store_true", help="Create a fictional validation project (retained), test stale writes and file storage.")
    args = parser.parse_args(argv)
    try:
        config = settings(args.secrets)
        repo = SupabaseRepository(config["url"], config["key"])
        store = SupabaseFileStore(config["url"], config["key"], config["bucket"])
        count = len(repo.list())
        check_bucket(config)
        print(f"PASS: database reachable ({count} projects); project-files bucket is private.")
        if args.write_test:
            venture_id = write_test(repo, store)
            print(f"PASS: project persistence, stale-write rejection and file checksum. Retained validation project: {venture_id}")
        else:
            print("Read-only check complete. Writes and optimistic locking have not been exercised.")
        return 0
    except (CloudStorageError, ValueError, KeyError) as error:
        # Provider response bodies and exception strings can contain private data.
        message = str(error) if isinstance(error, (CloudStorageError, ValueError)) else "A validation object was missing."
        print(f"FAIL: {message}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
