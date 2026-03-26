from __future__ import annotations

import argparse
import shlex
from dataclasses import dataclass
from pathlib import Path
from shutil import get_terminal_size
from textwrap import shorten, wrap
from typing import Callable

from .compress import CompressionResult, compress_pdf
from .errors import PDFToolError
from .ocr import OCRResult, run_ocr
from .progress import OperationProgress
from .utils import format_size_change, resolve_incremental_output_path

EXIT_COMMANDS = {"exit", "quit", ":q"}
APP_NAME = "PyDF Tool"
APP_TAGLINE = "terminal PDF workflow"
APP_SUMMARY = "OCR, compressione, salvataggio guidato e annullamento con Ctrl+C."
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
            "selected": "bg:#f5f5f5 fg:#1e1e1e",
            "dialog": "bg:#1e1e1e fg:#d4d4d4",
            "frame.border": "fg:#8a8a8a",
            "dialog frame.label": "fg:#e5e5e5 bold",
            "dialog.body": "bg:#1e1e1e fg:#d4d4d4",
            "dialog.body label": "bg:#1e1e1e fg:#f0f0f0",
            "dialog.body text-area": "bg:#2a2a2a fg:#f5f5f5",
            "dialog.body text-area.prompt": "bg:#2a2a2a fg:#a5a5a5",
            "dialog.body text-area cursor": "bg:#f5f5f5 fg:#1e1e1e",
            "dialog.body text-area last-line": "nounderline",
            "dialog_hint": "bg:#1e1e1e fg:#9f9f9f",
            "validation-toolbar": "bg:#3a3a3a fg:#f5f5f5",
            "dialog shadow": "bg:#1e1e1e",
            "button": "bg:#1e1e1e fg:#9f9f9f",
            "button.arrow": "fg:#9f9f9f",
            "button.focused": "bg:#2a2a2a fg:#ffffff bold",
            "button.focused.arrow": "fg:#ffffff bold",
            "radio": "fg:#9f9f9f",
            "radio-selected": "fg:#ffffff bold",
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
            key="ocr",
            title="OCR assistito",
            summary="PDF scansionato -> PDF ricercabile o TXT",
            detail=(
                "Renderizza le pagine, applica Tesseract e mostra avanzamento "
                "pagina per pagina."
            ),
            example="pydf-tool ocr scansione.pdf --lang it+en --output scansione.txt",
        ),
        MenuAction(
            key="compress",
            title="Compressione",
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

    def _header_state() -> tuple[str, list[str]]:
        try:
            columns = get_app().output.get_size().columns
        except Exception:
            columns = _terminal_columns()

        line_width = max(20, columns - 2)
        tagline_width = max(0, line_width - len(APP_NAME) - 2)
        tagline = ""
        if tagline_width >= 10:
            tagline = shorten(APP_TAGLINE, width=tagline_width, placeholder="...")
        summary_lines = _wrap_lines(APP_SUMMARY, line_width, 2)
        return tagline, summary_lines

    def _header_fragments():
        tagline, summary_lines = _header_state()
        fragments: list[tuple[str, str]] = [("class:app_brand", APP_NAME)]
        if tagline:
            fragments.append(("class:app_tagline", f"  {tagline}"))
        for line in summary_lines:
            fragments.append(("", "\n"))
            fragments.append(("class:app_header", line))
        return fragments

    def _header_window():
        _, summary_lines = _header_state()
        return Window(
            height=1 + len(summary_lines),
            content=FormattedTextControl(_header_fragments),
            always_hide_cursor=True,
        )

    def _layout_metrics() -> tuple[bool, int, int]:
        try:
            columns = get_app().output.get_size().columns
        except Exception:
            columns = 120

        if columns >= 110:
            menu_width = min(40, max(32, columns // 3))
            detail_width = max(28, columns - menu_width - 6)
            return True, menu_width, detail_width

        stacked_width = max(28, columns - 4)
        return False, stacked_width, stacked_width

    def _menu_fragments():
        _, menu_width, _ = _layout_metrics()
        text_width = max(18, menu_width - 4)
        fragments: list[tuple[str, str]] = [("class:home_section", "Azioni\n\n")]
        for index, action in enumerate(actions):
            selected = index == state["index"]
            marker_style = "class:home_marker_active" if selected else "class:home_marker"
            title_style = "class:home_title_active" if selected else "class:home_title"
            summary_style = (
                "class:home_summary_active" if selected else "class:home_summary"
            )
            indicator = "> " if selected else "  "
            fragments.append((marker_style, indicator))
            fragments.append((title_style, _fit_line(action.title, text_width) + "\n"))
            fragments.append(
                (summary_style, "  " + _fit_line(action.summary, text_width) + "\n\n")
            )
        return fragments

    def _detail_fragments():
        action = actions[state["index"]]
        _, _, detail_width = _layout_metrics()
        fragments: list[tuple[str, str]] = [("class:detail_section", "Anteprima\n\n")]
        for line in _wrap_lines(action.title, detail_width, 1):
            fragments.append(("class:detail_heading", line + "\n"))
        fragments.append(("class:detail_text", "\n"))
        for line in _wrap_lines(action.detail, detail_width, 3):
            fragments.append(("class:detail_text", line + "\n"))
        fragments.append(("class:detail_text", "\n"))
        fragments.append(("class:detail_label", "Comando\n"))
        for line in _wrap_lines(action.example, detail_width, 2):
            fragments.append(("class:detail_code", line + "\n"))
        return fragments

    def _footer_fragments():
        return [
            (
                "class:app_footer",
                "↑↓ naviga  Invio apre  H help  Q/Esc esce",
            )
        ]

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

    def _home_body():
        wide, menu_width, _ = _layout_metrics()
        menu_window = Window(
            width=menu_width,
            content=FormattedTextControl(_menu_fragments),
            always_hide_cursor=True,
        )
        detail_window = Window(
            content=FormattedTextControl(_detail_fragments),
            always_hide_cursor=True,
        )

        if wide:
            return VSplit(
                [
                    menu_window,
                    Window(width=1, char="│", style="class:app_divider"),
                    detail_window,
                ]
            )

        return HSplit(
            [
                menu_window,
                Window(height=1, char="─", style="class:app_divider"),
                detail_window,
            ]
        )

    layout = Layout(
        HSplit(
            [
                DynamicContainer(_header_window),
                Window(height=1, char="─", style="class:app_divider"),
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
            "": "bg:#1e1e1e fg:#d4d4d4",
            "app_brand": "fg:#f0f0f0 bold",
            "app_tagline": "fg:#8a8a8a",
            "app_header": "fg:#9a9a9a",
            "app_divider": "fg:#5f5f5f",
            "home_section": "fg:#a8a8a8 bold",
            "home_marker": "fg:#1e1e1e",
            "home_marker_active": "fg:#f0f0f0 bold",
            "home_title": "fg:#cfcfcf",
            "home_title_active": "fg:#ffffff bold",
            "home_summary": "fg:#777777",
            "home_summary_active": "fg:#9a9a9a",
            "detail_section": "fg:#a8a8a8 bold",
            "detail_heading": "fg:#ffffff bold",
            "detail_text": "fg:#cfcfcf",
            "detail_label": "fg:#8a8a8a bold",
            "detail_code": "fg:#d8d8d8",
            "app_footer": "fg:#9a9a9a",
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
            "- OCR: PDF scansionato -> PDF ricercabile o file .txt",
            "- Compressione: preset low / medium / high o livello numerico 1-100",
            "- Compressione in bianco e nero: opzionale e non attiva di default",
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
            "- OCR in `.txt`: scegli il formato TXT nel flusso guidato",
            "- Compressione custom: scegli `custom` e inserisci un valore 1-100",
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

    return Application(
        layout=Layout(dialog.container, focused_element=textfield),
        key_bindings=kb,
        style=_dialog_style(),
        full_screen=True,
        mouse_support=True,
    ).run()


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
                    text="Frecce navigano  Invio conferma  Esc annulla",
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
        event.app.exit(result=radio_list.current_value)

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
    source_path = Path(input_path).expanduser()
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

    output_path = Path(destination_dir).expanduser() / file_name.strip()
    if not output_path.suffix:
        output_path = output_path.with_suffix(default_extension)
    return str(output_path)


def _prompt_ocr_args() -> argparse.Namespace | None:
    input_path = _ask_text("OCR assistito", "Percorso del PDF di input")
    if not input_path:
        return None

    lang = _ask_choice(
        "OCR assistito",
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
        "OCR assistito",
        "Formato di output",
        [
            ("pdf", "PDF ricercabile"),
            ("txt", "TXT"),
        ],
    )
    if not output_format:
        return None

    output = _prompt_output_path(
        "OCR assistito",
        input_path,
        ".txt" if output_format == "txt" else ".pdf",
    )
    if output is None:
        return None

    return argparse.Namespace(input=input_path, lang=lang, output=output)


def _prompt_compress_args() -> argparse.Namespace | None:
    input_path = _ask_text("Compressione", "Percorso del PDF di input")
    if not input_path:
        return None

    level = _ask_choice(
        "Compressione",
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
            "Compressione",
            "Valore custom tra 1 e 100",
        )
        if not custom_level:
            return None
        level = custom_level

    color_mode = _ask_choice(
        "Compressione",
        "Modalita colore",
        [
            ("color", "A colori"),
            ("grayscale", "Bianco e nero"),
        ],
    )
    if not color_mode:
        return None

    output = _prompt_output_path("Compressione", input_path, ".pdf")
    if output is None:
        return None

    return argparse.Namespace(
        input=input_path,
        level=level,
        output=output,
        grayscale=color_mode == "grayscale",
    )


def _prompt_manual_command() -> str | None:
    return _ask_text(
        "Comando libero",
        "Scrivi un comando `ocr ...` o `compress ...`",
    )


def _pause(message: str = "Premi Invio per tornare al menu") -> None:
    _console().input(f"[bold]{message}.[/]")


def _show_error(message: str) -> None:
    rich = _load_rich()
    Panel = rich["Panel"]
    console = _console()
    console.print(
        Panel(
            message,
            title="[bold]Errore[/]",
            border_style="white",
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
            ),
            title=f"[bold]{APP_NAME}[/]",
            border_style="white",
            padding=(0, 1),
        )
    )

    progress = Progress(
        SpinnerColumn(style="white"),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(bar_width=None, complete_style="white", finished_style="white"),
        TaskProgressColumn(),
        TimeElapsedColumn(),
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
                str(exc),
                title="[bold]Errore[/]",
                border_style="white",
            )
        )
        _pause()
        return None
    except KeyboardInterrupt:
        console.print(
            Panel(
                "Operazione annullata dall'utente.",
                title="[bold]Operazione annullata[/]",
                border_style="white",
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
            title=f"[bold]{success_title}[/]",
            border_style="white",
        )
    )
    _pause()
    return result


def _run_ocr_interactive(args: argparse.Namespace) -> int:
    result = _run_with_progress(
        "OCR assistito",
        lambda progress_callback: run_ocr(
            input_path=args.input,
            output_path=args.output,
            lang=args.lang,
            progress_callback=progress_callback,
        ),
    )
    return 0 if result is not None else 0


def _run_compress_interactive(args: argparse.Namespace) -> int:
    result = _run_with_progress(
        "Compressione PDF",
        lambda progress_callback: compress_pdf(
            input_path=args.input,
            output_path=args.output,
            level=args.level,
            grayscale=getattr(args, "grayscale", False),
            progress_callback=progress_callback,
        ),
    )
    return 0 if result is not None else 0


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
        if action == "ocr":
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
