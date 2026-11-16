"""Text from project files, extracted on this computer (no service sees the file for this).

- PDF: pypdfium2 (the PDF engine of Chrome), page by page.
- Word .docx and PowerPoint .pptx: they are zip files of XML; read with the standard library, slide by slide.
- Excel .xlsx: openpyxl, sheet by sheet, values only.
- CSV, .txt, .md: decoded as text.
- Images and links: not read in this version.
Raises ExtractError when a file cannot be read (damaged, password-protected, or not what its name says).
"""
from __future__ import annotations

import io
import re
import zipfile
from xml.etree import ElementTree

from .models import FileKind

MAX_CHARS = 200_000  # text kept per version; the mentor reads it in parts
MAX_XML_BYTES = 30_000_000  # a guard against zip bombs
MAX_ROWS = 400  # per sheet
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"


class ExtractError(ValueError):
    pass


def text_of(kind: FileKind, data: bytes) -> str:
    """The readable text of a file ("" for images and links)."""
    readers = {FileKind.PDF: _pdf, FileKind.WORD: _docx, FileKind.SLIDES: _pptx, FileKind.SHEET: _xlsx,
               FileKind.CSV: _decode, FileKind.TEXT: _decode}
    reader = readers.get(FileKind(kind))
    if reader is None:
        return ""
    try:
        text = reader(data)
    except ExtractError:
        raise
    except Exception as err:  # noqa: BLE001 - any parser failure means the same thing to the team
        raise ExtractError(f"This file could not be read ({type(err).__name__}).") from err
    text = re.sub(r"\n{3,}", "\n\n", text.replace("\r\n", "\n")).strip()
    return text[:MAX_CHARS]


def _decode(data: bytes) -> str:
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def _pdf(data: bytes) -> str:
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(data)
    try:
        pages = []
        for i in range(len(pdf)):
            page = pdf[i]
            textpage = page.get_textpage()
            pages.append(f"[page {i + 1}]\n{textpage.get_text_bounded().strip()}")
            textpage.close()
            page.close()
        return "\n\n".join(pages)
    finally:
        pdf.close()


def _xml(z: zipfile.ZipFile, name: str) -> ElementTree.Element:
    info = z.getinfo(name)
    if info.file_size > MAX_XML_BYTES:
        raise ExtractError("This file is too large to read.")
    return ElementTree.fromstring(z.read(name))


def _paragraphs(root: ElementTree.Element, p: str, t: str) -> list[str]:
    lines = ("".join(node.text or "" for node in para.iter(t)).strip() for para in root.iter(p))
    return [line for line in lines if line]


def _docx(data: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        return "\n".join(_paragraphs(_xml(z, "word/document.xml"), f"{W}p", f"{W}t"))


def _pptx(data: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        slides = sorted((n for n in z.namelist() if re.fullmatch(r"ppt/slides/slide\d+\.xml", n)),
                        key=lambda n: int(re.search(r"(\d+)\.xml$", n).group(1)))
        return "\n\n".join(f"[slide {i}]\n" + "\n".join(_paragraphs(_xml(z, name), f"{A}p", f"{A}t"))
                           for i, name in enumerate(slides, 1))


def _xlsx(data: bytes) -> str:
    from openpyxl import load_workbook

    book = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    try:
        sheets = []
        for sheet in book.worksheets:
            rows = []
            for row in sheet.iter_rows(values_only=True):
                cells = ["" if c is None else str(c) for c in row]
                if any(cells):
                    rows.append("\t".join(cells).rstrip())
                if len(rows) >= MAX_ROWS:
                    rows.append("(more rows not shown)")
                    break
            sheets.append(f"[sheet {sheet.title}]\n" + "\n".join(rows))
        return "\n\n".join(sheets)
    finally:
        book.close()
