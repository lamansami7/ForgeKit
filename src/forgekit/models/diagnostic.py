"""Diagnostic result model."""

from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class DiagnosticResult:
    name: str
    status: str  # pass, warn, fail, skip
    message: str
    details: dict[str, Any] | None = None
    remediation: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
