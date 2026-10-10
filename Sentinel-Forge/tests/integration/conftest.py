"""Integration tests run against a real PostgreSQL server.

They are skipped unless SF_RUN_INTEGRATION=1 (``bash scripts/run_tests.sh
--integration`` sets it). When enabled, a missing or unreachable database is a
failure, not a silent skip, so a broken setup cannot look like a passing build.

The tests never touch your real lab role or schema. They create a separate
role (``sf_test_app``) and schema (``sf_test``) and remove both afterwards.
"""

import os
import secrets

import pytest
from psycopg import sql

from sentinelforge.config import Settings
from sentinelforge.db.connect import connect


@pytest.fixture(autouse=True)
def _require_integration_opt_in():
    if os.environ.get("SF_RUN_INTEGRATION") != "1":
        pytest.skip("set SF_RUN_INTEGRATION=1 to run database tests")


def _drop_test_objects(settings: Settings) -> None:
    schema = sql.Identifier(settings.db_schema)
    role = sql.Identifier(settings.db_app_user)
    database = sql.Identifier(settings.db_name)
    with connect(settings.admin_connection(), autocommit=True) as conn:
        # Dropping the schema also removes the role's schema grants and the
        # default privileges defined in it.
        conn.execute(sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(schema))
        found = conn.execute(
            "SELECT 1 FROM pg_roles WHERE rolname = %s", (settings.db_app_user,)
        ).fetchone()
        if found:
            # The last remaining privilege is CONNECT on the database. Revoking it
            # explicitly (instead of DROP OWNED) also works when the admin role is
            # not a superuser.
            conn.execute(sql.SQL("REVOKE ALL ON DATABASE {} FROM {}").format(database, role))
            conn.execute(sql.SQL("DROP ROLE {}").format(role))


@pytest.fixture
def test_settings():
    """Real connection settings, but with a throwaway schema and app role."""
    base = Settings()
    if base.db_admin_password is None:
        pytest.fail("SF_DB_ADMIN_PASSWORD must be set to run integration tests")
    data = base.model_dump()
    data.update(
        db_schema="sf_test",
        db_app_user="sf_test_app",
        db_app_password=secrets.token_urlsafe(24),
    )
    settings = Settings.model_validate(data)
    _drop_test_objects(settings)
    yield settings
    _drop_test_objects(settings)


@pytest.fixture
def admin_conn(test_settings):
    with connect(test_settings.admin_connection(), autocommit=True) as conn:
        yield conn
