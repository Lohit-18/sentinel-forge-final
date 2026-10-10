#!/usr/bin/env bash
# End-to-end Phase 2 demonstration: start the lab, generate synthetic events,
# ingest them, show that re-ingesting is a no-op, then run the tests.
#
# Usage: bash scripts/run_demo.sh
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
cd "$SF_ROOT"

step() { printf '\n========== %s ==========\n' "$*"; }

step "1/6  Start the lab database and prepare the app role"
bash "$SF_ROOT/scripts/start_lab.sh"

load_env
activate_venv

step "2/6  Apply database migrations"
sentinelforge db migrate

step "3/6  Generate 2 days of synthetic background activity (seed 1)"
demo_file="$SF_ROOT/data/generated/demo.jsonl"
sentinelforge events generate --dataset-id demo --seed 1 --days 2 --output "$demo_file"

step "4/6  Ingest the events into PostgreSQL"
sentinelforge events ingest "$demo_file" --dataset-id demo

step "5/6  Ingest the SAME file again (every event is a duplicate, so none are stored)"
sentinelforge events ingest "$demo_file" --dataset-id demo

step "6/6  Run the automated tests"
bash "$SF_ROOT/scripts/run_tests.sh" --integration

printf '\n'
ok "demo complete"
