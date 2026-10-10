#!/usr/bin/env bash
# Start PostgreSQL, prepare the least-privilege app role, and check the result.
#
# Usage: bash scripts/start_lab.sh
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
cd "$SF_ROOT"

load_env
activate_venv

mode="${SF_DB_MODE:-native}"
host="${SF_DB_HOST:-127.0.0.1}"
port="${SF_DB_PORT:-5432}"

wait_for_postgres() {
    local check=("$@") tries=30
    for ((i = 1; i <= tries; i++)); do
        if "${check[@]}" >/dev/null 2>&1; then
            ok "PostgreSQL is accepting connections"
            return 0
        fi
        sleep 2
    done
    return 1
}

case "$mode" in
    docker)
        have docker || die "docker not found. Use SF_DB_MODE=native (free default) or install Docker"
        docker info >/dev/null 2>&1 || die "the Docker engine is not running"
        info "starting the PostgreSQL container"
        docker compose up -d db
        info "waiting for PostgreSQL (up to 60 seconds)"
        wait_for_postgres docker compose exec -T db \
            pg_isready -U "${SF_DB_ADMIN_USER:-sentinelforge_admin}" -d "${SF_DB_NAME:-sentinelforge}" \
            || die "PostgreSQL did not become ready. See: docker compose logs db"
        ;;
    native)
        have pg_isready || die "pg_isready not found. On Ubuntu: sudo apt install postgresql"
        info "waiting for the local PostgreSQL service at $host:$port"
        if ! pg_isready -q -h "$host" -p "$port"; then
            info "PostgreSQL is not running; starting it (you may be asked for your Linux password)"
            sudo service postgresql start
        fi
        wait_for_postgres pg_isready -h "$host" -p "$port" \
            || die "PostgreSQL did not start. First time? Run: bash scripts/setup_native_db.sh"
        ;;
    *)
        die "SF_DB_MODE must be 'docker' or 'native' (found '$mode')"
        ;;
esac

info "creating or refreshing the application role and schema"
sentinelforge db bootstrap

info "checking the connection as the application role"
sentinelforge db status
