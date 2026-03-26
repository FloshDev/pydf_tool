from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from .errors import PDFToolError
from .progress import OperationProgress
from .utils import (
    ensure_distinct_paths,
    ensure_pdf_input,
    resolve_user_path,
    resolve_incremental_output_path,
)

PRESET_STRENGTHS = {
    "low": 25,
    "medium": 55,
    "high": 80,
}


@dataclass(frozen=True)
class CompressionProfile:
    label: str
    strength: int
    dpi: int
    pdf_setting: str


@dataclass(frozen=True)
class CompressionResult:
    output_path: Path
    level: str
    grayscale: bool
    size_before: int
    size_after: int


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


def resolve_compression_profile(level: str) -> CompressionProfile:
    normalized = level.strip().lower()
    if normalized in PRESET_STRENGTHS:
        strength = PRESET_STRENGTHS[normalized]
        label = normalized
    else:
        try:
            strength = int(normalized)
        except ValueError as exc:
            raise PDFToolError(
                "Livello non valido. Usa `low`, `medium`, `high` o un numero tra 1 e 100."
            ) from exc
        if not 1 <= strength <= 100:
            raise PDFToolError(
                "Il livello numerico deve essere compreso tra 1 e 100."
            )
        label = str(strength)

    dpi = 300 - round(((strength - 1) / 99) * (300 - 72))
    if strength <= 33:
        pdf_setting = "/printer"
    elif strength <= 66:
        pdf_setting = "/ebook"
    else:
        pdf_setting = "/screen"

    return CompressionProfile(
        label=label,
        strength=strength,
        dpi=max(72, dpi),
        pdf_setting=pdf_setting,
    )


def resolve_compress_output_path(input_path: Path, output: str | Path | None) -> Path:
    if output is None:
        output_path = resolve_incremental_output_path(input_path, ".pdf")
    else:
        output_path = resolve_user_path(output)
        if not output_path.suffix:
            output_path = output_path.with_suffix(".pdf")

    if output_path.suffix.lower() != ".pdf":
        raise PDFToolError("L'output della compressione deve essere un file `.pdf`.")

    ensure_distinct_paths(input_path, output_path)
    return output_path


def compress_pdf(
    input_path: str | Path,
    output_path: str | Path | None = None,
    level: str = "medium",
    grayscale: bool = False,
    progress_callback: Callable[[OperationProgress], None] | None = None,
) -> CompressionResult:
    source = ensure_pdf_input(input_path)
    destination = resolve_compress_output_path(source, output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)

    if shutil.which("gs") is None:
        raise PDFToolError(
            "Ghostscript non trovato. Installa `brew install ghostscript`."
        )

    profile = resolve_compression_profile(level)
    size_before = source.stat().st_size
    staged_source = source
    staged_destination = destination
    page_count: int | None = None
    if progress_callback is not None:
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise PDFToolError(
                "Dipendenze Python mancanti. Installa il progetto con `pip install -e .`."
            ) from exc

        try:
            page_count = len(PdfReader(str(source)).pages)
        except Exception:
            page_count = None

        _emit_progress(
            progress_callback,
            stage="prepare",
            message=(
                f"Preparazione compressione ({profile.label})"
                + (" in bianco e nero" if grayscale else "")
            ),
            total=page_count,
        )

    temp_dir: tempfile.TemporaryDirectory[str] | None = None
    try:
        temp_dir = tempfile.TemporaryDirectory(prefix="pydf-tool-gs-")
        staged_destination = Path(temp_dir.name) / "compressed-output.pdf"

        try:
            source_text = str(source)
            source_text.encode("ascii")
        except UnicodeEncodeError:
            staged_source = Path(temp_dir.name) / "input.pdf"
            shutil.copy2(source, staged_source)

        command = [
        "gs",
        "-sDEVICE=pdfwrite",
        "-dCompatibilityLevel=1.4",
        "-dNOPAUSE",
        "-dBATCH",
        "-dAutoRotatePages=/None",
        "-dDetectDuplicateImages=true",
        "-dCompressFonts=true",
        "-dSubsetFonts=true",
        "-dEmbedAllFonts=true",
        ]

        if grayscale:
            command.extend(
                [
                    "-sColorConversionStrategy=Gray",
                    "-sColorConversionStrategyForImages=Gray",
                    "-dProcessColorModel=/DeviceGray",
                ]
            )

        command.extend(
            [
                "-dDownsampleColorImages=true",
                "-dDownsampleGrayImages=true",
                "-dDownsampleMonoImages=true",
                "-dColorImageDownsampleType=/Bicubic",
                "-dGrayImageDownsampleType=/Bicubic",
                "-dMonoImageDownsampleType=/Subsample",
                "-dColorImageDownsampleThreshold=1.0",
                "-dGrayImageDownsampleThreshold=1.0",
                "-dMonoImageDownsampleThreshold=1.0",
                f"-dColorImageResolution={profile.dpi}",
                f"-dGrayImageResolution={profile.dpi}",
                f"-dMonoImageResolution={profile.dpi}",
                f"-dPDFSETTINGS={profile.pdf_setting}",
                f"-sOutputFile={staged_destination}",
                str(staged_source),
            ]
        )

        if progress_callback is None:
            quiet_command = command.copy()
            quiet_command.insert(4, "-dQUIET")
            try:
                subprocess.run(quiet_command, check=True, capture_output=True, text=True)
            except subprocess.CalledProcessError as exc:
                details = exc.stderr.strip() or exc.stdout.strip() or str(exc)
                raise PDFToolError(f"Compressione fallita: {details}") from exc
        else:
            process: subprocess.Popen[str] | None = None
            output_chunks: list[str] = []
            current_page = 0
            try:
                process = subprocess.Popen(
                    command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                )
                _emit_progress(
                    progress_callback,
                    stage="compress",
                    message=(
                        "Compressione in corso"
                        + (" in bianco e nero" if grayscale else "")
                    ),
                    completed=0,
                    total=page_count,
                )

                if process.stdout is not None:
                    for line in process.stdout:
                        output_chunks.append(line)
                        match = re.search(r"\bPage\s+(\d+)\b", line)
                        if match:
                            current_page = int(match.group(1))
                            _emit_progress(
                                progress_callback,
                                stage="compress",
                                message=(
                                    f"Compressione pagina {current_page}/"
                                    f"{page_count if page_count is not None else '?'}"
                                ),
                                completed=current_page,
                                total=page_count,
                            )

                return_code = process.wait()
                if return_code != 0:
                    raise subprocess.CalledProcessError(
                        return_code,
                        command,
                        output="".join(output_chunks),
                    )
            except KeyboardInterrupt:
                if process is not None and process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()
                if staged_destination.exists():
                    staged_destination.unlink(missing_ok=True)
                raise
            except subprocess.CalledProcessError as exc:
                if staged_destination.exists():
                    staged_destination.unlink(missing_ok=True)
                details = (exc.output or "").strip() or str(exc)
                raise PDFToolError(f"Compressione fallita: {details}") from exc
            finally:
                if process is not None and process.stdout is not None:
                    process.stdout.close()

        if not staged_destination.exists():
            raise PDFToolError("Compressione fallita: file di output non generato.")

        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.move(str(staged_destination), str(destination))
        except (OSError, shutil.Error) as exc:
            raise PDFToolError(
                f"Scrittura del file compresso fallita: {destination}"
            ) from exc

        destination = resolve_user_path(destination)
        size_after = destination.stat().st_size
        _emit_progress(
            progress_callback,
            stage="done",
            message="Compressione completata",
            completed=page_count or 0,
            total=page_count,
        )
        return CompressionResult(
            output_path=destination,
            level=profile.label,
            grayscale=grayscale,
            size_before=size_before,
            size_after=size_after,
        )
    finally:
        if temp_dir is not None:
            temp_dir.cleanup()
