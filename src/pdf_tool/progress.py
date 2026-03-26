from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OperationProgress:
    stage: str
    message: str
    completed: int = 0
    total: int | None = None
