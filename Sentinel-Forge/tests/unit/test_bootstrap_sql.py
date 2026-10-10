"""Check the bootstrap SQL without a database.

``Composed.as_string(None)`` renders the statement using psycopg's own quoting
rules, so we can see exactly what PostgreSQL would receive.
"""

import pytest
from pydantic import SecretStr

from sentinelforge.db.bootstrap import build_statements


def render(**overrides) -> list[str]:
    kwargs = {
        "database": "sentinelforge",
        "schema": "sentinelforge",
        "app_user": "sentinelforge_app",
        "app_password": SecretStr("pa'ss"),
        "role_exists": False,
    }
    kwargs.update(overrides)
    return [statement.as_string(None) for statement in build_statements(**kwargs)]


def test_new_role_is_created_with_explicit_limits():
    first = render()[0]
    assert first.startswith('CREATE ROLE "sentinelforge_app" WITH LOGIN NOSUPERUSER')
    for limit in ("NOCREATEDB", "NOCREATEROLE", "NOREPLICATION", "NOBYPASSRLS"):
        assert limit in first


def test_existing_role_only_gets_its_password_refreshed():
    # Regression test: ALTER ROLE ... NOSUPERUSER fails when the admin role is
    # not a superuser (native installs). Attributes are verified separately.
    first = render(role_exists=True)[0]
    assert first == """ALTER ROLE "sentinelforge_app" WITH LOGIN PASSWORD 'pa''ss'"""


def test_password_quotes_are_escaped():
    # A single quote inside the password must be doubled, not end the string.
    assert "PASSWORD 'pa''ss'" in render()[0]


def test_app_role_gets_no_delete_or_ddl_rights():
    sql = "\n".join(render())
    assert "GRANT SELECT, INSERT, UPDATE ON TABLES" in sql
    assert "DELETE" not in sql
    assert "TRUNCATE" not in sql
    assert "GRANT CREATE" not in sql
    assert "GRANT ALL" not in sql


def test_public_access_is_revoked():
    sql = "\n".join(render())
    assert 'REVOKE CONNECT, TEMPORARY ON DATABASE "sentinelforge" FROM PUBLIC' in sql
    assert 'REVOKE ALL ON SCHEMA "sentinelforge" FROM PUBLIC' in sql
    assert "REVOKE CREATE ON SCHEMA public FROM PUBLIC" in sql


def test_search_path_points_at_lab_schema():
    assert render()[-1] == (
        'ALTER ROLE "sentinelforge_app" IN DATABASE "sentinelforge" '
        'SET search_path = "sentinelforge"'
    )


@pytest.mark.parametrize("name", ['evil"; DROP SCHEMA public; --', "Mixed Case"])
def test_identifiers_are_always_quoted(name):
    # Settings blocks names like these, but even if one got through,
    # psycopg quotes it as a single identifier.
    statement = render(app_user=name)[2]  # GRANT CONNECT ... TO <app_user>
    quoted = '"' + name.replace('"', '""') + '"'
    assert statement.endswith(f"TO {quoted}")


def test_connection_hints_cover_common_failures():
    from sentinelforge.db.connect import _hint_for

    assert "does not match" in _hint_for('FATAL:  password authentication failed for user "x"')
    assert "not running" in _hint_for("Connection refused")
    assert _hint_for("something unexpected") is None
