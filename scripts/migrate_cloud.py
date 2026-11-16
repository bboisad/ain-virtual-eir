"""Copy explicitly selected local projects into Supabase without overwriting projects.

Default is a dry run. Choose --seed-demo or --source-dir, inspect the plan, then
repeat with --apply. Uploaded originals and extracted text are checksum-verified.
No conventional user-data directory is read unless explicitly supplied.
"""
from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from cloud_check import check_bucket, settings
from eir.cloud import CloudStorageError, StorageConflict, SupabaseFileStore, SupabaseRepository
from eir.filestore import LocalFileStore, SEED
from eir.models import Venture
from eir.repository import JsonFileRepository
from eir.seed import demo_ventures
from eir.serde import to_dict


def planned_blobs(venture: Venture, source: LocalFileStore) -> list[tuple[str, bytes]]:
    """Load only blobs referenced by this project's file-version records."""
    blobs: dict[str, bytes] = {}
    for project_file in venture.files:
        for version in project_file.versions:
            key = version.blob
            if not key:
                continue
            if key.startswith(SEED):
                # Bundled demo documents remain read-only seed references on every deployment.
                source.get(key)
                continue
            if not key.startswith(venture.id + "/"):
                raise ValueError("A file reference does not belong to its project.")
            original = source.get(key)
            digest = hashlib.sha256(original).hexdigest()
            if version.sha256 and digest != version.sha256:
                raise ValueError("A local file does not match its recorded checksum.")
            blobs[key] = original
            try:
                text = source.get(key + ".txt")
            except KeyError:
                if version.chars:
                    raise ValueError("Extracted text is missing for a readable local file.") from None
            else:
                blobs[key + ".txt"] = text
    return list(blobs.items())


def copy_verified(store: SupabaseFileStore, key: str, data: bytes) -> None:
    """Reuse an identical prior upload; reject a different object at the same key."""
    expected = hashlib.sha256(data).digest()
    try:
        previous = store.get(key)
    except KeyError:
        store.put(key, data)
    else:
        if hashlib.sha256(previous).digest() != expected:
            raise ValueError("A cloud object at this file key has different content; no overwrite was performed.")
    if hashlib.sha256(store.get(key)).digest() != expected:
        raise CloudStorageError("A cloud file failed checksum verification.")


def migrate(ventures: list[Venture], source: LocalFileStore, repo: SupabaseRepository,
            store: SupabaseFileStore) -> tuple[int, int]:
    copied = skipped = 0
    for venture in ventures:
        try:
            repo.get(venture.id)
        except KeyError:
            pass
        else:
            skipped += 1
            print(f"SKIP: {venture.id} already exists; existing records and files are unchanged.")
            continue
        # A failed file transfer leaves no project record pointing at incomplete files.
        # Identical objects from an interrupted run can be reused on the next attempt.
        blobs = planned_blobs(venture, source)
        for key, data in blobs:
            copy_verified(store, key, data)
        try:
            repo.save(venture)
        except StorageConflict:
            skipped += 1
            print(f"SKIP: {venture.id} was created concurrently; its project record was not overwritten.")
            continue
        if to_dict(repo.get(venture.id)) != to_dict(venture):
            raise CloudStorageError("A migrated project failed reload verification.")
        copied += 1
        print(f"PASS: {venture.id}; project payload and {len(blobs)} cloud objects verified.")
    return copied, skipped


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--seed-demo", action="store_true", help="Use only the bundled fictional demo ventures.")
    selection.add_argument("--source-dir", type=Path, help="Explicit local directory containing venture JSON files.")
    parser.add_argument("--files-dir", type=Path, help="Explicit upload directory; required with --source-dir.")
    parser.add_argument("--secrets", type=Path, help="Local secrets TOML path; credentials never belong in command arguments.")
    parser.add_argument("--apply", action="store_true", help="Perform cloud writes after reviewing the default dry run.")
    args = parser.parse_args(argv)
    if args.source_dir and not args.files_dir:
        parser.error("--source-dir requires --files-dir; no implicit user-data path is used.")
    if args.seed_demo and args.files_dir:
        parser.error("--files-dir is only used with --source-dir.")
    try:
        if args.seed_demo:
            ventures, source = demo_ventures(), LocalFileStore(ROOT / ".unused-seed-files")
        else:
            if not args.source_dir.is_dir() or not args.files_dir.is_dir():
                raise ValueError("The explicit source and upload directories must already exist.")
            ventures, source = JsonFileRepository(args.source_dir).list(), LocalFileStore(args.files_dir)
        for venture in ventures:
            blobs = planned_blobs(venture, source)
            print(f"PLAN: {venture.id}; {len(blobs)} referenced objects; {sum(len(data) for _, data in blobs)} bytes.")
        if not args.apply:
            print("Dry run complete; no cloud connection or writes were made. Repeat with --apply to migrate.")
            return 0
        config = settings(args.secrets)
        repo = SupabaseRepository(config["url"], config["key"])
        store = SupabaseFileStore(config["url"], config["key"], config["bucket"])
        check_bucket(config)
        copied, skipped = migrate(ventures, source, repo, store)
        print(f"Migration complete: {copied} copied, {skipped} skipped. No existing projects were overwritten.")
        return 0
    except (CloudStorageError, ValueError, KeyError, OSError):
        print("FAIL: migration stopped. Check source integrity, cloud configuration and permissions; existing project records were not overwritten.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
