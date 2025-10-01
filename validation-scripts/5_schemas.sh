#!/usr/bin/env bash
# aislamiento lógico por schemas en la misma DB.

set -euo pipefail
source "$(dirname "$0")/env.sh"

echo "== Tablas por schema =="
psql_db <<'SQL'
SELECT table_schema, table_name
FROM information_schema.tables
WHERE table_schema IN ('users','projects','tasks')
ORDER BY table_schema, table_name;
SQL
