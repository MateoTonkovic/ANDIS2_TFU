#!/usr/bin/env bash
#   - Ejecuta 10 creaciones concurrentes con el email.
#   - Esperable: 1x 201 y 9x 409.
#   - En la base hay sola 1 fila con ese email

set -euo pipefail
source "$(dirname "$0")/env.sh"

E="race.$(date +%s)@example.com"
export E

echo "== Disparar 10 requests concurrentes para $E =="
seq 10 | xargs -I{} -P 10 bash -lc '
  jq -n --arg name "Racer" --arg email "'"$E"'" "{name:\$name,email:\$email}"   | curl -s -o /dev/null -w "%{http_code}\n"       -X POST "$USERS/users" -H "Content-Type: application/json" --data-binary @-
'

echo "== Verificar en DB (debe ser 1) =="
psql_db <<SQL
SELECT COUNT(*) AS user_rows FROM users.users WHERE email='$E';
SQL
