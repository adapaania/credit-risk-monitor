#!/bin/sh
# Dedicated project cluster. Never starts a Homebrew/system service.
set -eu
project_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cluster="$project_dir/data/local_postgres"
socket_dir="/tmp/fe513-credit-$(id -u)"
port=55432
database=credit_risk_week2
if [ -z "${PG_BIN:-}" ]; then
    if command -v pg_ctl >/dev/null 2>&1; then
        PG_BIN=$(dirname "$(command -v pg_ctl)")
    elif command -v brew >/dev/null 2>&1; then
        PG_BIN="$(brew --prefix postgresql@16)/bin"
    else
        echo 'Install PostgreSQL 14+ and set PG_BIN to its bin directory.' >&2
        exit 1
    fi
fi
case "${1:-status}" in
    start)
        mkdir -p "$project_dir/data" "$socket_dir"
        chmod 700 "$socket_dir"
        if [ ! -f "$cluster/PG_VERSION" ]; then
            "$PG_BIN/initdb" -D "$cluster" --locale=C -E UTF8 --auth-local=peer --auth-host=reject
        fi
        if ! "$PG_BIN/pg_ctl" -D "$cluster" status >/dev/null 2>&1; then
            "$PG_BIN/pg_ctl" -D "$cluster" -l "$cluster/server.log" \
                -o "-k $socket_dir -p $port -c listen_addresses='' -c unix_socket_permissions=0700" -w start
        fi
        if ! "$PG_BIN/psql" -h "$socket_dir" -p "$port" -d postgres -Atqc \
             "SELECT 1 FROM pg_database WHERE datname = '$database'" | grep -q 1; then
            "$PG_BIN/createdb" -h "$socket_dir" -p "$port" "$database"
        fi
        echo "Project database ready. Export DATABASE_URL=\$(sh scripts/local_db.sh url)"
        ;;
    stop) "$PG_BIN/pg_ctl" -D "$cluster" -m fast -w stop ;;
    status) "$PG_BIN/pg_ctl" -D "$cluster" status ;;
    url) echo "postgresql:///$database?host=$socket_dir&port=$port" ;;
    *) echo 'Usage: sh scripts/local_db.sh start|stop|status|url' >&2; exit 1 ;;
esac
