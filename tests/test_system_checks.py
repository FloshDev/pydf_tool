import unittest
from unittest.mock import patch

from pydf_tool.errors import PDFToolError
from pydf_tool.system_checks import (
    check_compress_systems,
    check_global_systems,
    check_ocr_systems,
    check_operation_systems,
)


class SystemChecksTestCase(unittest.TestCase):
    def test_global_check_reports_all_tools_as_available(self) -> None:
        def fake_which(command: str):
            return {
                "tesseract": "/usr/local/bin/tesseract",
                "pdftocairo": "/usr/local/bin/pdftocairo",
                "pdftoppm": None,
                "gs": "/usr/local/bin/gs",
            }.get(command)

        with patch("pydf_tool.system_checks.shutil.which", side_effect=fake_which):
            report = check_global_systems()

        self.assertTrue(report.ok)
        self.assertEqual([check.key for check in report.checks], ["tesseract", "poppler", "ghostscript"])
        self.assertTrue(report.available[1].available_command.endswith("pdftocairo"))
        self.assertIn("Controlli di sistema globali", report.message)
        self.assertIn("disponibile (`/usr/local/bin/gs`)", report.message)

    def test_ocr_check_marks_missing_poppler_with_install_hint(self) -> None:
        def fake_which(command: str):
            return {
                "tesseract": "/usr/local/bin/tesseract",
                "pdftocairo": None,
                "pdftoppm": None,
                "gs": "/usr/local/bin/gs",
            }.get(command)

        with patch("pydf_tool.system_checks.shutil.which", side_effect=fake_which):
            report = check_ocr_systems()

        self.assertFalse(report.ok)
        self.assertEqual([check.key for check in report.missing], ["poppler"])
        self.assertIn("Poppler: non trovato", report.message)
        self.assertIn("brew install poppler", report.message)
        self.assertTrue(report.available[0].available_command.endswith("tesseract"))

    def test_compress_check_is_single_requirement(self) -> None:
        with patch("pydf_tool.system_checks.shutil.which", return_value=None):
            report = check_compress_systems()

        self.assertFalse(report.ok)
        self.assertEqual([check.key for check in report.checks], ["ghostscript"])
        self.assertIn("Ghostscript: non trovato", report.message)
        self.assertIn("brew install ghostscript", report.message)

    def test_check_operation_returns_empty_report(self) -> None:
        report = check_operation_systems("check")

        self.assertTrue(report.ok)
        self.assertEqual(report.checks, ())
        self.assertIn("Nessun controllo di sistema esterno richiesto", report.message)

    def test_generic_operation_dispatch_accepts_aliases(self) -> None:
        with patch("pydf_tool.system_checks.shutil.which", return_value="/usr/local/bin/gs"):
            report = check_operation_systems("system")

        self.assertEqual(report.scope, "global")
        self.assertTrue(report.ok)

    def test_generic_operation_dispatch_rejects_unknown_operation(self) -> None:
        with self.assertRaises(PDFToolError):
            check_operation_systems("unknown")

    def test_poppler_prefers_pdftocairo_when_available(self) -> None:
        def fake_which(command: str):
            return {
                "tesseract": None,
                "pdftocairo": "/usr/local/bin/pdftocairo",
                "pdftoppm": "/usr/local/bin/pdftoppm",
                "gs": None,
            }.get(command)

        with patch("pydf_tool.system_checks.shutil.which", side_effect=fake_which):
            report = check_ocr_systems()

        poppler = next(check for check in report.checks if check.key == "poppler")
        self.assertTrue(poppler.available_command.endswith("pdftocairo"))


if __name__ == "__main__":
    unittest.main()
