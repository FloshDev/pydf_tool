# REPORT VIBE CODING

## Executive Summary

`PyDF Tool` e una CLI/TUI Python per macOS. Il comando da terminale e `pydf-tool`.

Il progetto e dedicato a due operazioni su PDF:

- OCR di PDF scansionati verso PDF ricercabile o `.txt`
- compressione PDF con preset `low`, `medium`, `high` o livello numerico custom

Il progetto supporta due modalita di utilizzo:

- modalita diretta a sottocomandi: `pydf-tool ocr ...`, `pydf-tool compress ...`
- modalita interattiva full-screen: `pydf-tool` oppure `pydf-tool interactive`

La TUI e volutamente minimalista, con estetica pulita e focus keyboard-first, ispirata a Claude: pochi elementi, gerarchia visiva chiara, preview essenziale e dialog guidati.

## Current State

- Linguaggi OCR supportati dalla CLI: `it`, `en`, `it+en`
- Output OCR supportati: `.pdf`, `.txt`
- Default OCR: salvataggio nella stessa cartella dell input con nome incrementale come `documento.1.pdf`
- Compressione supportata: preset espliciti, livello numerico `1-100` e opzione opt-in in bianco e nero
- Default compression: salvataggio nella stessa cartella dell input con nome incrementale come `documento.1.pdf`
- Output personalizzato: da TUI o CLI si puo scegliere cartella e nome file
- Help disponibile sia come `-h/--help` sia come `pydf-tool help [ocr|compress|interactive]`
- TUI con:
  - home menu a frecce `up/down`
  - schermata help dedicata
  - layout home responsive che passa da split a stack su terminali piu stretti
  - preview essenziale della voce selezionata
  - dialog keyboard-first: `Enter` conferma, `Esc` annulla
  - progress live
  - annullamento con `Ctrl+C`

## Repository Layout

```text
.
├── pyproject.toml
├── README.md
├── COMPONENTS.md
├── REPORT VIBE CODING.md
├── scripts/
│   └── pydf-tool
├── src/
│   └── pdf_tool/
│       ├── __init__.py
│       ├── __main__.py
│       ├── cli.py
│       ├── tui.py
│       ├── ocr.py
│       ├── compress.py
│       ├── progress.py
│       ├── utils.py
│       └── errors.py
└── tests/
    └── test_cli.py
```

## Read Order For A New Agent

Per orientarsi in fretta:

1. `README.md`
2. `pyproject.toml`
3. `src/pdf_tool/cli.py`
4. `src/pdf_tool/tui.py`
5. `src/pdf_tool/ocr.py`
6. `src/pdf_tool/compress.py`
7. `tests/test_cli.py`
8. `COMPONENTS.md`

## Module Map

### `src/pdf_tool/cli.py`

Responsabilita:

- costruisce il parser `argparse`
- espone i sottocomandi `ocr`, `compress`, `interactive`, `help`
- in assenza di argomenti avvia la TUI
- gestisce l error boundary per gli errori user-facing

Punti chiave:

- `build_parser()` definisce tutta la superficie CLI
- `main()` instrada tra modalita diretta e TUI
- `_execute_handler()` traduce `PDFToolError` in stderr + exit code `1`
- `KeyboardInterrupt` viene tradotto in exit code `130`

### `src/pdf_tool/tui.py`

Responsabilita:

- implementa la TUI full-screen minimale
- gestisce il menu home, la schermata help e i dialog guidati
- esegue OCR/compressione con progress live
- permette l esecuzione di comandi manuali dentro la TUI

Struttura interna:

- `_show_home_menu()`:
  - costruisce la home full-screen con `prompt_toolkit`
  - adatta il layout in base alla larghezza del terminale
  - usa keybindings `up`, `down`, `enter`, `h`, `f1`, `q`, `escape`
- `_show_help_screen()`:
  - mostra una vista help dedicata con testo adattato alla larghezza disponibile
- `_prompt_ocr_args()` / `_prompt_compress_args()`:
  - raccolgono input utente tramite dialog keyboard-first
- `dispatch_interactive_command()`:
  - interpreta comandi manuali tipo `ocr file.pdf --lang it`
- `_run_with_progress()`:
  - usa `rich.Progress` per mostrare stato, percentuale, barra e tempo trascorso
- `run_interactive_app()`:
  - event loop della TUI

Azioni home attuali:

- `OCR assistito`
- `Compressione`
- `Comando libero`
- `Help`
- `Esci`

### `src/pdf_tool/ocr.py`

Responsabilita:

- valida input/output OCR
- risolve i codici lingua Tesseract
- esegue rasterizzazione PDF -> immagini
- esegue OCR per pagina
- genera output `.txt` oppure PDF ricercabile
- emette eventi di avanzamento per la TUI

Funzioni chiave:

- `resolve_tesseract_languages()`:
  - mappa `it -> ita`, `en -> eng`
  - accetta combinazioni `it+en`
- `resolve_ocr_output_path()`:
  - default: stessa cartella dell input, con nome incrementale come `documento.1.pdf`
  - consente solo `.pdf` o `.txt`
- `run_ocr()`:
  - controlla binari di sistema `tesseract` e `pdftoppm`/`pdftocairo`
  - usa `pdf2image.convert_from_path(...)`
  - usa `pytesseract.image_to_string(...)` per output `.txt`
  - usa `pytesseract.image_to_pdf_or_hocr(..., extension="pdf")` per output PDF
  - usa `pypdf.PdfWriter` per assemblare il PDF finale

Stadi progress emessi:

- `prepare`
- `render`
- `ocr`
- `finalize`
- `done`

### `src/pdf_tool/compress.py`

Responsabilita:

- valida input/output di compressione
- converte preset/livello custom in parametri Ghostscript
- gestisce l opzione opt-in in bianco e nero
- esegue la compressione PDF
- mostra dimensione prima/dopo
- in modalita TUI emette progress live e supporta l annullamento

Funzioni chiave:

- `resolve_compression_profile()`:
  - trasforma `low`, `medium`, `high` o `1-100` in:
    - `strength`
    - `dpi`
    - `pdf_setting`
- `resolve_compress_output_path()`:
  - default: stessa cartella dell input, con nome incrementale come `documento.1.pdf`
  - consente solo `.pdf`
- `compress_pdf()`:
  - controlla il binario `gs`
  - costruisce il comando Ghostscript
  - in modalita non-interattiva usa `subprocess.run(...)`
  - in modalita TUI usa `subprocess.Popen(...)`
  - intercetta righe tipo `Page N` da stdout per aggiornare la progress bar
  - su `Ctrl+C` termina il processo e rimuove l output parziale

Stadi progress emessi:

- `prepare`
- `compress`
- `done`

### `src/pdf_tool/progress.py`

Contiene il contratto dati condiviso per lo stato avanzamento:

- `OperationProgress(stage, message, completed=0, total=None)`

E volutamente minimale ed e usato sia da `ocr.py` sia da `compress.py`.

### `src/pdf_tool/utils.py`

Helper condivisi:

- `ensure_pdf_input()`
- `ensure_distinct_paths()`
- `resolve_incremental_output_path()`
- `human_size()`
- `format_size_change()`

### `src/pdf_tool/errors.py`

Contiene `PDFToolError`, l eccezione applicativa da mostrare all utente senza traceback tecnico.

### `src/pdf_tool/__main__.py`

Entry point per:

```bash
python -m pdf_tool
```

Delegato diretto a `pdf_tool.cli.main()`.

### `scripts/pydf-tool`

Bootstrap launcher installato via `script-files`.

Scopo:

- rendere robusto `pip install -e .` anche con path contenenti spazi
- recuperare la root sorgente tramite `direct_url.json` oppure ricerca negli antenati
- eseguire `pdf_tool.cli.main()`

## Runtime Flows

### 1. Direct CLI Flow

```text
pydf-tool ocr/compress/help
-> scripts/pydf-tool
-> pdf_tool.cli.main()
-> argparse parse
-> handler specifico
-> stdout/stderr user-facing
```

Dettagli:

- `pydf-tool --help` usa l help standard di `argparse`
- `pydf-tool help` e `pydf-tool help ocr` sono sottocomandi espliciti
- `pydf-tool` senza argomenti entra nella TUI

### 2. Interactive TUI Flow

```text
pydf-tool
-> pdf_tool.cli.main()
-> _run_interactive_shell_safe()
-> pdf_tool.tui.run_interactive_app()
-> home menu
-> dialog guidato o comando manuale
-> _run_with_progress()
-> run_ocr(...) / compress_pdf(...)
```

Caratteristiche:

- menu principale con navigazione a frecce
- ritorno al menu dopo completamento o errore
- help richiamabile dal menu o da tastiera
- il comando manuale usa lo stesso parser della CLI diretta

### 3. OCR Flow

```text
validate input
-> validate output
-> check Tesseract/Poppler
-> resolve OCR languages
-> count pages (best effort)
-> convert PDF pages to images
-> OCR each page
-> write .txt or assemble searchable PDF
```

Percorso `.txt`:

- una pagina immagine per volta
- `pytesseract.image_to_string(...)`
- scrittura testo finale con separatore `--- Pagina N ---`

Percorso `.pdf`:

- una pagina immagine per volta
- `pytesseract.image_to_pdf_or_hocr(..., extension="pdf")`
- merge pagine con `pypdf`

### 4. Compression Flow

```text
validate input
-> validate output
-> resolve profile
-> build Ghostscript command
-> execute gs
-> compute size delta
```

Due modalita:

- direct CLI:
  - esecuzione quiet con `subprocess.run`
- TUI:
  - esecuzione streamata con `subprocess.Popen`
  - parsing stdout per progress
  - cleanup su annullamento

## Command Surface

### Direct Commands

```bash
pydf-tool ocr input.pdf --lang it --output output.pdf
pydf-tool ocr input.pdf --lang it+en --output output.txt
pydf-tool compress input.pdf --level medium --output output.pdf
pydf-tool compress input.pdf --level 80 --output output.pdf
pydf-tool compress input.pdf --level medium --grayscale
pydf-tool help
pydf-tool help ocr
```

### Interactive Commands

Avvio:

```bash
pydf-tool
pydf-tool interactive
```

Controlli home:

- `up/down`: navigazione menu
- `enter`: selezione
- `h` / `f1`: help
- `q` / `esc`: uscita

Controlli job:

- `Ctrl+C`: annulla OCR/compressione in corso

## Dependencies

### Python Dependencies

Da `pyproject.toml`:

- `pdf2image==1.17.0`
- `prompt_toolkit==3.0.42`
- `pypdf==6.8.0`
- `pytesseract==0.3.13`
- `rich==13.7.1`
- `Pillow==12.1.1`

### System Dependencies

Richieste su macOS:

- `tesseract`
- `tesseract-lang`
- `poppler`
- `ghostscript`

Installazione prevista:

```bash
brew install tesseract tesseract-lang poppler ghostscript
```

Dettaglio licenze/versioni/scopo mantenuto in `COMPONENTS.md`.

## Packaging And Installation

Il progetto usa layout `src/` con `setuptools`.

Punti notevoli:

- `build-system`: `setuptools>=69`, `wheel`
- package root: `src`
- installazione locale:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Nota importante:

- l entrypoint installato e basato su `scripts/pydf-tool`
- questo evita alcuni problemi di editable install su path con spazi

## Test Strategy

I test attuali sono in `tests/test_cli.py` e usano `unittest` + `unittest.mock`.

Copertura attuale:

- dispatch dei comandi CLI
- avvio della TUI da `main()`
- help diretto e help contestuale
- dispatch di comandi dentro la TUI
- helper OCR
- helper compressione
- emissione eventi progress
- costruzione del comando Ghostscript
- invarianti del bootstrap script

Comando test:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

Verifica sintassi:

```bash
python3 -m compileall src tests scripts
```

## Error Handling Model

Il modello errori e semplice:

- gli errori prevedibili lanciano `PDFToolError`
- `cli.py` li converte in messaggi user-facing
- `KeyboardInterrupt` viene gestito separatamente
- la TUI mostra pannelli di errore invece di traceback raw

Questo approccio rende abbastanza semplice aggiungere nuove feature senza introdurre una gerarchia complessa di eccezioni.

## Extension Points

### Aggiungere una nuova voce di menu TUI

Toccare:

- `src/pdf_tool/tui.py`
  - `_home_actions()`
  - prompt/dialog dedicato
  - branch in `run_interactive_app()`
  - eventuale branch in `dispatch_interactive_command()`

### Aggiungere nuove lingue OCR

Toccare:

- `src/pdf_tool/ocr.py`
  - `SUPPORTED_LANGUAGE_CODES`
- `README.md`
- `COMPONENTS.md` solo se cambiano prerequisiti o dipendenze
- `tests/test_cli.py`

### Aggiungere nuovi preset di compressione

Toccare:

- `src/pdf_tool/compress.py`
  - `PRESET_STRENGTHS`
  - eventuale logica di mapping profilo
- `src/pdf_tool/tui.py`
  - scelta guidata del livello
- `README.md`
- `tests/test_cli.py`

### Migliorare la progress UI

Toccare:

- `src/pdf_tool/progress.py` per estendere il payload
- `src/pdf_tool/ocr.py` e `src/pdf_tool/compress.py` per nuovi stage/campi
- `src/pdf_tool/tui.py` per il rendering

## Known Constraints And Caveats

- La TUI e pensata per terminali reali. In alcuni ambienti pseudo-TTY o embedded puo comparire un warning tipo `Input is not a terminal`.
- La progress della compressione dipende dal formato stdout di Ghostscript e dal pattern `Page N`.
- I test non eseguono OCR/compressione reali: mockano le dipendenze esterne.
- La CLI diretta mostra output finale ma non usa la progress grafica di `rich`; la progress completa e disponibile nella TUI.
- Il supporto OCR lato CLI e limitato volontariamente a `it`, `en`, `it+en`, anche se Tesseract puo avere piu lingue installate.

## Practical Handoff Notes For REPORT VIBE CODING

Se bisogna modificare il progetto, conviene preservare questi invarianti:

- `pydf-tool` senza argomenti deve aprire la TUI
- `pydf-tool ocr ...` e `pydf-tool compress ...` devono continuare a funzionare da CLI classica
- `pydf-tool help` deve restare consistente con `--help`
- ogni modifica di dipendenze va riflessa in `pyproject.toml`, `README.md`, `COMPONENTS.md`
- il launcher `scripts/pydf-tool` non va semplificato senza ritestare l editable install in path con spazi

Se bisogna fare debugging, i file piu probabili da toccare sono:

- `src/pdf_tool/tui.py` per UX/interazione
- `src/pdf_tool/ocr.py` per OCR pipeline
- `src/pdf_tool/compress.py` per Ghostscript/progress/annullamento
- `tests/test_cli.py` per consolidare i comportamenti

## Quick Verification Checklist

```bash
source .venv/bin/activate
pydf-tool --help
pydf-tool help
pydf-tool help ocr
pydf-tool
PYTHONPATH=src python3 -m unittest discover -s tests -v
python3 -m compileall src tests scripts
```

## Git Publication Notes

Lo stato attuale e pronto per una pubblicazione iniziale, con una nota importante:

- ora esiste un `.gitignore` dedicato al progetto
- gli artefatti locali da non pubblicare includono `.venv/`, `__pycache__/`, `.DS_Store` e `*.egg-info`

Sequenza consigliata:

```bash
cd "/Users/flosh/Desktop/CLI PDF Tool"
git init -b main
git status --short
git status --ignored --short
git add .
git commit -m "Initial import of PyDF Tool"
git remote add origin git@github.com:USERNAME/NOME_REPO.git
git push -u origin main
```

Verifiche minime post-push:

```bash
git status
git branch -vv
git log --oneline --decorate -1
git ls-remote --heads origin
```

## Last Known Verified Behaviors

Ultimo assetto verificato localmente:

- help generale funzionante
- help contestuale funzionante
- TUI avviabile
- navigazione a frecce verificata
- repaint della selezione verificato
- comando `pydf-tool` installato e funzionante
