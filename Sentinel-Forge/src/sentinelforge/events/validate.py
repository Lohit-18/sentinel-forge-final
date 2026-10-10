"""Validate an event file against the common schema without touching the database."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from sentinelforge.events.readers import MAX_LINE_BYTES, LineError, read_records
from sentinelforge.events.schema import SecurityEvent

__all__ = ["MAX_LINE_BYTES", "LineError", "ValidationReport", "validate_file", "validate_jsonl"]


@dataclass
class ValidationReport:
    path: Path
    total: int = 0
    valid_events: list[SecurityEvent] = field(default_factory=list)
    errors: list[LineError] = field(default_factory=list)
    invalid_lines: set[int] = field(default_factory=set)
    unmapped_fields: dict[str, int] = field(default_factory=dict)

    @property
    def valid(self) -> int:
        return len(self.valid_events)

    @property
    def invalid(self) -> int:
        return len(self.invalid_lines)

    @property
    def ok(self) -> bool:
        return self.invalid == 0


def validate_file(path: Path, *, normalise: bool = False) -> ValidationReport:
    """Check every record. ``normalise=True`` accepts field aliases and synonyms."""
    report = ValidationReport(path=path)
    for record in read_records(path, normalise=normalise):
        report.total += 1
        for name in record.unmapped_fields:
            report.unmapped_fields[name] = report.unmapped_fields.get(name, 0) + 1
        if record.event is not None:
            report.valid_events.append(record.event)
        else:
            report.errors.extend(record.errors)
            report.invalid_lines.add(record.line_number)
    return report


def validate_jsonl(path: Path) -> ValidationReport:
    """Strict validation of a JSON Lines file in the common schema."""
    return validate_file(path, normalise=False)
