# Security policy

SentinelForge is a local training lab that uses synthetic data only. It is not
intended to be deployed on the internet or to process real security data.

## Reporting a vulnerability

If you find a security problem in SentinelForge, please open a GitHub issue, or
contact the maintainer privately through their GitHub profile. Please do not
post exploit details publicly until the issue has been addressed.

## Security design of the lab itself

- **Least privilege database access.** The application connects as a role that
  can only `SELECT`, `INSERT` and `UPDATE`. It cannot `CREATE`, `DROP`, `ALTER`,
  `DELETE` or `TRUNCATE`. Schema changes are made by a separate admin role used
  only by setup and migrations.
- **Parameterised SQL.** All queries pass values as parameters. Identifiers
  (role, schema and table names) are quoted with `psycopg.sql`, and configured
  names are validated against a strict pattern.
- **Secrets stay out of source control.** `.env` holds generated passwords, is
  created with owner-only permissions, is listed in `.gitignore`, and is parsed
  (never executed) by the shell scripts. `.env.example` contains placeholders
  only. Passwords are never printed by the CLI or written to logs.
- **Input validation.** Every event is validated against a strict schema before
  storage. Invalid records are rejected, not stored.
- **Local by default.** PostgreSQL listens on `127.0.0.1` only. The future
  dashboard is intended for `localhost`; exposing it more widely would require
  adding authentication first (see `docs/threat-model.md`).
- **Dependencies.** All dependencies are free and open source, checked by
  `bash scripts/check_licences.sh` in CI. Keep them updated.

## What this project is not

SentinelForge does not include malware, exploit code, or tools for attacking
systems. It models the *defensive* workflow of a SOC using generated log data.
