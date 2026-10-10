#!/usr/bin/env bash
# Run the SentinelForge test suite.
#
# Usage: bash scripts/run_tests.sh                 # lint + unit tests (no database needed)
#        bash scripts/run_tests.sh --integration   # also run tests against PostgreSQL
#                                                  # (start it first: bash scripts/start_lab.sh)
# Extra arguments after the option are passed to pytest, e.g. -k timestamp
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
cd "$SF_ROOT"
activate_venv

integration=false
if [[ "${1:-}" == "--integration" ]]; then
    integration=true
    shift
fi

info "lint"
bash "$SF_ROOT/scripts/lint.sh"

if [[ "$integration" == true ]]; then
    load_env
    export SF_RUN_INTEGRATION=1
    info "unit + integration tests"
    python -m pytest "$@"
else
    info "unit tests (add --integration to include database tests)"
    python -m pytest -m "not integration" "$@"
fi
