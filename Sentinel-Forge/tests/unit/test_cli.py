import json
import shutil

import pytest

from sentinelforge import __version__
from sentinelforge.cli import EXIT_CONFIG, EXIT_DB_UNAVAILABLE, EXIT_OK, EXIT_PROBLEM, main


def test_version(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert __version__ in capsys.readouterr().out


def test_help_lists_commands(capsys):
    with pytest.raises(SystemExit):
        main(["--help"])
    out = capsys.readouterr().out
    for word in ("config", "events", "db"):
        assert word in out


def test_missing_subcommand_is_a_usage_error():
    with pytest.raises(SystemExit) as exc:
        main([])
    assert exc.value.code == 2


def test_validate_sample_file_succeeds(repo_root, capsys):
    code = main(["events", "validate", str(repo_root / "data/sample/phase1_events.jsonl")])
    out = capsys.readouterr().out
    assert code == EXIT_OK
    assert "Valid:    8" in out
    assert "Result: OK" in out


def test_validate_mixed_file_fails_and_lists_errors(fixtures_dir, capsys):
    code = main(["events", "validate", str(fixtures_dir / "mixed_events.jsonl")])
    out = capsys.readouterr().out
    assert code == EXIT_PROBLEM
    assert "Invalid:  8" in out
    assert "line 2" in out
    assert "INVALID RECORDS FOUND" in out


def test_max_errors_limits_output(fixtures_dir, capsys):
    main(["events", "validate", "--max-errors", "2", str(fixtures_dir / "mixed_events.jsonl")])
    out = capsys.readouterr().out
    assert "more (use --max-errors to show more)" in out


def test_max_errors_must_be_positive(fixtures_dir):
    with pytest.raises(SystemExit) as exc:
        main(["events", "validate", "--max-errors", "0", str(fixtures_dir / "mixed_events.jsonl")])
    assert exc.value.code == 2


def test_show_normalised_writes_json_lines_to_stdout(repo_root, capsys):
    sample = repo_root / "data/sample/phase1_events.jsonl"
    main(["events", "validate", "--show-normalised", str(sample)])
    captured = capsys.readouterr()
    lines = captured.out.strip().splitlines()
    assert len(lines) == 8
    second = json.loads(lines[1])
    assert second["event_time"] == "2026-10-10T09:01:05Z"  # +05:30 converted to UTC
    assert second["outcome"] == "failure"
    assert "Result: OK" in captured.err  # summary moves to stderr


def test_missing_file_is_a_usage_error(capsys):
    assert main(["events", "validate", "nope.jsonl"]) == EXIT_CONFIG
    assert "file not found" in capsys.readouterr().err


def test_non_utf8_file_is_reported(tmp_path, capsys):
    path = tmp_path / "latin1.jsonl"
    path.write_bytes(b'{"user": "caf\xe9"}\n')
    assert main(["events", "validate", str(path)]) == EXIT_CONFIG
    assert "not UTF-8" in capsys.readouterr().err


def test_config_show_hides_passwords(tmp_path, capsys):
    (tmp_path / ".env").write_text("SF_DB_APP_PASSWORD=very-secret-value\n")
    assert main(["config", "show"]) == EXIT_OK
    out = capsys.readouterr().out
    assert "very-secret-value" not in out
    assert "set (hidden)" in out


def test_db_status_without_password_is_a_config_error(capsys):
    assert main(["db", "status"]) == EXIT_CONFIG
    assert "SF_DB_APP_PASSWORD is not set" in capsys.readouterr().err


def test_db_status_with_unreachable_server(monkeypatch, capsys):
    # Port 1 on localhost is closed, so the connection is refused immediately.
    monkeypatch.setenv("SF_DB_PORT", "1")
    monkeypatch.setenv("SF_DB_APP_PASSWORD", "app-secret-value")
    monkeypatch.setenv("SF_DB_CONNECT_TIMEOUT", "2")
    assert main(["db", "status"]) == EXIT_DB_UNAVAILABLE
    err = capsys.readouterr().err
    assert "cannot connect as sentinelforge_app@127.0.0.1:1/sentinelforge" in err
    assert "hint: PostgreSQL is not running" in err
    assert "app-secret-value" not in err


def test_sample_file_is_unchanged_by_validation(repo_root, tmp_path):
    # Validation must be read-only.
    source = repo_root / "data/sample/phase1_events.jsonl"
    copy = tmp_path / "copy.jsonl"
    shutil.copy(source, copy)
    before = copy.read_bytes()
    main(["events", "validate", str(copy)])
    assert copy.read_bytes() == before
