from __future__ import annotations

from dataclasses import dataclass
import shutil
from typing import Literal, cast

from .errors import PDFToolError

OperationName = Literal["global", "ocr", "compress", "check"]


@dataclass(frozen=True)
class ToolSpec:
    key: str
    label: str
    commands: tuple[str, ...]
    install_hint: str
    purpose: str

    def resolve(self) -> "ToolCheck":
        available_command = next(
            (
                resolved
                for command in self.commands
                if (resolved := shutil.which(command)) is not None
            ),
            None,
        )
        return ToolCheck(
            key=self.key,
            label=self.label,
            commands=self.commands,
            install_hint=self.install_hint,
            purpose=self.purpose,
            available_command=available_command,
        )


@dataclass(frozen=True)
class ToolCheck:
    key: str
    label: str
    commands: tuple[str, ...]
    install_hint: str
    purpose: str
    available_command: str | None = None

    @property
    def available(self) -> bool:
        return self.available_command is not None

    @property
    def display_commands(self) -> str:
        if len(self.commands) == 1:
            return f"`{self.commands[0]}`"
        return "`" + "`/`".join(self.commands) + "`"


@dataclass(frozen=True)
class SystemCheckReport:
    scope: OperationName
    checks: tuple[ToolCheck, ...]

    @property
    def ok(self) -> bool:
        return not self.missing

    @property
    def missing(self) -> tuple[ToolCheck, ...]:
        return tuple(check for check in self.checks if not check.available)

    @property
    def available(self) -> tuple[ToolCheck, ...]:
        return tuple(check for check in self.checks if check.available)

    @property
    def message(self) -> str:
        scope_label = _SCOPE_LABELS.get(self.scope, self.scope)
        if not self.checks:
            return f"Nessun controllo di sistema esterno richiesto per {scope_label}."

        if self.scope == "global":
            lines = ["Controlli di sistema globali:"]
        else:
            lines = [f"Controlli di sistema per {scope_label}:"]
        for check in self.checks:
            if check.available:
                lines.append(
                    f"- {check.label}: disponibile (`{check.available_command}`)"
                )
            else:
                lines.append(
                    f"- {check.label}: non trovato. {check.install_hint}"
                )
        return "\n".join(lines)


_TESSERACT = ToolSpec(
    key="tesseract",
    label="Tesseract",
    commands=("tesseract",),
    install_hint="Su macOS installa con `brew install tesseract`.",
    purpose="riconoscimento OCR del testo",
)
_POPPLER = ToolSpec(
    key="poppler",
    label="Poppler",
    commands=("pdftocairo", "pdftoppm"),
    install_hint="Su macOS installa con `brew install poppler`.",
    purpose="render delle pagine PDF per l'OCR",
)
_GHOSTSCRIPT = ToolSpec(
    key="ghostscript",
    label="Ghostscript",
    commands=("gs",),
    install_hint="Su macOS installa con `brew install ghostscript`.",
    purpose="compressione dei PDF",
)

_SCOPE_LABELS: dict[OperationName, str] = {
    "global": "controllo globale",
    "ocr": "OCR",
    "compress": "compressione",
    "check": "verifica PDF",
}

_CHECKS_BY_OPERATION: dict[OperationName, tuple[ToolSpec, ...]] = {
    "global": (_TESSERACT, _POPPLER, _GHOSTSCRIPT),
    "ocr": (_TESSERACT, _POPPLER),
    "compress": (_GHOSTSCRIPT,),
    "check": (),
}


def _normalize_operation(operation: str) -> OperationName:
    normalized = operation.strip().lower()
    if normalized in {"global", "all", "system", "sistema"}:
        return "global"
    if normalized in _CHECKS_BY_OPERATION:
        return cast(OperationName, normalized)
    raise PDFToolError(
        "Operazione non supportata per i controlli di sistema. "
        "Usa `global`, `ocr`, `compress` oppure `check`."
    )


def _build_report(scope: OperationName) -> SystemCheckReport:
    return SystemCheckReport(
        scope=scope,
        checks=tuple(spec.resolve() for spec in _CHECKS_BY_OPERATION[scope]),
    )


def check_global_systems() -> SystemCheckReport:
    return _build_report("global")


def check_operation_systems(operation: str) -> SystemCheckReport:
    return _build_report(_normalize_operation(operation))


def check_ocr_systems() -> SystemCheckReport:
    return _build_report("ocr")


def check_compress_systems() -> SystemCheckReport:
    return _build_report("compress")


__all__ = [
    "OperationName",
    "SystemCheckReport",
    "ToolCheck",
    "ToolSpec",
    "check_compress_systems",
    "check_global_systems",
    "check_ocr_systems",
    "check_operation_systems",
]
