# Piano implementativo: Migrazione TUI a Textual

**Data:** 2026-03-30
**Spec di riferimento:** `docs/superpowers/specs/2026-03-29-textual-migration-design.md`
**Issue:** #3 — alternanza prompt_toolkit/rich fragile
**Branch:** main

---

## Contesto di partenza

- `tui.py` attuale: ~1250 righe, alterna prompt_toolkit e rich
- Firma pubblica invariata: `run_interactive_app(*, parser_factory, executor)` e `dispatch_interactive_command(command_line, *, parser_factory, executor)`
- File **non toccati**: `cli.py`, `ocr.py`, `compress.py`, `check_ocr.py`, `utils.py`, `progress.py`, `errors.py`
- Suite attuale: 35 test, tutti verdi

---

## Allowed APIs (Textual)

Importazioni canoniche da usare in tutto il progetto:

```python
from textual.app import App, ComposeResult
from textual.screen import Screen, ModalScreen
from textual.widgets import ListView, ListItem, Label, Button, Input, Static, ProgressBar
from textual.containers import Horizontal, Vertical, ScrollableContainer
from textual.reactive import reactive
from textual.binding import Binding
from textual import work
```

Patterns approvati:
- `App.run()` — avvia l'event loop bloccante
- `Screen.compose() -> ComposeResult` — yield dei widget
- `Screen.BINDINGS = [Binding("key", "action_name", "Description")]`
- `def action_<name>(self) -> None:` — handler per binding
- `self.app.push_screen(screen_instance)` / `self.app.pop_screen()`
- `self.dismiss()` — solo su ModalScreen
- `@work(thread=True)` — decorator per metodi che girano in thread background
- `self.app.call_from_thread(callable, *args)` — aggiornamento UI thread-safe
- `reactive(default)` + `def watch_<attr>(self, value):` — stato reattivo
- `self.query_one("#id", WidgetType)` — accesso widget per id
- `ListView.Selected` event — `event.item.id` per identificare la voce
- `Button.Pressed` event — `event.button.id`
- `Input.Submitted` event — `event.value`

---

## Phase 0: Documentation Discovery — COMPLETATA

Analisi codebase eseguita. Dati raccolti:

### Firme pubbliche invariate

```python
# tui.py — deve restare identica
def run_interactive_app(
    *,
    parser_factory: Callable[[], argparse.ArgumentParser],
    executor: Callable[[argparse.Namespace], int],
) -> int: ...

def dispatch_interactive_command(
    command_line: str,
    *,
    parser_factory: Callable[[], argparse.ArgumentParser],
    executor: Callable[[argparse.Namespace], int],
) -> int: ...
```

### Dataclass di riferimento (non cambiamo)

```python
# progress.py
@dataclass(frozen=True)
class OperationProgress:
    stage: str
    message: str
    completed: int = 0
    total: int | None = None

# check_ocr.py
@dataclass(frozen=True)
class CheckOCRResult:
    pages_total: int
    pages_with_text: int
    pages_without_text: int
    chars_per_page_avg: float
    verdict: str  # "ocr_needed" | "already_searchable" | "mixed"
```

### 4 test da aggiornare in test_cli.py

| Test | Azione |
|---|---|
| `test_dialog_width_shrinks_with_terminal` | **Elimina** — `_dialog_width()` non esiste più |
| `test_wrap_dialog_text_wraps_bullets_with_indentation` | **Elimina** — `_wrap_dialog_text()` non esiste più |
| `test_interactive_shell_runs_guided_ocr_flow` | **Aggiorna** — mocka `PyDFApp.run` invece delle funzioni interne |
| `test_dispatch_interactive_command_supports_direct_ocr_command` | **Aggiorna** — rimane simile, patch `run_ocr` e `compress_pdf` direttamente |

---

## Phase 1: Dipendenze + CSS foundation

**File modificati:** `pyproject.toml`, `src/pydf_tool/tui.tcss` (nuovo)

### 1.1 — pyproject.toml

Modifica `dependencies`:
- **Rimuovi**: `"prompt_toolkit==3.0.42"`, `"rich==13.7.1"`
- **Aggiungi**: `"textual>=0.70.0"`

```toml
dependencies = [
    "pdf2image==1.17.0",
    "textual>=0.70.0",
    "pypdf==6.8.0",
    "pytesseract==0.3.13",
    "Pillow>=10.3.0,<12.0",
]
```

### 1.2 — tui.tcss (file nuovo)

Creare `src/pydf_tool/tui.tcss` con variabili colore CLAUDE.md e stili base:

```css
/* Variabili colore — palette CLAUDE.md */
$accent: #E8B84B;
$text: #D4D4D4;
$secondary: #7A7A7A;
$border: #3A3A3A;
$error: #E85B4B;
$success: #4BE87A;

/* Nessun background esplicito — sfondo sempre trasparente */

Screen {
    color: $text;
}

#header {
    color: $accent;
    border: solid $border;
    padding: 1 2;
    height: auto;
}

#footer-bar {
    color: $secondary;
    border-top: solid $border;
    padding: 0 2;
    height: 1;
}

ListView {
    border: solid $border;
    background: transparent;
}

ListView > ListItem {
    color: $text;
    background: transparent;
}

ListView > ListItem.--highlight {
    color: $accent;
    text-style: bold;
    background: transparent;
}

#preview-panel {
    border: solid $border;
    padding: 1 2;
    color: $secondary;
}

.step-indicator {
    color: $secondary;
    padding: 0 2;
}

.step-indicator .active {
    color: $accent;
    text-style: bold;
}

.error-label {
    color: $error;
    padding: 0 2;
}

.success-label {
    color: $success;
}

ProgressBar Bar {
    color: $accent;
    background: $border;
}

Button {
    border: solid $border;
    background: transparent;
    color: $text;
    margin: 0 1;
}

Button:focus {
    color: $accent;
    border: solid $accent;
}

HelpScreen > ScrollableContainer {
    border: solid $border;
    padding: 1 2;
    background: transparent;
}
```

**Anti-pattern:** NON usare `background:` con colori espliciti su Screen, ListView, Container.

### Verifica Phase 1

```bash
# Reinstalla dipendenze
pip install -e . && bash setup.sh

# Verifica che textual sia installato
python3 -c "import textual; print(textual.__version__)"

# Verifica che prompt_toolkit NON sia più importabile come dipendenza diretta
# (può essere ancora presente come sotto-dipendenza transitiva — non è un problema)

# Suite deve restare verde (nessun import di tui.py nei 31 test backend)
PYTHONPATH=src python3 -m unittest discover -s tests -v 2>&1 | tail -5
```

---

## Phase 2: PyDFApp + HomeScreen + HelpScreen

**File modificati:** `src/pydf_tool/tui.py` (riscritto da zero)

### 2.1 — Struttura file tui.py

```python
from __future__ import annotations

import argparse
import shlex
from collections.abc import Callable

from textual.app import App, ComposeResult
from textual.screen import Screen, ModalScreen
from textual.widgets import ListView, ListItem, Label, Button, Input, Static, ProgressBar
from textual.containers import Horizontal, Vertical, ScrollableContainer
from textual.reactive import reactive
from textual.binding import Binding
from textual import work

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
```

### 2.2 — Costanti e testi UI

```python
_HEADER_TEXT = """\
╠══ PyDF Tool ══╣   OCR  ·  compress  ·  check
──────────────────────────────────────────────
strumenti PDF da riga di comando · macOS"""

_MENU_ITEMS = [
    ("ocr",      "Esegui OCR",   "Converti PDF scansionato in PDF ricercabile"),
    ("compress", "Comprimi PDF", "Riduci dimensioni con Ghostscript"),
    ("check",    "Verifica OCR", "Controlla se il PDF ha già testo estraibile"),
]

_PREVIEW_TEXTS = {
    "ocr":      "Usa Tesseract per estrarre testo da PDF scansionati.\nOutput: PDF ricercabile o .txt",
    "compress": "Usa Ghostscript per ridurre le dimensioni del file.\nPreset: low · medium · high",
    "check":    "Legge i metadati del PDF e stima se OCR è necessario.\nRisultato immediato, nessuna elaborazione.",
}

_FOOTER_TEXT = "↑↓ naviga   Invio conferma   H/F1 help   Q/Esc esci"
```

### 2.3 — HelpScreen (ModalScreen)

```python
class HelpScreen(ModalScreen):
    BINDINGS = [
        Binding("escape", "dismiss", "Chiudi"),
        Binding("enter", "dismiss", "Chiudi"),
        Binding("q", "dismiss", "Chiudi"),
    ]

    def compose(self) -> ComposeResult:
        yield ScrollableContainer(
            Static(_HELP_TEXT, id="help-content"),
            id="help-container",
        )

    def action_dismiss(self) -> None:
        self.dismiss()
```

`_HELP_TEXT`: stringa con le istruzioni d'uso (copiare da tui.py attuale, adattare).

### 2.4 — HomeScreen

```python
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
            yield ListView(
                *[ListItem(Label(label), id=key) for key, label, _ in _MENU_ITEMS],
                id="menu-list",
            )
            yield Static(_PREVIEW_TEXTS[_MENU_ITEMS[0][0]], id="preview-panel")
        yield Static(_FOOTER_TEXT, id="footer-bar")

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        action_id = event.item.id  # "ocr" | "compress" | "check"
        self._dispatch_action(action_id)

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        if event.item is not None:
            preview = _PREVIEW_TEXTS.get(event.item.id, "")
            self.query_one("#preview-panel", Static).update(preview)

    def _dispatch_action(self, action_id: str) -> None:
        if action_id == "check":
            self.app.push_screen(CheckInputScreen("check"))
        else:
            self.app.push_screen(WizardScreen(mode=action_id))

    def action_quit_app(self) -> None:
        self.app.exit(0)

    def action_push_help(self) -> None:
        self.app.push_screen(HelpScreen())
```

**Nota:** `CheckInputScreen` è uno schermo minimale di input file per Verifica OCR (vedi Phase 4).

### 2.5 — PyDFApp

```python
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
```

**Anti-pattern:**
- NON usare `SCREENS = {...}` dict se le screen ricevono argomenti — istanziarle direttamente
- NON mescolare `push_screen` con `switch_screen` (usa sempre `push_screen` per mantenere lo stack)

### Verifica Phase 2

```bash
# Avviare la TUI — deve mostrare HomeScreen senza crash
PYTHONPATH=src python3 -c "
from pydf_tool.tui import run_interactive_app
import argparse
def fake_parser():
    p = argparse.ArgumentParser()
    return p
def fake_executor(ns):
    return 0
# NON chiamare run_interactive_app() — solo verificare import
print('Import OK')
"

# Suite invariata
PYTHONPATH=src python3 -m unittest discover -s tests -v 2>&1 | tail -5
```

Test manuale: `PYTHONPATH=src python3 -m pydf_tool` — deve aprire la HomeScreen, navigare con ↑↓, aprire help con H, uscire con Q.

---

## Phase 3: WizardScreen (stepper OCR + Comprimi)

**File modificati:** `src/pydf_tool/tui.py`

### 3.1 — Configurazione step per modalità

```python
from dataclasses import dataclass, field

@dataclass
class WizardStep:
    name: str               # etichetta nell'indicatore
    prompt: str             # testo sopra l'input
    placeholder: str        # placeholder nel campo Input
    choices: list[str] | None = None  # None = testo libero, list = scelta da lista

_WIZARD_STEPS: dict[str, list[WizardStep]] = {
    "ocr": [
        WizardStep("File",     "Percorso del PDF da elaborare:", "es. ~/Documents/doc.pdf"),
        WizardStep("Lingua",   "Lingua del documento:",          "it / en / it+en", choices=["it", "en", "it+en"]),
        WizardStep("Formato",  "Formato output:",                "pdf / txt",        choices=["pdf", "txt"]),
        WizardStep("Output",   "Percorso file di output:",       "es. ~/Desktop/out.pdf (vuoto = automatico)"),
    ],
    "compress": [
        WizardStep("File",    "Percorso del PDF da comprimere:", "es. ~/Documents/doc.pdf"),
        WizardStep("Livello", "Livello di compressione:",        "low / medium / high", choices=["low", "medium", "high"]),
        WizardStep("Colore",  "Modalità colore:",               "color / gray",         choices=["color", "gray"]),
        WizardStep("Output",  "Percorso file di output:",        "es. ~/Desktop/out.pdf (vuoto = automatico)"),
    ],
}
```

### 3.2 — WizardScreen

```python
class WizardScreen(Screen):
    BINDINGS = [
        Binding("escape", "go_back", "Indietro"),
    ]

    current_step: reactive[int] = reactive(0)

    def __init__(self, mode: str, prefill_path: str = "") -> None:
        super().__init__()
        self._mode = mode                          # "ocr" | "compress"
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
        yield Static(_FOOTER_TEXT_WIZARD, id="footer-bar")

    def on_mount(self) -> None:
        self._render_step(0)
        if self._prefill_path:
            self.query_one("#step-input", Input).value = self._prefill_path

    def watch_current_step(self, step: int) -> None:
        self._render_step(step)

    def _render_step(self, step: int) -> None:
        steps = self._steps
        # Indicatore: "1. File  ▶ 2. Lingua  3. Formato  4. Output"
        parts = []
        for i, s in enumerate(steps):
            marker = "▶ " if i == step else "   "
            parts.append(f"{marker}{i+1}. {s.name}")
        self.query_one("#step-indicator", Static).update("  ".join(parts))
        # Prompt e placeholder
        self.query_one("#step-prompt", Static).update(steps[step].prompt)
        inp = self.query_one("#step-input", Input)
        inp.placeholder = steps[step].placeholder
        inp.value = ""
        inp.focus()
        self.query_one("#step-error", Static).update("")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self._advance(event.value.strip())

    def _advance(self, value: str) -> None:
        step = self.current_step
        s = self._steps[step]
        # Validazione
        err = self._validate(step, value, s)
        if err:
            self.query_one("#step-error", Static).update(err)
            return
        # Salva valore
        self._values[s.name.lower()] = value
        # Passo successivo o fine
        if step + 1 < len(self._steps):
            self.current_step = step + 1
        else:
            self._finish()

    def _validate(self, step: int, value: str, s: WizardStep) -> str:
        """Restituisce stringa errore o "" se valido."""
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
        # Costruisce args namespace e lancia ProgressScreen
        args = self._build_args()
        self.app.push_screen(ProgressScreen(mode=self._mode, args=args))

    def _build_args(self) -> dict:
        """Raccoglie i valori inseriti in un dict normalizzato."""
        v = self._values
        if self._mode == "ocr":
            output = v.get("output", "").strip()
            return {
                "input": resolve_user_path(v["file"]),
                "lang": v.get("lingua", "it"),
                "format": v.get("formato", "pdf"),
                "output": resolve_incremental_output_path(
                    resolve_user_path(output) if output else resolve_user_path(v["file"])
                ) if not output else resolve_user_path(output),
            }
        else:  # compress
            output = v.get("output", "").strip()
            return {
                "input": resolve_user_path(v["file"]),
                "level": v.get("livello", "medium"),
                "color": v.get("colore", "color"),
                "output": resolve_incremental_output_path(
                    resolve_user_path(output) if output else resolve_user_path(v["file"])
                ) if not output else resolve_user_path(output),
            }

    def action_go_back(self) -> None:
        if self.current_step > 0:
            self.current_step -= 1
        else:
            self.app.pop_screen()
```

`_FOOTER_TEXT_WIZARD = "Invio avanza   Esc torna indietro"`

**Anti-pattern:**
- NON usare `Button` per avanzare tra i passi — usare `Input.Submitted` (Enter)
- NON ricaricare `tui.tcss` manualmente — Textual lo fa al mount

### Verifica Phase 3

Test manuale:
1. Aprire TUI → selezionare "Esegui OCR" → wizard si apre al passo 1
2. Inserire un path non valido → errore rosso appare sotto il campo
3. Inserire path valido → avanza al passo 2
4. Premere Esc al passo 2 → torna al passo 1
5. Premere Esc al passo 1 → torna alla HomeScreen
6. Completare tutti i passi → (stub: ProgressScreen non ancora implementata)

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v 2>&1 | tail -5
```

---

## Phase 4: CheckResultScreen + CheckInputScreen

**File modificati:** `src/pydf_tool/tui.py`

### 4.1 — CheckInputScreen (mini-wizard per file input)

Screen minima usata da HomeScreen per raccogliere il path prima di chiamare `check_ocr()`.

```python
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
        # Esecuzione sincrona (< 1s)
        try:
            result = check_ocr(path)
        except PDFToolError as e:
            self.query_one("#check-error", Static).update(str(e))
            return
        self.app.push_screen(CheckResultScreen(result=result, input_path=path))

    def action_go_back(self) -> None:
        self.app.pop_screen()
```

### 4.2 — CheckResultScreen

```python
class CheckResultScreen(Screen):
    BINDINGS = [
        Binding("escape", "go_home", "Menu"),
        Binding("enter", "default_action", "Continua"),
    ]

    def __init__(self, result: CheckOCRResult, input_path) -> None:
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
        if r.verdict in ("ocr_needed", "mixed"):
            yield Button("Esegui OCR su questo file", id="btn-run-ocr")
        yield Button("Torna al menu", id="btn-home")
        yield Static("Invio · Esc torna al menu", id="footer-bar")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-run-ocr":
            self._launch_ocr()
        else:
            self._go_home()

    def action_default_action(self) -> None:
        if self._result.verdict in ("ocr_needed", "mixed"):
            self._launch_ocr()
        else:
            self._go_home()

    def action_go_home(self) -> None:
        self._go_home()

    def _launch_ocr(self) -> None:
        # Pop CheckResultScreen e CheckInputScreen, push WizardScreen con path precompilato
        self.app.pop_screen()  # pop CheckResultScreen
        self.app.pop_screen()  # pop CheckInputScreen
        self.app.push_screen(WizardScreen(mode="ocr", prefill_path=str(self._input_path)))

    def _go_home(self) -> None:
        self.app.pop_screen()  # pop CheckResultScreen
        self.app.pop_screen()  # pop CheckInputScreen


def _verdict_label(verdict: str) -> str:
    return {
        "ocr_needed":       "OCR necessario",
        "already_searchable": "Già ricercabile",
        "mixed":            "Parzialmente ricercabile",
    }.get(verdict, verdict)
```

**Anti-pattern:**
- NON chiamare `check_ocr()` in un Worker — è sincrona e < 1s; il Worker aggiunge complessità inutile
- NON usare `self.app.switch_screen()` — perde lo stack di navigazione

### Verifica Phase 4

Test manuale:
1. Selezionare "Verifica OCR" → appare CheckInputScreen
2. Inserire path non-PDF → errore sotto
3. Inserire PDF valido → appare CheckResultScreen con tabella
4. Se verdetto `ocr_needed`: pulsante "Esegui OCR" visibile → click → apre WizardScreen OCR con path precompilato
5. Pulsante "Torna al menu" → torna alla HomeScreen

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v 2>&1 | tail -5
```

---

## Phase 5: ProgressScreen + Worker

**File modificati:** `src/pydf_tool/tui.py`

### 5.1 — ProgressScreen

```python
import threading

class ProgressScreen(Screen):
    BINDINGS = [
        Binding("ctrl+c", "cancel_op", "Annulla"),
    ]

    progress_value: reactive[int] = reactive(0)
    progress_total: reactive[int] = reactive(100)
    status_message: reactive[str] = reactive("Avvio in corso...")
    is_done: reactive[bool] = reactive(False)
    is_error: reactive[bool] = reactive(False)
    is_cancelled: reactive[bool] = reactive(False)

    def __init__(self, mode: str, args: dict) -> None:
        super().__init__()
        self._mode = mode
        self._args = args
        self._cancel_event = threading.Event()
        self._result_text: str = ""
        self._worker = None

    def compose(self) -> ComposeResult:
        title = "Esegui OCR" if self._mode == "ocr" else "Comprimi PDF"
        yield Static(f"PyDF Tool — {title}", id="header")
        yield Static("", id="status-msg")
        yield ProgressBar(total=100, id="progress-bar", show_eta=False)
        yield Static("", id="elapsed-label")
        yield Static("Ctrl+C per annullare", id="cancel-hint")
        yield Static("", id="footer-bar")

    def on_mount(self) -> None:
        self._worker = self.run_worker(self._run_operation, thread=True)

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
                    output_format=self._args["format"],
                    output_path=self._args["output"],
                    progress_callback=progress_cb,
                )
                self.app.call_from_thread(self._on_success_ocr, result)
            else:
                result = compress_pdf(
                    input_path=self._args["input"],
                    level=self._args["level"],
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

    def _on_success_ocr(self, result) -> None:
        self._show_result(
            f"OCR completato\n\nOutput: {result.output_path}\nPagine: {result.page_count}",
            success=True,
        )

    def _on_success_compress(self, result) -> None:
        change = format_size_change(result.original_size, result.compressed_size)
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
        # Aggiungi binding Enter per tornare
        self.BINDINGS = [Binding("enter", "go_back", "Menu"), Binding("escape", "go_back", "Menu")]
        self._result_ready = True

    def on_key(self, event) -> None:
        if getattr(self, "_result_ready", False) and event.key in ("enter", "escape"):
            self.app.pop_screen()

    def action_cancel_op(self) -> None:
        self._cancel_event.set()
```

**Nota Issue #6:** `_cancel_event.set()` segnala al thread di sollevare `KeyboardInterrupt` alla prossima chiamata alla callback. La granularità è per-pagina (non per-frame Tesseract). Questo è un limite architetturale documentato — non risolvere in questa fase.

**Anti-pattern:**
- NON chiamare `worker.cancel()` come meccanismo principale — Textual Worker non può interrompere processi C bloccanti. Usare il `threading.Event`.
- NON aggiornare widget direttamente dal thread del Worker — usare sempre `call_from_thread()`
- NON usare `self.BINDINGS =` in fase operativa — i binding dinamici si gestiscono via `on_key`

### Verifica Phase 5

Test manuale (su PDF di esempio piccolo):
1. Completare il wizard OCR → ProgressScreen si apre con barra progress
2. La barra avanza pagina per pagina
3. Al termine: barra scompare, mostra output path e conteggio pagine
4. Enter → torna alla HomeScreen

```bash
# Smoke test compress su PDF reale
pydf-tool compress "PDF Sample/sample.pdf" --level medium --output /tmp/test_compress.pdf

PYTHONPATH=src python3 -m unittest discover -s tests -v 2>&1 | tail -5
```

---

## Phase 6: Entry points pubblici

**File modificati:** `src/pydf_tool/tui.py`

### 6.1 — run_interactive_app

```python
def run_interactive_app(
    *,
    parser_factory: Callable[[], argparse.ArgumentParser],
    executor: Callable[[argparse.Namespace], int],
) -> int:
    """Entry point TUI. Firma invariata — cli.py non cambia."""
    app = PyDFApp(parser_factory=parser_factory, executor=executor)
    app.run()
    return 0
```

### 6.2 — dispatch_interactive_command

```python
def dispatch_interactive_command(
    command_line: str,
    *,
    parser_factory: Callable[[], argparse.ArgumentParser],
    executor: Callable[[argparse.Namespace], int],
) -> int:
    """Esegue un comando CLI testuale dalla TUI (es. 'ocr file.pdf --lang it').
    Firma invariata — cli.py non cambia.
    """
    try:
        args_list = shlex.split(command_line)
    except ValueError:
        return 1
    try:
        parser = parser_factory()
        ns = parser.parse_args(args_list)
        return executor(ns)
    except SystemExit as e:
        return int(e.code) if e.code is not None else 1
```

**Nota:** `dispatch_interactive_command` non usa Textual — si comporta come una chiamata CLI diretta. Non cambia rispetto alla versione precedente.

### Verifica Phase 6

```bash
# Import completo senza errori
PYTHONPATH=src python3 -c "from pydf_tool.tui import run_interactive_app, dispatch_interactive_command; print('OK')"

# cli.py chiama correttamente — verifica che --help funzioni
PYTHONPATH=src python3 -m pydf_tool --help

# Suite
PYTHONPATH=src python3 -m unittest discover -s tests -v 2>&1 | tail -5
```

---

## Phase 7: Aggiornamento test + verifica finale

**File modificati:** `tests/test_cli.py`

### 7.1 — Test da eliminare

Rimuovere completamente (funzioni non esistono più in Textual):
- `test_dialog_width_shrinks_with_terminal`
- `test_wrap_dialog_text_wraps_bullets_with_indentation`

### 7.2 — test_interactive_shell_runs_guided_ocr_flow

Sostituire il test con una verifica che `run_interactive_app` chiama `PyDFApp.run()`:

```python
@patch("pydf_tool.tui.PyDFApp.run")
def test_interactive_shell_runs_app(self, mock_run):
    mock_run.return_value = None
    result = run_interactive_app(
        parser_factory=build_parser,
        executor=_execute_handler,
    )
    mock_run.assert_called_once()
    self.assertEqual(result, 0)
```

### 7.3 — test_dispatch_interactive_command_supports_direct_ocr_command

Il test resta strutturalmente simile — `dispatch_interactive_command` parsa ancora command_line tramite argparse e chiama `executor`. Aggiornare solo i mock se cambiano i path:

```python
def test_dispatch_interactive_command_supports_direct_ocr_command(self):
    with patch("pydf_tool.tui.run_ocr") as mock_ocr, \
         patch("pydf_tool.ocr.run_ocr") as mock_ocr2:
        # Il test già mocka run_ocr — verificare quale path è corretto dopo Phase 5
        # e aggiornare il patch di conseguenza
        ...
```

**Nota:** leggere il test attuale prima di modificare — il patch path potrebbe già essere corretto.

### 7.4 — Verifica finale

```bash
# Conta test (deve essere 33 o più — 35 - 2 eliminati)
PYTHONPATH=src python3 -m unittest discover -s tests -v 2>&1 | grep -E "^(OK|FAILED|ERROR|Ran)"

# Zero FAILED, zero ERROR
PYTHONPATH=src python3 -m unittest discover -s tests -v

# Smoke test completo
PYTHONPATH=src python3 -m pydf_tool --help
PYTHONPATH=src python3 -m pydf_tool check --help
PYTHONPATH=src python3 -m pydf_tool ocr --help
PYTHONPATH=src python3 -m pydf_tool compress --help

# Avvio TUI manuale
PYTHONPATH=src python3 -m pydf_tool
```

---

## Anti-pattern globali

| Anti-pattern | Perché è sbagliato |
|---|---|
| `background: #...` nel CSS | CLAUDE.md: sfondo sempre trasparente |
| `App.switch_screen()` | Distrugge lo stack di navigazione |
| `worker.cancel()` come unico meccanismo di cancellazione | Non interrompe processi C bloccanti |
| Aggiornare widget direttamente dal Worker thread | Textual non è thread-safe — usare `call_from_thread()` |
| `from rich import ...` come import diretto | Rich è transitivo via Textual, non dipendenza diretta |
| `from prompt_toolkit import ...` | Rimossa da pyproject.toml |
| `self.BINDINGS = [...]` a runtime | I binding dinamici si gestiscono via `on_key` |
| `App.run_sync()` invece di `App.run()` | `run()` è il metodo corretto per l'event loop |

---

## Ordine di esecuzione raccomandato

```
Phase 1 → reinstall → suite verde
Phase 2 → import + avvio TUI manuale
Phase 3 → wizard navigabile manualmente
Phase 4 → check flow completo manualmente
Phase 5 → progress su PDF reale
Phase 6 → entry points + CLI funziona
Phase 7 → suite finale verde
```

Ogni fase deve lasciare la suite verde prima di procedere alla successiva.
