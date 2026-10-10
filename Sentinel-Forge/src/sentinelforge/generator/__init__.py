"""Deterministic synthetic event generation.

The generator produces normal day-to-day activity ("background") for the lab
organisation in ``configs/lab_inventory.yml``. Given the same seed it always
produces exactly the same events, so results are reproducible and tests are
stable.

Detection test data (events that look like attacks) is not generated here. Those
are supplied as small hand-written JSON Lines files, which also makes the
detection logic easier to explain.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from sentinelforge.generator.background import generate_day
from sentinelforge.generator.lab import LabEventFactory
from sentinelforge.inventory import Inventory

# A fixed anchor date keeps generated datasets comparable across runs and
# machines. The seed still makes each dataset distinct.
DEFAULT_ANCHOR = datetime(2026, 1, 5, tzinfo=UTC)  # a Monday


@dataclass(frozen=True)
class GenerationResult:
    dataset_id: str
    seed: int
    days: int
    event_count: int


def generate_background(
    inventory: Inventory,
    *,
    dataset_id: str,
    seed: int,
    days: int = 1,
    anchor: datetime = DEFAULT_ANCHOR,
) -> list[dict[str, Any]]:
    """Return all background events for ``days`` days, sorted by event time."""
    if days < 1:
        raise ValueError("days must be at least 1")
    # Synthetic data generation, not security: a reproducible PRNG is the point.
    rng = random.Random(seed)  # noqa: S311
    factory = LabEventFactory(inventory=inventory, rng=rng, dataset_id=dataset_id, seed=seed)
    events: list[dict[str, Any]] = []
    for offset in range(days):
        events.extend(generate_day(factory, anchor + timedelta(days=offset)))
    events.sort(key=lambda event: event["event_time"])
    return events


def write_jsonl(events: list[dict[str, Any]], path: Path) -> None:
    import json

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for event in events:
            handle.write(json.dumps(event, sort_keys=True))
            handle.write("\n")


def generate_to_file(
    inventory: Inventory,
    path: Path,
    *,
    dataset_id: str,
    seed: int,
    days: int = 1,
) -> GenerationResult:
    events = generate_background(inventory, dataset_id=dataset_id, seed=seed, days=days)
    write_jsonl(events, path)
    return GenerationResult(dataset_id=dataset_id, seed=seed, days=days, event_count=len(events))
