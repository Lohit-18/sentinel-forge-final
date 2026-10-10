-- SentinelForge migration 0001: event storage.
--
-- Each migration is applied once, inside a transaction, by the admin role.
-- The schema_migrations table records which have run.
--
-- All objects are created in the SentinelForge schema (the admin role's
-- search_path points there). The application role already has SELECT/INSERT/
-- UPDATE on new tables via the default privileges set in db/bootstrap.py.

CREATE TABLE IF NOT EXISTS schema_migrations (
    version      text PRIMARY KEY,
    applied_at   timestamptz NOT NULL DEFAULT now()
);

-- One row per import run. Gives every stored event a traceable origin.
CREATE TABLE dataset_imports (
    id               bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    dataset_id       text        NOT NULL,
    source_path      text        NOT NULL,
    started_at       timestamptz NOT NULL DEFAULT now(),
    finished_at      timestamptz,
    records_read     integer     NOT NULL DEFAULT 0,
    records_stored   integer     NOT NULL DEFAULT 0,
    duplicates       integer     NOT NULL DEFAULT 0,
    invalid          integer     NOT NULL DEFAULT 0,
    status           text        NOT NULL DEFAULT 'running'
                     CHECK (status IN ('running', 'completed', 'failed'))
);

-- The normalised event store.
CREATE TABLE security_events (
    id                   bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    -- fingerprint makes duplicate imports a no-op (see events/fingerprint.py).
    fingerprint          char(64)    NOT NULL UNIQUE,
    -- event_time: when it happened. ingested_at: when we received it. Keeping
    -- both lets us measure detection latency and spot delayed log delivery.
    event_time           timestamptz NOT NULL,
    ingested_at          timestamptz NOT NULL DEFAULT now(),
    category             text        NOT NULL,
    action               text        NOT NULL,
    outcome              text        NOT NULL,
    severity             text        NOT NULL,
    source_type          text        NOT NULL,
    source_host          text        NOT NULL,
    source_event_id      text,
    app_user             text,            -- the acting account ("user" is reserved-ish)
    target_user          text,
    src_ip               inet,
    src_port             integer,
    dst_ip               inet,
    dst_port             integer,
    dst_domain           text,
    process_name         text,
    process_path         text,
    parent_process_name  text,
    process_command_line text,
    file_sha256          char(64),
    object_name          text,
    dataset_id           text,
    scenario_id          text,
    import_id            bigint      REFERENCES dataset_imports (id),
    raw                  jsonb       NOT NULL DEFAULT '{}'::jsonb
);

-- Indexes chosen for the queries detection, hunting and the dashboard run:
-- "events for this host/user in this time window", newest first.
CREATE INDEX idx_events_event_time   ON security_events (event_time);
CREATE INDEX idx_events_host_time    ON security_events (source_host, event_time);
CREATE INDEX idx_events_user_time    ON security_events (app_user, event_time)
    WHERE app_user IS NOT NULL;
CREATE INDEX idx_events_category_time ON security_events (category, event_time);
CREATE INDEX idx_events_src_ip_time  ON security_events (src_ip, event_time)
    WHERE src_ip IS NOT NULL;
CREATE INDEX idx_events_dataset      ON security_events (dataset_id);
