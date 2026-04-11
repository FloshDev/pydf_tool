from __future__ import annotations

import argparse
import shlex
import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from textual import events, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.reactive import reactive
from textual.screen import ModalScreen, Screen
from textual.widgets import Button, Input, ListItem, ListView, ProgressBar, Static

from .check_ocr import CheckOCRResult, check_ocr
from .compress import CompressionResult, compress_pdf
from .errors import PDFToolError
from .macos_integration import choose_pdf_file, open_output_folder, open_with_default_app
from .ocr import OCRResult, run_ocr
from .preferences import Preferences, load_preferences, save_preferences
from .progress import OperationProgress
from .system_checks import SystemCheckReport, check_global_systems, check_operation_systems
from .utils import (
    ensure_pdf_input,
    format_size_change,
    resolve_incremental_output_path,
    resolve_user_path,
)

# ── Costanti ──────────────────────────────────────────────────────────────────

EXIT_COMMANDS = {"exit", "quit", ":q"}

@dataclass(frozen=True)
class MenuEntry:
    key: str
    title: str
    summary: str
    preview_title: str
    preview_body: str
    preview_hint: str


@dataclass(frozen=True)
class WizardChoice:
    value: str
    label: str
    summary: str = ""


_HOME_MENU_ITEMS: list[MenuEntry] = [
    MenuEntry(
        key="ocr-menu",
        title="OCR",
        summary="Verifica testo estraibile o esegui l'OCR guidato.",
        preview_title="Suite OCR",
        preview_body=(
            "Apri il sottomenu OCR.\n"
            "Verifica se il PDF ha testo estraibile\n"
            "oppure avvia subito il wizard OCR."
        ),
        preview_hint="Invio apre il sottomenu OCR",
    ),
    MenuEntry(
        key="compress",
        title="Comprimi PDF",
        summary="Riduci il peso del file con Ghostscript.",
        preview_title="Compressione PDF",
        preview_body=(
            "Riduci le dimensioni del PDF.\n"
            "Usa preset guidati nella TUI oppure\n"
            "livelli 1-100 dalla CLI."
        ),
        preview_hint="Invio apre il wizard di compressione",
    ),
    MenuEntry(
        key="help",
        title="Help",
        summary="Controlli rapidi, flussi supportati e suggerimenti.",
        preview_title="Guida rapida",
        preview_body=(
            "Controlli rapidi e flussi supportati.\n"
            "Apri l'help in qualsiasi momento\n"
            "con H o F1."
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
_FOOTER_WIZARD_INPUT = "Invio avanza   Esc torna indietro"
_FOOTER_WIZARD_FILE = "Invio avanza   F2 Finder   Esc torna indietro"
_FOOTER_WIZARD_CHOICE = "↑↓ seleziona   Invio conferma   Esc torna indietro"
_FOOTER_CHECK_INPUT = "Invio conferma   F2 Finder   Esc annulla"
_FOOTER_RESULT_ACTIONS = "↑↓ cambia pulsante   Invio conferma   Esc torna al menu"

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
  · Se annulli una compressione, il file parziale viene rimosso"""

_HELP_TEXT_PLAIN = """\
PyDF Tool — strumenti PDF da riga di comando

  pydf-tool ocr FILE [--lang LINGUA] [--output PATH]
  pydf-tool compress FILE [--level low|medium|high|1-100] [--output PATH] [--grayscale]
  pydf-tool check FILE

Per OCR, l'output è PDF o TXT in base all'estensione di PATH.
Usa 'pydf-tool COMANDO --help' per dettagli sul singolo comando."""


def _return_to_home(app: App) -> None:
    while len(app.screen_stack) > 1 and not isinstance(app.screen, HomeScreen):
        app.pop_screen()


def _display_path(path: str | Path) -> str:
    candidate = resolve_user_path(path)
    home = Path.home()
    try:
        return f"~/{candidate.relative_to(home)}"
    except ValueError:
        return str(candidate)


def _preferences_for_app(app: App) -> Preferences:
    return cast("PyDFApp", app).preferences


class SystemCheckScreen(ModalScreen):
    BINDINGS = [
        Binding("escape", "dismiss_screen", "Chiudi"),
        Binding("enter", "dismiss_screen", "Chiudi"),
        Binding("q", "dismiss_screen", "Chiudi"),
    ]

    def __init__(self, report: SystemCheckReport, *, title: str) -> None:
        super().__init__()
        self._report = report
        self._title = title

    def compose(self) -> ComposeResult:
        yield Static(self._title, id="header")
        yield ScrollableContainer(
            Static(self._report.message, id="system-check-content"),
            id="system-check-container",
        )
        with Vertical(id="system-check-buttons"):
            yield Button("Chiudi", id="btn-close-system-check")
        yield Static("Invio · Esc · Q chiudono questa schermata", id="footer-bar")

    def on_mount(self) -> None:
        self.query_one("#btn-close-system-check", Button).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-close-system-check":
            self.dismiss()

    def action_dismiss_screen(self) -> None:
        self.dismiss()


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
        yield Static("Invio · Esc · Q chiudono questa schermata", id="footer-bar")

    def action_dismiss_screen(self) -> None:
        self.dismiss()


class MenuEntryItem(ListItem):
    def __init__(self, entry: MenuEntry) -> None:
        super().__init__(id=entry.key)
        self.entry = entry

    def compose(self) -> ComposeResult:
        yield Static(self.entry.title, classes="menu-item-title")
        yield Static(self.entry.summary, classes="menu-item-summary")


class WizardChoiceItem(ListItem):
    def __init__(self, choice: WizardChoice) -> None:
        super().__init__()
        self.choice = choice

    def compose(self) -> ComposeResult:
        yield Static(self.choice.label, classes="menu-item-title")
        if self.choice.summary:
            yield Static(self.choice.summary, classes="menu-item-summary")


# ── MenuScreen ────────────────────────────────────────────────────────────────

class MenuScreen(Screen):
    """Base class per schermate con pannello menu + pannello preview."""

    _menu_items: list[MenuEntry] = []

    def _set_preview(self, action_id: str) -> None:
        entry = next((item for item in self._menu_items if item.key == action_id), None)
        if entry is None:
            return
        self.query_one("#preview-title", Static).update(entry.preview_title)
        self.query_one("#preview-body", Static).update(entry.preview_body)
        self.query_one("#preview-hint", Static).update(entry.preview_hint)

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        if event.item is not None:
            self._set_preview(event.item.id)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if event.item is not None:
            self._dispatch_action(event.item.id)

    def _dispatch_action(self, action_id: str) -> None:
        raise NotImplementedError


# ── HomeScreen ────────────────────────────────────────────────────────────────

class HomeScreen(MenuScreen):
    _menu_items = _HOME_MENU_ITEMS

    BINDINGS = [
        Binding("q", "quit_app", "Esci"),
        Binding("escape", "quit_app", "Esci"),
        Binding("h", "push_help", "Help"),
        Binding("f1", "push_help", "Help"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="home-header"):
            yield Static("╠══ PyDF Tool ══╣", id="home-brand")
            yield Static(
                "tool da terminale per operazioni su PDF",
                id="home-subtitle",
            )
            yield Static("scegli uno strumento per continuare", id="home-tagline")
        with Horizontal(id="body"):
            with Vertical(id="menu-panel"):
                yield Static("Strumenti", classes="panel-title")
                yield ListView(
                    *[MenuEntryItem(entry) for entry in _HOME_MENU_ITEMS],
                    id="menu-list",
                )
            with Vertical(id="preview-panel"):
                yield Static("Dettagli", classes="panel-title")
                with ScrollableContainer(id="preview-copy"):
                    yield Static("", id="preview-title")
                    yield Static("", id="preview-body")
                yield Static("", id="preview-hint")
        yield Static(_FOOTER_HOME, id="footer-bar")

    def on_mount(self) -> None:
        self._set_preview(_HOME_MENU_ITEMS[0].key)
        self.query_one("#menu-list", ListView).focus()

    def _dispatch_action(self, action_id: str) -> None:
        if action_id == "ocr-menu":
            self.app.push_screen(OCRMenuScreen())
        elif action_id == "compress":
            if not cast("PyDFApp", self.app).ensure_operation_available("compress"):
                return
            self.app.push_screen(WizardScreen(mode=action_id))
        elif action_id == "help":
            self.app.push_screen(HelpScreen())

    def action_quit_app(self) -> None:
        self.app.exit(0)

    def action_push_help(self) -> None:
        self.app.push_screen(HelpScreen())


class OCRMenuScreen(MenuScreen):
    _menu_items = _OCR_MENU_ITEMS

    BINDINGS = [
        Binding("escape", "go_back", "Indietro"),
        Binding("h", "push_help", "Help"),
        Binding("f1", "push_help", "Help"),
    ]

    def compose(self) -> ComposeResult:
        yield Static("OCR", id="wizard-title")
        yield Static("Scegli l'azione da eseguire.", id="step-prompt")
        with Vertical(id="ocr-menu-panel"):
            yield ListView(
                *[MenuEntryItem(entry) for entry in _OCR_MENU_ITEMS],
                id="menu-list",
            )
            with Vertical(id="ocr-menu-preview"):
                yield Static("", id="ocr-preview-title")
                yield Static("", id="ocr-preview-body")
                yield Static("", id="ocr-preview-hint")
        yield Static(_FOOTER_SUBMENU, id="footer-bar")

    def on_mount(self) -> None:
        self._set_preview(_OCR_MENU_ITEMS[0].key)
        self.query_one("#menu-list", ListView).focus()

    def _set_preview(self, action_id: str) -> None:
        entry = next((item for item in self._menu_items if item.key == action_id), None)
        if entry is None:
            return
        self.query_one("#ocr-preview-title", Static).update(entry.preview_title)
        self.query_one("#ocr-preview-body", Static).update(entry.preview_body)
        self.query_one("#ocr-preview-hint", Static).update(entry.preview_hint)

    def _dispatch_action(self, action_id: str) -> None:
        if action_id == "check":
            self.app.push_screen(CheckInputScreen())
        elif action_id == "ocr":
            if not cast("PyDFApp", self.app).ensure_operation_available("ocr"):
                return
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
    choices: list[WizardChoice] | None = None


_WIZARD_STEPS: dict[str, list[WizardStep]] = {
    "ocr": [
        WizardStep("File",    "Percorso del PDF da elaborare:",    "es. ~/Documents/doc.pdf"),
        WizardStep(
            "Lingua",
            "Lingua del documento:",
            "seleziona con le frecce",
            choices=[
                WizardChoice("it", "Italiano", "OCR in italiano."),
                WizardChoice("en", "Inglese", "OCR in inglese."),
                WizardChoice("it+en", "Italiano + Inglese", "Riconoscimento bilingue."),
            ],
        ),
        WizardStep(
            "Formato",
            "Formato output:",
            "seleziona con le frecce",
            choices=[
                WizardChoice("pdf", "PDF ricercabile", "Mantiene il layout del documento."),
                WizardChoice("txt", "Testo TXT", "Esporta solo il testo estratto."),
            ],
        ),
        WizardStep(
            "Output",
            "Percorso file di output:",
            "es. ~/Desktop/out.pdf (vuoto = stessa cartella del file di partenza)",
        ),
    ],
    "compress": [
        WizardStep("File",    "Percorso del PDF da comprimere:",   "es. ~/Documents/doc.pdf"),
        WizardStep(
            "Livello",
            "Livello di compressione:",
            "seleziona con le frecce",
            choices=[
                WizardChoice("low", "Low", "Compressione leggera, qualità più alta."),
                WizardChoice("medium", "Medium", "Bilanciamento tra qualità e peso."),
                WizardChoice("high", "High", "Compressione forte, file più leggero."),
                WizardChoice("custom", "Personalizzato", "Inserisci un valore numerico da 1 a 100."),
            ],
        ),
        WizardStep("Grado",   "Grado personalizzato di compressione:", "1-100"),
        WizardStep(
            "Colore",
            "Modalità colore:",
            "seleziona con le frecce",
            choices=[
                WizardChoice("color", "Colori originali", "Mantiene il PDF a colori."),
                WizardChoice("gray", "Scala di grigi", "Riduce il peso convertendo in grigio."),
            ],
        ),
        WizardStep(
            "Output",
            "Percorso file di output:",
            "es. ~/Desktop/out.pdf (vuoto = stessa cartella del file di partenza)",
        ),
    ],
}


class WizardScreen(Screen):
    BINDINGS = [
        Binding("escape", "go_back", "Indietro"),
        Binding("f2", "pick_pdf_from_finder", "Finder"),
        Binding("h", "push_help", "Help"),
        Binding("f1", "push_help", "Help"),
    ]

    current_step: reactive[int] = reactive(0)

    def __init__(self, mode: str, prefill_path: str = "") -> None:
        super().__init__()
        self._mode = mode
        self._steps = _WIZARD_STEPS[mode]
        self._values: dict[str, str] = {}
        self._prefill_path = prefill_path
        if self._prefill_path:
            self._values["file"] = self._prefill_path

    def compose(self) -> ComposeResult:
        title = "Esegui OCR" if self._mode == "ocr" else "Comprimi PDF"
        yield Static("", id="step-indicator")
        yield Static(title, id="wizard-title")
        yield Static("", id="step-prompt")
        yield Input(id="step-input")
        yield Button("Scegli PDF da Finder", id="finder-button")
        yield ListView(id="step-choices")
        yield Static("", id="step-hint")
        yield Static("", id="step-error", classes="error-label")
        yield Static("", id="footer-bar")

    def on_mount(self) -> None:
        self._apply_preference_defaults()
        self._render_step(0)

    def watch_current_step(self, step: int) -> None:
        self._render_step(step)

    def _apply_preference_defaults(self) -> None:
        preferences = _preferences_for_app(self.app)
        if self._mode == "ocr" and "lingua" not in self._values:
            self._values["lingua"] = preferences.ocr_language
            return

        if self._mode != "compress" or "livello" in self._values:
            return

        preferred_level = preferences.compression_level.strip().lower()
        if preferred_level in {"low", "medium", "high"}:
            self._values["livello"] = preferred_level
            return
        if preferred_level.isdigit() and 1 <= int(preferred_level) <= 100:
            self._values["livello"] = "custom"
            self._values["grado"] = preferred_level
            return
        self._values["livello"] = "medium"

    def _visible_steps(self) -> list[WizardStep]:
        steps = self._steps
        if self._mode == "ocr" and self._prefill_path:
            steps = [step for step in steps if step.name != "File"]
        if self._mode == "compress":
            steps = [
                step
                for step in steps
                if step.name != "Grado" or self._values.get("livello") == "custom"
            ]
        return steps

    def _render_step(self, step: int) -> None:
        steps = self._visible_steps()
        parts = []
        for i, s in enumerate(steps):
            marker = "▶ " if i == step else "   "
            parts.append(f"{marker}{i + 1}. {s.name}")
        self.query_one("#step-indicator", Static).update("  ".join(parts))
        current = steps[step]
        self.query_one("#step-prompt", Static).update(current.prompt)
        inp = self.query_one("#step-input", Input)
        finder_button = self.query_one("#finder-button", Button)
        choice_list = self.query_one("#step-choices", ListView)
        hint = self.query_one("#step-hint", Static)
        if current.choices:
            inp.display = False
            finder_button.display = False
            choice_list.display = True
            selected_value = self._values.get(current.name.lower(), current.choices[0].value)
            self._populate_choice_list(current.choices, selected_value)
            self.query_one("#footer-bar", Static).update(_FOOTER_WIZARD_CHOICE)
            hint.update(self._step_hint_text(current))
            hint.display = bool(hint.content)
        else:
            choice_list.display = False
            inp.display = True
            inp.placeholder = self._resolve_input_placeholder(current)
            inp.value = self._values.get(current.name.lower(), "")
            inp.focus()
            is_file_step = current.name == "File"
            finder_button.display = is_file_step
            self.query_one("#footer-bar", Static).update(
                _FOOTER_WIZARD_FILE if is_file_step else _FOOTER_WIZARD_INPUT
            )
            hint_text = self._step_hint_text(current)
            hint.update(hint_text)
            hint.display = bool(hint_text)
        self.query_one("#step-error", Static).update("")

    def _resolve_input_placeholder(self, step: WizardStep) -> str:
        if self._mode == "ocr" and step.name == "Output":
            extension = ".txt" if self._values.get("formato") == "txt" else ".pdf"
            return (
                f"es. ~/Desktop/out{extension} "
                "(vuoto = stessa cartella del file di partenza)"
            )
        return step.placeholder

    def _step_hint_text(self, step: WizardStep) -> str:
        preferences = _preferences_for_app(self.app)
        if step.name == "File":
            if preferences.last_directory is not None:
                return (
                    "F2 apre Finder. Ultima cartella usata: "
                    f"{_display_path(preferences.last_directory)}"
                )
            return "F2 apre Finder per selezionare un PDF senza scrivere il percorso."
        if step.name == "Output":
            suggestion = self._suggested_output_path()
            if suggestion is not None:
                return f"Lascia vuoto per usare: {_display_path(suggestion)}"
        return ""

    def _suggested_output_path(self) -> Path | None:
        file_value = self._values.get("file", "").strip()
        if not file_value:
            return None
        input_path = resolve_user_path(file_value)
        if self._mode == "ocr":
            extension = ".txt" if self._values.get("formato") == "txt" else ".pdf"
            return resolve_incremental_output_path(input_path, extension)
        return resolve_incremental_output_path(input_path, ".pdf")

    def _focus_choice_value(self, value: str) -> None:
        step = self._visible_steps()[self.current_step]
        choices = step.choices or []
        choice_list = self.query_one("#step-choices", ListView)
        selected_index = next(
            (index for index, choice in enumerate(choices) if choice.value == value),
            0,
        )
        choice_list.index = None
        choice_list.index = selected_index
        choice_list.focus()

    def _sync_choice_highlight_class(self) -> None:
        choice_list = self.query_one("#step-choices", ListView)
        for item in choice_list.query("ListItem"):
            assert isinstance(item, ListItem)
            item.highlighted = False
        highlighted_child = choice_list.highlighted_child
        if highlighted_child is not None:
            highlighted_child.highlighted = True

    @work(exclusive=True, group="wizard-choice-list")
    async def _populate_choice_list(
        self,
        choices: list[WizardChoice],
        selected_value: str,
    ) -> None:
        choice_list = self.query_one("#step-choices", ListView)
        await choice_list.clear()
        await choice_list.extend([WizardChoiceItem(choice) for choice in choices])
        self._focus_choice_value(selected_value)
        self._sync_choice_highlight_class()

    def on_key(self, event: events.Key) -> None:
        current_step = self._visible_steps()[self.current_step]
        if current_step.name != "File" or current_step.choices:
            return
        if event.key in {"down", "tab"}:
            event.stop()
            event.prevent_default()
            self._move_file_step_focus(1)
        elif event.key in {"up", "shift+tab"}:
            event.stop()
            event.prevent_default()
            self._move_file_step_focus(-1)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "finder-button":
            self.action_pick_pdf_from_finder()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self._advance(event.value.strip())

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if event.list_view.id != "step-choices":
            return
        if isinstance(event.item, WizardChoiceItem):
            self._advance(event.item.choice.value)

    def _advance(self, value: str) -> None:
        step = self.current_step
        s = self._visible_steps()[step]
        err = self._validate(step, value, s)
        if err:
            self.query_one("#step-error", Static).update(err)
            return
        self._values[s.name.lower()] = value
        self._remember_preference_from_step(s.name, value)
        if s.name == "Livello" and value != "custom":
            self._values.pop("grado", None)
        visible_steps = self._visible_steps()
        if step + 1 < len(visible_steps):
            self.current_step = step + 1
        else:
            self._finish()

    def _validate(self, step: int, value: str, s: WizardStep) -> str:
        if s.name == "File":
            if not value:
                return "Percorso obbligatorio."
            try:
                ensure_pdf_input(resolve_user_path(value))
            except PDFToolError as e:
                return str(e)
        elif s.name == "Grado":
            if not value:
                return "Inserisci un valore tra 1 e 100."
            if not value.isdigit():
                return "Il grado personalizzato deve essere numerico."
            numeric = int(value)
            if numeric < 1 or numeric > 100:
                return "Il grado personalizzato deve essere tra 1 e 100."
        elif s.choices and value not in {choice.value for choice in s.choices}:
            return f"Scegli tra: {' · '.join(choice.value for choice in s.choices)}"
        return ""

    def _remember_preference_from_step(self, step_name: str, value: str) -> None:
        app = cast("PyDFApp", self.app)
        normalized_name = step_name.lower()
        if normalized_name == "file":
            app.remember_path(value)
        elif normalized_name == "lingua":
            app.set_ocr_language(value)
        elif normalized_name == "livello" and value != "custom":
            app.set_compression_level(value)
        elif normalized_name == "grado":
            app.set_compression_level(value)
        elif normalized_name == "output" and value.strip():
            app.remember_path(value)

    def action_pick_pdf_from_finder(self) -> None:
        current_step = self._visible_steps()[self.current_step]
        if current_step.name != "File":
            return
        try:
            selected = choose_pdf_file(
                initial_directory=_preferences_for_app(self.app).last_directory,
                prompt=current_step.prompt,
            )
        except PDFToolError as exc:
            self.query_one("#step-error", Static).update(str(exc))
            return

        if selected is None:
            return

        input_widget = self.query_one("#step-input", Input)
        input_widget.value = str(selected)
        input_widget.focus()
        cast("PyDFApp", self.app).remember_path(selected)
        hint = self.query_one("#step-hint", Static)
        hint.update(self._step_hint_text(current_step))
        hint.display = bool(hint.content)

    def _move_file_step_focus(self, direction: int) -> None:
        focusables: list[Input | Button] = [
            self.query_one("#step-input", Input),
            self.query_one("#finder-button", Button),
        ]
        focused = self.app.focused
        if focused in focusables:
            next_index = (focusables.index(focused) + direction) % len(focusables)
        else:
            next_index = 0 if direction > 0 else len(focusables) - 1
        focusables[next_index].focus()

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
            level = v.get("livello", "medium")
            if level == "custom":
                level = v.get("grado", "50")
            return {
                "input": in_path,
                "level": level,
                "grayscale": v.get("colore", "color") == "gray",
                "output": out_path,
            }

    def action_go_back(self) -> None:
        if self.current_step > 0:
            new_step = self.current_step - 1
            self.current_step = min(new_step, len(self._visible_steps()) - 1)
        else:
            self.app.pop_screen()

    def action_push_help(self) -> None:
        self.app.push_screen(HelpScreen())


# ── CheckInputScreen + CheckResultScreen (Phase 4) ────────────────────────────

class CheckInputScreen(Screen):
    BINDINGS = [
        Binding("escape", "go_back", "Annulla"),
        Binding("f2", "pick_pdf_from_finder", "Finder"),
    ]

    def compose(self) -> ComposeResult:
        yield Static("Verifica OCR", id="wizard-title")
        yield Static("Percorso del PDF da verificare:", id="step-prompt")
        yield Input(placeholder="es. ~/Documents/doc.pdf", id="check-input")
        yield Button("Scegli PDF da Finder", id="check-picker-button")
        yield Static("", id="check-hint")
        yield Static("", id="check-error", classes="error-label")
        yield Static(_FOOTER_CHECK_INPUT, id="footer-bar")

    def on_mount(self) -> None:
        self.query_one("#check-input", Input).focus()
        self._update_hint()

    def on_key(self, event: events.Key) -> None:
        if event.key in {"down", "tab"}:
            event.stop()
            event.prevent_default()
            self._move_focus(1)
        elif event.key in {"up", "shift+tab"}:
            event.stop()
            event.prevent_default()
            self._move_focus(-1)

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
        cast("PyDFApp", self.app).remember_path(path)
        self.app.push_screen(CheckResultScreen(result=result, input_path=path))

    def action_go_back(self) -> None:
        self.app.pop_screen()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "check-picker-button":
            self.action_pick_pdf_from_finder()

    def action_pick_pdf_from_finder(self) -> None:
        try:
            selected = choose_pdf_file(
                initial_directory=_preferences_for_app(self.app).last_directory,
                prompt="Seleziona il PDF da verificare",
            )
        except PDFToolError as exc:
            self.query_one("#check-error", Static).update(str(exc))
            return

        if selected is None:
            return

        input_widget = self.query_one("#check-input", Input)
        input_widget.value = str(selected)
        input_widget.focus()
        cast("PyDFApp", self.app).remember_path(selected)
        self._update_hint()

    def _update_hint(self) -> None:
        hint = self.query_one("#check-hint", Static)
        last_directory = _preferences_for_app(self.app).last_directory
        if last_directory is None:
            hint.update("F2 apre Finder per selezionare un PDF senza scrivere il percorso.")
            return
        hint.update(
            "F2 apre Finder. Ultima cartella usata: "
            f"{_display_path(last_directory)}"
        )

    def _move_focus(self, direction: int) -> None:
        focusables: list[Input | Button] = [
            self.query_one("#check-input", Input),
            self.query_one("#check-picker-button", Button),
        ]
        focused = self.app.focused
        if focused in focusables:
            next_index = (focusables.index(focused) + direction) % len(focusables)
        else:
            next_index = 0 if direction > 0 else len(focusables) - 1
        focusables[next_index].focus()


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
        if not cast("PyDFApp", self.app).ensure_operation_available("ocr"):
            return
        self.app.pop_screen()  # pop CheckResultScreen
        self.app.pop_screen()  # pop CheckInputScreen
        self.app.pop_screen()  # pop OCRMenuScreen
        self.app.push_screen(WizardScreen(mode="ocr", prefill_path=str(self._input_path)))

    def _go_home(self) -> None:
        _return_to_home(self.app)


# ── ProgressScreen (Phase 5) ──────────────────────────────────────────────────

class ProgressScreen(Screen):
    BINDINGS = [
        Binding("ctrl+c", "cancel_op", "Annulla"),
        Binding("up", "focus_prev_button", "Prec", show=False),
        Binding("left", "focus_prev_button", "Prec", show=False),
        Binding("shift+tab", "focus_prev_button", "Prec", show=False),
        Binding("down", "focus_next_button", "Succ", show=False),
        Binding("right", "focus_next_button", "Succ", show=False),
        Binding("tab", "focus_next_button", "Succ", show=False),
    ]

    def __init__(self, mode: str, args: dict) -> None:
        super().__init__()
        self._mode = mode
        self._args = args
        self._cancel_event = threading.Event()
        self._result_ready = False
        self._result_path: Path | None = None
        self._result_message = ""

    def compose(self) -> ComposeResult:
        title = "Esegui OCR" if self._mode == "ocr" else "Comprimi PDF"
        yield Static(f"PyDF Tool — {title}", id="header")
        yield Static("Avvio in corso...", id="status-msg")
        yield ProgressBar(total=100, id="progress-bar", show_eta=False)
        with Vertical(id="progress-result-buttons"):
            yield Button("Apri file", id="btn-open-file")
            yield Button("Apri cartella", id="btn-open-folder")
            yield Button("Torna al menu", id="btn-progress-home")
        yield Static("Ctrl+C per annullare", id="footer-bar")

    def on_mount(self) -> None:
        self.query_one("#progress-result-buttons", Vertical).display = False
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
        cast("PyDFApp", self.app).remember_path(result.output_path)
        self._show_result(
            (
                "OCR completato\n\n"
                f"Output salvato in:\n{result.output_path}\n\n"
                f"Pagine elaborate: {result.pages}\n"
                "Prossimo passo: apri il file per controllare il risultato oppure "
                "apri la cartella di output."
            ),
            success=True,
            output_path=result.output_path,
        )

    def _on_success_compress(self, result: CompressionResult) -> None:
        cast("PyDFApp", self.app).remember_path(result.output_path)
        change = format_size_change(result.size_before, result.size_after)
        note = ""
        if result.size_after > result.size_before:
            note = "\nNota: il file finale è più grande dell'originale."
        self._show_result(
            (
                "Compressione completata\n\n"
                f"Output salvato in:\n{result.output_path}\n\n"
                f"Variazione dimensione: {change}{note}\n"
                "Prossimo passo: apri il file per verificare la qualità oppure "
                "apri la cartella di output."
            ),
            success=True,
            output_path=result.output_path,
        )

    def _on_error(self, message: str) -> None:
        self._show_result(f"Errore: {message}", success=False)

    def _on_cancelled(self) -> None:
        self._show_result("Operazione annullata.", cancelled=True)

    def _show_result(
        self,
        text: str,
        success: bool = False,
        cancelled: bool = False,
        output_path: Path | None = None,
    ) -> None:
        self.query_one("#progress-bar", ProgressBar).display = False
        self.query_one("#status-msg", Static).update(text)
        self._result_message = text
        self._result_path = output_path
        button_panel = self.query_one("#progress-result-buttons", Vertical)
        button_panel.display = True
        self.query_one("#btn-open-file", Button).display = success and output_path is not None
        self.query_one("#btn-open-folder", Button).display = success and output_path is not None
        self.query_one("#btn-progress-home", Button).display = True
        self.query_one("#footer-bar", Static).update(_FOOTER_RESULT_ACTIONS)
        self._result_ready = True
        self._focus_first_button()

    def on_key(self, event: events.Key) -> None:
        if self._result_ready and event.key == "escape":
            event.stop()
            event.prevent_default()
            _return_to_home(self.app)

    def action_cancel_op(self) -> None:
        self._cancel_event.set()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-open-file":
            self._open_result_file()
        elif event.button.id == "btn-open-folder":
            self._open_result_folder()
        else:
            _return_to_home(self.app)

    def action_focus_next_button(self) -> None:
        if self._result_ready:
            self._move_button_focus(1)

    def action_focus_prev_button(self) -> None:
        if self._result_ready:
            self._move_button_focus(-1)

    def _visible_buttons(self) -> list[Button]:
        return [button for button in self.query("#progress-result-buttons Button") if button.display]

    def _focus_first_button(self) -> None:
        buttons = self._visible_buttons()
        if buttons:
            buttons[0].focus()

    def _move_button_focus(self, direction: int) -> None:
        buttons = self._visible_buttons()
        if not buttons:
            return
        focused = self.app.focused
        if isinstance(focused, Button) and focused in buttons:
            current_index = buttons.index(focused)
        else:
            current_index = 0
        buttons[(current_index + direction) % len(buttons)].focus()

    def _open_result_file(self) -> None:
        if self._result_path is None:
            return
        try:
            open_with_default_app(self._result_path)
        except PDFToolError as exc:
            self._show_action_error(exc)

    def _open_result_folder(self) -> None:
        if self._result_path is None:
            return
        try:
            open_output_folder(self._result_path)
        except PDFToolError as exc:
            self._show_action_error(exc)

    def _show_action_error(self, exc: PDFToolError) -> None:
        self.query_one("#status-msg", Static).update(
            f"{self._result_message}\n\nErrore azione: {exc}"
        )


# ── PyDFApp ───────────────────────────────────────────────────────────────────

class PyDFApp(App):
    CSS_PATH = "tui.tcss"

    def __init__(
        self,
        *,
        show_startup_checks: bool = True,
        preferences: Preferences | None = None,
        global_system_report: SystemCheckReport | None = None,
    ) -> None:
        super().__init__()
        self._show_startup_checks = show_startup_checks
        self.preferences = preferences if preferences is not None else load_preferences()
        self.global_system_report = (
            global_system_report
            if global_system_report is not None
            else check_global_systems()
        )

    def on_mount(self) -> None:
        self.push_screen(HomeScreen())
        if self._show_startup_checks and not self.global_system_report.ok:
            self.push_screen(
                SystemCheckScreen(
                    self.global_system_report,
                    title="Prerequisiti mancanti",
                )
            )

    def save_preferences(self) -> None:
        try:
            save_preferences(self.preferences)
        except OSError:
            pass

    def remember_path(self, path: str | Path) -> None:
        self.preferences = self.preferences.remember_path(path)
        self.save_preferences()

    def set_ocr_language(self, language: str) -> None:
        self.preferences = self.preferences.with_ocr_language(language)
        self.save_preferences()

    def set_compression_level(self, level: str) -> None:
        self.preferences = self.preferences.with_compression_level(level)
        self.save_preferences()

    def ensure_operation_available(self, operation: str) -> bool:
        report = check_operation_systems(operation)
        if report.ok:
            return True
        self.push_screen(
            SystemCheckScreen(
                report,
                title="Prerequisiti mancanti",
            )
        )
        return False


# ── Entry points pubblici ─────────────────────────────────────────────────────

def run_interactive_app() -> int:
    """Entry point TUI."""
    app = PyDFApp()
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
