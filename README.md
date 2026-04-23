# PyDF Tool

`PyDF Tool` è un'app macOS per verificare se un PDF contiene già testo, eseguire OCR su scansioni e comprimere PDF pesanti. Si usa aprendo l'app dal Finder o dal terminale. La TUI guida l'utente con selezione file da Finder, controlli iniziali dei prerequisiti, output suggerito nella stessa cartella e azioni rapide a fine operazione.

## Prerequisiti

[Homebrew](https://brew.sh) e i tool OCR/PDF:

```bash
brew install tesseract tesseract-lang poppler ghostscript
```

`tesseract` serve per l'OCR, `poppler` per il render delle pagine PDF e `ghostscript` per la compressione.

## Installazione

1. Installa i prerequisiti (vedi sopra)
2. Scarica `PyDF-Tool-v1.0.0.dmg` dalla [pagina Releases](https://github.com/FloshDev/pydf_tool/releases)
3. Monta il DMG e apri `PyDF Tool.app`
4. Al primo avvio macOS mostra un avviso di sicurezza: right-click sull'app → **Apri** — richiesto una sola volta

Non serve Python.org, git clone o configurazione aggiuntiva.

## Uso

### TUI interattiva

Apri `PyDF Tool.app` dal Finder, oppure da terminale:

```bash
pydf-tool
```

Nella TUI:

- `OCR` apre un sottomenu con `Verifica OCR` ed `Esegui OCR`
- nei passi file e nella verifica OCR puoi aprire Finder con `F2` o con il pulsante dedicato
- nei passi output puoi usare `F2` per scegliere la cartella di destinazione
- all'avvio l'app controlla i prerequisiti e segnala subito eventuali mancanze
- l'output di default resta nella stessa cartella del file di partenza
- l'app ricorda ultima cartella usata, lingua OCR preferita e livello di compressione preferito
- a fine OCR o compressione puoi aprire subito il file o la cartella di output

Controlli principali:

- `↑/↓` naviga tra le opzioni
- `Enter` conferma
- `F2` apre Finder quando il campo corrente lo supporta
- `Esc` torna indietro o esce dai dialog
- `H` o `F1` apre l'help nelle schermate che lo supportano
- `Ctrl+C` interrompe un'operazione in corso

### CLI diretta

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

**macOS mostra "app da sviluppatore non identificato"**  
Right-click sull'app → **Apri**. Richiesto una sola volta.

**`tesseract`, `pdftocairo`/`pdftoppm` o `gs` non vengono trovati**  
Installa o reinstalla le dipendenze di sistema con Homebrew.

**La TUI segnala prerequisiti mancanti**  
L'app fa un controllo iniziale e può bloccare OCR o compressione se manca un tool esterno.

**Il PDF non viene riconosciuto dall'OCR**  
Verifica prima con `pydf-tool check documento.pdf`. Se il file è protetto o molto irregolare, l'OCR può fallire.

**La compressione non riduce molto il file**  
Se il PDF è già molto compresso o contiene solo testo vettoriale, il margine di riduzione è limitato.

## Sviluppo

Il codice sorgente è disponibile su [GitHub](https://github.com/FloshDev/pydf_tool).

Test locali (richiede setup venv di sviluppo con `bash setup.sh`):

```bash
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v
```
