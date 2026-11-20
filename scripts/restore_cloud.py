"""Restore a selected cloud snapshot by creating a new, version-checked revision.

Dry run by default: it reads the current project, selected historical revision
and referenced file objects without changing any record. --apply saves the old
payload as a new revision using the current revision as the CAS precondition.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import sys
from pathlib import Path
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from cloud_check import check_bucket, settings
from migrate_cloud import planned_blobs
from eir.cloud import CloudStorageError, SupabaseFileStore, SupabaseRepository
from eir.migrate import upgrade
from eir.models import Venture
from eir.serde import from_dict, to_dict


@dataclass
class RestorePlan:
    venture: Venture
    source_revision: int
    current_revision: int
    checked_objects: int


def prepare_restore(repo: SupabaseRepository, store: SupabaseFileStore, venture_id: str,
                    revision: int, expected_current: int | None = None) -> RestorePlan:
    """Read and validate a snapshot; retain the current revision on this object.

    The caller must save this exact planned object to retain its CAS precondition.
    A later read must never silently authorize overwriting another writer.
    """
    if type(revision) is not int or revision < 1:
        raise ValueError("Choose a positive historical revision.")
    current = repo.get(venture_id)  # Also validates the project identifier.
    current_revision = getattr(current, "_storage_revision", None)
    if type(current_revision) is not int or current_revision < 1:
        raise CloudStorageError("Current project version is invalid. Reload before restoring.")
    if expected_current is not None and current_revision != expected_current:
        raise CloudStorageError("The project changed since the reviewed dry run. Review a new restore plan.")
    query = urlencode({"venture_id": "eq." + venture_id, "revision": "eq." + str(revision),
                       "select": "venture_id,revision,payload", "limit": 1})
    rows = repo._client.json("GET", "/rest/v1/eir_venture_versions?" + query)
    if not isinstance(rows, list):
        raise CloudStorageError("Cloud version history returned an invalid response.")
    if not rows:
        raise ValueError("The selected historical revision does not exist for this project.")
    row = rows[0]
    if (not isinstance(row, dict) or row.get("venture_id") != venture_id or row.get("revision") != revision
            or not isinstance(row.get("payload"), dict) or row["payload"].get("id") != venture_id):
        raise ValueError("The historical snapshot does not match the selected project and revision.")
    try:
        restored = upgrade(from_dict(Venture, row["payload"]))
    except (TypeError, ValueError, AttributeError, KeyError):
        raise ValueError("The historical snapshot contains invalid project data.") from None
    if restored.id != current.id:
        raise ValueError("The historical snapshot belongs to a different project.")
    # This check reads retained private file bytes, including extracted text.
    # It also rejects cross-project references and mismatched original checksums.
    try:
        checked = len(planned_blobs(restored, store))
    except KeyError:
        raise ValueError("A file needed by this snapshot is missing. Restore its bytes before the project record.") from None
    restored._storage_revision = current_revision
    return RestorePlan(restored, revision, current_revision, checked)


def apply_restore(repo: SupabaseRepository, plan: RestorePlan) -> int:
    """Append a revision; the adapter rejects any concurrent intervening write."""
    repo.save(plan.venture)
    reloaded = repo.get(plan.venture.id)
    if to_dict(reloaded) != to_dict(plan.venture):
        raise CloudStorageError("Restore was saved but could not be verified. Inspect history before retrying.")
    return getattr(plan.venture, "_storage_revision")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--venture-id", required=True, help="The exact project identifier to restore.")
    parser.add_argument("--revision", type=int, required=True, help="The historical revision to restore.")
    parser.add_argument("--expected-current-revision", type=int,
                        help="Require the current revision printed by a reviewed dry run.")
    parser.add_argument("--secrets", type=Path, help="Local secrets TOML path, never a key in arguments.")
    parser.add_argument("--apply", action="store_true", help="Append the restored payload as a new revision.")
    args = parser.parse_args(argv)
    try:
        config = settings(args.secrets)
        repo = SupabaseRepository(config["url"], config["key"])
        store = SupabaseFileStore(config["url"], config["key"], config["bucket"])
        check_bucket(config)
        plan = prepare_restore(repo, store, args.venture_id, args.revision, args.expected_current_revision)
        print(f"PLAN: {args.venture_id}; restore revision {plan.source_revision} over current revision "
              f"{plan.current_revision}; {plan.checked_objects} file objects verified.")
        if not args.apply:
            print("Read-only dry run complete. No records changed. Repeat with --apply and "
                  f"--expected-current-revision {plan.current_revision} after reviewing this plan.")
            return 0
        new_revision = apply_restore(repo, plan)
        print(f"PASS: restored as revision {new_revision}; historical revisions remain unchanged.")
        return 0
    except (CloudStorageError, ValueError, KeyError, OSError) as error:
        message = str(error) if isinstance(error, (CloudStorageError, ValueError)) else "A project or file was missing."
        print(f"FAIL: {message}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
