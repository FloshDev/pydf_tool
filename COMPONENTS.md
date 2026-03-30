# COMPONENTS

Questo file elenca le dipendenze esterne di `PyDF Tool` (`pydf-tool`) e va aggiornato ogni volta che vengono aggiunte, rimosse o modificate dipendenze di progetto o tool di sistema richiesti.

## Dipendenze Python

| Nome | Versione | Licenza | Scopo nel progetto |
| --- | --- | --- | --- |
| `pdf2image` | `1.17.0` | `MIT` | Converte le pagine del PDF in immagini da passare all OCR. |
| `textual` | `>=0.70.0` (installata: `8.2.1`) | `MIT` | Framework unico della TUI interattiva: schermate, widget, keybinding e progress. |
| `pytesseract` | `0.3.13` | `Apache-2.0` | Wrapper Python del motore Tesseract per OCR e generazione del PDF ricercabile. |
| `Pillow` | `>=10.3.0,<12.0` (installata: `11.3.0`) | `MIT-CMU` | Backend immagini usato da `pdf2image` e `pytesseract` durante la pipeline OCR. |
| `pypdf` | `6.8.0` | `BSD-3-Clause` | Legge i PDF per `check_ocr` e unisce le singole pagine OCR nel PDF finale ricercabile. |

## Dipendenze transitive rilevanti

| Nome | Provenienza | Licenza | Scopo nel progetto |
| --- | --- | --- | --- |
| `rich` | transitiva via `textual` | `MIT` | Rendering interno usato da Textual; non è più una dipendenza diretta del progetto. |

## Dipendenze di sistema

| Nome | Versione verificata | Licenza | Scopo nel progetto |
| --- | --- | --- | --- |
| `tesseract` | `5.5.2` | `Apache-2.0` | Motore OCR usato da `pytesseract`. |
| `tesseract-lang` | `4.1.0` | `Apache-2.0` | Installa i language pack aggiuntivi necessari per l italiano. |
| `poppler` | `26.03.0` | `GPL-2.0-only` | Fornisce `pdftoppm` e `pdftocairo`, richiesti da `pdf2image`. |
| `ghostscript` | `10.07.0` | `AGPL-3.0-or-later` | Esegue la compressione del PDF nel comando `compress`, inclusa la variante opt-in in bianco e nero. |

## Nota di manutenzione

Quando cambi una dipendenza:

- aggiorna `pyproject.toml`
- aggiorna questo file con versione, licenza e scopo
- verifica anche i prerequisiti descritti in `README.md`
