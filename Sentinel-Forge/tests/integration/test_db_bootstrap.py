"""Prove the least-privilege design against a real PostgreSQL server."""

import psycopg
import pytest
from psycopg import sql

from sentinelforge.config import Settings
from sentinelforge.db.bootstrap import UnsafeRoleError, bootstrap
from sentinelforge.db.connect import DatabaseUnavailable, connect
from sentinelforge.db.status import get_status

pytestmark = pytest.mark.integration


def test_bootstrap_creates_role_then_is_idempotent(test_settings):
    first = bootstrap(test_settings)
    second = bootstrap(test_settings)
    assert first.role_created is True
    assert second.role_created is False


def test_status_reports_least_privilege(test_settings):
    bootstrap(test_settings)
    status = get_status(test_settings.app_connection(), test_settings.db_schema)
    assert status.user == test_settings.db_app_user
    assert status.schema_exists
    assert status.can_use_schema
    assert not status.can_create_in_schema
    assert not status.is_superuser
    assert status.least_privilege_ok


def test_status_flags_missing_schema(test_settings, admin_conn):
    bootstrap(test_settings)
    admin_conn.execute(
        sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(test_settings.db_schema))
    )
    status = get_status(test_settings.app_connection(), test_settings.db_schema)
    assert not status.schema_exists
    assert not status.least_privilege_ok


def test_app_role_cannot_create_tables(test_settings):
    bootstrap(test_settings)
    create = sql.SQL("CREATE TABLE {}.should_fail (id int)").format(
        sql.Identifier(test_settings.db_schema)
    )
    with (
        connect(test_settings.app_connection(), autocommit=True) as conn,
        pytest.raises(psycopg.errors.InsufficientPrivilege),
    ):
        conn.execute(create)


def test_app_role_can_read_write_but_not_delete(test_settings, admin_conn):
    bootstrap(test_settings)
    # Tables are created by the admin role, as migrations will be in Phase 2.
    admin_conn.execute(
        sql.SQL("CREATE TABLE {}.probe (id bigserial PRIMARY KEY, note text NOT NULL)").format(
            sql.Identifier(test_settings.db_schema)
        )
    )

    with connect(test_settings.app_connection(), autocommit=True) as app:
        # bootstrap set the app role's search_path, so the short name works.
        app.execute("INSERT INTO probe (note) VALUES (%s)", ("first",))
        app.execute("UPDATE probe SET note = %s WHERE note = %s", ("updated", "first"))
        assert app.execute("SELECT note FROM probe").fetchone() == ("updated",)

        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            app.execute("DELETE FROM probe")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            app.execute("DROP TABLE probe")


def test_wrong_app_password_is_reported_without_leaking_it(test_settings):
    bootstrap(test_settings)
    data = test_settings.model_dump()
    data["db_app_password"] = "definitely-wrong-password"
    wrong = Settings.model_validate(data)
    with pytest.raises(DatabaseUnavailable) as exc_info:
        get_status(wrong.app_connection(), wrong.db_schema)
    message = str(exc_info.value)
    assert "password authentication failed" in message
    assert "definitely-wrong-password" not in message
    assert "does not match" in exc_info.value.hint


def test_bootstrap_refuses_an_app_role_with_elevated_rights(test_settings, admin_conn):
    bootstrap(test_settings)
    role = sql.Identifier(test_settings.db_app_user)
    try:
        admin_conn.execute(sql.SQL("ALTER ROLE {} CREATEDB").format(role))
    except psycopg.errors.InsufficientPrivilege:
        pytest.skip("this admin role cannot grant CREATEDB, so the scenario cannot occur")
    with pytest.raises(UnsafeRoleError, match="CREATEDB"):
        bootstrap(test_settings)
