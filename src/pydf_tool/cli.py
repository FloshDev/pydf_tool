from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from .check_ocr import check_ocr
from .compress import compress_pdf
from .errors import PDFToolError
from .ocr import run_ocr
from .utils import format_size_change

APP_DISPLAY_NAME = "PyDF Tool"
APP_COMMAND = "pydf-tool"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=APP_COMMAND,
        description=f"{APP_DISPLAY_NAME}: OCR e compressione PDF per macOS.",
    )
    subparsers = parser.add_subparsers(dest="command")

    ocr_parser = subparsers.add_parser(
        "ocr",
        help="Converte un PDF scansionato in PDF ricercabile o file TXT.",
    )
    ocr_parser.add_argument("input", help="PDF di input.")
    ocr_parser.add_argument(
        "--lang",
        default="it",
        help="Lingua OCR: it, en oppure it+en.",
    )
    ocr_parser.add_argument(
        "--output",
        help=(
            "File di output (.pdf oppure .txt). "
            "Default: stessa cartella dell'input con nome incrementale."
        ),
    )
    ocr_parser.set_defaults(handler=_handle_ocr)

    compress_parser = subparsers.add_parser(
        "compress",
        help="Comprime un PDF e mostra la dimensione prima e dopo.",
    )
    compress_parser.add_argument("input", help="PDF di input.")
    compress_parser.add_argument(
        "--level",
        default="medium",
        help="Livello di compressione: low, medium, high oppure un numero 1-100.",
    )
    compress_parser.add_argument(
        "--output",
        help=(
            "File PDF di output. "
            "Default: stessa cartella dell'input con nome incrementale."
        ),
    )
    compress_parser.add_argument(
        "--grayscale",
        action="store_true",
        help="Converte l'output in bianco e nero per ridurre ulteriormente le dimensioni.",
    )
    compress_parser.set_defaults(handler=_handle_compress)

    check_parser = subparsers.add_parser(
        "check",
        help="Verifica se un PDF contiene già testo ricercabile o necessita di OCR.",
    )
    check_parser.add_argument("input", help="PDF da analizzare.")
    check_parser.set_defaults(handler=_handle_check)

    interactive_parser = subparsers.add_parser(
        "interactive",
        help="Apre la TUI interattiva di PyDF Tool.",
    )
    interactive_parser.set_defaults(handler=_handle_interactive)

    help_parser = subparsers.add_parser(
        "help",
        help="Mostra l'aiuto generale o di un sottocomando.",
    )
    help_parser.add_argument(
        "topic",
        nargs="?",
        choices=("ocr", "compress", "check", "interactive"),
        help="Comando di cui mostrare l'aiuto.",
    )
    help_parser.set_defaults(
        handler=lambda args, parser=parser: _handle_help(args, parser)
    )

    return parser


def _handle_ocr(args: argparse.Namespace) -> int:
    result = run_ocr(
        input_path=Path(args.input),
        output_path=args.output,
        lang=args.lang,
    )
    output_label = "PDF ricercabile" if result.output_type == "pdf" else "file di testo"
    print(
        f"OCR completato: {result.pages} pagine. "
        f"{output_label} generato in {result.output_path}."
    )
    return 0


def _handle_compress(args: argparse.Namespace) -> int:
    result = compress_pdf(
        input_path=Path(args.input),
        output_path=args.output,
        level=args.level,
        grayscale=args.grayscale,
    )
    mode_label = ", bianco e nero" if result.grayscale else ""
    print(
        f"Compressione completata (livello {result.level}{mode_label}): "
        f"{format_size_change(result.size_before, result.size_after)}. "
        f"Output salvato in {result.output_path}."
    )
    if result.size_after > result.size_before:
        print(
            "Nota: il file risultante e piu grande dell'originale. "
            "Prova un livello di compressione piu alto."
        )
    return 0


def _handle_check(args: argparse.Namespace) -> int:
    result = check_ocr(Path(args.input))
    verdetti = {
        "ocr_needed": "OCR necessario — il PDF non contiene testo ricercabile.",
        "already_searchable": "PDF già ricercabile — OCR non necessario.",
        "mixed": (
            f"PDF misto — {result.pages_with_text} pagine con testo, "
            f"{result.pages_without_text} senza."
        ),
    }
    print(f"File: {args.input}")
    print(f"Pagine totali: {result.pages_total}")
    print(f"Pagine con testo: {result.pages_with_text}")
    print(f"Pagine senza testo: {result.pages_without_text}")
    print(f"Media caratteri/pagina: {result.chars_per_page_avg:.0f}")
    print()
    print(f"Verdetto: {verdetti[result.verdict]}")
    return 0


def _handle_interactive(_: argparse.Namespace) -> int:
    return _run_interactive_shell()


def _handle_help(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    topic = getattr(args, "topic", None)
    if topic is None:
        parser.print_help()
        return 0

    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            subparser = action.choices.get(topic)
            if subparser is not None:
                subparser.print_help()
                return 0

    raise PDFToolError(f"Help non disponibile per il comando: {topic}")


def _execute_handler(args: argparse.Namespace) -> int:
    try:
        return args.handler(args)
    except PDFToolError as exc:
        print(f"Errore: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Operazione interrotta.", file=sys.stderr)
        return 130


def _dispatch_interactive_command(command_line: str) -> int:
    from .tui import dispatch_interactive_command

    return dispatch_interactive_command(
        command_line,
        parser_factory=build_parser,
        executor=_execute_handler,
    )


def _run_interactive_shell() -> int:
    from .tui import run_interactive_app

    return run_interactive_app(
        parser_factory=build_parser,
        executor=_execute_handler,
    )


def _run_interactive_shell_safe() -> int:
    try:
        return _run_interactive_shell()
    except PDFToolError as exc:
        print(f"Errore: {exc}", file=sys.stderr)
        return 1
    except (KeyboardInterrupt, EOFError):
        print("Operazione interrotta.", file=sys.stderr)
        return 130


def main(argv: Sequence[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if not arguments:
        return _run_interactive_shell_safe()

    parser = build_parser()
    args = parser.parse_args(arguments)
    if args.command is None:
        return _run_interactive_shell_safe()
    return _execute_handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
