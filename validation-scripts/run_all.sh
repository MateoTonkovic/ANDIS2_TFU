#!/usr/bin/env bash

set -euo pipefail
source "$(dirname "$0")/env.sh"

echo "== 1) Smoke =="
./1_smoke.sh

echo "== 2) ACID en Tasks =="
./2_acid_tasks.sh

echo "== 3) Idempotencia en Users =="
./3_idempotency_users.sh

echo "== 4) Stateless + persistencia =="
./4_stateless_restart.sh

echo "== 5) Schemas por servicio =="
./5_schemas.sh

echo "== 6) Concurrencia =="
./6_concurrency_users.sh

echo
echo "✔ Validaciones completas. Presioná CTRL+C para cerrar, o cerrá la ventana."
tail -f /dev/null
