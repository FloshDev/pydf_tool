# PyDF Tool — Guida alla comprensione del codice

Questo documento è pensato per chi ha costruito il progetto con Claude Code ma vuole capire davvero cosa c'è dentro, perché è fatto così, e come ragionare autonomamente sulle modifiche future. Non è un tutorial Python generico: parte da questo codice specifico e spiega i concetti dove servono.

---

## 1. Perché il progetto è strutturato così

Prima di guardare i singoli file, vale la pena capire le scelte organizzative di fondo, perché influenzano tutto il resto.

### La directory `src/`

Quasi tutti i progetti Python amatoriali mettono il codice direttamente nella root. Questo progetto usa invece `src/pydf_tool/`. Il motivo è tecnico ma importante: se il codice è nella root, Python lo trova automaticamente quando sei nella stessa cartella — il che sembra comodo ma crea un bug sottile: i test potrebbero girare sul codice locale non installato invece che sul pacchetto installato, rendendo invisibili certi errori di configurazione. Con `src/`, Python non trova il codice a meno che non sia stato installato (`pip install -e .`), il che garantisce che i test testino la stessa cosa che userebbe un utente reale.

### Il file `pyproject.toml`

È il file di configurazione moderno dei pacchetti Python (rimpiazza `setup.py`). Le cose che ti interessa capire:

- `[project.scripts]` definisce il comando `pydf-tool` che puoi eseguire dal terminale. La riga `pydf-tool = "pydf_tool.cli:main"` dice: "quando l'utente digita `pydf-tool`, chiama la funzione `main` nel file `src/pydf_tool/cli.py`".
- `dependencies` elenca le librerie Python richieste. Se aggiungi una dipendenza, va qui.
- `requires-python = ">=3.10"` è il minimo di Python supportato. Alcune sintassi usate nel codice (come `int | None`) non esistono in Python 3.9 o prima.

### Il virtual environment `.venv`

Un virtual environment è una copia isolata di Python con le sue librerie. Serve per non inquinare l'installazione globale di Python sul tuo Mac. `setup.sh` lo crea e lo configura. Regola pratica: se il comando `pydf-tool` non si trova, la venv probabilmente non è attiva — esegui `source .venv/bin/activate`.

C'è una nota critica nel `PROJECT_CONTEXT.md` su un bug specifico del Python.org Python 3.12 su macOS che impedisce ai `.pth` file (usati per trovare i pacchetti) di funzionare correttamente. La soluzione adottata è un workaround in `setup.sh` che fa tre cose pratiche: rimuove il flag `UF_HIDDEN` dalla venv, inietta `PYTHONPATH=src` nello script `activate` e patcha il wrapper `pydf-tool` con `sys.path.insert(0, src)`. Non è elegante, ma è il modo più robusto per aggirare il problema senza dipendere da meccanismi che macOS può sabotare.

---

## 2. La mappa dei file e i loro ruoli

```
src/pydf_tool/
├── __init__.py      — Marca la cartella come pacchetto Python; espone la versione
├── __main__.py      — Permette di eseguire il pacchetto con `python -m pydf_tool`
├── cli.py           — Punto di ingresso; gestisce argomenti e routing
├── tui.py           — Interfaccia interattiva (menu, dialog, progress bar)
├── ocr.py           — Pipeline OCR: PDF → immagini → testo → PDF ricercabile
├── compress.py      — Pipeline compressione: chiama Ghostscript
├── check_ocr.py     — Analisi PDF: ha già testo o no?
├── progress.py      — Un dataclass semplice per comunicare lo stato di avanzamento
├── utils.py         — Funzioni di supporto: path, dimensioni, Unicode
└── errors.py        — L'eccezione custom del progetto
```

Il principio di separazione usato qui è chiamato "separation of concerns": ogni file ha una responsabilità ben definita. `cli.py` non sa come funziona l'OCR — sa solo che esiste `run_ocr()` e come chiamarla. `ocr.py` non sa nulla della CLI — riceve un path e restituisce un risultato. Questo rende ogni parte più facile da testare e modificare indipendentemente.

---

## 3. Il file `errors.py` — Perché un'eccezione custom

```python
class PDFToolError(Exception):
    """User-facing error for predictable CLI failures."""
```

Questa è la cosa più semplice del progetto, ma concettualmente importante. In Python puoi sollevare qualsiasi eccezione (`raise ValueError(...)`, `raise RuntimeError(...)`), ma le eccezioni generiche portano informazioni tecniche non adatte all'utente.

L'idea qui è distinguere due categorie di errore:
- **Errori previsti** (file non trovato, lingua OCR non supportata, Ghostscript non installato): si solleva `PDFToolError` con un messaggio chiaro in italiano.
- **Errori imprevisti** (bug nel codice, crash di una libreria): si lascia propagare l'eccezione originale.

In `cli.py`, `_execute_handler()` cattura solo `PDFToolError` e la stampa come messaggio leggibile su stderr. Tutto il resto passa — il che è deliberato: un bug deve essere visibile, non soppresso.

---

## 4. Il file `utils.py` — Strumenti di supporto

Questo file contiene funzioni usate da più moduli. Vale la pena capirle una per una perché appaiono ovunque.

### `resolve_user_path(path)`

Il problema che risolve: su macOS, i nomi di file possono essere rappresentati in modi Unicode diversi (NFC, NFD, NFKC, NFKD). Un file chiamato "Università" potrebbe esistere su disco in forma NFD (accento come carattere separato) ma essere passato dal terminale in forma NFC (accento incorporato). Python vedrebbe due stringhe diverse e direbbe che il file non esiste, anche se è lì.

La funzione prova tutte le varianti di normalizzazione e restituisce il path che esiste realmente su disco. È un problema tipicamente macOS e non avresti modo di scoprirlo senza incappare nel bug.

### `ensure_pdf_input(path)`

Combina `resolve_user_path` con due controlli: il file esiste? Ha estensione `.pdf`? Se una delle due fallisce, solleva `PDFToolError` con messaggio chiaro. Questa funzione è chiamata come prima cosa da tutte le pipeline — è il "cancello" di ingresso.

### `resolve_incremental_output_path(input_path, extension)`

Se non specifichi un file di output, il programma non sovrascrive l'input. Genera invece un nome incrementale: `documento.1.pdf`, poi `documento.2.pdf`, ecc. La logica è un `while True` che prova numeri crescenti finché non trova uno che non esiste ancora. La riga `if candidate.resolve(strict=False) != input_resolved` garantisce che il candidato non sia lo stesso file dell'input anche se hanno nomi diversi (symlink, ecc.).

### `human_size` e `format_size_change`

Pura formattazione. `human_size` converte byte in KB/MB/GB leggibili. `format_size_change` mostra la variazione percentuale tra prima e dopo la compressione. Il `+` nel format string `{percent:+.1f}%` stampa esplicitamente il segno, così `-23.4%` e `+5.1%` sono entrambi chiari.

---

## 5. Il file `progress.py` — Un dataclass

```python
@dataclass(frozen=True)
class OperationProgress:
    stage: str
    message: str
    completed: int = 0
    total: int | None = None
```

Un `dataclass` è una classe Python che genera automaticamente `__init__`, `__repr__` e altri metodi boilerplate basandosi sui campi dichiarati. `frozen=True` lo rende immutabile: una volta creato, non puoi modificarne i campi. È usato come semplice "pacchetto di dati" da passare dalla pipeline alla TUI per aggiornare la barra di avanzamento.

`total: int | None = None` usa la sintassi union type di Python 3.10+: il totale può essere un intero oppure `None` (quando il numero di pagine non è ancora noto). Il `= None` è il valore di default se non si specifica.

---

## 6. Il file `check_ocr.py` — La pipeline più semplice

```python
CHARS_PER_PAGE_THRESHOLD = 50
```

Questa costante è la soglia di decisione: una pagina viene considerata "con testo" se contiene almeno 50 caratteri estratti. È un valore arbitrario ma ragionevole — abbastanza alto da ignorare artefatti OCR casuali, abbastanza basso da non escludere pagine con poco testo.

La funzione `check_ocr()` usa `pypdf.PdfReader` per leggere il PDF senza renderizzarlo. `pypdf` può estrarre il testo incorporato nel PDF (se c'è) direttamente dal file binario — è veloce e non richiede Tesseract. Se una pagina è uno scan (immagine), `extract_text()` restituisce una stringa vuota o quasi.

Il verdetto finale segue una logica a tre vie: se nessuna pagina ha testo → `ocr_needed`; se tutte le pagine hanno testo → `already_searchable`; se alcune sì e alcune no → `mixed`.

---

## 7. Il file `ocr.py` — La pipeline più complessa

Questa è la parte più elaborata del progetto. Vale la pena capirla per intero perché mostra molti pattern riutilizzabili.

### Perché tre librerie invece di una

Non esiste una singola libreria Python che faccia tutto l'OCR su PDF. Il processo richiede tre passaggi distinti, ognuno con il suo strumento migliore:

1. **pdf2image** (che usa Poppler internamente) converte le pagine PDF in immagini raster. Questo è necessario perché Tesseract non sa leggere PDF — lavora su immagini.
2. **pytesseract** è il wrapper Python di Tesseract, il motore OCR open-source di Google. Prende un'immagine e restituisce testo o un PDF "searchable" (dove il testo invisibile è sovrapposto all'immagine).
3. **pypdf** assembla le singole pagine PDF prodotte da Tesseract in un unico file.

### L'ottimizzazione della memoria

La versione naïve del codice caricherebbe tutte le pagine in RAM contemporaneamente. Con un PDF da 50 pagine a 300 DPI, ogni immagine pesa circa 26 MB → 1.3 GB totali. Su macOS con PDF grandi, questo causa crash o swap massiccio.

La soluzione adottata: se `PdfReader` riesce a contare le pagine, si processa **una pagina alla volta** (`first_page=N, last_page=N` in `convert_from_path`). L'immagine viene processata e liberata (`del image`) prima di passare alla successiva. Il picco RAM resta costante a ~26 MB indipendentemente dalla dimensione del PDF. Se `PdfReader` fallisce (PDF corrotto o insolito), si cade nel percorso "batch" che carica tutto.

### Il pattern `progress_callback`

```python
def run_ocr(
    input_path: ...,
    output_path: ...,
    lang: str = "it",
    progress_callback: Callable[[OperationProgress], None] | None = None,
) -> OCRResult:
```

`progress_callback` è un parametro opzionale che accetta una funzione. Se fornito, la pipeline chiama quella funzione a ogni aggiornamento di stato. Se `None`, non fa niente. Questo è il pattern "callback" ed è usato per disaccoppiare la logica di calcolo dalla presentazione: `ocr.py` non sa nulla di barre di avanzamento o terminali — sa solo che deve chiamare la funzione quando ha qualcosa da dire. La TUI passa la sua funzione di aggiornamento; i test passano `updates.append` per catturare gli aggiornamenti; la CLI non passa nulla.

### Import lazy

Noterai che `import pytesseract`, `from pdf2image import ...` ecc. sono dentro la funzione `run_ocr()`, non in cima al file. Questo è deliberato: se Tesseract non è installato, l'import fallisce con un `ImportError`. Facendolo dentro la funzione, l'errore viene catturato e convertito in un `PDFToolError` con messaggio leggibile. Se fossero in cima al file, il programma crasherebbe all'avvio anche per comandi che non usano l'OCR.

---

## 8. Il file `compress.py` — Ghostscript come subprocess

La compressione non usa librerie Python pure: delega a **Ghostscript**, un programma C esterno specializzato nella manipolazione PDF. Il motivo è pragmatico: non esiste una libreria Python che comprima PDF con la stessa qualità e flessibilità di Ghostscript.

### Come funziona `subprocess`

```python
subprocess.run(command, check=True, capture_output=True, text=True)
```

`subprocess.run` esegue un programma esterno e aspetta che finisca. `command` è una lista di stringhe (il comando e i suoi argomenti). `check=True` solleva un'eccezione se il programma esce con codice di errore. `capture_output=True` cattura stdout e stderr invece di stamparli.

Quando c'è il `progress_callback`, si usa invece `subprocess.Popen` che permette di leggere l'output di Ghostscript riga per riga mentre gira, senza aspettare che finisca. Il codice cerca il pattern `"Page N"` nell'output per sapere quale pagina è stata processata e aggiornare la barra.

### Il profilo di compressione

```python
dpi = 300 - round(((strength - 1) / 99) * (300 - 72))
```

Questa formula converte un valore di "forza" (1-100) in un DPI (punti per pollice) per il downsampling delle immagini. `strength=1` → `dpi=300` (alta qualità, poca compressione); `strength=100` → `dpi=72` (bassa qualità, massima compressione). Il DPI delle immagini è il principale leva di compressione perché le immagini sono tipicamente la parte più pesante di un PDF.

### Il pattern staging

L'output non viene mai scritto direttamente alla destinazione finale. Ghostscript scrive in una cartella temporanea (`tempfile.TemporaryDirectory`), poi il file viene spostato a destinazione con `shutil.move`. Il motivo: se Ghostscript fallisce a metà, non lascia un file corrotto al path di output. La directory temporanea viene sempre eliminata nel blocco `finally`, anche in caso di eccezione.

Un'ulteriore complicazione: Ghostscript è un programma C che non gestisce bene i path con caratteri Unicode non-ASCII. Se il path contiene "Università" o simili, anche il file di input viene copiato in un percorso temporaneo ASCII-safe prima di essere passato a Ghostscript.

---

## 9. Il file `cli.py` — Il punto d'ingresso

### Come funziona `argparse`

`argparse` è la libreria standard Python per il parsing degli argomenti da riga di comando. `build_parser()` costruisce l'intera struttura:

- `parser.add_subparsers(dest="command")` crea la struttura "sottocomando" (come `git commit`, `git push`, ecc.).
- Ogni sottocomando viene definito con `subparsers.add_parser("ocr", ...)` e ha i suoi argomenti.
- `set_defaults(handler=_handle_ocr)` associa ogni sottocomando alla sua funzione handler. Quando `parse_args()` ha finito, `args.handler` contiene già la funzione giusta da chiamare.

### Il pattern "error boundary"

```python
def _execute_handler(args: argparse.Namespace) -> int:
    try:
        return args.handler(args)
    except PDFToolError as exc:
        print(f"Errore: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Operazione interrotta.", file=sys.stderr)
        return 130
```

Questo è il confine tra il codice applicativo e il sistema operativo. Le pipeline possono sollevare `PDFToolError` liberamente — sanno che qualcuno sopra le gestirà. Il codice di uscita `1` indica errore per convenzione Unix; `130` è il codice standard per "interrotto da Ctrl+C" (128 + segnale 2).

### Perché `main()` lancia la TUI se non ci sono argomenti

```python
def main(argv: Sequence[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if not arguments:
        return _run_interactive_shell_safe()
```

`sys.argv` è la lista degli argomenti passati al programma. `sys.argv[0]` è il nome del programma stesso; `sys.argv[1:]` sono gli argomenti dell'utente. Se la lista è vuota (nessun argomento), si avvia la TUI interattiva. Il parametro `argv` permette ai test di passare argomenti senza toccare `sys.argv`.

---

## 10. Il file `tui.py` — La TUI Textual

La TUI non usa più `prompt_toolkit` e `rich` come framework separati. Dopo la migrazione del 30 marzo 2026, tutta l'interfaccia interattiva vive dentro `Textual`, che gestisce schermate, widget, keybinding e aggiornamenti live.

La struttura attuale è questa:

- `PyDFApp` è la classe principale `textual.App`
- `HomeScreen` mostra il menu principale e il pannello anteprima
- `WizardScreen` guida l'utente nei flussi OCR e compressione
- `CheckInputScreen` raccoglie il path da analizzare
- `CheckResultScreen` mostra il verdetto di `check_ocr()`
- `ProgressScreen` esegue OCR o compressione in un worker thread
- `HelpScreen` mostra l'help come modal overlay

Il vantaggio architetturale è importante: non c'è più alternanza tra framework incompatibili sullo stesso terminale. Layout, dialog e progress appartengono tutti allo stesso event loop.

### Worker e aggiornamenti UI

`ProgressScreen` usa `@work(thread=True)` per eseguire OCR e compressione senza bloccare la UI. La pipeline passa aggiornamenti tramite `progress_callback`; il thread worker inoltra questi aggiornamenti con `app.call_from_thread(...)`, che è il modo thread-safe con cui Textual aggiorna lo stato visuale.

### Import in `tui.py`

A differenza di `ocr.py` e `compress.py`, `tui.py` importa `textual` direttamente in testa al file. È una scelta deliberata: la TUI è una dipendenza diretta del progetto. Se `textual` manca, il problema non è del singolo comando ma dell'ambiente Python, quindi la soluzione corretta è sistemare la `.venv`, non intercettare l'errore dentro la TUI.

---

## 11. I test — Come funzionano i mock

Il file `tests/test_cli.py` usa `unittest`, la libreria di test standard Python, e `unittest.mock`, che permette di sostituire temporaneamente parti del sistema con oggetti controllati.

### Perché mockare

Le pipeline OCR e compressione dipendono da Tesseract, Ghostscript e Poppler — programmi di sistema che potrebbero non essere installati nell'ambiente di test, e che sarebbero comunque lenti. I mock sostituiscono queste dipendenze con oggetti che si comportano come previsto senza fare nulla di reale.

### `patch` e `patch.dict`

```python
with patch("pydf_tool.cli.run_ocr", return_value=mock_result):
    exit_code = main(["ocr", "scan.pdf"])
```

`patch` sostituisce `run_ocr` nel modulo `pydf_tool.cli` (non nel modulo originale) con un oggetto finto che restituisce sempre `mock_result`. Importante: si patcha dove l'oggetto è *usato*, non dove è *definito*. Quando il blocco `with` finisce, tutto viene ripristinato.

```python
with patch.dict(sys.modules, {"pypdf": fake_pypdf}):
```

`patch.dict` sostituisce temporaneamente una voce in un dizionario — in questo caso nel registro dei moduli Python. Così quando `check_ocr.py` fa `from pypdf import PdfReader`, ottiene il `PdfReader` falso invece di quello reale.

### Classi fake inline

I test definiscono classi locali (`FakePage`, `FakeReader`, `FakePopen`) che replicano l'interfaccia minima necessaria per far funzionare il codice testato. Non implementano tutto — solo i metodi che il codice effettivamente chiama. Questo è il pattern "duck typing" di Python: se l'oggetto ha il metodo `.pages` e il metodo `.extract_text()`, al codice non importa che sia un vero `PdfReader`.

---

## 12. I pattern ricorrenti da riconoscere

Questi pattern appaiono in più punti del codice. Riconoscerli ti permette di leggere codice nuovo più velocemente.

**Dataclass frozen**: `@dataclass(frozen=True)` per oggetti risultato immutabili (`OCRResult`, `CompressionResult`, `CheckOCRResult`, `OperationProgress`). Il principio: una funzione restituisce un valore, non lo modifica dopo.

**Callback opzionale**: `callback: Callable[[X], None] | None = None`. Una funzione accetta opzionalmente un'altra funzione come parametro. Se `None`, non fa niente; altrimenti la chiama con aggiornamenti. Permette di usare la stessa pipeline in contesti diversi (CLI silenziosa, TUI con progress bar, test che catturano gli aggiornamenti).

**Import lazy in funzione**: le dipendenze pesanti o opzionali lato backend (`pytesseract`, `pdf2image`, `pypdf`) vengono importate dentro la funzione che le usa, non in cima al file. Permette di catturare `ImportError` e convertirlo in un messaggio leggibile. `textual` fa eccezione perché è una dipendenza diretta della TUI.

**Staging temporaneo**: l'output viene scritto in una directory temporanea, poi spostato a destinazione. Garantisce atomicità: o il file finale è completo, o non esiste.

**Error boundary unico**: tutta la gestione degli errori è concentrata in `_execute_handler()`. Le funzioni interne sollevano liberamente `PDFToolError`, che risale la catena fino al boundary. Nessun `try/except` disseminato per gestire la stessa cosa in punti diversi.

---

## 13. Le issue aperte — Cosa manca e perché

Il `PROJECT_CONTEXT.md` tiene traccia dei limiti ancora aperti. I più importanti oggi sono tre.

**OCR non interrompibile dentro la singola pagina**: Tesseract lavora in codice C. Python può fermare il flusso tra una pagina e l'altra, ma non entrare nel mezzo di una chiamata OCR già partita. La TUI resta responsiva, ma la cancellazione non è istantanea su pagine pesanti.

**Gap nei test sulla TUI**: i test attuali coprono bene helper, parser e backend mockato, ma non esercitano davvero i flow Textual a livello schermata/widget. La parte più nuova del progetto è quindi anche quella meno blindata.

**Fragilità del setup**: il pacchetto dichiara supporto `Python 3.10+`, ma `setup.sh` oggi patcha il wrapper puntando a `.venv/bin/python3.12`. È il workflow verificato, ma non è ancora un setup completamente agnostico rispetto alla minor version.

---

## 14. Come orientarsi quando qualcosa non funziona

Se `pydf-tool` non si trova: la venv non è attiva. Esegui `source .venv/bin/activate` dalla directory del progetto.

Se si trova ma crasha con `ModuleNotFoundError: No module named 'pydf_tool'` oppure con import mancanti lato TUI: il setup della venv è incoerente. Esegui `rm -rf .venv && bash setup.sh`.

Se le dipendenze Python cambiano dopo un `pip install -e .`: riapplica il patch con `bash setup.sh` (è necessario dopo ogni reinstall manuale).

Se i test falliscono: esegui `source .venv/bin/activate` e poi `PYTHONPATH=src python -m unittest discover -s tests -v` dalla root del progetto. Il comando con `python3` di sistema può fallire semplicemente perché `textual` non è installato globalmente.

Se vuoi capire cosa fa un pezzo di codice specifico: il modo più veloce è aggiungere un `print()` temporaneo, eseguire il comando reale, e osservare l'output. Non è elegante, ma funziona. Per qualcosa di più sistematico, `python3 -m pdb` è il debugger interattivo di Python.
