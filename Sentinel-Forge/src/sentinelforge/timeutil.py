"""Timestamp parsing and normalisation.

Every event time in SentinelForge is stored as a time-zone-aware UTC datetime.
Correlation ("did the successful login happen within 10 minutes of the failures?")
is only correct if every timestamp is in the same time zone, so this module is
strict on purpose:

* ISO-8601 strings must include a UTC offset ("Z" or "+05:30").
* Timestamps without a time zone are rejected instead of being guessed.
* Unix epoch numbers are accepted in seconds or milliseconds.
* Times outside 2000-01-01 .. 2100-01-01 are rejected. This catches unit
  mistakes, such as epoch microseconds or a value of 0.
"""

from __future__ import annotations

import math
import re
from datetime import UTC, datetime

MIN_EVENT_TIME = datetime(2000, 1, 1, tzinfo=UTC)
MAX_EVENT_TIME = datetime(2100, 1, 1, tzinfo=UTC)

# Epoch seconds for the year 2100 are about 4.1e9, while epoch milliseconds for
# the year 2000 are about 9.5e11. Any value at or above 1e11 must therefore be
# milliseconds, and anything below must be seconds.
EPOCH_MS_THRESHOLD = 100_000_000_000

_NUMERIC_RE = re.compile(r"[+-]?\d+(\.\d+)?")


class TimestampError(ValueError):
    """Raised when a value cannot be turned into a valid UTC timestamp."""


def _from_epoch(value: float) -> datetime:
    if math.isnan(value) or math.isinf(value):
        raise TimestampError("epoch timestamp must be a finite number")
    seconds = value / 1000 if abs(value) >= EPOCH_MS_THRESHOLD else value
    try:
        return datetime.fromtimestamp(seconds, tz=UTC)
    except (OverflowError, OSError, ValueError):
        raise TimestampError(
            "timestamp is outside the supported range (2000-01-01 to 2100-01-01)"
        ) from None


def parse_timestamp(value: object) -> datetime:
    """Convert a supported timestamp value into an aware UTC datetime.

    >>> parse_timestamp("2026-10-10T14:45:00+05:30").isoformat()
    '2026-10-10T09:15:00+00:00'
    """
    # bool is a subclass of int in Python, so check it first: True must not
    # silently become 1970-01-01T00:00:01.
    if isinstance(value, bool):
        raise TimestampError("a boolean is not a timestamp")

    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, int | float):
        parsed = _from_epoch(float(value))
    elif isinstance(value, str):
        text = value.strip()
        if not text:
            raise TimestampError("timestamp is empty")
        if _NUMERIC_RE.fullmatch(text):
            parsed = _from_epoch(float(text))
        else:
            try:
                parsed = datetime.fromisoformat(text)
            except ValueError:
                raise TimestampError(
                    "unrecognised timestamp format; use ISO-8601 with a UTC offset "
                    "(for example 2026-10-10T09:15:00Z) or Unix epoch seconds"
                ) from None
    else:
        raise TimestampError(f"unsupported timestamp type: {type(value).__name__}")

    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise TimestampError(
            "timestamp has no time zone; add 'Z' for UTC or an offset such as +05:30"
        )

    parsed = parsed.astimezone(UTC)
    if not MIN_EVENT_TIME <= parsed < MAX_EVENT_TIME:
        raise TimestampError("timestamp is outside the supported range (2000-01-01 to 2100-01-01)")
    return parsed
