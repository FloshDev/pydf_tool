from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from .errors import PDFToolError
from .utils import resolve_user_path

__all__ = [
    "choose_pdf_file",
    "is_macos",
    "open_output_folder",
    "open_with_default_app",
    "reveal_in_finder",
]


def is_macos() -> bool:
    return sys.platform == "darwin"


def choose_pdf_file(
    initial_directory: str | Path | None = None,
    prompt: str = "Seleziona un PDF",
) -> Path | None:
    """Open Finder's file picker and return a PDF path, or None on cancel."""

    _require_macos()
    default_directory = _coerce_default_directory(initial_directory)
    command = [
        "osascript",
        "-e",
        _build_choose_pdf_script(),
        prompt.strip() or "Seleziona un PDF",
        str(default_directory) if default_directory is not None else "",
    ]

    try:
        completed = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        raise PDFToolError("`osascript` non è disponibile su questo sistema.") from exc
    except subprocess.CalledProcessError as exc:
        if _is_user_cancelled(exc):
            return None
        raise PDFToolError(_format_command_error("Selezione file", exc)) from exc

    selected = completed.stdout.strip()
    if not selected:
        raise PDFToolError("Selezione file non riuscita: Finder non ha restituito un percorso.")

    selected_path = resolve_user_path(selected)
    if selected_path.suffix.lower() != ".pdf":
        raise PDFToolError(f"Il file selezionato non è un PDF: {selected_path}")
    return selected_path


def open_with_default_app(path: str | Path) -> None:
    """Open a file or folder with macOS default application."""

    _require_macos()
    target = _resolve_existing_target(path)
    _run_open_command(["open", str(target)], "Apertura con l'app di default")


def reveal_in_finder(path: str | Path) -> None:
    """Reveal an existing file or folder in Finder."""

    _require_macos()
    target = _resolve_existing_target(path)
    _run_open_command(["open", "-R", str(target)], "Rivelazione in Finder")


def open_output_folder(path: str | Path) -> None:
    """Open the output folder for a file or folder path."""

    _require_macos()
    target = resolve_user_path(path)
    folder = target if target.is_dir() else target.parent
    if not folder.exists():
        raise PDFToolError(f"Cartella di output non trovata: {folder}")
    _run_open_command(["open", str(folder)], "Apertura cartella di output")


def _require_macos() -> None:
    if not is_macos():
        raise PDFToolError("Le integrazioni Finder di PyDF Tool sono disponibili solo su macOS.")


def _coerce_default_directory(initial_directory: str | Path | None) -> Path | None:
    if initial_directory is None:
        return None

    candidate = resolve_user_path(initial_directory)
    if candidate.exists():
        return candidate if candidate.is_dir() else candidate.parent
    if candidate.suffix:
        return candidate.parent
    return candidate


def _build_choose_pdf_script() -> str:
    return (
        "on run argv\n"
        "    set promptText to item 1 of argv\n"
        "    set defaultLocationPath to item 2 of argv\n"
        "    if defaultLocationPath is \"\" then\n"
        "        set chosenFile to choose file of type {\"com.adobe.pdf\"} with prompt promptText\n"
        "    else\n"
        "        set chosenFile to choose file of type {\"com.adobe.pdf\"} with prompt promptText default location (POSIX file defaultLocationPath)\n"
        "    end if\n"
        "    return POSIX path of chosenFile\n"
        "end run"
    )


def _resolve_existing_target(path: str | Path) -> Path:
    target = resolve_user_path(path)
    if not target.exists():
        raise PDFToolError(f"Percorso non trovato: {target}")
    return target


def _run_open_command(command: list[str], action: str) -> None:
    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise PDFToolError(f"`{command[0]}` non è disponibile su questo sistema.") from exc
    except subprocess.CalledProcessError as exc:
        raise PDFToolError(_format_command_error(action, exc)) from exc


def _is_user_cancelled(exc: subprocess.CalledProcessError) -> bool:
    combined_output = " ".join(
        part for part in (exc.stdout, exc.stderr) if isinstance(part, str) and part
    ).lower()
    if not combined_output:
        return exc.returncode in {1, 128}
    return "user canceled" in combined_output or "user cancelled" in combined_output


def _format_command_error(action: str, exc: subprocess.CalledProcessError) -> str:
    details = " ".join(
        part.strip()
        for part in (exc.stderr, exc.stdout)
        if isinstance(part, str) and part.strip()
    )
    if details:
        return f"{action} fallita: {details}"
    return f"{action} fallita con codice {exc.returncode}."
