#!/usr/bin/env bash
# ----------------------------------------------------------------------------
# env.sh
# ----------------------------------------------------------------------------
# Propósito: setea URLs de las APIs y define la función psql_db para entrar a la DB.
# Nota: solo exporta la función si estás en bash (zsh no soporta export -f).
# ----------------------------------------------------------------------------

set -euo pipefail

export USERS="http://localhost:8001"
export PROJECTS="http://localhost:8002"
export TASKS="http://localhost:8003"

# helper para ejecutar psql dentro del contenedor de la DB
psql_db () {
  docker compose exec -T db psql -U postgres -d appdb "$@"
}

# exportar solo en bash
if [ -n "${BASH_VERSION:-}" ]; then
  export -f psql_db
fi

echo "Entorno cargado:"
echo "  USERS=$USERS"
echo "  PROJECTS=$PROJECTS"
echo "  TASKS=$TASKS"
