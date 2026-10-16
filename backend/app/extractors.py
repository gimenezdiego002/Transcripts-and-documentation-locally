from __future__ import annotations

import html
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

class ExtractionResult:
    def __init__(self, markdown: str, warnings: list[str] | None = None, language: str | None = None):
        self.markdown = markdown
        self.warnings = warnings or []
        self.language = language


def _escape_table_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", "<br>").strip()


def extract_docx(path: Path) -> ExtractionResult:
    try:
        from docx import Document
    except ImportError as exc:
        raise RuntimeError("DOCX extraction requires python-docx. Run setup.bat, then retry this source.") from exc
    document = Document(path)
    output: list[str] = []
    warnings: list[str] = []
    paragraph_by_element = {id(paragraph._p): paragraph for paragraph in document.paragraphs}
    table_by_element = {id(table._tbl): table for table in document.tables}
    for block in document.element.body.iterchildren():
        tag = block.tag.rsplit("}", 1)[-1]
        if tag == "p":
            paragraph = paragraph_by_element.get(id(block))
            if paragraph is None:
                continue
            text = paragraph.text
            if not text.strip():
                output.append("")
                continue
            style = (paragraph.style.name or "").lower() if paragraph.style else ""
            heading_match = re.search(r"heading\s*(\d+)", style)
            if heading_match:
                output.append(f"{'#' * min(int(heading_match.group(1)), 6)} {text}")
            elif "list" in style:
                prefix = "1." if "number" in style else "-"
                output.append(f"{prefix} {text}")
            else:
                output.append(text)
        elif tag == "tbl":
            table = table_by_element.get(id(block))
            if table is None or not table.rows:
                continue
            rows = [[_escape_table_cell(cell.text) for cell in row.cells] for row in table.rows]
            width = max(len(row) for row in rows)
            rows = [row + [""] * (width - len(row)) for row in rows]
            output.extend([
                "| " + " | ".join(rows[0]) + " |",
                "| " + " | ".join(["---"] * width) + " |",
                *["| " + " | ".join(row) + " |" for row in rows[1:]],
                "",
            ])
        elif tag not in {"sectPr"}:
            warnings.append(f"Unsupported Word element preserved only when visible text was available: {tag}")
    return ExtractionResult("\n\n".join(part for part in output).strip(), warnings)


def extract_pdf(path: Path) -> ExtractionResult:
    try:
        import fitz
    except ImportError as exc:
        raise RuntimeError("PDF extraction requires PyMuPDF. Run setup.bat, then retry this source.") from exc
    pages: list[str] = []
    warnings: list[str] = []
    with fitz.open(path) as document:
        if document.is_encrypted:
            if not document.authenticate(""):
                raise ValueError("PDF is encrypted and requires a password")
        for index, page in enumerate(document):
            blocks = page.get_text("blocks", sort=True)
            text = "\n\n".join(block[4].strip() for block in blocks if block[4].strip())
            pages.append(f"## Page {index + 1}\n\n{text or '[No extractable text on this page]'}")
            if not text:
                warnings.append(f"Page {index + 1} had no extractable text; it may be scanned.")
    return ExtractionResult("\n\n".join(pages), warnings)


def extract_legacy_doc(path: Path) -> ExtractionResult:
    candidates = (["antiword", str(path)], ["catdoc", str(path)])
    for command in candidates:
        if shutil.which(command[0]):
            result = subprocess.run(command, capture_output=True, check=False)
            if result.returncode == 0:
                return ExtractionResult(result.stdout.decode("utf-8", errors="replace"), [f"Extracted with {command[0]}."])
    libreoffice = shutil.which("soffice") or shutil.which("libreoffice")
    if libreoffice:
        with tempfile.TemporaryDirectory() as temporary:
            result = subprocess.run(
                [libreoffice, "--headless", "--convert-to", "txt:Text", "--outdir", temporary, str(path)],
                capture_output=True,
                check=False,
            )
            converted = Path(temporary) / f"{path.stem}.txt"
            if result.returncode == 0 and converted.exists():
                return ExtractionResult(converted.read_text(encoding="utf-8", errors="replace"), ["Extracted with LibreOffice."])
    raise RuntimeError("Legacy .doc extraction requires local Antiword, Catdoc, or LibreOffice.")


def extract_text(path: Path) -> ExtractionResult:
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "utf-16", "cp1252", "latin-1"):
        try:
            return ExtractionResult(raw.decode(encoding))
        except UnicodeDecodeError:
            continue
    return ExtractionResult(raw.decode("utf-8", errors="replace"), ["Some undecodable characters were replaced."])


def extract_document(path: Path) -> ExtractionResult:
    extension = path.suffix.lower()
    if extension == ".docx":
        return extract_docx(path)
    if extension == ".pdf":
        return extract_pdf(path)
    if extension == ".doc":
        return extract_legacy_doc(path)
    if extension in {".txt", ".md", ".markdown", ".srt", ".vtt"}:
        return extract_text(path)
    raise ValueError(f"Unsupported document type: {html.escape(extension)}")

