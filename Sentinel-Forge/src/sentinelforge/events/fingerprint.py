"""Event fingerprints for duplicate detection.

The same log file is often imported twice, or two collectors forward the same
event. A fingerprint is a SHA-256 hash that is identical for duplicates, and a
unique database constraint on it stops duplicates being stored.

Choosing what to hash is a trade-off:

* If the source gives each record its own ID (``source_event_id``), we hash
  ``source_type + source_host + source_event_id``. Two genuinely separate
  events that look identical (two failed logins in the same second) keep
  different IDs, so both are kept.
* Without a source ID we hash the normalised content. Two identical events in
  the same second then collapse into one. This is a documented limitation;
  sources that provide record IDs avoid it.
"""

from __future__ import annotations

import hashlib
import json

from sentinelforge.events.schema import SecurityEvent

# Lab bookkeeping and the raw copy do not change what happened, so they are
# not part of the content fingerprint.
_EXCLUDED_FROM_CONTENT = {"raw", "dataset_id", "scenario_id"}


def fingerprint(event: SecurityEvent) -> str:
    if event.source_event_id:
        basis: dict[str, object] = {
            "source_type": event.source_type,
            "source_host": event.source_host,
            "source_event_id": event.source_event_id,
        }
    else:
        basis = event.model_dump(mode="json", exclude=_EXCLUDED_FROM_CONTENT)
    canonical = json.dumps(basis, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
