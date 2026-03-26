# PROJECT CONTEXT

## Purpose

`PyDF Tool` is a Python CLI/TUI project for macOS focused on two PDF workflows:

- OCR of scanned PDFs to searchable `.pdf` or `.txt`
- PDF compression with presets, numeric levels, and optional grayscale conversion

Primary command:

```bash
pydf-tool
```

This document is intentionally path-agnostic so it remains valid even if the project directory is moved.

## Project Identity

- Project name: `PyDF Tool`
- CLI command: `pydf-tool`
- Language: Python
- Target platform: macOS
- Main UX modes:
  - direct CLI with subcommands
  - interactive TUI built with `prompt_toolkit`

## Repository Layout

All paths below are relative to the repository root.

```text
.
├── pyproject.toml
├── README.md
├── COMPONENTS.md
├── REPORT VIBE CODING.md
├── PROJECT_CONTEXT.md
├── .gitignore
├── scripts/
│   └── pydf-tool
├── src/
│   └── pdf_tool/
│       ├── __init__.py
│       ├── __main__.py
│       ├── cli.py
│       ├── tui.py
│       ├── ocr.py
│       ├── compress.py
│       ├── progress.py
│       ├── utils.py
│       └── errors.py
└── tests/
    └── test_cli.py
```

## Architecture Summary

### `src/pdf_tool/cli.py`

Responsibility:

- builds the `argparse` interface
- exposes `ocr`, `compress`, `interactive`, `help`
- routes into direct CLI mode or TUI mode
- translates `PDFToolError` into user-facing stderr output

### `src/pdf_tool/tui.py`

Responsibility:

- implements the full-screen TUI
- renders home, help, guided dialogs, and progress UI
- runs OCR/compression from guided flows
- supports both keyboard-first and mouse-assisted interaction

Important behavior:

- responsive layout by terminal width
- compact layout when terminal height is limited
- home actions include `OCR assistito`, `Compressione`, `Comando libero`, `Help`, `Esci`
- radio lists confirm on `Enter` and on mouse click

### `src/pdf_tool/ocr.py`

Responsibility:

- validates OCR input/output
- resolves OCR languages
- rasterizes PDF pages with `pdf2image`
- runs OCR with `pytesseract`
- writes `.txt` or assembles a searchable PDF

### `src/pdf_tool/compress.py`

Responsibility:

- validates compression input/output
- converts level presets to Ghostscript options
- handles optional grayscale conversion
- runs Ghostscript
- reports size before/after

Important implementation detail:

- Ghostscript output is staged into a temporary safe path first
- final file is then moved into the requested destination path
- if input path contains Unicode characters that Ghostscript may mishandle, the source may be copied into a temporary ASCII-safe path first

### `src/pdf_tool/utils.py`

Responsibility:

- shared path and size helpers
- path normalization for macOS Unicode variants
- incremental output filename generation

Critical helper:

- `resolve_user_path()` normalizes macOS Unicode path variants such as names containing accented characters

## Current Known State

### Verified

- `pydf-tool --help` works
- `pydf-tool help` works
- TUI starts correctly
- TUI home navigation via arrows works
- help dialog works
- radio dialogs confirm by keyboard and mouse
- path normalization for macOS Unicode variants is implemented and covered by tests
- compression CLI flow was verified against a real user PDF with output in `/tmp`
- test suite passes

### Recently Fixed

- lingering selection rendering bug in TUI
- truncated help UI
- poor dialog keyboard flow
- path resolution failures on macOS Unicode paths such as `Università`
- Ghostscript output failures on Unicode destination paths by using staged temp output
- home layout hiding bottom actions on short terminals

### Still Sensitive / Needs Real-World Verification

- OCR on large real PDFs can appear stalled because it is slow and produces no immediate CLI output in direct mode
- writes into user folders like `~/Documents` could not be fully verified from the Codex sandbox
- TUI end-to-end flows with real OCR/compression targets should be rechecked locally after major changes
- compression can legitimately create a larger file than the original, depending on the source PDF

## Known Risks

### OCR runtime clarity

Direct CLI OCR has no rich live progress. On large files this can feel like a hang even when work is ongoing.

### Ghostscript unpredictability

Compression ratio is not guaranteed. Some PDFs get larger after recompression.

### Editable install after folder move

This project uses editable install mechanics and a bootstrap script. After moving the repository directory, the local environment must be refreshed.

### Sandbox mismatch

Some failures seen during development were caused by the sandbox not being allowed to write into user folders. These are not automatically application bugs.

## Move / Relocation Checklist

If the repository is moved to a different folder:

1. Open a shell in the new repository root.
2. Recreate or refresh the virtual environment.
3. Re-run editable install.
4. Re-test CLI entrypoint.
5. Re-test one OCR flow and one compression flow.

Recommended commands after moving:

```bash
cd /new/path/to/project
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
pydf-tool --help
```

If you keep the existing `.venv`, still do this:

```bash
cd /new/path/to/project
source .venv/bin/activate
pip install -e . --no-build-isolation
hash -r
pydf-tool --help
```

If you use shell aliases pointing at the old location, update them too.

## Local Verification Commands

Run from repo root.

### Test suite

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
python3 -m compileall src tests scripts
```

### CLI smoke checks

```bash
source .venv/bin/activate
pydf-tool --help
pydf-tool help
pydf-tool
```

### Compression smoke check

```bash
source .venv/bin/activate
pydf-tool compress "path/to/input.pdf" --level high --output /tmp/pydf-compress-check.pdf
```

### OCR smoke check

```bash
source .venv/bin/activate
pydf-tool ocr "path/to/input.pdf" --lang it --output /tmp/pydf-ocr-check.pdf
```

Note:

- OCR can take a long time on large PDFs
- if testing in a restricted environment, prefer `/tmp` as output target first

## Packaging Notes

- packaging uses `pyproject.toml`
- launcher is `scripts/pydf-tool`
- editable install is important for local usage
- after moving the folder, do not assume the old launcher state is still reliable until reinstall is done

## Documentation Notes

Main docs:

- `README.md`: user-facing install and usage
- `COMPONENTS.md`: dependency inventory
- `REPORT VIBE CODING.md`: longer technical handoff and recent debug history
- `PROJECT_CONTEXT.md`: portable, relocation-safe project context

## Suggested Read Order For Another Agent

1. `PROJECT_CONTEXT.md`
2. `REPORT VIBE CODING.md`
3. `README.md`
4. `pyproject.toml`
5. `src/pdf_tool/cli.py`
6. `src/pdf_tool/tui.py`
7. `src/pdf_tool/ocr.py`
8. `src/pdf_tool/compress.py`
9. `src/pdf_tool/utils.py`
10. `tests/test_cli.py`

## What Another Agent Should Audit First

Highest-value audit targets:

- end-to-end OCR behavior on real PDFs
- TUI robustness and focus management
- editable install / launcher behavior after repo moves
- Ghostscript subprocess strategy and portability
- path normalization strategy on macOS
- consistency between docs, tests, and actual runtime behavior

## Last Verified Snapshot

At the time of this document:

- `30` unit tests passed
- syntax compilation passed
- direct CLI compression on the real user PDF succeeded with output in `/tmp`
- macOS Unicode path handling was covered by tests and direct path resolution checks
- some writes to user folders were not fully verifiable inside the Codex sandbox
