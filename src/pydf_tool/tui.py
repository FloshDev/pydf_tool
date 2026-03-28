from __future__ import annotations

import argparse
import shlex
from dataclasses import dataclass
from pathlib import Path
from shutil import get_terminal_size
from textwrap import shorten, wrap
from typing import Callable

from .check_ocr import CheckOCRResult, check_ocr
from .compress import CompressionResult, compress_pdf
from .errors import PDFToolError
from .ocr import OCRResult, run_ocr
from .progress import OperationProgress
from .utils import ensure_pdf_input, format_size_change, resolve_incremental_output_path, resolve_user_path

EXIT_COMMANDS = {"exit", "quit", ":q"}
APP_NAME = "PyDF Tool"
APP_TAGLINE = "strumenti PDF da terminale"
APP_SUMMARY = "OCR di PDF scansionati, compressione, verifica testo ricercabile."
MENU_TEXT_WIDTH = 34
DETAIL_TEXT_WIDTH = 68


@dataclass(frozen=True)
class MenuAction:
    key: str
    title: str
    summary: str
    detail: str
    example: str


def _load_prompt_toolkit():
    try:
        from prompt_toolkit.application import Application
        from prompt_toolkit.application.current import get_app
        from prompt_toolkit.key_binding import KeyBindings
        from prompt_toolkit.layout import HSplit, Layout, VSplit, Window
        from prompt_toolkit.layout.containers import DynamicContainer
        from prompt_toolkit.layout.dimension import D
        from prompt_toolkit.layout.controls import FormattedTextControl
        from prompt_toolkit.styles import Style
        from prompt_toolkit.widgets import Dialog, Label, RadioList, TextArea
    except ImportError as exc:
        raise PDFToolError(
            "Dipendenze TUI mancanti. Riesegui `pip install -e .` per installare "
            "`prompt_toolkit` e `rich`."
        ) from exc

    return {
        "Application": Application,
        "D": D,
        "Dialog": Dialog,
        "DynamicContainer": DynamicContainer,
        "KeyBindings": KeyBindings,
        "Label": Label,
        "HSplit": HSplit,
        "Layout": Layout,
        "RadioList": RadioList,
        "TextArea": TextArea,
        "VSplit": VSplit,
        "Window": Window,
        "FormattedTextControl": FormattedTextControl,
        "Style": Style,
        "get_app": get_app,
    }


def _load_rich():
    try:
        from rich.console import Console
        from rich.panel import Panel
        from rich.progress import (
            BarColumn,
            Progress,
            SpinnerColumn,
            TaskProgressColumn,
            TextColumn,
            TimeElapsedColumn,
        )
        from rich.table import Table
        from rich.text import Text
    except ImportError as exc:
        raise PDFToolError(
            "Dipendenze TUI mancanti. Riesegui `pip install -e .` per installare "
            "`prompt_toolkit` e `rich`."
        ) from exc

    return {
        "Console": Console,
        "Panel": Panel,
        "Progress": Progress,
        "SpinnerColumn": SpinnerColumn,
        "BarColumn": BarColumn,
        "TaskProgressColumn": TaskProgressColumn,
        "TextColumn": TextColumn,
        "TimeElapsedColumn": TimeElapsedColumn,
        "Table": Table,
        "Text": Text,
    }


def _dialog_style():
    Style = _load_prompt_toolkit()["Style"]
    return Style.from_dict(
        {
            "selected": "fg:#E8B84B bold",
            "dialog": "fg:#D4D4D4",
            "frame.border": "fg:#3A3A3A",
            "dialog frame.label": "fg:#E8B84B bold",
            "dialog.body": "fg:#D4D4D4",
            "dialog.body label": "fg:#D4D4D4",
            "dialog.body text-area": "fg:#D4D4D4",
            "dialog.body text-area.prompt": "fg:#7A7A7A",
            "dialog.body text-area cursor": "reverse",
            "dialog.body text-area last-line": "nounderline",
            "dialog_hint": "fg:#7A7A7A",
            "validation-toolbar": "fg:#D4D4D4",
            "dialog shadow": "",
            "button": "fg:#7A7A7A",
            "button.arrow": "fg:#7A7A7A",
            "button.focused": "fg:#E8B84B bold",
            "button.focused.arrow": "fg:#E8B84B bold",
            "radio": "fg:#7A7A7A",
            "radio-selected": "fg:#E8B84B bold",
        }
    )


def _console():
    return _load_rich()["Console"](soft_wrap=True)


def _fit_line(text: str, width: int) -> str:
    single_line = " ".join(text.split())
    clipped = shorten(single_line, width=width, placeholder="...")
    return clipped.ljust(width)


def _wrap_lines(text: str, width: int, max_lines: int) -> list[str]:
    normalized = " ".join(text.split())
    lines = wrap(
        normalized,
        width=max(12, width),
        break_long_words=False,
        break_on_hyphens=False,
    )
    if not lines:
        return [""]
    if len(lines) > max_lines:
        tail = " ".join(lines[max_lines - 1 :])
        lines = lines[: max_lines - 1] + [
            shorten(tail, width=max(12, width), placeholder="...")
        ]
    return lines


def _terminal_columns(default: int = 120) -> int:
    try:
        return get_terminal_size((default, 24)).columns
    except OSError:
        return default


def _terminal_rows(default: int = 24) -> int:
    try:
        return get_terminal_size((120, default)).lines
    except OSError:
        return default


def _dialog_width(preferred: int, minimum: int = 48, margin: int = 6) -> int:
    columns = _terminal_columns()
    return max(minimum, min(preferred, max(minimum, columns - margin)))


def _wrap_dialog_text(lines: list[str], width: int) -> str:
    wrapped: list[str] = []
    for line in lines:
        if not line:
            wrapped.append("")
            continue
        if line.startswith("- "):
            body = wrap(
                line[2:],
                width=max(20, width - 2),
                initial_indent="- ",
                subsequent_indent="  ",
                break_long_words=False,
                break_on_hyphens=False,
            )
            wrapped.extend(body or ["- "])
            continue
        wrapped.extend(
            wrap(
                line,
                width=max(20, width),
                break_long_words=False,
                break_on_hyphens=False,
            )
            or [""]
        )
    return "\n".join(wrapped)


def _home_actions() -> list[MenuAction]:
    return [
        MenuAction(
            key="ocr_tool",
            title="Strumento OCR",
            summary="Verifica e conversione di PDF scansionati",
            detail=(
                "Verifica se il PDF ha gia testo ricercabile, "
                "oppure avvia l'OCR per renderlo ricercabile o esportarlo in TXT."
            ),
            example="pydf-tool check doc.pdf  /  pydf-tool ocr doc.pdf --lang it",
        ),
        MenuAction(
            key="compress",
            title="Comprimi PDF",
            summary="Preset, livello custom e modalita bianco e nero",
            detail=(
                "Usa Ghostscript con avanzamento live, delta dimensione e "
                "conversione opzionale in bianco e nero."
            ),
            example="pydf-tool compress documento.pdf --level 80 --grayscale",
        ),
        MenuAction(
            key="manual",
            title="Comando libero",
            summary="Incolla una riga di comando completa",
            detail=(
                "Utile se vuoi restare nella TUI ma scrivere il comando direttamente, "
                "senza usare il wizard."
            ),
            example='ocr "input.pdf" --lang it --output "output.pdf"',
        ),
        MenuAction(
            key="help",
            title="Help",
            summary="Scorciatoie, annullamento, esempi e flussi supportati",
            detail="Mostra una vista dedicata con indicazioni operative e scorciatoie.",
            example="Premi H dal menu principale.",
        ),
        MenuAction(
            key="exit",
            title="Esci",
            summary="Chiude la sessione interattiva",
            detail="Esce dalla TUI e torna alla shell di sistema.",
            example="Premi Q oppure Esc.",
        ),
    ]


def _show_ocr_submenu() -> str | None:
    """Sottomenu Strumento OCR. Ritorna 'check', 'ocr', o None se annullato."""
    return _ask_choice(
        "Strumento OCR",
        "Cosa vuoi fare?",
        [
            ("check", "Verifica OCR · controlla se il PDF ha gia testo ricercabile"),
            ("ocr", "Esegui OCR · converti PDF scansionato in PDF ricercabile o TXT"),
        ],
    )


def _show_home_menu() -> str | None:
    toolkit = _load_prompt_toolkit()
    Application = toolkit["Application"]
    DynamicContainer = toolkit["DynamicContainer"]
    KeyBindings = toolkit["KeyBindings"]
    HSplit = toolkit["HSplit"]
    Layout = toolkit["Layout"]
    VSplit = toolkit["VSplit"]
    Window = toolkit["Window"]
    FormattedTextControl = toolkit["FormattedTextControl"]
    Style = toolkit["Style"]
    get_app = toolkit["get_app"]

    actions = _home_actions()
    state = {"index": 0}

    def _screen_metrics() -> tuple[int, int]:
        try:
            size = get_app().output.get_size()
            return size.columns, size.rows
        except Exception:
            return _terminal_columns(), _terminal_rows()

    def _header_state() -> tuple[str, list[str]]:
        columns, _ = _screen_metrics()
        line_width = max(20, columns - 2)
        tagline_width = max(0, line_width - len(APP_NAME) - 2)
        tagline = ""
        if tagline_width >= 10:
            tagline = shorten(APP_TAGLINE, width=tagline_width, placeholder="...")
        summary_lines = _wrap_lines(APP_SUMMARY, line_width, 2)
        return tagline, summary_lines

    def _layout_metrics() -> tuple[bool, int, int, int, bool, bool]:
        columns, rows = _screen_metrics()
        compact = rows < 26
        show_detail = rows >= 22

        if columns >= 110 and show_detail:
            menu_width = min(40, max(32, columns // 3))
            detail_width = max(28, columns - menu_width - 2)
            return True, menu_width, detail_width, rows, compact, show_detail

        stacked_width = max(28, columns - 4)
        return False, stacked_width, stacked_width, rows, compact, show_detail

    # ── box helpers ──────────────────────────────────────────────────────────

    def _box_top(box_width: int, title: str, title_style: str) -> list[tuple[str, str]]:
        fill = max(1, box_width - len(title) - 5)
        return [
            ("class:app_border", "┌─ "),
            (title_style, title),
            ("class:app_border", " " + "─" * fill + "┐\n"),
        ]

    def _box_bottom(box_width: int) -> list[tuple[str, str]]:
        return [("class:app_border", "└" + "─" * (box_width - 2) + "┘\n")]

    def _box_line(box_width: int, content: list[tuple[str, str]]) -> list[tuple[str, str]]:
        return [("class:app_border", "│ ")] + content + [("class:app_border", " │\n")]

    def _box_blank(box_width: int) -> list[tuple[str, str]]:
        return [("class:app_border", "│ " + " " * (box_width - 4) + " │\n")]

    # ── header ───────────────────────────────────────────────────────────────

    def _header_fragments():
        columns, _ = _screen_metrics()
        box_w = max(20, columns - 2)
        inner_w = box_w - 4
        tagline, summary_lines = _header_state()
        frags: list[tuple[str, str]] = []
        frags += _box_top(box_w, APP_NAME, "class:app_brand")
        if tagline:
            frags += _box_line(box_w, [("class:app_tagline", tagline.ljust(inner_w)[:inner_w])])
        for line in summary_lines:
            frags += _box_line(box_w, [("class:app_header", line.ljust(inner_w)[:inner_w])])
        frags += _box_bottom(box_w)
        return frags

    def _header_window():
        tagline, summary_lines = _header_state()
        height = 2 + (1 if tagline else 0) + len(summary_lines)
        return Window(
            height=height,
            content=FormattedTextControl(_header_fragments),
            always_hide_cursor=True,
        )

    # ── menu ─────────────────────────────────────────────────────────────────

    def _menu_fragments():
        _, menu_width, _, _, compact, _ = _layout_metrics()
        inner_w = max(4, menu_width - 4)
        item_gap = not compact
        frags: list[tuple[str, str]] = []
        frags += _box_top(menu_width, "Azioni", "class:home_section")
        for index, action in enumerate(actions):
            selected = index == state["index"]
            marker = "> " if selected else "  "
            title_style = "class:home_title_active" if selected else "class:home_title"
            summary_style = "class:home_summary_active" if selected else "class:home_summary"
            marker_style = "class:home_marker_active" if selected else "class:home_marker"
            frags += _box_line(menu_width, [
                (marker_style, marker),
                (title_style, _fit_line(action.title, inner_w - 2)),
            ])
            frags += _box_line(menu_width, [
                (summary_style, "  " + _fit_line(action.summary, inner_w - 2)),
            ])
            if item_gap and index < len(actions) - 1:
                frags += _box_blank(menu_width)
        frags += _box_bottom(menu_width)
        return frags

    # ── detail ────────────────────────────────────────────────────────────────

    def _detail_fragments():
        action = actions[state["index"]]
        _, _, detail_width, _, compact, _ = _layout_metrics()
        detail_lines_n = 2 if compact else 3
        command_lines_n = 1 if compact else 2
        inner_w = max(4, detail_width - 4)
        frags: list[tuple[str, str]] = []
        frags += _box_top(detail_width, "Anteprima", "class:detail_section")
        frags += _box_blank(detail_width)
        for line in _wrap_lines(action.title, inner_w, 1):
            frags += _box_line(detail_width, [("class:detail_heading", line.ljust(inner_w)[:inner_w])])
        frags += _box_blank(detail_width)
        for line in _wrap_lines(action.detail, inner_w, detail_lines_n):
            frags += _box_line(detail_width, [("class:detail_text", line.ljust(inner_w)[:inner_w])])
        frags += _box_blank(detail_width)
        frags += _box_line(detail_width, [("class:detail_label", "Comando".ljust(inner_w)[:inner_w])])
        for line in _wrap_lines(action.example, inner_w, command_lines_n):
            frags += _box_line(detail_width, [("class:detail_code", line.ljust(inner_w)[:inner_w])])
        frags += _box_blank(detail_width)
        frags += _box_bottom(detail_width)
        return frags

    # ── footer ────────────────────────────────────────────────────────────────

    def _footer_fragments():
        return [("class:app_footer", "↑↓ naviga  Invio apre  H help  Q/Esc esce")]

    # ── key bindings ─────────────────────────────────────────────────────────

    kb = KeyBindings()

    @kb.add("up")
    def _go_up(event) -> None:
        state["index"] = (state["index"] - 1) % len(actions)

    @kb.add("down")
    def _go_down(event) -> None:
        state["index"] = (state["index"] + 1) % len(actions)

    @kb.add("enter")
    def _select(event) -> None:
        event.app.exit(result=actions[state["index"]].key)

    @kb.add("q")
    @kb.add("escape")
    def _quit(event) -> None:
        event.app.exit(result="exit")

    @kb.add("h")
    @kb.add("f1")
    def _help(event) -> None:
        event.app.exit(result="help")

    # ── layout ───────────────────────────────────────────────────────────────

    def _home_body():
        wide, menu_width, _, _, _, show_detail = _layout_metrics()

        menu_window = Window(
            width=menu_width,
            content=FormattedTextControl(_menu_fragments),
            always_hide_cursor=True,
        )

        if not show_detail:
            return menu_window

        detail_window = Window(
            content=FormattedTextControl(_detail_fragments),
            always_hide_cursor=True,
        )

        if wide:
            return VSplit([menu_window, Window(width=2), detail_window])

        return HSplit([menu_window, Window(height=1), detail_window])

    layout = Layout(
        HSplit(
            [
                DynamicContainer(_header_window),
                Window(height=1),
                DynamicContainer(_home_body),
                Window(height=1, char="─", style="class:app_divider"),
                Window(
                    height=1,
                    content=FormattedTextControl(_footer_fragments),
                    always_hide_cursor=True,
                ),
            ]
        )
    )

    style = Style.from_dict(
        {
            "": "fg:#D4D4D4",
            "app_brand": "fg:#E8B84B bold",
            "app_tagline": "fg:#7A7A7A",
            "app_header": "fg:#7A7A7A",
            "app_border": "fg:#3A3A3A",
            "app_divider": "fg:#3A3A3A",
            "home_section": "fg:#E8B84B",
            "home_marker": "",
            "home_marker_active": "fg:#E8B84B bold",
            "home_title": "fg:#D4D4D4",
            "home_title_active": "fg:#E8B84B bold",
            "home_summary": "fg:#7A7A7A",
            "home_summary_active": "fg:#7A7A7A",
            "detail_section": "fg:#E8B84B",
            "detail_heading": "fg:#E8B84B bold",
            "detail_text": "fg:#D4D4D4",
            "detail_label": "fg:#7A7A7A",
            "detail_code": "fg:#D4D4D4",
            "app_footer": "fg:#7A7A7A",
        }
    )

    return Application(
        layout=layout,
        key_bindings=kb,
        style=style,
        full_screen=True,
    ).run()


def _show_help_screen() -> None:
    toolkit = _load_prompt_toolkit()
    Application = toolkit["Application"]
    D = toolkit["D"]
    Dialog = toolkit["Dialog"]
    HSplit = toolkit["HSplit"]
    KeyBindings = toolkit["KeyBindings"]
    Label = toolkit["Label"]
    Layout = toolkit["Layout"]
    dialog_width = _dialog_width(90, minimum=56)
    help_text = _wrap_dialog_text(
        [
            "Flussi supportati",
            "",
            "- Strumento OCR > Verifica OCR: analizza se il PDF ha gia testo ricercabile",
            "- Strumento OCR > Esegui OCR: converti PDF scansionato in PDF o TXT",
            "- Comprimi PDF: preset low / medium / high o livello numerico 1-100",
            "- Comprimi PDF in bianco e nero: opzionale, non attiva di default",
            "- Comando libero: incolla una riga come `ocr file.pdf --lang it`",
            "",
            "Controlli",
            "",
            "- Frecce su/giu: naviga nel menu",
            "- Invio: apre l'azione selezionata",
            "- H o F1: apre l'help",
            "- Q o Esc: esce dalla home",
            "- Ctrl+C durante OCR o compressione: annulla l'operazione",
            "",
            "Suggerimenti",
            "",
            "- Verifica OCR propone di avviare Esegui OCR se il PDF non ha testo",
            "- Esegui OCR in TXT: scegli formato TXT nel flusso guidato",
            "- Comprimi PDF custom: scegli `custom` e inserisci un valore 1-100",
            "- Salvataggio custom: scegli prima la cartella e poi il nome file",
            "- Se annulli una compressione, il file parziale viene rimosso.",
        ],
        width=max(32, dialog_width - 8),
    )
    dialog = Dialog(
        title=f"{APP_NAME} help",
        body=HSplit(
            [
                Label(text=help_text),
                Label(
                    text="Invio o Esc chiudono questa schermata.",
                    style="class:dialog_hint",
                ),
            ],
            padding=1,
        ),
        buttons=[],
        with_background=True,
        width=D(preferred=dialog_width),
    )
    kb = KeyBindings()

    @kb.add("enter")
    @kb.add("escape")
    @kb.add("q")
    def _close(event) -> None:
        event.app.exit(result=None)

    Application(
        layout=Layout(dialog.container),
        key_bindings=kb,
        style=_dialog_style(),
        full_screen=True,
        mouse_support=True,
    ).run()


def _show_info_dialog(title: str, text: str) -> None:
    toolkit = _load_prompt_toolkit()
    Application = toolkit["Application"]
    D = toolkit["D"]
    Dialog = toolkit["Dialog"]
    HSplit = toolkit["HSplit"]
    KeyBindings = toolkit["KeyBindings"]
    Label = toolkit["Label"]
    Layout = toolkit["Layout"]
    dialog_width = _dialog_width(72, minimum=44)
    dialog = Dialog(
        title=title,
        body=HSplit(
            [
                Label(text=text),
                Label(
                    text="Invio o Esc chiudono questa schermata.",
                    style="class:dialog_hint",
                ),
            ],
            padding=1,
        ),
        buttons=[],
        with_background=True,
        width=D(preferred=dialog_width),
    )
    kb = KeyBindings()

    @kb.add("enter")
    @kb.add("escape")
    @kb.add("q")
    def _close(event) -> None:
        event.app.exit(result=None)

    Application(
        layout=Layout(dialog.container),
        key_bindings=kb,
        style=_dialog_style(),
        full_screen=True,
        mouse_support=True,
    ).run()


def _ask_text(title: str, text: str, default: str = "") -> str | None:
    toolkit = _load_prompt_toolkit()
    Application = toolkit["Application"]
    D = toolkit["D"]
    Dialog = toolkit["Dialog"]
    HSplit = toolkit["HSplit"]
    KeyBindings = toolkit["KeyBindings"]
    Label = toolkit["Label"]
    Layout = toolkit["Layout"]
    TextArea = toolkit["TextArea"]

    textfield = TextArea(
        text=default,
        multiline=False,
        focus_on_click=True,
    )
    dialog_width = _dialog_width(72, minimum=44)
    dialog = Dialog(
        title=title,
        body=HSplit(
            [
                Label(text=text),
                textfield,
                Label(
                    text="Invio conferma  Esc annulla",
                    style="class:dialog_hint",
                ),
            ],
            padding=1,
        ),
        buttons=[],
        with_background=True,
        width=D(preferred=dialog_width),
    )
    kb = KeyBindings()

    @kb.add("enter")
    def _confirm(event) -> None:
        event.app.exit(result=textfield.text)

    @kb.add("escape")
    @kb.add("c-c")
    def _cancel(event) -> None:
        event.app.exit(result=None)

    result = Application(
        layout=Layout(dialog.container, focused_element=textfield),
        key_bindings=kb,
        style=_dialog_style(),
        full_screen=True,
        mouse_support=True,
    ).run()
    if isinstance(result, str):
        result = result.strip()
    return result


def _ask_choice(title: str, text: str, values: list[tuple[str, str]]) -> str | None:
    toolkit = _load_prompt_toolkit()
    Application = toolkit["Application"]
    D = toolkit["D"]
    Dialog = toolkit["Dialog"]
    HSplit = toolkit["HSplit"]
    KeyBindings = toolkit["KeyBindings"]
    Label = toolkit["Label"]
    Layout = toolkit["Layout"]
    RadioList = toolkit["RadioList"]

    radio_list = RadioList(values=values)
    dialog_width = _dialog_width(72, minimum=44)
    dialog = Dialog(
        title=title,
        body=HSplit(
            [
                Label(text=text),
                radio_list,
                Label(
                    text="Frecce navigano  Invio o click confermano  Esc annulla",
                    style="class:dialog_hint",
                ),
            ],
            padding=1,
        ),
        buttons=[],
        with_background=True,
        width=D(preferred=dialog_width),
    )
    kb = KeyBindings()

    @kb.add("enter", eager=True)
    def _confirm(event) -> None:
        event.app.exit(result=radio_list.values[radio_list._selected_index][0])

    @kb.add("escape")
    @kb.add("c-c")
    def _cancel(event) -> None:
        event.app.exit(result=None)

    return Application(
        layout=Layout(dialog.container, focused_element=radio_list),
        key_bindings=kb,
        style=_dialog_style(),
        full_screen=True,
        mouse_support=True,
    ).run()


def _prompt_output_path(
    title: str,
    input_path: str,
    default_extension: str,
) -> str | None:
    source_path = resolve_user_path(input_path)
    suggested_path = resolve_incremental_output_path(source_path, default_extension)
    save_mode = _ask_choice(
        title,
        "Salvataggio output",
        [
            (
                "default",
                f"Default · stessa cartella ({suggested_path.name})",
            ),
            (
                "custom",
                "Personalizzato · scegli cartella e nome file",
            ),
        ],
    )
    if not save_mode:
        return None
    if save_mode == "default":
        return str(suggested_path)

    destination_dir = _ask_text(
        title,
        "Cartella di destinazione",
        default=str(source_path.parent),
    )
    if destination_dir is None:
        return None
    destination_dir = destination_dir.strip() or str(source_path.parent)

    default_name = source_path.with_suffix(default_extension).name
    file_name = _ask_text(
        title,
        "Nome del file",
        default=default_name,
    )
    if file_name is None or not file_name.strip():
        return None

    output_path = resolve_user_path(destination_dir) / file_name.strip()
    if not output_path.suffix:
        output_path = output_path.with_suffix(default_extension)
    return str(output_path)


def _prompt_ocr_args(input_path_default: str = "") -> argparse.Namespace | None:
    input_path = _ask_text("Esegui OCR", "Percorso del PDF di input", default=input_path_default)
    if not input_path:
        return None
    input_path = _clean_path_input(input_path)
    if not input_path:
        return None
    try:
        ensure_pdf_input(resolve_user_path(input_path))
    except PDFToolError as exc:
        _show_info_dialog("Esegui OCR", f"Percorso non valido:\n\n{exc}")
        return None

    lang = _ask_choice(
        "Esegui OCR",
        "Lingua OCR",
        [
            ("it", "Italiano"),
            ("en", "English"),
            ("it+en", "Italiano + English"),
        ],
    )
    if not lang:
        return None

    output_format = _ask_choice(
        "Esegui OCR",
        "Formato di output",
        [
            ("pdf", "PDF ricercabile"),
            ("txt", "TXT"),
        ],
    )
    if not output_format:
        return None

    output = _prompt_output_path(
        "Esegui OCR",
        input_path,
        ".txt" if output_format == "txt" else ".pdf",
    )
    if output is None:
        return None

    return argparse.Namespace(input=input_path, lang=lang, output=output)


def _prompt_compress_args() -> argparse.Namespace | None:
    input_path = _ask_text("Comprimi PDF", "Percorso del PDF di input")
    if not input_path:
        return None
    input_path = _clean_path_input(input_path)
    if not input_path:
        return None
    try:
        ensure_pdf_input(resolve_user_path(input_path))
    except PDFToolError as exc:
        _show_info_dialog("Comprimi PDF", f"Percorso non valido:\n\n{exc}")
        return None

    level = _ask_choice(
        "Comprimi PDF",
        "Livello di compressione",
        [
            ("low", "low · compressione leggera"),
            ("medium", "medium · bilanciato"),
            ("high", "high · compressione aggressiva"),
            ("custom", "custom · inserisci valore 1-100"),
        ],
    )
    if not level:
        return None
    if level == "custom":
        custom_level = _ask_text(
            "Comprimi PDF",
            "Valore custom tra 1 e 100",
        )
        if not custom_level:
            return None
        level = custom_level

    color_mode = _ask_choice(
        "Comprimi PDF",
        "Modalita colore",
        [
            ("color", "A colori"),
            ("grayscale", "Bianco e nero"),
        ],
    )
    if not color_mode:
        return None

    output = _prompt_output_path("Comprimi PDF", input_path, ".pdf")
    if output is None:
        return None

    return argparse.Namespace(
        input=input_path,
        level=level,
        output=output,
        grayscale=color_mode == "grayscale",
    )


def _prompt_check_args() -> argparse.Namespace | None:
    input_path = _ask_text("Verifica OCR", "Percorso del PDF da analizzare")
    if not input_path:
        return None
    input_path = _clean_path_input(input_path)
    if not input_path:
        return None
    try:
        ensure_pdf_input(resolve_user_path(input_path))
    except PDFToolError as exc:
        _show_info_dialog("Verifica OCR", f"Percorso non valido:\n\n{exc}")
        return None
    return argparse.Namespace(input=input_path)


def _show_check_result(result: CheckOCRResult, input_path: str) -> str | None:
    verdetti = {
        "ocr_needed": "OCR necessario — nessuna pagina ha testo ricercabile.",
        "already_searchable": "Gia ricercabile — OCR non necessario.",
        "mixed": (
            f"Misto — {result.pages_without_text} pagine su "
            f"{result.pages_total} senza testo ricercabile."
        ),
    }
    verdict_text = verdetti[result.verdict]
    col_w = 22
    lines = [
        f"{'Pagine totali':<{col_w}}{result.pages_total}",
        f"{'Pagine con testo':<{col_w}}{result.pages_with_text}",
        f"{'Pagine senza testo':<{col_w}}{result.pages_without_text}",
        f"{'Media caratteri/pag.':<{col_w}}{result.chars_per_page_avg:.0f}",
        "",
        f"Verdetto: {verdict_text}",
    ]
    body_text = "\n".join(lines)

    if result.verdict in {"ocr_needed", "mixed"}:
        return _ask_choice(
            "Verifica OCR — risultato",
            body_text,
            [
                ("ocr", "Esegui OCR su questo file"),
                ("no", "Torna al menu"),
            ],
        )
    else:
        _show_info_dialog("Verifica OCR — risultato", body_text)
        return None


def _run_check_interactive(args: argparse.Namespace) -> int:
    try:
        result = check_ocr(args.input)
    except PDFToolError as exc:
        _show_error(str(exc))
        return 1

    action = _show_check_result(result, str(args.input))
    if action == "ocr":
        ocr_args = _prompt_ocr_args(input_path_default=str(args.input))
        if ocr_args is not None:
            return _run_ocr_interactive(ocr_args)
    return 0


def _clean_path_input(path: str) -> str:
    """Rimuove whitespace e virgolette circostanti da un path incollato nella TUI."""
    path = path.strip()
    if len(path) >= 2 and path[0] in ('"', "'") and path[-1] == path[0]:
        path = path[1:-1].strip()
    return path


def _prompt_manual_command() -> str | None:
    return _ask_text(
        "Comando libero",
        "Scrivi un comando `ocr ...` o `compress ...`",
    )


def _pause(message: str = "Premi Invio per tornare al menu") -> None:
    try:
        _console().input(f"[bold]{message}.[/]")
    except EOFError:
        pass


def _show_error(message: str) -> None:
    rich = _load_rich()
    Panel = rich["Panel"]
    console = _console()
    console.print(
        Panel(
            f"[#E85B4B]{message}[/]",
            title="[bold #E85B4B]Errore[/]",
            border_style="#E85B4B",
        )
    )
    _pause()


def _run_with_progress(
    title: str,
    runner: Callable[[Callable[[OperationProgress], None]], object],
):
    rich = _load_rich()
    Console = rich["Console"]
    Panel = rich["Panel"]
    Progress = rich["Progress"]
    SpinnerColumn = rich["SpinnerColumn"]
    BarColumn = rich["BarColumn"]
    TaskProgressColumn = rich["TaskProgressColumn"]
    TextColumn = rich["TextColumn"]
    TimeElapsedColumn = rich["TimeElapsedColumn"]
    Table = rich["Table"]
    Text = rich["Text"]

    console = Console()
    console.clear()
    console.print(
        Panel(
            Text(
                title + "\nPremi Ctrl+C per annullare l'operazione.",
                justify="left",
                style="#D4D4D4",
            ),
            title=f"[bold #E8B84B]{APP_NAME}[/]",
            border_style="#3A3A3A",
            padding=(0, 1),
        )
    )

    progress = Progress(
        SpinnerColumn(style="#E8B84B"),
        TextColumn("[progress.description]{task.description}", style="#D4D4D4"),
        BarColumn(bar_width=None, complete_style="#E8B84B", finished_style="#E8B84B"),
        TaskProgressColumn(style="#7A7A7A"),
        TimeElapsedColumn(style="#7A7A7A"),
        console=console,
        expand=True,
    )
    task_id = progress.add_task("Avvio operazione", total=None)

    def _on_progress(update: OperationProgress) -> None:
        progress.update(
            task_id,
            description=update.message,
            total=update.total,
            completed=update.completed,
        )

    try:
        with progress:
            result = runner(_on_progress)
    except PDFToolError as exc:
        console.print(
            Panel(
                f"[#E85B4B]{exc}[/]",
                title="[bold #E85B4B]Errore[/]",
                border_style="#E85B4B",
            )
        )
        _pause()
        return None
    except KeyboardInterrupt:
        console.print(
            Panel(
                "[#7A7A7A]Operazione annullata dall'utente.[/]",
                title="[#7A7A7A]Operazione annullata[/]",
                border_style="#3A3A3A",
            )
        )
        _pause()
        return None

    table = Table.grid(padding=(0, 1))
    if isinstance(result, OCRResult):
        output_label = "PDF ricercabile" if result.output_type == "pdf" else "TXT"
        table.add_row("Output", str(result.output_path))
        table.add_row("Tipo", output_label)
        table.add_row("Pagine", str(result.pages))
        success_title = "OCR completato"
    elif isinstance(result, CompressionResult):
        table.add_row("Output", str(result.output_path))
        table.add_row("Livello", result.level)
        table.add_row(
            "Modalita",
            "Bianco e nero" if result.grayscale else "A colori",
        )
        table.add_row(
            "Dimensioni",
            format_size_change(result.size_before, result.size_after),
        )
        success_title = "Compressione completata"
    else:
        table.add_row("Esito", str(result))
        success_title = "Operazione completata"

    console.print(
        Panel(
            table,
            title=f"[bold #4BE87A]{success_title}[/]",
            border_style="#4BE87A",
        )
    )
    _pause()
    return result


def _run_ocr_interactive(args: argparse.Namespace) -> int:
    result = _run_with_progress(
        "Esegui OCR",
        lambda progress_callback: run_ocr(
            input_path=args.input,
            output_path=args.output,
            lang=args.lang,
            progress_callback=progress_callback,
        ),
    )
    return 0 if result is not None else 1


def _run_compress_interactive(args: argparse.Namespace) -> int:
    result = _run_with_progress(
        "Comprimi PDF",
        lambda progress_callback: compress_pdf(
            input_path=args.input,
            output_path=args.output,
            level=args.level,
            grayscale=getattr(args, "grayscale", False),
            progress_callback=progress_callback,
        ),
    )
    return 0 if result is not None else 1


def dispatch_interactive_command(
    command_line: str,
    *,
    parser_factory: Callable[[], argparse.ArgumentParser],
    executor: Callable[[argparse.Namespace], int],
) -> int:
    if not command_line.strip():
        return 0

    try:
        tokens = shlex.split(command_line)
    except ValueError as exc:
        raise PDFToolError(f"Sintassi del comando non valida: {exc}") from exc

    if not tokens:
        return 0

    command = tokens[0].lower()

    if command in EXIT_COMMANDS:
        return -1
    if command == "help" and len(tokens) == 1:
        _show_help_screen()
        return 0
    if command == "interactive":
        return 0
    if command == "check" and len(tokens) == 1:
        args = _prompt_check_args()
        return 0 if args is None else _run_check_interactive(args)
    if command == "ocr" and len(tokens) == 1:
        args = _prompt_ocr_args()
        return 0 if args is None else _run_ocr_interactive(args)
    if command == "compress" and len(tokens) == 1:
        args = _prompt_compress_args()
        return 0 if args is None else _run_compress_interactive(args)

    parser = parser_factory()
    try:
        args = parser.parse_args(tokens)
    except SystemExit as exc:
        raise PDFToolError(
            "Comando non valido. Usa il menu guidato oppure apri Help."
        ) from exc

    if args.command == "check":
        return _run_check_interactive(args)
    if args.command == "ocr":
        return _run_ocr_interactive(args)
    if args.command == "compress":
        return _run_compress_interactive(args)
    if args.command == "interactive":
        return 0
    return executor(args)


def run_interactive_app(
    *,
    parser_factory: Callable[[], argparse.ArgumentParser],
    executor: Callable[[argparse.Namespace], int],
) -> int:
    while True:
        try:
            action = _show_home_menu()
        except PDFToolError as exc:
            _show_error(str(exc))
            continue
        if action in {None, "exit"}:
            return 0
        if action == "help":
            _show_help_screen()
            continue
        if action == "ocr_tool":
            sub = _show_ocr_submenu()
            if sub == "check":
                args = _prompt_check_args()
                if args is not None:
                    _run_check_interactive(args)
            elif sub == "ocr":
                args = _prompt_ocr_args()
                if args is not None:
                    _run_ocr_interactive(args)
            continue
        if action == "compress":
            args = _prompt_compress_args()
            if args is not None:
                _run_compress_interactive(args)
            continue
        if action == "manual":
            command = _prompt_manual_command()
            if command:
                try:
                    result = dispatch_interactive_command(
                        command,
                        parser_factory=parser_factory,
                        executor=executor,
                    )
                except PDFToolError as exc:
                    _show_error(str(exc))
                    continue
                if result == -1:
                    return 0
            continue
