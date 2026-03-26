import argparse
import io
import os
import sys
import tempfile
import types
import unicodedata
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from pdf_tool.cli import _dispatch_interactive_command, _run_interactive_shell, main
from pdf_tool.compress import (
    compress_pdf,
    resolve_compress_output_path,
    resolve_compression_profile,
)
from pdf_tool.errors import PDFToolError
from pdf_tool.ocr import OCRResult, resolve_ocr_output_path, resolve_tesseract_languages
from pdf_tool.ocr import run_ocr
from pdf_tool.tui import _dialog_width, _wrap_dialog_text
from pdf_tool.utils import ensure_pdf_input, resolve_user_path


class OCRHelpersTestCase(unittest.TestCase):
    def test_resolve_tesseract_languages_accepts_combined_langs(self) -> None:
        self.assertEqual(resolve_tesseract_languages("it+en"), "ita+eng")

    def test_resolve_tesseract_languages_rejects_unsupported_lang(self) -> None:
        with self.assertRaises(PDFToolError):
            resolve_tesseract_languages("fr")

    def test_resolve_ocr_output_defaults_to_pdf(self) -> None:
        result = resolve_ocr_output_path(Path("scan.pdf"), None)
        self.assertEqual(result, Path("scan.1.pdf"))


class TUIHelpersTestCase(unittest.TestCase):
    @patch("pdf_tool.tui.get_terminal_size", return_value=os.terminal_size((60, 24)))
    def test_dialog_width_shrinks_with_terminal(self, _mock_terminal_size) -> None:
        self.assertEqual(_dialog_width(72, minimum=44, margin=6), 54)

    def test_wrap_dialog_text_wraps_bullets_with_indentation(self) -> None:
        wrapped = _wrap_dialog_text(
            ["- Compressione custom: scegli custom e inserisci un valore 1-100"],
            width=24,
        )

        self.assertIn("- Compressione custom:", wrapped)
        self.assertIn("\n  scegli custom", wrapped)


class PathNormalizationTestCase(unittest.TestCase):
    def test_ensure_pdf_input_accepts_unicode_normalization_variants(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            actual_dir = Path(temp_dir, unicodedata.normalize("NFD", "Università"))
            actual_dir.mkdir()
            actual_file = actual_dir / "slide.pdf"
            actual_file.write_bytes(b"%PDF-1.4")

            requested_path = Path(
                temp_dir,
                unicodedata.normalize("NFC", "Università"),
                "slide.pdf",
            )

            resolved_path = ensure_pdf_input(requested_path)

            self.assertTrue(resolved_path.exists())
            self.assertTrue(resolved_path.samefile(actual_file))

    def test_resolve_user_path_normalizes_existing_parent(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            actual_dir = Path(temp_dir, unicodedata.normalize("NFD", "Università"))
            actual_dir.mkdir()

            requested_path = Path(
                temp_dir,
                unicodedata.normalize("NFC", "Università"),
                "out.pdf",
            )
            resolved_path = resolve_user_path(requested_path)

            self.assertTrue(resolved_path.parent.exists())
            self.assertTrue(resolved_path.parent.samefile(actual_dir))
            self.assertEqual(resolved_path.name, "out.pdf")


class CompressionHelpersTestCase(unittest.TestCase):
    def test_resolve_compression_profile_supports_numeric_level(self) -> None:
        low_strength = resolve_compression_profile("10")
        high_strength = resolve_compression_profile("90")
        self.assertLess(high_strength.dpi, low_strength.dpi)

    def test_resolve_compress_output_adds_pdf_suffix(self) -> None:
        result = resolve_compress_output_path(Path("file.pdf"), "out")
        self.assertEqual(result, Path("out.pdf"))

    def test_resolve_compress_output_defaults_to_incremental_pdf(self) -> None:
        result = resolve_compress_output_path(Path("file.pdf"), None)
        self.assertEqual(result, Path("file.1.pdf"))

    def test_compress_pdf_builds_ghostscript_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir, "input.pdf")
            output_path = Path(temp_dir, "output.pdf")
            input_path.write_bytes(b"original-pdf")
            captured: dict[str, list[str]] = {}

            def fake_run(command, check, capture_output, text):
                captured["command"] = command
                staged_output = Path(
                    next(
                        part.split("=", 1)[1]
                        for part in command
                        if part.startswith("-sOutputFile=")
                    )
                )
                staged_output.write_bytes(b"small")
                return None

            with patch("pdf_tool.compress.shutil.which", return_value="/usr/local/bin/gs"):
                with patch("pdf_tool.compress.subprocess.run", side_effect=fake_run):
                    result = compress_pdf(input_path, output_path, level="high")

        self.assertEqual(result.output_path, output_path)
        self.assertFalse(result.grayscale)
        self.assertIn("-dPDFSETTINGS=/screen", captured["command"])
        staged_output_arg = next(
            part for part in captured["command"] if part.startswith("-sOutputFile=")
        )
        self.assertNotEqual(staged_output_arg, f"-sOutputFile={output_path}")

    def test_compress_pdf_adds_grayscale_flags(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir, "input.pdf")
            output_path = Path(temp_dir, "output.pdf")
            input_path.write_bytes(b"original-pdf")
            captured: dict[str, list[str]] = {}

            def fake_run(command, check, capture_output, text):
                captured["command"] = command
                staged_output = Path(
                    next(
                        part.split("=", 1)[1]
                        for part in command
                        if part.startswith("-sOutputFile=")
                    )
                )
                staged_output.write_bytes(b"small")
                return None

            with patch("pdf_tool.compress.shutil.which", return_value="/usr/local/bin/gs"):
                with patch("pdf_tool.compress.subprocess.run", side_effect=fake_run):
                    result = compress_pdf(
                        input_path,
                        output_path,
                        level="medium",
                        grayscale=True,
                    )

        self.assertTrue(result.grayscale)
        self.assertIn("-sColorConversionStrategy=Gray", captured["command"])
        self.assertIn("-dProcessColorModel=/DeviceGray", captured["command"])

    def test_compress_pdf_emits_progress_updates(self) -> None:
        class FakePdfReader:
            def __init__(self, _source) -> None:
                self.pages = [object(), object()]

        class FakePopen:
            def __init__(self, command, stdout, stderr, text) -> None:
                self.command = command
                self.stdout = io.StringIO("Page 1\nPage 2\n")
                output_arg = next(
                    part for part in command if part.startswith("-sOutputFile=")
                )
                output_path = Path(output_arg.split("=", 1)[1])
                output_path.write_bytes(b"compressed")
                self._returncode = 0

            def wait(self, timeout=None):
                return self._returncode

            def poll(self):
                return self._returncode

            def terminate(self):
                self._returncode = -15

            def kill(self):
                self._returncode = -9

        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir, "input.pdf")
            output_path = Path(temp_dir, "output.pdf")
            input_path.write_bytes(b"original-pdf")
            updates = []

            fake_pypdf = types.SimpleNamespace(PdfReader=FakePdfReader)

            with patch.dict(sys.modules, {"pypdf": fake_pypdf}):
                with patch("pdf_tool.compress.shutil.which", return_value="/usr/local/bin/gs"):
                    with patch("pdf_tool.compress.subprocess.Popen", FakePopen):
                        result = compress_pdf(
                            input_path,
                            output_path,
                            level="high",
                            progress_callback=updates.append,
                        )

        self.assertEqual(result.output_path, output_path)
        self.assertTrue(any(update.stage == "compress" for update in updates))
        self.assertTrue(any(update.completed == 2 for update in updates))

    def test_compress_pdf_uses_staged_paths_for_unicode_locations(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            unicode_dir = Path(temp_dir, unicodedata.normalize("NFD", "Università"))
            unicode_dir.mkdir()
            input_path = unicode_dir / "input.pdf"
            output_path = unicode_dir / "output.pdf"
            input_path.write_bytes(b"original-pdf")
            captured: dict[str, list[str]] = {}

            def fake_run(command, check, capture_output, text):
                captured["command"] = command
                staged_output = Path(
                    next(
                        part.split("=", 1)[1]
                        for part in command
                        if part.startswith("-sOutputFile=")
                    )
                )
                staged_output.write_bytes(b"small")
                return None

            with patch("pdf_tool.compress.shutil.which", return_value="/usr/local/bin/gs"):
                with patch("pdf_tool.compress.subprocess.run", side_effect=fake_run):
                    result = compress_pdf(input_path, output_path, level="medium")

            self.assertEqual(result.output_path, output_path)
            self.assertTrue(result.output_path.exists())
            self.assertTrue(result.output_path.samefile(output_path))
            self.assertIn("input.pdf", captured["command"][-1])
            self.assertNotEqual(captured["command"][-1], str(input_path))


class OCRRuntimeTestCase(unittest.TestCase):
    def test_run_ocr_uses_pdftoppm_when_pdftocairo_missing(self) -> None:
        fake_pytesseract = types.SimpleNamespace(
            get_languages=lambda config="": ["ita"],
            image_to_string=lambda image, lang="": "ciao",
        )

        convert_calls: dict[str, object] = {}

        def fake_convert_from_path(path, dpi, use_pdftocairo):
            convert_calls["path"] = path
            convert_calls["dpi"] = dpi
            convert_calls["use_pdftocairo"] = use_pdftocairo
            return ["image-1"]

        fake_pdf2image = types.SimpleNamespace(convert_from_path=fake_convert_from_path)
        fake_pypdf = types.SimpleNamespace(PdfReader=object, PdfWriter=object)

        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir, "scan.pdf")
            output_path = Path(temp_dir, "scan.txt")
            input_path.write_bytes(b"%PDF-1.4")

            with patch.dict(
                sys.modules,
                {
                    "pytesseract": fake_pytesseract,
                    "pdf2image": fake_pdf2image,
                    "pypdf": fake_pypdf,
                },
            ):
                with patch(
                    "pdf_tool.ocr.shutil.which",
                    side_effect=lambda name: {
                        "tesseract": "/usr/local/bin/tesseract",
                        "pdftoppm": "/usr/local/bin/pdftoppm",
                        "pdftocairo": None,
                    }.get(name),
                ):
                    result = run_ocr(input_path, output_path=output_path, lang="it")

        self.assertEqual(result.output_type, "txt")
        self.assertFalse(convert_calls["use_pdftocairo"])

    def test_run_ocr_emits_progress_updates(self) -> None:
        class FakePdfReader:
            def __init__(self, _source) -> None:
                self.pages = [object(), object()]

        fake_pytesseract = types.SimpleNamespace(
            get_languages=lambda config="": ["ita"],
            image_to_string=lambda image, lang="": "ciao",
        )
        fake_pdf2image = types.SimpleNamespace(
            convert_from_path=lambda path, dpi, use_pdftocairo: ["image-1", "image-2"]
        )
        fake_pypdf = types.SimpleNamespace(PdfReader=FakePdfReader, PdfWriter=object)
        updates = []

        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir, "scan.pdf")
            output_path = Path(temp_dir, "scan.txt")
            input_path.write_bytes(b"%PDF-1.4")

            with patch.dict(
                sys.modules,
                {
                    "pytesseract": fake_pytesseract,
                    "pdf2image": fake_pdf2image,
                    "pypdf": fake_pypdf,
                },
            ):
                with patch(
                    "pdf_tool.ocr.shutil.which",
                    side_effect=lambda name: {
                        "tesseract": "/usr/local/bin/tesseract",
                        "pdftoppm": "/usr/local/bin/pdftoppm",
                        "pdftocairo": None,
                    }.get(name),
                ):
                    result = run_ocr(
                        input_path,
                        output_path=output_path,
                        lang="it",
                        progress_callback=updates.append,
                    )

        self.assertEqual(result.output_type, "txt")
        self.assertTrue(any(update.stage == "ocr" for update in updates))
        self.assertTrue(any(update.completed == 2 for update in updates))

    def test_run_ocr_wraps_runtime_errors(self) -> None:
        fake_pytesseract = types.SimpleNamespace(
            get_languages=lambda config="": ["ita"],
            image_to_string=lambda image, lang="": (_ for _ in ()).throw(
                RuntimeError("ocr boom")
            ),
        )
        fake_pdf2image = types.SimpleNamespace(
            convert_from_path=lambda path, dpi, use_pdftocairo: ["image-1"]
        )
        fake_pypdf = types.SimpleNamespace(PdfReader=object, PdfWriter=object)

        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir, "scan.pdf")
            output_path = Path(temp_dir, "scan.txt")
            input_path.write_bytes(b"%PDF-1.4")

            with patch.dict(
                sys.modules,
                {
                    "pytesseract": fake_pytesseract,
                    "pdf2image": fake_pdf2image,
                    "pypdf": fake_pypdf,
                },
            ):
                with patch(
                    "pdf_tool.ocr.shutil.which",
                    side_effect=lambda name: {
                        "tesseract": "/usr/local/bin/tesseract",
                        "pdftoppm": "/usr/local/bin/pdftoppm",
                        "pdftocairo": None,
                    }.get(name),
                ):
                    with self.assertRaises(PDFToolError):
                        run_ocr(input_path, output_path=output_path, lang="it")


class CLITestCase(unittest.TestCase):
    def test_main_without_args_starts_interactive_mode(self) -> None:
        with patch("pdf_tool.cli._run_interactive_shell", return_value=0) as mock_shell:
            exit_code = main([])

        self.assertEqual(exit_code, 0)
        mock_shell.assert_called_once_with()

    def test_main_interactive_subcommand_starts_shell(self) -> None:
        with patch("pdf_tool.cli._run_interactive_shell", return_value=0) as mock_shell:
            exit_code = main(["interactive"])

        self.assertEqual(exit_code, 0)
        mock_shell.assert_called_once_with()

    @patch("pdf_tool.cli.run_ocr")
    def test_main_dispatches_ocr(self, mock_run_ocr) -> None:
        mock_run_ocr.return_value = OCRResult(
            output_path=Path("scan.1.pdf"),
            pages=2,
            output_type="pdf",
        )
        stdout = io.StringIO()

        with redirect_stdout(stdout):
            exit_code = main(["ocr", "scan.pdf", "--lang", "it"])

        self.assertEqual(exit_code, 0)
        mock_run_ocr.assert_called_once_with(
            input_path=Path("scan.pdf"),
            output_path=None,
            lang="it",
        )
        self.assertIn("OCR completato", stdout.getvalue())

    @patch("pdf_tool.cli.compress_pdf")
    def test_main_dispatches_compress(self, mock_compress_pdf) -> None:
        mock_compress_pdf.return_value = type(
            "CompressionStub",
            (),
            {
                "output_path": Path("doc.1.pdf"),
                "level": "medium",
                "grayscale": False,
                "size_before": 1_000_000,
                "size_after": 500_000,
            },
        )()
        stdout = io.StringIO()

        with redirect_stdout(stdout):
            exit_code = main(["compress", "doc.pdf", "--level", "medium"])

        self.assertEqual(exit_code, 0)
        mock_compress_pdf.assert_called_once_with(
            input_path=Path("doc.pdf"),
            output_path=None,
            level="medium",
            grayscale=False,
        )
        self.assertIn("Compressione completata", stdout.getvalue())

    def test_main_returns_error_code_for_pdf_tool_error(self) -> None:
        stderr = io.StringIO()
        with patch("pdf_tool.cli.run_ocr", side_effect=PDFToolError("boom")):
            with redirect_stderr(stderr):
                exit_code = main(["ocr", "scan.pdf"])

        self.assertEqual(exit_code, 1)
        self.assertIn("Errore: boom", stderr.getvalue())

    def test_main_supports_help_subcommand(self) -> None:
        stdout = io.StringIO()

        with redirect_stdout(stdout):
            exit_code = main(["help"])

        self.assertEqual(exit_code, 0)
        self.assertIn("{ocr,compress,interactive,help}", stdout.getvalue())

    def test_main_supports_help_for_specific_subcommand(self) -> None:
        stdout = io.StringIO()

        with redirect_stdout(stdout):
            exit_code = main(["help", "ocr"])

        self.assertEqual(exit_code, 0)
        self.assertIn("--lang", stdout.getvalue())
        self.assertIn("--output", stdout.getvalue())

    @patch("pdf_tool.tui._run_with_progress", side_effect=lambda title, runner: runner(lambda update: None))
    @patch("pdf_tool.tui.run_ocr")
    def test_dispatch_interactive_command_supports_direct_ocr_command(
        self,
        mock_run_ocr,
        _mock_progress,
    ) -> None:
        mock_run_ocr.return_value = OCRResult(
            output_path=Path("scan.1.pdf"),
            pages=2,
            output_type="pdf",
        )
        stdout = io.StringIO()

        with redirect_stdout(stdout):
            exit_code = _dispatch_interactive_command(
                'ocr "scan.pdf" --lang it --output "out.pdf"'
            )

        self.assertEqual(exit_code, 0)
        mock_run_ocr.assert_called_once_with(
            input_path="scan.pdf",
            output_path="out.pdf",
            lang="it",
            progress_callback=unittest.mock.ANY,
        )

    @patch("pdf_tool.tui._show_home_menu", side_effect=["ocr", "exit"])
    @patch("pdf_tool.tui._prompt_ocr_args", return_value=argparse.Namespace(input="scan.pdf", lang="it", output=None))
    @patch("pdf_tool.tui._run_ocr_interactive", return_value=0)
    def test_interactive_shell_runs_guided_ocr_flow(
        self,
        mock_run_ocr_interactive,
        _mock_prompt_ocr_args,
        _mock_show_home_menu,
    ) -> None:
        exit_code = _run_interactive_shell()
        self.assertEqual(exit_code, 0)
        mock_run_ocr_interactive.assert_called_once()

    @patch("pdf_tool.tui._show_help_screen")
    def test_dispatch_interactive_command_supports_help(self, mock_help) -> None:
        exit_code = _dispatch_interactive_command("help")
        self.assertEqual(exit_code, 0)
        mock_help.assert_called_once()

    def test_dispatch_interactive_command_supports_command_help(self) -> None:
        stdout = io.StringIO()

        with redirect_stdout(stdout):
            exit_code = _dispatch_interactive_command("help compress")

        self.assertEqual(exit_code, 0)
        self.assertIn("--level", stdout.getvalue())

    def test_pyproject_configures_script_file(self) -> None:
        import tomllib

        with Path("pyproject.toml").open("rb") as file_obj:
            pyproject = tomllib.load(file_obj)

        script_files = pyproject["tool"]["setuptools"]["script-files"]
        self.assertEqual(script_files, ["scripts/pydf-tool"])

    def test_bootstrap_script_uses_shell_wrapper(self) -> None:
        content = Path("scripts/pydf-tool").read_text(encoding="utf-8")
        self.assertTrue(content.startswith("#!/bin/sh"))
        self.assertIn('PDF_TOOL_BOOTSTRAP_SCRIPT="$0"', content)
        self.assertIn('metadata.distribution("pydf-tool")', content)
        self.assertIn('"$SCRIPT_DIR/python3" -c', content)
        self.assertNotIn('<<\'PY\'', content)


if __name__ == "__main__":
    unittest.main()
