# Database schema

PostgreSQL stores every event in the `sentinelforge` schema. Tables are created
by numbered SQL migrations in `migrations/`, applied with `sentinelforge db
migrate`. The current version is **0001**.

## Roles

| Role | Used by | Rights |
|---|---|---|
| `sentinelforge_admin` | setup and migrations only | owns the schema, creates and changes tables |
| `sentinelforge_app` | the running application | `SELECT`, `INSERT`, `UPDATE` only |

The app role has no `DELETE` or `TRUNCATE`, so stored events and import history
cannot be erased through the application.

## Tables (migration 0001)

### `security_events`

The normalised event store. One row per event.

| Column | Type | Notes |
|---|---|---|
| `id` | bigint identity | primary key |
| `fingerprint` | char(64) | SHA-256; **unique**, so duplicates are rejected |
| `event_time` | timestamptz | when the event happened (UTC) |
| `ingested_at` | timestamptz | when SentinelForge received it (defaults to now) |
| `category` | text | authentication, endpoint, network, system, application, external_alert |
| `action`, `outcome`, `severity` | text | normalised values |
| `source_type`, `source_host` | text | which sensor, which machine |
| `source_event_id` | text | the source's own record ID, if any |
| `app_user`, `target_user` | text | the acting and acted-on accounts |
| `src_ip`, `dst_ip` | inet | PostgreSQL's native IP type |
| `src_port`, `dst_port` | integer | |
| `dst_domain` | text | |
| `process_name`, `process_path`, `parent_process_name` | text | |
| `process_command_line` | text | |
| `file_sha256` | char(64) | |
| `object_name` | text | the thing acted on (group, file, setting, URL path) |
| `dataset_id`, `scenario_id` | text | lab bookkeeping |
| `import_id` | bigint | which import run stored this event |
| `raw` | jsonb | the original record, kept as evidence |

**Event time vs ingestion time.** These are deliberately separate. Event time
is what the log says; ingestion time is when we received it. The gap is
detection latency, and a large gap can reveal delayed or replayed log delivery.

**Indexes.** Chosen for the queries detection and the dashboard will run, which
are almost always "events for this host / user / source address, in this time
window, newest first": `event_time`; `(source_host, event_time)`; `(app_user,
event_time)`; `(category, event_time)`; `(src_ip, event_time)`; and
`dataset_id`.

### `dataset_imports`

One row per import run. Gives every stored event a traceable origin and records
how many records were read, stored, duplicate or invalid, plus start and finish
times and a status (`running`, `completed`, `failed`).

### `schema_migrations`

Records which migration versions have been applied, so each runs once.

## Why fingerprints, not a natural key

Security events have no reliable natural primary key: two different failed
logins can share the same user, host and second. The fingerprint (see
`events/fingerprint.py`) hashes the source's own record ID when present, and
otherwise the event's content. A unique constraint on it means importing the
same file twice stores nothing the second time. The limitation — two identical
events in the same second with no source record ID collapse into one — is
documented there.
