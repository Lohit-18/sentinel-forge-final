#!/usr/bin/env bash
# Stop the lab database. Your data is kept unless you pass --delete-data.
#
# Usage: bash scripts/stop_lab.sh                # stop, keep data
#        bash scripts/stop_lab.sh --delete-data  # stop and erase the database volume
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
cd "$SF_ROOT"

load_env
delete_data=false
case "${1:-}" in
    "") ;;
    --delete-data) delete_data=true ;;
    -h|--help) sed -n '2,5p' "$0"; exit 0 ;;
    *) die "unknown option: $1 (use --help)" ;;
esac

if [[ "${SF_DB_MODE:-native}" == "native" ]]; then
    info "native mode: SentinelForge does not manage the PostgreSQL service."
    info "to stop it: sudo service postgresql stop"
    exit 0
fi

if [[ "$delete_data" == true ]]; then
    warn "this permanently deletes every event, alert and incident in the lab database."
    read -r -p "Type DELETE to continue: " answer
    [[ "$answer" == "DELETE" ]] || die "cancelled; nothing was deleted"
    docker compose down --volumes
    ok "database stopped and its data volume deleted"
else
    docker compose stop db
    ok "database stopped (data kept; start again with: bash scripts/start_lab.sh)"
fi
