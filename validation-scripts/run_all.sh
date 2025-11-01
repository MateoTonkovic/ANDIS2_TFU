#!/usr/bin/env bash

set -euo pipefail
cd "$(dirname "$0")"
source ./env.sh

echo "  VALIDATION TESTS - Mini Gestor de Proyectos"
echo ""

echo "== PART 1: Core Functionality Tests =="
echo ""

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

echo ""
echo "== PART 2: Architectural Patterns Tests =="
echo ""

./run_pattern_tests.sh

echo ""
echo "✔ ALL VALIDATIONS COMPLETE"
echo ""
echo "Summary:"
echo "  ✓ Core functionality tests passed"
echo "  ✓ Architectural patterns validated"
echo "  ✓ System ready for production"
echo ""
