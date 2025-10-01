#!/usr/bin/env bash
#   - Crear tarea, reiniciar solo el contenedor de tasks-api
#   - Listar tareas y confirmar que la creada sigue estando.

set -euo pipefail
source "$(dirname "$0")/env.sh"

echo "== Crear tarea antes del restart =="
curl -s -X POST "$TASKS/tasks" -H "Content-Type: application/json"   -d '{"title":"Sigue después del restart","project_id":1,"assignee_user_id":1}' | jq .

echo "== Reiniciar solo tasks-api =="
docker compose restart tasks-api

echo "== Listar últimas tareas =="
sleep 2
curl -s "$TASKS/tasks" | jq '.[-5:]'
