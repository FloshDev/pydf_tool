# Design: Migrazione TUI da prompt_toolkit+rich a Textual

**Data:** 2026-03-29
**Progetto:** PyDF Tool
**Issue:** #3 — alternanza prompt_toolkit/rich fragile su terminali non-standard
**Stato:** approvato

---

## Problema

`tui.py` alterna due framework incompatibili sullo stesso terminale:
- **prompt_toolkit** per menu, dialog, input (full-screen, intercetta ogni tasto)
- **rich** per progress bar e output a scorrimento

Ogni operazione produce 3 cambi di contesto del terminale (PT → shell → rich → shell → PT).
Su terminali non-standard (tmux, screen, emulatori IDE) il ripristino può essere incompleto:
cursore che sparisce, colori residui, input che smette di funzionare.

## Soluzione

Sostituire entrambi i framework con **Textual** — un unico framework TUI che gestisce
layout, widget, keybinding, progress bar e thread worker nello stesso ciclo di render.

---

## Vincoli

- `cli.py`, `ocr.py`, `compress.py`, `check_ocr.py`, `utils.py`, `progress.py`, `errors.py` **non vengono toccati**
- La firma di `run_interactive_app(parser_factory, executor)` rimane **invariata** — `cli.py` non sa che il framework è cambiato
- Palette colori CLAUDE.md invariata (vedi sotto)
- Sfondo sempre trasparente (nessun `background` esplicito nel CSS Textual)
- La suite di test rimane verde durante tutto il lavoro

---

## Architettura

### Struttura App

```
PyDFApp(textual.App)
├── HomeScreen(Screen)          — menu principale + pannello anteprima
├── WizardScreen(Screen)        — stepper riutilizzato per OCR e Comprimi
├── ProgressScreen(Screen)      — avanzamento operazione lunga + risultato finale
├── CheckResultScreen(Screen)   — risultato Verifica OCR (sincrona, istantanea)
└── HelpScreen(ModalScreen)     — overlay help, home visibile in trasparenza
```

### File

| File | Azione |
|---|---|
| `src/pydf_tool/tui.py` | **Riscritto da zero** con Textual |
| `src/pydf_tool/tui.tcss` | **Nuovo** — CSS Textual con palette CLAUDE.md |
| `pyproject.toml` | `textual` entra; `prompt_toolkit` esce; `rich` esce come dipendenza diretta |
| `tests/test_cli.py` | 4 test aggiornati (vedi sezione Test) |

---

## Schermate

### HomeScreen

**Layout:** due pannelli affiancati (Horizontal).
- Sinistra: `ListView` con le azioni del menu (↑↓ per navigare)
- Destra: pannello `Static` con anteprima dell'azione selezionata

**Header (stile D approvato):**
```
┌──────────────────────────────────────────────────┐
│                                                  │
│   ╠══ PyDF Tool ══╣   OCR  ·  compress  ·  check │
│                                                  │
│   ─────────────────────────────────────────────  │
│   strumenti PDF da riga di comando · macOS       │
│                                                  │
└──────────────────────────────────────────────────┘
```

**Keybinding:**
- `↑` / `↓` — naviga nel menu
- `Enter` — attiva l'azione selezionata
- `H` / `F1` — apre HelpScreen
- `Q` / `Esc` — esce dalla TUI

**Comportamento reattivo:** la selezione cambia il pannello destra via `on_list_view_selected()`.
Sotto 26 righe: il pannello destra si nasconde (solo lista).

---

### WizardScreen (stepper)

Schermata **unica e riutilizzabile** per OCR e Comprimi:
- OCR: 4 passi — File · Lingua · Formato · Output
- Comprimi: 4 passi — File · Livello · Colore · Output

Verifica OCR **non usa WizardScreen**: ha un singolo input testuale (file), gira
sincrona (< 1s), e mostra il risultato in `CheckResultScreen` (vedi sotto).

**Layout:**
```
┌─ Esegui OCR ──────────────────────────────────────┐
│  1. File  ▶ 2. Lingua  3. Formato  4. Output      │  ← indicatore passo
├───────────────────────────────────────────────────┤
│                                                   │
│  [contenuto del passo corrente]                   │
│                                                   │
├───────────────────────────────────────────────────┤
│  Invio avanza  Esc torna indietro                 │  ← footer
└───────────────────────────────────────────────────┘
```

**Navigazione:**
- `Enter` — avanza al passo successivo (con validazione inline)
- `Esc` — torna al passo precedente; se al passo 1, torna alla HomeScreen

**Validazione inline:** errori mostrati in rosso `#E85B4B` sotto il campo, senza dialog separati. Il wizard non avanza finché il campo non è valido.

**Al completamento dell'ultimo passo:** `app.push_screen(ProgressScreen(args))`.

---

### ProgressScreen

Aperta con `app.push_screen()`. Copre tutta la finestra.

**Fase operazione:**
```
┌─ PyDF Tool — Esegui OCR ──────────────────────────┐
│                                                   │
│  OCR pagina 3 / 12                                │
│                                                   │
│  ████████████░░░░░░░░░░░░░░░  25%                 │
│                                                   │
│  Tempo trascorso: 0:00:14                         │
│                                                   │
│  Ctrl+C per annullare                             │
│                                                   │
└───────────────────────────────────────────────────┘
```

**Implementazione:**
- L'operazione gira in un `Worker` Textual (thread separato)
- La `progress_callback` chiama `app.call_from_thread(self.update_progress, update)`
- Textual aggiorna la barra in modo thread-safe

**Al termine (successo):** la barra sparisce, appare il riepilogo risultato (output path, pagine/dimensioni). `Enter` → `app.pop_screen()`.

**Al termine (errore):** pannello rosso `#E85B4B` con messaggio. `Enter` → `app.pop_screen()`.

**Ctrl+C / cancellazione:**
Textual Worker espone un metodo `cancel()`. Quando l'utente preme `Ctrl+C`,
`ProgressScreen` chiama `worker.cancel()`, che imposta un flag interno. Tuttavia
Tesseract e Ghostscript sono processi C bloccanti — il Worker non può interromperli
dall'interno. Il meccanismo reale è:
- Per **Ghostscript**: `compress_pdf()` gestisce già `KeyboardInterrupt` (termina il
  subprocess e pulisce il file temporaneo). Il segnale viene propagato al thread del
  Worker tramite `worker.cancel()` + un evento threading che la callback controlla tra
  una pagina e l'altra.
- Per **OCR**: stesso approccio — il `KeyboardInterrupt` arriva tra una pagina e l'altra
  (non dentro la singola chiamata Tesseract).

In pratica: la finestra di reattività è la durata di una singola pagina (Issue #6 aperta,
non risolta in questa migrazione). La schermata mostra "Operazione annullata" in grigio
`#7A7A7A`. `Enter` → `app.pop_screen()`.

---

### CheckResultScreen

Usata esclusivamente per Verifica OCR. `check_ocr()` è sincrona e veloce (legge solo
metadati PDF, < 1s) — non ha bisogno di progress bar.

**Flusso:**
1. HomeScreen → input file (dialog `_ask_text` equivalente Textual, o mini-schermata)
2. Esecuzione sincrona di `check_ocr(path)`
3. Push `CheckResultScreen` con il risultato

**Contenuto:**
```
┌─ Verifica OCR — risultato ────────────────────────┐
│                                                   │
│  Pagine totali          12                        │
│  Pagine con testo        0                        │
│  Pagine senza testo     12                        │
│  Media caratteri/pag.    3                        │
│                                                   │
│  Verdetto: OCR necessario                         │
│                                                   │
│  [ Esegui OCR su questo file ]   [ Torna al menu ]│
│                                                   │
└───────────────────────────────────────────────────┘
```

Se verdetto è `already_searchable`: solo pulsante "Torna al menu".
Se verdetto è `ocr_needed` o `mixed`: pulsante "Esegui OCR" → pop + push WizardScreen(OCR)
con il path già precompilato.

---

### HelpScreen

`ModalScreen`: la HomeScreen rimane visibile in trasparenza dietro.
Contiene il testo di help formattato.
Chiude con `Enter`, `Esc` o `Q`.

---

## Palette colori (CLAUDE.md)

Implementata in `tui.tcss` come variabili CSS Textual:

| Ruolo | Valore | Uso |
|---|---|---|
| Accento primario | `#E8B84B` | Titolo, voce selezionata, step attivo, barra progresso |
| Testo normale | `#D4D4D4` | Corpo testo, voci menu non selezionate |
| Testo secondario | `#7A7A7A` | Hint, label, step inattivi, tempo trascorso |
| Bordi | `#3A3A3A` | Bordi box, separatori |
| Errore | `#E85B4B` | Messaggi di errore, validazione inline |
| Successo | `#4BE87A` | Conferme, operazione completata |
| Sfondo | trasparente | Mai impostare `background` esplicitamente |

---

## Dipendenze

### Rimosse
- `prompt_toolkit` — rimossa da `pyproject.toml`
- `rich` — rimossa come dipendenza diretta (Textual la porta come dipendenza interna)

### Aggiunte
- `textual` — versione stabile corrente (≥ 0.70.0)

---

## Test

### Test invariati (31)
Tutti i test che testano `ocr.py`, `compress.py`, `check_ocr.py`, `utils.py` e `cli.py`
(con backend mockato) non toccano `tui.py` — restano invariati.

### Test aggiornati (4)
| Test attuale | Azione |
|---|---|
| `test_dialog_width_shrinks_with_terminal` | Rimosso — `_dialog_width()` non esiste più |
| `test_wrap_dialog_text_wraps_bullets_with_indentation` | Rimosso — `_wrap_dialog_text()` non esiste più |
| `test_interactive_shell_runs_guided_ocr_flow` | Aggiornato per struttura Textual |
| `test_interactive_shell_exits_on_exit_key` | Aggiornato per struttura Textual |

### Test Textual (da aggiungere in seguito)
Textual fornisce un `Pilot` headless per testare schermate senza terminale reale.
Da aggiungere come attività separata dopo la migrazione.

---

## Piano di esecuzione (alto livello)

1. Aggiungere `textual` a `pyproject.toml`, rimuovere `prompt_toolkit` e `rich`
2. Creare `tui.tcss` con le variabili colore
3. Implementare `HomeScreen` con header stile D e layout due pannelli
4. Implementare `HelpScreen` (ModalScreen)
5. Implementare `WizardScreen` stepper per OCR
6. Implementare `WizardScreen` stepper per Comprimi
7. Implementare `CheckResultScreen` per Verifica OCR (+ flusso file input)
8. Implementare `ProgressScreen` con Worker
9. Implementare `run_interactive_app()` e `dispatch_interactive_command()`
10. Aggiornare i 4 test di `tui.py`
11. Verifica suite completa verde
