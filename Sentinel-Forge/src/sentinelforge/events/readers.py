"""Read event files (JSON Lines or CSV) record by record.

Each record is reported with its line number, so a problem in one line can be
fixed without guessing. Bad lines never stop the rest of the file from being
read.
"""

from __future__ import annotations

import csv
import json
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import ValidationError

from sentinelforge.events.normalise import normalise_record
from sentinelforge.events.schema import SecurityEvent

MAX_LINE_BYTES = 1_000_000
SUPPORTED_SUFFIXES = {".jsonl": "jsonl", ".ndjson": "jsonl", ".csv": "csv"}


class UnsupportedFormat(ValueError):
    pass


@dataclass(frozen=True)
class LineError:
    line_number: int
    field: str
    message: str


@dataclass
class ParsedRecord:
    line_number: int
    event: SecurityEvent | None = None
    errors: list[LineError] = field(default_factory=list)
    unmapped_fields: list[str] = field(default_factory=list)


def file_format(path: Path) -> str:
    fmt = SUPPORTED_SUFFIXES.get(path.suffix.lower())
    if fmt is None:
        raise UnsupportedFormat(
            f"unsupported file type {path.suffix!r}; use .jsonl (JSON Lines) or .csv"
        )
    return fmt


def _pydantic_errors(line_number: int, exc: ValidationError) -> list[LineError]:
    """Readable messages. ``include_input=False`` keeps raw values (which might be
    secrets that ended up in the wrong field) out of error messages."""
    errors = []
    for err in exc.errors(include_input=False):
        location = ".".join(str(part) for part in err["loc"]) or "(event)"
        errors.append(LineError(line_number, location, err["msg"].removeprefix("Value error, ")))
    return errors


def _raw_jsonl(path: Path) -> Iterator[tuple[int, dict | LineError]]:
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            if len(line.encode("utf-8")) > MAX_LINE_BYTES:
                yield line_number, LineError(line_number, "(line)", "line is too long")
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                yield line_number, LineError(line_number, "(line)", f"not valid JSON: {exc.msg}")
                continue
            if not isinstance(record, dict):
                yield (
                    line_number,
                    LineError(line_number, "(line)", "each line must be a JSON object"),
                )
                continue
            yield line_number, record


def _raw_csv(path: Path) -> Iterator[tuple[int, dict | LineError]]:
    # utf-8-sig removes the byte-order mark that Excel adds to CSV files.
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            return
        for row in reader:
            line_number = reader.line_num
            if None in row:
                yield line_number, LineError(line_number, "(line)", "more values than headers")
                continue
            # Empty CSV cells mean "not provided".
            record = {k.strip(): v for k, v in row.items() if v is not None and v.strip() != ""}
            if record:
                yield line_number, record


def read_records(path: Path, *, normalise: bool = True) -> Iterator[ParsedRecord]:
    """Yield one ``ParsedRecord`` per non-blank record.

    ``normalise=True`` maps aliases and synonyms first (used for ingestion).
    ``normalise=False`` requires the file to use the common schema exactly
    (used by ``sentinelforge events validate``).
    """
    raw_records = _raw_jsonl(path) if file_format(path) == "jsonl" else _raw_csv(path)
    for line_number, item in raw_records:
        if isinstance(item, LineError):
            yield ParsedRecord(line_number, errors=[item])
            continue
        unmapped: list[str] = []
        data = item
        if normalise:
            result = normalise_record(item)
            data, unmapped = result.data, result.unmapped_fields
        try:
            event = SecurityEvent.model_validate(data)
        except ValidationError as exc:
            yield ParsedRecord(line_number, errors=_pydantic_errors(line_number, exc))
            continue
        yield ParsedRecord(line_number, event=event, unmapped_fields=unmapped)
