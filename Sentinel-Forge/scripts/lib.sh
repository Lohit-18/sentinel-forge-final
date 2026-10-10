#!/usr/bin/env bash
# Shared helpers for SentinelForge scripts. Other scripts `source` this file;
# it is not meant to be run on its own.

SF_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export SF_ROOT

info() { printf '[ info ] %s\n' "$*"; }
ok()   { printf '[  ok  ] %s\n' "$*"; }
warn() { printf '[ warn ] %s\n' "$*" >&2; }
die()  { printf '[ fail ] %s\n' "$*" >&2; exit 1; }

have() { command -v "$1" >/dev/null 2>&1; }

# Read SF_* variables from .env WITHOUT executing the file.
# `source .env` would run any command hidden in the file; this parser only
# accepts KEY=VALUE lines. Variables already set in the environment win,
# matching how the Python settings loader behaves.
load_env() {
    local file="${1:-$SF_ROOT/.env}"
    [[ -f "$file" ]] || die ".env not found. Run: bash scripts/setup.sh"

    local line key value
    while IFS= read -r line || [[ -n "$line" ]]; do
        line="${line%$'\r'}"                       # tolerate Windows line endings
        [[ "$line" =~ ^[[:space:]]*(#|$) ]] && continue
        if [[ "$line" =~ ^(SF_[A-Z0-9_]+)=(.*)$ ]]; then
            key="${BASH_REMATCH[1]}"
            value="${BASH_REMATCH[2]}"
            if [[ "$value" =~ ^\"(.*)\"$ || "$value" =~ ^\'(.*)\'$ ]]; then
                value="${BASH_REMATCH[1]}"
            fi
            if [[ -z "${!key+set}" ]]; then
                export "$key=$value"
            fi
        else
            warn "ignoring a line in .env that is not an SF_* setting"
        fi
    done < "$file"
}

# Activate the project's virtual environment.
activate_venv() {
    local activate="$SF_ROOT/.venv/bin/activate"
    [[ -f "$activate" ]] || die "virtual environment not found. Run: bash scripts/setup.sh"
    # shellcheck disable=SC1090
    source "$activate"
}
