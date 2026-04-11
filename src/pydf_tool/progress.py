from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class OperationProgress:
    stage: str
    message: str
    completed: int = 0
    total: int | None = None


def emit_progress(
    callback: Callable[[OperationProgress], None] | None,
    *,
    stage: str,
    message: str,
    completed: int = 0,
    total: int | None = None,
) -> None:
    if callback is None:
        return
    callback(
        OperationProgress(
            stage=stage,
            message=message,
            completed=completed,
            total=total,
        )
    )
