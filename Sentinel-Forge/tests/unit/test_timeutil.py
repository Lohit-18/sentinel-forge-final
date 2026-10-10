from datetime import UTC, datetime, timedelta, timezone

import pytest

from sentinelforge.timeutil import TimestampError, parse_timestamp

EXPECTED = datetime(2026, 10, 10, 9, 15, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    "value",
    [
        "2026-10-10T09:15:00Z",
        "2026-10-10T09:15:00+00:00",
        "2026-10-10T14:45:00+05:30",  # India Standard Time
        "2026-10-10T20:15:00+11:00",  # Melbourne daylight time
        "  2026-10-10T09:15:00Z  ",  # surrounding whitespace
        "2026-10-10 09:15:00Z",  # space instead of 'T'
        1791623700,  # epoch seconds (int)
        1791623700.0,  # epoch seconds (float)
        "1791623700",  # epoch seconds (string)
        1791623700000,  # epoch milliseconds
    ],
)
def test_supported_formats_normalise_to_the_same_utc_instant(value):
    result = parse_timestamp(value)
    assert result == EXPECTED
    assert result.tzinfo is UTC


def test_aware_datetime_is_converted_to_utc():
    ist = timezone(timedelta(hours=5, minutes=30))
    assert parse_timestamp(datetime(2026, 10, 10, 14, 45, tzinfo=ist)) == EXPECTED


def test_fractional_seconds_are_kept():
    assert parse_timestamp("2026-10-10T09:15:00.250Z").microsecond == 250_000


@pytest.mark.parametrize(
    ("value", "message"),
    [
        ("2026-10-10T09:15:00", "no time zone"),  # naive: we refuse to guess
        (datetime(2026, 10, 10, 9, 15), "no time zone"),
        ("2026-10-10", "no time zone"),  # date only
        ("10/10/2026 09:15", "unrecognised timestamp format"),
        ("yesterday", "unrecognised timestamp format"),
        ("", "empty"),
        ("   ", "empty"),
        (True, "boolean"),
        (None, "unsupported timestamp type"),
        ([2026, 10, 10], "unsupported timestamp type"),
        (0, "outside the supported range"),  # 1970: almost always a bug
        ("2150-01-01T00:00:00Z", "outside the supported range"),
        (1791623700000000, "outside the supported range"),  # microseconds by mistake
        (float("nan"), "finite"),
        (float("inf"), "finite"),
    ],
)
def test_invalid_timestamps_are_rejected_with_a_clear_reason(value, message):
    with pytest.raises(TimestampError, match=message):
        parse_timestamp(value)
