from collections import Counter

import pytest

from sentinelforge.config import Settings
from sentinelforge.events.fingerprint import fingerprint
from sentinelforge.events.schema import SecurityEvent
from sentinelforge.generator import generate_background
from sentinelforge.inventory import load_inventory


@pytest.fixture(scope="module")
def inventory():
    return load_inventory(Settings().inventory_path)


def validated(events):
    return [SecurityEvent.model_validate(e) for e in events]


def test_same_seed_produces_identical_events(inventory):
    a = generate_background(inventory, dataset_id="ds_test", seed=123, days=1)
    b = generate_background(inventory, dataset_id="ds_test", seed=123, days=1)
    assert a == b


def test_different_seeds_produce_different_events(inventory):
    a = generate_background(inventory, dataset_id="ds_test", seed=1, days=1)
    b = generate_background(inventory, dataset_id="ds_test", seed=2, days=1)
    assert a != b


def test_every_generated_event_is_schema_valid(inventory):
    events = generate_background(inventory, dataset_id="ds_test", seed=5, days=1)
    assert len(validated(events)) == len(events)


def test_events_are_sorted_by_time(inventory):
    events = generate_background(inventory, dataset_id="ds_test", seed=5, days=1)
    times = [e["event_time"] for e in events]
    assert times == sorted(times)


def test_fingerprints_are_unique_so_no_real_event_is_lost_to_dedup(inventory):
    events = validated(generate_background(inventory, dataset_id="ds_test", seed=9, days=2))
    fingerprints = {fingerprint(e) for e in events}
    assert len(fingerprints) == len(events)


def test_all_event_categories_appear(inventory):
    events = validated(generate_background(inventory, dataset_id="ds_test", seed=3, days=1))
    categories = Counter(e.category.value for e in events)
    for expected in ("authentication", "endpoint", "network", "system", "application"):
        assert categories[expected] > 0


def test_more_days_means_more_events(inventory):
    one = generate_background(inventory, dataset_id="ds_test", seed=4, days=1)
    three = generate_background(inventory, dataset_id="ds_test", seed=4, days=3)
    assert len(three) > len(one)


def test_days_must_be_positive(inventory):
    with pytest.raises(ValueError, match="at least 1"):
        generate_background(inventory, dataset_id="ds_test", seed=1, days=0)


def test_all_events_carry_the_dataset_label(inventory):
    events = generate_background(inventory, dataset_id="my_dataset", seed=1, days=1)
    assert all(e["dataset_id"] == "my_dataset" for e in events)


def test_background_events_are_labelled_background(inventory):
    events = generate_background(inventory, dataset_id="ds_test", seed=1, days=1)
    assert all(e["scenario_id"] == "background" for e in events)
