"""Uploads remain consistent when object writes and project CAS are interrupted."""
from urllib.error import URLError

import pytest

from eir import files
from eir.cloud import CloudStorageError, StorageConflict
from eir.filestore import MemoryFileStore
from eir.seed import demo_ventures
from eir.serde import to_dict

from test_cloud import Backend, repo, store


class InterruptUpload(Backend):
    def __init__(self, fail_put):
        super().__init__()
        self.fail_put = fail_put
        self.puts = 0

    def open(self, request, timeout):
        if request.method == "POST" and "/storage/v1/object/" in request.full_url:
            self.puts += 1
            if self.puts == self.fail_put:
                raise URLError("simulated interrupted upload")
        return super().open(request, timeout)


def blank():
    venture = demo_ventures()[0]
    venture.files = []
    return venture


@pytest.mark.parametrize("fail_put", [1, 2])
def test_failed_new_upload_never_leaves_empty_file_metadata(fail_put):
    backend, venture = InterruptUpload(fail_put), blank()
    with pytest.raises(CloudStorageError):
        files.add_version(venture, store(backend), "New notes.md", b"Team interview notes", "m1")
    assert venture.files == []
    # A chat handler may still save its message after catching an upload error.
    repo(backend).save(venture)
    assert repo(backend).get(venture.id).files == []


@pytest.mark.parametrize("fail_put", [3, 4])
def test_failed_next_upload_keeps_previous_name_and_version(fail_put):
    backend, venture = InterruptUpload(fail_put), blank()
    file, original, _ = files.add_version(venture, store(backend), "Plan.md", b"Initial notes", "m1")
    before = to_dict(file)
    with pytest.raises(CloudStorageError):
        files.add_version(venture, store(backend), "Plan v2.md", b"Revised notes", "m1")
    assert to_dict(file) == before
    assert file.latest is original
    assert store(backend).get(original.blob) == b"Initial notes"


def test_orphan_upload_from_failed_project_cas_does_not_block_visible_version_retry():
    backend, venture = Backend(), blank()
    writer, objects = repo(backend), store(backend)
    files.add_version(venture, objects, "Plan.md", b"Initial plan", "m1")
    writer.save(venture)
    stale, other = writer.get(venture.id), writer.get(venture.id)
    _, orphan, _ = files.add_version(stale, objects, "Plan v2.md", b"Uncommitted update", "m1")
    other.description = "A teammate changed another field"
    writer.save(other)
    with pytest.raises(StorageConflict):
        writer.save(stale)
    fresh = writer.get(venture.id)
    assert fresh.files[0].latest.number == 1
    file, retried, _ = files.add_version(fresh, objects, "Plan v2.md", b"New intended update", "m1")
    writer.save(fresh)
    assert retried.number == orphan.number == 2
    assert retried.blob != orphan.blob
    assert [v.number for v in file.versions] == [1, 2]
    assert objects.get(orphan.blob) == b"Uncommitted update"
    assert objects.get(retried.blob) == b"New intended update"
    assert writer.get(venture.id).files[0].latest.blob == retried.blob


def test_old_sequential_paths_stay_readable_while_new_cloud_paths_are_unique():
    backend, venture = Backend(), blank()
    local = MemoryFileStore()
    file, old, _ = files.add_version(venture, local, "Plan.md", b"Old stored plan", "m1")
    assert old.blob.endswith("/v1.md")
    cloud = store(backend)
    cloud.put(old.blob, local.get(old.blob))
    cloud.put(old.blob + ".txt", local.get(old.blob + ".txt"))
    _, new, _ = files.add_version(venture, cloud, "Plan v2.md", b"New cloud plan", "m1")
    assert "/v2-" in new.blob and new.blob.endswith(".md")
    assert files.read(cloud, file, number=1).endswith("Old stored plan")
    assert files.read(cloud, file, number=2).endswith("New cloud plan")
