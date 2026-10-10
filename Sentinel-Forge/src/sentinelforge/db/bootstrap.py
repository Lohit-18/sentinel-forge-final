"""One-time database setup: the least-privilege application role and schema.

Two roles keep the lab safer:

* **admin role** (``SF_DB_ADMIN_USER``): owns the schema and creates tables.
  Only setup scripts and migrations use it.
* **app role** (``SF_DB_APP_USER``): used by SentinelForge at runtime. It can
  SELECT, INSERT and UPDATE rows, but cannot CREATE, DROP, ALTER or DELETE.
  If the application has a bug, or an attacker abuses it, the damage is
  limited, and the investigation history cannot be deleted through the app.

Running bootstrap more than once is safe (it is idempotent): an existing role
gets its password and limits refreshed instead of failing.

Why the SQL below is "composed" instead of parameterised
-------------------------------------------------------
Normal queries pass values as parameters (``WHERE name = %s``), which prevents
SQL injection. PostgreSQL does not allow parameters for *identifiers* (role or
schema names) or inside DDL commands such as ``CREATE ROLE``. For those,
``psycopg.sql.Identifier`` and ``psycopg.sql.Literal`` quote each value
safely. We also validate the names with a strict pattern in ``config.py``.
"""

from __future__ import annotations

from dataclasses import dataclass

import psycopg
from psycopg import sql
from pydantic import SecretStr

from sentinelforge.config import Settings
from sentinelforge.db.connect import connect


@dataclass(frozen=True)
class BootstrapResult:
    role_created: bool
    app_user: str
    schema: str
    database: str


def build_statements(
    *,
    database: str,
    schema: str,
    app_user: str,
    app_password: SecretStr,
    role_exists: bool,
) -> list[sql.Composed]:
    """Return the SQL statements bootstrap will run, in order.

    Kept separate from execution so unit tests can check the SQL without a
    database.
    """
    db = sql.Identifier(database)
    sch = sql.Identifier(schema)
    app = sql.Identifier(app_user)
    # Note: the password travels to the server inside this statement. Do not
    # enable statement logging (log_statement = 'all') on a server you bootstrap.
    pw = sql.Literal(app_password.get_secret_value())

    if role_exists:
        # Only refresh the password. Changing attributes such as SUPERUSER needs
        # superuser rights, which the admin role may not have (native installs).
        # verify_app_role() checks the attributes separately afterwards.
        role_stmt = sql.SQL("ALTER ROLE {} WITH LOGIN PASSWORD {}").format(app, pw)
    else:
        role_stmt = sql.SQL(
            "CREATE ROLE {} WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION "
            "NOBYPASSRLS PASSWORD {}"
        ).format(app, pw)

    return [
        role_stmt,
        # Only roles we explicitly allow may connect to this database.
        sql.SQL("REVOKE CONNECT, TEMPORARY ON DATABASE {} FROM PUBLIC").format(db),
        sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(db, app),
        # Nobody but the admin may create objects in the default "public" schema.
        sql.SQL("REVOKE CREATE ON SCHEMA public FROM PUBLIC"),
        # The SentinelForge schema is owned by the admin role running bootstrap.
        sql.SQL("CREATE SCHEMA IF NOT EXISTS {} AUTHORIZATION CURRENT_USER").format(sch),
        sql.SQL("REVOKE ALL ON SCHEMA {} FROM PUBLIC").format(sch),
        sql.SQL("GRANT USAGE ON SCHEMA {} TO {}").format(sch, app),
        # Tables and sequences the admin creates later (in migrations) automatically
        # grant the app role these rights, and nothing more. No DELETE, no DDL.
        sql.SQL(
            "ALTER DEFAULT PRIVILEGES IN SCHEMA {} GRANT SELECT, INSERT, UPDATE ON TABLES TO {}"
        ).format(sch, app),
        sql.SQL(
            "ALTER DEFAULT PRIVILEGES IN SCHEMA {} GRANT USAGE, SELECT ON SEQUENCES TO {}"
        ).format(sch, app),
        # Unqualified table names used by the app resolve to the SentinelForge schema.
        sql.SQL("ALTER ROLE {} IN DATABASE {} SET search_path = {}").format(app, db, sch),
    ]


class UnsafeRoleError(Exception):
    """The app role already exists with more power than it should have."""


_ELEVATED_ATTRIBUTES_SQL = """
SELECT rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolbypassrls
FROM pg_roles WHERE rolname = %s
"""


def verify_app_role(conn: psycopg.Connection, role: str) -> None:
    """Refuse to continue if the app role has any elevated attribute."""
    row = conn.execute(_ELEVATED_ATTRIBUTES_SQL, (role,)).fetchone()
    names = ("SUPERUSER", "CREATEDB", "CREATEROLE", "REPLICATION", "BYPASSRLS")
    elevated = [name for name, flag in zip(names, row, strict=True) if flag]
    if elevated:
        raise UnsafeRoleError(
            f"role '{role}' has {', '.join(elevated)}. An application role must not. "
            f"Remove them as a superuser, e.g. ALTER ROLE {role} NO{elevated[0]};"
        )


def role_exists(conn: psycopg.Connection, role: str) -> bool:
    # A normal parameterised query: the role name is passed as a value.
    row = conn.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (role,)).fetchone()
    return row is not None


def bootstrap(settings: Settings) -> BootstrapResult:
    """Create or refresh the app role and schema. Runs in one transaction."""
    admin = settings.admin_connection()
    app = settings.app_connection()  # validates that the app password is set

    with connect(admin) as conn, conn.transaction():
        exists = role_exists(conn, settings.db_app_user)
        for statement in build_statements(
            database=settings.db_name,
            schema=settings.db_schema,
            app_user=settings.db_app_user,
            app_password=app.password,
            role_exists=exists,
        ):
            conn.execute(statement)
        verify_app_role(conn, settings.db_app_user)

    return BootstrapResult(
        role_created=not exists,
        app_user=settings.db_app_user,
        schema=settings.db_schema,
        database=settings.db_name,
    )
