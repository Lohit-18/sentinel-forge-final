"""Configuration loaded from environment variables and the local .env file.

Every setting uses the ``SF_`` prefix, for example ``SF_DB_HOST``.
Real environment variables take priority over values in ``.env``.

Passwords are stored as ``SecretStr`` so they are never printed by accident
(``repr`` and ``str`` show ``**********`` instead of the value).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# PostgreSQL identifiers we create (roles, schema, database). We restrict them to
# simple lowercase names. psycopg also quotes identifiers safely, so this is a
# second layer of defence and keeps names predictable.
IDENTIFIER_RE = re.compile(r"[a-z_][a-z0-9_]{0,62}")

PLACEHOLDER_PREFIX = "change-me"

# The repository root (src/sentinelforge/config.py -> ../../). Paths to configs,
# rules and data are resolved from here, so commands work from any directory.
PROJECT_ROOT = Path(__file__).resolve().parents[2]

ANALYST_RE = re.compile(r"[a-z][a-z0-9._-]{1,63}")


class ConfigError(Exception):
    """Raised when required configuration is missing or unsafe."""


@dataclass(frozen=True)
class ConnectionParams:
    """Everything needed to open one PostgreSQL connection."""

    host: str
    port: int
    dbname: str
    user: str
    password: SecretStr
    connect_timeout: int = 5

    def to_psycopg_kwargs(self) -> dict[str, Any]:
        # Passing keyword arguments (instead of building a URL string) means
        # special characters in passwords never need escaping.
        return {
            "host": self.host,
            "port": self.port,
            "dbname": self.dbname,
            "user": self.user,
            "password": self.password.get_secret_value(),
            "connect_timeout": self.connect_timeout,
            "application_name": "sentinelforge",
        }

    def describe(self) -> str:
        """A safe, password-free description such as ``user@host:5432/db``."""
        return f"{self.user}@{self.host}:{self.port}/{self.dbname}"


class Settings(BaseSettings):
    """All SentinelForge settings. Defaults are safe for a local lab."""

    model_config = SettingsConfigDict(
        env_prefix="SF_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    db_mode: Literal["native", "docker"] = "native"
    db_host: str = "127.0.0.1"
    db_port: int = Field(default=5432, ge=1, le=65535)
    db_name: str = "sentinelforge"
    db_schema: str = "sentinelforge"
    db_admin_user: str = "sentinelforge_admin"
    db_admin_password: SecretStr | None = None
    db_app_user: str = "sentinelforge_app"
    db_app_password: SecretStr | None = None
    db_connect_timeout: int = Field(default=5, ge=1, le=60)
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    # Lab configuration and data locations.
    config_dir: Path = PROJECT_ROOT / "configs"
    data_dir: Path = PROJECT_ROOT / "data"
    reports_dir: Path = PROJECT_ROOT / "reports"

    # Analyst names offered by the dashboard and accepted by the CLI. This is a
    # convenience for a single-user lab, not authentication (see docs/threat-model.md).
    analysts: str = "analyst.one,analyst.two,analyst.three"

    @property
    def rules_dir(self) -> Path:
        return self.config_dir / "rules"

    @property
    def inventory_path(self) -> Path:
        return self.config_dir / "lab_inventory.yml"

    @property
    def analyst_names(self) -> list[str]:
        return [name.strip() for name in self.analysts.split(",") if name.strip()]

    @field_validator("analysts")
    @classmethod
    def _check_analysts(cls, value: str) -> str:
        names = [name.strip() for name in value.split(",") if name.strip()]
        if not names:
            raise ValueError("at least one analyst name is required")
        for name in names:
            if not ANALYST_RE.fullmatch(name):
                raise ValueError(f"invalid analyst name {name!r} (use letters, digits, . _ -)")
        return value

    @field_validator("db_name", "db_schema", "db_admin_user", "db_app_user")
    @classmethod
    def _check_identifier(cls, value: str) -> str:
        if not IDENTIFIER_RE.fullmatch(value):
            raise ValueError(
                "must be 1-63 characters: lowercase letters, digits or underscore, "
                "starting with a letter or underscore"
            )
        return value

    def _params(self, user: str, password: SecretStr | None, env_name: str) -> ConnectionParams:
        if password is None or not password.get_secret_value():
            raise ConfigError(f"{env_name} is not set. Run `bash scripts/setup.sh` or edit .env.")
        if password.get_secret_value().startswith(PLACEHOLDER_PREFIX):
            raise ConfigError(
                f"{env_name} still has the placeholder value from .env.example. "
                "Replace it with a real password."
            )
        return ConnectionParams(
            host=self.db_host,
            port=self.db_port,
            dbname=self.db_name,
            user=user,
            password=password,
            connect_timeout=self.db_connect_timeout,
        )

    def app_connection(self) -> ConnectionParams:
        """Connection details for the least-privilege application role."""
        return self._params(self.db_app_user, self.db_app_password, "SF_DB_APP_PASSWORD")

    def admin_connection(self) -> ConnectionParams:
        """Connection details for the admin role (setup and migrations only)."""
        return self._params(self.db_admin_user, self.db_admin_password, "SF_DB_ADMIN_PASSWORD")

    def safe_summary(self) -> dict[str, str]:
        """Settings that are safe to display. Passwords show only set / not set."""

        def password_state(secret: SecretStr | None) -> str:
            if secret is None or not secret.get_secret_value():
                return "not set"
            if secret.get_secret_value().startswith(PLACEHOLDER_PREFIX):
                return "PLACEHOLDER - replace it"
            return "set (hidden)"

        return {
            "db_mode": self.db_mode,
            "db_host": self.db_host,
            "db_port": str(self.db_port),
            "db_name": self.db_name,
            "db_schema": self.db_schema,
            "db_admin_user": self.db_admin_user,
            "db_admin_password": password_state(self.db_admin_password),
            "db_app_user": self.db_app_user,
            "db_app_password": password_state(self.db_app_password),
            "log_level": self.log_level,
            "config_dir": str(self.config_dir),
            "analysts": ", ".join(self.analyst_names),
        }


def load_settings() -> Settings:
    """Load settings, turning validation problems into a readable ConfigError."""
    from pydantic import ValidationError

    try:
        return Settings()
    except ValidationError as exc:
        problems = "; ".join(
            f"SF_{'_'.join(str(p) for p in err['loc']).upper()}: {err['msg']}"
            for err in exc.errors(include_input=False)
        )
        raise ConfigError(f"invalid configuration: {problems}") from None
