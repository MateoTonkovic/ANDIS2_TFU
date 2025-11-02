#!/bin/bash
# Script maestro para ejecutar todas las pruebas de validación de patrones arquitectónicos

set -e

SCRIPT_DIR="$(dirname "$0")"

echo "  SUITE DE VALIDACIÓN DE PATRONES ARQUITECTÓNICOS"
echo ""
echo "Ejecutando pruebas de validación para 7 patrones implementados:"
echo "  Disponibilidad: Health Monitoring, Circuit Breaker, Retry"
echo "  Rendimiento: Cache-Aside, Queue-Based Load Leveling"
echo "  Seguridad: Rate Limiting, Gateway Offloading"
echo ""
echo ""

# Seguimiento de resultados
TOTAL_TESTS=7
PASSED_TESTS=0
FAILED_TESTS=0

# Función para ejecutar un test
run_test() {
    local test_name=$1
    local test_script=$2
    
    echo ""
    echo "Ejecutando: $test_name"
    
    if bash "$SCRIPT_DIR/$test_script"; then
        ((PASSED_TESTS++))
        echo "✓ $test_name: PASÓ"
    else
        ((FAILED_TESTS++))
        echo "✗ $test_name: FALLÓ"
    fi
}

# Ejecutar todas las pruebas de patrones
run_test "Health Endpoint Monitoring" "7_health_monitoring.sh"
run_test "Patrón Cache-Aside" "8_cache_aside.sh"
run_test "Patrones Circuit Breaker + Retry" "9_circuit_breaker_retry.sh"
run_test "Patrón Rate Limiting" "10_rate_limiting.sh"
run_test "Queue-Based Load Leveling" "11_queue_load_leveling.sh"
run_test "Patrón Gateway Offloading" "12_gateway_offloading.sh"
run_test "Patrón Gatekeeper" "13_gatekeeper.sh"

# Resumen
echo ""
echo "  RESUMEN DE TESTS"
echo ""
echo "Total de tests: $TOTAL_TESTS"
echo "Pasados: $PASSED_TESTS"
echo "Fallados: $FAILED_TESTS"
echo ""

if [ $FAILED_TESTS -eq 0 ]; then
    echo "✓ ¡TODOS LOS PATRONES VALIDADOS EXITOSAMENTE!"
    echo ""
    echo "Patrones Implementados:"
    echo "  1. Health Endpoint Monitoring - Health checks detallados"
    echo "  2. Circuit Breaker - Previene fallos en cascada"
    echo "  3. Retry - Exponential backoff para fallos transitorios"
    echo "  4. Rate Limiting - Throttling de requests multi-capa"
    echo "  5. Cache-Aside - Cache Redis para rendimiento"
    echo "  6. Queue-Based Load Leveling - Procesamiento async con RabbitMQ"
    echo "  7. Gateway Offloading - Concerns cross-cutting centralizados"
    echo "  8. Gatekeeper - Autenticación/Autorización centralizada"
    echo ""
    exit 0
else
    echo "✗ Algunos tests fallaron. Por favor revisar la salida anterior."
    exit 1
fi
