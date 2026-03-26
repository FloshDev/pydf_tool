from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .errors import PDFToolError
from .utils import ensure_pdf_input

CHARS_PER_PAGE_THRESHOLD = 50


@dataclass(frozen=True)
class CheckOCRResult:
    pages_total: int
    pages_with_text: int
    pages_without_text: int
    chars_per_page_avg: float
    verdict: str  # "ocr_needed" | "already_searchable" | "mixed"


def check_ocr(input_path: str | Path) -> CheckOCRResult:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise PDFToolError(
            "Dipendenze Python mancanti. Installa il progetto con `pip install -e .`."
        ) from exc

    source = ensure_pdf_input(input_path)

    try:
        reader = PdfReader(str(source))
    except Exception as exc:
        raise PDFToolError(f"Impossibile leggere il PDF: {source}") from exc

    pages_total = len(reader.pages)
    if pages_total == 0:
        raise PDFToolError("Il PDF non contiene pagine.")

    pages_with_text = 0
    pages_without_text = 0
    total_chars = 0

    for page in reader.pages:
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""
        chars = len(text.strip())
        total_chars += chars
        if chars >= CHARS_PER_PAGE_THRESHOLD:
            pages_with_text += 1
        else:
            pages_without_text += 1

    chars_per_page_avg = total_chars / pages_total

    if pages_with_text == 0:
        verdict = "ocr_needed"
    elif pages_without_text == 0:
        verdict = "already_searchable"
    else:
        verdict = "mixed"

    return CheckOCRResult(
        pages_total=pages_total,
        pages_with_text=pages_with_text,
        pages_without_text=pages_without_text,
        chars_per_page_avg=chars_per_page_avg,
        verdict=verdict,
    )
