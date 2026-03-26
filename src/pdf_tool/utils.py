from __future__ import annotations

from pathlib import Path

from .errors import PDFToolError


def ensure_pdf_input(path: str | Path) -> Path:
    input_path = Path(path).expanduser()
    if not input_path.exists():
        raise PDFToolError(f"File di input non trovato: {input_path}")
    if input_path.suffix.lower() != ".pdf":
        raise PDFToolError(f"Il file di input deve essere un PDF: {input_path}")
    return input_path


def ensure_distinct_paths(input_path: Path, output_path: Path) -> None:
    if input_path.resolve(strict=False) == output_path.resolve(strict=False):
        raise PDFToolError("Il file di output deve essere diverso da quello di input.")


def resolve_incremental_output_path(input_path: Path, extension: str) -> Path:
    normalized_extension = extension if extension.startswith(".") else f".{extension}"
    base_name = input_path.stem

    input_resolved = input_path.resolve(strict=False)
    counter = 1
    while True:
        candidate = input_path.with_name(f"{base_name}.{counter}{normalized_extension}")
        if candidate.resolve(strict=False) != input_resolved and not candidate.exists():
            return candidate
        counter += 1


def human_size(num_bytes: int) -> str:
    value = float(num_bytes)
    units = ["B", "KB", "MB", "GB", "TB"]
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.2f} {unit}"
        value /= 1024
    return f"{num_bytes} B"


def format_size_change(size_before: int, size_after: int) -> str:
    if size_before <= 0:
        return f"{human_size(size_before)} -> {human_size(size_after)}"

    delta = size_after - size_before
    percent = (delta / size_before) * 100
    return (
        f"{human_size(size_before)} -> {human_size(size_after)} "
        f"({percent:+.1f}%)"
    )
