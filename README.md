# PyDF Tool

`PyDF Tool` è una beta locale per macOS che aiuta a verificare se un PDF contiene già testo, eseguire OCR su scansioni e comprimere PDF pesanti. Si usa da terminale, ma la TUI è stata resa più guidata: selezione file da Finder, controlli iniziali dei prerequisiti, output suggerito nella stessa cartella e azioni rapide a fine operazione.

## Stato del progetto

Il progetto è usabile nella sua forma attuale come beta locale su macOS. Le tre funzioni principali sono presenti e la TUI supporta flussi più semplici rispetto alla CLI pura. Restano possibili evoluzioni dell'interfaccia, ma il comportamento documentato qui riflette lo stato attuale del codice.

## Prerequisiti

Serve macOS con Python `3.10+`. Il workflow verificato oggi è quello con Python.org Python `3.12` su macOS, perché `setup.sh` crea la `venv`, installa le dipendenze e applica il workaround necessario al wrapper `pydf-tool`.

Dipendenze di sistema via Homebrew:

```bash
brew install tesseract tesseract-lang poppler ghostscript
```

`tesseract` serve per l'OCR, `poppler` per la lettura/render delle pagine PDF e `ghostscript` per la compressione. `tesseract-lang` è utile se vuoi i pacchetti lingua aggiuntivi.

## Installazione

Setup consigliato:

```bash
bash setup.sh
source .venv/bin/activate
```

Verifica rapida:

```bash
pydf-tool --help
```

Se reinstalli le dipendenze con `pip install -e .`, riesegui anche `bash setup.sh` per riallineare il wrapper e il workaround macOS.

## Uso

### TUI interattiva

Avvia `pydf-tool` senza argomenti per aprire la TUI:

```bash
pydf-tool
```

Nella TUI attuale:

- nei campi file puoi aprire Finder con `F2` o con il pulsante dedicato
- all'avvio l'app controlla i prerequisiti e segnala subito eventuali mancanze
- nei wizard OCR e compressione l'output di default resta nella stessa cartella del file di partenza
- l'app ricorda ultima cartella usata, lingua OCR preferita e livello di compressione preferito
- a fine OCR o compressione puoi aprire subito il file o la cartella di output
- i messaggi di esito indicano dove ha salvato il file e, per la compressione, quanto ha ridotto

Controlli principali:

- `↑/↓` naviga tra le opzioni
- `Enter` conferma
- `Esc` torna indietro o esce dai dialog
- `H` o `F1` apre l'help
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
```

Se `--output` non viene specificato, il file viene creato nella stessa cartella dell'input con un nome incrementale.

## Funzioni disponibili

| Comando | Descrizione |
|---|---|
| `check` | Verifica se un PDF contiene già testo ricercabile o se serve OCR |
| `ocr` | Converte un PDF scansionato in PDF ricercabile o in TXT |
| `compress` | Comprimi un PDF con preset o livello personalizzato |

## Troubleshooting

**`pydf-tool: command not found`**  
Attiva la virtual environment con `source .venv/bin/activate` e riprova.

**`tesseract`, `pdftocairo`/`pdftoppm` o `gs` non vengono trovati**  
Installa o reinstalla le dipendenze di sistema con Homebrew.

**La TUI segnala prerequisiti mancanti**  
L'app ora fa un controllo iniziale e può bloccare OCR o compressione se manca un tool esterno.

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
