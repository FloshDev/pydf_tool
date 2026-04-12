# PyDF Tool

`PyDF Tool` è una beta locale per macOS che aiuta a verificare se un PDF contiene già testo, eseguire OCR su scansioni e comprimere PDF pesanti. Si usa da terminale, ma la TUI è stata resa più guidata: selezione file da Finder, controlli iniziali dei prerequisiti, output suggerito nella stessa cartella e azioni rapide a fine operazione.

## Stato del progetto

Il progetto è usabile nella sua forma attuale come beta locale su macOS. Le tre funzioni principali sono presenti, la TUI supporta flussi più semplici rispetto alla CLI pura e la repo include ora anche un launcher `.app` locale con icona dedicata per aprire il tool dal Finder. Restano possibili evoluzioni dell'interfaccia e del packaging, ma il comportamento documentato qui riflette lo stato attuale del codice.

## Prerequisiti

- macOS (testato con Python.org Python `3.12`)
- [Homebrew](https://brew.sh) — gestore pacchetti macOS
- [Python 3.12](https://www.python.org/downloads/macos/) da python.org

Dipendenze di sistema via Homebrew:

```bash
brew install tesseract tesseract-lang poppler ghostscript
```

`tesseract` serve per l'OCR, `poppler` per il render delle pagine PDF e `ghostscript` per la compressione.

## Installazione

```bash
git clone https://github.com/FloshDev/pydf_tool.git "PyDF Tool"
cd "PyDF Tool"
brew install tesseract tesseract-lang poppler ghostscript
bash setup.sh
source .venv/bin/activate
```

Verifica rapida:

```bash
pydf-tool --help
```

Se reinstalli le dipendenze con `pip install -e .`, riesegui anche `bash setup.sh` per riallineare il wrapper e il workaround macOS.

## Launcher macOS

Per costruire il launcher `.app` locale con icona:

```bash
scripts/build_macos_launcher.sh
```

Output generati:

- `assets/icon/pydf-tool-icon-1024.png` — master PNG definitivo dell'icona
- `assets/icon/pydf-tool.icns` — icona macOS generata dal PNG
- `dist/PyDF Tool.app` — launcher locale apribile dal Finder

Il launcher apre Terminal e lancia `pydf-tool` dentro questa repo con la `.venv` corrente. Non è ancora un'app standalone: se sposti la cartella del progetto o ricrei la `.venv`, conviene rigenerarlo con `scripts/build_macos_launcher.sh`. Se in futuro cambi l'icona, sostituisci prima `assets/icon/pydf-tool-icon-1024.png`.

## Uso

### TUI interattiva

Avvia `pydf-tool` senza argomenti per aprire la TUI:

```bash
pydf-tool
```

Nella TUI attuale:

- `OCR` apre un sottomenu con `Verifica OCR` ed `Esegui OCR`
- nei passi file e nella verifica OCR puoi aprire Finder con `F2` o con il pulsante dedicato
- nei passi output puoi usare `F2` per scegliere la cartella di destinazione e il file finale viene proposto automaticamente
- all'avvio l'app controlla i prerequisiti e segnala subito eventuali mancanze
- nei wizard OCR e compressione l'output di default resta nella stessa cartella del file di partenza
- l'app ricorda ultima cartella usata, lingua OCR preferita e livello di compressione preferito
- a fine OCR o compressione puoi aprire subito il file o la cartella di output
- i messaggi di esito indicano dove ha salvato il file e, per la compressione, quanto ha ridotto

Controlli principali:

- `↑/↓` naviga tra le opzioni
- `Enter` conferma
- `F2` apre Finder quando il campo corrente lo supporta
- `Esc` torna indietro o esce dai dialog
- `H` o `F1` apre l'help nelle schermate che lo supportano
- `Ctrl+C` interrompe un'operazione in corso

### CLI diretta

Se vuoi saltare la TUI:

```bash
pydf-tool check documento.pdf

pydf-tool ocr scansione.pdf --lang it --output output.pdf
pydf-tool ocr scansione.pdf --lang it+en --output scansione.txt

pydf-tool compress documento.pdf --level medium --output output.pdf
pydf-tool compress documento.pdf --level 65 --output documento-small.pdf
pydf-tool compress documento.pdf --level medium --grayscale

pydf-tool interactive
pydf-tool help
pydf-tool help ocr
```

Se `--output` non viene specificato, il file viene creato nella stessa cartella dell'input con un nome incrementale.

## Funzioni disponibili

| Comando | Descrizione |
|---|---|
| `check` | Verifica se un PDF contiene già testo ricercabile o se serve OCR |
| `ocr` | Converte un PDF scansionato in PDF ricercabile o in TXT |
| `compress` | Comprimi un PDF con preset o livello personalizzato |
| `interactive` | Apre esplicitamente la TUI interattiva |
| `help` | Mostra l'aiuto generale o di un sottocomando |

## Troubleshooting

**`pydf-tool: command not found`**  
Attiva la virtual environment con `source .venv/bin/activate` e riprova.

**`tesseract`, `pdftocairo`/`pdftoppm` o `gs` non vengono trovati**  
Installa o reinstalla le dipendenze di sistema con Homebrew.

**La TUI segnala prerequisiti mancanti**  
L'app ora fa un controllo iniziale e può bloccare OCR o compressione se manca un tool esterno.

**Il launcher `.app` non parte o apre un terminale con errore sulla `.venv`**  
Ricrea l'ambiente con `bash setup.sh` e rigenera il bundle con `scripts/build_macos_launcher.sh`.

**Il PDF non viene riconosciuto dall'OCR**  
Verifica prima con `pydf-tool check documento.pdf`. Se il file è protetto o molto irregolare, l'OCR può fallire.

**La compressione non riduce molto il file**  
Se il PDF è già molto compresso o contiene solo testo vettoriale, il margine di riduzione è limitato.

## Sviluppo

Test locali con la venv attiva:

```bash
source .venv/bin/activate
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v
```

