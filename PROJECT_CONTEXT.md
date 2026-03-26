# PROJECT CONTEXT — PyDF Tool

Documento unico di handoff. Da aggiornare a ogni sessione significativa.
Leggere questo file è sufficiente per riprendere il lavoro senza rileggere il codice da zero.

---

## Identità

- Nome: `PyDF Tool`
- Comando: `pydf-tool`
- Linguaggio: Python 3.10+
- Piattaforma target: macOS
- Modalità: TUI interattiva (`prompt_toolkit` + `rich`) e CLI diretta (`argparse`)
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
│   └── pdf_tool/
│       ├── __init__.py
│       ├── __main__.py    # entry point per `python -m pdf_tool`
│       ├── cli.py         # argparse, routing CLI/TUI, error boundary
│       ├── tui.py         # TUI full-screen, dialog, progress
│       ├── ocr.py         # pipeline OCR (pdf2image + pytesseract + pypdf)
│       ├── compress.py    # pipeline compressione (Ghostscript)
│       ├── progress.py    # dataclass OperationProgress
│       ├── utils.py       # path helpers, Unicode normalization, size format
│       └── errors.py      # PDFToolError
└── tests/
    └── test_cli.py        # 30 test unittest
```

---

## Dipendenze

### Python (pyproject.toml)

| Pacchetto | Versione |
|---|---|
| pdf2image | 1.17.0 |
| prompt_toolkit | 3.0.42 |
| pypdf | 6.8.0 |
| pytesseract | 0.3.13 |
| rich | 13.7.1 |
| Pillow | >=10.3.0,<12.0 |

Nota: `Pillow==12.x` è incompatibile con `pypdf==6.8.0` (accesso a `PIL.__version__` rimosso).
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
`ModuleNotFoundError: No module named 'pdf_tool'`.

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

- `run_interactive_app()`: event loop principale (while True → home menu → azione)
- `_show_home_menu()`: prompt_toolkit full-screen Application
- `_ask_choice()` / `_ask_text()`: dialog input utente
- `_run_with_progress()`: rich Console + Progress bar durante operazione
- `dispatch_interactive_command()`: parsa comandi manuali nella TUI
- Architettura: alterna prompt_toolkit (menu/dialog) e rich (progress) — vedi Issue #3

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

**Issue #2 — TUI: monkey-patch `_handle_enter` su RadioList**
- File: `tui.py:606-615`
- Sovrascrive metodo privato di `prompt_toolkit.RadioList`
- `try/except Exception: pass` inghiotte errori silenziosamente
- Fragile a aggiornamenti di `prompt_toolkit`
- Fix: keybinding esplicito `Enter` che legge `radio_list.current_value` e chiama `get_app().exit()`

**Issue #3 — TUI: alternanza prompt_toolkit / rich**
- File: `tui.py:997-1037`
- Ogni ciclo: prompt_toolkit full-screen → rich Console → prompt_toolkit
- Strutturalmente fragile su terminali non-standard
- Mitigazione a lungo termine: unificare su un solo framework

**Issue #4 — Validazione path input troppo tardiva nel wizard TUI**
- File: `tui.py:701-703`
- Il path viene validato solo quando `run_ocr` / `compress_pdf` partono
- L'utente scopre l'errore dopo aver completato tutti i dialog
- Fix: chiamare `ensure_pdf_input()` subito dopo `_ask_text()` nel wizard

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
| 3 | **Issue #4** — Validazione path early nel wizard | Fix | Media |
| 4 | ~~**Issue #1** — OCR page-by-page (memoria)~~ | Fix | FATTO |
| 5 | **Issue #2** — Fix monkey-patch RadioList | Fix | Media |
| 6 | Colmare gap test (OCR .pdf, compress TUI, utils) | Test | Media |
| 7 | **Issue #6** — OCR in thread worker | Arch | Bassa |
| 8 | **Issue #3** — Unificare framework TUI | Arch | Bassa |

---

## Feature: Check OCR — spec

Funzione da implementare in `src/pdf_tool/check_ocr.py`:

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
- `src/pdf_tool/check_ocr.py` (nuovo)
- `src/pdf_tool/cli.py` (nuovo subparser `check`)
- `src/pdf_tool/tui.py` (nuova voce `_home_actions`, nuovo dialog, nuovo branch in `run_interactive_app`)
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
