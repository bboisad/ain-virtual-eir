"""Project files (design section 6): documents only, read on this computer, kept in versions; what a document says is
a claim, not evidence; the mentor reads summaries, opens text only when needed, suggests revisions as tasks and checks
them in the next version; consultants see only what the mentor attaches."""
import io
import zipfile

import pytest

from eir import access, actions, changes, extract, files, memory
from eir.coach.ai import AICoach
from eir.coach.scripted import ScriptedCoach
from eir.filestore import MemoryFileStore
from eir.models import EIR, FileKind, Message, StepStatus
from eir.seed import demo_ventures

NOTES = ("# Pricing survey\nWe asked 40 students at the dining hall.\n"
         "- 28 of 40 said they would pay $3 to sell a mini-fridge.\n- 9 of 40 had already sold furniture online.\n"
         "Students love the idea.").encode()


def venture(vid="V-CAMPUS"):
    return next(v for v in demo_ventures() if v.id == vid)


def docx(*paragraphs: str) -> bytes:
    w = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    body = "".join(f"<w:p><w:r><w:t>{p[:5]}</w:t></w:r><w:r><w:t xml:space='preserve'>{p[5:]}</w:t></w:r></w:p>"
                   for p in paragraphs)
    return _zip({"word/document.xml": f"<w:document xmlns:w='{w}'><w:body>{body}</w:body></w:document>"})


def pptx(*slides: str) -> bytes:
    a, p = ("http://schemas.openxmlformats.org/drawingml/2006/main",
            "http://schemas.openxmlformats.org/presentationml/2006/main")
    return _zip({f"ppt/slides/slide{i}.xml": f"<p:sld xmlns:a='{a}' xmlns:p='{p}'><p:cSld><p:spTree><p:sp><p:txBody>"
                 f"<a:p><a:r><a:t>{text}</a:t></a:r></a:p></p:txBody></p:sp></p:spTree></p:cSld></p:sld>"
                 for i, text in enumerate(slides, 1)})


def _zip(parts: dict[str, str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name, xml in parts.items():
            z.writestr(name, xml)
    return buf.getvalue()


def xlsx() -> bytes:
    from openpyxl import Workbook
    book = Workbook()
    book.active.title = "Fees"
    book.active.append(["Item", "Price", "Sold"])
    book.active.append(["Mini-fridge", 15, 3])
    buf = io.BytesIO()
    book.save(buf)
    return buf.getvalue()


def pdf(text: str) -> bytes:
    stream = f"BT /F1 18 Tf 20 100 Td ({text}) Tj ET".encode()
    objs = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 400 144] /Contents 4 0 R /Resources << /Font << /F1 5 0 R "
            b">> >> >>", b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    out, offsets = b"%PDF-1.4\n", []
    for i, body in enumerate(objs, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % i + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1) + b"".join(b"%010d 00000 n \n" % o for o in offsets)
    return out + b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, xref)


# ---- reading documents on this computer ----
def test_documents_are_read_page_by_page_slide_by_slide_and_sheet_by_sheet():
    assert extract.text_of(FileKind.WORD, docx("Hello world", "Second line")) == "Hello world\nSecond line"
    slides = extract.text_of(FileKind.SLIDES, pptx(*[f"Slide text {i}" for i in range(1, 11)]))
    assert slides.startswith("[slide 1]\nSlide text 1") and slides.endswith("[slide 10]\nSlide text 10")
    assert "Mini-fridge\t15\t3" in extract.text_of(FileKind.SHEET, xlsx())
    assert extract.text_of(FileKind.PDF, pdf("28 of 40 would pay")) == "[page 1]\n28 of 40 would pay"
    assert extract.text_of(FileKind.CSV, b"\xef\xbb\xbfitem,price\nfridge,15") == "item,price\nfridge,15"
    assert extract.text_of(FileKind.IMAGE, b"\x89PNG....") == ""
    with pytest.raises(extract.ExtractError):
        extract.text_of(FileKind.WORD, b"not a zip file")


def test_documents_only_and_versions_by_name():
    with pytest.raises(ValueError, match="Code"):
        files.kind_of("pricing_model.py")
    with pytest.raises(ValueError, match="not supported"):
        files.kind_of("movie.mov")
    assert files.base_name("Pitch_Deck v2 (1).pdf") == files.base_name("pitch deck.pdf") == "pitch deck"
    assert files.base_name("Deck-FINAL.pptx") == "deck" and files.base_name("2025 plan.docx") == "2025 plan"
    v, store = venture(), MemoryFileStore()
    f, v1, _ = files.add_version(v, store, "Pitch deck.pdf", pdf("Version one"), "m1")
    same, v2, text = files.add_version(v, store, "Pitch_Deck v2.pdf", pdf("Version two"), "m2")
    assert same is f and (v1.number, v2.number) == (1, 2) and f.name == "Pitch_Deck v2.pdf" and "two" in text
    with pytest.raises(ValueError, match="same as version 2"):
        files.add_version(v, store, "pitch deck.pdf", pdf("Version two"), "m1")
    with pytest.raises(ValueError):
        files.add_version(v, store, "Empty.txt", b"", "m1")
    with pytest.raises(ValueError, match="10 MB"):
        files.add_version(v, store, "Huge.txt", b"x" * (files.MAX_BYTES + 1), "m1")
    other, _, _ = files.add_version(v, store, "Pitch deck.pptx", pptx("Slides"), "m1")
    assert other is not f  # a different kind is a different file
    assert store.get(v2.blob) == pdf("Version two") and f.versions[0].blob.endswith(f"{f.id}/v1.pdf")


# ---- sharing a file with the mentor ----
def test_an_upload_is_summarized_and_the_mentor_treats_its_claims_as_claims():
    v, store, coach = venture(), MemoryFileStore(), ScriptedCoach()
    reply = actions.upload_file(v, coach, store, "m1", "Pricing survey.md", NOTES, "Our survey results")
    f = v.files[-1]
    member = v.conversation[-2]
    assert (member.author, member.text, member.file_id, member.file_version) == ("m1", "Our survey results", f.id, 1)
    version = f.latest
    assert version.chars and version.summary and "28 of 40 said they would pay $3" in version.claims[0]
    assert reply.author == EIR and "claim, not evidence" in reply.text and len(reply.change_groups) == 2
    h = v.hypotheses[-1]
    assert h.statement.startswith("28 of 40") and h.rung == 1  # a document is a claim until the mentor grades it
    revision = files.revision_tasks(v, f)[0]
    assert revision.file_id == f.id and revision.text.startswith("Revise Pricing survey.md")
    changes.undo_group(v, reply.change_groups[1], "m1")  # each update can be undone
    assert files.revision_tasks(v, f) == []


def test_a_new_version_is_checked_against_the_open_revisions():
    v, store, coach = venture(), MemoryFileStore(), ScriptedCoach()
    actions.upload_file(v, coach, store, "m1", "Pricing survey.md", NOTES)
    f = v.files[-1]
    reply = actions.upload_file(v, coach, store, "m2", "pricing survey v2.md", NOTES + b"\n28 names are in the sheet.")
    assert f.latest.number == 2 and v.conversation[-2].text == f"Here is a new version of {f.name}."
    assert "Revise Pricing survey.md" in reply.text and "Which of these did this version address" in reply.text
    messages, _ = memory.window(v)
    assert "a new version of an earlier file" in messages[-2]["content"]  # the member's upload, before the reply
    context = memory.lead_context(v)
    assert "PROJECT FILES" in context and "Previous version's summary" in context and "Open revision tasks" in context


def test_the_ai_summary_compares_versions_withholds_ip_details_and_never_blocks_an_upload():
    class FakeLLM:
        class cfg:
            model_name = "fake-model"

        def __init__(self, fail=False):
            self.fail, self.prompts = fail, []

        def chat_json(self, system, prompt):
            self.prompts.append(prompt)
            if self.fail:
                raise RuntimeError("timeout")
            return {"summary": "A survey of 40 students.", "claims": ["28 of 40 would pay (40 interviews: said)"]}

    luma, store = venture("V-LUMA"), MemoryFileStore()
    llm = FakeLLM()
    f, v1, text = files.add_version(luma, store, "Survey.md", NOTES, "m1")
    s = AICoach(llm).summarize_file(luma, f, v1, text)
    assert s.summary == "A survey of 40 students." and s.claims == ["28 of 40 would pay (40 interviews: said)"]
    assert "IP-SENSITIVE" in llm.prompts[0]
    v1.summary = s.summary
    f, v2, text = files.add_version(luma, store, "Survey v2.md", NOTES + b" More.", "m1")
    AICoach(llm).summarize_file(luma, f, v2, text, previous=v1)
    assert "Previous version's summary: A survey of 40 students." in llm.prompts[1]
    fallback = AICoach(FakeLLM(fail=True)).summarize_file(luma, f, v2, text, previous=v1)
    assert fallback.summary.startswith("Version 2.") and "without AI" in fallback.summary


def test_the_mentor_sees_attachments_and_consultants_see_only_attached_files():
    v, store = venture(), MemoryFileStore()
    actions.upload_file(v, ScriptedCoach(), store, "m1", "Pricing survey.md", NOTES)
    survey = v.files[-1]
    messages, _ = memory.window(v)
    assert f"(attached: {survey.id} \"Pricing survey.md\", text, version 1" in messages[-2]["content"]
    c = actions.invite_consultant(v, "pricing", "Is $3 supported?", "Brief", EIR, file_ids=(survey.id,))
    view = access.consultant_view(v, c)
    assert "FILES THE MENTOR ATTACHED" in view and "Pricing survey.md" in view
    assert "Move-out interview notes.md" not in view  # the demo file was not attached
    assert "Pricing survey.md" not in access.consultant_view(v, actions.invite_consultant(v, "strategy", "Who else?",
                                                                                          "Brief", EIR))


def test_removing_a_file_deletes_every_version_and_keeps_the_tasks():
    v, store = venture(), MemoryFileStore()
    actions.upload_file(v, ScriptedCoach(), store, "m1", "Pricing survey.md", NOTES)
    f = v.files[-1]
    blob = f.latest.blob
    with pytest.raises(PermissionError):
        actions.delete_file(v, store, "outsider", f.id)
    actions.delete_file(v, store, "m1", f.id)
    assert v.file(f.id) is None and v.timeline[-1].text == "File removed: Pricing survey.md"
    with pytest.raises(KeyError):
        store.get(blob)
    assert v.next_steps[-1].text.startswith("Revise Pricing survey.md") and not v.next_steps[-1].file_id
    assert memory.attachment(v, v.conversation[-2]) == ""


def test_links_and_images_are_listed_but_never_read():
    v, store = venture(), MemoryFileStore()
    with pytest.raises(ValueError):
        actions.add_link(v, "m1", "campusloop.example", "our landing page")
    link = actions.add_link(v, "m1", "https://campusloop.example", "Our landing page with the waitlist form")
    assert link.kind == FileKind.LINK and "waitlist form" in files.read(store, link)
    reply = actions.upload_file(v, ScriptedCoach(), store, "m2", "Table photo.png", b"\x89PNG fake image", "Our table")
    assert "can't read Table photo.png" in reply.text and v.files[-1].latest.chars == 0


def test_the_demo_file_is_readable_and_a_failed_reply_keeps_the_upload():
    v, store = venture(), MemoryFileStore()
    notes = v.file("F-notes")
    assert "2 of 3 would only use the service if it is free" in files.text(store, notes, notes.latest)

    class Down(ScriptedCoach):
        def lead_turn(self, *args, **kwargs):
            raise RuntimeError("the endpoint timed out")

    with pytest.raises(RuntimeError):
        actions.upload_file(v, Down(), store, "m1", "Pricing survey.md", NOTES)
    assert v.files[-1].name == "Pricing survey.md" and v.conversation[-1].file_id == v.files[-1].id
    assert actions.awaiting_reply(v)
    reply = actions.retry_reply(v, ScriptedCoach(), "m1", files=store)
    assert "Pricing survey.md" in reply.text and not actions.awaiting_reply(v)


def test_staff_never_see_project_files():
    from eir.repository import InMemoryRepository
    entry = access.staff_directory(access.Account("roberto", "AIN staff", access.Role.STAFF),
                                   InMemoryRepository([venture()]))[0]
    assert "file" not in " ".join(vars(entry)).lower()
    assert "Move-out interview notes" not in str(vars(entry))


def test_a_completed_revision_is_still_listed_as_done():
    v, store = venture(), MemoryFileStore()
    actions.upload_file(v, ScriptedCoach(), store, "m1", "Pricing survey.md", NOTES)
    f = v.files[-1]
    task = files.revision_tasks(v, f)[0]
    actions.complete_step(v, task.id, "m1", "Added the names sheet")
    assert files.revision_tasks(v, f) == [] and files.revision_tasks(v, f, open_only=False)[0].status == StepStatus.DONE
    assert isinstance(v.conversation[0], Message)


# ---- the Overview's project files: save first, discuss with the Virtual EIR when the team chooses ----
def test_saving_a_file_on_the_overview_needs_no_coaching_turn_and_changes_no_evidence():
    v, store = venture(), MemoryFileStore()
    before = (len(v.conversation), len(v.changes), [h.rung for h in v.hypotheses], len(v.next_steps))
    f = actions.save_file(v, store, "m1", "Pricing survey.md", NOTES)
    assert (len(v.conversation), len(v.changes), [h.rung for h in v.hypotheses], len(v.next_steps)) == before
    assert f.latest.summary.startswith("Document excerpt (not reviewed): # Pricing survey We asked 40 students")
    assert f.latest.claims == [] and files.discussion(v, f) is None
    assert files.text(store, f, f.latest).startswith("# Pricing survey")
    with pytest.raises(PermissionError):
        actions.save_file(v, store, "outsider", "Notes.md", b"x")
    with pytest.raises(ValueError, match="Code"):
        actions.save_file(v, store, "m1", "model.py", b"print(1)")


def test_discussing_a_saved_file_hands_it_to_the_virtual_eir():
    v, store, coach = venture(), MemoryFileStore(), ScriptedCoach()
    f = actions.save_file(v, store, "m1", "Pricing survey.md", NOTES)
    reply = actions.discuss_file(v, coach, store, "m1", f.id, "Is our pricing convincing?")
    shared = v.conversation[-2]
    assert (shared.author, shared.text, shared.file_id, shared.file_version) == ("m1", "Is our pricing convincing?",
                                                                                  f.id, 1)
    assert reply.author == EIR and reply.change_groups and files.discussion(v, f) is shared
    assert not f.latest.summary.startswith("Document excerpt") and f.latest.claims  # summarized when discussed
    f2 = actions.save_file(v, store, "m2", "Pricing survey v2.md", NOTES + b"\n- 12 of 40 prepaid.")
    assert f2 is f and f.latest.number == 2 and files.discussion(v, f) is None  # the new version is not discussed yet
    actions.discuss_file(v, coach, store, "m2", f.id)
    assert v.conversation[-2].text == "Here is a new version of Pricing survey v2.md."
    actions.delete_file(v, store, "m1", f.id)
    with pytest.raises(ValueError, match="no longer available"):
        actions.discuss_file(v, coach, store, "m1", f.id)


def test_a_failed_reply_keeps_the_discussed_file_in_the_chat():
    class Down(ScriptedCoach):
        def lead_turn(self, v, box, event=None):
            raise RuntimeError("the endpoint timed out")

    v, store = venture(), MemoryFileStore()
    f = actions.save_file(v, store, "m1", "Pricing survey.md", NOTES)
    with pytest.raises(RuntimeError):
        actions.discuss_file(v, Down(), store, "m1", f.id)
    assert files.discussion(v, f) is v.conversation[-1] and actions.awaiting_reply(v)
    assert actions.retry_reply(v, ScriptedCoach(), "m1", files=store).author == EIR
