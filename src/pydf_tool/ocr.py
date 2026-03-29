from __future__ import annotations

import shutil
from collections.abc import Callable
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from .errors import PDFToolError
from .progress import OperationProgress
from .utils import (
    ensure_distinct_paths,
    ensure_pdf_input,
    resolve_incremental_output_path,
    resolve_user_path,
)

SUPPORTED_LANGUAGE_CODES = {
    "it": "ita",
    "ita": "ita",
    "en": "eng",
    "eng": "eng",
}


@dataclass(frozen=True)
class OCRResult:
    output_path: Path
    pages: int
    output_type: str


def _emit_progress(
    callback: Callable[[OperationProgress], None] | None,
    *,
    stage: str,
    message: str,
    completed: int = 0,
    total: int | None = None,
) -> None:
    if callback is None:
        return
    callback(
        OperationProgress(
            stage=stage,
            message=message,
            completed=completed,
            total=total,
        )
    )


def resolve_tesseract_languages(lang: str) -> str:
    tokens = [token.strip().lower() for token in lang.replace(",", "+").split("+")]
    tokens = [token for token in tokens if token]

    if not tokens:
        raise PDFToolError("Specifica almeno una lingua OCR valida: it, en o it+en.")

    resolved: list[str] = []
    for token in tokens:
        try:
            mapped = SUPPORTED_LANGUAGE_CODES[token]
        except KeyError as exc:
            raise PDFToolError(
                "Lingua OCR non supportata. Usa `it`, `en` oppure una combinazione "
                "come `it+en`."
            ) from exc
        if mapped not in resolved:
            resolved.append(mapped)

    return "+".join(resolved)


def resolve_ocr_output_path(input_path: Path, output: str | Path | None) -> Path:
    if output is None:
        output_path = resolve_incremental_output_path(input_path, ".pdf")
    else:
        output_path = resolve_user_path(output)
        if not output_path.suffix:
            output_path = output_path.with_suffix(".pdf")

    if output_path.suffix.lower() not in {".pdf", ".txt"}:
        raise PDFToolError("L'output OCR deve essere un file `.pdf` o `.txt`.")

    ensure_distinct_paths(input_path, output_path)
    return output_path


def run_ocr(
    input_path: str | Path,
    output_path: str | Path | None = None,
    lang: str = "it",
    progress_callback: Callable[[OperationProgress], None] | None = None,
) -> OCRResult:
    try:
        import pytesseract
        from pdf2image import convert_from_path
        from pypdf import PdfReader, PdfWriter
    except ImportError as exc:
        raise PDFToolError(
            "Dipendenze Python mancanti. Installa il progetto con `pip install -e .`."
        ) from exc

    source = ensure_pdf_input(input_path)
    destination = resolve_ocr_output_path(source, output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)

    if shutil.which("tesseract") is None:
        raise PDFToolError("Tesseract non trovato. Installa `brew install tesseract`.")
    if shutil.which("pdftoppm") is None and shutil.which("pdftocairo") is None:
        raise PDFToolError("Poppler non trovato. Installa `brew install poppler`.")

    tesseract_lang = resolve_tesseract_languages(lang)
    page_count: int | None = None
    try:
        page_count = len(PdfReader(str(source)).pages)
    except Exception:
        page_count = None

    _emit_progress(
        progress_callback,
        stage="prepare",
        message="Analisi del PDF",
        total=page_count,
    )

    try:
        available_languages = set(pytesseract.get_languages(config=""))
    except Exception as exc:
        raise PDFToolError(
            "Impossibile leggere le lingue disponibili da Tesseract. "
            "Verifica l'installazione di `tesseract`."
        ) from exc

    requested_languages = set(tesseract_lang.split("+"))
    missing_languages = sorted(requested_languages - available_languages)
    if missing_languages:
        raise PDFToolError(
            "Lingue OCR non disponibili in Tesseract: "
            f"{', '.join(missing_languages)}. "
            "Su macOS installa `brew install tesseract-lang`."
        )

    use_pdftocairo = shutil.which("pdftocairo") is not None

    # Se page_count è noto, processiamo pagina per pagina (low-memory).
    # Ogni pagina viene caricata, processata e liberata prima di passare alla successiva.
    # Picco RAM: ~26 MB/pagina a 300 DPI (vs N*26 MB con caricamento batch).
    # Se page_count è None (PdfReader ha fallito), si ricade nel percorso batch originale.

    if page_count is not None:
        _emit_progress(
            progress_callback,
            stage="ocr",
            message=f"OCR pronto: 0/{page_count} pagine",
            completed=0,
            total=page_count,
        )

        if destination.suffix.lower() == ".txt":
            page_texts: list[str] = []
            for page_num in range(1, page_count + 1):
                try:
                    page_imgs = convert_from_path(
                        str(source),
                        dpi=300,
                        use_pdftocairo=use_pdftocairo,
                        first_page=page_num,
                        last_page=page_num,
                    )
                except Exception as exc:
                    raise PDFToolError(
                        f"Rendering pagina {page_num} fallito. "
                        "Verifica che Poppler sia installato e il PDF valido."
                    ) from exc
                if not page_imgs:
                    raise PDFToolError(
                        f"Nessuna immagine prodotta per la pagina {page_num}."
                    )
                image = page_imgs[0]
                del page_imgs
                try:
                    text = pytesseract.image_to_string(
                        image, lang=tesseract_lang
                    ).strip()
                except Exception as exc:
                    raise PDFToolError(
                        f"OCR fallito sulla pagina {page_num}. "
                        "Verifica lingua OCR e installazione di Tesseract."
                    ) from exc
                finally:
                    del image
                page_header = f"--- Pagina {page_num} ---"
                page_texts.append(page_header if not text else f"{page_header}\n{text}")
                _emit_progress(
                    progress_callback,
                    stage="ocr",
                    message=f"OCR pagina {page_num}/{page_count}",
                    completed=page_num,
                    total=page_count,
                )

            _emit_progress(
                progress_callback,
                stage="finalize",
                message="Scrittura output testuale",
                completed=page_count,
                total=page_count,
            )
            destination.write_text("\n\n".join(page_texts) + "\n", encoding="utf-8")
            _emit_progress(
                progress_callback,
                stage="done",
                message="OCR completato",
                completed=page_count,
                total=page_count,
            )
            return OCRResult(
                output_path=destination, pages=page_count, output_type="txt"
            )

        writer = PdfWriter()
        for page_num in range(1, page_count + 1):
            try:
                page_imgs = convert_from_path(
                    str(source),
                    dpi=300,
                    use_pdftocairo=use_pdftocairo,
                    first_page=page_num,
                    last_page=page_num,
                )
            except Exception as exc:
                raise PDFToolError(
                    f"Rendering pagina {page_num} fallito. "
                    "Verifica che Poppler sia installato e il PDF valido."
                ) from exc
            if not page_imgs:
                raise PDFToolError(
                    f"Nessuna immagine prodotta per la pagina {page_num}."
                )
            image = page_imgs[0]
            del page_imgs
            try:
                searchable_page = pytesseract.image_to_pdf_or_hocr(
                    image,
                    extension="pdf",
                    lang=tesseract_lang,
                )
                page_reader = PdfReader(BytesIO(searchable_page))
                writer.add_page(page_reader.pages[0])
            except Exception as exc:
                raise PDFToolError(
                    f"Generazione del PDF OCR fallita sulla pagina {page_num}. "
                    "Verifica il PDF di input e l'installazione OCR."
                ) from exc
            finally:
                del image
            _emit_progress(
                progress_callback,
                stage="ocr",
                message=f"OCR pagina {page_num}/{page_count}",
                completed=page_num,
                total=page_count,
            )

        _emit_progress(
            progress_callback,
            stage="finalize",
            message="Scrittura PDF ricercabile",
            completed=page_count,
            total=page_count,
        )
        try:
            with destination.open("wb") as file_obj:
                writer.write(file_obj)
        except Exception as exc:
            raise PDFToolError(
                f"Scrittura del file OCR fallita: {destination}"
            ) from exc

        _emit_progress(
            progress_callback,
            stage="done",
            message="OCR completato",
            completed=page_count,
            total=page_count,
        )
        return OCRResult(output_path=destination, pages=page_count, output_type="pdf")

    # Percorso batch (fallback): page_count sconosciuto, carica tutto in memoria.
    _emit_progress(
        progress_callback,
        stage="render",
        message="Rendering pagine con Poppler",
        total=None,
    )
    try:
        images = convert_from_path(str(source), dpi=300, use_pdftocairo=use_pdftocairo)
    except Exception as exc:
        raise PDFToolError(
            "Conversione PDF->immagini fallita. Verifica che Poppler sia installato "
            "e che il PDF di input sia valido."
        ) from exc

    if not images:
        raise PDFToolError("Nessuna pagina convertita dal PDF di input.")

    page_count = len(images)
    _emit_progress(
        progress_callback,
        stage="ocr",
        message=f"OCR pronto: 0/{page_count} pagine",
        completed=0,
        total=page_count,
    )

    if destination.suffix.lower() == ".txt":
        page_texts_batch: list[str] = []
        for index, image in enumerate(images, start=1):
            try:
                text = pytesseract.image_to_string(image, lang=tesseract_lang).strip()
            except Exception as exc:
                raise PDFToolError(
                    f"OCR fallito sulla pagina {index}. "
                    "Verifica lingua OCR e installazione di Tesseract."
                ) from exc
            page_header = f"--- Pagina {index} ---"
            page_texts_batch.append(
                page_header if not text else f"{page_header}\n{text}"
            )
            _emit_progress(
                progress_callback,
                stage="ocr",
                message=f"OCR pagina {index}/{page_count}",
                completed=index,
                total=page_count,
            )

        del images
        _emit_progress(
            progress_callback,
            stage="finalize",
            message="Scrittura output testuale",
            completed=page_count,
            total=page_count,
        )
        destination.write_text("\n\n".join(page_texts_batch) + "\n", encoding="utf-8")
        _emit_progress(
            progress_callback,
            stage="done",
            message="OCR completato",
            completed=page_count,
            total=page_count,
        )
        return OCRResult(output_path=destination, pages=page_count, output_type="txt")

    writer = PdfWriter()
    for index, image in enumerate(images, start=1):
        try:
            searchable_page = pytesseract.image_to_pdf_or_hocr(
                image,
                extension="pdf",
                lang=tesseract_lang,
            )
            page_reader = PdfReader(BytesIO(searchable_page))
            writer.add_page(page_reader.pages[0])
        except Exception as exc:
            raise PDFToolError(
                f"Generazione del PDF OCR fallita sulla pagina {index}. "
                "Verifica il PDF di input e l'installazione OCR."
            ) from exc
        _emit_progress(
            progress_callback,
            stage="ocr",
            message=f"OCR pagina {index}/{page_count}",
            completed=index,
            total=page_count,
        )

    del images
    _emit_progress(
        progress_callback,
        stage="finalize",
        message="Scrittura PDF ricercabile",
        completed=page_count,
        total=page_count,
    )
    try:
        with destination.open("wb") as file_obj:
            writer.write(file_obj)
    except Exception as exc:
        raise PDFToolError(f"Scrittura del file OCR fallita: {destination}") from exc

    _emit_progress(
        progress_callback,
        stage="done",
        message="OCR completato",
        completed=page_count,
        total=page_count,
    )
    return OCRResult(output_path=destination, pages=page_count, output_type="pdf")
