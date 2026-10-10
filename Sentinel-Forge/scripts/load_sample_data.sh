#!/usr/bin/env bash
# Generate synthetic background events and load them into the database.
#
# Usage: bash scripts/load_sample_data.sh [DAYS] [SEED]
#   DAYS  number of days to generate (default: 3)
#   SEED  random seed (default: 1)
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
cd "$SF_ROOT"
load_env
activate_venv

days="${1:-3}"
seed="${2:-1}"
out="$SF_ROOT/data/generated/background_seed${seed}_${days}d.jsonl"

info "generating $days day(s) of synthetic background activity (seed $seed)"
sentinelforge events generate --dataset-id background --seed "$seed" --days "$days" --output "$out"

info "applying database migrations"
sentinelforge db migrate

info "ingesting the generated events"
sentinelforge events ingest "$out" --dataset-id background

ok "sample data loaded"
