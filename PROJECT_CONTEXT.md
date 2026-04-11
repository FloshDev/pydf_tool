# PROJECT CONTEXT — PyDF Tool

Documento di handoff aggiornato al `2026-04-12`.
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
- il focus dei pulsanti in `CheckResultScreen` è coerente: niente sfondo giallo pieno su `Torna al menu`
- nei passi a scelta del wizard la prima opzione risulta evidenziata subito, incluso `Formato` dopo `Lingua`
- nei passi `Output`, lasciare il campo vuoto significa salvare nella stessa cartella del file di partenza
- nei passi `File` di OCR/compressione e nella schermata `check` si può aprire Finder con `F2` oppure col pulsante dedicato
- nei passi `File` di OCR/compressione e nella schermata `check` il focus passa tra input e pulsante Finder anche con `↑↓` e `Tab`
- dopo una selezione via Finder il focus torna automaticamente sul campo percorso, così `Invio` successivo conferma il path invece di riaprire il picker
- all'avvio l'app mostra un modal se mancano prerequisiti esterni (`tesseract`, `poppler`, `ghostscript`)
- OCR e compressione vengono bloccati in TUI con messaggio esplicito se mancano i tool necessari
- al termine di OCR/compressione la schermata finale offre pulsanti `Apri file`, `Apri cartella`, `Torna al menu`
- i wizard usano preferenze persistenti per ultima cartella, lingua OCR e livello compressione
- il sottomenu `OCR` usa ora un layout compatto coerente col wizard, senza hero grande né dashboard a doppio pannello

---

## Layout repository

```text
.
├── pyproject.toml
├── README.md
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
│       ├── macos_integration.py
│       ├── preferences.py
│       ├── tui.py
│       ├── tui.tcss
│       ├── ocr.py
│       ├── compress.py
│       ├── check_ocr.py
│       ├── progress.py
│       ├── system_checks.py
│       ├── utils.py
│       └── errors.py
├── tests/
│   ├── test_cli.py
│   ├── test_macos_integration.py
│   ├── test_preferences.py
│   ├── test_system_checks.py
│   └── test_tui_usability.py
```

Cartelle locali comunemente presenti ma non tracciate: `.superpowers/`, `PDF Sample/`.

Numero test attuale: `94` test `unittest`.

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
- `PyDFApp` carica preferenze persistenti e lancia un preflight iniziale dei prerequisiti
- `HomeScreen` funge da launcher e apre `OCR`, `Comprimi PDF` o `Help`
- `OCRMenuScreen` separa `Verifica OCR` da `Esegui OCR`
- `WizardScreen` gestisce i flussi guidati
- `WizardScreen` supporta selezione file da Finder con `F2` / pulsante dedicato
- `WizardScreen` usa hint espliciti per suggerire output default nella stessa cartella dell'input
- `CheckInputScreen` e `CheckResultScreen` coprono `check`
- `CheckResultScreen` gestisce il focus dei pulsanti via tastiera
- `ProgressScreen` avvia OCR/compressione con `@work(thread=True)`
- `ProgressScreen` espone azioni finali `Apri file` / `Apri cartella`
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

### `preferences.py`

- persistenza locale delle preferenze in `~/Library/Application Support/PyDF Tool/preferences.json`
- salva ultima cartella usata
- salva lingua OCR preferita
- salva livello compressione preferito

### `system_checks.py`

- controlli di sistema per `global`, `ocr`, `compress`, `check`
- rilevamento di `tesseract`, `pdftocairo`/`pdftoppm`, `gs`
- messaggi user-facing con hint Homebrew

### `macos_integration.py`

- apertura del file picker Finder via `osascript`
- apertura file con app di default via `open`
- apertura/rivelazione cartella output via Finder

---

## Stato verificato

### Verificato in questa fase

- suite test verde: `94` test
- import e runtime verificati dentro `.venv`
- struttura docs/spec/plan presente e leggibile
- launcher TUI verificato con home, sottomenu OCR e focus pulsanti
- wizard OCR verificato con highlight immediato del passo `Formato` dopo `Lingua`
- placeholder output verificati: `vuoto = stessa cartella del file di partenza`
- picker Finder verificato con test dedicati
- preflight prerequisiti e blocchi OCR/compress verificati con test dedicati
- preferenze persistenti verificate con round-trip e fallback da file corrotto

### Funzionalità implementate

- `check`, `ocr`, `compress` disponibili da CLI
- TUI Textual con home launcher, sottomenu OCR, wizard, help, check e progress
- wizard TUI con scelte guidate a frecce per lingua, formato, colore e preset
- picker Finder per i campi file in TUI (`F2` + pulsante)
- compressione TUI con supporto al grado numerico personalizzato `1-100`
- avvio OCR da `Verifica OCR` con path già in memoria e passo file saltato
- placeholder output più espliciti: il default salva nella stessa cartella dell'input; OCR adatta l'estensione suggerita a `.pdf` o `.txt`
- output suggerito mostrato in chiaro con hint dedicato
- checks iniziali su dipendenze esterne e blocco delle operazioni non eseguibili
- preferenze persistenti per cartella, lingua OCR e livello compressione
- schermata finale con azioni pratiche `Apri file` / `Apri cartella`
- messaggi finali più utili: percorso salvato, variazione dimensione, passo successivo suggerito
- OCR low-memory pagina per pagina
- compressione con staging e supporto path Unicode
- naming incrementale degli output

### Fix applicati (2026-04-11) — Cleanup & Refactoring (COMPLETATO)

Piano: `docs/superpowers/plans/2026-04-11-cleanup-refactor-plan.md`
Spec: `docs/superpowers/specs/2026-04-11-cleanup-refactor-design.md`

Task completati (subagent-driven, 46 test verdi):

- **Task 1 ✅**: rimosso `_HEADER_TEXT` (tui.py), return irraggiungibile in `human_size` (utils.py), regole CSS `.step-indicator` e `#btn-run-ocr:focus` (tui.tcss), `resolve_user_path` ridondante (compress.py).
- **Task 2 ✅**: `_emit_progress` spostata in `progress.py` come `emit_progress` pubblica; rimossa da `ocr.py` e `compress.py`; 3 nuovi test (totale: 46).
- **Task 3 ✅**: `MenuScreen(Screen)` base class; `HomeScreen` e `OCRMenuScreen` la subclassano; rimossi 3 metodi duplicati per classe.
- **Task 4 ✅**: rimossi `parser_factory`/`executor` da `PyDFApp.__init__` e `run_interactive_app`; aggiornati `cli.py` e i test.

Tutti e 8 i task sono stati completati. Stato finale di quel blocco: **51 test verdi**.

### Fix e follow-up UX

- **CSS `btn-home` focus**: aggiunto selettore `#result-buttons Button:focus` (specificità 0,1,1,1) per battere il DEFAULT_CSS di Textual 8.x `Button.-style-default:focus` (0,0,2,1) che causava sfondo ambra sul pulsante "Torna al menu" quando focalizzato
- **Wizard choice highlight**: il popolamento asincrono delle liste del wizard ora attende il mount delle opzioni prima di impostare indice e classe `-highlight`; questo evita il caso in cui il passo `Formato` mostrasse la prima opzione non evidenziata finché l'utente non si muoveva con le frecce
- **Placeholder output più chiaro**: i passi `Output` di OCR e compressione non parlano più di “automatico”; dichiarano esplicitamente che il file viene salvato nella stessa cartella dell'input se il campo resta vuoto. Nel wizard OCR il placeholder segue anche il formato scelto (`.pdf` o `.txt`)
- **File picker Finder**: i campi file dei wizard e della verifica OCR possono aprire il selettore di macOS via `osascript`, con hint sulla directory usata più di recente
- **Preflight prerequisiti**: `PyDFApp` esegue controlli iniziali e blocca OCR/compressione se mancano i binari esterni richiesti
- **Preferenze persistenti**: ultima cartella, lingua OCR e livello compressione vengono salvati in `~/Library/Application Support/PyDF Tool/preferences.json`
- **Azioni finali pratiche**: le schermate di esito possono aprire il file prodotto o la cartella di destinazione direttamente dal Finder
- **Navigazione mista mouse+tastiera nei passi file**: wizard e schermata `check` permettono ora di raggiungere il pulsante Finder anche con `↑↓` e `Tab`, senza dipendere dal click del mouse; il bottone ha anche spacing verticale corretto rispetto all'input
- **Focus post-Finder corretto**: dopo aver scelto un file dal picker macOS, il focus ritorna automaticamente al campo percorso invece di restare sul pulsante Finder
- **Progress screen ripulita**: la schermata di avanzamento mostra un solo hint `Ctrl+C` nel footer e la barra di progresso usa tutta la larghezza utile del layout
- **OCR submenu compattato**: `OCRMenuScreen` è stato riallineato visivamente ai flussi operativi, con titolo/prompt compatti e preview sotto la lista invece del vecchio layout hero + doppio pannello

### Note tecniche (Textual 8.x)

- `Static.renderable` non esiste — usare `.content` (property pubblica)
- Lo stack include una DefaultScreen interna: `len(screen_stack)` inizia a 2
- Il binding 'h' funziona solo quando il focus è su ListView, non su Input

### Ultime sessioni Codex

Sessione del `2026-04-12` svolta da `Codex`.

File toccati in questa sessione:

- `src/pydf_tool/preferences.py`
  - nuovo modulo per persistenza preferenze locali con salvataggio atomico e fallback da file corrotto
- `src/pydf_tool/system_checks.py`
  - nuovo modulo per controlli di sistema globali e per singola operazione (`check`, `ocr`, `compress`)
- `src/pydf_tool/macos_integration.py`
  - nuovo modulo per picker Finder, apertura file con app di default e apertura cartella output
- `src/pydf_tool/tui.py`
  - fix del popolamento asincrono delle liste del wizard per mostrare subito l'highlight sulla prima scelta disponibile
  - integrazione di preferenze persistenti, picker Finder e preflight prerequisiti
  - placeholder output resi espliciti sul salvataggio nella stessa cartella del file di partenza
  - placeholder OCR reso dipendente dal formato scelto (`.pdf` / `.txt`)
  - schermata finale estesa con azioni `Apri file` / `Apri cartella` e messaggi più pratici
  - navigazione dei passi file estesa per permettere focus `input <-> Finder` via `↑↓` e `Tab`
  - focus riportato ai campi percorso dopo la selezione da Finder in wizard e schermata `check`
  - schermata di avanzamento semplificata rimuovendo il doppio hint di annullamento
  - sottomenu OCR convertito a layout compatto coerente col wizard
- `src/pydf_tool/tui.tcss`
  - neutralizzato il `reverse`/`background-tint` di Textual sul focus dei pulsanti risultato per eliminare lo sfondo giallo pieno su `Torna al menu`
  - aggiunti gli stili per picker Finder, hint di output, modal prerequisiti e azioni finali
  - corretto il margine verticale dei pulsanti Finder sotto gli input file
  - estesa la barra di progresso a tutta la larghezza utile del pannello
  - aggiunti gli stili dedicati per il nuovo layout compatto del sottomenu OCR
- `tests/test_cli.py`
  - regressione sul focus coerente di `btn-home`
  - regressione sul primo highlight del passo `Formato`
  - regressioni sui placeholder output di OCR e compressione
  - aggiunto test sul layout compatto del sottomenu OCR
- `tests/test_preferences.py`
  - test sul round-trip delle preferenze e sul recupero da JSON corrotto
- `tests/test_system_checks.py`
  - test sui report di prerequisiti mancanti e sui controlli per operazione
- `tests/test_macos_integration.py`
  - test sul parsing dell'output `osascript` e sui comandi `open`
- `tests/test_tui_usability.py`
  - regressioni su picker Finder, preferenze default, preflight iniziale, hint output, pulsanti finali, navigazione `input <-> Finder` e focus corretto dopo il picker
- `PROJECT_CONTEXT.md`
  - aggiornato il handoff con stato reale, test count, fix recenti e stato delle priorità di usabilità per una beta locale

Sessione del `2026-03-31` svolta da `Codex`.

File toccati in quella sessione:

- `src/pydf_tool/tui.py`
  - home ridisegnata come launcher
  - header home separato in brand, sottotitolo e tagline per una gerarchia visiva piu chiara
  - preview della home resa scrollabile per mantenere leggibile il testo anche su finestre strette
  - `Help` reinserito nella lista principale
  - nuovo `OCRMenuScreen` con `Verifica OCR` ed `Esegui OCR`
  - wizard con passi a scelta via scorrimento per OCR e compressione
  - supporto TUI al livello custom `1-100` nella compressione
  - avvio OCR da `CheckResultScreen` con passo file saltato se il path è già noto
  - fix focus/navigazione dei pulsanti in `CheckResultScreen`
  - fix ritorno al launcher da `ProgressScreen` e schermata finale check
- `src/pydf_tool/tui.tcss`
  - styling più leggibile per launcher, card menu, preview e pulsanti
  - scrollbar del menu strumenti uniformata alla palette e card home rese piu compatte
  - tool selezionato evidenziato con barra laterale accent e pannello dettagli piu compatto
  - highlight del tool selezionato aggiornato a riquadro accent completo e gutter scrollbar ridotto
  - corretto il selettore CSS di highlight Textual (`-highlight`) e rimossa la scrollbar del menu strumenti
  - ripristinato lo scroll verticale del menu strumenti mantenendo invisibile la scrollbar
  - styling del wizard esteso alle liste di scelta guidata
  - help, input e pulsanti riallineati al linguaggio visivo della home
- `src/pydf_tool/utils.py`
  - parsing di path shell-style con virgolette o spazi escapati
- `tests/test_cli.py`
  - test Textual per home, submenu OCR e navigazione pulsanti
  - regressione sullo scroll automatico del menu home verso l'elemento evidenziato
  - test sulle scelte guidate del wizard OCR e sul livello custom della compressione
  - regressione sul wizard OCR precompilato che salta il passo file
  - regressione sul ritorno alla home dopo il completamento di OCR/compressione
- `PROJECT_CONTEXT.md`
  - stato reale TUI, conteggio test e note di handoff aggiornate
- `GUIDA_CODICE.md`
  - nuova sezione operativa per modificare in autonomia tutti i testi della TUI senza rompere la logica

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

### Gap nei test

- nessun end-to-end OCR `.pdf` con Tesseract reale
- nessun end-to-end con Tesseract o Ghostscript reali
- nessun test di integrazione reale su Finder / `open` macOS fuori dai mock
- nessun test per `resolve_incremental_output_path` con collisioni multiple

### Debito tecnico leggero

- `ProgressScreen` ha un `elapsed-label` presente ma non aggiornato

### Priorità usabilità per una beta locale

Completato in questa fase:

- selezione file da Finder al posto dell'inserimento manuale dei path
- controlli iniziali che segnalano subito assenza di `tesseract`, `poppler` o `ghostscript`
- output più guidato: default nella stessa cartella, naming più esplicito, azioni finali `Apri file` / `Apri cartella`
- preferenze persistenti: ultima cartella usata, lingua OCR preferita, livello compressione preferito
- messaggi post-operazione più pratici: dove è stato salvato il file, quanto è cambiata la dimensione, passo successivo suggerito

Residuo prima di chiamarla beta distribuibile:

- test su un Mac pulito, senza toolchain già preparata, prima di etichettare una beta come distribuibile
- launcher macOS `.app` con icona che apre Terminal e avvia `pydf-tool`; utile per tester non tecnici, ma non ancora equivalente a un'app standalone con runtime e dipendenze integrate
- eventuale packaging successivo con runtime Python incorporato e dipendenze meglio nascoste all'utente finale

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
