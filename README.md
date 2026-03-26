# PyDF Tool

`PyDF Tool` e una CLI per macOS scritta in Python. Il comando da terminale e `pydf-tool`.

Supporta due modalita:

- modalita interattiva TUI, avviata con `pydf-tool`
- modalita diretta con sottocomandi espliciti

Funzioni principali:

- `ocr`: converte un PDF scansionato in un PDF con testo selezionabile oppure in un file `.txt`
- `compress`: comprime un PDF con preset espliciti o livello numerico custom, con opzione opt-in per output in bianco e nero

## Funzionalita

### OCR

Il comando `ocr` usa `pdf2image` per rasterizzare ogni pagina del PDF e `pytesseract` per riconoscere il testo.

- Output supportati: `.pdf` ricercabile oppure `.txt`
- Lingue supportate dalla CLI: `it`, `en`, `it+en`
- Default output: nella stessa cartella dell input, con nome incrementale come `documento.1.pdf`
- Dalla TUI puoi scegliere cartella e nome del file di output

### Compressione

Il comando `compress` usa Ghostscript per generare una versione piu leggera del PDF.

- Preset espliciti: `low`, `medium`, `high`
- Livello numerico custom: intero tra `1` e `100`
- Opzione opt-in per comprimere in bianco e nero
- Default output: nella stessa cartella dell input, con nome incrementale come `documento.1.pdf`
- Dalla TUI puoi scegliere cartella e nome del file di output
- Mostra dimensione prima e dopo l operazione

Nota sul livello numerico:

- `1` = compressione minima, qualita piu alta
- `100` = compressione massima, file piu piccolo

### TUI interattiva

La modalita `pydf-tool` senza argomenti apre una TUI full-screen minimalista, ispirata a Claude, con:

- layout pulito e focalizzato, pensato per terminale
- layout responsive che si adatta meglio anche a finestre piu strette
- menu home navigabile con frecce `↑/↓`
- preview laterale essenziale della voce selezionata
- schermata help dedicata richiamabile dal menu o con `H` / `F1`
- wizard guidati per OCR e compressione
- dialog guidati keyboard-first: `Enter` conferma, `Esc` annulla
- salvataggio custom di cartella + nome file
- progresso live durante le operazioni
- annullamento con `Ctrl+C` durante OCR e compressione

## Prerequisiti di sistema

Su macOS installa le dipendenze richieste con Homebrew:

```bash
brew install tesseract tesseract-lang poppler ghostscript
```

Perche servono:

- `tesseract`: motore OCR
- `tesseract-lang`: dati lingua aggiuntivi, necessari per l italiano
- `poppler`: fornisce `pdftoppm` e `pdftocairo`, usati da `pdf2image`
- `ghostscript`: motore usato dal comando `compress` e dalla variante opt-in in bianco e nero

## Installazione

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Se hai gia installato una versione precedente, riesegui `pip install -e .` per
aggiornare le dipendenze Python e il launcher `pydf-tool`.

Verifica rapida dell entrypoint dopo l installazione:

```bash
pydf-tool --help
pydf-tool help
```

Per entrare nella shell interattiva:

```bash
pydf-tool
```

## Utilizzo

### Modalita interattiva

Avvia la TUI:

```bash
pydf-tool
```

Oppure in modo esplicito:

```bash
pydf-tool interactive
```

Per l aiuto generale o contestuale:

```bash
pydf-tool help
pydf-tool help ocr
pydf-tool help compress
```

Dentro la TUI puoi:

- usare `↑/↓` per muoverti nel menu home
- premere `Enter` per aprire l azione selezionata
- premere `H` o `F1` per l help
- premere `Q` o `Esc` per uscire
- usare `Enter` per confermare e `Esc` per annullare dentro i dialog guidati
- usare il menu `Comando libero` per eseguire un comando completo come `ocr scansione.pdf --lang it`
- premere `Ctrl+C` per annullare OCR o compressione in corso

### OCR in PDF ricercabile

```bash
pydf-tool ocr input.pdf --lang it --output output.pdf
```

### OCR in testo semplice

```bash
pydf-tool ocr input.pdf --lang it+en --output output.txt
```

Se `--output` non viene specificato, la CLI salva il file nella stessa cartella dell input con nome incrementale, ad esempio `input.1.pdf`.

### Compressione con preset

```bash
pydf-tool compress input.pdf --level medium --output output.pdf
```

### Compressione con livello custom

```bash
pydf-tool compress input.pdf --level 80 --output output.pdf
pydf-tool compress input.pdf --level medium --grayscale
```

Se `--output` non viene specificato, la CLI salva il file nella stessa cartella dell input con nome incrementale, ad esempio `input.1.pdf`.

## Esempi rapidi

```bash
pydf-tool ocr scansione.pdf --lang it
pydf-tool ocr scansione.pdf --lang en --output scansione.txt
pydf-tool compress documento.pdf --level low
pydf-tool compress documento.pdf --level medium --grayscale
pydf-tool compress documento.pdf --level 65 --output documento-small.pdf
```

## Sviluppo e test

Esegui i test locali con:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```
