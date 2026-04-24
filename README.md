# PyDF Tool

[![Release](https://img.shields.io/github/v/release/FloshDev/pydf_tool)](https://github.com/FloshDev/pydf_tool/releases)
[![Platform](https://img.shields.io/badge/platform-macOS-lightgrey)](https://github.com/FloshDev/pydf_tool)
[![License](https://img.shields.io/github/license/FloshDev/pydf_tool)](https://github.com/FloshDev/pydf_tool/blob/main/LICENSE)

> Strumento da riga di comando per macOS per controllare, eseguire OCR e comprimere file PDF — senza bisogno di installare Python.

PyDF Tool gestisce tre operazioni comuni sui PDF: rilevare se un PDF scansionato contiene già testo ricercabile, eseguire l'OCR su scansioni per produrre un PDF ricercabile o testo semplice, e comprimere PDF pesanti con livelli di qualità preimpostati o personalizzati. Viene distribuito come bundle `.app` autonomo (Python incluso) che si usa **dal terminale** — sia tramite TUI interattiva che direttamente da riga di comando.

## Installazione

### Prerequisiti

[Homebrew](https://brew.sh) deve essere installato, poi:

```bash
brew install tesseract tesseract-lang poppler ghostscript
```

| Strumento | Funzione |
|---|---|
| `tesseract` | Motore OCR per estrarre testo dalle pagine scansionate |
| `tesseract-lang` | Pacchetti dati linguistici per Tesseract (include italiano, inglese e altre lingue) |
| `poppler` | Convertitore PDF-in-immagine (`pdftocairo`/`pdftoppm`) usato prima dell'OCR |
| `ghostscript` | Backend per la compressione PDF (`gs`) |

Non serve Python.org, `pip` o ambienti virtuali — l'app include il proprio interprete.

### Download

1. Scarica `PyDF-Tool-v1.0.3.dmg` dalla pagina [Releases](https://github.com/FloshDev/pydf_tool/releases)
2. Apri il DMG e trascina **PyDF Tool** nella cartella **Applicazioni** usando il collegamento incluso
3. Al primo avvio: macOS Gatekeeper avverte che lo sviluppatore non è identificato — fai clic destro sull'app → **Apri** (richiesto una sola volta)

### Aggiornamenti

All'avvio, PyDF Tool verifica automaticamente se è disponibile una nuova versione e mostra un avviso nella schermata principale. Per aggiornare:

1. Scarica il nuovo DMG dalla pagina [Releases](https://github.com/FloshDev/pydf_tool/releases)
2. Apri il DMG e trascina **PyDF Tool** nella cartella **Applicazioni**, sovrascrivendo la versione precedente

## Utilizzo

### TUI interattiva

PyDF Tool è un'applicazione da terminale. Aprendo **PyDF Tool.app** dal Finder si avvia automaticamente una nuova finestra di Terminal.app con la TUI. In alternativa, dopo aver configurato il comando `pydf-tool` come descritto nella sezione [CLI](#cli), da qualsiasi terminale:

```bash
pydf-tool
```

<!-- screenshot -->

La TUI verifica i prerequisiti all'avvio e segnala immediatamente gli strumenti mancanti. La cartella di output predefinita è la stessa del file di input; l'app ricorda la cartella usata l'ultima volta, la lingua OCR preferita e il livello di compressione preferito tra le sessioni.

Controlli principali:

| Tasto | Azione |
|---|---|
| `↑` / `↓` | Naviga tra le opzioni |
| `Invio` | Conferma |
| `F2` | Apre una finestra Finder (selettore file o cartella, dove supportato) |
| `Esc` | Torna indietro o chiude un dialogo |
| `H` o `F1` | Apre la guida in linea (nelle schermate che la supportano) |
| `Ctrl+C` | Interrompe un'operazione in corso |

La voce di menu **OCR** si espande in due sotto-azioni: **Controlla OCR** (rileva testo esistente) ed **Esegui OCR** (avvia l'OCR). Dopo ogni operazione puoi aprire il file di output o la cartella che lo contiene direttamente dalla schermata dei risultati.

### CLI

La CLI permette di usare PyDF Tool direttamente da terminale, senza la TUI interattiva.

#### 1. Apri Terminal

Premi **Cmd+Spazio**, digita `Terminale` e premi Invio. Si apre la finestra del terminale.

#### 2. Rendi disponibile il comando `pydf-tool`

L'app include Python al suo interno ma non installa automaticamente il comando `pydf-tool` nel terminale. Esegui **una volta sola**:

```bash
echo 'alias pydf-tool="/Applications/PyDF Tool.app/Contents/Frameworks/python/bin/python3 -m pydf_tool"' >> ~/.zshrc && source ~/.zshrc
```

Da quel momento `pydf-tool` sarà disponibile in ogni nuova finestra di terminale.

#### 3. Ottieni il percorso del file PDF

Per indicare un file al comando, hai bisogno del suo percorso completo. Il modo più semplice: trascina il file PDF direttamente nella finestra del terminale — il percorso viene incollato automaticamente.

In alternativa, usa `~/Desktop/documento.pdf` per un file sul Desktop, o il percorso completo come `/Users/tuonome/Documenti/documento.pdf`.

#### 4. Comandi

```bash
# Controlla se un PDF contiene già testo ricercabile
pydf-tool check /percorso/del/file.pdf

# OCR su un PDF scansionato — produce un PDF ricercabile
pydf-tool ocr /percorso/del/file.pdf --lang it --output /percorso/output.pdf

# OCR con più lingue, output come file di testo
pydf-tool ocr /percorso/del/file.pdf --lang it+en --output /percorso/output.txt

# Compressione con livello preimpostato (low / medium / high)
pydf-tool compress /percorso/del/file.pdf --level medium --output /percorso/output.pdf

# Compressione con qualità personalizzata (0 = massima compressione, 100 = qualità originale)
pydf-tool compress /percorso/del/file.pdf --level 65 --output /percorso/output.pdf

# Comprimi e converti in scala di grigi
pydf-tool compress /percorso/del/file.pdf --level medium --grayscale

# Verifica se è disponibile una nuova versione
pydf-tool update

# Mostra la guida per un comando specifico
pydf-tool help ocr
```

Se `--output` viene omesso, il file di output viene creato nella stessa cartella del file di input con un nome incrementale automatico.

## Funzionalità

| Comando | Descrizione |
|---|---|
| `check` | Rileva se un PDF contiene già testo ricercabile o necessita di OCR |
| `ocr` | Converte un PDF scansionato in un PDF ricercabile o in un file di testo semplice |
| `compress` | Riduce le dimensioni del PDF usando un livello preimpostato o un valore di qualità personalizzato |
| `interactive` | Avvia esplicitamente la TUI interattiva |
| `update` | Verifica se è disponibile una nuova versione |
| `help` | Mostra la guida generale o la guida dettagliata per un sottocomando |

## Risoluzione dei problemi

**macOS mostra l'avviso "sviluppatore non identificato"**
Fai clic destro sull'app → **Apri**. È richiesto solo al primo avvio.

**`tesseract`, `pdftocairo`/`pdftoppm` o `gs` non trovati**
Installa o reinstalla le dipendenze di sistema tramite Homebrew (vedi [Prerequisiti](#prerequisiti)).

**La TUI segnala prerequisiti mancanti**
L'app esegue un controllo dei prerequisiti all'avvio e blocca OCR e compressione se uno strumento esterno richiesto è assente.

**Il PDF non viene riconosciuto dall'OCR**
Esegui prima `pydf-tool check document.pdf`. File protetti da password o gravemente corrotti possono causare il fallimento dell'OCR.

**La compressione non riduce significativamente le dimensioni del file**
Se il PDF è già molto compresso o contiene solo testo vettoriale, la riduzione dimensionale è limitata.

## Sviluppo

```bash
git clone https://github.com/FloshDev/pydf_tool
cd pydf_tool
pip install -e ".[dev]"
pytest tests/
```

Per costruire il bundle `.app` autonomo e il DMG:

```bash
scripts/build_macos_app.sh
```

Lo script produce un `.dmg` in `dist/` con un collegamento ad Applicazioni per l'installazione tramite trascinamento. Eventuali DMG precedenti della stessa versione vengono rimossi prima della build.

## Licenza

Questo progetto è distribuito secondo i termini riportati nel file [LICENSE](LICENSE).
