"""Real-model check of project files on the fictional demo venture Campus Loop (in memory; nothing is saved).

Run from virtual_eir/:  python scripts/smoke_files.py
Alice attaches a short pitch deck in the chat (a .pptx built here, fictional content); the Virtual EIR summarizes it,
records its key claims and suggests revisions as tasks. Then she saves version 2, which fixes one weak claim, on the
Overview (no model call) and asks to discuss it; the Virtual EIR compares the versions and ticks off what was fixed.
Prints every step. Uses the app's settings (scripts/smoke_llm.py).
"""
from __future__ import annotations

import io
import sys
import time
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from eir import actions, changes, files  # noqa: E402
from eir.coach import make_coach  # noqa: E402
from eir.filestore import MemoryFileStore  # noqa: E402
from eir.seed import demo_ventures  # noqa: E402
from smoke_llm import settings  # noqa: E402

V1 = ["Campus Loop: sell your dorm stuff without carrying it home",
      "Problem: every May, students leave furniture and fridges in hallways",
      "Customers love it: everyone we talked to said they would use it",
      "Business model: sellers pay $3 per item listed",
      "Market: 4,000 students move out of our residence halls each year"]
V2 = V1[:2] + ["Interviews: 5 movers; 4 of 5 would only use it if listing is free",
               "Business model: free to list; buyers pay a $1 pickup fee (to test at the Residence Life table)"] + V1[4:]


def pptx(slides: list[str]) -> bytes:
    a, p = ("http://schemas.openxmlformats.org/drawingml/2006/main",
            "http://schemas.openxmlformats.org/presentationml/2006/main")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for i, text in enumerate(slides, 1):
            z.writestr(f"ppt/slides/slide{i}.xml", f"<p:sld xmlns:a='{a}' xmlns:p='{p}'><p:cSld><p:spTree><p:sp>"
                       f"<p:txBody><a:p><a:r><a:t>{text}</a:t></a:r></a:p></p:txBody></p:sp></p:spTree></p:cSld></p:sld>")
    return buf.getvalue()


def share(v, coach, store, name, slides, note, overview=False):
    where = "saves on the Overview, then discusses" if overview else "attaches in the chat"
    print("=" * 100 + f"\nAlice {where} {name}: {note}\n" + "-" * 100)
    start = time.perf_counter()
    if overview:  # the Overview's Project files: saved with no model call; read when the team asks
        saved = actions.save_file(v, store, "m1", name, pptx(slides))
        print(f"saved in {time.perf_counter() - start:.2f}s, not read yet: {saved.latest.summary[:90]}…")
        reply = actions.discuss_file(v, coach, store, "m1", saved.id, note)
    else:
        reply = actions.upload_file(v, coach, store, "m1", name, pptx(slides), note)
    f = v.file(v.conversation[-2].file_id)
    version = f.latest
    print(f"({time.perf_counter() - start:.1f}s) {f.name} version {version.number}, {version.chars} characters read")
    print(f"SUMMARY: {version.summary}\nCLAIMS:\n" + "\n".join(f"  - {c}" for c in version.claims))
    print(f"\nMENTOR:\n{reply.text}")
    for group in reply.change_groups:
        for ch in changes.changes_in(v, group):
            print(f"  changed: {ch.summary}")
    print("  open revisions now: " + ("; ".join(s.text for s in files.revision_tasks(v, f)) or "none"))
    return f


def main() -> int:
    coach = make_coach(settings())
    if not hasattr(coach, "client"):
        print("No model configured: fill in ~/.streamlit/secrets.toml first.")
        return 2
    v, store = next(x for x in demo_ventures() if x.id == "V-CAMPUS"), MemoryFileStore()
    print(f"Model: {coach.label} · fictional demo venture: {v.name}\n")
    share(v, coach, store, "Campus Loop pitch.pptx", V1, "Our pitch deck for Foundry Friday. What do you think?")
    share(v, coach, store, "Campus Loop pitch v2.pptx", V2, "Updated the deck with the interview numbers and the new fee.",
          overview=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
