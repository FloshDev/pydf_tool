import asyncio
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

from textual.widgets import Input, ListView, ProgressBar, Static

from pydf_tool.check_ocr import CheckOCRResult, check_ocr
from pydf_tool.cli import _dispatch_interactive_command, _run_interactive_shell, main
from pydf_tool.compress import (
    compress_pdf,
    resolve_compress_output_path,
    resolve_compression_profile,
)
from pydf_tool.errors import PDFToolError
from pydf_tool.ocr import OCRResult, resolve_ocr_output_path, resolve_tesseract_languages
from pydf_tool.ocr import run_ocr
from pydf_tool.preferences import Preferences
from pydf_tool.tui import (
    CheckInputScreen,
    CheckResultScreen,
    HelpScreen,
    HomeScreen,
    MenuEntryItem,
    OCRMenuScreen,
    ProgressScreen,
    PyDFApp,
    WizardScreen,
)
from pydf_tool.utils import ensure_pdf_input, resolve_user_path


class EmitProgressTestCase(unittest.TestCase):
    def test_emit_progress_is_exported_from_progress_module(self) -> None:
        from pydf_tool.progress import emit_progress
        self.assertTrue(callable(emit_progress))

    def test_emit_progress_calls_callback_with_correct_fields(self) -> None:
        from pydf_tool.progress import emit_progress, OperationProgress
        calls: list[OperationProgress] = []
        emit_progress(calls.append, stage="ocr", message="ciao", completed=3, total=10)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].stage, "ocr")
        self.assertEqual(calls[0].message, "ciao")
        self.assertEqual(calls[0].completed, 3)
        self.assertEqual(calls[0].total, 10)

    def test_emit_progress_skips_none_callback(self) -> None:
        from pydf_tool.progress import emit_progress
        emit_progress(None, stage="done", message="ok")  # nessuna eccezione


class CheckOCRTestCase(unittest.TestCase):
    def _make_fake_reader(self, texts_per_page: list[str]):
        class FakePage:
            def __init__(self, text: str) -> None:
                self._text = text

            def extract_text(self) -> str:
                return self._text

        class FakeReader:
            def __init__(self, _source) -> None:
                self.pages = [FakePage(t) for t in texts_per_page]

        return FakeReader

    def test_check_ocr_verdict_ocr_needed(self) -> None:
        FakeReader = self._make_fake_reader(["", "", ""])
        fake_pypdf = types.SimpleNamespace(PdfReader=FakeReader)

        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir, "scan.pdf")
            input_path.write_bytes(b"%PDF-1.4")

            with patch.dict(sys.modules, {"pypdf": fake_pypdf}):
                result = check_ocr(input_path)

        self.assertEqual(result.verdict, "ocr_needed")
        self.assertEqual(result.pages_total, 3)
        self.assertEqual(result.pages_with_text, 0)
        self.assertEqual(result.pages_without_text, 3)

    def test_check_ocr_verdict_already_searchable(self) -> None:
        long_text = "A" * 200
        FakeReader = self._make_fake_reader([long_text, long_text])
        fake_pypdf = types.SimpleNamespace(PdfReader=FakeReader)

        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir, "scan.pdf")
            input_path.write_bytes(b"%PDF-1.4")

            with patch.dict(sys.modules, {"pypdf": fake_pypdf}):
                result = check_ocr(input_path)

        self.assertEqual(result.verdict, "already_searchable")
        self.assertEqual(result.pages_with_text, 2)
        self.assertEqual(result.pages_without_text, 0)

    def test_check_ocr_verdict_mixed(self) -> None:
        long_text = "A" * 200
        FakeReader = self._make_fake_reader([long_text, "", long_text, ""])
        fake_pypdf = types.SimpleNamespace(PdfReader=FakeReader)

        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir, "scan.pdf")
            input_path.write_bytes(b"%PDF-1.4")

            with patch.dict(sys.modules, {"pypdf": fake_pypdf}):
                result = check_ocr(input_path)

        self.assertEqual(result.verdict, "mixed")
        self.assertEqual(result.pages_with_text, 2)
        self.assertEqual(result.pages_without_text, 2)

    def test_check_ocr_chars_per_page_avg(self) -> None:
        FakeReader = self._make_fake_reader(["A" * 100, "A" * 200])
        fake_pypdf = types.SimpleNamespace(PdfReader=FakeReader)

        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir, "scan.pdf")
            input_path.write_bytes(b"%PDF-1.4")

            with patch.dict(sys.modules, {"pypdf": fake_pypdf}):
                result = check_ocr(input_path)

        self.assertAlmostEqual(result.chars_per_page_avg, 150.0)

    def test_main_dispatches_check(self) -> None:
        mock_result = CheckOCRResult(
            pages_total=3,
            pages_with_text=0,
            pages_without_text=3,
            chars_per_page_avg=0.0,
            verdict="ocr_needed",
        )
        stdout = io.StringIO()

        with patch("pydf_tool.cli.check_ocr", return_value=mock_result):
            with redirect_stdout(stdout):
                exit_code = main(["check", "scan.pdf"])

        self.assertEqual(exit_code, 0)
        self.assertIn("OCR necessario", stdout.getvalue())
        self.assertIn("3", stdout.getvalue())


class OCRHelpersTestCase(unittest.TestCase):
    def test_resolve_tesseract_languages_accepts_combined_langs(self) -> None:
        self.assertEqual(resolve_tesseract_languages("it+en"), "ita+eng")

    def test_resolve_tesseract_languages_rejects_unsupported_lang(self) -> None:
        with self.assertRaises(PDFToolError):
            resolve_tesseract_languages("fr")

    def test_resolve_ocr_output_defaults_to_pdf(self) -> None:
        result = resolve_ocr_output_path(Path("scan.pdf"), None)
        self.assertEqual(result, Path("scan.1.pdf"))



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

    def test_ensure_pdf_input_accepts_shell_quoted_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            sample_dir = Path(temp_dir, "PDF Sample")
            sample_dir.mkdir()
            actual_file = sample_dir / "noOCR.pdf"
            actual_file.write_bytes(b"%PDF-1.4")

            resolved_path = ensure_pdf_input(f"'{actual_file}'")

            self.assertTrue(resolved_path.exists())
            self.assertTrue(resolved_path.samefile(actual_file))

    def test_ensure_pdf_input_accepts_shell_escaped_spaces(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            sample_dir = Path(temp_dir, "PDF Sample")
            sample_dir.mkdir()
            actual_file = sample_dir / "noOCR.pdf"
            actual_file.write_bytes(b"%PDF-1.4")

            escaped_path = str(actual_file).replace(" ", "\\ ")
            resolved_path = ensure_pdf_input(escaped_path)

            self.assertTrue(resolved_path.exists())
            self.assertTrue(resolved_path.samefile(actual_file))


class TUIScreenTestCase(unittest.TestCase):
    def _make_app(self) -> PyDFApp:
        return PyDFApp(
            show_startup_checks=False,
            preferences=Preferences.default(),
        )

    def test_home_menu_shows_ocr_compress_and_help(self) -> None:
        async def scenario() -> None:
            app = self._make_app()
            async with app.run_test():
                self.assertEqual(
                    [item.id for item in app.screen.query(MenuEntryItem)],
                    ["ocr-menu", "compress", "help"],
                )
                self.assertEqual(app.focused.id if app.focused else None, "menu-list")

        asyncio.run(scenario())

    def test_ocr_menu_is_a_submenu_with_check_and_ocr_actions(self) -> None:
        async def scenario() -> None:
            app = self._make_app()
            async with app.run_test() as pilot:
                await pilot.press("enter")
                await pilot.pause()

                self.assertIsInstance(app.screen, OCRMenuScreen)
                self.assertEqual(
                    [item.id for item in app.screen.query(MenuEntryItem)],
                    ["check", "ocr"],
                )
                self.assertEqual(app.focused.id if app.focused else None, "menu-list")

        asyncio.run(scenario())

    def test_ocr_menu_uses_compact_submenu_layout(self) -> None:
        async def scenario() -> None:
            app = self._make_app()
            async with app.run_test() as pilot:
                await pilot.press("enter")
                await pilot.pause()

                title = app.screen.query_one("#wizard-title", Static)
                prompt = app.screen.query_one("#step-prompt", Static)
                preview_title = app.screen.query_one("#ocr-preview-title", Static)

                self.assertEqual(title.content, "OCR")
                self.assertIn("Scegli l'azione", prompt.content)
                self.assertEqual(preview_title.content, "Verifica OCR")
                self.assertEqual(len(list(app.screen.query("#header"))), 0)

        asyncio.run(scenario())

    def test_home_menu_scrolls_to_keep_highlighted_item_visible(self) -> None:
        async def scenario() -> None:
            app = self._make_app()
            async with app.run_test(size=(80, 24)) as pilot:
                menu = app.screen.query_one("#menu-list", ListView)

                await pilot.press("down")
                await pilot.pause()
                await pilot.press("down")
                await pilot.pause()

                self.assertEqual(menu.highlighted_child.id if menu.highlighted_child else None, "help")
                self.assertGreater(menu.scroll_y, 0)

        asyncio.run(scenario())

    def test_ocr_wizard_language_step_uses_scroll_selection(self) -> None:
        async def scenario() -> None:
            app = self._make_app()
            async with app.run_test() as pilot:
                wizard = WizardScreen(mode="ocr")
                app.push_screen(wizard)
                await pilot.pause()

                wizard._values["file"] = "/tmp/input.pdf"
                wizard.current_step = 1
                await pilot.pause()

                self.assertEqual(app.focused.id if app.focused else None, "step-choices")

                choice_list = wizard.query_one("#step-choices", ListView)
                self.assertEqual(
                    choice_list.highlighted_child.choice.value if choice_list.highlighted_child else None,
                    "it",
                )

                await pilot.press("down")
                await pilot.pause()
                await pilot.press("enter")
                await pilot.pause()

                self.assertEqual(wizard._values["lingua"], "en")
                self.assertEqual(wizard.current_step, 2)

        asyncio.run(scenario())

    def test_ocr_wizard_format_step_highlights_first_option_immediately(self) -> None:
        async def scenario() -> None:
            app = self._make_app()
            async with app.run_test() as pilot:
                wizard = WizardScreen(mode="ocr", prefill_path="/tmp/input.pdf")
                app.push_screen(wizard)
                await pilot.pause()

                await pilot.press("enter")
                await pilot.pause()

                self.assertEqual(wizard.current_step, 1)
                self.assertEqual(app.focused.id if app.focused else None, "step-choices")

                choice_list = wizard.query_one("#step-choices", ListView)
                self.assertEqual(
                    choice_list.highlighted_child.choice.value if choice_list.highlighted_child else None,
                    "pdf",
                )

                first_item = list(choice_list.query("ListItem"))[0]
                self.assertIn("-highlight", first_item.classes)

        asyncio.run(scenario())

    def test_prefilled_ocr_wizard_skips_file_step(self) -> None:
        async def scenario() -> None:
            app = self._make_app()
            async with app.run_test() as pilot:
                wizard = WizardScreen(mode="ocr", prefill_path="/tmp/input.pdf")
                app.push_screen(wizard)
                await pilot.pause()

                self.assertEqual(wizard._values["file"], "/tmp/input.pdf")
                self.assertEqual([step.name for step in wizard._visible_steps()], ["Lingua", "Formato", "Output"])
                self.assertEqual(app.focused.id if app.focused else None, "step-choices")

        asyncio.run(scenario())

    def test_ocr_output_placeholder_mentions_same_source_folder_and_selected_extension(self) -> None:
        async def scenario() -> None:
            app = self._make_app()
            async with app.run_test() as pilot:
                wizard = WizardScreen(mode="ocr", prefill_path="/tmp/input.pdf")
                app.push_screen(wizard)
                await pilot.pause()

                wizard._values["formato"] = "txt"
                wizard.current_step = 2
                await pilot.pause()

                input_widget = wizard.query_one("#step-input", Input)
                self.assertIn("stessa cartella del file di partenza", input_widget.placeholder)
                self.assertIn("out.txt", input_widget.placeholder)

        asyncio.run(scenario())

    def test_compress_wizard_accepts_custom_numeric_level(self) -> None:
        async def scenario() -> None:
            app = self._make_app()
            async with app.run_test() as pilot:
                wizard = WizardScreen(mode="compress")
                app.push_screen(wizard)
                await pilot.pause()

                wizard._values["file"] = "/tmp/input.pdf"
                wizard.current_step = 1
                await pilot.pause()

                await pilot.press("down")
                await pilot.pause()
                await pilot.press("down")
                await pilot.pause()
                await pilot.press("down")
                await pilot.pause()
                await pilot.press("enter")
                await pilot.pause()

                self.assertEqual(wizard._values["livello"], "custom")
                self.assertEqual(wizard.current_step, 2)
                self.assertEqual(app.focused.id if app.focused else None, "step-input")

                wizard.query_one("#step-input", Input).value = "42"
                await pilot.press("enter")
                await pilot.pause()

                self.assertEqual(wizard._values["grado"], "42")
                self.assertEqual(wizard.current_step, 3)

        asyncio.run(scenario())

    def test_compress_output_placeholder_mentions_same_source_folder(self) -> None:
        async def scenario() -> None:
            app = self._make_app()
            async with app.run_test() as pilot:
                wizard = WizardScreen(mode="compress")
                app.push_screen(wizard)
                await pilot.pause()

                wizard._values["file"] = "/tmp/input.pdf"
                wizard._values["livello"] = "medium"
                wizard._values["colore"] = "color"
                wizard.current_step = 3
                await pilot.pause()

                input_widget = wizard.query_one("#step-input", Input)
                self.assertIn("stessa cartella del file di partenza", input_widget.placeholder)
                self.assertIn("out.pdf", input_widget.placeholder)

        asyncio.run(scenario())

    def test_check_result_buttons_support_arrow_navigation(self) -> None:
        async def scenario() -> None:
            app = self._make_app()
            async with app.run_test() as pilot:
                app.push_screen(
                    CheckResultScreen(
                        result=CheckOCRResult(
                            pages_total=1,
                            pages_with_text=0,
                            pages_without_text=1,
                            chars_per_page_avg=0.0,
                            verdict="ocr_needed",
                        ),
                        input_path=Path("scan.pdf"),
                    )
                )
                await pilot.pause()

                self.assertEqual(app.focused.id if app.focused else None, "btn-run-ocr")

                await pilot.press("down")
                await pilot.pause()
                self.assertEqual(app.focused.id if app.focused else None, "btn-home")

                await pilot.press("up")
                await pilot.pause()
                self.assertEqual(app.focused.id if app.focused else None, "btn-run-ocr")

                await pilot.press("right")
                await pilot.pause()
                self.assertEqual(app.focused.id if app.focused else None, "btn-home")

                await pilot.press("left")
                await pilot.pause()
                self.assertEqual(app.focused.id if app.focused else None, "btn-run-ocr")

        asyncio.run(scenario())

    def test_check_result_home_button_focus_does_not_use_reverse_style(self) -> None:
        async def scenario() -> None:
            app = self._make_app()
            async with app.run_test() as pilot:
                app.push_screen(
                    CheckResultScreen(
                        result=CheckOCRResult(
                            pages_total=1,
                            pages_with_text=0,
                            pages_without_text=1,
                            chars_per_page_avg=0.0,
                            verdict="ocr_needed",
                        ),
                        input_path=Path("scan.pdf"),
                    )
                )
                await pilot.pause()

                await pilot.press("down")
                await pilot.pause()

                button = app.screen.query_one("#btn-home")
                self.assertFalse(button.styles.text_style.reverse)
                self.assertEqual(button.styles.background_tint.a, 0)

        asyncio.run(scenario())

    def test_progress_result_enter_returns_to_home_screen(self) -> None:
        async def scenario() -> None:
            app = self._make_app()
            async with app.run_test() as pilot:
                wizard = WizardScreen(mode="compress")
                app.push_screen(wizard)
                await pilot.pause()

                wizard._values = {
                    "file": "/tmp/input.pdf",
                    "livello": "medium",
                    "colore": "color",
                }
                wizard.current_step = 3
                await pilot.pause()
                wizard.query_one("#step-input", Input).value = "/tmp/output.pdf"

                progress = ProgressScreen(
                    mode="compress",
                    args={
                        "input": Path("/tmp/input.pdf"),
                        "level": "medium",
                        "grayscale": False,
                        "output": Path("/tmp/output.pdf"),
                    },
                )
                progress._run_operation = lambda: None  # type: ignore[method-assign]
                app.push_screen(progress)
                await pilot.pause()

                progress._show_result("Compressione completata", success=True)
                await pilot.pause()

                await pilot.press("enter")
                await pilot.pause()

                self.assertIsInstance(app.screen, HomeScreen)
                self.assertEqual(len(app.screen_stack), 2)

        asyncio.run(scenario())

    def test_progress_screen_footer_shows_cancel_hint_on_mount(self) -> None:
        async def scenario() -> None:
            app = self._make_app()
            async with app.run_test() as pilot:
                progress = ProgressScreen(
                    mode="compress",
                    args={
                        "input": Path("/tmp/input.pdf"),
                        "level": "medium",
                        "grayscale": False,
                        "output": Path("/tmp/output.pdf"),
                    },
                )
                progress._run_operation = lambda: None  # type: ignore[method-assign]
                app.push_screen(progress)
                await pilot.pause()

                footer = progress.query_one("#footer-bar", Static)
                self.assertIn("Ctrl+C", footer.content)
                self.assertEqual(len(list(progress.query("#cancel-hint"))), 0)

                bar = progress.query_one("#progress-bar", ProgressBar)
                self.assertGreater(bar.size.width, 50)
                inner_bar = progress.query_one("#bar")
                self.assertGreater(inner_bar.size.width, 50)

        asyncio.run(scenario())

    def test_wizard_screen_h_opens_help(self) -> None:
        async def scenario() -> None:
            app = self._make_app()
            async with app.run_test() as pilot:
                # prefill_path skips the File step (Input) so the first step
                # rendered is Lingua (ListView), which doesn't consume 'h'
                wizard = WizardScreen(mode="ocr", prefill_path="/tmp/input.pdf")
                app.push_screen(wizard)
                await pilot.pause()

                await pilot.press("h")
                await pilot.pause()

                self.assertIsInstance(app.screen, HelpScreen)

        asyncio.run(scenario())

    def test_wizard_back_navigation_clamps_step_index(self) -> None:
        async def scenario() -> None:
            app = self._make_app()
            async with app.run_test() as pilot:
                wizard = WizardScreen(mode="compress")
                app.push_screen(wizard)
                await pilot.pause()

                wizard._values["file"] = "/tmp/input.pdf"
                wizard._values["livello"] = "custom"
                wizard.current_step = 2
                await pilot.pause()

                await pilot.press("escape")
                await pilot.pause()
                self.assertEqual(wizard.current_step, 1)

                wizard._values["livello"] = "low"
                wizard._values.pop("grado", None)
                await pilot.press("escape")
                await pilot.pause()
                self.assertEqual(wizard.current_step, 0)

        asyncio.run(scenario())

    def test_help_screen_has_separate_footer_widget(self) -> None:
        async def scenario() -> None:
            app = self._make_app()
            async with app.run_test() as pilot:
                app.push_screen(HelpScreen())
                await pilot.pause()

                footer = app.screen.query_one("#footer-bar", Static)
                self.assertIn("Esc", footer.content)

        asyncio.run(scenario())

    def test_launch_ocr_from_check_result_removes_ocr_menu_from_stack(self) -> None:
        async def scenario() -> None:
            app = self._make_app()
            async with app.run_test() as pilot:
                app.push_screen(OCRMenuScreen())
                await pilot.pause()
                app.push_screen(CheckInputScreen())
                await pilot.pause()

                result_screen = CheckResultScreen(
                    result=CheckOCRResult(
                        pages_total=1,
                        pages_with_text=0,
                        pages_without_text=1,
                        chars_per_page_avg=0.0,
                        verdict="ocr_needed",
                    ),
                    input_path=Path("/tmp/scan.pdf"),
                )
                app.push_screen(result_screen)
                await pilot.pause()

                self.assertEqual(len(app.screen_stack), 5)

                result_screen._launch_ocr()
                await pilot.pause()

                self.assertEqual(len(app.screen_stack), 3)
                self.assertIsInstance(app.screen, WizardScreen)

        asyncio.run(scenario())


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

            with patch("pydf_tool.compress.shutil.which", return_value="/usr/local/bin/gs"):
                with patch("pydf_tool.compress.subprocess.run", side_effect=fake_run):
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

            with patch("pydf_tool.compress.shutil.which", return_value="/usr/local/bin/gs"):
                with patch("pydf_tool.compress.subprocess.run", side_effect=fake_run):
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
                with patch("pydf_tool.compress.shutil.which", return_value="/usr/local/bin/gs"):
                    with patch("pydf_tool.compress.subprocess.Popen", FakePopen):
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

            with patch("pydf_tool.compress.shutil.which", return_value="/usr/local/bin/gs"):
                with patch("pydf_tool.compress.subprocess.run", side_effect=fake_run):
                    result = compress_pdf(input_path, output_path, level="medium")

            self.assertEqual(result.output_path, output_path)
            self.assertTrue(result.output_path.exists())
            self.assertTrue(result.output_path.samefile(output_path))
            positional_args = [p for p in captured["command"] if not p.startswith("-")]
            source_arg = positional_args[-1]  # last positional is the source file
            self.assertIn("input.pdf", source_arg)
            self.assertNotEqual(source_arg, str(input_path))


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
                    "pydf_tool.ocr.shutil.which",
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
            convert_from_path=lambda path, dpi, use_pdftocairo, first_page=None, last_page=None: ["image-1"]
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
                    "pydf_tool.ocr.shutil.which",
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
                    "pydf_tool.ocr.shutil.which",
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
        with patch("pydf_tool.cli._run_interactive_shell", return_value=0) as mock_shell:
            exit_code = main([])

        self.assertEqual(exit_code, 0)
        mock_shell.assert_called_once_with()

    def test_main_interactive_subcommand_starts_shell(self) -> None:
        with patch("pydf_tool.cli._run_interactive_shell", return_value=0) as mock_shell:
            exit_code = main(["interactive"])

        self.assertEqual(exit_code, 0)
        mock_shell.assert_called_once_with()

    @patch("pydf_tool.cli.run_ocr")
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

    @patch("pydf_tool.cli.compress_pdf")
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
        with patch("pydf_tool.cli.run_ocr", side_effect=PDFToolError("boom")):
            with redirect_stderr(stderr):
                exit_code = main(["ocr", "scan.pdf"])

        self.assertEqual(exit_code, 1)
        self.assertIn("Errore: boom", stderr.getvalue())

    def test_main_supports_help_subcommand(self) -> None:
        stdout = io.StringIO()

        with redirect_stdout(stdout):
            exit_code = main(["help"])

        self.assertEqual(exit_code, 0)
        self.assertIn("{ocr,compress,check,interactive,help}", stdout.getvalue())

    def test_main_supports_help_for_specific_subcommand(self) -> None:
        stdout = io.StringIO()

        with redirect_stdout(stdout):
            exit_code = main(["help", "ocr"])

        self.assertEqual(exit_code, 0)
        self.assertIn("--lang", stdout.getvalue())
        self.assertIn("--output", stdout.getvalue())

    @patch("pydf_tool.cli.run_ocr")
    def test_dispatch_interactive_command_supports_direct_ocr_command(
        self,
        mock_run_ocr,
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
            input_path=Path("scan.pdf"),
            output_path="out.pdf",
            lang="it",
        )

    @patch("pydf_tool.tui.PyDFApp.run")
    def test_interactive_shell_runs_app(self, mock_run) -> None:
        mock_run.return_value = None
        exit_code = _run_interactive_shell()
        mock_run.assert_called_once()
        self.assertEqual(exit_code, 0)

    def test_dispatch_interactive_command_supports_help(self) -> None:
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            exit_code = _dispatch_interactive_command("help")
        self.assertEqual(exit_code, 0)
        self.assertIn("pydf-tool", stdout.getvalue())

    def test_dispatch_interactive_command_supports_command_help(self) -> None:
        stdout = io.StringIO()

        with redirect_stdout(stdout):
            exit_code = _dispatch_interactive_command("help compress")

        self.assertEqual(exit_code, 0)
        self.assertIn("--level", stdout.getvalue())

    def test_pyproject_configures_entry_point(self) -> None:
        import tomllib

        with Path("pyproject.toml").open("rb") as file_obj:
            pyproject = tomllib.load(file_obj)

        scripts = pyproject["project"]["scripts"]
        self.assertEqual(scripts["pydf-tool"], "pydf_tool.cli:main")

    def test_entry_point_target_is_callable(self) -> None:
        from pydf_tool.cli import main

        self.assertTrue(callable(main))


if __name__ == "__main__":
    unittest.main()
