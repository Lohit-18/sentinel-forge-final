"""Map raw source records onto the common event schema.

Different tools name the same thing differently ("timestamp", "@timestamp",
"TimeCreated") and use different words for the same value ("FAILED",
"denied", "failure"). Normalisation translates them so detection rules only
ever deal with one vocabulary.

Normalisation is deliberately conservative: it renames known aliases and
translates known synonyms, then the strict ``SecurityEvent`` validation
decides whether the result is acceptable. Fields it does not recognise stay
in ``raw`` (nothing is thrown away) and are reported, never silently used.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sentinelforge.events.schema import SecurityEvent

CANONICAL_FIELDS = frozenset(SecurityEvent.model_fields)

# alias (lower-case, '-' and ' ' replaced by '_') -> canonical field
FIELD_ALIASES: dict[str, str] = {
    # time
    "timestamp": "event_time",
    "@timestamp": "event_time",
    "time": "event_time",
    "timecreated": "event_time",
    "eventtime": "event_time",
    # where
    "host": "source_host",
    "hostname": "source_host",
    "computer": "source_host",
    "computername": "source_host",
    "sensor": "source_type",
    "event_id": "source_event_id",
    "record_id": "source_event_id",
    "eventrecordid": "source_event_id",
    # what
    "event_category": "category",
    "event_action": "action",
    "eventaction": "action",
    "result": "outcome",
    "event_outcome": "outcome",
    "level": "severity",
    # who
    "username": "user",
    "user_name": "user",
    "account": "user",
    "accountname": "user",
    "subjectusername": "user",
    "targetusername": "target_user",
    "target_username": "target_user",
    # network
    "source_ip": "src_ip",
    "src": "src_ip",
    "client_ip": "src_ip",
    "source_port": "src_port",
    "destination_ip": "dst_ip",
    "dest_ip": "dst_ip",
    "dst": "dst_ip",
    "destination_port": "dst_port",
    "dest_port": "dst_port",
    "destination_domain": "dst_domain",
    "dest_domain": "dst_domain",
    # process
    "process": "process_name",
    "image_name": "process_name",
    "parent_process": "parent_process_name",
    "parent_image_name": "parent_process_name",
    "commandline": "process_command_line",
    "command_line": "process_command_line",
    "sha256": "file_sha256",
    "hash_sha256": "file_sha256",
    # target object
    "object": "object_name",
    "target_object": "object_name",
    # lab bookkeeping
    "dataset": "dataset_id",
    "scenario": "scenario_id",
}

VALUE_SYNONYMS: dict[str, dict[str, str]] = {
    "category": {
        "auth": "authentication",
        "authn": "authentication",
        "login": "authentication",
        "logon": "authentication",
        "identity": "authentication",
        "process": "endpoint",
        "edr": "endpoint",
        "host": "endpoint",
        "net": "network",
        "firewall": "network",
        "connection": "network",
        "os": "system",
        "audit": "system",
        "server": "system",
        "app": "application",
        "web": "application",
        "webapp": "application",
        "alert": "external_alert",
        "ids": "external_alert",
    },
    "outcome": {
        "succeeded": "success",
        "successful": "success",
        "ok": "success",
        "allowed": "success",
        "allow": "success",
        "pass": "success",
        "passed": "success",
        "failed": "failure",
        "fail": "failure",
        "denied": "failure",
        "deny": "failure",
        "blocked": "failure",
        "block": "failure",
        "rejected": "failure",
        "error": "failure",
    },
    "severity": {
        "info": "informational",
        "information": "informational",
        "notice": "informational",
        "warn": "low",
        "warning": "low",
        "error": "medium",
        "err": "medium",
        "crit": "critical",
    },
}


@dataclass
class NormalisedRecord:
    data: dict[str, Any]
    unmapped_fields: list[str] = field(default_factory=list)


def _alias_key(key: str) -> str:
    return key.strip().lower().replace("-", "_").replace(" ", "_")


def normalise_record(record: dict[str, Any]) -> NormalisedRecord:
    """Rename aliases and translate synonyms. Always keeps the original in ``raw``."""
    data: dict[str, Any] = {}
    unmapped: list[str] = []

    # Canonical names win over aliases when both are present.
    for key, value in record.items():
        if key in CANONICAL_FIELDS and key != "raw":
            data[key] = value
    for key, value in record.items():
        if key in CANONICAL_FIELDS:
            continue
        target = FIELD_ALIASES.get(_alias_key(key))
        if target is None:
            unmapped.append(key)
        elif target not in data:
            data[target] = value
        else:
            unmapped.append(key)  # alias clashes with a field already set

    for field_name, synonyms in VALUE_SYNONYMS.items():
        value = data.get(field_name)
        if isinstance(value, str):
            data[field_name] = synonyms.get(value.strip().lower(), value)

    original = record.get("raw") if isinstance(record.get("raw"), dict) else record
    data["raw"] = {k: v for k, v in original.items() if k != "raw"}
    return NormalisedRecord(data=data, unmapped_fields=sorted(unmapped))
