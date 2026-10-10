#!/usr/bin/env bash
# First-time setup for PostgreSQL installed natively in WSL/Ubuntu (the free
# default; no Docker needed). Creates the SentinelForge admin role and database.
#
# Usage: bash scripts/setup_native_db.sh
#
# Needs sudo once, because only the "postgres" system user can create roles on a
# fresh install. Safe to run again: existing roles and databases are kept, and
# the admin password is refreshed from .env.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
cd "$SF_ROOT"

load_env
[[ "${SF_DB_MODE:-native}" == "native" ]] \
    || die "SF_DB_MODE is '${SF_DB_MODE}'. This script is only for SF_DB_MODE=native"

have psql || die "PostgreSQL is not installed. Run: sudo apt install -y postgresql"
have sudo || die "sudo is required to create the first database role"

admin_user="${SF_DB_ADMIN_USER:-sentinelforge_admin}"
db_name="${SF_DB_NAME:-sentinelforge}"
admin_password="${SF_DB_ADMIN_PASSWORD:-}"

[[ "$admin_user" =~ ^[a-z_][a-z0-9_]{0,62}$ ]] || die "SF_DB_ADMIN_USER has an invalid name"
[[ "$db_name" =~ ^[a-z_][a-z0-9_]{0,62}$ ]] || die "SF_DB_NAME has an invalid name"
[[ -n "$admin_password" && "$admin_password" != change-me* ]] \
    || die "SF_DB_ADMIN_PASSWORD is missing or a placeholder. Run: bash scripts/setup.sh"
# The password is passed to psql on standard input (never on the command line,
# where other users could see it in the process list). Restricting it to the
# characters setup.sh generates keeps that input unambiguous.
[[ "$admin_password" =~ ^[A-Za-z0-9_-]{16,}$ ]] \
    || die "SF_DB_ADMIN_PASSWORD must be 16+ characters of A-Z a-z 0-9 _ - (setup.sh generates one)"

if ! pg_isready -q -h "${SF_DB_HOST:-127.0.0.1}" -p "${SF_DB_PORT:-5432}"; then
    info "starting the PostgreSQL service (you may be asked for your Linux password)"
    sudo service postgresql start
fi

info "creating or refreshing role '$admin_user' and database '$db_name'"
# \gexec runs each generated statement. format() with %I (identifier) and
# %L (literal) quotes the values safely.
sudo -u postgres psql --quiet -v ON_ERROR_STOP=1 -d postgres <<SQL
\set admin_user '$admin_user'
\set db_name '$db_name'
\set admin_password '$admin_password'

SELECT format('CREATE ROLE %I WITH LOGIN CREATEROLE PASSWORD %L', :'admin_user', :'admin_password')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'admin_user') \gexec

SELECT format('ALTER ROLE %I WITH LOGIN CREATEROLE PASSWORD %L', :'admin_user', :'admin_password') \gexec

SELECT format('CREATE DATABASE %I OWNER %I', :'db_name', :'admin_user')
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = :'db_name') \gexec
SQL

ok "admin role and database are ready"
info "next: bash scripts/start_lab.sh"
