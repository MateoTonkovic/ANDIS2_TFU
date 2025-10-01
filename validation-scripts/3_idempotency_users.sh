#!/usr/bin/env bash
# probar idempotencia/unicidad al crear usuarios.
# Qué valida:
#   - Primera creación = 201
#   - Segunda creación del mismo email -= 409 (conflicto)
#   - En DB: 1 sola fila en users.users y al menos un audit log de CREATE_USER.

set -euo pipefail
source "$(dirname "$0")/env.sh"

EMAIL="bob.$(date +%s)@example.com"

echo "== Create 1 (esperado 201) =="
jq -n --arg name "Bob" --arg email "$EMAIL" '{name:$name,email:$email}' | curl -s -o /dev/null -w "HTTP %{http_code}\n"     -X POST "$USERS/users" -H "Content-Type: application/json" --data-binary @-

echo "== Create 2 (esperado 409) =="
jq -n --arg name "Bob" --arg email "$EMAIL" '{name:$name,email:$email}' | curl -s -o /dev/null -w "HTTP %{http_code}\n"     -X POST "$USERS/users" -H "Content-Type: application/json" --data-binary @-

echo "== Verificar en DB =="
psql_db <<SQL
SELECT COUNT(*) AS total_users FROM users.users WHERE email='$EMAIL';
SELECT id, action, detail, created_at
FROM users.audit_logs
ORDER BY id DESC
LIMIT 5;
SQL
