import asyncio
import unittest
from pathlib import Path
from unittest.mock import patch

from textual.widgets import Button, Input, Static

from pydf_tool.compress import CompressionResult
from pydf_tool.preferences import Preferences
from pydf_tool.system_checks import SystemCheckReport, ToolCheck
from pydf_tool.tui import (
    HomeScreen,
    ProgressScreen,
    PyDFApp,
    SystemCheckScreen,
    WizardScreen,
    CheckInputScreen,
)


def _missing_tool_report() -> SystemCheckReport:
    return SystemCheckReport(
        scope="global",
        checks=(
            ToolCheck(
                key="tesseract",
                label="Tesseract",
                commands=("tesseract",),
                install_hint="brew install tesseract",
                purpose="OCR",
                available_command=None,
            ),
        ),
    )


class TUIUsabilityTestCase(unittest.TestCase):
    def _make_app(
        self,
        *,
        show_startup_checks: bool = False,
        preferences: Preferences | None = None,
        global_system_report: SystemCheckReport | None = None,
    ) -> PyDFApp:
        return PyDFApp(
            show_startup_checks=show_startup_checks,
            preferences=preferences,
            global_system_report=global_system_report,
        )

    def test_app_shows_startup_checks_modal_when_dependencies_are_missing(self) -> None:
        async def scenario() -> None:
            app = self._make_app(
                show_startup_checks=True,
                global_system_report=_missing_tool_report(),
            )
            async with app.run_test() as pilot:
                await pilot.pause()
                self.assertIsInstance(app.screen, SystemCheckScreen)

        asyncio.run(scenario())

    def test_compress_action_is_blocked_when_system_checks_fail(self) -> None:
        async def scenario() -> None:
            app = self._make_app()
            async with app.run_test() as pilot:
                with patch(
                    "pydf_tool.tui.check_operation_systems",
                    return_value=_missing_tool_report(),
                ):
                    await pilot.press("down")
                    await pilot.pause()
                    await pilot.press("enter")
                    await pilot.pause()

                self.assertIsInstance(app.screen, SystemCheckScreen)

        asyncio.run(scenario())

    def test_wizard_uses_saved_ocr_language_as_default_choice(self) -> None:
        async def scenario() -> None:
            app = self._make_app(
                preferences=Preferences.default().with_ocr_language("it+en")
            )
            async with app.run_test() as pilot:
                wizard = WizardScreen(mode="ocr", prefill_path="/tmp/input.pdf")
                app.push_screen(wizard)
                await pilot.pause()

                choice_list = wizard.query_one("#step-choices")
                highlighted = choice_list.highlighted_child
                self.assertEqual(highlighted.choice.value if highlighted else None, "it+en")

        asyncio.run(scenario())

    def test_wizard_f2_picker_populates_file_input_and_remembers_directory(self) -> None:
        async def scenario() -> None:
            app = self._make_app()
            selected = Path("/tmp/finder-picked/document.pdf")
            async with app.run_test() as pilot:
                wizard = WizardScreen(mode="ocr")
                app.push_screen(wizard)
                await pilot.pause()

                with patch("pydf_tool.tui.choose_pdf_file", return_value=selected):
                    await pilot.press("f2")
                    await pilot.pause()

                input_widget = wizard.query_one("#step-input", Input)
                self.assertEqual(input_widget.value, str(selected))
                self.assertEqual(app.focused.id if app.focused else None, "step-input")
                self.assertEqual(app.preferences.last_directory, selected.parent)

        asyncio.run(scenario())

    def test_wizard_file_step_arrow_keys_cycle_between_input_and_finder_button(self) -> None:
        async def scenario() -> None:
            app = self._make_app()
            async with app.run_test() as pilot:
                wizard = WizardScreen(mode="compress")
                app.push_screen(wizard)
                await pilot.pause()

                self.assertEqual(app.focused.id if app.focused else None, "step-input")

                await pilot.press("down")
                await pilot.pause()
                self.assertEqual(app.focused.id if app.focused else None, "finder-button")

                await pilot.press("up")
                await pilot.pause()
                self.assertEqual(app.focused.id if app.focused else None, "step-input")

        asyncio.run(scenario())

    def test_check_input_screen_f2_picker_populates_input(self) -> None:
        async def scenario() -> None:
            app = self._make_app()
            selected = Path("/tmp/check-picked/scan.pdf")
            async with app.run_test() as pilot:
                screen = CheckInputScreen()
                app.push_screen(screen)
                await pilot.pause()

                with patch("pydf_tool.tui.choose_pdf_file", return_value=selected):
                    await pilot.press("f2")
                    await pilot.pause()

                input_widget = screen.query_one("#check-input", Input)
                self.assertEqual(input_widget.value, str(selected))
                self.assertEqual(app.focused.id if app.focused else None, "check-input")
                self.assertEqual(app.preferences.last_directory, selected.parent)

        asyncio.run(scenario())

    def test_check_input_screen_arrow_keys_cycle_between_input_and_finder_button(self) -> None:
        async def scenario() -> None:
            app = self._make_app()
            async with app.run_test() as pilot:
                screen = CheckInputScreen()
                app.push_screen(screen)
                await pilot.pause()

                self.assertEqual(app.focused.id if app.focused else None, "check-input")

                await pilot.press("down")
                await pilot.pause()
                self.assertEqual(
                    app.focused.id if app.focused else None,
                    "check-picker-button",
                )

                await pilot.press("up")
                await pilot.pause()
                self.assertEqual(app.focused.id if app.focused else None, "check-input")

        asyncio.run(scenario())

    def test_output_step_hint_shows_suggested_path_in_same_folder(self) -> None:
        async def scenario() -> None:
            app = self._make_app()
            async with app.run_test() as pilot:
                wizard = WizardScreen(mode="ocr", prefill_path="/tmp/input.pdf")
                app.push_screen(wizard)
                await pilot.pause()

                wizard._values["formato"] = "txt"
                wizard.current_step = 2
                await pilot.pause()

                hint = wizard.query_one("#step-hint", Static)
                self.assertIn("/tmp/input.1.txt", hint.content)

        asyncio.run(scenario())

    def test_progress_success_shows_open_actions(self) -> None:
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

                progress._on_success_compress(
                    CompressionResult(
                        output_path=Path("/tmp/output.pdf"),
                        level="medium",
                        grayscale=False,
                        size_before=1_000_000,
                        size_after=500_000,
                    )
                )
                await pilot.pause()

                self.assertTrue(progress.query_one("#btn-open-file", Button).display)
                self.assertTrue(progress.query_one("#btn-open-folder", Button).display)
                self.assertEqual(app.focused.id if app.focused else None, "btn-open-file")

        asyncio.run(scenario())


if __name__ == "__main__":
    unittest.main()
