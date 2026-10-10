from sentinelforge.events.validate import MAX_LINE_BYTES, validate_jsonl


def test_sample_dataset_is_fully_valid(repo_root):
    report = validate_jsonl(repo_root / "data" / "sample" / "phase1_events.jsonl")
    assert report.ok
    assert report.total == 8
    assert report.valid == 8
    categories = {event.category.value for event in report.valid_events}
    assert categories == {
        "authentication",
        "endpoint",
        "network",
        "system",
        "application",
        "external_alert",
    }


def test_mixed_file_reports_each_bad_line(fixtures_dir):
    report = validate_jsonl(fixtures_dir / "mixed_events.jsonl")

    assert report.total == 9  # the blank line is skipped, not counted
    assert report.valid == 1
    assert report.invalid == 8
    assert not report.ok
    assert report.invalid_lines == {2, 3, 4, 5, 6, 7, 9, 10}

    by_line = {}
    for error in report.errors:
        by_line.setdefault(error.line_number, []).append(error)

    assert "no time zone" in by_line[2][0].message
    assert "must include 'user'" in by_line[3][0].message
    assert by_line[4][0].field == "dst_ip"
    assert by_line[5][0].field == "dst_port"
    assert {e.field for e in by_line[6]} >= {"usr"}
    assert "not valid JSON" in by_line[7][0].message
    assert "JSON object" in by_line[9][0].message
    assert "dst_ip" in by_line[10][0].message


def test_error_messages_do_not_echo_input_values(tmp_path):
    secret = "Sup3rS3cretPassw0rd"
    path = tmp_path / "leak.jsonl"
    path.write_text(
        '{"event_time": "2026-10-10T09:00:00Z", "category": "authentication", '
        '"action": "logon", "source_type": "synthetic_auth", "source_host": "ws-01", '
        f'"user": "alice.lab", "src_ip": "{secret}"}}\n',
        encoding="utf-8",
    )
    report = validate_jsonl(path)
    assert report.invalid == 1
    assert all(secret not in error.message for error in report.errors)


def test_oversized_line_is_rejected_without_parsing(tmp_path):
    path = tmp_path / "big.jsonl"
    path.write_text('{"x": "' + "a" * MAX_LINE_BYTES + '"}\n', encoding="utf-8")
    report = validate_jsonl(path)
    assert report.invalid == 1
    assert report.errors[0].message == "line is too long"


def test_empty_file_is_valid_with_zero_records(tmp_path):
    path = tmp_path / "empty.jsonl"
    path.write_text("\n\n", encoding="utf-8")
    report = validate_jsonl(path)
    assert report.total == 0
    assert report.ok
