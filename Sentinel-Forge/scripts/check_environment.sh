#!/usr/bin/env bash
# Check that this machine has what SentinelForge needs. Changes nothing.
#
# Usage: bash scripts/check_environment.sh
set -uo pipefail   # no -e: we want to report every problem, not stop at the first
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

failures=0
problem() { printf '[ fail ] %s\n' "$*" >&2; failures=$((failures + 1)); }

info "Checking the SentinelForge environment in $SF_ROOT"

# --- Shell and operating system ----------------------------------------------
if (( BASH_VERSINFO[0] >= 4 )); then
    ok "bash ${BASH_VERSION}"
else
    problem "bash 4 or newer is required (found ${BASH_VERSION})"
fi

case "$(uname -s)" in
    Linux)
        if grep -qi microsoft /proc/version 2>/dev/null; then
            ok "running inside WSL (Windows Subsystem for Linux)"
            if [[ "$SF_ROOT" == /mnt/* ]]; then
                info "project is on the Windows drive ($SF_ROOT). This works, but installs and"
                info "tests run faster if the project is inside the WSL home folder (~)."
            fi
        else
            ok "running on Linux"
        fi
        ;;
    Darwin) ok "running on macOS" ;;
    MINGW*|MSYS*|CYGWIN*)
        problem "Git Bash/MSYS is not supported. Please use WSL 2 (see docs/installation.md)" ;;
    *) warn "untested operating system: $(uname -s)" ;;
esac

# --- Line endings: a CRLF script fails with "$'\r': command not found" -------
crlf_files="$(grep -l $'\r' "$SF_ROOT"/scripts/*.sh 2>/dev/null || true)"
if [[ -n "$crlf_files" ]]; then
    problem "these scripts have Windows (CRLF) line endings: $crlf_files"
    info "fix: sed -i 's/\r\$//' scripts/*.sh   (and see .gitattributes)"
else
    ok "scripts use Unix (LF) line endings"
fi

# --- Python ------------------------------------------------------------------
if have python3; then
    if python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)'; then
        ok "$(python3 --version)"
    else
        problem "Python 3.11 or newer is required (found $(python3 --version 2>&1))"
    fi
    if python3 -c 'import ensurepip, venv' 2>/dev/null; then
        ok "python venv module available"
    else
        problem "python venv module missing. On Ubuntu: sudo apt install python3-venv"
    fi
else
    problem "python3 not found. On Ubuntu: sudo apt install python3 python3-venv"
fi

if [[ -x "$SF_ROOT/.venv/bin/python" ]]; then
    ok "virtual environment exists (.venv)"
else
    warn "virtual environment not created yet. Run: bash scripts/setup.sh"
fi

# --- Git ---------------------------------------------------------------------
if have git; then ok "$(git --version)"; else problem "git not found. On Ubuntu: sudo apt install git"; fi

# --- Configuration -----------------------------------------------------------
if [[ -f "$SF_ROOT/.env" ]]; then
    ok ".env exists"
    if grep -Eq '^SF_DB_(ADMIN|APP)_PASSWORD=change-me' "$SF_ROOT/.env"; then
        problem ".env still contains placeholder passwords. Run: bash scripts/setup.sh"
    fi
    perms="$(stat -c '%a' "$SF_ROOT/.env" 2>/dev/null || echo unknown)"
    if [[ "$perms" != "600" && "$perms" != "unknown" ]]; then
        info ".env permissions are $perms; 600 (owner read/write only) is recommended: chmod 600 .env"
    fi
    load_env "$SF_ROOT/.env"
else
    warn ".env not found yet. Run: bash scripts/setup.sh"
fi

# --- PostgreSQL --------------------------------------------------------------
mode="${SF_DB_MODE:-native}"
info "database mode: $mode"
if [[ "$mode" == "docker" ]]; then
    if have docker; then
        ok "$(docker --version)"
        if docker compose version >/dev/null 2>&1; then
            ok "$(docker compose version)"
        else
            problem "docker compose plugin not found. On Ubuntu: sudo apt install docker-compose-plugin"
        fi
        if docker info >/dev/null 2>&1; then
            ok "Docker engine is running"
        else
            problem "the Docker engine is not running (start Docker, or use SF_DB_MODE=native)"
        fi
    else
        problem "docker not found. Set SF_DB_MODE=native in .env (free default) or install Docker"
    fi
elif [[ "$mode" == "native" ]]; then
    if have psql && have pg_isready; then
        ok "$(psql --version)"
        if pg_isready -q -h "${SF_DB_HOST:-127.0.0.1}" -p "${SF_DB_PORT:-5432}"; then
            ok "PostgreSQL is running"
        else
            info "PostgreSQL is not running yet (start_lab.sh starts it)"
        fi
    else
        problem "PostgreSQL not found. On Ubuntu: sudo apt install -y postgresql"
    fi
else
    problem "SF_DB_MODE must be 'docker' or 'native' (found '$mode')"
fi

echo
if (( failures > 0 )); then
    printf '[ fail ] %d problem(s) found. Fix them and run this check again.\n' "$failures" >&2
    exit 1
fi
ok "environment looks good"
