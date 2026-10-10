#!/usr/bin/env bash
# One-time project setup: virtual environment, dependencies and .env.
# Safe to run again: it never overwrites an existing .env.
#
# Usage: bash scripts/setup.sh
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
cd "$SF_ROOT"

have python3 || die "python3 not found. On Ubuntu: sudo apt install python3 python3-venv"
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' \
    || die "Python 3.11 or newer is required (found $(python3 --version 2>&1))"

# 1. Virtual environment: an isolated folder for this project's packages, so
#    they do not clash with system Python or other projects.
if [[ ! -x .venv/bin/python ]]; then
    info "creating virtual environment in .venv"
    python3 -m venv .venv || die "could not create .venv. On Ubuntu: sudo apt install python3-venv"
else
    ok "virtual environment already exists"
fi
activate_venv

# 2. Dependencies. -e (editable) means code changes take effect without reinstalling.
info "installing SentinelForge and development tools (this can take a minute)"
python -m pip install --quiet --upgrade pip
python -m pip install --quiet -e ".[dev]"
ok "installed: $(sentinelforge --version)"

# 3. Local configuration with random passwords.
if [[ -f .env ]]; then
    ok ".env already exists (left unchanged)"
else
    info "creating .env from .env.example with random passwords"
    umask 077   # the new file is readable by you only
    python - <<'PY'
import secrets
from pathlib import Path

lines = []
for line in Path(".env.example").read_text(encoding="utf-8").splitlines():
    key, sep, value = line.partition("=")
    if sep and key.startswith("SF_") and value == "change-me":
        value = secrets.token_urlsafe(24)  # letters, digits, '-' and '_' only
    lines.append(f"{key}{sep}{value}" if sep else line)
Path(".env").write_text("\n".join(lines) + "\n", encoding="utf-8")
PY
    chmod 600 .env
    ok ".env created (passwords generated; the file is listed in .gitignore)"
fi

echo
ok "setup complete"
info "next steps:"
info "  bash scripts/check_environment.sh"
info "  bash scripts/start_lab.sh"
