# PyDF Tool

`PyDF Tool` e un progetto di vibe coding in Python, orientato a macOS, con un obiettivo pratico: rendere semplice il trattamento di PDF scansionati e pesanti da terminale o da TUI.

Al momento il progetto punta a due funzioni principali:

- OCR di PDF scansionati, con output in PDF ricercabile o testo semplice
- compressione PDF su macOS, con preset e livello di compressione personalizzabile

Il progetto e in evoluzione. Interfaccia, comandi e dettagli di comportamento possono cambiare mentre la base funzionale si stabilizza.

## Overview

`pydf-tool` e il comando principale.

Modalita disponibili:

- TUI interattiva, avviata con `pydf-tool`
- CLI diretta con sottocomandi espliciti

Funzioni supportate oggi:

- `check` — verifica se un PDF ha già testo ricercabile
- `ocr` — OCR di PDF scansionati
- `compress` — compressione PDF

## Prerequisiti

Questo progetto e pensato per macOS.

Serve Python 3.10 o superiore.

Dipendenze di sistema richieste tramite Homebrew:

```bash
brew install tesseract tesseract-lang poppler ghostscript
```

Ruolo dei componenti esterni:

- `tesseract` esegue l'OCR
- `tesseract-lang` fornisce i dati lingua aggiuntivi
- `poppler` fornisce gli strumenti usati da `pdf2image`
- `ghostscript` viene usato per la compressione PDF

## Installazione

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Se il progetto era gia installato in precedenza, riesegui `pip install -e .` dopo eventuali aggiornamenti del codice.

Verifica rapida del comando:

```bash
pydf-tool --help
```

Avvio della TUI:

```bash
pydf-tool
```

## Uso ad Alto Livello

### TUI interattiva

Lancia `pydf-tool` senza argomenti per aprire l'interfaccia interattiva. Da li puoi scegliere OCR, compressione, help e comandi liberi.

Nella TUI:

- usa `↑/↓` per navigare
- usa `Enter` per confermare
- usa `Esc` per annullare o uscire dai dialog
- usa `H` o `F1` per aprire l'help
- usa `Ctrl+C` per interrompere un'operazione in corso

### CLI diretta

Usa i sottocomandi quando vuoi eseguire un'operazione precisa senza passare dalla TUI.

Verifica OCR:

```bash
pydf-tool check documento.pdf
```

OCR:

```bash
pydf-tool ocr input.pdf --lang it --output output.pdf
```

Compressione:

```bash
pydf-tool compress input.pdf --level medium --output output.pdf
```

## Esempi Principali

OCR in PDF ricercabile:

```bash
pydf-tool ocr scansione.pdf --lang it
```

OCR in testo semplice:

```bash
pydf-tool ocr scansione.pdf --lang it+en --output scansione.txt
```

Compressione con preset:

```bash
pydf-tool compress documento.pdf --level low
```

Compressione con livello custom:

```bash
pydf-tool compress documento.pdf --level 65 --output documento-small.pdf
```

Compressione con variante in bianco e nero:

```bash
pydf-tool compress documento.pdf --level medium --grayscale
```

Se `--output` non viene specificato, il file viene salvato nella stessa cartella dell'input con un nome incrementale.

## Note Sullo Stato Del Progetto

- Il progetto e in fase di evoluzione e non va considerato ancora una CLI definitiva.
- Le due aree su cui si concentra oggi sono OCR e compressione PDF.
- La TUI e la CLI esistono entrambe, ma possono cambiare layout, opzioni o flussi di interazione.
- Se usi il progetto per lavoro quotidiano, conviene verificare il comportamento dopo ogni aggiornamento.

## Sviluppo

Esegui i test locali con:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```
