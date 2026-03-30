# PROJECT CONTEXT — PyDF Tool

Documento di handoff aggiornato al `2026-03-31`.
Descrive lo stato reale della repo. Le specifiche storiche in `docs/superpowers/` restano utili come cronologia di design, ma non sostituiscono questo file.

---

## Identità

- Nome: `PyDF Tool`
- Comando: `pydf-tool`
- Linguaggio: Python
- Versione minima dichiarata: `3.10+`
- Piattaforma target: macOS
- Interfacce: CLI `argparse` e TUI `Textual`
- Funzioni attuali:
  - verifica OCR (`check`)
  - OCR di PDF scansionati (`ocr`)
  - compressione PDF (`compress`)

---

## Superficie utente

### CLI

Sottocomandi reali in `src/pydf_tool/cli.py`:

- `check INPUT.pdf`
- `ocr INPUT.pdf [--lang it|en|it+en] [--output PATH]`
- `compress INPUT.pdf [--level low|medium|high|1-100] [--output PATH] [--grayscale]`
- `interactive`
- `help [ocr|compress|check|interactive]`

Nota: per `ocr` il tipo di output non si sceglie con `--format`; dipende dall'estensione di `--output`.
- `.pdf` → PDF ricercabile
- `.txt` → testo semplice
- senza `--output` → output incrementale `.pdf`

### TUI

Schermate reali in `src/pydf_tool/tui.py`:

- `HomeScreen`
- `OCRMenuScreen`
- `WizardScreen` per OCR e compressione
- `CheckInputScreen`
- `CheckResultScreen`
- `ProgressScreen`
- `HelpScreen`

La TUI attuale non usa più `prompt_toolkit` o `rich` come framework separati: la migrazione a Textual è completata.
La home attuale è un launcher a card con tre ingressi:

- `OCR`
- `Comprimi PDF`
- `Help`

Il flusso `OCR` apre un sottomenu dedicato con:

- `Verifica OCR`
- `Esegui OCR`
- `Torna al menu`

Nota UX verificata:
- `CheckResultScreen` supporta navigazione tastiera tra i pulsanti con `↑↓←→`, `Tab` e `Shift+Tab`
- il focus iniziale cade sul primo pulsante disponibile

---

## Layout repository

```text
.
├── pyproject.toml
├── README.md
├── COMPONENTS.md
├── PROJECT_CONTEXT.md
├── GUIDA_CODICE.md
├── ISTRUZIONI.txt
├── setup.sh
├── docs/
│   └── superpowers/
│       ├── specs/
│       └── plans/
├── src/
│   └── pydf_tool/
│       ├── __init__.py
│       ├── __main__.py
│       ├── cli.py
│       ├── tui.py
│       ├── tui.tcss
│       ├── ocr.py
│       ├── compress.py
│       ├── check_ocr.py
│       ├── progress.py
│       ├── utils.py
│       └── errors.py
├── tests/
│   └── test_cli.py
```

Cartelle locali comunemente presenti ma non tracciate: `.superpowers/`, `PDF Sample/`.

Numero test attuale: `38` test `unittest` in `tests/test_cli.py`.

---

## Dipendenze

### Python

Dipendenze dirette definite in `pyproject.toml`:

| Pacchetto | Versione |
| --- | --- |
| `pdf2image` | `1.17.0` |
| `textual` | `>=0.70.0` |
| `pypdf` | `6.8.0` |
| `pytesseract` | `0.3.13` |
| `Pillow` | `>=10.3.0,<12.0` |

Note:
- `rich` non è più una dipendenza diretta: arriva transitivamente tramite `textual`
- `prompt_toolkit` non è più usato
- il pin `Pillow>=10.3.0,<12.0` evita l'incompatibilità con `pypdf==6.8.0`

### Sistema

Prerequisiti Homebrew:

```bash
brew install tesseract tesseract-lang poppler ghostscript
```

---

## Installazione e verifica

### Metodo canonico

Usare sempre `setup.sh`:

```bash
rm -rf .venv && bash setup.sh
source .venv/bin/activate
pydf-tool --help
```

### Cosa fa `setup.sh`

1. crea `.venv`
2. esegue `pip install -e .`
3. rimuove il flag macOS `UF_HIDDEN` dalla venv con `chflags -R nohidden`
4. inietta `PYTHONPATH=src` nello script `activate`
5. patcha il wrapper `.venv/bin/pydf-tool` con `sys.path.insert(0, src)`

### Nota importante sull'ambiente

Il pacchetto dichiara supporto `Python 3.10+`, ma il workflow oggi verificato è quello con Python.org Python 3.12 su macOS.
`setup.sh` patcha esplicitamente il wrapper usando `.venv/bin/python3.12`.
Se si usa una diversa minor version di Python, il packaging resta teoricamente compatibile ma il setup script potrebbe richiedere un adattamento.

### Workflow dopo modifiche

| Cosa è cambiato | Cosa fare |
| --- | --- |
| File in `src/` | rilanciare `pydf-tool` |
| `pyproject.toml` o dipendenze | `pip install -e .` poi `bash setup.sh` |
| Venv corrotta / import mancanti | `rm -rf .venv && bash setup.sh` |

### Test

Eseguire i test con la venv attiva:

```bash
source .venv/bin/activate
PYTHONPATH=src python -m unittest discover -s tests -v
```

Alternativa equivalente senza attivare la shell:

```bash
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v
```

Il comando con `python3` di sistema non è sufficiente se `textual` non è installato globalmente.

---

## Architettura

### `cli.py`

- costruisce il parser
- gestisce il dispatch CLI
- avvia la TUI se non ci sono argomenti
- traduce `PDFToolError` in messaggi user-facing

### `tui.py`

- TUI Textual pura
- `PyDFApp` monta `HomeScreen`
- `HomeScreen` funge da launcher e apre `OCR`, `Comprimi PDF` o `Help`
- `OCRMenuScreen` separa `Verifica OCR` da `Esegui OCR`
- `WizardScreen` gestisce i flussi guidati
- `CheckInputScreen` e `CheckResultScreen` coprono `check`
- `CheckResultScreen` gestisce il focus dei pulsanti via tastiera
- `ProgressScreen` avvia OCR/compressione con `@work(thread=True)`
- `dispatch_interactive_command()` resta come helper per comandi testuali e test

### `ocr.py`

- OCR via `pdf2image` + `pytesseract` + `pypdf`
- supporta output `.pdf` e `.txt`
- processa pagina per pagina se riesce a leggere il page count
- accetta `progress_callback`

### `compress.py`

- compressione via Ghostscript
- accetta preset `low|medium|high` o livello numerico `1-100`
- usa staging temporaneo prima dello spostamento finale
- copia l'input in un path ASCII-safe se necessario
- espone progress tramite parsing di `Page N`

### `check_ocr.py`

- stima se un PDF contiene già testo estraibile
- ritorna `ocr_needed`, `already_searchable` o `mixed`

### `utils.py`

- normalizzazione path Unicode macOS
- validazione input `.pdf`
- generazione output incrementale
- formattazione dimensioni

---

## Stato verificato

### Verificato in questa fase

- suite test verde: `38` test
- import e runtime verificati dentro `.venv`
- struttura docs/spec/plan presente e leggibile
- launcher TUI verificato con home, sottomenu OCR e focus pulsanti

### Funzionalità implementate

- `check`, `ocr`, `compress` disponibili da CLI
- TUI Textual con home launcher, sottomenu OCR, wizard, help, check e progress
- OCR low-memory pagina per pagina
- compressione con staging e supporto path Unicode
- naming incrementale degli output

### Ultima sessione Codex

Sessione del `2026-03-31` svolta da `Codex`.

File toccati in questa sessione:

- `src/pydf_tool/tui.py`
  - home ridisegnata come launcher
  - `Help` reinserito nella lista principale
  - nuovo `OCRMenuScreen` con `Verifica OCR` ed `Esegui OCR`
  - fix focus/navigazione dei pulsanti in `CheckResultScreen`
- `src/pydf_tool/tui.tcss`
  - styling più leggibile per launcher, card menu, preview e pulsanti
- `src/pydf_tool/utils.py`
  - parsing di path shell-style con virgolette o spazi escapati
- `tests/test_cli.py`
  - test Textual per home, submenu OCR e navigazione pulsanti
- `PROJECT_CONTEXT.md`
  - stato reale TUI, conteggio test e note di handoff aggiornate

### Documenti storici rilevanti

- design migrazione Textual:
  `docs/superpowers/specs/2026-03-29-textual-migration-design.md`
- piano implementativo:
  `docs/superpowers/plans/2026-03-30-textual-migration-plan.md`

---

## Limiti e gap aperti

### Limiti funzionali

- l'OCR non è interrompibile dentro la singola chiamata C di Tesseract
- `Ctrl+C` viene servito tra una pagina e l'altra
- il wizard TUI di compressione espone solo `low|medium|high`, non il livello numerico `1-100`

### Gap nei test

- nessun test dedicato al path OCR `.pdf`
- nessun test Textual completo sul wizard OCR/compress o sul flow `check -> run ocr`
- nessun end-to-end con Tesseract o Ghostscript reali
- nessun test per `resolve_incremental_output_path` con collisioni multiple

### Debito tecnico leggero

- `_emit_progress` è duplicata in `ocr.py` e `compress.py`
- `ProgressScreen` ha un `elapsed-label` presente ma non aggiornato

---

## Cronologia recente

- `2026-03-27` `aa620b7`
  - aggiunti `check_ocr`, OCR low-memory, `console_scripts`, workaround `UF_HIDDEN`
  - commit co-firmato con Claude
- `2026-03-27` `53efa80`
  - ristrutturata la vecchia TUI pre-Textual
  - commit co-firmato con Claude
- `2026-03-28` `3d1722f`
  - rinomina `pdf_tool` → `pydf_tool`, applicazione design system
  - commit co-firmato con Claude
- `2026-03-29` `90fb878`
  - design/spec della migrazione a Textual
  - commit co-firmato con Claude
- `2026-03-30` `1daffdb`
  - migrazione completa TUI a Textual
  - commit co-firmato con Claude
- `2026-03-30` `1b56205`
  - follow-up manuale su `setup.sh`, `tui.py` e `tui.tcss`

---

## Note operative

- attivare sempre la venv prima di usare `pydf-tool`
- dopo `pip install -e .` manuale, rilanciare `bash setup.sh`
- se `pydf-tool` fallisce con `ModuleNotFoundError`, ricreare la venv con `setup.sh`
- OCR e Ghostscript reali richiedono le dipendenze Homebrew installate
