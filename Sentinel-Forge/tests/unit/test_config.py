import pytest

from sentinelforge.config import ConfigError, Settings, load_settings


def test_defaults_are_local_and_have_no_passwords():
    settings = Settings()
    assert settings.db_host == "127.0.0.1"
    assert settings.db_port == 5432
    assert settings.db_admin_password is None
    assert settings.db_app_password is None


def test_values_are_read_from_environment(monkeypatch):
    monkeypatch.setenv("SF_DB_PORT", "55432")
    monkeypatch.setenv("SF_DB_APP_PASSWORD", "app-secret-value")
    settings = Settings()
    assert settings.db_port == 55432
    assert settings.app_connection().password.get_secret_value() == "app-secret-value"


def test_values_are_read_from_dotenv_file(tmp_path):
    # The unit-test fixture runs each test inside tmp_path.
    (tmp_path / ".env").write_text("SF_DB_NAME=labdb\nSF_DB_APP_PASSWORD=from-file\n")
    settings = Settings()
    assert settings.db_name == "labdb"
    assert settings.db_app_password.get_secret_value() == "from-file"


def test_environment_overrides_dotenv(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text("SF_DB_NAME=from_file\n")
    monkeypatch.setenv("SF_DB_NAME", "from_env")
    assert Settings().db_name == "from_env"


def test_passwords_never_appear_in_repr_or_summary():
    settings = Settings(db_app_password="app-secret-value", db_admin_password="admin-secret")
    text = repr(settings) + str(settings.safe_summary()) + repr(settings.app_connection())
    assert "app-secret-value" not in text
    assert "admin-secret" not in text
    assert settings.safe_summary()["db_app_password"] == "set (hidden)"


def test_connection_description_has_no_password():
    params = Settings(db_app_password="app-secret-value").app_connection()
    assert params.describe() == "sentinelforge_app@127.0.0.1:5432/sentinelforge"


def test_missing_password_gives_actionable_error():
    with pytest.raises(ConfigError, match="SF_DB_APP_PASSWORD is not set"):
        Settings().app_connection()


def test_placeholder_password_is_refused():
    settings = Settings(db_admin_password="change-me")
    with pytest.raises(ConfigError, match="placeholder"):
        settings.admin_connection()
    assert settings.safe_summary()["db_admin_password"].startswith("PLACEHOLDER")


@pytest.mark.parametrize(
    "bad_name", ["Sentinel", "app-user", 'x"; DROP ROLE postgres; --', "", "1abc", "a" * 64]
)
def test_unsafe_database_identifiers_are_rejected(monkeypatch, bad_name):
    monkeypatch.setenv("SF_DB_APP_USER", bad_name)
    with pytest.raises(ConfigError, match="SF_DB_APP_USER"):
        load_settings()


def test_invalid_port_is_reported_by_name(monkeypatch):
    monkeypatch.setenv("SF_DB_PORT", "99999")
    with pytest.raises(ConfigError, match="SF_DB_PORT"):
        load_settings()
