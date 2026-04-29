# Piano di refactoring — PyDF Tool

Stato base: v1.0.5 · 3217 righe · 101 test passanti

---

## Sessione 1 — Dead code removal

**File: `tui.py`**

Rimuovere:
- `dispatch_interactive_command()` (riga 1421–1471) — funzione pubblica mai raggiungibile da `main()`
- `EXIT_COMMANDS = {"exit", "quit", ":q"}` — usato solo dalla funzione sopra
- `_HELP_TEXT_PLAIN` (riga 156–163) — usato solo dalla funzione sopra
- `import argparse` (riga 3) — usato solo dalla funzione sopra
- `import shlex` (riga 4) — usato solo dalla funzione sopra

**File: `cli.py`**

Rimuovere:
- `_dispatch_interactive_command()` (riga 207–213) — wrapper della funzione rimossa da tui.py, mai chiamata da `main()`

**File: `macos_integration.py`**

Rimuovere:
- `reveal_in_finder()` (riga 114–119) — esportata in `__all__` ma mai importata da nessun modulo
- Rimuoverla da `__all__`

**File: `tests/test_cli.py`**

Rimuovere:
- Import di `_dispatch_interactive_command` (riga 16)
- Classe o metodi di test per `_dispatch_interactive_command` (righe ~1060–1110)

**Verifica:** `pytest tests/` deve passare 101 → N test (N < 101 dopo rimozione test dead code).

---

## Sessione 2 — tui.py: deduplicazione strutturale

**Problema 1: `OCRMenuScreen._set_preview` duplica `MenuScreen._set_preview`**

`MenuScreen._set_preview` aggiorna `#preview-title`, `#preview-body`, `#preview-hint`.  
`OCRMenuScreen._set_preview` aggiorna `#ocr-preview-title`, `#ocr-preview-body`, `#ocr-preview-hint`.

Fix: aggiungere un metodo `_preview_ids()` che ritorna una tupla `(title_id, body_id, hint_id)`.  
`MenuScreen` ritorna i default, `OCRMenuScreen` override con i propri ID.  
`_set_preview` nel base class usa `_preview_ids()` — `OCRMenuScreen._set_preview` si rimuove.

**Problema 2: `_move_button_focus` e `_focus_first_button` duplicati**

`CheckResultScreen` e `ProgressScreen` hanno entrambi:
- `_focus_first_button()`
- `_move_button_focus(direction)`
- `action_focus_next_button()` / `action_focus_prev_button()`
- Differiscono solo in `_buttons()` vs `_visible_buttons()` (stessa logica, diverso filtro)

Fix: aggiungere un `_ButtonNavigableMixin` con `_navigable_buttons() -> list[Button]` astratto,
`_focus_first_button()` e `_move_button_focus()` condivisi.
`CheckResultScreen._navigable_buttons()` ritorna `list(self.query(Button))`.
`ProgressScreen._navigable_buttons()` ritorna i bottoni visibili.

**Problema 3: `_suggest_output_path_in_directory` in tui.py**

Funzione di utilità su path che appartiene a `utils.py`.  
Spostare in `utils.py`, aggiornare import in `tui.py`.

---

## Sessione 3 — compress.py: cleanup

**Problema 1: `CompressionProfile.pdf_setting` sempre `/ebook`**

Il campo è vestigiale da quando si usavano `/printer` e `/screen` (rimossi in v1.0.2–v1.0.4).  
Fix: rimuovere il campo dal dataclass, sostituire con costante di modulo `_GS_PDF_SETTING = "/ebook"`,
usarla direttamente nella costruzione del comando.

**Problema 2: due percorsi subprocess quasi identici in `compress_pdf`**

Il branch `if progress_callback is None` esegue `subprocess.run(quiet_command)`.  
Il branch `else` esegue `subprocess.Popen` con streaming.

Estrarre `_run_gs_quiet(command)` e `_run_gs_streaming(command, progress_callback, page_count, grayscale)`.
`compress_pdf` chiama l'uno o l'altro — la costruzione del comando resta condivisa.

---

## Sessione 4 — ocr.py: deduplicazione loop OCR

**Problema: quattro percorsi quasi identici**

`run_ocr` contiene:
1. Page-by-page TXT (riga 141–201)
2. Page-by-page PDF (riga 203–270)
3. Batch TXT (riga 299–339)
4. Batch PDF (riga 341–386)

I percorsi 1 e 2 differiscono solo nella chiamata OCR (`image_to_string` vs `image_to_pdf_or_hocr`).
I percorsi 3 e 4 idem.
I percorsi 1–2 e 3–4 differiscono solo nel modo di caricare le immagini (una per volta vs batch).

Fix:
- Estrarre `_process_page(image, tesseract_lang, output_type) -> str | bytes`
- Estrarre `_write_txt_output(destination, page_results)` e `_write_pdf_output(destination, page_results)`
- Unificare il loop in una singola funzione `_run_ocr_loop(...)` che accetta un generatore di immagini
- Il percorso batch diventa un caso speciale del percorso page-by-page con `first_page=1, last_page=None`

---

## Sessione 5 — macos_integration.py: deduplicazione osascript

**Problema: `choose_pdf_file` e `choose_directory` duplicano il pattern subprocess**

Entrambe costruiscono un comando osascript, eseguono `subprocess.run`, gestiscono cancel e errori.
Differiscono solo nello script AppleScript e nella validazione del risultato.

Fix: estrarre `_run_osascript_chooser(script, prompt, initial_dir) -> str | None`
che ritorna il percorso selezionato o `None` su cancel.
`choose_pdf_file` e `choose_directory` chiamano `_run_osascript_chooser` e applicano validazione specifica.

---

## Note operative per le sessioni

- Ogni sessione: eseguire `pytest tests/` a fine lavoro — 0 regressioni ammesse
- Non aggiungere feature, non cambiare comportamento osservabile
- Sessione 1 va eseguita prima delle altre (rimuove codice che le sessioni successive non devono toccare)
- Sessioni 2–5 sono indipendenti tra loro, eseguibili in qualsiasi ordine dopo Sessione 1
- Aggiornare `PROJECT_CONTEXT.md` a fine refactoring con le nuove decisioni architetturali
