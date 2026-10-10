from sentinelforge.events.fingerprint import fingerprint
from sentinelforge.events.schema import SecurityEvent


def event(**overrides):
    data = {
        "event_time": "2026-01-05T09:00:00Z",
        "category": "authentication",
        "action": "logon",
        "outcome": "failure",
        "source_type": "synthetic_auth",
        "source_host": "ws-01",
        "user": "alice.lab",
    }
    data.update(overrides)
    return SecurityEvent.model_validate(data)


def test_identical_events_have_the_same_fingerprint():
    assert fingerprint(event()) == fingerprint(event())


def test_fingerprint_is_64_hex_characters():
    fp = fingerprint(event())
    assert len(fp) == 64
    assert all(c in "0123456789abcdef" for c in fp)


def test_dataset_and_scenario_labels_do_not_change_the_fingerprint():
    # The same event imported under two dataset labels is still one event.
    assert fingerprint(event(dataset_id="ds_a")) == fingerprint(event(dataset_id="ds_b"))
    assert fingerprint(event(scenario_id="sc_x")) == fingerprint(event(scenario_id="sc_y"))


def test_different_content_changes_the_fingerprint():
    assert fingerprint(event(user="alice.lab")) != fingerprint(event(user="bob.lab"))
    assert fingerprint(event(outcome="success")) != fingerprint(event(outcome="failure"))


def test_source_event_id_distinguishes_otherwise_identical_events():
    # Two failed logins in the same second are different events when the source
    # gives them different record IDs.
    a = event(source_event_id="100")
    b = event(source_event_id="101")
    assert fingerprint(a) != fingerprint(b)


def test_same_source_event_id_is_a_duplicate_regardless_of_other_fields():
    # With a source record ID, that ID identifies the event.
    a = event(source_event_id="100", severity="low")
    b = event(source_event_id="100", severity="high")
    assert fingerprint(a) == fingerprint(b)
