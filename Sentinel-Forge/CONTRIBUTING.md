# Contributing to SentinelForge

Thanks for your interest. SentinelForge is a learning project, so clarity and
tests matter more than cleverness.

## Setup

See [docs/installation.md](docs/installation.md). In short:

```bash
bash scripts/setup.sh
bash scripts/setup_native_db.sh   # or set SF_DB_MODE=docker
bash scripts/start_lab.sh
bash scripts/run_tests.sh --integration
```

## Before you open a pull request

Run the checks locally. CI runs the same ones:

```bash
bash scripts/lint.sh          # Ruff linter and formatter
bash scripts/check_licences.sh
bash scripts/run_tests.sh --integration
```

## Guidelines

- **Write tests.** New behaviour needs a test. Fixing a bug? Add a test that
  fails before your fix and passes after. Never claim tests pass without running
  them.
- **Keep SQL parameterised.** Pass values as parameters; quote identifiers with
  `psycopg.sql`. The application role stays least-privilege.
- **Only synthetic data.** Do not add real logs, credentials, malware samples,
  or exploit code. Example network addresses use the documentation ranges from
  RFC 5737; domains use the reserved names from RFC 2606.
- **Keep dependencies free and open source.** `check_licences.sh` must pass.
- **Explain the "why".** A short comment on a non-obvious choice (a threshold, a
  trade-off) is worth more than a comment restating the code.
- **Keep the CLI honest.** Only register commands that work. Document new ones.

## Commit messages

Describe what changed and why in plain language. Group related changes into one
commit where it helps a reader follow the history.
