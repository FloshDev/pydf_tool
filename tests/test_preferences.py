import json
import tempfile
import unittest
from pathlib import Path

from pydf_tool.preferences import (
    APP_NAME,
    DEFAULT_COMPRESSION_LEVEL,
    DEFAULT_OCR_LANGUAGE,
    PREFERENCES_FILENAME,
    PREFERENCES_SCHEMA_VERSION,
    Preferences,
    load_preferences,
    preferences_directory,
    preferences_file_path,
    save_preferences,
)


class PreferencesPathTestCase(unittest.TestCase):
    def test_preferences_directory_uses_macos_application_support(self) -> None:
        home = Path("/Users/flosh")
        expected = home / "Library" / "Application Support" / APP_NAME

        self.assertEqual(preferences_directory(home), expected)

    def test_preferences_file_path_points_to_preferences_json(self) -> None:
        home = Path("/Users/flosh")
        expected = (
            home / "Library" / "Application Support" / APP_NAME / PREFERENCES_FILENAME
        )

        self.assertEqual(preferences_file_path(home), expected)


class PreferencesModelTestCase(unittest.TestCase):
    def test_default_preferences_are_sensible(self) -> None:
        preferences = Preferences.default()

        self.assertIsNone(preferences.last_directory)
        self.assertEqual(preferences.ocr_language, DEFAULT_OCR_LANGUAGE)
        self.assertEqual(preferences.compression_level, DEFAULT_COMPRESSION_LEVEL)
        self.assertEqual(preferences.schema_version, PREFERENCES_SCHEMA_VERSION)

    def test_remember_path_uses_parent_for_file_paths(self) -> None:
        preferences = Preferences.default()

        updated = preferences.remember_path(Path("/tmp/input scan.pdf"))

        self.assertEqual(updated.last_directory, Path("/tmp"))

    def test_remember_path_keeps_directories(self) -> None:
        preferences = Preferences.default()

        updated = preferences.remember_path(Path("/tmp/Scans"))

        self.assertEqual(updated.last_directory, Path("/tmp/Scans"))

    def test_with_helpers_return_new_preferences(self) -> None:
        preferences = Preferences.default()

        updated = (
            preferences.with_ocr_language("it+en")
            .with_compression_level("80")
            .with_last_directory(Path("/tmp"))
        )

        self.assertEqual(updated.ocr_language, "it+en")
        self.assertEqual(updated.compression_level, "80")
        self.assertEqual(updated.last_directory, Path("/tmp"))
        self.assertEqual(preferences.ocr_language, DEFAULT_OCR_LANGUAGE)

    def test_to_mapping_serializes_path_as_string(self) -> None:
        preferences = Preferences(last_directory=Path("/Users/flosh/Documents"))

        payload = preferences.to_mapping()

        self.assertEqual(payload["last_directory"], "/Users/flosh/Documents")
        self.assertEqual(payload["schema_version"], PREFERENCES_SCHEMA_VERSION)

    def test_from_mapping_uses_defaults_for_invalid_values(self) -> None:
        payload = {
            "schema_version": 99,
            "last_directory": 123,
            "ocr_language": "",
            "compression_level": None,
        }

        preferences = Preferences.from_mapping(payload)

        self.assertIsNone(preferences.last_directory)
        self.assertEqual(preferences.ocr_language, DEFAULT_OCR_LANGUAGE)
        self.assertEqual(preferences.compression_level, DEFAULT_COMPRESSION_LEVEL)
        self.assertEqual(preferences.schema_version, PREFERENCES_SCHEMA_VERSION)


class PreferencesStoreTestCase(unittest.TestCase):
    def test_load_preferences_returns_defaults_when_file_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            home = Path(temp_dir)

            preferences = load_preferences(home)

            self.assertEqual(preferences, Preferences.default())

    def test_load_preferences_returns_defaults_when_file_is_corrupt(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            home = Path(temp_dir)
            path = preferences_file_path(home)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("{not-json", encoding="utf-8")

            preferences = load_preferences(home)

            self.assertEqual(preferences, Preferences.default())

    def test_save_preferences_round_trips(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            home = Path(temp_dir)
            input_dir = home / "Documents" / "Scans"
            input_dir.mkdir(parents=True)
            preferences = Preferences(
                last_directory=input_dir,
                ocr_language="it+en",
                compression_level="80",
            )

            saved_path = save_preferences(preferences, home)
            reloaded = load_preferences(home)

            self.assertEqual(saved_path, preferences_file_path(home))
            self.assertTrue(saved_path.exists())
            self.assertEqual(reloaded, preferences)

    def test_save_preferences_creates_parent_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            home = Path(temp_dir)
            preferences = Preferences.default().with_last_directory(Path("/tmp"))

            saved_path = save_preferences(preferences, home)

            self.assertTrue(saved_path.parent.exists())
            self.assertTrue(saved_path.exists())

    def test_load_preferences_ignores_partial_payload(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            home = Path(temp_dir)
            path = preferences_file_path(home)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(
                    {
                        "last_directory": "/Users/flosh/Documents",
                        "ocr_language": "en",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            preferences = load_preferences(home)

            self.assertEqual(preferences.last_directory, Path("/Users/flosh/Documents"))
            self.assertEqual(preferences.ocr_language, "en")
            self.assertEqual(preferences.compression_level, DEFAULT_COMPRESSION_LEVEL)

