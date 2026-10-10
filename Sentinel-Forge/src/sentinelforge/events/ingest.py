"""Ingestion pipeline: file -> validate/normalise -> store in PostgreSQL.

Steps:
1. Record the start of an import run (traceable origin for every event).
2. Read the file record by record, normalising field aliases and synonyms.
3. Validate each record against the common schema; invalid records are counted
   and reported, never stored.
4. Insert valid events in batches, skipping duplicates by fingerprint.
5. Record the final counts and mark the run completed (or failed).

Invalid records do not stop the import; the rest of the file is still ingested.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import psycopg

from sentinelforge.config import Settings
from sentinelforge.db.connect import connect
from sentinelforge.db.events_repo import insert_events
from sentinelforge.events.readers import LineError, file_format, read_records

BATCH_SIZE = 500


@dataclass
class IngestResult:
    import_id: int | None
    dataset_id: str
    path: Path
    records_read: int = 0
    stored: int = 0
    duplicates: int = 0
    invalid: int = 0
    errors: list[LineError] = field(default_factory=list)
    unmapped_fields: dict[str, int] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.invalid == 0


def _start_import(conn: psycopg.Connection, dataset_id: str, path: Path) -> int:
    row = conn.execute(
        "INSERT INTO dataset_imports (dataset_id, source_path) VALUES (%s, %s) RETURNING id",
        (dataset_id, str(path)),
    ).fetchone()
    return row[0]


def _finish_import(conn: psycopg.Connection, import_id: int, result: IngestResult, status: str):
    conn.execute(
        "UPDATE dataset_imports SET finished_at = now(), records_read = %s, "
        "records_stored = %s, duplicates = %s, invalid = %s, status = %s WHERE id = %s",
        (result.records_read, result.stored, result.duplicates, result.invalid, status, import_id),
    )


def ingest_file(settings: Settings, path: Path, *, dataset_id: str | None = None) -> IngestResult:
    """Ingest one event file into PostgreSQL. Raises if the file type is unsupported."""
    file_format(path)  # raises UnsupportedFormat early if the extension is wrong
    dataset = dataset_id or path.stem
    result = IngestResult(import_id=None, dataset_id=dataset, path=path)

    with connect(settings.app_connection()) as conn:
        import_id = _start_import(conn, dataset, path)
        result.import_id = import_id
        conn.commit()
        try:
            batch = []
            for record in read_records(path, normalise=True):
                result.records_read += 1
                for name in record.unmapped_fields:
                    result.unmapped_fields[name] = result.unmapped_fields.get(name, 0) + 1
                if record.event is None:
                    result.invalid += 1
                    result.errors.extend(record.errors)
                    continue
                event = record.event
                # A file need not carry a dataset label. When it doesn't, the
                # event inherits the import's dataset so it can be found later.
                if event.dataset_id is None:
                    event = event.model_copy(update={"dataset_id": dataset})
                batch.append(event)
                if len(batch) >= BATCH_SIZE:
                    _flush(conn, batch, import_id, result)
                    batch = []
            if batch:
                _flush(conn, batch, import_id, result)
            _finish_import(conn, import_id, result, "completed")
            conn.commit()
        except Exception:
            conn.rollback()
            with connect(settings.app_connection()) as cleanup:
                _finish_import(cleanup, import_id, result, "failed")
                cleanup.commit()
            raise
    return result


def _flush(conn, batch, import_id, result: IngestResult) -> None:
    outcome = insert_events(conn, batch, import_id=import_id)
    result.stored += outcome.stored
    result.duplicates += outcome.duplicates
    conn.commit()
