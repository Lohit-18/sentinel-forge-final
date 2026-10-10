import pytest

from sentinelforge.events.readers import UnsupportedFormat, file_format, read_records


def write(tmp_path, name, text):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def test_file_format_detection(tmp_path):
    assert file_format(tmp_path / "a.jsonl") == "jsonl"
    assert file_format(tmp_path / "a.ndjson") == "jsonl"
    assert file_format(tmp_path / "a.csv") == "csv"
    with pytest.raises(UnsupportedFormat):
        file_format(tmp_path / "a.txt")


def test_csv_with_aliases_and_synonyms(tmp_path):
    path = write(
        tmp_path,
        "in.csv",
        "TimeCreated,Computer,sensor,event_category,event_action,result,AccountName\n"
        "2026-01-05T09:00:00Z,WS-01,siem,auth,logon,FAILED,alice.lab\n",
    )
    records = list(read_records(path, normalise=True))
    assert len(records) == 1
    event = records[0].event
    assert event is not None
    assert event.outcome.value == "failure"
    assert event.source_host == "ws-01"


def test_csv_empty_cells_become_absent(tmp_path):
    path = write(
        tmp_path,
        "in.csv",
        "event_time,category,action,source_type,source_host,user,src_ip\n"
        "2026-01-05T09:00:00Z,system,service_start,siem,srv-01,,\n",
    )
    event = next(read_records(path, normalise=True)).event
    assert event is not None
    assert event.user is None
    assert event.src_ip is None


def test_jsonl_bad_line_does_not_stop_the_file(tmp_path):
    path = write(
        tmp_path,
        "in.jsonl",
        '{"event_time":"2026-01-05T09:00:00Z","category":"system","action":"service_start",'
        '"source_type":"siem","source_host":"h"}\n'
        "not json\n"
        '{"event_time":"2026-01-05T09:01:00Z","category":"system","action":"service_stop",'
        '"source_type":"siem","source_host":"h"}\n',
    )
    records = list(read_records(path, normalise=True))
    assert len(records) == 3
    assert records[0].event is not None
    assert records[1].event is None and records[1].errors
    assert records[2].event is not None


def test_empty_csv_yields_nothing(tmp_path):
    path = write(tmp_path, "in.csv", "")
    assert list(read_records(path)) == []
