#!/usr/bin/env bash

# smoke test de salud y flujo básico (usuarios - proyectos - tareas)
#   - Disponibilidad de los 3 servicios (/health)
#   - Flujo mínimo: crear user, crear proyecto, crear tarea

set -euo pipefail
source "$(dirname "$0")/env.sh"

echo "== Health =="
curl -s -o /dev/null -w "users %{http_code}\n"    "$USERS/health"
curl -s -o /dev/null -w "projects %{http_code}\n" "$PROJECTS/health"
curl -s -o /dev/null -w "tasks %{http_code}\n"    "$TASKS/health"

echo "== Crear usuario =="
# email random para evitar conflictos previos
EMAIL="alice.$(date +%s)@example.com"
curl -s -X POST "$USERS/users" -H "Content-Type: application/json"   -d "{\"name\":\"Alice\",\"email\":\"$EMAIL\"}" | jq .

echo "== Crear proyecto (owner_user_id=1) =="
curl -s -X POST "$PROJECTS/projects" -H "Content-Type: application/json"   -d '{"name":"TFU","owner_user_id":1}' | jq .

echo "== Crear tarea (project_id=1, assignee_user_id=1) =="
curl -s -X POST "$TASKS/tasks" -H "Content-Type: application/json"   -d '{"title":"Preparar entrega","project_id":1,"assignee_user_id":1}' | jq .
