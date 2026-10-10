from sentinelforge.events.normalise import normalise_record
from sentinelforge.events.schema import EventCategory, Outcome, SecurityEvent, Severity


def test_field_aliases_are_renamed():
    result = normalise_record(
        {
            "TimeCreated": "2026-01-05T09:00:00Z",
            "Computer": "WS-01",
            "sensor": "winlog",
            "event_category": "auth",
            "event_action": "logon",
            "result": "SUCCEEDED",
            "AccountName": "alice.lab",
            "source_ip": "10.0.0.5",
        }
    )
    event = SecurityEvent.model_validate(result.data)
    assert event.category is EventCategory.AUTHENTICATION
    assert event.outcome is Outcome.SUCCESS
    assert event.source_host == "ws-01"
    assert event.user == "alice.lab"
    assert str(event.src_ip) == "10.0.0.5"
    assert result.unmapped_fields == []


def test_value_synonyms_are_translated():
    for raw, expected in [
        ("FAILED", "failure"),
        ("denied", "failure"),
        ("blocked", "failure"),
        ("allowed", "success"),
        ("ok", "success"),
    ]:
        result = normalise_record(
            {
                "timestamp": "2026-01-05T09:00:00Z",
                "host": "h",
                "sensor": "s",
                "category": "network",
                "action": "connection",
                "result": raw,
                "dst_ip": "10.0.0.1",
            }
        )
        assert result.data["outcome"] == expected


def test_severity_synonyms():
    for raw, expected in [("warn", "low"), ("information", "informational"), ("crit", "critical")]:
        result = normalise_record({"level": raw})
        assert result.data["severity"] == expected


def test_unmapped_fields_are_reported_and_kept_in_raw():
    result = normalise_record(
        {
            "event_time": "2026-01-05T09:00:00Z",
            "category": "system",
            "action": "service_start",
            "source_type": "siem",
            "source_host": "h",
            "mystery_field": "value",
            "another": 1,
        }
    )
    assert result.unmapped_fields == ["another", "mystery_field"]
    assert result.data["raw"]["mystery_field"] == "value"


def test_canonical_fields_win_over_aliases():
    # If both "source_host" and its alias "host" appear, the canonical one wins.
    result = normalise_record(
        {
            "event_time": "2026-01-05T09:00:00Z",
            "category": "system",
            "action": "service_start",
            "source_type": "siem",
            "source_host": "canonical",
            "host": "alias",
        }
    )
    assert result.data["source_host"] == "canonical"
    assert "host" in result.unmapped_fields


def test_original_record_is_preserved_in_raw():
    original = {
        "timestamp": "2026-01-05T09:00:00Z",
        "host": "h",
        "sensor": "s",
        "category": "system",
        "action": "service_start",
        "extra": "kept",
    }
    result = normalise_record(original)
    assert result.data["raw"]["extra"] == "kept"
    assert result.data["raw"]["timestamp"] == "2026-01-05T09:00:00Z"


def test_severity_default_not_overwritten_when_absent():
    result = normalise_record(
        {
            "event_time": "2026-01-05T09:00:00Z",
            "category": "system",
            "action": "service_start",
            "source_type": "siem",
            "source_host": "h",
        }
    )
    event = SecurityEvent.model_validate(result.data)
    assert event.severity is Severity.INFORMATIONAL
