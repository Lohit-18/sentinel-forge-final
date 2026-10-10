#!/usr/bin/env bash
# Static checks: Ruff linter (bugs, security smells, import order) and formatter.
#
# Usage: bash scripts/lint.sh          # check only
#        bash scripts/lint.sh --fix    # apply automatic fixes and formatting
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
cd "$SF_ROOT"
activate_venv

if [[ "${1:-}" == "--fix" ]]; then
    ruff check --fix src tests
    ruff format src tests
else
    ruff check src tests
    ruff format --check src tests
fi
ok "lint passed"
