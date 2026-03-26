# PyDF Tool

> **Progetto in sviluppo attivo.** Funziona, ma comandi, opzioni e comportamenti possono cambiare tra una versione e l’altra. Non considerare ancora l’interfaccia come stabile.

`pydf-tool` è un tool da terminale per macOS pensato per semplificare due operazioni comuni sui PDF: l’OCR di documenti scansionati e la compressione di file pesanti. Disponibile sia come CLI diretta che come TUI interattiva.

-----

## Stato del progetto

Il progetto è funzionale nelle sue due aree principali — OCR e compressione — ma è ancora in evoluzione. La struttura dei comandi, le opzioni disponibili e i dettagli di comportamento possono variare mentre la base si stabilizza. Se usi il tool regolarmente, verifica il comportamento dopo ogni aggiornamento.

-----

## Prerequisiti

macOS con Python 3.10 o superiore.

Per verificare la versione di Python installata:

```bash
python3 --version
```

Dipendenze di sistema tramite Homebrew:

```bash
brew install tesseract tesseract-lang poppler ghostscript
```

|Componente      |Ruolo                                      |
|----------------|-------------------------------------------|
|`tesseract`     |Esegue l’OCR                               |
|`tesseract-lang`|Fornisce i dati lingua aggiuntivi          |
|`poppler`       |Strumenti usati internamente da `pdf2image`|
|`ghostscript`   |Motore di compressione PDF                 |

-----

## Installazione

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Per verificare che il comando sia disponibile:

```bash
pydf-tool --help
```

Se il progetto era già installato in precedenza, riesegui `pip install -e .` dopo aggiornamenti del codice.

-----

## Funzioni disponibili

|Comando   |Descrizione                                                           |
|----------|----------------------------------------------------------------------|
|`check`   |Verifica se un PDF ha già testo ricercabile                           |
|`ocr`     |OCR di PDF scansionati, con output in PDF ricercabile o testo semplice|
|`compress`|Compressione PDF con preset o livello personalizzabile                |

-----

## Utilizzo

### TUI interattiva

Avvia `pydf-tool` senza argomenti per aprire l’interfaccia interattiva:

```bash
pydf-tool
```

Navigazione:

- `↑/↓` — navigare tra le opzioni
- `Enter` — confermare
- `Esc` — annullare o uscire dai dialog
- `H` o `F1` — aprire l’help
- `Ctrl+C` — interrompere un’operazione in corso

### CLI diretta

Usa i sottocomandi per eseguire un’operazione specifica senza passare dalla TUI.

**Verifica:**

```bash
pydf-tool check documento.pdf
```

**OCR:**

```bash
# Output in PDF ricercabile
pydf-tool ocr scansione.pdf --lang it --output output.pdf

# Output in testo semplice
pydf-tool ocr scansione.pdf --lang it+en --output scansione.txt
```

**Compressione:**

```bash
# Preset predefiniti: low, medium, high
pydf-tool compress documento.pdf --level medium --output output.pdf

# Livello personalizzato (valore numerico)
pydf-tool compress documento.pdf --level 65 --output documento-small.pdf

# Conversione in bianco e nero durante la compressione
pydf-tool compress documento.pdf --level medium --grayscale
```

Se `--output` non viene specificato, il file viene salvato nella stessa cartella dell’input con un nome incrementale.

-----

## Troubleshooting

**`pydf-tool: command not found`**
Il virtual environment non è attivo. Esegui `source .venv/bin/activate` e riprova.

**`tesseract: command not found` o `gs: command not found`**
Le dipendenze di sistema non sono installate o non sono nel PATH. Verifica con `brew list` e reinstalla se necessario.

**Il PDF non viene riconosciuto dall’OCR**
Alcuni PDF sono protetti da password o hanno un encoding non standard. Verifica prima con `pydf-tool check documento.pdf`.

**La compressione non riduce il file in modo significativo**
Se il PDF contiene già immagini molto compresse o testo vettoriale, i margini di riduzione sono limitati. Prova con `--level high` o `--grayscale`.

-----

## Sviluppo

Esegui i test locali con:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```