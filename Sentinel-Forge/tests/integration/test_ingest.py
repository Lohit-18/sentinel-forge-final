"""Ingestion and migrations against a real PostgreSQL server."""

import pytest
from psycopg import sql

from sentinelforge.db.bootstrap import bootstrap
from sentinelforge.db.connect import connect
from sentinelforge.db.events_repo import count_events
from sentinelforge.db.migrate import migrate
from sentinelforge.events.ingest import ingest_file

pytestmark = pytest.mark.integration


@pytest.fixture
def ready(test_settings):
    """A bootstrapped, migrated throwaway schema."""
    bootstrap(test_settings)
    migrate(test_settings)
    return test_settings


def write(tmp_path, name, text):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def test_migrate_creates_tables_and_is_idempotent(test_settings):
    bootstrap(test_settings)
    first = migrate(test_settings)
    second = migrate(test_settings)
    assert "0001" in first.applied
    assert second.applied == []
    assert "0001" in second.already_current

    schema = sql.Identifier(test_settings.db_schema)
    with connect(test_settings.app_connection()) as conn:
        # Data tables start empty.
        for table in ("security_events", "dataset_imports"):
            rows = conn.execute(
                sql.SQL("SELECT count(*) FROM {}.{}").format(schema, sql.Identifier(table))
            ).fetchone()
            assert rows[0] == 0
        # schema_migrations records the one migration that ran.
        rows = conn.execute(
            sql.SQL("SELECT count(*) FROM {}.schema_migrations").format(schema)
        ).fetchone()
        assert rows[0] == 1


def test_ingest_stores_events(ready, tmp_path):
    path = write(
        tmp_path,
        "events.jsonl",
        '{"event_time":"2026-01-05T09:00:00Z","category":"authentication","action":"logon",'
        '"outcome":"success","source_type":"synthetic_auth","source_host":"ws-01",'
        '"user":"alice.lab","source_event_id":"1"}\n'
        '{"event_time":"2026-01-05T09:01:00Z","category":"network","action":"connection",'
        '"source_type":"fw","source_host":"fw-01","dst_ip":"10.0.0.1","dst_port":443,'
        '"source_event_id":"2"}\n',
    )
    result = ingest_file(ready, path, dataset_id="test")
    assert result.stored == 2
    assert result.duplicates == 0
    assert result.invalid == 0
    with connect(ready.app_connection()) as conn:
        assert count_events(conn, "test") == 2


def test_reingesting_the_same_file_stores_nothing(ready, tmp_path):
    path = write(
        tmp_path,
        "events.jsonl",
        '{"event_time":"2026-01-05T09:00:00Z","category":"system","action":"service_start",'
        '"source_type":"siem","source_host":"h","source_event_id":"1"}\n',
    )
    first = ingest_file(ready, path, dataset_id="ds")
    second = ingest_file(ready, path, dataset_id="ds")
    assert first.stored == 1
    assert second.stored == 0
    assert second.duplicates == 1
    with connect(ready.app_connection()) as conn:
        assert count_events(conn) == 1


def test_invalid_records_are_skipped_but_valid_ones_are_stored(ready, tmp_path):
    path = write(
        tmp_path,
        "mixed.jsonl",
        '{"event_time":"2026-01-05T09:00:00Z","category":"system","action":"service_start",'
        '"source_type":"siem","source_host":"h","source_event_id":"1"}\n'
        '{"event_time":"no-timezone","category":"system","action":"service_stop",'
        '"source_type":"siem","source_host":"h"}\n',
    )
    result = ingest_file(ready, path, dataset_id="ds")
    assert result.stored == 1
    assert result.invalid == 1
    assert not result.ok


def test_event_time_and_ingested_at_are_both_recorded(ready, tmp_path):
    path = write(
        tmp_path,
        "e.jsonl",
        '{"event_time":"2026-01-05T09:00:00Z","category":"system","action":"service_start",'
        '"source_type":"siem","source_host":"h","source_event_id":"1"}\n',
    )
    ingest_file(ready, path, dataset_id="ds")
    schema = sql.Identifier(ready.db_schema)
    with connect(ready.app_connection()) as conn:
        row = conn.execute(
            sql.SQL("SELECT event_time, ingested_at FROM {}.security_events").format(schema)
        ).fetchone()
    event_time, ingested_at = row
    assert event_time.year == 2026
    assert ingested_at > event_time  # ingested now, event happened in January


def test_import_run_is_recorded(ready, tmp_path):
    path = write(
        tmp_path,
        "e.jsonl",
        '{"event_time":"2026-01-05T09:00:00Z","category":"system","action":"service_start",'
        '"source_type":"siem","source_host":"h","source_event_id":"1"}\n',
    )
    result = ingest_file(ready, path, dataset_id="ds")
    schema = sql.Identifier(ready.db_schema)
    with connect(ready.app_connection()) as conn:
        row = conn.execute(
            sql.SQL(
                "SELECT dataset_id, records_read, records_stored, status "
                "FROM {}.dataset_imports WHERE id = %s"
            ).format(schema),
            (result.import_id,),
        ).fetchone()
    assert row == ("ds", 1, 1, "completed")


def test_app_role_cannot_delete_events(ready, tmp_path):
    import psycopg

    path = write(
        tmp_path,
        "e.jsonl",
        '{"event_time":"2026-01-05T09:00:00Z","category":"system","action":"service_start",'
        '"source_type":"siem","source_host":"h","source_event_id":"1"}\n',
    )
    ingest_file(ready, path, dataset_id="ds")
    schema = sql.Identifier(ready.db_schema)
    with (
        connect(ready.app_connection(), autocommit=True) as conn,
        pytest.raises(psycopg.errors.InsufficientPrivilege),
    ):
        conn.execute(sql.SQL("DELETE FROM {}.security_events").format(schema))
