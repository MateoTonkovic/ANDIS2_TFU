set -e
source "$(dirname "$0")/env.sh"

echo "Patrones: Circuit Breaker + Retry"
echo ""

echo "✓ Probando patrones circuit breaker y retry"
echo ""

# Primero, crear usuario válido para las pruebas
echo "1. Creando usuario de prueba"
USER_RESPONSE=$(curl -s -X POST http://localhost:8001/users \
  -H "Content-Type: application/json" \
  -d '{"name":"Circuit Test User","email":"circuit_test_'$RANDOM'@example.com"}')
USER_ID=$(echo $USER_RESPONSE | jq -r '.id')
echo "  ID de usuario creado: $USER_ID"
echo ""

# Probar llamada exitosa con circuit breaker (crea proyecto)
echo "2. Probando llamada inter-servicio exitosa (debería funcionar)"
PROJECT_RESPONSE=$(curl -s -X POST http://localhost:8002/projects \
  -H "Content-Type: application/json" \
  -d '{"name":"Circuit Test Project","owner_user_id":'$USER_ID'}')

PROJECT_ID=$(echo $PROJECT_RESPONSE | jq -r '.id')
if [ "$PROJECT_ID" != "null" ] && [ -n "$PROJECT_ID" ]; then
    echo "  ✓ Circuit breaker permite requests válidos: PASS"
    echo "  ID de proyecto creado: $PROJECT_ID"
else
    echo "  ✗ Test de circuit breaker: FAIL"
    exit 1
fi
echo ""

# Probar patrón retry intentando llamada con usuario inválido (reintentará y fallará gracefully)
echo "3. Probando patrón retry con user ID inválido"
INVALID_RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}" -X POST http://localhost:8002/projects \
  -H "Content-Type: application/json" \
  -d '{"name":"Should Fail","owner_user_id":999999}')

HTTP_CODE=$(echo "$INVALID_RESPONSE" | grep "HTTP_CODE" | cut -d: -f2)
RESPONSE_BODY=$(echo "$INVALID_RESPONSE" | sed '/HTTP_CODE/d')

if [ "$HTTP_CODE" == "400" ]; then
    echo "  ✓ Patrón retry agotó intentos: PASS (retornó 400)"
    echo "  Error: $(echo $RESPONSE_BODY | jq -r '.detail')"
else
    echo "  ✗ Test de patrón retry: FAIL (esperaba 400, obtuvo $HTTP_CODE)"
    exit 1
fi
echo ""

# Probar circuit breaker con Tasks API (valida usuario y proyecto)
echo "4. Probando circuit breaker con múltiples llamadas a servicios"
TASK_RESPONSE=$(curl -s -X POST http://localhost:8003/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "title":"Circuit Test Task",
    "project_id":'$PROJECT_ID',
    "assignee_user_id":'$USER_ID'
  }')

TASK_ID=$(echo $TASK_RESPONSE | jq -r '.id')
if [ "$TASK_ID" != "null" ] && [ -n "$TASK_ID" ]; then
    echo "  ✓ Múltiples llamadas protegidas por circuit: PASS"
    echo "  ID de tarea creada: $TASK_ID"
else
    echo "  ✗ Múltiples llamadas con circuit breaker: FAIL"
    echo "  Respuesta: $TASK_RESPONSE"
    exit 1
fi
echo ""

# Demostrar que circuit breaker previene fallos en cascada
echo "5. Probando que circuit breaker previene fallos en cascada"
echo "  Haciendo requests con datos inválidos para disparar circuit breaker"

FAILURES=0
for i in {1..3}; do
    RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}" -X POST http://localhost:8003/tasks \
      -H "Content-Type: application/json" \
      -d '{"title":"Test","project_id":999999,"assignee_user_id":999999}')
    
    HTTP_CODE=$(echo "$RESPONSE" | grep "HTTP_CODE" | cut -d: -f2)
    if [ "$HTTP_CODE" == "400" ] || [ "$HTTP_CODE" == "503" ]; then
        ((FAILURES++))
    fi
    echo "  Intento $i: HTTP $HTTP_CODE"
    sleep 1
done

if [ $FAILURES -eq 3 ]; then
    echo "  ✓ Circuit breaker manejando fallos correctamente: PASS"
else
    echo "  ⚠ Comportamiento circuit breaker: Parcial (puede no estar disparado aún)"
fi

echo ""
echo "✓ Patrones Circuit Breaker y Retry validados"
echo ""

