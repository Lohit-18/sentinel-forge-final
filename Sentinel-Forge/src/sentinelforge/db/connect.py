"""Opening PostgreSQL connections with safe, helpful error messages."""

from __future__ import annotations

import psycopg

from sentinelforge.config import ConnectionParams

# Known failure reasons and what to do about them.
_HINTS = (
    (
        "password authentication failed",
        "the password in .env does not match the database role. For the app role, "
        "`bash scripts/start_lab.sh` resets it from .env.",
    ),
    (
        "does not exist",
        "the database or role does not exist yet. See docs/installation.md.",
    ),
    (
        "connection refused",
        "PostgreSQL is not running or uses another port. Try: bash scripts/start_lab.sh",
    ),
    (
        "timeout",
        "PostgreSQL did not answer in time. Check SF_DB_HOST and SF_DB_PORT in .env.",
    ),
)


class DatabaseUnavailable(Exception):
    """The database could not be reached or refused the login."""

    def __init__(self, message: str, hint: str | None = None) -> None:
        super().__init__(message)
        self.hint = hint


def _hint_for(reason: str) -> str | None:
    lowered = reason.lower()
    for needle, hint in _HINTS:
        if needle in lowered:
            return hint
    return None


def connect(params: ConnectionParams, *, autocommit: bool = False) -> psycopg.Connection:
    """Open a connection, or raise ``DatabaseUnavailable`` with a readable reason.

    The error message names the user, host and port, never the password.
    """
    try:
        return psycopg.connect(**params.to_psycopg_kwargs(), autocommit=autocommit)
    except psycopg.OperationalError as exc:
        # psycopg messages can span several lines. The first line holds the
        # reason ("... failed: Connection refused"); later lines are advice.
        text = str(exc)
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        reason = lines[0] if lines else exc.__class__.__name__
        raise DatabaseUnavailable(
            f"cannot connect as {params.describe()}: {reason}", hint=_hint_for(text)
        ) from None
