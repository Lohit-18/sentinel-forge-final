# Installation

SentinelForge is free to build and run. Every required tool is free and open source, and nothing needs a paid account, cloud service or subscription. See [cost-and-licences.md](cost-and-licences.md) for the full list.

It runs on Linux, macOS, and Windows through **WSL 2** (Windows Subsystem for Linux, built into Windows 10/11). The Bash scripts do not run in PowerShell, Command Prompt or Git Bash.

## Windows 11 / 10

### 1. Install WSL 2 with Ubuntu (once)

In **PowerShell as Administrator**:

```powershell
wsl --install -d Ubuntu-24.04
```

Restart when asked. Then open **Ubuntu** from the Start menu and create a Linux username and password. Check that it is WSL version 2:

```powershell
wsl -l -v
```

### 2. Install the tools inside Ubuntu

In the **Ubuntu** terminal:

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git unzip postgresql
python3 --version   # needs 3.11 or newer; Ubuntu 24.04 ships 3.12
psql --version      # Ubuntu 24.04 ships PostgreSQL 16
```

### 3. Get the project and set it up

Put the project inside your WSL home folder for the best speed (`~/sentinelforge-soc`), or on the Windows drive (`/mnt/c/Users/<you>/sentinelforge-soc`) if you want to edit it with Windows tools. Both work. The Windows drive is slower for installs and tests.

```bash
cd ~/sentinelforge-soc
bash scripts/setup.sh              # .venv, packages, .env with random passwords
bash scripts/setup_native_db.sh    # first time only: creates the admin role and database (asks for sudo)
bash scripts/check_environment.sh  # reports anything missing
bash scripts/start_lab.sh          # starts PostgreSQL if needed, creates the app role, checks it
bash scripts/run_tests.sh --integration
```

Run scripts with `bash scripts/<name>.sh`. This works even if the Windows drive does not keep the executable permission.

To use the `sentinelforge` command directly, activate the virtual environment first:

```bash
source .venv/bin/activate
sentinelforge --help
```

WSL does not start services automatically. After restarting Windows, `bash scripts/start_lab.sh` starts PostgreSQL again.

## Optional: Docker instead of native PostgreSQL

Docker is **not required**. If you prefer containers, `compose.yaml` runs PostgreSQL 16, and you set `SF_DB_MODE=docker` in `.env`. Two ways to get Docker:

- **Docker Engine inside Ubuntu (free, open source).** Follow Docker's official instructions for installing Docker Engine on Ubuntu, then `sudo apt install docker-compose-plugin`.
- **Docker Desktop for Windows.** Free for personal use, education, non-commercial open-source projects and small businesses. Larger companies need a paid subscription. Check Docker's current terms before relying on it.

Docker Hub limits how many images an anonymous user can download per hour. This lab downloads one image, once.

## Linux and macOS

Install Python 3.11+, git and PostgreSQL 16 with your package manager, then follow step 3. On macOS, `setup_native_db.sh` expects Ubuntu's `postgres` system user. Instead, create the role and database as in the manual steps below.

### Manual database setup (any system)

`\password` asks for the password, so it never appears in your shell history. Paste the `SF_DB_ADMIN_PASSWORD` value from `.env` when prompted:

```bash
sudo -u postgres psql -c "CREATE ROLE sentinelforge_admin WITH LOGIN CREATEROLE"
sudo -u postgres psql -c "\password sentinelforge_admin"
sudo -u postgres createdb -O sentinelforge_admin sentinelforge
```

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `$'\r': command not found` | The script has Windows (CRLF) line endings | `sed -i 's/\r$//' scripts/*.sh`. The repo's `.gitattributes` prevents this for fresh clones |
| `python3 -m venv` fails with `ensurepip is not available` | Ubuntu's venv package is missing | `sudo apt install python3-venv` |
| `PostgreSQL did not start` | Not installed, or the first-time setup was skipped | `sudo apt install -y postgresql`, then `bash scripts/setup_native_db.sh` |
| `password authentication failed for user "sentinelforge_admin"` | `.env` was recreated, so the password changed | Native: `bash scripts/setup_native_db.sh` (refreshes it). Docker: restore the old `.env`, or `bash scripts/stop_lab.sh --delete-data` and start again |
| `password authentication failed for user "sentinelforge_app"` | The app password in `.env` changed | `bash scripts/start_lab.sh` resets it from `.env` |
| `address already in use` / `port is already allocated` | Something else uses port 5432 | Set `SF_DB_PORT=5433` in `.env` (and in the PostgreSQL config for native installs) |
| `SF_DB_APP_PASSWORD is not set` | No `.env`, or the command was run outside the project folder | `cd` into the project and run `bash scripts/setup.sh` |
| `database "sentinelforge" does not exist` | First-time database setup not done | `bash scripts/setup_native_db.sh` |
