# PROJECT CONTEXT — PyDF Tool

Documento unico di handoff. Da aggiornare a ogni sessione significativa.
Leggere questo file è sufficiente per riprendere il lavoro senza rileggere il codice da zero.

---

## Identità

- Nome: `PyDF Tool`
- Comando: `pydf-tool`
- Linguaggio: Python 3.10+
- Piattaforma target: macOS
- Modalità: TUI interattiva (`textual`) e CLI diretta (`argparse`)
- Funzioni attuali: OCR di PDF scansionati, compressione PDF

---

## Layout repository

```
.
├── pyproject.toml
├── README.md
├── COMPONENTS.md          # inventario dipendenze e licenze
├── PROJECT_CONTEXT.md     # questo file
├── .gitignore
├── src/
│   └── pydf_tool/
│       ├── __init__.py
│       ├── __main__.py    # entry point per `python -m pydf_tool`
│       ├── cli.py         # argparse, routing CLI/TUI, error boundary
│       ├── tui.py         # TUI Textual (in migrazione da prompt_toolkit+rich)
│       ├── tui.tcss       # CSS Textual con palette CLAUDE.md
│       ├── ocr.py         # pipeline OCR (pdf2image + pytesseract + pypdf)
│       ├── compress.py    # pipeline compressione (Ghostscript)
│       ├── progress.py    # dataclass OperationProgress
│       ├── utils.py       # path helpers, Unicode normalization, size format
│       └── errors.py      # PDFToolError
└── tests/
    └── test_cli.py        # 35 test unittest
```

---

## Dipendenze

### Python (pyproject.toml)

| Pacchetto | Versione |
|---|---|
| pdf2image | 1.17.0 |
| textual | >=0.70.0 (installata: 8.2.1) |
| pypdf | 6.8.0 |
| pytesseract | 0.3.13 |
| Pillow | >=10.3.0,<12.0 |

Note:
- `prompt_toolkit` e `rich` rimossi come dipendenze dirette (2026-03-30, Issue #3).
  `rich` resta presente come dipendenza transitiva di `textual`.
- `Pillow==12.x` è incompatibile con `pypdf==6.8.0` (accesso a `PIL.__version__` rimosso).
  Il pin è stato corretto a `>=10.3.0,<12.0`.

### Sistema (Homebrew)

```bash
brew install tesseract tesseract-lang poppler ghostscript
```

---

## Installazione e verifica

**Metodo canonico — usare sempre `setup.sh`:**

```bash
rm -rf .venv && bash setup.sh
source .venv/bin/activate
pydf-tool --help
```

`setup.sh` fa tre cose: (1) crea la venv, (2) esegue `pip install -e .`, (3) **patcha
il wrapper `.venv/bin/pydf-tool`** iniettando il path assoluto di `src/` direttamente
nello script prima dell'import. Va rieseguito dopo ogni `pip install -e .` manuale.

**Nota critica — Python.org Python 3.12 su macOS (workaround definitivo):**
Il `site.py` del Python.org Python 3.12 salta tutti i `.pth` file marcati con il flag
filesystem macOS `UF_HIDDEN`. Il comando `python3 -m venv .venv` imposta `UF_HIDDEN`
sull'intera cartella `.venv` — tutti i `.pth` installati da pip vengono saltati →
`ModuleNotFoundError: No module named 'pydf_tool'`.

Approcci precedenti tentati:
- `chflags -R nohidden .venv` → parziale: pip ricreava i file con UF_HIDDEN
- `sitecustomize.py` in site-packages → pip lo eliminava/sovrascriveva in reinstall

Soluzione definitiva (2026-03-26): `setup.sh` patcha direttamente il file
`.venv/bin/pydf-tool` con un blocco `sys.path.insert(0, src_path)` hardcoded prima
dell'import. Il path di `src/` è iniettato come stringa assoluta dallo script bash.
Non dipende da `.pth` né da `sitecustomize.py`.

**Workflow dopo modifiche al codice:**

| Cosa è cambiato | Cosa fare |
|---|---|
| File in `src/` (codice Python) | Solo riavviare `pydf-tool` — nessun reinstall |
| `pyproject.toml` (dipendenze) | `pip install -e .` poi `bash setup.sh` |
| Venv corrotta / errore all'avvio | `rm -rf .venv && bash setup.sh` |

Suite di test:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

Smoke check compressione:

```bash
pydf-tool compress "input.pdf" --level medium --output /tmp/test.pdf
```

Smoke check OCR:

```bash
pydf-tool ocr "input.pdf" --lang it --output /tmp/test.pdf
```

---

## Architettura — punti chiave

### cli.py

- `build_parser()`: definisce tutta la superficie CLI
- `main()`: se nessun argomento → TUI; altrimenti dispatch al handler
- `_execute_handler()`: traduce `PDFToolError` in stderr + exit code 1
- `_run_interactive_shell_safe()`: wrapper con error boundary per la TUI

### tui.py

- `run_interactive_app()`: avvia `PyDFApp` (Textual) — firma invariata, cli.py non cambia
- `dispatch_interactive_command()`: parsa comandi CLI testuali — firma invariata
- `PyDFApp`: `textual.App`, monta `HomeScreen` all'avvio, carica `tui.tcss`
- `HomeScreen`: layout two-panel (ListView menu + preview Static), HelpScreen modal su H/F1
- `WizardScreen`: stepper 4 passi per OCR e Comprimi; validazione inline per step File
- `CheckInputScreen` / `CheckResultScreen`: flusso Verifica OCR sincrono (< 1s, no Worker)
- `ProgressScreen`: operazione in `@work(thread=True)`; aggiornamenti via `call_from_thread()`; cancellazione via `threading.Event`

### ocr.py

- `run_ocr()`: pipeline completa; accetta `progress_callback`
- `resolve_tesseract_languages()`: mappa `it/en/it+en` → codici Tesseract
- Lingue supportate: `it`, `ita`, `en`, `eng` — estendibile in `SUPPORTED_LANGUAGE_CODES`
- Output: `.pdf` (searchable PDF via pypdf.PdfWriter) o `.txt`
- Problema aperto: tutte le pagine caricate in RAM simultaneamente (Issue #1)

### compress.py

- `compress_pdf()`: pipeline Ghostscript; accetta `progress_callback`
- `resolve_compression_profile()`: mappa preset (low/medium/high) o numerico 1-100
- Staging: output sempre scritto in temp dir, poi spostato a destinazione
- Input Unicode: se il path contiene caratteri non-ASCII, l'input viene copiato in temp dir ASCII-safe
- Progress TUI: parsing `"Page N"` da stdout Ghostscript

### utils.py

- `resolve_user_path()`: normalizza varianti Unicode macOS (NFC/NFD/NFKC/NFKD)
- `ensure_pdf_input()`: verifica esistenza e estensione .pdf
- `resolve_incremental_output_path()`: genera nome incrementale (`file.1.pdf`, `file.2.pdf`, ...)

---

## Stato corrente

### Verificato e funzionante

- `pydf-tool --help`, `pydf-tool help`, `pydf-tool help ocr/compress/check`
- TUI: avvio, navigazione home, help dialog
- TUI: sottomenu "Strumento OCR" con "Verifica OCR" e "Esegui OCR"
- TUI: dialog "Esegui OCR" e "Comprimi PDF" con wizard guidato
- TUI: progress live compressione (barra + pagine)
- TUI: progress live OCR (pagina per pagina, low-memory)
- CLI: compressione con output in `/tmp` su PDF reale
- CLI: OCR su PDF di esempio piccoli
- Normalizzazione path Unicode (NFC/NFD): coperta da test e verificata
- Staging Ghostscript per path Unicode: coperto da test e verificato
- Suite 35 test: verde
- Modulo rinominato `pydf_tool` (era `pdf_tool`) — entry point, test, wrapper, docs aggiornati
- TUI: layout box-drawing Unicode con palette CLAUDE.md, sfondo trasparente
- Code quality: ruff clean (F401, I001, UP035, RET505 risolti), formatting applicato

### Completato (2026-03-30) — Sessione 3.0

**Migrazione TUI: prompt_toolkit + rich → Textual (Issue #3) — COMPLETATA**

Obiettivo: eliminare l'alternanza prompt_toolkit/rich che rende la TUI fragile su terminali
non-standard. Textual unifica layout, dialog, progress e keybinding in un solo framework
reattivo (modello CSS + widget).

**Tutte le fasi completate:**
- Phase 1: `pyproject.toml` aggiornato; `tui.tcss` creato con palette CLAUDE.md
- Phase 2: `PyDFApp` + `HomeScreen` (two-panel) + `HelpScreen` (modal)
- Phase 3: `WizardScreen` stepper (4 passi OCR, 4 passi Comprimi) con validazione inline
- Phase 4: `CheckInputScreen` + `CheckResultScreen` con offerta avvio OCR se necessario
- Phase 5: `ProgressScreen` con `@work(thread=True)` + `threading.Event` per cancellazione
- Phase 6: entry points `run_interactive_app` e `dispatch_interactive_command` (firme invariate)
- Phase 7: test aggiornati — rimossi `_dialog_width`/`_wrap_dialog_text`; aggiornato mock a `PyDFApp.run`

**Suite: 33 test, tutti verdi** (da 35: rimossi 2 test di funzioni non più esistenti)

Spec: `docs/superpowers/specs/2026-03-29-textual-migration-design.md` ✓
Piano: `docs/superpowers/plans/2026-03-30-textual-migration-plan.md` ✓

### Decisioni di design approvate (brainstorming 2026-03-29)

**Wizard style: Stepper (opzione B)**
- Una singola WizardScreen con indicatore di passo in cima (es. "1. File  ▶ 2. Lingua  3. Formato  4. Output")
- Il contenuto cambia al passo corrente, il titolo e la barra step restano visibili
- Esc torna al passo precedente (o alla home se al passo 1)

**Progress screen: Schermata dedicata (opzione A)**
- App.push_screen(ProgressScreen) quando parte l'operazione
- Copre tutta la finestra: niente home in background
- L'operazione gira in un Textual Worker (thread separato)
- Aggiornamenti via app.call_from_thread()
- Al termine: contenuto cambia da progress bar a riepilogo risultato
- "Invio per tornare al menu" → pop_screen()

**Struttura App:**
```
PyDFApp (textual.App)
├── HomeScreen           ← menu + pannello anteprima (layout two-panel)
├── WizardScreen         ← stepper per OCR (4 passi) e Comprimi (4 passi)
├── ProgressScreen       ← avanzamento operazione lunga + risultato
├── CheckResultScreen    ← risultato Verifica OCR (check è sincrono, < 1s)
└── HelpScreen           ← modal overlay help
```

**Nota Verifica OCR:** `check_ocr()` è sincrona e veloce — nessuna ProgressScreen.
Il risultato appare in CheckResultScreen; se `ocr_needed`/`mixed`, offre di lanciare WizardScreen OCR con path precompilato.

**HomeScreen header (opzione D approvata):**
```
┌──────────────────────────────────────────────────┐
│                                                  │
│   ╠══ PyDF Tool ══╣   OCR  ·  compress  ·  check │
│                                                  │
│   ─────────────────────────────────────────────  │
│   strumenti PDF da riga di comando · macOS       │
│                                                  │
└──────────────────────────────────────────────────┘
```
Il titolo è incorniciato con `╠══╣`, affiancato dalle tre funzioni chiave.
Separatore orizzontale divide titolo dalla tagline.

**Entry point:** `run_interactive_app(parser_factory, executor)` — firma invariata, cli.py non cambia.

**Dipendenze:**
- `textual` entra in pyproject.toml
- `prompt_toolkit` esce da pyproject.toml
- `rich` esce come dipendenza diretta (Textual lo porta come dipendenza interna)

**File invariati:** `cli.py`, `ocr.py`, `compress.py`, `check_ocr.py`, `utils.py`, `progress.py`, `errors.py`
**File riscritto:** `tui.py` (da zero, stesso nome)
**CSS Textual:** `src/pydf_tool/tui.tcss` (nuovo file con palette CLAUDE.md)

**Palette CLAUDE.md invariata:**
- Accento: `#E8B84B` — voce selezionata, titoli, step attivo
- Testo: `#D4D4D4`
- Secondario: `#7A7A7A` — hint, label, step inattivi
- Bordi: `#3A3A3A`
- Errore: `#E85B4B`
- Successo: `#4BE87A`
- Sfondo: trasparente (nessun `background` esplicito nel CSS)

**Test:** i 4 test che testano funzioni di tui.py (`_dialog_width`, `_wrap_dialog_text`,
mock di `_show_home_menu`/`_show_ocr_submenu`) saranno aggiornati; i 31 test backend restano invariati.

### Fix applicati (2026-03-29) — Sessione 2.0

**Code quality (ruff):**
- `tui.py`: rimosso `from pathlib import Path` inutilizzato (F401)
- `tui.py`: `from typing import Callable` → `from collections.abc import Callable` (UP035)
- `cli.py`: `from typing import Sequence` → `from collections.abc import Sequence` (UP035)
- `compress.py` + `ocr.py`: ordinamento alfabetico import nel blocco `from .utils import` (I001)
- `tui.py:959`: rimosso `else` superfluo dopo `return` in `_show_check_result` (RET505)
- Formatting (ruff format): indentazione lista `command` in `compress.py`, line-length 88 in più punti

**Debito tecnico noto (non toccato):**
- `_emit_progress` duplicata verbatim in `ocr.py` e `compress.py` — spostare in `progress.py`
- `bare except Exception` in `check_ocr.py:47` — intentionale (pypdf su pagine corrotte)
- Import lazy dentro funzione (`from pypdf import ...`) — intentionale (lazy load)

### Fix applicati (2026-03-28) — Sessione 1.0

**Rinomina semantica modulo `pdf_tool` → `pydf_tool`:**
- Directory `src/pdf_tool/` rinominata in `src/pydf_tool/`
- `pyproject.toml`: entry point aggiornato a `pydf_tool.cli:main`
- `tests/test_cli.py`: tutti gli import e le stringhe `patch(...)` aggiornati
- `setup.sh`: import nel wrapper patchato + commenti aggiornati
- `ISTRUZIONI.txt`: messaggio di errore "No module named" aggiornato
- `PROJECT_CONTEXT.md`: tutti i path e riferimenti al modulo aggiornati

**TUI — applicazione design system (CLAUDE.md globale):**
- Palette colori: `#E8B84B` accento, `#D4D4D4` testo, `#7A7A7A` secondario, `#3A3A3A` bordi, `#E85B4B` errore, `#4BE87A` successo
- `_dialog_style()`: tutti i colori allineati alla palette
- Home menu style: accento su brand, voce selezionata, titoli sezioni
- Output Rich: progress bar `#E8B84B`, errori `#E85B4B`, successo `#4BE87A`, annullato `#3A3A3A`
- Sfondo trasparente: rimossi tutti i `bg:#` espliciti; cursore text-area usa `reverse` nativo

**TUI — redesign strutturale layout (box-drawing Unicode):**
- Header: box completo `┌─ PyDF Tool ─┐` con tagline e summary dentro
- Menu: box `┌─ Azioni ─┐` con items; item selezionato in `#E8B84B bold`
- Detail: box `┌─ Anteprima ─┐` con heading, testo, comando
- Separatore header→body: riga vuota; separatore body→footer: `─` pieno
- Rimosso divider `│` tra menu e detail; sostituito con spaziatore `Window(width=2)`
- Helper interni: `_box_top`, `_box_bottom`, `_box_line`, `_box_blank`

### Fix applicati (2026-03-28) — Sessione precedente

**TUI — crash e chiusure improvvise: 4 fix:**
- **`_pause()` EOFError**: aggiunto `try/except EOFError: pass` — evita crash quando stdin è in stato strano dopo prompt_toolkit full-screen
- **Issue #2 risolto — monkey-patch RadioList eliminato**: sostituito con `@kb.add("enter", eager=True)` che legge `radio_list.values[radio_list._selected_index][0]` e chiama `event.app.exit()` — nessun monkey-patch, nessun `try/except Exception: pass` silente
- **`_run_interactive_shell_safe()` cattura EOFError**: aggiunto `EOFError` a fianco di `KeyboardInterrupt` nel boundary top-level
- **Issue #4 risolto — validazione path early**: `_prompt_ocr_args()`, `_prompt_compress_args()`, `_prompt_check_args()` ora chiamano `ensure_pdf_input()` subito dopo `_ask_text()` — se il path è invalido mostra `_show_info_dialog()` e ritorna `None` immediatamente, prima di aprire ulteriori dialog

### Modifiche applicate (2026-03-27)

**TUI — ristrutturazione menu e testi:**
- Header: `APP_TAGLINE` e `APP_SUMMARY` riformulati
- Home menu: "Verifica OCR" e "OCR assistito" unificate in "Strumento OCR" (key: `ocr_tool`)
- Aggiunto `_show_ocr_submenu()`: dialog con "Verifica OCR" e "Esegui OCR"
- "OCR assistito" rinominato "Esegui OCR" in tutti i dialog e titoli
- "Compressione" rinominata "Comprimi PDF" in tutti i dialog e titoli
- Help screen aggiornato con nuova struttura menu
- Test aggiornato: `test_interactive_shell_runs_guided_ocr_flow` ora mocka `_show_home_menu` con `"ocr_tool"` e `_show_ocr_submenu` con `"ocr"`

**TUI — Verifica OCR: risultati visibili (fix critico):**
- Problema: `_run_check_interactive` mostrava i risultati con rich (Console/Panel), poi chiamava `_ask_choice()` con `full_screen=True` che avviava un'app prompt_toolkit e cancellava il terminale — i risultati erano invisibili
- Soluzione: eliminato rich da `_run_check_interactive`; aggiunto `_show_info_dialog(title, text)` (pura prompt_toolkit, stesso pattern di `_show_help_screen`) e `_show_check_result(result, input_path)` che mostra statistiche e verdetto in dialog prompt_toolkit
- Se verdetto è `ocr_needed` o `mixed`: `_ask_choice()` con opzioni "Esegui OCR" / "Torna al menu"
- Se verdetto è `already_searchable`: `_show_info_dialog()` con i dati, chiudibile con Invio/Esc

**OCR RAM fix (Issue #1 risolto):**
- `ocr.py`: quando `page_count` è noto (da PdfReader), ogni pagina viene convertita con `convert_from_path(first_page=N, last_page=N)` e liberata subito
- Picco RAM: ~26 MB/pagina invece di N×26 MB (50 pagine: 26 MB vs ~1.3 GB)
- Fallback batch mantenuto per quando `page_count` è None (PdfReader ha fallito)
- Test aggiornato: `fake_convert_from_path` accetta `first_page`/`last_page` kwargs

### Fix applicati (2026-03-26)

- **P1.1**: aggiunto `_emit_progress(stage="done")` nel path OCR `.txt` (mancava)
- **P1.2**: `_run_ocr_interactive` / `_run_compress_interactive` ora restituiscono `1` su errore (prima sempre `0`)
- **P1.3**: `-dQUIET` in append invece di `insert(4, ...)` — robusto a variazioni della struttura comando
- **Test**: `test_compress_pdf_uses_staged_paths_for_unicode_locations` cerca source file tra argomenti posizionali, non assume `command[-1]`
- **Pillow pin**: cambiato da `==12.1.1` a `>=10.3.0,<12.0` (incompatibilità con pypdf 6.8.0)
- **P3.1**: migrazione da `script-files` a `[project.scripts]` entry point standard; `scripts/pydf-tool` eliminato; i 2 test sul bootstrap sostituiti con `test_pyproject_configures_entry_point` e `test_entry_point_target_is_callable`
- **Check OCR**: nuovo modulo `check_ocr.py`, subcommand `pydf-tool check`, sottomenu TUI in "Strumento OCR"; soglia 50 char/pagina; verdetti `ocr_needed` / `already_searchable` / `mixed`

---

## Issue aperte — per priorità

### Priorità 2 (fix concreti, alta urgenza)

**~~Issue #1 — OCR: tutte le pagine in RAM~~** — RISOLTO (2026-03-27)
- `convert_from_path()` ora chiamata per singola pagina con `first_page=N, last_page=N`
- Fallback batch per i casi in cui PdfReader non riesce a leggere il page count

**~~Issue #2 — TUI: monkey-patch `_handle_enter` su RadioList~~** — RISOLTO (2026-03-28)
- Sostituito con `@kb.add("enter", eager=True)` + `radio_list.values[radio_list._selected_index][0]`

**~~Issue #3 — TUI: alternanza prompt_toolkit / rich~~** — RISOLTO (2026-03-30)
- `tui.py` riscritto interamente in Textual (tutte le 7 fasi completate)
- Spec: `docs/superpowers/specs/2026-03-29-textual-migration-design.md`
- Piano: `docs/superpowers/plans/2026-03-30-textual-migration-plan.md`

**~~Issue #4 — Validazione path input troppo tardiva nel wizard TUI~~** — RISOLTO (2026-03-28)
- `ensure_pdf_input()` ora chiamata in tutti e tre i wizard subito dopo `_ask_text()`; errore mostrato con `_show_info_dialog()` prima di aprire dialog successivi

### Priorità 3 (architetturali)

**~~Issue #5 — `script-files` invece di `console_scripts`~~** — RISOLTO
- Migrato a `[project.scripts]` standard; `scripts/pydf-tool` eliminato

**Issue #6 — OCR sincrono, non interrompibile dentro chiamate C Tesseract**
- File: `ocr.py`, `tui.py`
- `Ctrl+C` è servito tra una pagina e l'altra, non dentro la singola chiamata Tesseract
- Su pagine pesanti, finestra di reattività lunga
- Fix: thread worker con cancellation event

### Gap nei test

- Nessun test per OCR output `.pdf` (solo `.txt` testato)
- Nessun test per `_run_compress_interactive` TUI path
- Nessun test per `_prompt_output_path`
- Nessun test per `human_size` / `format_size_change`
- Nessun test per `resolve_incremental_output_path` con file già esistenti
- Nessun test end-to-end con Ghostscript / Tesseract reali

---

## Prossimi passi — in ordine

| # | Task | Tipo | Urgenza |
|---|---|---|---|
| 1 | ~~**Feature: Check OCR**~~ — `pydf-tool check input.pdf` | Feature | FATTO |
| 2 | ~~**Issue #5** — Migrazione a `console_scripts`~~ | Arch | FATTO |
| 3 | ~~**Issue #4** — Validazione path early nel wizard~~ | Fix | FATTO |
| 4 | ~~**Issue #1** — OCR page-by-page (memoria)~~ | Fix | FATTO |
| 5 | ~~**Issue #2** — Fix monkey-patch RadioList~~ | Fix | FATTO |
| 6 | Colmare gap test (OCR .pdf, compress TUI, utils) | Test | Media |
| 7 | **Issue #6** — OCR in thread worker | Arch | Bassa |
| 8 | ~~**Issue #3** — Unificare framework TUI → migrazione a Textual~~ | Arch | FATTO |

---

## Feature: Check OCR — spec

Funzione da implementare in `src/pydf_tool/check_ocr.py`:

```
check_ocr(path) -> CheckOCRResult
  pages_total: int
  pages_with_text: int       # pagine con > 50 caratteri estratti
  pages_without_text: int
  verdict: "ocr_needed" | "already_searchable" | "mixed"
  chars_per_page_avg: float
```

Soglia suggerita: 50 caratteri/pagina per discriminare immagine vs testo.

Superficie CLI da aggiungere:
- `pydf-tool check input.pdf` → output tabellare (rich)

Superficie TUI da aggiungere:
- Nuova voce menu home: `Verifica OCR`
- Pannello risultato con verdict + offerta di procedere con OCR se `ocr_needed` o `mixed`

Tocca:
- `src/pydf_tool/check_ocr.py` (nuovo)
- `src/pydf_tool/cli.py` (nuovo subparser `check`)
- `src/pydf_tool/tui.py` (nuova voce `_home_actions`, nuovo dialog, nuovo branch in `run_interactive_app`)
- `tests/test_cli.py` (nuovi test)
- `README.md` (nuovo esempio)

---

## Note operative

- OCR reale su PDF grandi può sembrare bloccato: è normale, non è un hang
- Ghostscript può produrre file più grandi dell'originale su PDF già ottimizzati
- Scritture in `~/Documents` non verificabili in ambienti sandbox: testare sulla macchina locale
- Dopo aggiornamenti di Python la venv può corrompersi: `rm -rf .venv && bash setup.sh`
- Il comando `pydf-tool` funziona solo con la venv attiva (`source .venv/bin/activate`)
- **P3.1 applicato**: non esiste più `scripts/pydf-tool`; l'entry point è gestito da `[project.scripts]`
- **UF_HIDDEN fix definitivo**: `setup.sh` patcha `.venv/bin/pydf-tool` con `sys.path.insert(0, src)` hardcoded; non dipende più da `.pth` né da `sitecustomize.py`
- Modifiche al codice in `src/` sono immediate (editable install); basta rilanciare `pydf-tool`
- Dopo `pip install -e .` manuale: rieseguire `bash setup.sh` per ripristinare il patch
