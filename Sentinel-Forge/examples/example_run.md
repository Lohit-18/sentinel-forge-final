# SentinelForge — example run transcript

Real output captured from the commands below (PostgreSQL 16, synthetic data).
Reproduce with: bash scripts/run_demo.sh

## 1. Generate deterministic synthetic activity
```console
$ sentinelforge events generate --dataset-id background --seed 42 --days 1
Generated 1670 synthetic background events
  Dataset:  background
  Seed:     42 (same seed always produces the same events)
  Days:     1
  Written:  data/generated/background.jsonl
Next: sentinelforge events ingest data/generated/background.jsonl
```

## 2. Validate the file against the common schema
```console
$ sentinelforge events validate examples/background_1day_seed42.jsonl
Validated examples/background_1day_seed42.jsonl
  Records:  1670
  Valid:    1670
  Invalid:  0
Result: OK
```

## 3. Ingest into PostgreSQL (duplicates are skipped)
```console
$ sentinelforge events ingest examples/background_1day_seed42.jsonl
Ingested examples/background_1day_seed42.jsonl
  Dataset:      background_1day_seed42
  Import ID:    1
  Records read: 1670
  Stored:       1670
  Duplicates:   0 (already in the database)
  Invalid:      0
Result: OK
```

## 4. Re-ingest the same file — every event is already stored
```console
$ sentinelforge events ingest examples/background_1day_seed42.jsonl
  Records read: 1670
  Stored:       0
  Duplicates:   1670 (already in the database)
  Invalid:      0
Result: OK
```

## 5. Ingest a DIFFERENT tool's CSV (field names + values auto-normalised)
```console
$ cat other_tool.csv
TimeCreated,Computer,sensor,event_category,event_action,result,AccountName,source_ip
2026-01-06T09:00:00Z,WS-FIN-02,otherSIEM,auth,logon,SUCCEEDED,bob.lab,10.20.1.12
2026-01-06T09:00:07Z,WS-FIN-02,otherSIEM,auth,logon,DENIED,bob.lab,10.20.1.12

$ sentinelforge events ingest other_tool.csv --dataset-id csv_demo
Ingested other_tool.csv
  Dataset:      csv_demo
  Records read: 2
  Stored:       2
  Duplicates:   0 (already in the database)
  Invalid:      0
Result: OK
```

The CSV's `TimeCreated`/`AccountName`/`SUCCEEDED`/`DENIED` were mapped to the common
schema (`event_time`/`user`/`success`/`failure`) automatically.

## 6. Database health (connected as the least-privilege app role)
```console
$ sentinelforge db status
Database status
  Server:             PostgreSQL 16.15 (Ubuntu 16.15-0ubuntu0.24.04.1)
  Database:           sentinelforge
  Connected as:       sentinelforge_app
  Superuser:          no
  Schema:             sentinelforge (exists)
  Can use schema:     yes
  Can create tables:  no (expected: no)
Result: OK (application role is connected with least privilege)
```

## 7. Test suite
```console
$ bash scripts/run_tests.sh --integration
[  ok  ] lint passed
165 passed in 2.02s
```
