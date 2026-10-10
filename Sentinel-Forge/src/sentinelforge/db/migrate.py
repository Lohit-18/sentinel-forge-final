"""Apply SQL migrations in order, once each.

Each file in ``migrations/`` is named ``NNNN_description.sql``. The numeric
prefix sets the order. A file is applied once; its version is recorded in
``schema_migrations`` so re-running is safe. Each migration runs in its own
transaction, so a failure leaves the database on the last good version.

Migrations run as the **admin** role, which owns the schema. The application
role never creates or changes tables.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import psycopg
from psycopg import sql

from sentinelforge.config import PROJECT_ROOT, Settings
from sentinelforge.db.connect import connect

MIGRATIONS_DIR = PROJECT_ROOT / "migrations"
_FILENAME_RE = re.compile(r"^(\d{4})_[a-z0-9_]+\.sql$")


@dataclass(frozen=True)
class Migration:
    version: str
    path: Path

    @property
    def sql_text(self) -> str:
        return self.path.read_text(encoding="utf-8")


@dataclass(frozen=True)
class MigrationResult:
    applied: list[str]
    already_current: list[str]


def discover_migrations(directory: Path = MIGRATIONS_DIR) -> list[Migration]:
    migrations = []
    for path in sorted(directory.glob("*.sql")):
        match = _FILENAME_RE.match(path.name)
        if not match:
            raise ValueError(f"migration file has an unexpected name: {path.name}")
        migrations.append(Migration(version=match.group(1), path=path))
    versions = [m.version for m in migrations]
    if len(set(versions)) != len(versions):
        raise ValueError("two migrations share the same version number")
    return migrations


def _ensure_tracking_table(conn: psycopg.Connection, schema: str) -> None:
    conn.execute(
        sql.SQL(
            "CREATE TABLE IF NOT EXISTS {}.schema_migrations "
            "(version text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())"
        ).format(sql.Identifier(schema))
    )


def applied_versions(conn: psycopg.Connection, schema: str) -> set[str]:
    _ensure_tracking_table(conn, schema)
    rows = conn.execute(
        sql.SQL("SELECT version FROM {}.schema_migrations").format(sql.Identifier(schema))
    ).fetchall()
    return {row[0] for row in rows}


def migrate(settings: Settings, directory: Path = MIGRATIONS_DIR) -> MigrationResult:
    migrations = discover_migrations(directory)
    admin = settings.admin_connection()
    applied, current = [], []

    with connect(admin) as conn:
        # The admin role's search_path may not be set, so point it at our schema
        # for this session. Unqualified names in migrations then resolve correctly.
        conn.execute(sql.SQL("SET search_path = {}").format(sql.Identifier(settings.db_schema)))
        done = applied_versions(conn, settings.db_schema)

        for migration in migrations:
            if migration.version in done:
                current.append(migration.version)
                continue
            with conn.transaction():
                conn.execute(migration.sql_text)
                conn.execute(
                    sql.SQL("INSERT INTO {}.schema_migrations (version) VALUES (%s)").format(
                        sql.Identifier(settings.db_schema)
                    ),
                    (migration.version,),
                )
            applied.append(migration.version)

    return MigrationResult(applied=applied, already_current=current)
