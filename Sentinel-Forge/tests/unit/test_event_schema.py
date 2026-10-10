from datetime import UTC, datetime
from ipaddress import IPv4Address, IPv6Address

import pytest
from pydantic import ValidationError

from sentinelforge.events.schema import EventCategory, Outcome, SecurityEvent, Severity


def make_event(**overrides):
    """A valid authentication event; tests override one field at a time."""
    data = {
        "event_time": "2026-10-10T09:00:00Z",
        "category": "authentication",
        "action": "logon",
        "outcome": "success",
        "source_type": "synthetic_auth",
        "source_host": "ws-01",
        "user": "alice.lab",
    }
    data.update(overrides)
    return SecurityEvent.model_validate(data)


def error_text(exc_info) -> str:
    return " | ".join(e["msg"] for e in exc_info.value.errors())


# --- valid events and normalisation ------------------------------------------
def test_minimal_valid_event_gets_safe_defaults():
    event = SecurityEvent.model_validate(
        {
            "event_time": "2026-10-10T09:00:00Z",
            "category": "system",
            "action": "service_start",
            "source_type": "synthetic_system",
            "source_host": "srv-01",
        }
    )
    assert event.outcome is Outcome.UNKNOWN
    assert event.severity is Severity.INFORMATIONAL
    assert event.raw == {}


def test_values_are_normalised():
    event = make_event(
        event_time="2026-10-10T14:30:00+05:30",
        category=" Authentication ",
        action="Logon Attempt",
        outcome="FAILURE",
        severity="High",
        source_host="WS-FIN-01",
        user="  Alice.Lab ",
    )
    assert event.event_time == datetime(2026, 10, 10, 9, 0, tzinfo=UTC)
    assert event.category is EventCategory.AUTHENTICATION
    assert event.action == "logon_attempt"
    assert event.outcome is Outcome.FAILURE
    assert event.severity is Severity.HIGH
    assert event.source_host == "ws-fin-01"
    assert event.user == "alice.lab"


@pytest.mark.parametrize("user", ["LAB\\alice", "alice@lab.example.com", "ws-01$", "svc_backup"])
def test_common_account_formats_are_accepted(user):
    assert make_event(user=user).user == user.lower()


def test_ipv4_and_ipv6_addresses_are_parsed():
    event = make_event(src_ip="10.20.1.15", src_port=50211)
    assert event.src_ip == IPv4Address("10.20.1.15")
    v6 = make_event(src_ip="2001:db8::10")
    assert v6.src_ip == IPv6Address("2001:db8::10")


def test_empty_optional_strings_become_none():
    event = make_event(category="endpoint", action="file_change", process_name="", process_path=" ")
    assert event.process_name is None
    assert event.process_path is None


def test_empty_optional_values_of_every_type_become_none():
    event = make_event(
        category="system",
        action="service_start",
        user="",
        src_ip="",
        src_port="",
        source_event_id="",
        dataset_id=" ",
    )
    assert event.user is None
    assert event.src_ip is None
    assert event.src_port is None
    assert event.source_event_id is None
    assert event.dataset_id is None


def test_empty_user_still_fails_for_authentication():
    with pytest.raises(ValidationError, match="must include 'user'"):
        make_event(user="")


def test_events_are_immutable():
    event = make_event()
    with pytest.raises(ValidationError):
        event.user = "mallory"


def test_severity_rank_orders_levels():
    assert Severity.INFORMATIONAL.rank < Severity.LOW.rank < Severity.CRITICAL.rank


def test_normalised_event_serialises_to_json():
    data = make_event(src_ip="10.0.0.5").model_dump(mode="json")
    assert data["event_time"] == "2026-10-10T09:00:00Z"
    assert data["src_ip"] == "10.0.0.5"
    assert data["category"] == "authentication"


# --- invalid events ----------------------------------------------------------
def test_unknown_fields_are_rejected_so_typos_are_caught():
    with pytest.raises(ValidationError, match="usr"):
        make_event(usr="alice.lab")


REQUIRED = ["event_time", "category", "action", "source_type", "source_host"]


@pytest.mark.parametrize("field", REQUIRED)
def test_required_fields(field):
    data = {
        "event_time": "2026-10-10T09:00:00Z",
        "category": "system",
        "action": "service_start",
        "source_type": "synthetic_system",
        "source_host": "srv-01",
    }
    del data[field]
    with pytest.raises(ValidationError) as exc_info:
        SecurityEvent.model_validate(data)
    assert exc_info.value.errors()[0]["loc"] == (field,)


def test_naive_timestamp_is_rejected():
    with pytest.raises(ValidationError, match="no time zone"):
        make_event(event_time="2026-10-10T09:00:00")


@pytest.mark.parametrize("category", ["login", "dns", "malware"])
def test_unknown_category_is_rejected(category):
    with pytest.raises(ValidationError):
        make_event(category=category)


@pytest.mark.parametrize("action", ["", "1logon", "logon;drop", "a" * 65])
def test_malformed_action_is_rejected(action):
    with pytest.raises(ValidationError):
        make_event(action=action)


@pytest.mark.parametrize("host", ["", "bad host!", "-starts-with-dash", "h" * 254])
def test_malformed_host_is_rejected(host):
    with pytest.raises(ValidationError):
        make_event(source_host=host)


def test_user_with_unsafe_characters_is_rejected():
    with pytest.raises(ValidationError):
        make_event(user="alice'; DROP TABLE users;--")


@pytest.mark.parametrize("ip", ["999.1.1.1", "10.0.0", "not-an-ip"])
def test_invalid_ip_is_rejected(ip):
    with pytest.raises(ValidationError):
        make_event(src_ip=ip)


@pytest.mark.parametrize("port", [-1, 65536, 70000])
def test_port_out_of_range_is_rejected(port):
    with pytest.raises(ValidationError):
        make_event(src_ip="10.0.0.5", src_port=port)


# --- category-specific rules -------------------------------------------------
def test_authentication_event_requires_user():
    with pytest.raises(ValidationError) as exc_info:
        make_event(user=None)
    assert "authentication events must include 'user'" in error_text(exc_info)


def test_process_event_requires_process_name():
    with pytest.raises(ValidationError) as exc_info:
        make_event(category="endpoint", action="process_start")
    assert "process_name" in error_text(exc_info)


def test_non_process_endpoint_event_does_not_require_process_name():
    event = make_event(category="endpoint", action="security_setting_changed", user=None)
    assert event.process_name is None


def test_network_event_requires_destination_ip():
    with pytest.raises(ValidationError) as exc_info:
        make_event(category="network", action="connection", user=None)
    assert "dst_ip" in error_text(exc_info)


def test_port_without_ip_is_rejected():
    with pytest.raises(ValidationError) as exc_info:
        make_event(src_port=443)
    assert "'src_port' requires 'src_ip'" in error_text(exc_info)


def test_all_category_problems_are_reported_together():
    with pytest.raises(ValidationError) as exc_info:
        make_event(category="network", action="connection", dst_port=443)
    text = error_text(exc_info)
    assert "dst_ip" in text
    assert "'dst_port' requires 'dst_ip'" in text
