# Cost and licences

**Goal:** SentinelForge can be built, run, tested and published without paying for anything.

## Required (all free and open source)

| Tool | Purpose | Licence | Cost |
|---|---|---|---|
| WSL 2 + Ubuntu | Linux environment on Windows | Part of Windows; Ubuntu is free | Free |
| Python 3.11+ | Application language | PSF | Free |
| PostgreSQL 16 | Database | PostgreSQL Licence | Free |
| Bash, git | Automation, version control | GPL | Free |
| pydantic, pydantic-settings | Validation, settings | MIT | Free |
| psycopg 3 | PostgreSQL driver | LGPL-3.0 | Free (we use it unmodified) |
| pytest, Ruff | Tests, linting | MIT | Free |

Planned later, also free and open source: Streamlit (Apache-2.0), pandas (BSD-3-Clause), scikit-learn (BSD-3-Clause), FastAPI (MIT, only if the optional API is built).

Run `bash scripts/check_licences.sh` to list the licence of every installed Python package. It flags any package that isn't under a well-known open-source licence.

## Free services with conditions

These are free today, but their providers can change the terms, so the project never depends on them to run.

| Service | Used for | Free condition |
|---|---|---|
| GitHub | Hosting the repository | Free for public and private repositories |
| GitHub Actions | Running the tests on every push (`.github/workflows/tests.yml`) | Free for **public** repositories on standard runners. Private repositories get a monthly quota of free minutes |
| Docker Desktop (optional) | Running PostgreSQL in a container | Free for personal use, education, non-commercial open source, and businesses with fewer than 250 employees **and** less than US$10 million annual revenue. Docker Engine on Linux/WSL is free for everyone |
| Docker Hub (optional) | Downloading the `postgres` image | Free, with hourly download limits for anonymous users (we download one image) |

## Not used, to keep the project free

- No commercial SIEM (Splunk, Sentinel, QRadar), cloud hosting or paid threat-intelligence feeds.
- All data is synthetic, so no dataset licence is needed. Third-party datasets will only be added if their licence allows it, and that will be recorded here.
- The dashboard runs on your own computer (`localhost`). Free public hosting is avoided because a SOC dashboard should not be exposed to the internet without proper access control.

Licence and cost terms last checked: October 2026.
