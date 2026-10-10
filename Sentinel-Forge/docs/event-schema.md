# Event schema (v1)

Every event that enters SentinelForge is converted into one common shape, `SecurityEvent`, defined in [`src/sentinelforge/events/schema.py`](../src/sentinelforge/events/schema.py). Detection rules only ever see this shape, so a rule written once works for every source.

Phase 1 defines and validates the shape. Mapping raw source formats into it (renaming fields, translating synonyms such as `FAILED` → `failure`) is added in Phase 2.

## Fields

| Field | Type | Required | Normalisation and rules |
|---|---|---|---|
| `event_time` | timestamp | yes | Converted to UTC. ISO-8601 **with** an offset (`2026-10-10T09:15:00Z`, `…+05:30`) or Unix epoch seconds/milliseconds. Times without a time zone are rejected. Range 2000-01-01 to 2100-01-01. |
| `category` | enum | yes | `authentication`, `endpoint`, `network`, `system`, `application`, `external_alert`. Case-insensitive. |
| `action` | token | yes | What happened, e.g. `logon`, `process_start`, `connection`. Lower-cased; spaces and dashes become `_`. Pattern `^[a-z][a-z0-9_]{1,63}$`. |
| `outcome` | enum | no | `success`, `failure`, `unknown` (default). Case-insensitive. |
| `severity` | enum | no | `informational` (default), `low`, `medium`, `high`, `critical`. Severity reported by the source, **not** a verdict. |
| `source_type` | token | yes | The kind of sensor, e.g. `synthetic_auth`, `synthetic_firewall`. |
| `source_host` | hostname | yes | The machine that reported the event. Lower-cased. |
| `source_event_id` | string ≤128 | no | The source's own ID for the record, if it has one. |
| `user` | account | depends | Lower-cased. Allows `alice`, `LAB\alice`, `alice@lab.example.com`, `ws-01$`. |
| `src_ip`, `dst_ip` | IPv4/IPv6 | depends | Validated with Python's `ipaddress` rules. |
| `src_port`, `dst_port` | 0–65535 | no | Only allowed together with the matching IP. |
| `process_name` | string ≤260 | depends | e.g. `powershell.exe` |
| `process_path` | string ≤1024 | no | Full path of the executable. |
| `parent_process_name` | string ≤260 | no | The process that started this one. |
| `dataset_id` | token | no | Which dataset the event belongs to. |
| `scenario_id` | token | no | Which synthetic scenario produced it. Used for evaluation, never by detection rules. |
| `process_command_line` | string ≤4096 | no | The full command line, when the source provides it. |
| `file_sha256` | 64 hex chars | no | SHA-256 of a file involved in the event. |
| `dst_domain` | domain | no | Destination domain name for a connection. |
| `target_user` | account | no | The account acted upon (e.g. added to a group). |
| `object_name` | string ≤1024 | no | The thing acted on: a group, file path, setting or URL path. |
| `raw` | object | no | The original record, kept as evidence. |

Empty strings in optional fields are treated as "not provided". **Unknown fields are rejected**, so a typo such as `usr` is reported instead of being silently ignored.

## Category rules

| Category | Extra requirement | Why |
|---|---|---|
| `authentication` | `user` | A login without an account cannot be correlated with anything. |
| `endpoint` with an action starting `process_` | `process_name` | Process detections need to know which process. |
| `network` | `dst_ip` | Connection detections need a destination. |
| any | a port requires its IP | A port on its own is meaningless. |

All rule problems for one event are reported together.

## Timestamps

| Input | Result |
|---|---|
| `2026-10-10T14:45:00+05:30` | `2026-10-10T09:15:00Z` |
| `1791623700` (epoch seconds) | `2026-10-10T09:15:00Z` |
| `1791623700000` (epoch milliseconds) | `2026-10-10T09:15:00Z` |
| `2026-10-10T09:15:00` (no zone) | **rejected**: the time zone would be a guess |
| `10/10/2026 09:15` | **rejected**: day/month order is ambiguous |

Numbers at or above 10¹¹ are treated as milliseconds. Epoch seconds for the year 2100 are about 4.1 × 10⁹, and epoch milliseconds for the year 2000 are about 9.5 × 10¹¹, so the two can't be confused.

Event time (when it happened) and ingestion time (when SentinelForge received it) are different. Ingestion time is recorded by the ingestion pipeline in Phase 2.

## Example

```json
{"event_time": "2026-10-10T14:31:05+05:30", "category": "Authentication", "action": "Logon",
 "outcome": "FAILURE", "source_type": "synthetic_auth", "source_host": "srv-vpn-01",
 "user": "bob.lab", "src_ip": "198.51.100.23", "src_port": 50211}
```

After validation, the time is `2026-10-10T09:01:05Z`, the category is `authentication`, the action is `logon` and the outcome is `failure`.

Check a file with:

```bash
sentinelforge events validate data/sample/phase1_events.jsonl
```
