"""Reading and writing events in PostgreSQL (as the application role).

The application role has INSERT/UPDATE/SELECT only. Duplicate events are handled
by ``INSERT ... ON CONFLICT (fingerprint) DO NOTHING``: importing the same file
twice stores nothing the second time.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

import psycopg
from psycopg import sql

from sentinelforge.events.fingerprint import fingerprint
from sentinelforge.events.schema import SecurityEvent

# Maps schema field -> database column. ``user`` becomes ``app_user`` because
# "user" is awkward in SQL; everything else matches.
_COLUMN_FOR_FIELD = {"user": "app_user"}

# Event fields stored as their own columns (raw and the renamed user handled separately).
_EVENT_COLUMNS = [
    "event_time",
    "category",
    "action",
    "outcome",
    "severity",
    "source_type",
    "source_host",
    "source_event_id",
    "app_user",
    "target_user",
    "src_ip",
    "src_port",
    "dst_ip",
    "dst_port",
    "dst_domain",
    "process_name",
    "process_path",
    "parent_process_name",
    "process_command_line",
    "file_sha256",
    "object_name",
    "dataset_id",
    "scenario_id",
]


def _row_values(event: SecurityEvent) -> dict[str, object]:
    data = event.model_dump(mode="json")
    values: dict[str, object] = {}
    for field_name, value in data.items():
        if field_name == "raw":
            continue
        column = _COLUMN_FOR_FIELD.get(field_name, field_name)
        values[column] = value
    values["fingerprint"] = fingerprint(event)
    values["raw"] = json.dumps(data.get("raw", {}))
    return values


@dataclass
class InsertResult:
    stored: int
    duplicates: int


def insert_events(
    conn: psycopg.Connection, events: list[SecurityEvent], *, import_id: int | None = None
) -> InsertResult:
    """Insert events, skipping duplicates. Returns how many were stored vs skipped."""
    if not events:
        return InsertResult(stored=0, duplicates=0)

    columns = ["fingerprint", *_EVENT_COLUMNS, "raw", "import_id"]
    placeholders = sql.SQL(", ").join(sql.Placeholder(c) for c in columns)
    statement = sql.SQL(
        "INSERT INTO security_events ({cols}) VALUES ({vals}) "
        "ON CONFLICT (fingerprint) DO NOTHING RETURNING 1"
    ).format(
        cols=sql.SQL(", ").join(sql.Identifier(c) for c in columns),
        vals=placeholders,
    )

    stored = 0
    with conn.cursor() as cur:
        for event in events:
            params = {c: None for c in columns}
            params.update(_row_values(event))
            params["raw"] = psycopg.types.json.Jsonb(json.loads(params["raw"]))
            params["import_id"] = import_id
            cur.execute(statement, params)
            if cur.fetchone() is not None:
                stored += 1
    return InsertResult(stored=stored, duplicates=len(events) - stored)


def count_events(conn: psycopg.Connection, dataset_id: str | None = None) -> int:
    if dataset_id is None:
        return conn.execute("SELECT count(*) FROM security_events").fetchone()[0]
    return conn.execute(
        "SELECT count(*) FROM security_events WHERE dataset_id = %s", (dataset_id,)
    ).fetchone()[0]
