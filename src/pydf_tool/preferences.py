from __future__ import annotations

import json
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

APP_NAME = "PyDF Tool"
PREFERENCES_FILENAME = "preferences.json"
PREFERENCES_SCHEMA_VERSION = 1

DEFAULT_OCR_LANGUAGE = "it"
DEFAULT_COMPRESSION_LEVEL = "medium"

__all__ = [
    "APP_NAME",
    "DEFAULT_COMPRESSION_LEVEL",
    "DEFAULT_OCR_LANGUAGE",
    "PREFERENCES_FILENAME",
    "PREFERENCES_SCHEMA_VERSION",
    "Preferences",
    "load_preferences",
    "preferences_directory",
    "preferences_file_path",
    "save_preferences",
]


def _normalize_storage_path(path: Path) -> Path:
    expanded_path = path.expanduser()
    if expanded_path.is_absolute():
        return expanded_path
    return expanded_path.resolve(strict=False)


def _coerce_optional_path(value: Any) -> Path | None:
    if value is None:
        return None
    if isinstance(value, Path):
        return _normalize_storage_path(value)
    if not isinstance(value, str):
        return None

    text = value.strip()
    if not text:
        return None
    return _normalize_storage_path(Path(text))


def _coerce_text(value: Any, default: str) -> str:
    if isinstance(value, str):
        text = value.strip()
        if text:
            return text
    return default


def preferences_directory(home: Path | None = None) -> Path:
    base_home = home if home is not None else Path.home()
    return base_home / "Library" / "Application Support" / APP_NAME


def preferences_file_path(home: Path | None = None) -> Path:
    return preferences_directory(home) / PREFERENCES_FILENAME


@dataclass(frozen=True, slots=True)
class Preferences:
    last_directory: Path | None = None
    ocr_language: str = DEFAULT_OCR_LANGUAGE
    compression_level: str = DEFAULT_COMPRESSION_LEVEL
    schema_version: int = PREFERENCES_SCHEMA_VERSION

    @classmethod
    def default(cls) -> "Preferences":
        return cls()

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "Preferences":
        return cls(
            last_directory=_coerce_optional_path(payload.get("last_directory")),
            ocr_language=_coerce_text(payload.get("ocr_language"), DEFAULT_OCR_LANGUAGE),
            compression_level=_coerce_text(
                payload.get("compression_level"), DEFAULT_COMPRESSION_LEVEL
            ),
            schema_version=PREFERENCES_SCHEMA_VERSION,
        )

    def to_mapping(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "last_directory": str(self.last_directory) if self.last_directory else None,
            "ocr_language": self.ocr_language,
            "compression_level": self.compression_level,
        }

    def with_last_directory(self, path: str | Path | None) -> "Preferences":
        return replace(self, last_directory=_coerce_optional_path(path))

    def with_ocr_language(self, language: str) -> "Preferences":
        return replace(self, ocr_language=_coerce_text(language, DEFAULT_OCR_LANGUAGE))

    def with_compression_level(self, level: str) -> "Preferences":
        return replace(
            self, compression_level=_coerce_text(level, DEFAULT_COMPRESSION_LEVEL)
        )

    def remember_path(self, path: str | Path) -> "Preferences":
        candidate = Path(path).expanduser()
        if candidate.exists():
            if candidate.is_dir():
                return self.with_last_directory(candidate)
            return self.with_last_directory(candidate.parent)
        if candidate.suffix:
            return self.with_last_directory(candidate.parent)
        if candidate.name:
            return self.with_last_directory(candidate)
        return self.with_last_directory(candidate.parent)


def load_preferences(home: Path | None = None) -> Preferences:
    path = preferences_file_path(home)
    try:
        raw_payload = path.read_text(encoding="utf-8")
        payload = json.loads(raw_payload)
    except (FileNotFoundError, OSError, UnicodeDecodeError, json.JSONDecodeError):
        return Preferences.default()

    if not isinstance(payload, Mapping):
        return Preferences.default()

    return Preferences.from_mapping(payload)


def save_preferences(preferences: Preferences, home: Path | None = None) -> Path:
    path = preferences_file_path(home)
    path.parent.mkdir(parents=True, exist_ok=True)

    payload = json.dumps(preferences.to_mapping(), ensure_ascii=False, indent=2, sort_keys=True)

    temp_file = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{PREFERENCES_FILENAME}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temp_file = Path(handle.name)
            handle.write(payload)
            handle.write("\n")

        temp_file.replace(path)
        return path
    except Exception:
        if temp_file is not None:
            temp_file.unlink(missing_ok=True)
        raise
