# PyDF Tool

[![Release](https://img.shields.io/github/v/release/FloshDev/pydf_tool)](https://github.com/FloshDev/pydf_tool/releases)
[![Platform](https://img.shields.io/badge/platform-macOS-lightgrey)](https://github.com/FloshDev/pydf_tool)
[![License](https://img.shields.io/github/license/FloshDev/pydf_tool)](https://github.com/FloshDev/pydf_tool/blob/main/LICENSE)

> A standalone macOS app for checking, OCR-ing, and compressing PDF files — no Python installation required.

PyDF Tool handles three common PDF tasks: detecting whether a scanned PDF already contains searchable text, running OCR on scans to produce a searchable PDF or plain text, and compressing heavy PDFs with preset or custom quality levels. It ships as a self-contained `.app` bundle (Python embedded) and can be driven either through an interactive terminal UI or directly from the command line.

## Installation

### Prerequisites

[Homebrew](https://brew.sh) must be installed, then:

```bash
brew install tesseract tesseract-lang poppler ghostscript
```

| Tool | Purpose |
|---|---|
| `tesseract` | OCR engine used to extract text from scanned pages |
| `tesseract-lang` | Language data packs for Tesseract (includes Italian, English, and more) |
| `poppler` | PDF-to-image renderer (`pdftocairo`/`pdftoppm`) used before OCR |
| `ghostscript` | PDF compression backend (`gs`) |

No Python.org, `pip`, or virtual environment setup needed — the app bundles its own interpreter.

### Download

1. Download `PyDF-Tool-v1.0.1.dmg` from [Releases](https://github.com/FloshDev/pydf_tool/releases)
2. Open the DMG, drag **PyDF Tool** into the **Applications** folder using the included shortcut
3. First launch: macOS Gatekeeper will warn about an unidentified developer — right-click the app → **Open** (required once only)

## Usage

### Interactive TUI

Launch from the Finder by opening **PyDF Tool.app**, or from any terminal:

```bash
pydf-tool
```

<!-- screenshot -->

The TUI checks prerequisites on startup and reports any missing tools immediately. The default output location is the same folder as the input file; the app remembers the last used folder, preferred OCR language, and preferred compression level across sessions.

Key controls:

| Key | Action |
|---|---|
| `↑` / `↓` | Navigate options |
| `Enter` | Confirm |
| `F2` | Open a Finder dialog (file or folder picker, when supported) |
| `Esc` | Go back or dismiss a dialog |
| `H` or `F1` | Open inline help (on screens that support it) |
| `Ctrl+C` | Abort a running operation |

The **OCR** menu entry expands into two sub-actions: **Check OCR** (detect existing text) and **Run OCR** (perform OCR). After each operation you can open the output file or its containing folder directly from the result screen.

### CLI

```bash
# Check whether a PDF already contains searchable text
pydf-tool check document.pdf

# OCR a scanned PDF — output as searchable PDF
pydf-tool ocr scan.pdf --lang it --output output.pdf

# OCR with multiple languages, output as plain text
pydf-tool ocr scan.pdf --lang it+en --output scan.txt

# Compress with a named preset
pydf-tool compress document.pdf --level medium --output output.pdf

# Compress with a custom quality level (0–100)
pydf-tool compress document.pdf --level 65 --output document-small.pdf

# Compress and convert to grayscale
pydf-tool compress document.pdf --level medium --grayscale

# Open the interactive TUI explicitly
pydf-tool interactive

# Show general help or help for a subcommand
pydf-tool help
pydf-tool help ocr
```

If `--output` is omitted, the output file is created in the same folder as the input with an auto-incremented name.

## Features

| Command | Description |
|---|---|
| `check` | Detect whether a PDF already contains searchable text or needs OCR |
| `ocr` | Convert a scanned PDF to a searchable PDF or plain-text file |
| `compress` | Reduce PDF file size using a named preset or a custom quality level |
| `interactive` | Explicitly launch the interactive TUI |
| `help` | Show general help or detailed help for a subcommand |

## Troubleshooting

**macOS shows "unidentified developer" warning**
Right-click the app → **Open**. This is required only on the first launch.

**`tesseract`, `pdftocairo`/`pdftoppm`, or `gs` not found**
Install or reinstall the system dependencies via Homebrew (see [Prerequisites](#prerequisites)).

**The TUI reports missing prerequisites**
The app runs a prerequisite check at startup and blocks OCR or compression if a required external tool is absent.

**The PDF is not recognized by OCR**
Run `pydf-tool check document.pdf` first. Password-protected or heavily corrupted files may cause OCR to fail.

**Compression does not reduce the file size significantly**
If the PDF is already highly compressed or contains only vector text, further size reduction is limited.

## Development

```bash
git clone https://github.com/FloshDev/pydf_tool
cd pydf_tool
pip install -e ".[dev]"
pytest tests/
```

To build the standalone `.app` bundle and DMG:

```bash
scripts/build_macos_app.sh
```

The script produces a `.dmg` in `dist/` with an Applications symlink for drag-to-install. Any previous DMG for the same version is removed before building.

## License

This project is licensed under the terms found in the [LICENSE](LICENSE) file.
