"""Project files (design section 6): the documents a team shares with its mentor.

- Documents only: decks, plans, interview notes, surveys, sheets, screenshots, links. Never code.
- What a document says counts as the team's claims, not as evidence: the mentor grades it (interview notes that
  name who was asked, how many, and what they said can be rung 3).
- Every upload keeps its versions. An upload with the same name, ignoring "v2", "final", "(1)" and the like, is the
  next version of that file; an identical upload is refused.
- The mentor reads each version's summary and opens the text only when it needs detail (read in parts).
- Only team members see files. A consultant sees only the summaries of the files the lead mentor attaches.
- The mentor never edits files: a revision it suggests becomes a task linked to the file, checked against the next
  version.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import PurePath

from . import extract
from .filestore import SEED, FileStore
from .models import FileKind, FileVersion, ProjectFile, StepStatus, Venture

MAX_MB = 10
MAX_BYTES = MAX_MB * 1024 * 1024
PART_CHARS = 8_000  # what the mentor reads at a time
KINDS = {".pdf": FileKind.PDF, ".docx": FileKind.WORD, ".pptx": FileKind.SLIDES, ".xlsx": FileKind.SHEET,
         ".csv": FileKind.CSV, ".txt": FileKind.TEXT, ".md": FileKind.TEXT, ".png": FileKind.IMAGE,
         ".jpg": FileKind.IMAGE, ".jpeg": FileKind.IMAGE, ".gif": FileKind.IMAGE, ".webp": FileKind.IMAGE}
ACCEPTED = tuple(ext.lstrip(".") for ext in KINDS)  # for the upload control
CODE = {".py", ".ipynb", ".js", ".jsx", ".ts", ".tsx", ".java", ".kt", ".swift", ".c", ".h", ".cpp", ".cs", ".go",
        ".rb", ".php", ".rs", ".r", ".m", ".sql", ".sh", ".ps1", ".bat", ".html", ".css", ".json", ".yaml", ".yml",
        ".zip", ".7z", ".rar", ".exe", ".dll"}
LABELS = {FileKind.PDF: "PDF", FileKind.WORD: "Word", FileKind.SLIDES: "Slides", FileKind.SHEET: "Spreadsheet",
          FileKind.CSV: "CSV", FileKind.TEXT: "Text", FileKind.IMAGE: "Image", FileKind.LINK: "Link"}
_VERSION_WORDS = re.compile(r"(?:^|\s)(?:v\s?\d+|version\s?\d+|final|draft|new|latest|copy|updated|rev\s?\d*|\d+)$")


def kind_of(name: str) -> FileKind:
    ext = PurePath(name).suffix.lower()
    if ext in CODE:
        raise ValueError("Code and archives are not collected in this version. Share documents instead, and describe "
                         "what the code does in the chat.")
    if ext not in KINDS:
        raise ValueError(f"This file type is not supported. Share {', '.join(ACCEPTED)} files.")
    return KINDS[ext]


def base_name(name: str) -> str:
    """The name without extension, case, separators and version words: "Pitch_Deck v2 (1).pdf" -> "pitch deck"."""
    stem = re.sub(r"\(\d+\)", " ", PurePath(name).stem.lower())
    stem = re.sub(r"[^a-z0-9]+", " ", stem).strip()
    while (shorter := _VERSION_WORDS.sub("", stem).strip()) != stem and shorter:
        stem = shorter
    return stem


def same_file(v: Venture, name: str, kind: FileKind) -> ProjectFile | None:
    """An earlier file this upload is a new version of."""
    key = base_name(name)
    return next((f for f in v.files if f.kind == kind and f.kind != FileKind.LINK and base_name(f.name) == key), None)


def add_version(v: Venture, store: FileStore, name: str, data: bytes, by: str,
                note: str = "") -> tuple[ProjectFile, FileVersion, str]:
    """Store an upload as a new file or as the next version of an existing one, with its extracted text.
    Returns the file, the version and the text ("" when it cannot be read; the version records that as 0 chars)."""
    name = PurePath(name.strip()).name
    if not name:
        raise ValueError("The file has no name")
    kind = kind_of(name)
    if not data:
        raise ValueError("The file is empty")
    if len(data) > MAX_BYTES:
        raise ValueError(f"Files can be up to {MAX_MB} MB")
    digest = hashlib.sha256(data).hexdigest()
    f = same_file(v, name, kind)
    if f is not None and f.latest is not None and f.latest.sha256 == digest:
        raise ValueError(f"This is the same as version {f.latest.number} of {f.name}.")
    try:
        text = extract.text_of(kind, data)
    except extract.ExtractError:
        text = ""
    if f is None:
        f = ProjectFile(name=name, kind=kind, created_by=by)
        v.files.append(f)
    number = len(f.versions) + 1
    blob = f"{v.id}/{f.id}/v{number}{PurePath(name).suffix.lower()}"
    store.put(blob, data)
    store.put(blob + ".txt", text.encode("utf-8"))
    version = FileVersion(number, by, size=len(data), sha256=digest, blob=blob, chars=len(text), note=note.strip())
    f.name = name
    f.versions.append(version)
    return f, version, text


def add_link(v: Venture, url: str, description: str, by: str) -> ProjectFile:
    url, description = url.strip(), " ".join(description.split())
    if not re.match(r"https?://\S+$", url):
        raise ValueError("Enter a full link, starting with http:// or https://")
    if not description:
        raise ValueError("Say in a few words what the link shows")
    f = ProjectFile(name=url, kind=FileKind.LINK, url=url, created_by=by,
                    versions=[FileVersion(1, by, summary=description, note=description)])
    v.files.append(f)
    return f


def text(store: FileStore, f: ProjectFile, version: FileVersion) -> str:
    """A version's extracted text ("" when there is none)."""
    if not f.kind.readable or not version.blob:
        return ""
    try:
        return store.get(version.blob + ".txt").decode("utf-8")
    except KeyError:
        if version.blob.startswith(SEED):  # demo files are read straight from the seed folder
            try:
                return extract.text_of(f.kind, store.get(version.blob))
            except (KeyError, extract.ExtractError):
                return ""
        return ""


def read(store: FileStore, f: ProjectFile, number: int = 0, part: int = 1) -> str:
    """One part of a version's text (the latest version by default), for the mentor's read_file action."""
    version = f.version(number) if number else f.latest
    if version is None:
        raise ValueError(f"{f.name} has no version {number}")
    if not f.kind.readable:
        return f"{f.name} is {LABELS[f.kind].lower()}: it cannot be read in this version. What the team says: " \
               f"{version.summary or '(nothing)'}"
    body = text(store, f, version)
    if not body:
        return f"{f.name} version {version.number} has no readable text."
    parts = max(1, -(-len(body) // PART_CHARS))
    part = min(max(1, int(part)), parts)
    chunk = body[(part - 1) * PART_CHARS:part * PART_CHARS]
    return f"{f.name}, version {version.number}, part {part} of {parts}:\n{chunk}"


UNREAD = "Document excerpt (not reviewed): "  # starts the summary of a version the Virtual EIR has not read yet
NO_TEXT = "Uploaded project file; no text could be extracted."


def saved_summary(text: str, note: str = "") -> str:
    """The summary of a version saved on the Overview, until the Virtual EIR reads it: the start of its text, marked
    as not reviewed (or the team's note when there is no text)."""
    excerpt = " ".join(text.split())[:600]
    return f"{UNREAD}{excerpt}" if excerpt else note.strip() or NO_TEXT


def read_by_eir(f: ProjectFile, version: FileVersion) -> bool:
    """Whether the version's summary was written by the Virtual EIR when it read the file (not an excerpt, the
    team's note, or a link's description in the team's words)."""
    s = version.summary
    return bool(s) and f.kind != FileKind.LINK and not s.startswith(UNREAD) and s not in (NO_TEXT, version.note)


def discussion(v: Venture, f: ProjectFile):
    """The team message that gave the latest version of this file to the Virtual EIR, if any (None: saved on the
    Overview but not discussed yet). Read from the chat, so nothing extra is stored."""
    latest = f.latest
    if latest is None:
        return None
    return next((m for m in reversed(v.conversation) if m.file_id == f.id and m.file_version == latest.number), None)


def revision_tasks(v: Venture, f: ProjectFile, open_only: bool = True) -> list:
    return [s for s in v.next_steps if s.file_id == f.id and (s.status == StepStatus.OPEN or not open_only)]


def delete(v: Venture, store: FileStore, file_id: str) -> ProjectFile:
    """Remove a file and every version (e.g. a technical document uploaded by mistake). Its revision tasks stay."""
    f = v.file(file_id)
    if f is None:
        raise ValueError("This file does not exist")
    for version in f.versions:
        if version.blob:
            store.delete(version.blob)
            store.delete(version.blob + ".txt")
    v.files = [x for x in v.files if x.id != file_id]
    for s in v.next_steps:
        if s.file_id == file_id:
            s.file_id = ""
    return f
