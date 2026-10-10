import os

import pytest


@pytest.fixture(autouse=True)
def isolated_environment(monkeypatch, tmp_path):
    """Unit tests must not depend on the developer's own .env or SF_* variables.

    We remove every SF_* variable and run each test from an empty temporary
    directory, so `Settings()` cannot find a real .env file.
    """
    for name in list(os.environ):
        if name.upper().startswith("SF_"):
            monkeypatch.delenv(name, raising=False)
    monkeypatch.chdir(tmp_path)
