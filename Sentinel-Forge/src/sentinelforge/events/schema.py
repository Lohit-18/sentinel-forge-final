"""The SentinelForge common event schema.

Security tools describe the same thing in different ways: one log says
``"timestamp"``, another ``"TimeCreated"``; one uses ``"Failure"``, another
``"FAILED"``. A SOC converts every source into one common shape so that the
same detection rule works on all of them. ``SecurityEvent`` is that shape.

This module only defines and validates the common shape. Mapping raw source
formats into it (field renaming, synonyms) is the job of the ingestion
normaliser built in Phase 2.

The full field list and rules are documented in docs/event-schema.md.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Any

from pydantic import (
    AwareDatetime,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    IPvAnyAddress,
    StringConstraints,
    model_validator,
)

from sentinelforge.timeutil import parse_timestamp


class EventCategory(StrEnum):
    AUTHENTICATION = "authentication"
    ENDPOINT = "endpoint"
    NETWORK = "network"
    SYSTEM = "system"
    APPLICATION = "application"
    EXTERNAL_ALERT = "external_alert"


class Outcome(StrEnum):
    SUCCESS = "success"
    FAILURE = "failure"
    UNKNOWN = "unknown"


class Severity(StrEnum):
    """Source-reported severity. Not a verdict: an informational event can still
    be part of an attack, and a 'high' event can still be a false positive."""

    INFORMATIONAL = "informational"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

    @property
    def rank(self) -> int:
        return list(Severity).index(self)


def _lower_strip(value: Any) -> Any:
    """Case-insensitive matching: ' Authentication ' -> 'authentication'."""
    return value.strip().lower() if isinstance(value, str) else value


def _to_token(value: Any) -> Any:
    """'Process Start' / 'process-start' -> 'process_start'."""
    if isinstance(value, str):
        return value.strip().lower().replace(" ", "_").replace("-", "_")
    return value


def _empty_to_none(value: Any) -> Any:
    """Treat '' or whitespace-only strings as 'not provided'."""
    if isinstance(value, str) and not value.strip():
        return None
    return value


# Reusable field types --------------------------------------------------------
EventTime = Annotated[AwareDatetime, BeforeValidator(parse_timestamp)]

Token = Annotated[
    str,
    BeforeValidator(_to_token),
    StringConstraints(pattern=r"^[a-z][a-z0-9_]{1,63}$"),
]

Hostname = Annotated[
    str,
    BeforeValidator(_lower_strip),
    StringConstraints(pattern=r"^[a-z0-9][a-z0-9._-]{0,252}$"),
]

# Accepts plain names, DOMAIN\user, user@domain and machine accounts ending in $.
Username = Annotated[
    str,
    BeforeValidator(_lower_strip),
    StringConstraints(pattern=r"^[a-z0-9._@\\$-]{1,256}$"),
]

Port = Annotated[int, Field(ge=0, le=65535)]

# Optional fields: an empty string means "not provided". The empty-string check
# must run *before* pydantic chooses between "a value" and None, so it wraps
# the whole `X | None` union.
OptionalToken = Annotated[Token | None, BeforeValidator(_empty_to_none)]
OptionalUsername = Annotated[Username | None, BeforeValidator(_empty_to_none)]
OptionalIP = Annotated[IPvAnyAddress | None, BeforeValidator(_empty_to_none)]
OptionalPort = Annotated[Port | None, BeforeValidator(_empty_to_none)]
OptionalId = Annotated[
    Annotated[str, StringConstraints(max_length=128)] | None, BeforeValidator(_empty_to_none)
]
OptionalName = Annotated[
    Annotated[str, StringConstraints(max_length=260)] | None, BeforeValidator(_empty_to_none)
]
OptionalPath = Annotated[
    Annotated[str, StringConstraints(max_length=1024)] | None, BeforeValidator(_empty_to_none)
]
OptionalCommandLine = Annotated[
    Annotated[str, StringConstraints(max_length=4096)] | None, BeforeValidator(_empty_to_none)
]
OptionalSha256 = Annotated[
    Annotated[str, BeforeValidator(_lower_strip), StringConstraints(pattern=r"^[a-f0-9]{64}$")]
    | None,
    BeforeValidator(_empty_to_none),
]
OptionalDomain = Annotated[
    Annotated[
        str,
        BeforeValidator(_lower_strip),
        StringConstraints(max_length=253, pattern=r"^[a-z0-9-]{1,63}(\.[a-z0-9-]{1,63})+$"),
    ]
    | None,
    BeforeValidator(_empty_to_none),
]


class SecurityEvent(BaseModel):
    """One normalised security event."""

    model_config = ConfigDict(
        extra="forbid",  # unknown fields are errors, so typos like "usr" are caught
        str_strip_whitespace=True,
        frozen=True,  # events are facts; they must not change after validation
    )

    # When it happened (always UTC). Ingestion time is added by the ingestion
    # pipeline in Phase 2, because it is not part of the source record.
    event_time: EventTime

    # What kind of event it is.
    category: Annotated[EventCategory, BeforeValidator(_lower_strip)]
    action: Token
    outcome: Annotated[Outcome, BeforeValidator(_lower_strip)] = Outcome.UNKNOWN
    severity: Annotated[Severity, BeforeValidator(_lower_strip)] = Severity.INFORMATIONAL

    # Where it came from.
    source_type: Token
    source_host: Hostname
    source_event_id: OptionalId = None

    # Who and what was involved (optional; depends on the category).
    user: OptionalUsername = None  # the account that performed the action
    target_user: OptionalUsername = None  # the account acted upon (e.g. added to a group)
    src_ip: OptionalIP = None
    src_port: OptionalPort = None
    dst_ip: OptionalIP = None
    dst_port: OptionalPort = None
    process_name: OptionalName = None
    process_path: OptionalPath = None
    parent_process_name: OptionalName = None
    process_command_line: OptionalCommandLine = None
    file_sha256: OptionalSha256 = None
    dst_domain: OptionalDomain = None
    # The thing acted on: a group name, file path, security setting or URL path.
    object_name: OptionalPath = None

    # Lab bookkeeping: which dataset and synthetic scenario produced the event.
    dataset_id: OptionalToken = None
    scenario_id: OptionalToken = None

    # The original record, kept for investigation and audit.
    raw: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _check_category_requirements(self) -> SecurityEvent:
        problems: list[str] = []

        if self.category is EventCategory.AUTHENTICATION and self.user is None:
            problems.append("authentication events must include 'user'")
        if (
            self.category is EventCategory.ENDPOINT
            and self.action.startswith("process_")
            and self.process_name is None
        ):
            problems.append("process events must include 'process_name'")
        if self.category is EventCategory.NETWORK and self.dst_ip is None:
            problems.append("network events must include 'dst_ip'")
        if self.src_port is not None and self.src_ip is None:
            problems.append("'src_port' requires 'src_ip'")
        if self.dst_port is not None and self.dst_ip is None:
            problems.append("'dst_port' requires 'dst_ip'")

        if problems:
            raise ValueError("; ".join(problems))
        return self
