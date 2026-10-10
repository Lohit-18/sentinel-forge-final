"""Database health check, run as the application role."""

from __future__ import annotations

from dataclasses import dataclass

from sentinelforge.config import ConnectionParams
from sentinelforge.db.connect import connect


@dataclass(frozen=True)
class DatabaseStatus:
    server_version: str
    database: str
    user: str
    is_superuser: bool
    schema: str
    schema_exists: bool
    can_use_schema: bool
    can_create_in_schema: bool

    @property
    def least_privilege_ok(self) -> bool:
        """True when the app role can use the schema but cannot change it."""
        return (
            self.schema_exists
            and self.can_use_schema
            and not self.can_create_in_schema
            and not self.is_superuser
        )


_STATUS_SQL = """
SELECT
    current_setting('server_version')                         AS server_version,
    current_database()                                         AS database,
    current_user                                               AS username,
    (SELECT rolsuper FROM pg_roles WHERE rolname = current_user) AS is_superuser,
    EXISTS (SELECT 1 FROM pg_namespace WHERE nspname = %(schema)s) AS schema_exists
"""

_PRIVILEGE_SQL = """
SELECT
    has_schema_privilege(current_user, %(schema)s, 'USAGE')  AS can_use,
    has_schema_privilege(current_user, %(schema)s, 'CREATE') AS can_create
"""


def get_status(params: ConnectionParams, schema: str) -> DatabaseStatus:
    with connect(params) as conn:
        version, database, user, is_superuser, schema_exists = conn.execute(
            _STATUS_SQL, {"schema": schema}
        ).fetchone()

        can_use = can_create = False
        if schema_exists:
            can_use, can_create = conn.execute(_PRIVILEGE_SQL, {"schema": schema}).fetchone()

    return DatabaseStatus(
        server_version=version,
        database=database,
        user=user,
        is_superuser=bool(is_superuser),
        schema=schema,
        schema_exists=bool(schema_exists),
        can_use_schema=bool(can_use),
        can_create_in_schema=bool(can_create),
    )
