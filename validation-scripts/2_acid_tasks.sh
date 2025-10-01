#!/usr/bin/env bash
# demostramos ACID en Tasks API.
#   - POST /tasks crea Task y TaskActivity en una sola transacción
#   - Verifica en DB que exista la tarea y su actividad asociada

set -euo pipefail
source "$(dirname "$0")/env.sh"

echo "== Crear tarea (ACID) =="
curl -s -X POST "$TASKS/tasks" -H "Content-Type: application/json"   -d '{"title":"Tarea ACID","project_id":1,"assignee_user_id":1}' | jq .

echo "== Verificar en DB =="
psql_db <<'SQL'
SELECT id, title, project_id, assignee_user_id, created_at
FROM tasks.tasks
ORDER BY id DESC
LIMIT 5;

SELECT id, task_id, action, note, created_at
FROM tasks.task_activities
WHERE task_id IN (SELECT id FROM tasks.tasks ORDER BY id DESC LIMIT 5)
ORDER BY id D   ESC;
SQL
