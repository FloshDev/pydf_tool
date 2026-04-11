import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pydf_tool.errors import PDFToolError
from pydf_tool.macos_integration import (
    choose_pdf_file,
    open_output_folder,
    open_with_default_app,
    reveal_in_finder,
)


class MacOSIntegrationTestCase(unittest.TestCase):
    def test_choose_pdf_file_returns_selected_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            default_directory = Path(temp_dir, "Inbox")
            default_directory.mkdir()
            input_reference = default_directory / "seed.pdf"
            input_reference.write_bytes(b"%PDF-1.4")
            selected_path = Path(temp_dir, "selected.pdf")

            captured: dict[str, list[str]] = {}

            def fake_run(command, check, capture_output, text):
                captured["command"] = command
                self.assertEqual(check, True)
                self.assertEqual(capture_output, True)
                self.assertEqual(text, True)
                return subprocess.CompletedProcess(
                    command,
                    0,
                    stdout=f"{selected_path}\n",
                    stderr="",
                )

            with patch("pydf_tool.macos_integration.subprocess.run", side_effect=fake_run):
                result = choose_pdf_file(
                    initial_directory=input_reference,
                    prompt="Scegli un PDF",
                )

        self.assertEqual(result, selected_path)
        self.assertEqual(captured["command"][0], "osascript")
        self.assertIn("choose file of type {\"com.adobe.pdf\"}", captured["command"][2])
        self.assertEqual(captured["command"][3], "Scegli un PDF")
        self.assertEqual(captured["command"][4], str(default_directory))

    def test_choose_pdf_file_returns_none_when_user_cancels(self) -> None:
        def fake_run(command, check, capture_output, text):
            raise subprocess.CalledProcessError(
                returncode=1,
                cmd=command,
                output="",
                stderr="User canceled.",
            )

        with patch("pydf_tool.macos_integration.subprocess.run", side_effect=fake_run):
            result = choose_pdf_file()

        self.assertIsNone(result)

    def test_choose_pdf_file_raises_on_unexpected_osascript_error(self) -> None:
        def fake_run(command, check, capture_output, text):
            raise subprocess.CalledProcessError(
                returncode=1,
                cmd=command,
                output="",
                stderr="Syntax Error",
            )

        with patch("pydf_tool.macos_integration.subprocess.run", side_effect=fake_run):
            with self.assertRaises(PDFToolError) as context:
                choose_pdf_file()

        self.assertIn("Selezione file fallita", str(context.exception))
        self.assertIn("Syntax Error", str(context.exception))

    def test_choose_pdf_file_rejects_non_pdf_selection(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            selected_path = Path(temp_dir, "selected.txt")

            def fake_run(command, check, capture_output, text):
                return subprocess.CompletedProcess(
                    command,
                    0,
                    stdout=f"{selected_path}\n",
                    stderr="",
                )

            with patch("pydf_tool.macos_integration.subprocess.run", side_effect=fake_run):
                with self.assertRaises(PDFToolError) as context:
                    choose_pdf_file()

        self.assertIn("non è un PDF", str(context.exception))

    def test_open_with_default_app_uses_open_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir, "report.pdf")
            file_path.write_bytes(b"%PDF-1.4")
            captured: dict[str, list[str]] = {}

            def fake_run(command, check, capture_output, text):
                captured["command"] = command
                return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

            with patch("pydf_tool.macos_integration.subprocess.run", side_effect=fake_run):
                open_with_default_app(file_path)

        self.assertEqual(captured["command"], ["open", str(file_path)])

    def test_reveal_in_finder_uses_open_r(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir, "report.pdf")
            file_path.write_bytes(b"%PDF-1.4")
            captured: dict[str, list[str]] = {}

            def fake_run(command, check, capture_output, text):
                captured["command"] = command
                return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

            with patch("pydf_tool.macos_integration.subprocess.run", side_effect=fake_run):
                reveal_in_finder(file_path)

        self.assertEqual(captured["command"], ["open", "-R", str(file_path)])

    def test_open_output_folder_opens_parent_directory_for_file_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir, "nested", "out.pdf")
            output_path.parent.mkdir()
            captured: dict[str, list[str]] = {}

            def fake_run(command, check, capture_output, text):
                captured["command"] = command
                return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

            with patch("pydf_tool.macos_integration.subprocess.run", side_effect=fake_run):
                open_output_folder(output_path)

        self.assertEqual(captured["command"], ["open", str(output_path.parent)])

    def test_open_with_default_app_rejects_missing_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            missing_path = Path(temp_dir, "missing.pdf")

            with self.assertRaises(PDFToolError) as context:
                open_with_default_app(missing_path)

        self.assertIn("Percorso non trovato", str(context.exception))

    def test_choose_pdf_file_requires_macos(self) -> None:
        with patch("pydf_tool.macos_integration.sys.platform", "linux"):
            with self.assertRaises(PDFToolError) as context:
                choose_pdf_file()

        self.assertIn("solo su macOS", str(context.exception))


if __name__ == "__main__":
    unittest.main()
