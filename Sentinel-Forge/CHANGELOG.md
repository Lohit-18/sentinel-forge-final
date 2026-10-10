# Changelog

All notable changes to SentinelForge are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions use
[Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.2.0] - Phase 2: event ingestion

### Added
- **Common event schema v1.1**: five optional fields (`target_user`,
  `process_command_line`, `file_sha256`, `dst_domain`, `object_name`) for later
  detection work.
- **Event normalisation** (`events/normalise.py`): maps other tools' field names
  (`TimeCreated`, `AccountName`, …) and value synonyms (`FAILED`, `denied` →
  `failure`) onto the common schema. Unrecognised fields are kept in `raw` and
  reported, never silently used.
- **File readers** (`events/readers.py`): JSON Lines and CSV, record by record,
  with per-line error reporting. A bad line never stops the file.
- **Duplicate detection** (`events/fingerprint.py`): a SHA-256 fingerprint per
  event. A unique constraint makes re-importing a file a no-op.
- **PostgreSQL event store**: migration `0001_events.sql` with
  `security_events`, `dataset_imports` and `schema_migrations`, chosen indexes,
  and event time vs ingestion time recorded separately.
- **Migration runner** (`db/migrate.py`): applies SQL migrations once each, in
  order, each in its own transaction, as the admin role.
- **Ingestion pipeline** (`events/ingest.py`): file → normalise → validate →
  store, skipping duplicates and recording an import run for traceability.
- **Deterministic synthetic generator** (`generator/`): reproducible normal
  "background" activity for the lab organisation. The same seed always produces
  the same events.
- **Lab inventory** (`configs/lab_inventory.yml`, `inventory.py`): synthetic
  identities and assets with criticality and privilege, for later context.
- **New CLI commands**: `events generate`, `events ingest`, `db migrate`.
- **New scripts**: `setup_native_db.sh`, `load_sample_data.sh`, `run_demo.sh`,
  `check_licences.sh`.
- Documentation: `docs/database-schema.md`; updated event schema and architecture.
- **Project dashboard** (`dashboard.html`) and screenshots, plus a ready-made
  1,670-event sample dataset and a captured run transcript in `examples/`.

### Notes
- Detection rules, correlation, alerts, incidents and the dashboard are planned
  for later phases. Detection test data (events that resemble attacks) is
  supplied as hand-written JSON Lines fixtures, not produced by the generator.

## [0.1.0] - Phase 1: foundation

### Added
- Configuration from environment and `.env`, with passwords hidden.
- The common `SecurityEvent` schema and strict UTC timestamp parsing.
- JSON Lines file validation and the `sentinelforge` CLI (`config`, `events
  validate`, `db bootstrap`, `db status`).
- PostgreSQL setup with a least-privilege application role.
- Bash scripts for setup, environment check, start/stop, lint and tests.
- Unit and integration tests, GitHub Actions CI, and the free/open-source
  licence check.
