from __future__ import annotations

import argparse
import shlex
import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.reactive import reactive
from textual.screen import ModalScreen, Screen
from textual.widgets import Button, Input, ListItem, ListView, ProgressBar, Static

from .check_ocr import CheckOCRResult, check_ocr
from .compress import CompressionResult, compress_pdf
from .errors import PDFToolError
from .ocr import OCRResult, run_ocr
from .progress import OperationProgress
from .utils import (
    ensure_pdf_input,
    format_size_change,
    resolve_incremental_output_path,
    resolve_user_path,
)

# ── Costanti ──────────────────────────────────────────────────────────────────

EXIT_COMMANDS = {"exit", "quit", ":q"}

_HEADER_TEXT = """\
╠══ PyDF Tool ══╣
launcher TUI per OCR, compressione e supporto
scegli uno strumento per continuare"""

_OCR_HEADER_TEXT = """\
OCR
verifica un PDF oppure avvia subito l'OCR guidato
scegli l'azione da eseguire"""


@dataclass(frozen=True)
class MenuEntry:
    key: str
    title: str
    summary: str
    preview_title: str
    preview_body: str
    preview_hint: str


_HOME_MENU_ITEMS: list[MenuEntry] = [
    MenuEntry(
        key="ocr-menu",
        title="OCR",
        summary="Verifica un PDF o avvia l'OCR guidato.",
        preview_title="Suite OCR",
        preview_body=(
            "Apri il sottomenu OCR.\n"
            "Da qui puoi controllare se il PDF ha gia testo estraibile "
            "oppure lanciare direttamente il wizard OCR."
        ),
        preview_hint="Invio apre il sottomenu OCR",
    ),
    MenuEntry(
        key="compress",
        title="Comprimi PDF",
        summary="Riduci il peso del file con Ghostscript.",
        preview_title="Compressione PDF",
        preview_body=(
            "Riduci le dimensioni del PDF con preset guidati.\n"
            "La CLI supporta anche livelli numerici 1-100 e la conversione in grigio."
        ),
        preview_hint="Invio apre il wizard di compressione",
    ),
    MenuEntry(
        key="help",
        title="Help",
        summary="Controlli rapidi, flussi supportati e suggerimenti.",
        preview_title="Guida rapida",
        preview_body=(
            "Apri la schermata di help della TUI.\n"
            "Disponibile anche in qualsiasi momento con H o F1."
        ),
        preview_hint="Invio apre l'help",
    ),
]

_OCR_MENU_ITEMS: list[MenuEntry] = [
    MenuEntry(
        key="check",
        title="Verifica OCR",
        summary="Analizza se il PDF ha gia testo ricercabile.",
        preview_title="Verifica OCR",
        preview_body=(
            "Legge i metadati del PDF e stima se OCR e necessario.\n"
            "Se serve, potrai poi passare direttamente al wizard OCR."
        ),
        preview_hint="Invio apre la verifica OCR",
    ),
    MenuEntry(
        key="ocr",
        title="Esegui OCR",
        summary="Converti un PDF scansionato in PDF ricercabile o TXT.",
        preview_title="OCR guidato",
        preview_body=(
            "Wizard a passi per scegliere file, lingua, formato e output.\n"
            "Supporta italiano, inglese e combinazione it+en."
        ),
        preview_hint="Invio apre il wizard OCR",
    ),
    MenuEntry(
        key="back",
        title="Torna al menu",
        summary="Rientra nella home principale del launcher.",
        preview_title="Ritorno alla home",
        preview_body=(
            "Chiude il sottomenu OCR e riporta al launcher principale."
        ),
        preview_hint="Invio torna alla home",
    ),
]

_FOOTER_HOME = "↑↓ naviga   Invio apre   H/F1 help   Q/Esc esci"
_FOOTER_SUBMENU = "↑↓ naviga   Invio apre   Esc torna indietro"
_FOOTER_WIZARD = "Invio avanza   Esc torna indietro"

_HELP_TEXT = """\
Flussi supportati

  · Verifica OCR: analizza se il PDF ha già testo ricercabile
  · Esegui OCR: converti PDF scansionato in PDF ricercabile o TXT
  · Comprimi PDF: preset low / medium / high

Controlli

  · ↑ / ↓  naviga nel menu
  · Invio   apre l'azione selezionata
  · H o F1  apre l'help
  · Q o Esc esce dalla home
  · Ctrl+C  annulla OCR o compressione in corso

Suggerimenti

  · OCR apre un sottomenu con Verifica OCR e Esegui OCR
  · Verifica OCR propone di avviare Esegui OCR se il PDF non ha testo
  · Esegui OCR in TXT: scegli formato TXT nel flusso guidato
  · Se annulli una compressione, il file parziale viene rimosso

─────────────────────────────────────────────────
Invio · Esc · Q chiudono questa schermata"""

_HELP_TEXT_PLAIN = """\
PyDF Tool — strumenti PDF da riga di comando

  pydf-tool ocr FILE [--lang LINGUA] [--output PATH]
  pydf-tool compress FILE [--level low|medium|high|1-100] [--output PATH] [--grayscale]
  pydf-tool check FILE

Per OCR, l'output è PDF o TXT in base all'estensione di PATH.
Usa 'pydf-tool COMANDO --help' per dettagli sul singolo comando."""


# ── HelpScreen ────────────────────────────────────────────────────────────────

class HelpScreen(ModalScreen):
    BINDINGS = [
        Binding("escape", "dismiss_screen", "Chiudi"),
        Binding("enter", "dismiss_screen", "Chiudi"),
        Binding("q", "dismiss_screen", "Chiudi"),
    ]

    def compose(self) -> ComposeResult:
        yield ScrollableContainer(
            Static(_HELP_TEXT, id="help-content"),
            id="help-container",
        )

    def action_dismiss_screen(self) -> None:
        self.dismiss()


class MenuEntryItem(ListItem):
    def __init__(self, entry: MenuEntry) -> None:
        super().__init__(id=entry.key)
        self.entry = entry

    def compose(self) -> ComposeResult:
        yield Static(self.entry.title, classes="menu-item-title")
        yield Static(self.entry.summary, classes="menu-item-summary")


# ── HomeScreen ────────────────────────────────────────────────────────────────

class HomeScreen(Screen):
    BINDINGS = [
        Binding("q", "quit_app", "Esci"),
        Binding("escape", "quit_app", "Esci"),
        Binding("h", "push_help", "Help"),
        Binding("f1", "push_help", "Help"),
    ]

    def compose(self) -> ComposeResult:
        yield Static(_HEADER_TEXT, id="header")
        with Horizontal(id="body"):
            with Vertical(id="menu-panel"):
                yield Static("Strumenti", classes="panel-title")
                yield ListView(
                    *[MenuEntryItem(entry) for entry in _HOME_MENU_ITEMS],
                    id="menu-list",
                )
            with Vertical(id="preview-panel"):
                yield Static("Dettagli", classes="panel-title")
                yield Static("", id="preview-title")
                yield Static("", id="preview-body")
                yield Static("", id="preview-hint")
        yield Static(_FOOTER_HOME, id="footer-bar")

    def on_mount(self) -> None:
        self._set_preview(_HOME_MENU_ITEMS[0].key)
        self.query_one("#menu-list", ListView).focus()

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        if event.item is not None:
            self._set_preview(event.item.id)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if event.item is not None:
            self._dispatch_action(event.item.id)

    def _set_preview(self, action_id: str) -> None:
        entry = next((item for item in _HOME_MENU_ITEMS if item.key == action_id), None)
        if entry is None:
            return
        self.query_one("#preview-title", Static).update(entry.preview_title)
        self.query_one("#preview-body", Static).update(entry.preview_body)
        self.query_one("#preview-hint", Static).update(entry.preview_hint)

    def _dispatch_action(self, action_id: str) -> None:
        if action_id == "ocr-menu":
            self.app.push_screen(OCRMenuScreen())
        elif action_id == "compress":
            self.app.push_screen(WizardScreen(mode=action_id))
        elif action_id == "help":
            self.app.push_screen(HelpScreen())

    def action_quit_app(self) -> None:
        self.app.exit(0)

    def action_push_help(self) -> None:
        self.app.push_screen(HelpScreen())


class OCRMenuScreen(Screen):
    BINDINGS = [
        Binding("escape", "go_back", "Indietro"),
        Binding("h", "push_help", "Help"),
        Binding("f1", "push_help", "Help"),
    ]

    def compose(self) -> ComposeResult:
        yield Static(_OCR_HEADER_TEXT, id="header")
        with Horizontal(id="body"):
            with Vertical(id="menu-panel"):
                yield Static("Azioni OCR", classes="panel-title")
                yield ListView(
                    *[MenuEntryItem(entry) for entry in _OCR_MENU_ITEMS],
                    id="menu-list",
                )
            with Vertical(id="preview-panel"):
                yield Static("Dettagli", classes="panel-title")
                yield Static("", id="preview-title")
                yield Static("", id="preview-body")
                yield Static("", id="preview-hint")
        yield Static(_FOOTER_SUBMENU, id="footer-bar")

    def on_mount(self) -> None:
        self._set_preview(_OCR_MENU_ITEMS[0].key)
        self.query_one("#menu-list", ListView).focus()

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        if event.item is not None:
            self._set_preview(event.item.id)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if event.item is not None:
            self._dispatch_action(event.item.id)

    def _set_preview(self, action_id: str) -> None:
        entry = next((item for item in _OCR_MENU_ITEMS if item.key == action_id), None)
        if entry is None:
            return
        self.query_one("#preview-title", Static).update(entry.preview_title)
        self.query_one("#preview-body", Static).update(entry.preview_body)
        self.query_one("#preview-hint", Static).update(entry.preview_hint)

    def _dispatch_action(self, action_id: str) -> None:
        if action_id == "check":
            self.app.push_screen(CheckInputScreen())
        elif action_id == "ocr":
            self.app.push_screen(WizardScreen(mode="ocr"))
        else:
            self.app.pop_screen()

    def action_go_back(self) -> None:
        self.app.pop_screen()

    def action_push_help(self) -> None:
        self.app.push_screen(HelpScreen())


# ── WizardScreen (Phase 3) ────────────────────────────────────────────────────

@dataclass
class WizardStep:
    name: str
    prompt: str
    placeholder: str
    choices: list[str] | None = None


_WIZARD_STEPS: dict[str, list[WizardStep]] = {
    "ocr": [
        WizardStep("File",    "Percorso del PDF da elaborare:",    "es. ~/Documents/doc.pdf"),
        WizardStep("Lingua",  "Lingua del documento:",              "it / en / it+en", choices=["it", "en", "it+en"]),
        WizardStep("Formato", "Formato output:",                    "pdf / txt",        choices=["pdf", "txt"]),
        WizardStep("Output",  "Percorso file di output:",           "es. ~/Desktop/out.pdf (vuoto = automatico)"),
    ],
    "compress": [
        WizardStep("File",    "Percorso del PDF da comprimere:",   "es. ~/Documents/doc.pdf"),
        WizardStep("Livello", "Livello di compressione:",           "low / medium / high", choices=["low", "medium", "high"]),
        WizardStep("Colore",  "Modalità colore:",                   "color / gray",         choices=["color", "gray"]),
        WizardStep("Output",  "Percorso file di output:",           "es. ~/Desktop/out.pdf (vuoto = automatico)"),
    ],
}


class WizardScreen(Screen):
    BINDINGS = [
        Binding("escape", "go_back", "Indietro"),
    ]

    current_step: reactive[int] = reactive(0)

    def __init__(self, mode: str, prefill_path: str = "") -> None:
        super().__init__()
        self._mode = mode
        self._steps = _WIZARD_STEPS[mode]
        self._values: dict[str, str] = {}
        self._prefill_path = prefill_path

    def compose(self) -> ComposeResult:
        title = "Esegui OCR" if self._mode == "ocr" else "Comprimi PDF"
        yield Static("", id="step-indicator")
        yield Static(title, id="wizard-title")
        yield Static("", id="step-prompt")
        yield Input(id="step-input")
        yield Static("", id="step-error", classes="error-label")
        yield Static(_FOOTER_WIZARD, id="footer-bar")

    def on_mount(self) -> None:
        self._render_step(0)
        if self._prefill_path:
            self.query_one("#step-input", Input).value = self._prefill_path

    def watch_current_step(self, step: int) -> None:
        self._render_step(step)

    def _render_step(self, step: int) -> None:
        steps = self._steps
        parts = []
        for i, s in enumerate(steps):
            marker = "▶ " if i == step else "   "
            parts.append(f"{marker}{i + 1}. {s.name}")
        self.query_one("#step-indicator", Static).update("  ".join(parts))
        self.query_one("#step-prompt", Static).update(steps[step].prompt)
        inp = self.query_one("#step-input", Input)
        inp.placeholder = steps[step].placeholder
        inp.value = self._values.get(steps[step].name.lower(), "")
        inp.focus()
        self.query_one("#step-error", Static).update("")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self._advance(event.value.strip())

    def _advance(self, value: str) -> None:
        step = self.current_step
        s = self._steps[step]
        err = self._validate(step, value, s)
        if err:
            self.query_one("#step-error", Static).update(err)
            return
        self._values[s.name.lower()] = value
        if step + 1 < len(self._steps):
            self.current_step = step + 1
        else:
            self._finish()

    def _validate(self, step: int, value: str, s: WizardStep) -> str:
        if step == 0:  # File
            if not value:
                return "Percorso obbligatorio."
            try:
                ensure_pdf_input(resolve_user_path(value))
            except PDFToolError as e:
                return str(e)
        elif s.choices and value not in s.choices:
            return f"Scegli tra: {' · '.join(s.choices)}"
        return ""

    def _finish(self) -> None:
        args = self._build_args()
        self.app.push_screen(ProgressScreen(mode=self._mode, args=args))

    def _build_args(self) -> dict:
        v = self._values
        if self._mode == "ocr":
            output_raw = v.get("output", "").strip()
            fmt = v.get("formato", "pdf")
            ext = ".txt" if fmt == "txt" else ".pdf"
            in_path = resolve_user_path(v["file"])
            if output_raw:
                out_path = resolve_user_path(output_raw)
                if not out_path.suffix:
                    out_path = out_path.with_suffix(ext)
            else:
                out_path = resolve_incremental_output_path(in_path, ext)
            return {
                "input": in_path,
                "lang": v.get("lingua", "it"),
                "output": out_path,
            }
        else:  # compress
            output_raw = v.get("output", "").strip()
            in_path = resolve_user_path(v["file"])
            if output_raw:
                out_path = resolve_user_path(output_raw)
                if not out_path.suffix:
                    out_path = out_path.with_suffix(".pdf")
            else:
                out_path = resolve_incremental_output_path(in_path, ".pdf")
            return {
                "input": in_path,
                "level": v.get("livello", "medium"),
                "grayscale": v.get("colore", "color") == "gray",
                "output": out_path,
            }

    def action_go_back(self) -> None:
        if self.current_step > 0:
            self.current_step -= 1
        else:
            self.app.pop_screen()


# ── CheckInputScreen + CheckResultScreen (Phase 4) ────────────────────────────

class CheckInputScreen(Screen):
    BINDINGS = [Binding("escape", "go_back", "Annulla")]

    def compose(self) -> ComposeResult:
        yield Static("Verifica OCR", id="wizard-title")
        yield Static("Percorso del PDF da verificare:", id="step-prompt")
        yield Input(placeholder="es. ~/Documents/doc.pdf", id="check-input")
        yield Static("", id="check-error", classes="error-label")
        yield Static("Invio conferma   Esc annulla", id="footer-bar")

    def on_mount(self) -> None:
        self.query_one("#check-input", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        path_str = event.value.strip()
        if not path_str:
            self.query_one("#check-error", Static).update("Percorso obbligatorio.")
            return
        try:
            path = resolve_user_path(path_str)
            ensure_pdf_input(path)
        except PDFToolError as e:
            self.query_one("#check-error", Static).update(str(e))
            return
        try:
            result = check_ocr(path)
        except PDFToolError as e:
            self.query_one("#check-error", Static).update(str(e))
            return
        self.app.push_screen(CheckResultScreen(result=result, input_path=path))

    def action_go_back(self) -> None:
        self.app.pop_screen()


def _verdict_label(verdict: str) -> str:
    return {
        "ocr_needed": "OCR necessario",
        "already_searchable": "Già ricercabile",
        "mixed": "Parzialmente ricercabile",
    }.get(verdict, verdict)


class CheckResultScreen(Screen):
    BINDINGS = [
        Binding("escape", "go_home", "Menu"),
        Binding("up", "focus_prev_button", "Prec", show=False),
        Binding("left", "focus_prev_button", "Prec", show=False),
        Binding("shift+tab", "focus_prev_button", "Prec", show=False),
        Binding("down", "focus_next_button", "Succ", show=False),
        Binding("right", "focus_next_button", "Succ", show=False),
        Binding("tab", "focus_next_button", "Succ", show=False),
        Binding("enter", "default_action", "Continua"),
    ]

    def __init__(self, result: CheckOCRResult, input_path: Path) -> None:
        super().__init__()
        self._result = result
        self._input_path = input_path

    def compose(self) -> ComposeResult:
        r = self._result
        table = (
            f"Pagine totali          {r.pages_total}\n"
            f"Pagine con testo       {r.pages_with_text}\n"
            f"Pagine senza testo     {r.pages_without_text}\n"
            f"Media caratteri/pag.   {r.chars_per_page_avg:.0f}\n\n"
            f"Verdetto: {_verdict_label(r.verdict)}"
        )
        yield Static("Verifica OCR — risultato", id="header")
        yield Static(table, id="result-table")
        with Vertical(id="result-buttons"):
            if r.verdict in ("ocr_needed", "mixed"):
                yield Button("Esegui OCR su questo file", id="btn-run-ocr")
            yield Button("Torna al menu", id="btn-home")
        yield Static("↑↓ cambia pulsante   Invio conferma   Esc torna al menu", id="footer-bar")

    def on_mount(self) -> None:
        self._focus_first_button()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-run-ocr":
            self._launch_ocr()
        else:
            self._go_home()

    def action_default_action(self) -> None:
        focused = self.app.focused
        if isinstance(focused, Button):
            self._activate_button(focused.id)
            return
        if self._result.verdict in ("ocr_needed", "mixed"):
            self._launch_ocr()
            return
        self._go_home()

    def action_go_home(self) -> None:
        self._go_home()

    def action_focus_next_button(self) -> None:
        self._move_button_focus(1)

    def action_focus_prev_button(self) -> None:
        self._move_button_focus(-1)

    def _buttons(self) -> list[Button]:
        return list(self.query(Button))

    def _focus_first_button(self) -> None:
        buttons = self._buttons()
        if buttons:
            buttons[0].focus()

    def _move_button_focus(self, direction: int) -> None:
        buttons = self._buttons()
        if not buttons:
            return
        focused = self.app.focused
        if isinstance(focused, Button) and focused in buttons:
            current_index = buttons.index(focused)
        else:
            current_index = 0
        buttons[(current_index + direction) % len(buttons)].focus()

    def _activate_button(self, button_id: str | None) -> None:
        if button_id == "btn-run-ocr":
            self._launch_ocr()
            return
        self._go_home()

    def _launch_ocr(self) -> None:
        self.app.pop_screen()  # pop CheckResultScreen
        self.app.pop_screen()  # pop CheckInputScreen
        self.app.push_screen(WizardScreen(mode="ocr", prefill_path=str(self._input_path)))

    def _go_home(self) -> None:
        self.app.pop_screen()  # pop CheckResultScreen
        self.app.pop_screen()  # pop CheckInputScreen


# ── ProgressScreen (Phase 5) ──────────────────────────────────────────────────

class ProgressScreen(Screen):
    BINDINGS = [
        Binding("ctrl+c", "cancel_op", "Annulla"),
    ]

    def __init__(self, mode: str, args: dict) -> None:
        super().__init__()
        self._mode = mode
        self._args = args
        self._cancel_event = threading.Event()
        self._result_ready = False

    def compose(self) -> ComposeResult:
        title = "Esegui OCR" if self._mode == "ocr" else "Comprimi PDF"
        yield Static(f"PyDF Tool — {title}", id="header")
        yield Static("Avvio in corso...", id="status-msg")
        yield ProgressBar(total=100, id="progress-bar", show_eta=False)
        yield Static("", id="elapsed-label")
        yield Static("Ctrl+C per annullare", id="cancel-hint")
        yield Static("", id="footer-bar")

    def on_mount(self) -> None:
        self._run_operation()

    @work(thread=True)
    def _run_operation(self) -> None:
        def progress_cb(p: OperationProgress) -> None:
            if self._cancel_event.is_set():
                raise KeyboardInterrupt
            self.app.call_from_thread(self._on_progress, p)

        try:
            if self._mode == "ocr":
                result = run_ocr(
                    input_path=self._args["input"],
                    lang=self._args["lang"],
                    output_path=self._args["output"],
                    progress_callback=progress_cb,
                )
                self.app.call_from_thread(self._on_success_ocr, result)
            else:
                result = compress_pdf(
                    input_path=self._args["input"],
                    level=self._args["level"],
                    grayscale=self._args["grayscale"],
                    output_path=self._args["output"],
                    progress_callback=progress_cb,
                )
                self.app.call_from_thread(self._on_success_compress, result)
        except KeyboardInterrupt:
            self.app.call_from_thread(self._on_cancelled)
        except PDFToolError as e:
            self.app.call_from_thread(self._on_error, str(e))

    def _on_progress(self, p: OperationProgress) -> None:
        self.query_one("#status-msg", Static).update(p.message)
        if p.total:
            bar = self.query_one("#progress-bar", ProgressBar)
            bar.update(total=p.total, progress=p.completed)

    def _on_success_ocr(self, result: OCRResult) -> None:
        self._show_result(
            f"OCR completato\n\nOutput: {result.output_path}\nPagine: {result.pages}",
            success=True,
        )

    def _on_success_compress(self, result: CompressionResult) -> None:
        change = format_size_change(result.size_before, result.size_after)
        self._show_result(
            f"Compressione completata\n\nOutput: {result.output_path}\nRiduzione: {change}",
            success=True,
        )

    def _on_error(self, message: str) -> None:
        self._show_result(f"Errore: {message}", success=False)

    def _on_cancelled(self) -> None:
        self._show_result("Operazione annullata.", cancelled=True)

    def _show_result(self, text: str, success: bool = False, cancelled: bool = False) -> None:
        self.query_one("#progress-bar", ProgressBar).display = False
        self.query_one("#cancel-hint", Static).display = False
        self.query_one("#status-msg", Static).update(text)
        self.query_one("#footer-bar", Static).update("Invio per tornare al menu")
        self._result_ready = True

    def on_key(self, event) -> None:
        if self._result_ready and event.key in ("enter", "escape"):
            self.app.pop_screen()

    def action_cancel_op(self) -> None:
        self._cancel_event.set()


# ── PyDFApp ───────────────────────────────────────────────────────────────────

class PyDFApp(App):
    CSS_PATH = "tui.tcss"

    def __init__(
        self,
        parser_factory: Callable[[], argparse.ArgumentParser],
        executor: Callable[[argparse.Namespace], int],
    ) -> None:
        super().__init__()
        self._parser_factory = parser_factory
        self._executor = executor

    def on_mount(self) -> None:
        self.push_screen(HomeScreen())


# ── Entry points pubblici ─────────────────────────────────────────────────────

def run_interactive_app(
    *,
    parser_factory: Callable[[], argparse.ArgumentParser],
    executor: Callable[[argparse.Namespace], int],
) -> int:
    """Entry point TUI. Firma invariata — cli.py non cambia."""
    app = PyDFApp(parser_factory=parser_factory, executor=executor)
    app.run()
    return 0


def dispatch_interactive_command(
    command_line: str,
    *,
    parser_factory: Callable[[], argparse.ArgumentParser],
    executor: Callable[[argparse.Namespace], int],
) -> int:
    """Esegue un comando CLI testuale (es. 'ocr file.pdf --lang it').
    Firma invariata — cli.py non cambia.
    """
    stripped = command_line.strip()
    if not stripped:
        return 0

    try:
        tokens = shlex.split(stripped)
    except ValueError as exc:
        raise PDFToolError(f"Sintassi del comando non valida: {exc}") from exc

    if not tokens:
        return 0

    command = tokens[0].lower()

    if command in EXIT_COMMANDS:
        return -1

    if command == "help":
        if len(tokens) == 1:
            print(_HELP_TEXT_PLAIN)
            return 0
        # "help ocr" / "help compress" / "help check" → argparse --help
        sub_tokens = tokens[1:] + ["--help"]
        parser = parser_factory()
        try:
            parser.parse_args(sub_tokens)
        except SystemExit:
            return 0
        return 0

    if command == "interactive":
        return 0

    parser = parser_factory()
    try:
        ns = parser.parse_args(tokens)
    except SystemExit as exc:
        raise PDFToolError(
            "Comando non valido. Usa il menu guidato oppure apri Help."
        ) from exc

    return executor(ns)
